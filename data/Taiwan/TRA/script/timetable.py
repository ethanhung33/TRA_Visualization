import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# ==========================================
# 1. 基礎設定與動態拓撲讀取 (Single Source of Truth)
# ==========================================
SCRIPT_DIR = Path(__file__).parent
JSON_DIR = SCRIPT_DIR.parent / "json"
TOPOLOGY_PATH = JSON_DIR / "topology.json"

with open(TOPOLOGY_PATH, "r", encoding="utf-8") as f:
    TOPOLOGY = json.load(f)

STATION_INFO = {}

# 準備兩個空的 Set，用來裝動態抓取的山海線車站
COAST_STATIONS = set()
MOUNTAIN_STATIONS = set()

for seg in TOPOLOGY['segments']:
    seg_id = seg.get('id', '')
    
    for st in seg['stations']:
        name = st['name']
        if name not in STATION_INFO:
            STATION_INFO[name] = {"segments": [], "km_map": {}, "id": st['id']}
        STATION_INFO[name]["segments"].append(seg_id)
        STATION_INFO[name]["km_map"][seg_id] = st['km']
        
        # 🌟 動態分類：直接根據 topology 裡的 segment ID 建立山海線勢力範圍
        if seg_id == "sea_line":  # 請確認這個 ID 跟你的 json 吻合
            COAST_STATIONS.add(name)
        elif seg_id == "mountain_line": # 請確認這個 ID 跟你的 json 吻合
            MOUNTAIN_STATIONS.add(name)

# 剔除交會站，確保跨線判定的絕對精準
JUNCTIONS = {"八堵", "竹南", "彰化", "枋寮", "追分", "成功"}
COAST_STATIONS = COAST_STATIONS - JUNCTIONS
MOUNTAIN_STATIONS = MOUNTAIN_STATIONS - JUNCTIONS

print(f"🌊 自動載入海線車站: {len(COAST_STATIONS)} 站")
print(f"⛰️ 自動載入山線車站: {len(MOUNTAIN_STATIONS)} 站")

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
# 🌟 1.5 拓撲修補器 (成追線自動內插)
# ==========================================
def patch_chengzhui(raw_stops):
    patched = []
    for i in range(len(raw_stops)):
        curr = raw_stops[i]
        patched.append(curr)

        if i == len(raw_stops) - 1:
            break

        nxt = raw_stops[i + 1]
        
        # A. 海轉山 (南下跨線)
        if curr['name'] in COAST_STATIONS and nxt['name'] in MOUNTAIN_STATIONS:
            diff = nxt['arr'] - curr['dep']
            t1 = int(curr['dep'] + diff * 0.4)
            t2 = int(curr['dep'] + diff * 0.6)
            patched.append({"name": "追分", "arr": t1, "dep": t1, "is_pass": True})
            patched.append({"name": "成功", "arr": t2, "dep": t2, "is_pass": True})

        # B. 山轉海 (北上跨線)
        elif curr['name'] in MOUNTAIN_STATIONS and nxt['name'] in COAST_STATIONS:
            diff = nxt['arr'] - curr['dep']
            t1 = int(curr['dep'] + diff * 0.4)
            t2 = int(curr['dep'] + diff * 0.6)
            patched.append({"name": "成功", "arr": t1, "dep": t1, "is_pass": True})
            patched.append({"name": "追分", "arr": t2, "dep": t2, "is_pass": True})

    return patched

