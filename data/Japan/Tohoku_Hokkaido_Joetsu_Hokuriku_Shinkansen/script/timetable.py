import requests
from bs4 import BeautifulSoup
import re
import json
import os
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin
from datetime import date, timedelta

# ==========================================
# 🌟 全域設定 (2026/04/20 - 2026/07/31)
# ==========================================
START_DATE = date(2026, 4, 20)
END_DATE = date(2026, 7, 31)

script_dir = os.path.dirname(os.path.abspath(__file__))
system_dir = os.path.dirname(script_dir)
json_dir = os.path.join(system_dir, "json")

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def get_reference_sets():
    weekdays, weekends = set(), set()
    curr = START_DATE
    while curr <= END_DATE:
        d_str = curr.strftime("%Y-%m-%d")
        if curr.weekday() < 5: weekdays.add(d_str)
        else: weekends.add(d_str)
        curr += timedelta(days=1)
    return weekdays, weekends

REF_WEEKDAY, REF_WEEKEND = get_reference_sets()

# ==========================================
# 🔍 核心工具
# ==========================================

def clean_station_name(text):
    text = re.sub(r'\[.*?\]|（.*?）|\(.*?\)|[†*※‡駅]', '', text)
    anomalies = {"東京山区": "東京", "東京都区": "東京", "上野都区": "上野", "仙台仙": "仙台"}
    return anomalies.get(text.strip(), text.strip())

def parse_calendar_logic(soup, current_url):
    current_dates = set()
    variant_urls = set()
    calendar_div = soup.find('div', class_='serviceDayCalendar')
    if not calendar_div: return current_dates, variant_urls

    for table in calendar_div.find_all('table', class_='calendar-month'):
        caption = table.find('caption')
        if not caption: continue
        ym = re.search(r'(\d{4})年(\d{1,2})月', caption.text)
        if not ym: continue
        y, m = int(ym.group(1)), int(ym.group(2))
        
        for td in table.find_all('td'):
            classes = td.get('class', [])
            if 'invalid' in classes: continue
            
            a_tag = td.find('a')
            if a_tag:
                variant_urls.add(urljoin(current_url, a_tag['href']))
            elif 'none' not in classes:
                day_text = td.get_text(strip=True)
                if day_text.isdigit():
                    d = int(day_text)
                    if START_DATE <= date(y, m, d) <= END_DATE:
                        current_dates.add(f"{y}-{m:02d}-{d:02d}")
                        
    return current_dates, list(variant_urls)

def fetch_single_train_detail(url):
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, 'html.parser')
        train_div = soup.find('div', class_='trainlist')
        if not train_div: return []
        
        # 🌟 1. 掃描表頭，抓出這頁所有的車 (名字與番號)
        train_names = []
        train_nos = []
        for tr in train_div.find('table').find_all('tr'):
            th = tr.find('th')
            if not th: continue
            label = th.get_text().strip()
            tds = tr.find_all('td')
            if '列車名' in label:
                train_names = [td.get_text().strip() for td in tds]
            elif '列車番号' in label:
                train_nos = [td.get_text().strip() for td in tds]
        
        if not train_names: return []
        
        # 🌟 2. 透過神將白名單過濾
        VALID_SHINKANSEN_NAMES = [
            "はやぶさ", "はやて", "やまびこ", "なすの",
            "こまち", "つばさ",
            "とき", "たにがわ",
            "かがやき", "はくたか", "あさま", "つるぎ"
        ]
        
        valid_indices = []
        for i, tname in enumerate(train_names):
            tno = train_nos[i] if i < len(train_nos) else ""
            if any(valid_name in tname for valid_name in VALID_SHINKANSEN_NAMES):
                if not (any(tk in tname for tk in ["のぞみ", "ひかり", "こだま"]) or tno.endswith(('A','K'))):
                    valid_indices.append(i)
                    
        if not valid_indices: return []
        
        cur_dates, variants = parse_calendar_logic(soup, url)
        
        stops_by_train = {i: [] for i in valid_indices}
        
        # 🌟 3. 極簡逐站解析 (看到什麼抓什麼，空白直接跳過)
        for row in train_div.find('table').find_all('tr'):
            th = row.find('th')
            if not th: continue
            sta = clean_station_name(th.get_text())
            tds = row.find_all('td')
            
            for i in valid_indices:
                time_idx = i * 2 # 每台車佔 2 個 td (時間、番線)
                if time_idx >= len(tds): continue
                
                time_txt = tds[time_idx].get_text().replace(' ', '').replace('\n', '').strip()
                
                # 如果格子是空的、寫著 || 或 レ，直接跳過這站
                if time_txt in ["", "||", "レ", "==="]:
                    continue 
                    
                # 即使是「┗━分割08:48発」，正規表達式也能精準抓出 08:48發
                arr_m = re.search(r'(\d{2}:\d{2})着', time_txt)
                dep_m = re.search(r'(\d{2}:\d{2})[発發发]', time_txt)
                
                arr = (int(arr_m.group(1)[:2])*60 + int(arr_m.group(1)[3:])) if arr_m else ""
                dep = (int(dep_m.group(1)[:2])*60 + int(dep_m.group(1)[3:])) if dep_m else ""
                
                if arr == "" and dep != "": arr = dep
                if dep == "" and arr != "": dep = arr
                
                if arr != "" or dep != "":
                    stops_by_train[i].append({"sta": sta, "arr": arr, "dep": dep})
                    
        # 🌟 4. 打包所有抓到的車回傳
        results = []
        for i in valid_indices:
            if not cur_dates and not stops_by_train[i]: continue
            
            tname = train_names[i]
            match = re.match(r'([^\d\sa-zA-Z]+)', tname)
            clean_type = match.group(1) if match else tname
            
            results.append({
                "no": train_nos[i] if i < len(train_nos) else "",
                "type": clean_type,
                "dates": cur_dates,
                "data": stops_by_train[i],
                "url": url,
                "variants": variants if i == valid_indices[0] else []
            })
            
        return results
    except Exception as e:
        print(f"解析 {url} 發生錯誤: {e}")
        return []
    
