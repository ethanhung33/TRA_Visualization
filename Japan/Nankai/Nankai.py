import requests, re, time, pandas as pd, json
from bs4 import BeautifulSoup
from urllib.parse import urljoin
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

RAW_MASTER_LINES = {
    "南海本線": [
        "難波", "新今宮", "天下茶屋", "岸里玉出", "粉浜", "住吉大社", "住ノ江", "七道", 
        "堺", "湊", "石津川", "諏訪ノ森", "浜寺公園", "羽衣", "高石", "北助松", 
        "松ノ浜", "泉大津", "忠岡", "春木", "和泉大宮", "岸和田", "蛸地蔵", "貝塚", 
        "二色浜", "鶴原", "井原里", "泉佐野", "羽倉崎", "吉見ノ里", "岡田浦", "樽井", 
        "尾崎", "鳥取ノ荘", "箱作", "淡輪", "みさき公園", "孝子", "和歌山大学前", "紀ノ川", "和歌山市"
    ],
    "空港線": ["泉佐野", "りんくうタウン", "関西空港"],
    "加太線": ["紀ノ川", "東松江", "中松江", "八幡前", "西ノ庄", "二里ケ浜", "磯ノ浦", "加太"],
    "多奈川線": ["みさき公園", "深日町", "深日港", "多奈川"],
    "和歌山港線": ["和歌山市", "和歌山港"],
    "高師浜線": ["羽衣", "伽羅橋", "高師浜"],
    "高野線": [
        "難波", "今宮戎", "新今宮", "萩ノ茶屋", "天下茶屋", "岸里玉出", "帝塚山", "住吉東", "沢ノ町", 
        "我孫子前", "浅香山", "堺東", "三国ヶ丘", "百舌鳥八幡", "中百舌鳥", "白鷺", "初芝", "萩原天神", 
        "北野田", "狭山", "大阪狭山市", "金剛", "滝谷", "千代田", "河内長野", "三日市町", "美加の台", 
        "千早口", "天見", "紀見峠", "林間田園都市", "御幸辻", "橋本", "紀伊清水", "学文路", "九度山", 
        "高野下", "下古沢", "上古沢", "紀伊細川", "紀伊神谷", "極楽橋"
    ],
    "泉北線": ["中百舌鳥", "深井", "泉ケ丘", "栂・美木多", "光明池", "和泉中央"],
    "高野線（汐見橋方面）": ["汐見橋", "芦原町", "木津川", "津守", "西天下茶屋", "岸里玉出"],
    "高野山ケーブル": ["極楽橋", "高野山"]
}
MASTER_LINES = {line: [norm_st(st) for st in stations] for line, stations in RAW_MASTER_LINES.items()}

@lru_cache(maxsize=2048)
def get_soup(url, retries=3):
    for i in range(retries):
        try:
            time.sleep(0.2) 
            resp = SESSION.get(url, timeout=20)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")
        except:
            time.sleep((i + 1) * 2)
    return BeautifulSoup("", "html.parser")

def scan_single_station(st_url):
    local_groups = []
    for a in get_soup(st_url).select('a[href*="/pc/T5?"]'):
        t5 = urljoin(st_url, a["href"])
        if m := re.search(r"■\s*(.+?)\s+(平日|土休日)", get_soup(t5).get_text(" ", strip=True)):
            parts = m.group(1).split()
            if len(parts) >= 2:
                line_name = "高野線（汐見橋方面）" if "汐見橋" in parts[0] else parts[0]
                direction = parts[-1]
                if line_name == "南海本線" and "和歌山市" in direction:
                    direction = "◇和歌山市・関西空港方面"
                local_groups.append((f"{line_name}_{direction}_{m.group(2)}", t5))
    return local_groups

