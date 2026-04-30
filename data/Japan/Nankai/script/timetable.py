import os, requests, time, json
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})

def norm_st(name):
    return name.replace("ヶ", "ケ").replace("・", "･").replace(" ", "").strip()

def time_to_minutes(time_str, prev_mins=0):
    if not time_str or time_str in ("∥", "−", "-"): return None
    try:
        time_str = time_str.replace("：", ":")
        h, m = map(int, time_str.split(":"))
        mins = h * 60 + m
        while mins < prev_mins - 300: mins += 24 * 60
        return mins
    except:
        return None

def time_to_minutes_for_sort(time_str):
    if not time_str or time_str in ("∥", "−", "-", "", "↓"): return 9999
    try:
        h, m = map(int, time_str.replace("：", ":").split(":"))
        if h < 4: h += 24
        return h * 60 + m
    except:
        return 9999

def get_tx_from_url(url):
    qs = parse_qs(urlparse(url).query)
    return qs.get('tx', [None])[0]

PREFIX_LIST = [
    ("ラα", "特急ラピートα"), ("ラβ", "特急ラピートβ"), ("ラピ", "特急ラピート"), ("特サ", "特急サザン"), 
    ("サザン", "特急サザン"), ("特泉", "特急泉北ライナー"), ("泉北ライナー", "特急泉北ライナー"), ("泉北", "特急泉北ライナー"), 
    ("天空", "観光列車「天空」"), ("特高", "特急こうや"), ("こうや", "特急こうや"), ("こう", "特急こうや"),       
    ("特林", "特急りんかん"), ("りんかん", "特急りんかん"), ("りん", "特急りんかん"), ("空急", "空港急行"), 
    ("区急", "区間急行"), ("快急", "快速急行"), ("準急", "準急"), ("急行", "急行"), ("各停", "區間"), 
    ("特急", "特急"), ("普通", "區間")
]

@lru_cache(maxsize=2048)
def get_soup(url, retries=3):
    for i in range(retries):
        try:
            time.sleep(0.05) 
            resp = SESSION.get(url, timeout=20)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")
        except: time.sleep((i + 1) * 2)
    return BeautifulSoup("", "html.parser")

def extract_t7_from_t5(t5_url):
    soup = get_soup(t5_url)
    t7_list = []
    for a in soup.select('a[href*="T7?"]'):
        link = urljoin(t5_url, a["href"])
        tx = get_tx_from_url(link)
        if not tx: continue
        
        qs = parse_qs(urlparse(link).query)
        dw = qs.get("dw", ["0"])[0]
        day = "平日" if dw == "0" else "土休日"
        
        btn_text = a.get_text(" ", strip=True).replace("(平日)", "").replace("(土休日)", "").strip()
        t_type = "區間" # 預設為區間車
        for abbr, full_name in PREFIX_LIST:
            if btn_text.startswith(abbr):
                t_type = full_name
                break
                
        t7_list.append({"tx": tx, "url": link, "day": day, "type": t_type})
    return t7_list

def fetch_train_details(t7_dict):
    soup = get_soup(t7_dict["url"])
    table = soup.select_one("#ekt")
    stops = {}
    if not table: return t7_dict["tx"], stops
    
    for tr in table.select("tr"):
        tds = tr.select("td")
        if len(tds) == 3 and (st := tds[0].text.strip()) != "停車駅":
            st = norm_st(st)
            stops[st] = {
                "arrival": tds[1].text.strip() or "−",
                "departure": tds[2].text.strip() or "−"
            }
    return t7_dict["tx"], stops

