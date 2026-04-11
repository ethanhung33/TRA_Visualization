import os, requests, re, time, pandas as pd, json
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

RAW_MASTER_LINES = {
    "南海本線": ["難波", "新今宮", "天下茶屋", "岸里玉出", "粉浜", "住吉大社", "住ノ江", "七道", "堺", "湊", "石津川", "諏訪ノ森", "浜寺公園", "羽衣", "高石", "北助松", "松ノ浜", "泉大津", "忠岡", "春木", "和泉大宮", "岸和田", "蛸地蔵", "貝塚", "二色浜", "鶴原", "井原里", "泉佐野", "羽倉崎", "吉見ノ里", "岡田浦", "樽井", "尾崎", "鳥取ノ荘", "箱作", "淡輪", "みさき公園", "孝子", "和歌山大学前", "紀ノ川", "和歌山市"],
    "空港線": ["泉佐野", "りんくうタウン", "関西空港"],
    "加太線": ["紀ノ川", "東松江", "中松江", "八幡前", "西ノ庄", "二里ケ浜", "磯ノ浦", "加太"],
    "多奈川線": ["みさき公園", "深日町", "深日港", "多奈川"],
    "和歌山港線": ["和歌山市", "和歌山港"],
    "高師浜線": ["羽衣", "伽羅橋", "高師浜"],
    "高野線": ["難波", "今宮戎", "新今宮", "萩ノ茶屋", "天下茶屋", "岸里玉出", "帝塚山", "住吉東", "沢ノ町", "我孫子前", "浅香山", "堺東", "三国ヶ丘", "百舌鳥八幡", "中百舌鳥", "白鷺", "初芝", "萩原天神", "北野田", "狭山", "大阪狭山市", "金剛", "滝谷", "千代田", "河内長野", "三日市町", "美加の台", "千早口", "天見", "紀見峠", "林間田園都市", "御幸辻", "橋本", "紀伊清水", "学文路", "九度山", "高野下", "下古沢", "上古沢", "紀伊細川", "紀伊神谷", "極楽橋"],
    "泉北線": ["中百舌鳥", "深井", "泉ケ丘", "栂・美木多", "光明池", "和泉中央"],
    "高野線（汐見橋方面）": ["汐見橋", "芦原町", "木津川", "津守", "西天下茶屋", "岸里玉出"],
    "高野山ケーブル": ["極楽橋", "高野山"]
}
MASTER_LINES = {line: [norm_st(st) for st in stations] for line, stations in RAW_MASTER_LINES.items()}

