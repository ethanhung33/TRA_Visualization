import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime, timedelta
from tqdm import tqdm
import sys
from pathlib import Path

# ==========================================
# 1. 環境設定與 Topology 載入
# ==========================================
SCRIPT_DIR = Path(__file__).parent
JSON_DIR = SCRIPT_DIR.parent / "json"
TOPOLOGY_PATH = JSON_DIR / "topology.json"

if not TOPOLOGY_PATH.exists():
    print(f"❌ 找不到 {TOPOLOGY_PATH}，請先執行 build_topology.py")
    sys.exit(1)

with open(TOPOLOGY_PATH, "r", encoding="utf-8") as f:
    TOPOLOGY = json.load(f)

STATION_INFO = {}
for seg in TOPOLOGY['segments']:
    for st in seg['stations']:
        name = st['name']
        if name not in STATION_INFO:
            STATION_INFO[name] = {"segments": [], "km_map": {}}
        STATION_INFO[name]["segments"].append(seg['id'])
        STATION_INFO[name]["km_map"][seg['id']] = st['km']

JUNCTIONS = ["八堵", "竹南", "彰化", "枋寮"]

# 偽裝瀏覽器 Header
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.railway.gov.tw/tra-tip-web/tip/tip001/tip112/querybyStation'
}

# ==========================================
# 2. 工具函數
# ==========================================
def time_to_min(time_str):
    try:
        parts = list(map(int, time_str.split(':')))
        return parts[0] * 60 + parts[1]
    except: return 0

def interpolate_time(st1_name, st2_name, target_name, t1, t2, seg_id):
    try:
        km1 = STATION_INFO[st1_name]["km_map"][seg_id]
        km2 = STATION_INFO[st2_name]["km_map"][seg_id]
        km_target = STATION_INFO[target_name]["km_map"][seg_id]
        ratio = (km_target - km1) / (km2 - km1)
        return int(t1 + (t2 - t1) * ratio)
    except:
        return (t1 + t2) // 2

# ==========================================
# 3. 核心編譯邏輯 (處理區段切分與插值)
# ==========================================
def compile_train_data(raw_stops, is_mountain):
    compiled_segments = []
    current_seg_id = None
    seg_stops = []
    
    for i in range(len(raw_stops)):
        st_now = raw_stops[i]
        name_now = st_now['name']
        possible_segs = STATION_INFO.get(name_now, {}).get("segments", [])

        if not current_seg_id:
            current_seg_id = possible_segs[0] if possible_segs else "UNKNOWN"
        else:
            # 偵測跨越點 (這裡簡化，主要處理北轉山/海)
            if current_seg_id == "north_main" and "north_main" not in possible_segs:
                junction = "竹南"
                t_pass = interpolate_time(raw_stops[i-1]['name'], name_now, junction, raw_stops[i-1]['dep'], st_now['arr'], "north_main")
                seg_stops.append({"name": junction, "arr": t_pass, "dep": t_pass, "type": "PASS"})
                compiled_segments.append({"segment_id": current_seg_id, "stops": seg_stops})
                current_seg_id = "mountain_line" if is_mountain else "sea_line"
                seg_stops = [{"name": junction, "arr": t_pass, "dep": t_pass, "type": "PASS"}]
            
            elif current_seg_id in ["mountain_line", "sea_line"] and "south_main" in possible_segs and current_seg_id not in possible_segs:
                junction = "彰化"
                t_pass = interpolate_time(raw_stops[i-1]['name'], name_now, junction, raw_stops[i-1]['dep'], st_now['arr'], current_seg_id)
                seg_stops.append({"name": junction, "arr": t_pass, "dep": t_pass, "type": "PASS"})
                compiled_segments.append({"segment_id": current_seg_id, "stops": seg_stops})
                current_seg_id = "south_main"
                seg_stops = [{"name": junction, "arr": t_pass, "dep": t_pass, "type": "PASS"}]

        st_type = "STOP"
        if i == 0: st_type = "START"
        elif i == len(raw_stops)-1: st_type = "END"
        
        seg_stops.append({
            "name": name_now, "arr": st_now['arr'], "dep": st_now['dep'], "type": st_type
        })
        
    if seg_stops:
        compiled_segments.append({"segment_id": current_seg_id, "stops": seg_stops})
    return compiled_segments