# ==========================================
# 2. 核心編譯邏輯 (終極雷達版 + 支援通過站)
# ==========================================
def compile_train_data(raw_stops):
    # 1. 預先過濾
    valid_stops = []
    for st in raw_stops:
        name = st['name']
        if name in STATION_INFO:
            st_info = STATION_INFO[name]
            segs = list(st_info["segments"]) 
            if segs:
                valid_stops.append({
                    "id": st_info["id"],
                    "arr": st['arr'],
                    "dep": st['dep'],
                    "segs": segs,
                    "km_map": st_info["km_map"],
                    "is_pass": st.get("is_pass", False) # 🌟 讀取剛剛修補的標籤
                })

    if not valid_stops: return []

    # 1.5 未來雷達 (終點站繼承法)
    for i in range(len(valid_stops)):
        current_segs = valid_stops[i]["segs"]
        
        if i < len(valid_stops) - 1:
            next_segs = valid_stops[i+1]["segs"]
            common_segs = [s for s in current_segs if s in next_segs]
            if common_segs:
                valid_stops[i]["true_seg"] = common_segs[0]
                continue

        if i > 0:
            prev_seg = valid_stops[i-1].get("true_seg")
            if prev_seg and prev_seg in current_segs:
                valid_stops[i]["true_seg"] = prev_seg
                continue
                
        valid_stops[i]["true_seg"] = current_segs[0]

    TYPE_MAP = {"START": 0, "STOP": 1, "PASS": 2, "END": 3}

    # 🌟 讓編譯器知道這站是「通過」還是「停靠」
    def get_v_type(idx, total, st_data):
        if idx == 0: return TYPE_MAP["START"]
        if idx == total - 1: return TYPE_MAP["END"]
        if st_data.get("is_pass", False): return TYPE_MAP["PASS"]
        return TYPE_MAP["STOP"]

    # 2. 核心分段
    compiled_segments = []
    current_seg_id = valid_stops[0]["true_seg"]
    s_ids, t_times, v_types = [], [], []

    def get_junction(seg1, seg2):
        for name, info in STATION_INFO.items():
            if seg1 in info["segments"] and seg2 in info["segments"]: return info
        return None

    for i in range(len(valid_stops)):
        st = valid_stops[i]
        v_type = get_v_type(i, len(valid_stops), st) # 🌟 傳入 st
        
        if st["true_seg"] != current_seg_id:
            if current_seg_id in st["segs"]:
                s_ids.append(st["id"])
                t_times.extend([st['arr'], st['dep']])
                v_types.append(v_type)
                
                if len(s_ids) > 1:
                    compiled_segments.append({"id": current_seg_id, "s": s_ids, "t": t_times, "v": v_types})
                
                current_seg_id = st["true_seg"]
                s_ids = [st["id"]]
                t_times = [st['arr'], st['dep']]
                v_types = [v_type]
                
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
            s_ids.append(st["id"])
            t_times.extend([st['arr'], st['dep']])
            v_types.append(v_type)

    if len(s_ids) > 1:
        compiled_segments.append({"id": current_seg_id, "s": s_ids, "t": t_times, "v": v_types})

    return compiled_segments

# ==========================================
# 3. 執行緒工作任務
# ==========================================
def fetch_worker(t_type, t_no, date):
    url = f"https://www.railway.gov.tw/tra-tip-web/tip/tip001/tip112/querybytrainno?rideDate={date}&trainNo={t_no}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        tbodies = soup.find_all("tbody")
        if len(tbodies) < 2: return None
        
        rows = tbodies[1].find_all("tr")
        raw_stops, last_time = [], -1

        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 3: continue
            name = cols[0].get_text().strip()
            arr, dep = time_to_min(cols[1].get_text()), time_to_min(cols[2].get_text())
            
            if arr < last_time: arr += 1440
            if dep < arr: dep += 1440
            last_time = dep
            
            # 🌟 加上 is_pass 預設值
            raw_stops.append({"name": name, "arr": arr, "dep": dep, "is_pass": False})
        
        # 🌟 啟動拓撲修補！
        raw_stops = patch_chengzhui(raw_stops)
        
        segments = compile_train_data(raw_stops)
        
        if not segments: return None
            
        return {"no": t_no, "type": t_type, "segments": segments}
    except Exception as e: 
        print(f"❌ 獲取車次 {t_no} 時發生錯誤: {e}")
        return None

# ==========================================
# 4. 主程式
# ==========================================
def main():
    station_list = [
        '0900-基隆', '0920-七堵', '1000-臺北', '1070-樹林', 
        '1210-新竹', '1250-竹南', '3300-臺中', '3360-彰化', '3190-嘉義', 
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

    # 確保輸出目錄存在
    output_dir = JSON_DIR / "timetable"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"timetable_{date.replace('/','')}.json"
    
    # 🌟 完美的「一班車一行」輸出邏輯
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("[\n")
        for i, res in enumerate(results):
            line = json.dumps(res, ensure_ascii=False, separators=(',', ':'))
            if i < len(results) - 1:
                f.write(line + ",\n")
            else:
                f.write(line + "\n")
        f.write("]\n")
    
    print(f"🎉 完美儲存！請查看 {output_path}")

if __name__ == "__main__":
    main()