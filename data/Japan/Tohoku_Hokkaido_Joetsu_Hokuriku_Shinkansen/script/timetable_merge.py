import requests
from bs4 import BeautifulSoup
import re
import json
import os
import urllib.request
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin
from datetime import date, timedelta
import unicodedata
from collections import OrderedDict

# ==========================================
# 🌟 全域路徑與設定
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
# 🛠️ 共用字串與時間處理工具
# ==========================================
def clean_station_name(text):
    text = re.sub(r'\[.*?\]|（.*?）|\(.*?\)|[†*※‡駅]', '', text)
    anomalies = {"東京山区": "東京", "東京都区": "東京", "上野都区": "上野", "仙台仙": "仙台"}
    return anomalies.get(text.strip(), text.strip())

def to_minutes(hh_mm):
    """將 HH:MM 字串轉換為當天的絕對分鐘數"""
    if not hh_mm: return ""
    try:
        h, m = map(int, hh_mm.split(':'))
        return h * 60 + m
    except: return ""

def clean_text(text):
    """清除 HTML 標籤與不必要的空白"""
    is_split = "分割" in text
    is_through = "直通" in text
    text = re.sub(r'<[^>]+>', '', text)
    cleaned = "".join(text.split())
    if is_split: return "分割" + cleaned.replace("分割", "")
    if is_through: return "直通" + cleaned.replace("直通", "")
    return cleaned

# ==========================================
# 🚂 引擎 A：JR 東日本全量爬蟲
# ==========================================
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
        
        table = train_div.find('table')
        train_names, train_nos, op_dates_text = [], [], {}
        coupling_info_raw = {}
        
        for tr in table.find_all('tr'):
            th = tr.find('th')
            if not th: continue
            label = th.get_text().strip()
            tds = tr.find_all('td')
            
            if '列車名' in label: train_names = [td.get_text().strip() for td in tds]
            elif '列車番号' in label: train_nos = [td.get_text().strip() for td in tds]
            elif '運転日' in label: 
                for idx, td in enumerate(tds): op_dates_text[idx] = td.get_text().strip()
            elif '併結運転' in label:
                for idx, td in enumerate(tds): coupling_info_raw[idx] = td.get_text().strip()
        
        if not train_names: return []
        
        VALID_SHINKANSEN_NAMES = ["はやぶさ", "はやて", "やまびこ", "なすの", "こまち", "つばさ", "とき", "たにがわ", "かがやき", "はくたか", "あさま", "つるぎ"]
        valid_indices = []
        for i, tname in enumerate(train_names):
            tno = train_nos[i] if i < len(train_nos) else ""
            if any(valid_name in tname for valid_name in VALID_SHINKANSEN_NAMES):
                if not (any(tk in tname for tk in ["のぞみ", "ひかり", "こだま"]) or tno.endswith(('A','K'))):
                    valid_indices.append(i)
                    
        if not valid_indices: return []
        
        page_dates, variants = parse_calendar_logic(soup, url)
        final_dates_by_train = {}
        for i in valid_indices:
            if page_dates:
                final_dates_by_train[i] = set(page_dates)
            else:
                op_text = op_dates_text.get(i, "")
                if "土曜・休日" in op_text: final_dates_by_train[i] = set(REF_WEEKEND)
                elif "平日" in op_text: final_dates_by_train[i] = set(REF_WEEKDAY)
                else: final_dates_by_train[i] = REF_WEEKDAY.union(REF_WEEKEND)

        stops_by_train = {i: [] for i in valid_indices}
        for row in table.find_all('tr'):
            th = row.find('th')
            tds = row.find_all('td')
            if not th or len(tds) == 0: continue
            
            sta = clean_station_name(th.get_text())
            for i in valid_indices:
                time_idx = i * 2 
                if time_idx >= len(tds): continue
                
                time_txt = tds[time_idx].get_text(separator="\n").strip()
                if not time_txt or any(x in time_txt for x in ["||", "レ", "==="]): continue
                    
                is_direct = "直通" in time_txt or "└" in time_txt
                times = re.findall(r'\d{2}:\d{2}', time_txt)
                
                if not times: continue
                
                arr_str = times[0]
                dep_str = times[-1]
                arr = int(arr_str[:2]) * 60 + int(arr_str[3:])
                dep = int(dep_str[:2]) * 60 + int(dep_str[3:])
                
                stops_by_train[i].append({"sta": sta, "arr": arr, "dep": dep, "is_direct": is_direct})

        results = []
        for i in valid_indices:
            if not stops_by_train[i]: continue
            tname = train_names[i]
            match = re.match(r'([^\d\sa-zA-Z]+)', tname)
            clean_type = match.group(1) if match else tname
            
            train_obj = {
                "no": train_nos[i],
                "type": clean_type,
                "dates": final_dates_by_train[i],
                "data": stops_by_train[i],
                "url": url,
                "variants": variants if i == valid_indices[0] else [],
                "coupled_with": []
            }
            
            info_text = coupling_info_raw.get(i, "")
            if "併結" in info_text:
                info_text_half = unicodedata.normalize('NFKC', info_text)
                target_no_match = re.search(r'(\d+[A-Z])', info_text_half)
                if target_no_match:
                    train_obj["coupled_with"].append({
                        "train_id": target_no_match.group(1),
                        "action": "split"
                    })
            results.append(train_obj)
            
        for idx in range(len(results) - 1):
            t_curr = results[idx]
            t_next = results[idx + 1]
            direct_stop = next((s for s in t_curr["data"] if s.get("is_direct")), None)
            if direct_stop:
                link_station = direct_stop["sta"]
                t_curr["coupled_with"].append({"train_id": t_next["no"], "station_id": link_station, "action": "direct"})
                t_next["coupled_with"].append({"train_id": t_curr["no"], "station_id": link_station, "action": "direct"})
                
        for t in results:
            for s in t["data"]: s.pop("is_direct", None)
            if not t["coupled_with"]: del t["coupled_with"]
            
        return results
    except Exception as e:
        return []

