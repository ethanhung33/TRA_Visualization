import requests
from bs4 import BeautifulSoup
import json
import re
import time
from urllib.parse import urlparse, parse_qs
from tqdm import tqdm
import concurrent.futures
import os
import random

# ==========================================
# 🛑 測試模式開關 (除錯時請設為 True)
# ==========================================
TEST_MODE = False

# ==========================================
# 🛠️ 站名對應翻譯蒟蒻 (STATION_MAPPING)
# ==========================================
STATION_MAPPING = {
    "難波": "大阪難波",
    "上本町": "大阪上本町",
    "西大寺": "大和西大寺",
    "奈良": "近鉄奈良",
    "名古屋": "近鉄名古屋",
    "四日市": "近鉄四日市",
    "丹波橋": "近鉄丹波橋",
    "郡山": "近鉄郡山",
    "八尾": "近鉄八尾",
    "下田": "近鉄下田",
    "富田": "近鉄富田",
    "長島": "近鉄長島",
    "弥富": "近鉄弥富",
    "蟹江": "近鉄蟹江",
    "八田": "近鉄八田",
    "新庄": "近鉄新庄",
    "御所": "近鉄御所",
    "瓢箪山": "瓢簞山" 
}

# ==========================================
# 🛡️ 直通運轉黑名單 (EXTERNAL_NETWORKS)
# 在這些站停靠的資料將會被自動刪除，只保留近鐵境內的行駛紀錄
# ==========================================
EXTERNAL_NETWORKS = {
    # 阪神電鐵
    "桜川", "ドーム前", "九条", "西九条", "千鳥橋", "伝法", "福", "出来島", "大物", "尼崎",
    "尼崎センタープール前", "武庫川", "鳴尾・武庫川女子大前", "甲子園", "久寿川", "今津", 
    "西宮", "香櫨園", "打出", "芦屋", "深江", "青木", "魚崎", "住吉", "御影", "石屋川", 
    "新在家", "大石", "西灘", "岩屋", "西代", "神戸三宮", "元町", "神戸高速",
    # 京都市營地下鐵
    "国際会館", "松ヶ崎", "北山", "北大路", "鞍馬口", "今出川", "丸太町", "烏丸御池", 
    "四条", "五条", "くいな橋", "十条",
    # 大阪 Metro 中央線
    "コスモスクエア", "大阪港", "朝潮橋", "弁天町", "阿波座", "本町", "堺筋本町", 
    "谷町四丁目", "森ノ宮", "緑橋", "深江橋", "高井田"
}

MISSING_STATIONS = set()

route_dict = {
    "A": "namba_nara", "B": "kyoto_kashihara", "C": "keihanna", "D": "osaka",
    "E": "nagoya", "F": "minamiosaka_yoshino", "G": "ikoma", "H": "tenri",
    "I": "tawaramoto", "J": "shigi", "K": "yunoyama", "L": "suzuka",
    "M": "yamada_toba_shima", "N": "domyoji", "O": "nagano", "P": "gose",
    "Y": "ikomacable", "Z": "nishishigicable",
}

def clean_station_name(name):
    name = re.sub(r'\[.*?\]', '', name)
    name = re.sub(r'（.*?）', '', name)
    name = name.replace('\u3000', '').replace(' ', '')
    if name.endswith("駅"):
        name = name[:-1]
    name = name.strip()
    
    if name in STATION_MAPPING:
        return STATION_MAPPING[name]
    return name

def convert_to_minutes(time_str):
    if not time_str or time_str.strip() == "": return time_str
    match = re.search(r'(\d{1,2})[:：](\d{2})', time_str)
    if match: return int(match.group(1)) * 60 + int(match.group(2))
    return time_str

def get_topology_path():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, '..', 'json', 'topology.json')

def get_output_dir():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, '..', 'json', 'timetable')
    os.makedirs(output_dir, exist_ok=True)
    return output_dir

def load_topology():
    topology_path = get_topology_path()
    try:
        with open(topology_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"警告: 找不到拓樸檔 {topology_path}！")
        return {"segments": []}