# ==========================================
# 4. 主程式
# ==========================================
def main():
    # 這裡放你原本那串超長的 station_list
    full_station_list = ['0900-基隆','0920-八堵','1000-臺北','1210-新竹','1250-竹南','2200-大甲','3300-臺中','3360-彰化','4080-嘉義','4220-臺南','4400-高雄','5120-枋寮','6000-臺東','7000-花蓮','7190-宜蘭','7360-瑞芳'] # 先放代表性的測試
    
    # 🌟 日期自動設為明天，避免深夜抓不到車
    date = (datetime.today() + timedelta(days=1)).strftime("%Y/%m/%d")
    
    train_list = set()
    print(f"📡 正在抓取 {date} 的車次清單...")
    
    for station in tqdm(full_station_list):
        try:
            url = f"https://www.railway.gov.tw/tra-tip-web/tip/tip001/tip112/querybystationblank?rideDate={date}&station={station}"
            resp = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            tbodies = soup.find_all("tbody")
            
            for tbody in tbodies[:2]:
                for row in tbody.find_all("tr"):
                    content = row.find_all("td")
                    if len(content) < 2: continue
                    a_tag = content[1].find("a")
                    if not a_tag: continue
                    
                    train_id_text = a_tag.get_text().strip()
                    # 車種解析邏輯
                    if "自強(3000)" in train_id_text:
                        train_list.add(("新自強", train_id_text[8:]))
                    elif any(x in train_id_text for x in ["區間快", "普悠瑪", "太魯閣"]):
                        train_list.add((train_id_text[:3], train_id_text[3:]))
                    else:
                        train_list.add((train_id_text[:2], train_id_text[2:]))
        except: continue

    train_list = list(train_list)
    print(f"🚆 抓到 {len(train_list)} 班車，開始編譯詳細時刻表...")

    final_json = []
    # 這裡我們只抓前 50 班來測試穩定性，沒問題再拿掉 [:50]
    for (t_type, t_no) in tqdm(train_list[:50]):
        url = f"https://www.railway.gov.tw/tra-tip-web/tip/tip001/tip112/querybytrainno?rideDate={date}&trainNo={t_no}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            rows = soup.find_all("tbody")[1].find_all("tr")
            
            raw_stops = []
            last_time = -1
            has_mountain_station = False
            
            # 山線特有站清單 (用於判定路徑)
            mountain_specific = [s['name'] for s in TOPOLOGY['segments'][1]['stations'] if s['name'] not in JUNCTIONS]

            for row in rows:
                cols = row.find_all("td")
                if len(cols) < 3: continue
                st_name = cols[0].get_text().strip()
                arr = time_to_min(cols[1].get_text())
                dep = time_to_min(cols[2].get_text())
                
                # 跨日邏輯
                if arr < last_time: arr += 1440
                if dep < arr: dep += 1440
                last_time = dep
                
                if st_name in mountain_specific: has_mountain_station = True
                raw_stops.append({"name": st_name, "arr": arr, "dep": dep})
            
            segments = compile_train_data(raw_stops, has_mountain_station)
            final_json.append({
                "train_no": t_no,
                "train_type": t_type,
                "segments": segments
            })
        except: continue

    # 儲存 JSON
    output_fn = f"timetable_{date.replace('/','')}.json"
    output_path = JSON_DIR / output_fn
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_json, f, ensure_ascii=False, indent=2)
    
    print(f"\n🎉 成功！編譯完成 {len(final_json)} 班車。\n👉 {output_path.resolve()}")

if __name__ == "__main__":
    main()