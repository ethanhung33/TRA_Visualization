import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timedelta
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from pathlib import Path

# ==========================================
# 1. 基礎設定與 ID 映射
# ==========================================
SCRIPT_DIR = Path(__file__).parent
JSON_DIR = SCRIPT_DIR.parent / "json"
TOPOLOGY_PATH = JSON_DIR / "topology.json"

with open(TOPOLOGY_PATH, "r", encoding="utf-8") as f:
    TOPOLOGY = json.load(f)

STATION_INFO = {}
for seg in TOPOLOGY['segments']:
    for st in seg['stations']:
        name = st['name']
        if name not in STATION_INFO:
            # 🌟 這裡新增記錄車站 ID
            STATION_INFO[name] = {"segments": [], "km_map": {}, "id": st['id']}
        STATION_INFO[name]["segments"].append(seg['id'])
        STATION_INFO[name]["km_map"][seg['id']] = st['km']

JUNCTIONS = ["八堵", "竹南", "彰化", "枋寮"]
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.railway.gov.tw/tra-tip-web/tip/tip001/tip112/querybyStation'
}

def time_to_min(time_str):
    try:
        parts = list(map(int, time_str.split(':')))
        return parts[0] * 60 + parts[1]
    except: return 0

# ==========================================
# 2. 核心編譯邏輯 (改存 ID)
# ==========================================
# ==========================================
# 2. 核心編譯邏輯 (拔除 UNKNOWN 版本)
# ==========================================
def compile_train_data(raw_stops, is_mountain):
    compiled_segments = []
    current_seg_id = None
    
    s_ids, t_times, v_types = [], [], []
    TYPE_MAP = {"START": 0, "STOP": 1, "PASS": 2, "END": 3}

    # 🌟 1. 預先過濾：只保留我們在 Topology 中認識的車站
    valid_stops = []
    for st in raw_stops:
        if st['name'] in STATION_INFO:
            valid_stops.append(st)

    # 如果這班車(例如平溪線)全部都不認識，直接回傳空陣列
    if not valid_stops:
        return []

    for i in range(len(valid_stops)):
        st_now = valid_stops[i]
        name_now = st_now['name']
        
        st_info = STATION_INFO.get(name_now, {})
        possible_segs = st_info.get("segments", [])
        st_id = st_info.get("id", "UNKNOWN")

        if "mountain_line" in possible_segs and is_mountain:
            best_seg = "mountain_line"
        elif "sea_line" in possible_segs and not is_mountain:
            best_seg = "sea_line"
        else:
            best_seg = possible_segs[0] if possible_segs else "UNKNOWN"

        if current_seg_id is None:
            current_seg_id = best_seg

        if i > 0 and current_seg_id != best_seg and name_now in JUNCTIONS:
            s_ids.append(st_id) 
            t_times.extend([st_now['arr'], st_now['dep']])
            v_types.append(TYPE_MAP["STOP"] if st_now['arr'] != st_now['dep'] else TYPE_MAP["PASS"])
            
            # 🌟 2. 確保不是 UNKNOWN 區段才寫入
            if current_seg_id != "UNKNOWN" and s_ids:
                compiled_segments.append({"id": current_seg_id, "s": s_ids, "t": t_times, "v": v_types})
            
            current_seg_id = best_seg
            s_ids, t_times, v_types = [st_id], [st_now['arr'], st_now['dep']], [TYPE_MAP["STOP"] if st_now['arr'] != st_now['dep'] else TYPE_MAP["PASS"]]
            continue

        s_ids.append(st_id) 
        t_times.extend([st_now['arr'], st_now['dep']])
        
        st_type = "STOP"
        if i == 0: st_type = "START"
        elif i == len(valid_stops) - 1: st_type = "END"
        elif st_now['arr'] == st_now['dep']: st_type = "PASS"
        v_types.append(TYPE_MAP[st_type])

    # 🌟 3. 最後結尾也要防堵 UNKNOWN
    if s_ids and current_seg_id != "UNKNOWN":
        compiled_segments.append({"id": current_seg_id, "s": s_ids, "t": t_times, "v": v_types})
        
    return compiled_segments

# ==========================================
# 3. 執行緒工作任務 (維持不變)
# ==========================================
def fetch_worker(t_type, t_no, date):
    url = f"https://www.railway.gov.tw/tra-tip-web/tip/tip001/tip112/querybytrainno?rideDate={date}&trainNo={t_no}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        tbodies = soup.find_all("tbody")
        if len(tbodies) < 2: return None
        
        rows = tbodies[1].find_all("tr")
        raw_stops, last_time, has_mountain = [], -1, False
        mountain_specific = [s['name'] for s in TOPOLOGY['segments'][1]['stations'] if s['name'] not in JUNCTIONS]

        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 3: continue
            name = cols[0].get_text().strip()
            arr, dep = time_to_min(cols[1].get_text()), time_to_min(cols[2].get_text())
            
            if arr < last_time: arr += 1440
            if dep < arr: dep += 1440
            last_time = dep
            
            if name in mountain_specific: has_mountain = True
            raw_stops.append({"name": name, "arr": arr, "dep": dep})
        
        segments = compile_train_data(raw_stops, has_mountain)
        
        # 🌟 攔截完全沒有路線的車次 (如純支線)
        if not segments:
            return None
            
        return {"no": t_no, "type": t_type, "segments": segments}
    except: return None

# ==========================================
# 4. 主程式
# ==========================================
def main():
    # 🌟 這裡放你的完整車站清單
    station_list = ['1000-臺北', '1250-竹南', '3360-彰化', '4400-高雄', '6000-臺東', '7000-花蓮'] 
    
    date = datetime.today().strftime("%Y/%m/%d")
    train_list = set()
    print(f"📡 正在獲取 {date} 的車次名單...")
    
    for station in tqdm(station_list):
        try:
            url = f"https://www.railway.gov.tw/tra-tip-web/tip/tip001/tip112/querybystationblank?rideDate={date}&station={station}"
            resp = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            for tbody in soup.find_all("tbody")[:2]:
                for row in tbody.find_all("tr"):
                    content = row.find_all("td")
                    if len(content) < 2: continue
                    a_tag = content[1].find("a")
                    if not a_tag: continue
                    t_text = a_tag.get_text().strip()
                    if "自強(3000)" in t_text: train_list.add(("新自強", t_text[8:]))
                    elif any(x in t_text for x in ["區間快", "普悠瑪", "太魯閣"]): train_list.add((t_text[:3], t_text[3:]))
                    else: train_list.add((t_text[:2], t_text[2:]))
        except: continue

    print(f"✅ 找到 {len(train_list)} 班獨特車次。開始下載...")

    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(fetch_worker, t[0], t[1], date) for t in train_list]
        for f in tqdm(as_completed(futures), total=len(futures)):
            res = f.result()
            if res: results.append(res)

    output_path = JSON_DIR / f"timetable" / f"timetable_{date.replace('/','')}.json"
    
    # 🌟 完美的「一班車一行」輸出邏輯
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("[\n")
        for i, res in enumerate(results):
            # separators=(',', ':') 確保這班車內部不會有任何換行或空格
            line = json.dumps(res, ensure_ascii=False, separators=(',', ':'))
            if i < len(results) - 1:
                f.write(line + ",\n")
            else:
                f.write(line + "\n")
        f.write("]\n")
    
    print(f"🎉 完美儲存！請查看 {output_path}")

if __name__ == "__main__":
    main()