def fetch_jreast_data():
    print("\n🚂 [引擎 A] 啟動 JR 東日本全量爬蟲引擎...")
    TERMINAL_STATIONS = ["1039", "350", "0854", "39", "867", "1137", "1085", "285", "913", "1565"]
    processed_urls, all_raw_results, seed_urls = set(), [], set()

    for station_id in tqdm(TERMINAL_STATIONS, desc="🔍 掃描端點站"):
        entry_url = f"https://www.jreast-timetable.jp/timetable/list{str(station_id).zfill(4)}.html"
        try:
            res = requests.get(entry_url, headers=HEADERS)
            soup = BeautifulSoup(res.content, 'html.parser')
            valid_links = []
            for tr in soup.find_all('tr'):
                if '新幹線' in tr.get_text() and '東海道' not in tr.get_text():
                    for a in tr.find_all('a', class_='fortimeLink')[:2]:
                        valid_links.append(a)
            
            for a in valid_links:
                try:
                    sub_res = requests.get(urljoin(entry_url, a['href']), headers=HEADERS)
                    sub_soup = BeautifulSoup(sub_res.content, 'html.parser')
                    for ta in sub_soup.find_all('a', href=re.compile(r'/train/')):
                        seed_urls.add(urljoin(urljoin(entry_url, a['href']), ta['href']).replace("www.jreast-timetable.jp", "timetables.jreast.co.jp"))
                except: continue
        except Exception: continue
                
    queue = list(seed_urls)
    while queue:
        new_v = set()
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = {executor.submit(fetch_single_train_detail, url): url for url in queue if url not in processed_urls}
            if not futures: break
            for f in tqdm(as_completed(futures), total=len(futures), desc="🚄 抓取 JR 東日本時刻"):
                url = futures[f]
                processed_urls.add(url)
                res_list = f.result()
                if res_list:
                    for res in res_list:
                        all_raw_results.append(res)
                        for v_url in res.get("variants", []):
                            if v_url not in processed_urls: new_v.add(v_url)
        queue = list(new_v)
        
    return all_raw_results