def build_station_map(topology):
    station_map = {}
    for segment in topology.get("segments", []):
        seg_id = segment["id"]
        for st in segment["stations"]:
            name = clean_station_name(st["name"])
            if name not in station_map:
                station_map[name] = {"id": st["id"], "lines": set()}
            station_map[name]["lines"].add(seg_id)
    return station_map

def build_segment_dict(seg_id, stops, station_map):
    s_arr = []
    t_arr = []
    v_arr = []
    
    for i, stop in enumerate(stops):
        st_name = clean_station_name(stop["station"])
        st_id = station_map.get(st_name, {}).get("id", "Unknown")

        arr = stop["arr"]
        dep = stop["dep"]
        
        if not isinstance(arr, int): arr = dep
        if not isinstance(dep, int): dep = arr
        if not isinstance(arr, int): arr = 0
        if not isinstance(dep, int): dep = 0
        
        if i == 0: v = 0
        elif i == len(stops) - 1: v = 3
        else: v = 1
            
        s_arr.append(st_id)
        t_arr.extend([arr, dep])
        v_arr.append(v)
        
    return {"id": seg_id, "s": s_arr, "t": t_arr, "v": v_arr}

def format_nankai_style(raw_train, station_map):
    stop_data = raw_train.get("data", [])
    if not stop_data: return None

    # ★ 核心修改：只保留真正在近鐵範圍內的車站！
    valid_stops = []
    for stop in stop_data:
        st_name = clean_station_name(stop["station"])
        
        # 如果站名在 Topology 裡找得到，代表是自家人，加進去
        if st_name in station_map:
            valid_stops.append(stop)
        else:
            # 如果找不到，檢查是不是已知的外網車站。如果連外網也不是，才跳出警告
            if st_name not in EXTERNAL_NETWORKS and st_name not in MISSING_STATIONS:
                MISSING_STATIONS.add(st_name)

    # 如果這班車在近鐵境內停靠不到兩站，就失去畫圖意義了，直接拋棄
    if len(valid_stops) < 2:
        return None

    segments = []
    current_segment_stops = []
    current_possible_lines = set()

    for i in range(len(valid_stops)):
        stop = valid_stops[i]
        st_name = clean_station_name(stop["station"])
        st_lines = station_map.get(st_name, {}).get("lines", set())
        
        if not current_segment_stops:
            current_segment_stops.append(stop)
            current_possible_lines = set(st_lines)
        else:
            new_possible_lines = current_possible_lines.intersection(st_lines)
            if new_possible_lines:
                current_segment_stops.append(stop)
                current_possible_lines = new_possible_lines
            else:
                seg_id = list(current_possible_lines)[0] if current_possible_lines else "unknown_line"
                segments.append(build_segment_dict(seg_id, current_segment_stops, station_map))
                
                last_stop = current_segment_stops[-1]
                last_st_name = clean_station_name(last_stop["station"])
                last_st_lines = station_map.get(last_st_name, {}).get("lines", set())
                
                current_segment_stops = [last_stop, stop]
                current_possible_lines = last_st_lines.intersection(st_lines)
                if not current_possible_lines:
                    current_possible_lines = set(st_lines)

    if len(current_segment_stops) > 1:
        seg_id = list(current_possible_lines)[0] if current_possible_lines else "unknown_line"
        segments.append(build_segment_dict(seg_id, current_segment_stops, station_map))

    return {"no": raw_train.get("no", "Unknown"), "type": raw_train.get("type", "Unknown"), "segments": segments}