PREFIX_LIST = [
    ("ラα", "特急ラピートα"), ("ラβ", "特急ラピートβ"), ("ラピ", "特急ラピート"), ("特サ", "特急サザン"), 
    ("サザン", "特急サザン"), ("特泉", "特急泉北ライナー"), ("泉北ライナー", "特急泉北ライナー"), ("泉北", "特急泉北ライナー"), 
    ("天空", "観光列車「天空」"), ("特高", "特急こうや"), ("こうや", "特急こうや"), ("こう", "特急こうや"),       
    ("特林", "特急りんかん"), ("りんかん", "特急りんかん"), ("りん", "特急りんかん"), ("空急", "空港急行"), 
    ("区急", "区間急行"), ("快急", "快速急行"), ("準急", "準急"), ("急行", "急行"), ("各停", "各駅停車"), 
    ("特急", "特急"), ("普通", "普通")
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
        t_type = "普通"
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
    t_dest = "不明"
    if not table: return t7_dict["tx"], t_dest, stops
    
    for tr in table.select("tr"):
        tds = tr.select("td")
        if len(tds) == 3 and (st := tds[0].text.strip()) != "停車駅":
            st = norm_st(st)
            stops[st] = {
                "arrival": tds[1].text.strip() or "−",
                "departure": tds[2].text.strip() or "−"
            }
            t_dest = st
    return t7_dict["tx"], t_dest, stops

def main():
    output_dir = os.path.join("Japan", "Nankai")
    os.makedirs(output_dir, exist_ok=True)
    excel_path = os.path.join(output_dir, "Nankai_Final_Timetable.xlsx")
    json_path = os.path.join(output_dir, "Nankai_Timetable.json")

    print("1. 正在從核心發車站收集所有時刻表目錄...")
    
    # 💡 暴力突破：我們直接組合出正確的 /traffic/ 網址，絕對不會再誤入觀光網頁而漏掉車站！
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
            tx, t_dest, stops = f.result()
            t7_pool[tx]["dest"] = t_dest
            t7_pool[tx]["stops"] = stops
    print("\n✅ 所有列車資料下載完成！\n")

    print("4. 正在進行矩陣運算與生成資料...")
    route_matrix = {} 
    flat_json_output = []
    global_train_map = {}
    global_train_counter = 1001

    for tx, t_info in t7_pool.items():
        stops = t_info.get("stops", {})
        if not stops: continue
        
        t_stops_order = list(stops.keys())
        
        for line_name, line_stations in MASTER_LINES.items():
            intersect = [st for st in t_stops_order if st in line_stations]
            if len(intersect) < 2: continue
            
            idx_first = line_stations.index(intersect[0])
            idx_last = line_stations.index(intersect[-1])
            
            if idx_first < idx_last:
                direction = "下行"
                ordered_stations = line_stations
            else:
                direction = "上行"
                ordered_stations = line_stations[::-1]
            
            sort_st = intersect[0]
            arr = stops[sort_st].get("arrival", "−")
            dep = stops[sort_st].get("departure", "−")
            sort_time_str = dep if dep not in ("∥", "−", "-", "↓", "") else arr
            sort_time = time_to_minutes_for_sort(sort_time_str)
            
            key = (line_name, direction, t_info["day"])
            if key not in route_matrix:
                route_matrix[key] = {"stations": ordered_stations, "trains": []}
                
            route_matrix[key]["trains"].append({
                "tx": tx,
                "type": t_info["type"],
                "dest": t_info["dest"],
                "stops": stops,
                "sort_time": sort_time
            })

    with pd.ExcelWriter(excel_path) as writer:
        for (line_name, direction, day), group in sorted(route_matrix.items()):
            trains = sorted(group["trains"], key=lambda x: x["sort_time"])
            if not trains: continue
            
            headers_type = ["Station", "Arr/Dep"] + [t["type"] for t in trains]
            headers_dest = ["", ""] + [t["dest"] for t in trains]
            headers_tx   = ["", "Train ID"] + [t["tx"] for t in trains]
            
            rows = [headers_type, headers_dest, headers_tx]
            
            for st in group["stations"]:
                row_arr = [st, "arrival"]
                row_dep = ["", "departure"]
                
                for t in trains:
                    t_stops = t["stops"].get(st, {})
                    row_arr.append(t_stops.get("arrival", "−"))
                    row_dep.append(t_stops.get("departure", "−"))
                
                rows.append(row_arr)
                rows.append(row_dep)
                
            df = pd.DataFrame(rows)
            sheet_name = f"{line_name}_{direction}_{day}"[:31]
            df.to_excel(writer, sheet_name=sheet_name, index=False, header=False)
            
            # 💡 建立供 JSON 輸出的結構
            for t in trains:
                tx = t["tx"]
                if tx not in global_train_map:
                    global_train_map[tx] = global_train_counter
                    global_train_counter += 1
                
                t_json = {
                    "line": line_name,
                    "direction": direction,
                    "drive": day,
                    "train": t["type"],
                    "number": global_train_map[tx],
                    "data": []
                }
                
                p_mins = 0
                for st in group["stations"]:
                    d = t["stops"].get(st, {"arrival": "∥", "departure": "∥"})
                    am = time_to_minutes(d.get("arrival", "∥"), p_mins)
                    if am: p_mins = am
                    dm = time_to_minutes(d.get("departure", "∥"), p_mins)
                    if dm: p_mins = dm
                    
                    if am and dm:
                        if am == dm:
                            t_json["data"].append({"x": st, "y": am - 0.5})
                            t_json["data"].append({"x": st, "y": dm + 0.5})
                        else:
                            t_json["data"].append({"x": st, "y": am})
                            t_json["data"].append({"x": st, "y": dm})
                    elif am or dm:
                        t_json["data"].append({"x": st, "y": am or dm})
                
                flat_json_output.append(t_json)

    # 💡 強制讓一班車變成 JSON 裡的一行！
    with open(json_path, "w", encoding="utf-8") as f:
        f.write("[\n")
        for i, train in enumerate(flat_json_output):
            # 關閉縮排即可讓物件變成單行字串
            line = json.dumps(train, ensure_ascii=False)
            comma = "," if i < len(flat_json_output) - 1 else ""
            f.write(f"  {line}{comma}\n")
        f.write("]\n")

    print(f"\n🎉 完美大功告成！檔案已儲存至: {output_dir}")

if __name__ == "__main__":
    main()