# ==========================================
# 🔗 拓樸轉換、併結與輸出
# ==========================================
def apply_coupling_logic(trains):
    print("\n🔗 正在計算併結關係...")
    for t in trains:
        t["_sched"] = {s["s"][i]: (s["t"][i*2], s["t"][i*2+1]) for s in t["segments"] for i in range(len(s["s"]))}
        t["coupled_with"] = []
        
    for i in range(len(trains)):
        for j in range(i + 1, len(trains)):
            t1, t2 = trains[i], trains[j]
            
            if t1["no"] == t2["no"]: continue
                
            if t1["operation"] == "irregular" and t2["operation"] == "irregular":
                if not set(t1.get("dates", [])).intersection(set(t2.get("dates", []))):
                    continue
                    
            overlap = [st for st, time in t1["_sched"].items() if st in t2["_sched"] and t2["_sched"][st] == time]
            if len(overlap) >= 2:
                overlap.sort(key=lambda x: t1["_sched"][x][0])
                split_station = overlap[-1] 
                
                if not any(c["train_id"] == t2["no"] for c in t1["coupled_with"]):
                    t1["coupled_with"].append({"train_id": t2["no"], "station_id": split_station, "action": "split"})
                if not any(c["train_id"] == t1["no"] for c in t2["coupled_with"]):
                    t2["coupled_with"].append({"train_id": t1["no"], "station_id": split_station, "action": "split"})
                    
    for t in trains:
        del t["_sched"]
        if not t["coupled_with"]: 
            del t["coupled_with"]
            
    return trains

def save_json_per_line(path, data_list):
    with open(path, "w", encoding="utf-8") as f:
        f.write("[\n")
        for i, tr in enumerate(data_list):
            if "dates" in tr: tr["dates"] = sorted(list(tr["dates"]))
            line = json.dumps(tr, ensure_ascii=False, separators=(',', ':'))
            f.write(f"  {line}{',' if i < len(data_list)-1 else ''}\n")
        f.write("]\n")