# ==========================================
# 🚀 靈光一閃：用「最後一站」作為目的地
# ==========================================
def extract_train_data(t7_url, passed_t_type="普通"):
    soup = get_soup(t7_url)
    table = soup.select_one("#ekt")
    if not table: return passed_t_type, "不明", {}
    
    stops = {}
    t_dest = "不明" # 預設目的地
    
    for tr in table.select("tr"):
        if len(tds := tr.select("td")) == 3 and (st := tds[0].text.strip()) != "停車駅":
            st = norm_st(st)
            stops[st] = {"arrival": tds[1].text.strip() or "∥", "departure": tds[2].text.strip() or "∥"}
            # 💡 每次讀到新的一站就覆寫，迴圈結束時，t_dest 就是這班車的終點站！
            t_dest = st 
            
    return passed_t_type, t_dest, stops

def main():
    print("1. 平行掃描車站中...")
    base_url = "https://www.nankai.co.jp/traffic/railway.html"
    st_urls = list(dict.fromkeys([urljoin(base_url, a["href"]) for a in get_soup(base_url).select('a[href*="/station/"]')]))

    groups = {}
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {executor.submit(scan_single_station, url): url for url in st_urls}
        for i, future in enumerate(as_completed(futures), 1):
            print(f"\r  車站進度: {i} / {len(st_urls)}", end="", flush=True)
            for g_name, t5 in future.result():
                groups.setdefault(g_name, []).append(t5)
    print("\n✅ 車站掃描完成！\n")

    flat_json_output = []
    line_order = list(RAW_MASTER_LINES.keys())
    
    def sort_groups(item):
        g_name = item[0]
        l_name = g_name.split("_")[0]
        line_idx = line_order.index(l_name) if l_name in line_order else 999
        day_idx = 0 if "平日" in g_name else 1
        return (line_idx, day_idx, g_name)

    prefix_list = [
        ("ラα", "特急ラピートα"), ("ラβ", "特急ラピートβ"), ("ラピ", "特急ラピート"),
        ("特サ", "特急サザン"), ("サザン", "特急サザン"), 
        ("特泉", "特急泉北ライナー"), ("泉北ライナー", "特急泉北ライナー"), ("泉北", "特急泉北ライナー"), 
        ("天空", "観光列車「天空」"), 
        ("特高", "特急こうや"), ("こうや", "特急こうや"), ("こう", "特急こうや"),       
        ("特林", "特急りんかん"), ("りんかん", "特急りんかん"), ("りん", "特急りんかん"), 
        ("空急", "空港急行"), ("区急", "区間急行"), ("快急", "快速急行"), 
        ("準急", "準急"), ("急行", "急行"), ("各停", "各駅停車"), ("特急", "特急"), ("普通", "普通")
    ]

    print(f"2. 開始處理 {len(groups)} 條路線...")
    
    # 💡 改為使用特徵碼記錄編號
    global_train_map = {} 
    global_train_counter = 1001 

    with pd.ExcelWriter("Nankai_Final_Output.xlsx") as writer:
        for group_name, t5_urls in sorted(groups.items(), key=sort_groups):
            print(f"處理: {group_name}")
            
            group_parts = group_name.split("_")
            line_name = group_parts[0]
            direction_name = group_parts[1] if len(group_parts) > 1 else "不明"
            drive_day = group_parts[2] if len(group_parts) > 2 else "不明"
            
            standard_stations = MASTER_LINES.get(line_name)
            if not standard_stations: continue

            best_t5 = max(t5_urls, key=lambda u: len(get_soup(u).select('a[href*="T7?"]')))
            
            t7_tasks = []
            for a in get_soup(best_t5).select('a[href*="T7?"]'):
                link = urljoin(best_t5, a["href"])
                btn_text = a.get_text(" ", strip=True).replace("(平日)", "").replace("(土休日)", "").strip()
                
                t_type = "普通"
                for abbr, full_name in prefix_list:
                    if btn_text.startswith(abbr):
                        t_type = full_name
                        break
                        
                t7_tasks.append((link, t_type))

            if not t7_tasks: continue

            current_stations = standard_stations.copy()
            _, _, peek_stops = extract_train_data(t7_tasks[0][0])
            v_stops = [st for st in peek_stops.keys() if st in current_stations]
            if len(v_stops) >= 2 and current_stations.index(v_stops[0]) > current_stations.index(v_stops[-1]):
                current_stations = current_stations[::-1]

            results_by_idx = {}
            total_t = len(t7_tasks)
            
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(extract_train_data, task[0], task[1]): idx for idx, task in enumerate(t7_tasks)}
                for future in as_completed(futures):
                    train_idx = futures[future]
                    t_type, t_dest, scraped_stops = future.result()
                    if not scraped_stops: continue
                    
                    # 💡 4. 建立「列車 DNA 特徵碼」
                    # 把這台車在所有站的真實到離站時間串接起來 (過濾掉空白或沒停的站)
                    valid_times = [t for st, d in scraped_stops.items() for t in (d["arrival"], d["departure"]) if t and t not in ("∥", "−", "-")]
                    time_hash = "".join(valid_times)
                    
                    # 特徵碼 = 平假日_車種_目的地_所有時間字串
                    # 只要時刻表一模一樣，它跨幾條線特徵碼都一樣！
                    train_signature = f"{drive_day}_{t_type}_{t_dest}_{time_hash}"
                    
                    train_json = {
                        "line": line_name,
                        "direction": direction_name,
                        "drive": drive_day,
                        "train": t_type, 
                        "number": 0, 
                        "data": []
                    }
                    
                    col_times = []
                    p_mins = 0
                    
                    for st in current_stations:
                        st_data = scraped_stops.get(st, {"arrival": "∥", "departure": "∥"})
                        arr_s, dep_s = st_data["arrival"], st_data["departure"]
                        col_times.extend([arr_s, dep_s])
                        
                        if st in scraped_stops:
                            am = time_to_minutes(arr_s, p_mins)
                            if am: p_mins = am
                            dm = time_to_minutes(dep_s, p_mins)
                            if dm: p_mins = dm
                            
                            if am and dm:
                                if am == dm: 
                                    train_json["data"].append({"x": st, "y": am - 0.5})
                                    train_json["data"].append({"x": st, "y": dm + 0.5})
                                else:
                                    train_json["data"].append({"x": st, "y": am})
                                    train_json["data"].append({"x": st, "y": dm})
                            elif am or dm:
                                train_json["data"].append({"x": st, "y": am or dm})
                    
                    results_by_idx[train_idx] = {
                        "signature": train_signature,  # 💡 記錄特徵碼取代 link
                        "t_type": t_type, "t_dest": t_dest, 
                        "col_times": col_times, "json": train_json
                    }
                    print(f"\r  下載列車: {len(results_by_idx)}/{total_t}", end="", flush=True)
            print() 

            if not results_by_idx: continue

            train_types = ["", ""]
            train_dests = ["Station", "Type"]
            train_data = []
            
            for idx in sorted(results_by_idx.keys()):
                res = results_by_idx[idx]
                sig = res["signature"] # 💡 取得特徵碼
                train_types.append(res["t_type"])
                train_dests.append(res["t_dest"])
                train_data.append(res["col_times"])
                
                # 💡 利用特徵碼做全域比對，同一班車就算跨線也會拿到一樣的 number
                if sig not in global_train_map:
                    global_train_map[sig] = global_train_counter
                    global_train_counter += 1
                
                res["json"]["number"] = global_train_map[sig]
                flat_json_output.append(res["json"])
                
            transposed_data = list(zip(*train_data))
            row_tuples = []
            for st in current_stations:
                row_tuples.extend([(st, "arrival"), ("", "departure")])
                
            final_rows = []
            for i, row in enumerate(transposed_data):
                final_rows.append(list(row_tuples[i]) + list(row))
                
            df_matrix = pd.DataFrame([train_types, train_dests] + final_rows)
            sheet_name = re.sub(r"[\\/*?:\[\]]", "_", group_name)[:31]
            df_matrix.to_excel(writer, sheet_name=sheet_name, index=False, header=False)

    with open("Nankai_Timetable.json", "w", encoding="utf-8") as f:
        f.write("[\n")
        for i, train in enumerate(flat_json_output):
            line = json.dumps(train, ensure_ascii=False)
            comma = "," if i < len(flat_json_output) - 1 else ""
            f.write(f"  {line}{comma}\n")
        f.write("]")

    print("\n✅ 完成！跨路線的直通列車 (如南海本線<=>空港線) 已經完美共用同一個編號！")

if __name__ == "__main__":
    main()