# ==========================================
# 🌊 引擎 B：JR 西日本 (Odekake Net) 補齊北陸
# ==========================================
def fetch_odekake_hokuriku(target_date_str):
    print("\n🌊 [引擎 B] 啟動 JR 西日本 (Odekake Net) 補齊引擎...")
    route_file_path = r"D:\鐵路\TRA_Visualization\data\Japan\Tokkaido_Sanyo_Kyushu_Shinkansen\json\station_route_shinkansen.json"
    
    if not os.path.exists(route_file_path):
        print(f"❌ 找不到 {route_file_path}，跳過 JR 西日本資料。")
        return []
        
    with open(route_file_path, 'r', encoding='utf-8') as f: routes = json.load(f)
        
    train_entries = []
    seen_pairs = set()
    
    for route_obj in routes:
        route_name = route_obj.get("route", "")
        # 避免 JSON 中混入在來線導致抓錯
        if "北陸" not in route_name or "本線" in route_name: continue 
        r_id = route_obj.get("id")
        
        url = f"https://timetable.jr-odekake.net/station-timetable/{r_id}?date={target_date_str}"
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req) as response:
                html_content = response.read().decode('utf-8')
                for t_id in re.findall(r'href="/train-timetable/(\d+)\?date=', html_content):
                    if t_id not in seen_pairs:
                        seen_pairs.add(t_id)
                        train_entries.append(t_id)
        except Exception: continue

    odekake_results = []
    
    for t_id in tqdm(train_entries, desc="🚄 抓取 JR 西日本時刻"):
        url = f"https://timetable.jr-odekake.net/train-timetable/{t_id}"
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req) as response:
                html = response.read().decode('utf-8')

            details_match = re.search(r'<tbody class="train-details">(.*?)</tbody>', html, re.DOTALL)
            if not details_match: continue

            rows = re.findall(r'<tr>(.*?)</tr>', details_match.group(1), re.DOTALL)
            first_row_tds = re.findall(r'<td.*?>(.*?)</td>', rows[0], re.DOTALL)
            num_trains = len(first_row_tds)

            page_trains = [OrderedDict() for _ in range(num_trains)]

            for row in rows:
                th_match = re.search(r'<th.*?>(.*?)</th>', row, re.DOTALL)
                if not th_match: continue
                key = clean_text(th_match.group(1))
                tds = re.findall(r'<td.*?>(.*?)</td>', row, re.DOTALL)
                for i in range(min(len(tds), num_trains)):
                    page_trains[i][key] = clean_text(tds[i])

            time_match = re.search(r'<tbody class="time-details">(.*?)</tbody>', html, re.DOTALL)
            if time_match:
                time_rows = re.findall(r'<tr>(.*?)</tr>', time_match.group(1), re.DOTALL)
                for row in time_rows:
                    sta_match = re.search(r'<td class="cell-fixed">(.*?)</td>', row, re.DOTALL)
                    if not sta_match: continue
                    sta_name = clean_station_name(clean_text(sta_match.group(1)))
                    data_cells = re.findall(r'<td.*?>(.*?)</td>', row, re.DOTALL)[1:]
                    
                    for i in range(num_trains):
                        cell_idx = i * 2
                        if cell_idx >= len(data_cells): continue
                        raw_cell = data_cells[cell_idx]
                        
                        if '<div>レ</div>' in raw_cell or '<div>||</div>' in raw_cell: continue
                            
                        # 完美運作的時間解析邏輯
                        arr_val, dep_val = "", ""
                        times = re.findall(r'(\d{2}:\d{2})', raw_cell)
                        
                        if times:
                            if len(times) >= 2:
                                arr_val = to_minutes(times[0])
                                dep_val = to_minutes(times[-1])
                            else: 
                                if '着' in raw_cell:
                                    arr_val = to_minutes(times[0])
                                else:
                                    dep_val = to_minutes(times[0])
                                    arr_val = dep_val
                        
                        if arr_val != "" or dep_val != "" or "分割" in raw_cell or "直通" in raw_cell:
                            entry_data = {"sta": sta_name, "arr": arr_val, "dep": dep_val}
                            if "data" not in page_trains[i]: page_trains[i]["data"] = []
                            page_trains[i]["data"].append(entry_data)

            for pt in page_trains:
                if not pt.get("data"): continue
                
                t_no = pt.get("列車番号", "")
                
                # 🌟 致命錯誤修正：絕對優先抓取「列車名」！
                t_name = pt.get("列車名", "")
                if not t_name: t_name = pt.get("列車", "")
                
                match = re.match(r'([^\d\sa-zA-Z]+)', t_name)
                clean_type = match.group(1) if match else t_name
                
                VALID_HOKURIKU = ["かがやき", "はくたか", "あさま", "つるぎ"]
                if not any(v in clean_type for v in VALID_HOKURIKU): continue
                
                odekake_results.append({
                    "no": t_no,
                    "type": clean_type,
                    "dates": REF_WEEKDAY.union(REF_WEEKEND),
                    "data": pt["data"],
                    "url": url,
                    "variants": [],
                    "coupled_with": []
                })

        except Exception as e:
            continue

    return odekake_results