# ==========================================
# 🚀 主程式
# ==========================================
# ==========================================
# 🚀 主程式 (極速精準優化版)
# ==========================================
def main():
    print(f"🚀 JR 東日本新幹線全量採集啟動 (極速優化版)")
    
    TERMINAL_STATIONS = [
        "1039", # 東京 (下行本陣)
        "350",  # 大宮 (東北 上行 下行)
        "843",  # 新青森 (東北 上行)
        "39",   # 秋田 (秋田 上行)
        "805",  # 新庄 (山形 上行)
        "1137", # 新潟 (上越 上行)
        "913",  # 仙台 (區間車)
        "1565"  # 盛岡 (區間車)
    ]

    processed_urls, all_raw_results = set(), []
    seed_urls = set()

    # 1. 遍歷所有端點站，蒐集所有的列車連結
    for station_id in TERMINAL_STATIONS:
        padded_id = str(station_id).zfill(4)
        entry_url = f"https://www.jreast-timetable.jp/timetable/list{padded_id}.html"
        
        try:
            res = requests.get(entry_url, headers=HEADERS)
            soup = BeautifulSoup(res.content, 'html.parser')
            
            valid_links = []
            
            # 🌟 核心修正：改為先掃描「每一列 (tr)」
            for tr in soup.find_all('tr'):
                row_text = tr.get_text()
                
                # 判斷這列是不是我們要的新幹線
                if '新幹線' in row_text and '東海道' not in row_text:
                    
                    # 抓出這列裡面所有的按鈕 (通常會有 4 個)
                    links_in_row = tr.find_all('a', class_='fortimeLink')
                    
                    # 🌟 終極剪枝法：我們只要前 2 個按鈕 (純文字時刻表)
                    # 後面的「デジタル時刻表」連看都不看，直接丟棄！
                    for a in links_in_row[:2]:
                        valid_links.append(a)
            
            if valid_links:
                for a in tqdm(valid_links, desc=f"🔍 掃描端點站 {padded_id} ({station_id})"):
                    try:
                        sub_res = requests.get(urljoin(entry_url, a['href']), headers=HEADERS)
                        sub_soup = BeautifulSoup(sub_res.content, 'html.parser')
                        for ta in sub_soup.find_all('a', href=re.compile(r'/train/')):
                            full_url = urljoin(urljoin(entry_url, a['href']), ta['href']).replace("www.jreast-timetable.jp", "timetables.jreast.co.jp")
                            seed_urls.add(full_url)
                    except:
                        continue
            else:
                print(f"⚠️ 警告：端點站 {padded_id} 找不到目標路線")
                
        except Exception as e:
            print(f"無法讀取端點站 {padded_id}: {e}")

    print(f"🎯 共收集到 {len(seed_urls)} 個獨立的列車種子連結！準備深度抓取...")
    
    # ... (下面維持原本的 Queue 與 ThreadPoolExecutor 邏輯不變) ...

    # 2. 深度遞迴掃描變體
    queue = list(seed_urls)
    while queue:
        new_v = set()
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = {executor.submit(fetch_single_train_detail, url): url for url in queue if url not in processed_urls}
            if not futures: break
            for f in tqdm(as_completed(futures), total=len(futures), desc="🚄 正在抓取時刻與變體"):
                url = futures[f]
                processed_urls.add(url)
                
                # 🌟 將回傳的陣列展開
                res_list = f.result()
                if res_list:
                    for res in res_list:
                        all_raw_results.append(res)
                        for v_url in res.get("variants", []):
                            if v_url not in processed_urls: new_v.add(v_url)
        queue = list(new_v)

    print("\n🗺️ 正在處理拓樸轉換與分類...")
    topo_path = os.path.join(json_dir, "topology.json")
    with open(topo_path, 'r', encoding='utf-8') as f: topo = json.load(f)
    STA_MAP = {clean_station_name(st["name"]): st["id"] for seg in topo["segments"] for st in seg["stations"]}
    LINE_MAP = {seg["id"]: [clean_station_name(st["name"]) for st in seg["stations"]] for seg in topo["segments"]}

    processed_final = []
    for train in all_raw_results:
        stop_dict = {s["sta"]: (s["arr"], s["dep"]) for s in train["data"]}
        segs = []
        for l_id, l_sts in LINE_MAP.items():
            intersect = [s["sta"] for s in train["data"] if s["sta"] in l_sts]
            if len(intersect) < 2: continue
            s_list, t_list, v_list = [], [], []
            for i, s_name in enumerate(intersect):
                s_list.append(STA_MAP.get(s_name, s_name))
                t_list.extend([stop_dict[s_name][0], stop_dict[s_name][1]])
                v_list.append(0 if i == 0 else (3 if i == len(intersect)-1 else 1))
            segs.append({"id": l_id, "s": s_list, "t": t_list, "v": v_list})
        
        if not segs: continue
        d_set = train["dates"]
        
        if d_set.issuperset(REF_WEEKDAY) and d_set.issuperset(REF_WEEKEND): op = "daily"
        elif d_set.issuperset(REF_WEEKDAY): op = "weekday"
        elif d_set.issuperset(REF_WEEKEND): op = "weekend"
        else: op = "irregular"
        
        item = {"no": train["no"], "type": train["type"].strip(), "operation": op, "segments": segs}
        if op == "irregular": item["dates"] = sorted(list(d_set))
        processed_final.append(item)
        
    processed_final = apply_coupling_logic(processed_final)

    # 檔案分流與精確過濾
    wd_final, we_final = [], []
    for t in processed_final:
        if t["operation"] in ["daily", "weekday"]:
            wd_final.append(t)
        elif t["operation"] == "irregular":
            valid_wd = [d for d in t.get("dates", []) if d in REF_WEEKDAY]
            if valid_wd:
                new_t = t.copy()
                new_t["dates"] = valid_wd
                wd_final.append(new_t)
        
        if t["operation"] in ["daily", "weekend"]:
            we_final.append(t)
        elif t["operation"] == "irregular":
            valid_we = [d for d in t.get("dates", []) if d in REF_WEEKEND]
            if valid_we:
                new_t = t.copy()
                new_t["dates"] = valid_we
                we_final.append(new_t)

    output_dir = os.path.join(json_dir, "timetable")
    os.makedirs(output_dir, exist_ok=True)
    save_json_per_line(os.path.join(output_dir, "timetable_weekday.json"), wd_final)
    save_json_per_line(os.path.join(output_dir, "timetable_holiday.json"), we_final)

    print(f"\n🎉 採集完成！平日：{len(wd_final)} 班次，假日：{len(we_final)} 班次")

if __name__ == "__main__":
    main()