def get_all_station_urls(d_val):
    urls = []
    
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=350-0&d=1&dw={d_val}")
    for k in range(1, 23): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=350-{k}&d=2&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=350-23&d=1&dw={d_val}")
    for k in range(1, 23): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=350-{23-k}&d=1&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=350-0&d=2&dw={d_val}")
    
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=360-0&d=1&dw={d_val}")
    for k in range(1, 25): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=360-{k}&d=2&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=361-0&d=1&dw={d_val}")
    for k in range(1, 16): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=361-{k}&d=2&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=361-16&d=1&dw={d_val}")
    for k in range(1, 16): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=361-{16-k}&d=1&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=360-25&d=1&dw={d_val}")
    for k in range(1, 25): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=360-{25-k}&d=1&dw={d_val}")
    
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=352-0&d=1&dw={d_val}")
    for k in range(1, 7): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=352-{k}&d=2&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=352-7&d=1&dw={d_val}")
    for k in range(1, 7): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=352-{7-k}&d=1&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=352-0&d=2&dw={d_val}")
    
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=356-0&d=1&dw={d_val}")
    for k in range(1, 47): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=356-{k}&d=2&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=356-47&d=1&dw={d_val}")
    for k in range(1, 47): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=356-{47-k}&d=1&dw={d_val}")

    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=413-1&d=1&dw={d_val}")
    for k in range(2, 44): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=413-{k}&d=2&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=413-44&d=1&dw={d_val}")
    for k in range(2, 44): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=413-{45-k}&d=1&dw={d_val}")
    
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=349-0&d=1&dw={d_val}")
    for k in range(1, 27): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=349-{k}&d=2&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=373-0&d=1&dw={d_val}")
    for k in range(1, 15): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=373-{k}&d=2&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=373-15&d=1&dw={d_val}")
    for k in range(1, 15): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=373-{15-k}&d=1&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=349-27&d=1&dw={d_val}")
    for k in range(1, 27): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=349-{27-k}&d=1&dw={d_val}")

    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=357-0&d=1&dw={d_val}")
    for k in range(1, 11): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=357-{k}&d=2&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=357-11&d=1&dw={d_val}")
    for k in range(1, 11): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=357-{11-k}&d=1&dw={d_val}")

    other_lines = [
        ("H", 354, 3), ("I", 353, 7), ("J", 358, 2), ("K", 409, 10, True), 
        ("L", 415, 5, True), ("N", 351, 2), ("O", 355, 7), ("P", 359, 3)
    ]
    for line_info in other_lines:
        code = line_info[1]
        max_k = line_info[2]
        is_one_based = len(line_info) > 3 and line_info[3]
        start = 1 if is_one_based else 0
        urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode={code}-{start}&d=1&dw={d_val}")
        for k in range(start + 1, max_k):
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode={code}-{k}&d=2&dw={d_val}")
        urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode={code}-{max_k}&d=1&dw={d_val}")
        for k in range(start + 1, max_k):
            back_idx = max_k - k if not is_one_based else (max_k + 1) - k
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode={code}-{back_idx}&d=1&dw={d_val}")

    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=452-1&d=1&dw={d_val}")
    for k in range(2, 14): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=452-{k}&d=2&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=453-1&d=1&dw={d_val}")
    for k in range(2, 5): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=453-{k}&d=2&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=454-1&d=1&dw={d_val}")
    for k in range(2, 16): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=454-{k}&d=2&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=454-16&d=1&dw={d_val}")
    for k in range(2, 16): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=454-{17-k}&d=1&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=453-5&d=1&dw={d_val}")
    for k in range(2, 5): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=453-{6-k}&d=1&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=452-14&d=1&dw={d_val}")
    for k in range(2, 14): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=452-{15-k}&d=1&dw={d_val}")

    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=665-0&d=1&dw={d_val}")
    for k in range(1, 4): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=665-{k}&d=2&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=665-4&d=1&dw={d_val}")
    for k in range(1, 4): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=665-{4-k}&d=1&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=666-0&d=1&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=666-1&d=1&dw={d_val}")

    if TEST_MODE:
        step = max(1, len(urls) // 30)
        return urls[::step]

    return urls

def fetch_station_page(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    found_trains = []
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'shift_jis'
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'T7?' in href:
                    params = parse_qs(urlparse(href).query)
                    tx = params.get('tx', [None])[0]
                    dw = params.get('dw', [None])[0]
                    sf = params.get('sf', [None])[0]
                    if tx:
                        found_trains.append({"tx": tx, "dw": dw, "sf": sf})
    except Exception:
        pass
    return found_trains

def fetch_and_format_train_detail(train_info, station_map):
    headers = {'User-Agent': 'Mozilla/5.0'}
    tx = train_info['tx']
    url = f"https://eki.kintetsu.co.jp/norikae/T7?sf={train_info['sf']}&tx={tx}&dw={train_info['dw']}"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'shift_jis'
        if response.status_code != 200: return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        header_cell = soup.find('td', {'bgcolor': '#FFB334', 'colspan': '3'})
        if not header_cell: return None
        header_text = header_cell.get_text(strip=True)
        meta_match = re.search(r'(.*?)\s+(.*?行き.*?)\s+(.*)のダイヤ', header_text)
        
        train_type = meta_match.group(1).strip() if meta_match else "Unknown"

        stop_data = []
        for row in soup.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) == 3:
                station_text = cells[0].get_text(strip=True)
                
                # ✅ 修正：過濾掉空值、表頭，以及超長的觀光列車免責聲明
                if station_text in ["停車駅", ""] or "ご覧ください" in station_text or "変更" in station_text: 
                    continue
                
                raw_arr = cells[1].get_text(strip=True).replace('\xa0', '')
                raw_dep = cells[2].get_text(strip=True).replace('\xa0', '')
                
                stop_data.append({
                    "station": station_text,
                    "arr": convert_to_minutes(raw_arr),
                    "dep": convert_to_minutes(raw_dep)
                })

        raw_train = {
            "no": tx, 
            "type": train_type,
            "data": stop_data
        }
        
        return format_nankai_style(raw_train, station_map)
    except Exception:
        return None

def process_timetable_concurrently(d_val, output_filename, station_map, max_workers=20):
    day_name = "Weekday" if d_val == 0 else "Weekend/Holiday"
    print(f"\n🚀 [{day_name}] 階段 1/2: 掃描車站獲取車次清單...")
    
    urls = get_all_station_urls(d_val)
    train_queries_dict = {}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_station_page, url): url for url in urls}
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(urls), desc="掃描中"):
            trains = future.result()
            for t in trains:
                if t['tx'] not in train_queries_dict:
                    train_queries_dict[t['tx']] = t

    unique_trains = list(train_queries_dict.values())
    
    if TEST_MODE:
        random.shuffle(unique_trains)
        unique_trains = unique_trains[:150]
        print(f"\n⚠️ 測試模式開啟：已均勻抽樣各線車站，隨機挑選 {len(unique_trains)} 班車測試")

    print(f"\n🚀 [{day_name}] 階段 2/2: 處理 {len(unique_trains)} 班車的時刻...")

    final_timetable = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_and_format_train_detail, train_info, station_map): train_info for train_info in unique_trains}
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(unique_trains), desc="處理中"):
            formatted_train = future.result()
            if formatted_train:
                final_timetable.append(formatted_train)

    final_timetable.sort(key=lambda x: x.get("no", ""))

    output_dir = get_output_dir()
    output_path = os.path.join(output_dir, f'{output_filename}.json')
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("[\n")
        for i, train in enumerate(final_timetable):
            train_json_str = json.dumps(train, ensure_ascii=False, separators=(',', ':'))
            f.write(f"  {train_json_str}")
            if i < len(final_timetable) - 1:
                f.write(",\n")
            else:
                f.write("\n")
        f.write("]\n")
    
    print(f"🎉 [{day_name}] 處理完成！檔案儲存至: {os.path.abspath(output_path)}")

    if MISSING_STATIONS:
        print("\n" + "="*60)
        print("🚨 發現未匹配的站名！(可能是近鐵站名錯誤，或是有新的直通運轉車站)")
        print("請將以下內容複製，並貼上到程式碼上方的 STATION_MAPPING 字典中：\n")
        for st in sorted(list(MISSING_STATIONS)):
            if st:
                print(f'    "{st}": "請填入 topology 中的站名 (若是外網車站可略過)",')
        print("="*60 + "\n")


if __name__ == "__main__":
    print(f"⚡ 啟動近鐵時刻表爬蟲 (TEST_MODE={TEST_MODE}) ⚡\n")
    
    WORKERS = 30
    
    topology_data = load_topology()
    st_map = build_station_map(topology_data)
    
    process_timetable_concurrently(d_val=0, output_filename="timetable_weekday_test" if TEST_MODE else "timetable_weekday", station_map=st_map, max_workers=WORKERS)
    
    if not TEST_MODE:
        print("-" * 60)
        process_timetable_concurrently(d_val=1, output_filename="timetable_holiday", station_map=st_map, max_workers=WORKERS)
    
    print("\n🏆 所有作業執行完畢！")