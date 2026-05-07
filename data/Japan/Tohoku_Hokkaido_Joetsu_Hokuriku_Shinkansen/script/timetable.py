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
    """
    🌟 修正：接收 current_url，精確拼接相對路徑[cite: 2]
    """
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
                # ✅ 完美拼接：從目前的 URL 延伸相對路徑[cite: 2]
                variant_urls.add(urljoin(current_url, a_tag['href']))
            elif 'none' not in classes:
                # 藍色運行日期
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
        if not train_div: return None
        
        info = {}
        for th in train_div.find_all('th'):
            label = th.get_text().strip()
            td = th.find_next('td')
            if td:
                if '列車名' in label: info['type_full'] = td.get_text().strip()
                if '列車番号' in label: info['no'] = td.get_text().strip()

        # 排除東海道[cite: 2]
        if any(tk in info.get('type_full','') for tk in ["のぞみ", "ひかり", "こだま"]) or info.get('no','').endswith(('A','K')):
            return None

        # 將 URL 傳入以處理相對路徑
        cur_dates, variants = parse_calendar_logic(soup, url)
        
        stops = []
        for row in train_div.find('table').find_all('tr'):
            cols = row.find_all(['th', 'td'])
            if len(cols) < 2: continue
            sta = clean_station_name(cols[0].get_text())
            time_txt = cols[1].get_text().replace(' ', '')
            
            arr_m = re.search(r'(\d{2}:\d{2})着', time_txt)
            dep_m = re.search(r'(\d{2}:\d{2})[発發发]', time_txt)
            if not (arr_m or dep_m): continue
            
            arr = (int(arr_m.group(1)[:2])*60 + int(arr_m.group(1)[3:])) if arr_m else ""
            dep = (int(dep_m.group(1)[:2])*60 + int(dep_m.group(1)[3:])) if dep_m else ""
            if arr == "" and dep != "": arr = dep
            if dep == "" and arr != "": dep = arr
            stops.append({"sta": sta, "arr": arr, "dep": dep})

        if not cur_dates and not stops: return None

        return {
            "no": info.get('no'),
            "type": re.match(r'([^\d\s]+)', info.get('type_full','')).group(1) if info.get('type_full') else "",
            "dates": cur_dates,
            "data": stops,
            "url": url,
            "variants": variants
        }
    except: return None

# ==========================================
# 🔗 拓樸轉換、併結與輸出
# ==========================================

def apply_coupling_logic(trains):
    """ 計算併結關係 (已修正變體自我併結 Bug) """
    print("\n🔗 正在計算併結關係...")
    for t in trains:
        t["_sched"] = {s["s"][i]: (s["t"][i*2], s["t"][i*2+1]) for s in t["segments"] for i in range(len(s["s"]))}
        t["coupled_with"] = []
        
    for i in range(len(trains)):
        for j in range(i + 1, len(trains)):
            t1, t2 = trains[i], trains[j]
            
            # 🛡️ 防呆 1：絕對不可能自己跟自己（的變體）併結
            if t1["no"] == t2["no"]:
                continue
                
            # 🛡️ 防呆 2：如果不定期列車的行駛日期完全沒有交集，就不可能併結
            if t1["operation"] == "irregular" and t2["operation"] == "irregular":
                if not set(t1.get("dates", [])).intersection(set(t2.get("dates", []))):
                    continue
                    
            # 檢查時間重疊的車站
            overlap = [st for st, time in t1["_sched"].items() if st in t2["_sched"] and t2["_sched"][st] == time]
            if len(overlap) >= 2:
                overlap.sort(key=lambda x: t1["_sched"][x][0])
                split_station = overlap[-1] # 最後一個重合的站就是解連站
                
                # 🛡️ 防呆 3：避免被對方的多個變體重複加入
                if not any(c["train_id"] == t2["no"] for c in t1["coupled_with"]):
                    t1["coupled_with"].append({"train_id": t2["no"], "station_id": split_station, "action": "split"})
                if not any(c["train_id"] == t1["no"] for c in t2["coupled_with"]):
                    t2["coupled_with"].append({"train_id": t1["no"], "station_id": split_station, "action": "split"})
                    
    # 清理暫存欄位
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

def main():
    print(f"🚀 JR 東日本新幹線全量採集啟動 (包含變體追蹤)")
    ENTRY_URL = "https://www.jreast-timetable.jp/timetable/list1039.html"
    processed_urls, all_raw_results = set(), []
    
    res = requests.get(ENTRY_URL, headers=HEADERS)
    soup = BeautifulSoup(res.text, 'html.parser')
    shinkansen_div = soup.find('div', class_='rosentable')
    
    seed_urls = set()
    for a in tqdm(shinkansen_div.find_all('a', class_='fortimeLink'), desc="🔍 掃描路線目錄"):
        if '東海道' in a.parent.parent.get_text(): continue
        try:
            sub_res = requests.get(urljoin(ENTRY_URL, a['href']), headers=HEADERS)
            sub_soup = BeautifulSoup(sub_res.text, 'html.parser')
            for ta in sub_soup.find_all('a', href=re.compile(r'/train/')):
                full_url = urljoin(urljoin(ENTRY_URL, a['href']), ta['href']).replace("www.jreast-timetable.jp", "timetables.jreast.co.jp")
                seed_urls.add(full_url)
        except: continue

    # 深度遞迴掃描變體[cite: 2]
    queue = list(seed_urls)
    while queue:
        new_v = set()
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = {executor.submit(fetch_single_train_detail, url): url for url in queue if url not in processed_urls}
            if not futures: break
            for f in tqdm(as_completed(futures), total=len(futures), desc="🚄 正在抓取時刻與變體"):
                url = futures[f]
                processed_urls.add(url)
                res = f.result()
                if res:
                    all_raw_results.append(res)
                    for v_url in res.get("variants", []):
                        if v_url not in processed_urls: new_v.add(v_url)
        queue = list(new_v)

    # 拓樸轉換
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