import urllib.request
import re
import json
import os
from tqdm import tqdm
from collections import OrderedDict

# ==========================================
# 🌟 全域路徑設定
# ==========================================
script_dir = os.path.dirname(os.path.abspath(__file__))
system_dir = os.path.dirname(script_dir)
json_dir = os.path.join(system_dir, "json")

def to_minutes(hh_mm):
    """將 HH:MM 字串轉換為當天的絕對分鐘數"""
    if not hh_mm: return ""
    try:
        h, m = map(int, hh_mm.split(':'))
        return h * 60 + m
    except:
        return ""

def clean_text(text):
    """清除 HTML 標籤與不必要的空白"""
    is_split = "分割" in text
    is_through = "直通" in text
    text = re.sub(r'<[^>]+>', '', text)
    cleaned = "".join(text.split())
    if is_split: return "分割" + cleaned.replace("分割", "")
    if is_through: return "直通" + cleaned.replace("直通", "")
    return cleaned

def fetch_and_parse_timetable(date_str):
    """
    爬取 JR Odekake 網站的時刻表資料，並在記憶體中整理成原始的火車物件列表。
    這個函數合併了原本的 fetch_train_ids 和 fetch_train_details。
    """
    route_file_path = os.path.join(json_dir, 'station_route_shinkansen.json')
    if not os.path.exists(route_file_path):
        print(f"❌ 找不到路線定義檔！請確認檔案存在: {route_file_path}")
        return []

    with open(route_file_path, 'r', encoding='utf-8') as f:
        routes = json.load(f)

    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # 1. 收集所有不重複的 Train ID
    seen_pairs = set()
    train_entries = []
    
    for route_obj in tqdm(routes, desc="🔍 搜尋列車 ID"):
        route_name = route_obj.get("route", "Unknown Route")
        r_id = route_obj.get("id")
        if not r_id: continue

        url = f"https://timetable.jr-odekake.net/station-timetable/{r_id}?date={date_str}"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req) as response:
                html_content = response.read().decode('utf-8')
                
            train_id_pattern = r'href="/train-timetable/(\d+)\?date='
            found_ids = re.findall(train_id_pattern, html_content)
            
            for t_id in found_ids:
                pair = (route_name, t_id)
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    train_entries.append({"route": route_name, "id": t_id})
        except Exception as e:
            tqdm.write(f"  ❌ 抓取路線 {r_id} 失敗: {e}")

    # 2. 爬取每一班車的詳細時刻表
    all_raw_trains = []
    for entry in tqdm(train_entries, desc="🚄 下載並解析時刻表"):
        t_id = entry.get("id")
        t_route = entry.get("route", "")
        
        url = f"https://timetable.jr-odekake.net/train-timetable/{t_id}"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req) as response:
                html = response.read().decode('utf-8')

            details_match = re.search(r'<tbody class="train-details">(.*?)</tbody>', html, re.DOTALL)
            if not details_match: continue

            rows = re.findall(r'<tr>(.*?)</tr>', details_match.group(1), re.DOTALL)
            first_row_tds = re.findall(r'<td.*?>(.*?)</td>', rows[0], re.DOTALL)
            num_trains = len(first_row_tds)

            page_trains = [OrderedDict() for _ in range(num_trains)]

            for row in rows:
                th_match = re.search(r'<th.*?>(.*?)</th>', row, re.DOTALL)
                if not th_match: continue
                key = clean_text(th_match.group(1))
                tds = re.findall(r'<td.*?>(.*?)</td>', row, re.DOTALL)
                for i in range(min(len(tds), num_trains)):
                    page_trains[i][key] = clean_text(tds[i])
                    page_trains[i]["route"] = t_route

            time_match = re.search(r'<tbody class="time-details">(.*?)</tbody>', html, re.DOTALL)
            if time_match:
                time_rows = re.findall(r'<tr>(.*?)</tr>', time_match.group(1), re.DOTALL)
                for row in time_rows:
                    sta_match = re.search(r'<td class="cell-fixed">(.*?)</td>', row, re.DOTALL)
                    if not sta_match: continue
                    sta_name = clean_text(sta_match.group(1))
                    data_cells = re.findall(r'<td.*?>(.*?)</td>', row, re.DOTALL)[1:]
                    
                    for i in range(num_trains):
                        cell_idx = i * 2
                        if cell_idx >= len(data_cells): continue
                        raw_cell = data_cells[cell_idx]
                        
                        if '<div>レ</div>' in raw_cell or '<div>||</div>' in raw_cell: continue
                            
                        arr_m = re.search(r'(\d{2}:\d{2})<span class="destination">\s*着', raw_cell)
                        dep_m = re.search(r'(\d{2}:\d{2})<span class="destination">\s*発', raw_cell)
                        
                        arr_val = to_minutes(arr_m.group(1)) if arr_m else ""
                        dep_val = to_minutes(dep_m.group(1)) if dep_m else ""
                        
                        if arr_val != "" or dep_val != "" or "分割" in raw_cell or "直通" in raw_cell:
                            entry_data = {"sta": sta_name, "arr": arr_val, "dep": dep_val}
                            if "data" not in page_trains[i]: page_trains[i]["data"] = []
                            page_trains[i]["data"].append(entry_data)

            # 整理物件屬性順序
            for train in page_trains:
                if "data" in train:
                    data_temp = train.pop("data")
                    final_train = OrderedDict({"列車番号": train.pop("列車番号", "")})
                    final_train.update(train)
                    final_train["data"] = data_temp
                    all_raw_trains.append(final_train)

        except Exception as e:
            tqdm.write(f"  ❌ 解析列車 {t_id} 失敗: {e}")

    return all_raw_trains

