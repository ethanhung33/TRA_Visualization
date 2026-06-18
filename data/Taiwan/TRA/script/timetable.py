import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime, timedelta
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import re

# ==========================================
# 1. 基礎設定與動態拓撲讀取 (Single Source of Truth)
# ==========================================
SCRIPT_DIR = Path(__file__).parent
JSON_DIR = SCRIPT_DIR.parent / "json"
TOPOLOGY_PATH = JSON_DIR / "topology.json"

with open(TOPOLOGY_PATH, "r", encoding="utf-8") as f:
    TOPOLOGY = json.load(f)

STATION_INFO = {}
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
        
        if seg_id == "sea_line": 
            COAST_STATIONS.add(name)
        elif seg_id == "mountain_line": 
            MOUNTAIN_STATIONS.add(name)

JUNCTIONS = {"八堵", "竹南", "彰化", "枋寮", "追分", "成功"}
COAST_STATIONS = COAST_STATIONS - JUNCTIONS
MOUNTAIN_STATIONS = MOUNTAIN_STATIONS - JUNCTIONS

print(f"🌊 自動載入海線車站: {len(COAST_STATIONS)} 站")
print(f"⛰️ 自動載入山線車站: {len(MOUNTAIN_STATIONS)} 站")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.railway.gov.tw/tra-tip-web/tip/tip001/tip112/querybyStation'
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

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
        
        if curr['name'] in COAST_STATIONS and nxt['name'] in MOUNTAIN_STATIONS:
            diff = nxt['arr'] - curr['dep']
            t1 = int(curr['dep'] + diff * 0.4)
            t2 = int(curr['dep'] + diff * 0.6)
            patched.append({"name": "追分", "arr": t1, "dep": t1, "is_pass": True})
            patched.append({"name": "成功", "arr": t2, "dep": t2, "is_pass": True})

        elif curr['name'] in MOUNTAIN_STATIONS and nxt['name'] in COAST_STATIONS:
            diff = nxt['arr'] - curr['dep']
            t1 = int(curr['dep'] + diff * 0.4)
            t2 = int(curr['dep'] + diff * 0.6)
            patched.append({"name": "成功", "arr": t1, "dep": t1, "is_pass": True})
            patched.append({"name": "追分", "arr": t2, "dep": t2, "is_pass": True})

    return patched

# ==========================================
# 2. 核心編譯邏輯
# ==========================================
def compile_train_data(raw_stops):
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
                    "is_pass": st.get("is_pass", False)
                })

    if not valid_stops: return []

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

    def get_v_type(idx, total, st_data):
        if idx == 0: return TYPE_MAP["START"]
        if idx == total - 1: return TYPE_MAP["END"]
        if st_data.get("is_pass", False): return TYPE_MAP["PASS"]
        return TYPE_MAP["STOP"]

    compiled_segments = []
    current_seg_id = valid_stops[0]["true_seg"]
    s_ids, t_times, v_types = [], [], []

    def get_junction(seg1, seg2):
        for name, info in STATION_INFO.items():
            if seg1 in info["segments"] and seg2 in info["segments"]: return info
        return None

    for i in range(len(valid_stops)):
        st = valid_stops[i]
        v_type = get_v_type(i, len(valid_stops), st)
        
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
def fetch_worker(t_type, t_no, seen_dates, max_retries=3):
    dates_to_try = set()
    for d in seen_dates:
        dates_to_try.add(d)
        dt = datetime.strptime(d, "%Y/%m/%d")
        prev_dt = dt - timedelta(days=1)
        dates_to_try.add(prev_dt.strftime("%Y/%m/%d"))
    
    dates_to_try = sorted(list(dates_to_try))
    
    for date in dates_to_try:
        url = f"https://www.railway.gov.tw/tra-tip-web/tip/tip001/tip112/querybytrainno?rideDate={date}&trainNo={t_no}"
        
        for attempt in range(max_retries):
            try:
                time.sleep(1) 
                resp = SESSION.get(url, timeout=15)
                resp.raise_for_status() 
                
                soup = BeautifulSoup(resp.text, "html.parser")
                tbodies = soup.find_all("tbody")
                
                if len(tbodies) < 2: 
                    if any(msg in resp.text for msg in ["查無", "沒有找到", "無法查詢", "alert"]):
                        break 
                    else:
                        raise ValueError("WAF")
                
                raw_stops, last_time = [], -1

                for tbody in tbodies[1:]:
                    for row in tbody.find_all("tr"):
                        cols = row.find_all("td")
                        if len(cols) < 3: continue
                        name = cols[0].get_text().strip()
                        arr, dep = time_to_min(cols[1].get_text()), time_to_min(cols[2].get_text())
                        
                        if arr < last_time: arr += 1440
                        if dep < arr: dep += 1440
                        last_time = dep
                        
                        raw_stops.append({"name": name, "arr": arr, "dep": dep, "is_pass": False})
                
                raw_stops = patch_chengzhui(raw_stops)
                segments = compile_train_data(raw_stops)
                
                if not segments: 
                    return None
                    
                return {"no": t_no, "type": t_type, "segments": segments}
                
            except ValueError:
                SESSION.cookies.clear()
                time.sleep(10)
                try: SESSION.get("https://www.railway.gov.tw/tra-tip-web/tip", timeout=10)
                except: pass
                if attempt == max_retries - 1:
                    print(f"\n❌ 車次 {t_no} ({date}) 遭遇嚴格防護，跳過。")
            except Exception as e: 
                time.sleep(2)
                
    return None

def get_date_range(start_str, end_str):
    start_date = datetime.strptime(start_str, "%Y/%m/%d")
    end_date = datetime.strptime(end_str, "%Y/%m/%d")
    days_diff = (end_date - start_date).days
    
    if days_diff < 0:
        return [start_str]
        
    dates = []
    for i in range(days_diff + 1):
        curr_date = start_date + timedelta(days=i)
        dates.append(curr_date.strftime("%Y/%m/%d"))
    return dates