def main():
    # 🌟 自動精準定位輸出與讀取資料夾
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_dir = os.path.join(os.path.dirname(script_dir), "json")
    output_dir = os.path.join(json_dir, "timetable")
    topology_path = os.path.join(json_dir, "topology.json")
    
    os.makedirs(output_dir, exist_ok=True)
    
    json_path_weekday = os.path.join(output_dir, "timetable_weekday.json")
    json_path_holiday = os.path.join(output_dir, "timetable_holiday.json")

    # ==========================================
    # 🌟 新增：動態讀取 topology.json，不再手寫站名！
    # ==========================================
    print("0. 正在讀取並解析 topology.json...")
    if not os.path.exists(topology_path):
        print(f"❌ 嚴重錯誤：找不到 topology.json！請先執行爬取里程的程式。路徑: {topology_path}")
        return

    with open(topology_path, 'r', encoding='utf-8') as f:
        topology_data = json.load(f)

    # 動態建立 MASTER_LINES, LINE_ID_MAPPING 和 STATION_ID_MAP
    MASTER_LINES = {}
    LINE_ID_MAPPING = {}
    STATION_ID_MAP = {} # 🌟 新增：站名轉 ID 的字典
    
    for segment in topology_data.get("segments", []):
        line_id = segment.get("id")
        line_name = segment.get("name")
        
        station_names = []
        for st in segment.get("stations", []):
            st_name = norm_st(st.get("name"))
            st_id = st.get("id")
            station_names.append(st_name)
            STATION_ID_MAP[st_name] = st_id # 🌟 建立對應：例如 "難波" -> "NK01"
            
        MASTER_LINES[line_name] = station_names
        LINE_ID_MAPPING[line_name] = line_id
    
    for segment in topology_data.get("segments", []):
        line_id = segment.get("id")
        line_name = segment.get("name")
        # 依序抓出該路線的所有站名，並進行正規化 (確保和時刻表抓到的名字格式一致)
        station_names = [norm_st(st.get("name")) for st in segment.get("stations", [])]
        
        MASTER_LINES[line_name] = station_names
        LINE_ID_MAPPING[line_name] = line_id
        
    print(f"  ✅ 成功載入 {len(MASTER_LINES)} 條路線設定！\n")
    # ==========================================

    print("1. 正在從核心發車站收集所有時刻表目錄...")
    CORE_STATION_URLS = [
        "namba", "shinimamiya", "tengachaya", "suminoe", "sakai", "haruki", "kishiwada", "izumisano", "hagurazaki", "tarui", "ozaki", "misakikoen", "wakayamashi", "kansaiairport",
        "hagoromo", "takashinohama", "tanagawa", "kinokawa", "kada", "wakayamako",
        "sakaihigashi", "nakamozu", "chiyoda", "kawachinagano", "mikkaichicho", "rinkandenentoshi", "hashimoto", "koyashita", "gokurakubashi", "koyasan",
        "izumichuo", "komyoike", "shiomibashi", "kishinosatotamade"
    ]
    st_urls = [f"https://www.nankai.co.jp/traffic/station/{sid}.html" for sid in CORE_STATION_URLS]

    t5_urls = set()
    with ThreadPoolExecutor(max_workers=10) as executor:
        futs = {executor.submit(get_soup, url): url for url in st_urls}
        for i, f in enumerate(as_completed(futs), 1):
            print(f"\r  掃描車站 T5 目錄: {i}/{len(st_urls)}", end="", flush=True)
            soup = f.result()
            st_url = futs[f]
            for a in soup.select('a[href*="/pc/T5?"]'):
                t5_urls.add(urljoin(st_url, a["href"]))
    print()

    print(f"2. 正在提取 {len(t5_urls)} 個目錄中的所有車次...")
    t7_pool = {}
    with ThreadPoolExecutor(max_workers=15) as executor:
        futs = {executor.submit(extract_t7_from_t5, t5): t5 for t5 in t5_urls}
        for f in as_completed(futs):
            for t_dict in f.result():
                if t_dict["tx"] not in t7_pool:
                    t7_pool[t_dict["tx"]] = t_dict

    print(f"3. 準備下載 {len(t7_pool)} 班獨立列車資料...")
    with ThreadPoolExecutor(max_workers=15) as executor:
        futs = {executor.submit(fetch_train_details, t_dict): t_dict["tx"] for t_dict in t7_pool.values()}
        for i, f in enumerate(as_completed(futs), 1):
            print(f"\r  下載進度: {i}/{len(t7_pool)}", end="", flush=True)
            tx, stops = f.result()
            t7_pool[tx]["stops"] = stops
    print("\n✅ 所有列車資料下載完成！\n")

    print("4. 🌟 正在完美建構相容 TRA 的 Segments JSON 格式...")
    trains_by_tx = {}
    global_train_counter = 1001

    for tx, t_info in t7_pool.items():
        stops = t_info.get("stops", {})
        if not stops: continue
        
        t_stops_order = list(stops.keys())
        
        if tx not in trains_by_tx:
            trains_by_tx[tx] = {
                "no": str(global_train_counter),
                "type": t_info["type"],
                "drive": t_info["day"],
                "segments": []
            }
            global_train_counter += 1
            
        for line_name, line_stations in MASTER_LINES.items():
            intersect = [st for st in t_stops_order if st in line_stations]
            if len(intersect) < 2: continue
            
            idx_first = line_stations.index(intersect[0])
            idx_last = line_stations.index(intersect[-1])
            
            ordered_stations = line_stations if idx_first < idx_last else line_stations[::-1]
            
            s_list = []
            t_list = []
            v_list = []
            p_mins = 0
            
            intersect_in_order = [s for s in ordered_stations if s in stops]
            
            for i, st in enumerate(intersect_in_order):
                d = stops[st]
                arr_str = d.get("arrival", "−")
                dep_str = d.get("departure", "−")
                
                am = time_to_minutes(arr_str, p_mins)
                if am: p_mins = am
                dm = time_to_minutes(dep_str, p_mins)
                if dm: p_mins = dm
                
                final_am = am if am is not None else dm
                final_dm = dm if dm is not None else am
                
                if final_am is None or final_dm is None: continue
                
                v_val = 1
                if i == 0: v_val = 0
                elif i == len(intersect_in_order) - 1: v_val = 3
                
                # 🌟 使用官方代碼作為 s 陣列的值 (若找不到則退回用站名)
                s_list.append(STATION_ID_MAP.get(st, st))
                t_list.extend([final_am, final_dm])
                v_list.append(v_val)

            if s_list:
                segment = {
                    "id": LINE_ID_MAPPING.get(line_name, "unknown"),
                    "s": s_list,
                    "t": t_list,
                    "v": v_list
                }
                trains_by_tx[tx]["segments"].append(segment)

    flat_json_output = list(trains_by_tx.values())

    weekday_data = [t for t in flat_json_output if t.get("drive") == "平日"]
    holiday_data = [t for t in flat_json_output if t.get("drive") == "土休日"]

    for t in weekday_data: t.pop("drive", None)
    for t in holiday_data: t.pop("drive", None)

    print(f"正在輸出平日時刻表 (共 {len(weekday_data)} 班)...")
    with open(json_path_weekday, "w", encoding="utf-8") as f:
        f.write("[\n")
        for i, train in enumerate(weekday_data):
            line = json.dumps(train, ensure_ascii=False, separators=(',', ':'))
            comma = "," if i < len(weekday_data) - 1 else ""
            f.write(f"  {line}{comma}\n")
        f.write("]\n")

    print(f"正在輸出土休日時刻表 (共 {len(holiday_data)} 班)...")
    with open(json_path_holiday, "w", encoding="utf-8") as f:
        f.write("[\n")
        for i, train in enumerate(holiday_data):
            line = json.dumps(train, ensure_ascii=False, separators=(',', ':'))
            comma = "," if i < len(holiday_data) - 1 else ""
            f.write(f"  {line}{comma}\n")
        f.write("]\n")

    print(f"\n🎉 完美大功告成！已將時刻表存入正確的 JSON 資料夾。")
    print(f"平日檔案: {json_path_weekday}")
    print(f"假日檔案: {json_path_holiday}")

if __name__ == "__main__":
    main()