# ==========================================
# 🔗 拓樸轉換、併結與輸出
# ==========================================
def apply_coupling_logic(trains):
    for t in trains:
        t.setdefault("coupled_with", [])
        t["_sched"] = {s["s"][i]: (s["t"][i*2], s["t"][i*2+1]) for s in t["segments"] for i in range(len(s["s"]))}
            
    for i in range(len(trains)):
        for c in trains[i].get("coupled_with", []):
            if c["action"] != "split": continue 
            if "station_id" in c: continue 
            
            partner = next((pt for pt in trains if pt["no"] == c["train_id"]), None)
            if not partner: continue
            
            if not any(pc["train_id"] == trains[i]["no"] for pc in partner["coupled_with"]):
                partner["coupled_with"].append({"train_id": trains[i]["no"], "action": "split"})
            
            overlap = []
            for st, (arr1, dep1) in trains[i]["_sched"].items():
                if st in partner["_sched"]:
                    arr2, dep2 = partner["_sched"][st]
                    if abs(dep1 - dep2) <= 3 or abs(arr1 - arr2) <= 3:
                        overlap.append(st)
                        
            if len(overlap) >= 1:
                overlap.sort(key=lambda x: trains[i]["_sched"][x][1])
                first_over = overlap[0]
                last_over = overlap[-1]
                
                digits = re.findall(r'\d+', trains[i]["no"])
                is_downbound = int(digits[-1]) % 2 != 0 if digits else True
                
                junction = last_over if is_downbound else first_over
                    
                c["station_id"] = junction
                for pc in partner["coupled_with"]:
                    if pc["train_id"] == trains[i]["no"]:
                        pc["station_id"] = junction
                
    for t in trains:
        if "_sched" in t: del t["_sched"]
        t["coupled_with"] = [c for c in t["coupled_with"] if "station_id" in c or c["action"] == "direct"]
        if not t["coupled_with"]: del t["coupled_with"]
            
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
# 🚀 整合主程式 (終極雙引擎版)
# ==========================================
def main():
    target_date_str = START_DATE.strftime("%Y%m%d")
    print(f"🚀 開始執行全網合併採集 (JR東 + JR西)")
    
    # 1. 雙引擎同時啟動，各自取得資料
    east_trains = fetch_jreast_data()
    west_trains = fetch_odekake_hokuriku(target_date_str)
    
    # 2. 嚴謹合併：利用列車編號 (Train No.) 去重，確保跨區不重疊
    all_raw_results = east_trains.copy()
    existing_nos = {t["no"] for t in all_raw_results}
    
    added_count = 0
    for ot in west_trains:
        if ot["no"] not in existing_nos:
            all_raw_results.append(ot)
            existing_nos.add(ot["no"])
            added_count += 1
            
    print(f"\n✨ 合併完畢，總計 {len(all_raw_results)} 班車次 (從 JR 西日本補齊 {added_count} 班)。")

    # 3. 讀取 topology 並進行 Segment 映射
    print("🗺️ 正在處理拓樸轉換與分類...")
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
        
        item = {
            "no": train["no"], 
            "type": train["type"].strip(), 
            "operation": op, 
            "segments": segs
        }
        
        if "coupled_with" in train:
            item["coupled_with"] = train["coupled_with"]
            
        if op == "irregular": 
            item["dates"] = sorted(list(d_set))
            
        processed_final.append(item)
        
    print("🔗 正在執行全量關聯優化 (時空拓樸純淨版)...")
    processed_final = apply_coupling_logic(processed_final)

    # 4. 檔案分流與精確過濾
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

    # 5. 輸出存檔
    output_dir = os.path.join(json_dir, "timetable")
    os.makedirs(output_dir, exist_ok=True)
    save_json_per_line(os.path.join(output_dir, "timetable_weekday.json"), wd_final)
    save_json_per_line(os.path.join(output_dir, "timetable_holiday.json"), we_final)

    print(f"\n🎉 完美大功告成！\n👉 平日：{len(wd_final)} 班次\n👉 假日：{len(we_final)} 班次")

if __name__ == "__main__":
    main()