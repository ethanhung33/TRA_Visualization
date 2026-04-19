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
    # ==========================================
    # 1. 預先過濾 (🔥 刪除所有 is_mountain 判斷，全靠雷達！)
    # ==========================================
    valid_stops = []
    for st in raw_stops:
        name = st['name']
        if name in STATION_INFO:
            st_info = STATION_INFO[name]
            segs = list(st_info["segments"]) 

            # 只要有找到對應的路線，就直接收進來，我們相信後面的雷達！
            if segs:
                valid_stops.append({
                    "id": st_info["id"],
                    "arr": st['arr'],
                    "dep": st['dep'],
                    "segs": segs,
                    "km_map": st_info["km_map"]
                })

    if not valid_stops: return []

    # ==========================================
    # 🌟 1.5 未來雷達 (🔥 升級：終點站繼承法)
    # ==========================================
    for i in range(len(valid_stops)):
        current_segs = valid_stops[i]["segs"]
        
        # 1. 看下一站找交集
        if i < len(valid_stops) - 1:
            next_segs = valid_stops[i+1]["segs"]
            common_segs = [s for s in current_segs if s in next_segs]
            
            if common_segs:
                valid_stops[i]["true_seg"] = common_segs[0]
                continue

        # 2. 如果沒有下一站 (終點)，或找不到交集...
        # 🌟 終極防呆：回頭看上一站！如果上一站的路線我也有，就繼續走！
        if i > 0:
            prev_seg = valid_stops[i-1].get("true_seg")
            if prev_seg and prev_seg in current_segs:
                valid_stops[i]["true_seg"] = prev_seg
                continue
                
        # 3. 最衰保底 (正常情況下不會走到這)
        valid_stops[i]["true_seg"] = current_segs[0]

    # ... (下面 2. 核心分段 的迴圈完全不用動！)

    TYPE_MAP = {"START": 0, "STOP": 1, "PASS": 2, "END": 3}

    def get_v_type(idx, total):
        if idx == 0: return TYPE_MAP["START"]
        if idx == total - 1: return TYPE_MAP["END"]
        return TYPE_MAP["STOP"]

    # ==========================================
    # 🌟 2. 核心分段 (現在變得超級簡單，完全依賴 true_seg)
    # ==========================================
    compiled_segments = []
    current_seg_id = valid_stops[0]["true_seg"]
    s_ids, t_times, v_types = [], [], []

    # 交會站函數保留
    def get_junction(seg1, seg2):
        for name, info in STATION_INFO.items():
            if seg1 in info["segments"] and seg2 in info["segments"]: return info
        return None

    for i in range(len(valid_stops)):
        st = valid_stops[i]
        v_type = get_v_type(i, len(valid_stops))
        
        # 🌟 因為我們有雷達，路線切換會「精準發生在成功站」！
        if st["true_seg"] != current_seg_id:
            
            # 情況 A：無縫接軌 (舊路線有這個站，例如：成功有山線)
            if current_seg_id in st["segs"]:
                # 1. 結束舊路線
                s_ids.append(st["id"])
                t_times.extend([st['arr'], st['dep']])
                v_types.append(v_type)
                
                if len(s_ids) > 1:
                    compiled_segments.append({"id": current_seg_id, "s": s_ids, "t": t_times, "v": v_types})
                
                # 2. 開啟新路線
                current_seg_id = st["true_seg"]
                s_ids = [st["id"]]
                t_times = [st['arr'], st['dep']]
                v_types = [v_type]
                
            # 情況 B：跳站內插 (跟之前一樣，保留你的寫法)
            else:
                junc = get_junction(current_seg_id, st["true_seg"])
                if junc:
                    prev_st = valid_stops[i-1]
                    km1 = prev_st["km_map"].get(current_seg_id, 0)
                    km2 = st["km_map"].get(st["true_seg"], 0)
                    kmJ1 = junc["km_map"].get(current_seg_id, 0)
                    kmJ2 = junc["km_map"].get(st["true_seg"], 0)
                    
                    d1, d2 = abs(kmJ1 - km1), abs(km2 - kmJ2)
                    total_d = d1 + d2
                    ratio = d1 / total_d if total_d > 0 else 0
                    t_junc = int(prev_st["dep"] + (st["arr"] - prev_st["dep"]) * ratio)
                    
                    s_ids.append(junc["id"])
                    t_times.extend([t_junc, t_junc])
                    v_types.append(TYPE_MAP["PASS"])
                    
                    if len(s_ids) > 1:
                        compiled_segments.append({"id": current_seg_id, "s": s_ids, "t": t_times, "v": v_types})
                        
                    current_seg_id = st["true_seg"]
                    s_ids = [junc["id"]]
                    t_times = [t_junc, t_junc]
                    v_types = [TYPE_MAP["PASS"]]
                
                s_ids.append(st["id"])
                t_times.extend([st['arr'], st['dep']])
                v_types.append(v_type)
        else:
            # 同路線正常加入
            s_ids.append(st["id"])
            t_times.extend([st['arr'], st['dep']])
            v_types.append(v_type)

    if len(s_ids) > 1:
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
    except: 
        print(f"❌ 獲取車次 {t_no} 時發生錯誤")
        import traceback
        traceback.print_exc() # 這行會印出到底是哪一行程式碼爆炸的！
        return None

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