# ==========================================
# 4. 主程式 (終極跨夜過濾版)
# ==========================================
def main():
    station_list = [
        '0900-基隆', '0920-七堵', '1000-臺北', '1040-樹林', '1193-竹中',
        '1210-新竹', '1250-竹南', '3300-臺中', '3360-彰化', '3430-二水', '4080-嘉義', 
        '4220-臺南', '4400-高雄', '5050-潮州', '5120-枋寮', 
        '6000-臺東', '7000-花蓮', '7130-蘇澳新', '7190-宜蘭', '7360-瑞芳'
    ]
    
    start_date = "2026/06/01" 
    end_date = "2026/08/31" 
    
    date_list = get_date_range(start_date, end_date)
    print(f"🗓️ 準備進行快取優化抓取: {start_date} ~ {end_date} (共 {len(date_list)} 天)")

    daily_train_registry = {}    
    unique_trains_to_fetch = {}  

    print("\n🔍 [階段一] 正在掃描各日期的車站看板，確認出勤車次與出沒時間...")
    for date in date_list:
        # 🌟 核心修復 1：改用 dict 記錄每班車被看到的「時間」
        daily_t_dict = {}
        
        for station in tqdm(station_list, desc=f"掃描 {date}"):
            try:
                url = f"https://www.railway.gov.tw/tra-tip-web/tip/tip001/tip112/querybystationblank?rideDate={date}&station={station}"
                resp = SESSION.get(url, timeout=10)
                soup = BeautifulSoup(resp.text, "html.parser")
                
                for tbody in soup.find_all("tbody"):
                    for row in tbody.find_all("tr"):
                        for a_tag in row.find_all("a"):
                            t_text = a_tag.get_text().strip()
                            if not any(x in t_text for x in ["自強", "區間", "普悠瑪", "太魯閣", "莒光"]): continue
                            
                            numbers = re.findall(r'\d+[A-Za-z]*', t_text)
                            if numbers:
                                t_no = numbers[-1]
                                
                                # 🌟 萃取看板上顯示的時間
                                time_matches = re.findall(r'\d{2}:\d{2}', row.get_text())
                                board_time = time_to_min(time_matches[0]) if time_matches else -1
                                
                                if t_no not in daily_t_dict:
                                    daily_t_dict[t_no] = []
                                if board_time != -1:
                                    daily_t_dict[t_no].append(board_time)
                                
                                if t_no not in unique_trains_to_fetch:
                                    if "自強(3000)" in t_text: t_type = "新自強"
                                    elif any(x in t_text for x in ["區間快", "普悠瑪", "太魯閣"]): t_type = t_text[:3]
                                    else: t_type = t_text[:2]
                                    
                                    unique_trains_to_fetch[t_no] = {"type": t_type, "seen_dates": set([date])}
                                else:
                                    unique_trains_to_fetch[t_no]["seen_dates"].add(date)
            except Exception as e: 
                continue
            time.sleep(0.3) 
            
        daily_train_registry[date] = daily_t_dict

    print(f"✅ 掃描完成！發現全區間共有 {len(unique_trains_to_fetch)} 種不重複車次。")

    print(f"\n⚡ [階段二] 開始下載時刻表 (僅需抓取 {len(unique_trains_to_fetch)} 次)...")
    train_database = {} 
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(fetch_worker, info["type"], t_no, info["seen_dates"], 3): t_no 
                   for t_no, info in unique_trains_to_fetch.items()}
        
        for f in tqdm(as_completed(futures), total=len(futures), desc="下載與編譯"):
            res = f.result()
            if res:
                train_database[res["no"]] = res

    print("\n📦 [階段三] 正在過濾幽靈車並將資料分配至正確的發車日期...")
    output_dir = JSON_DIR / "timetable"
    output_dir.mkdir(parents=True, exist_ok=True)

    for date in date_list:
        daily_results = []
        
        # 🌟 核心修復 2：利用看板時間與絕對時刻表的差集，精準抓出幽靈車！
        for t_no, board_times in daily_train_registry[date].items():
            if t_no in train_database:
                train_data = train_database[t_no]
                
                # 收集這班車從起點到終點的「絕對時間」
                sched_times = []
                for seg in train_data["segments"]:
                    sched_times.extend(seg["t"])
                    
                originates_today = False
                
                # 如果因為網頁版型變更沒抓到時間，啟動保底機制放行
                if not board_times:
                    originates_today = True
                else:
                    for b_time in board_times:
                        # 檢驗：這個出沒時間，是不是對應到它「跨夜前」(時間 < 1440) 的行程？
                        # 如果它只有在跨夜後才出現 (例如 2273 在週六凌晨 01:10 被看見)，就會被無情拋棄！
                        if any(s_time < 1440 and abs(s_time - b_time) <= 15 for s_time in sched_times):
                            originates_today = True
                            break
                            
                if originates_today:
                    daily_results.append(train_data)
                
        daily_results.sort(key=lambda x: int(re.sub(r'\D', '', str(x.get("no", "0"))) or 0))

        output_path = output_dir / f"timetable_{date.replace('/','')}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("[\n")
            for i, res in enumerate(daily_results):
                line = json.dumps(res, ensure_ascii=False, separators=(',', ':'))
                if i < len(daily_results) - 1: f.write(line + ",\n")
                else: f.write(line + "\n")
            f.write("]\n")
            
        print(f"🎉 成功組裝 {date} (共 {len(daily_results)} 班) -> {output_path.name}")

    print("\n🚀 任務全數完美結束！")

if __name__ == "__main__":
    main()