def convert_to_segments(raw_trains):
    """
    將原始的火車物件列表，對照 topology.json 轉換成前端畫布所需的 segments 格式。
    """
    topology_path = os.path.join(json_dir, "topology.json")
    print("\n3. 正在讀取並解析 topology.json...")
    if not os.path.exists(topology_path):
        print(f"❌ 找不到 topology.json！路徑: {topology_path}")
        return []

    with open(topology_path, 'r', encoding='utf-8') as f:
        topology_data = json.load(f)

    MASTER_LINES = {}
    STATION_ID_MAP = {}
    
    for segment in topology_data.get("segments", []):
        line_id = segment.get("id")
        station_names = []
        for st in segment.get("stations", []):
            st_name = st.get("name")
            station_names.append(st_name)
            STATION_ID_MAP[st_name] = st.get("id") 
        MASTER_LINES[line_id] = station_names
        
    print(f"  ✅ 成功載入 {len(MASTER_LINES)} 條路線地圖！")

    formatted_trains = []
    print("4. 正在縫合路線並格式化時刻表...")

    for train in raw_trains:
        train_no = str(train.get("列車番号", ""))
        raw_name = train.get("列車名", "")
        
        type_match = re.match(r'([^\d]+)', raw_name)
        train_type = type_match.group(1).strip() if type_match else raw_name
        
        stops = train.get("data", [])
        if not stops: continue

        stop_dict = {}
        for st in stops:
            arr = st.get("arr", "")
            dep = st.get("dep", "")
            if arr == "": arr = dep
            if dep == "": dep = arr
            if arr == "" and dep == "": continue 
            stop_dict[st["sta"]] = {"arr": int(arr), "dep": int(dep)}
            
        t_stops_order = list(stop_dict.keys())
        raw_segments = []
        
        for line_id, line_stations in MASTER_LINES.items():
            intersect = [st for st in t_stops_order if st in line_stations]
            if len(intersect) < 2: continue
            
            idx_first = line_stations.index(intersect[0])
            idx_last = line_stations.index(intersect[-1])
            ordered_stations = line_stations if idx_first < idx_last else line_stations[::-1]
            
            s_list = []
            t_list = []
            v_list = []
            
            intersect_in_order = [s for s in ordered_stations if s in stop_dict]
            
            for i, st_name in enumerate(intersect_in_order):
                d = stop_dict[st_name]
                v_val = 1
                if i == 0: v_val = 0
                elif i == len(intersect_in_order) - 1: v_val = 3
                
                st_id = STATION_ID_MAP.get(st_name, st_name)
                s_list.append(st_id)
                t_list.extend([d["arr"], d["dep"]])
                v_list.append(v_val)

            if s_list:
                raw_segments.append({
                    "id": line_id,
                    "s": s_list,
                    "t": t_list,
                    "v": v_list,
                    "_s_set": set(s_list)
                })

        filtered_segments = []
        for i, seg_i in enumerate(raw_segments):
            is_subset = False
            for j, seg_j in enumerate(raw_segments):
                if i != j and seg_i["_s_set"].issubset(seg_j["_s_set"]):
                    if len(seg_i["_s_set"]) < len(seg_j["_s_set"]) or i > j:
                        is_subset = True
                        break
            if not is_subset:
                filtered_segments.append(seg_i)

        for seg in filtered_segments:
            if "_s_set" in seg:
                del seg["_s_set"]

        if filtered_segments:
            filtered_segments.sort(key=lambda seg: seg["t"][0] if seg["t"] else 9999)
            formatted_trains.append({
                "no": train_no,
                "type": train_type,
                "segments": filtered_segments
            })

    return formatted_trains

def main():
    target_date = "20260505" # 🌟 這裡設定你要抓取的日期 (檔名會自動跟隨這個變數)
    
    print(f"🚀 開始執行新幹線時刻表爬蟲與轉換程序 (目標日期: {target_date})")
    
    # 確保 json 資料夾存在
    os.makedirs(json_dir, exist_ok=True)
    
    # ==========================================
    # 🌟 核心新增：自動建立 timetable 子資料夾
    # ==========================================
    timetable_dir = os.path.join(json_dir, "timetable")
    os.makedirs(timetable_dir, exist_ok=True)
    
    # 步驟 1 & 2: 爬取並解析資料 (存於記憶體)
    raw_train_data = fetch_and_parse_timetable(target_date)
    
    if not raw_train_data:
        print("❌ 沒有抓到任何資料，程式結束。")
        return

    # 步驟 3: 轉換為前端 Segments 格式
    formatted_trains = convert_to_segments(raw_train_data)
    
    # ==========================================
    # 🌟 核心新增：動態命名輸出檔案路徑
    # ==========================================
    output_filename = f"timetable_{target_date}.json"
    output_path = os.path.join(timetable_dir, output_filename)
    
    print(f"\n5. 正在輸出時刻表 (共 {len(formatted_trains)} 班)...")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("[\n")
        for i, train in enumerate(formatted_trains):
            line = json.dumps(train, ensure_ascii=False, separators=(',', ':'))
            comma = "," if i < len(formatted_trains) - 1 else ""
            f.write(f"  {line}{comma}\n")
        f.write("]\n")

    print(f"\n🎉 完美大功告成！已將時刻表精準存入：\n👉 {output_path}")

if __name__ == "__main__":
    main()