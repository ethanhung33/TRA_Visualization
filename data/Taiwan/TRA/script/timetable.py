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
# ==========================================
# 2. 核心編譯邏輯 (終極雙向交疊分段版)
# ==========================================
def compile_train_data(raw_stops, is_mountain):
    compiled_segments = []
    TYPE_MAP = {"START": 0, "STOP": 1, "PASS": 2, "END": 3}

    # 1. 預先過濾與特判
    valid_stops = []
    for st in raw_stops:
        name = st['name']
        if name in STATION_INFO:
            st_info = STATION_INFO[name]
            segs = list(st_info["segments"]) 

            # 🌟 台鐵特判：強制過濾山海線
            if "mountain_line" in segs and not is_mountain: segs.remove("mountain_line")
            if "sea_line" in segs and is_mountain: segs.remove("sea_line")

            if segs:
                valid_stops.append({
                    "id": st_info["id"],
                    "arr": st['arr'],
                    "dep": st['dep'],
                    "segs": segs
                })

    if not valid_stops: return []

    def get_v_type(idx, total):
        if idx == 0: return TYPE_MAP["START"]
        if idx == total - 1: return TYPE_MAP["END"]
        if valid_stops[idx]['arr'] == valid_stops[idx]['dep']: return TYPE_MAP["PASS"]
        return TYPE_MAP["STOP"]

    # 2. 狀態機初始化
    current_seg_id = valid_stops[0]["segs"][0]
    s_ids, t_times, v_types = [], [], []

    # 3. 核心分段與橋接迴圈
    for i in range(len(valid_stops)):
        st = valid_stops[i]
        v_type = get_v_type(i, len(valid_stops))

        # 🚨 【跨線判定】：如果目前的區段已經不適用於這個車站
        if current_seg_id not in st["segs"]:
            
            # 🌟 動作 A：封裝舊路線，並「往前咬住下一站」
            # 將出界的車站一起打包，讓前端知道這條線要往哪裡畫出去
            temp_s_ids = s_ids + [st["id"]]
            temp_t_times = t_times + [st["arr"], st["dep"]]
            temp_v_types = v_types + [v_type]

            if len(temp_s_ids) > 1:
                compiled_segments.append({
                    "id": current_seg_id, 
                    "s": temp_s_ids, 
                    "t": temp_t_times, 
                    "v": temp_v_types
                })

            # 🌟 動作 B：切換新路線
            current_seg_id = st["segs"][0]

            # 🌟 動作 C：新路線「回頭咬住上一站」當作起點
            # 讓前端知道這條線是從哪裡冒出來的
            prev_st = valid_stops[i-1]
            prev_v_type = get_v_type(i-1, len(valid_stops))

            s_ids = [prev_st["id"]]
            t_times = [prev_st["arr"], prev_st["dep"]]
            v_types = [prev_v_type]

        # 將目前車站正常加入目前區段
        s_ids.append(st["id"])
        t_times.extend([st["arr"], st["dep"]])
        v_types.append(v_type)

    # 迴圈結束，儲存最後一段
    if len(s_ids) > 1:
        compiled_segments.append({
            "id": current_seg_id, 
            "s": s_ids, 
            "t": t_times, 
            "v": v_types
        })

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
    # 🌟 擴充版：涵蓋全台主要運轉端點站，確保抓到所有區間車
    station_list = [
        '0900-基隆', '0920-七堵', '1000-臺北', '1070-樹林', 
        '1210-新竹', '1250-竹南', '3360-彰化', '3190-嘉義', 
        '4220-臺南', '4400-高雄', '5050-潮州', '5120-枋寮', 
        '6000-臺東', '7000-花蓮', '7190-宜蘭', '7360-瑞芳'
    ]
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