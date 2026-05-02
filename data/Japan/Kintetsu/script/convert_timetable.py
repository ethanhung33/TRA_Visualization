import json
import os
import re

# ==========================================
# 🛠️ 站名對應翻譯蒟蒻 (STATION_MAPPING)
# 確保你同學抓下來的站名能完美對應到 topology.json
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

# 🛡️ 直通運轉黑名單 (過濾外網車站)
EXTERNAL_NETWORKS = {
    "桜川", "ドーム前", "九条（京都地下鉄）", "九条（阪神）", "西九条", "千鳥橋", "伝法", "福", "出来島", "大物", "尼崎",
    "尼崎センタープール前", "武庫川", "鳴尾・武庫川女子大前", "甲子園", "久寿川", "今津", 
    "西宮", "香櫨園", "打出", "芦屋", "深江", "青木", "魚崎", "住吉", "御影", "石屋川", 
    "新在家", "大石", "西灘", "岩屋", "西代", "神戸三宮", "元町", "神戸高速",
    "国際会館", "松ヶ崎", "北山", "北大路", "鞍馬口", "今出川", "丸太町", "烏丸御池", 
    "四条", "五条", "くいな橋", "十条",
    "コスモスクエア", "大阪港", "朝潮橋", "弁天町", "阿波座", "本町", "堺筋本町", 
    "谷町四丁目", "森ノ宮", "緑橋", "深江橋", "高井田",
    "「観光特急あをによし」の運行日はこちらをご覧ください。特急の車種は予告なく変更する場合があります。",
    "「観光特急しまかぜ」の運行日はこちらをご覧ください。特急の車種は予告なく変更する場合があります。",
    "夢洲"
}

MISSING_STATIONS = set()

def clean_station_name(name):
    name = re.sub(r'\[.*?\]', '', name)
    name = re.sub(r'（.*?）', '', name)
    name = name.replace('\u3000', '').replace(' ', '')
    if name.endswith("駅"):
        name = name[:-1]
    name = name.strip()
    return STATION_MAPPING.get(name, name)

def clean_train_type(raw_type):
    """清理車種名稱，移除括號備註與ひのとり的車次編號"""
    if not raw_type:
        return "Unknown"
        
    # 1. 移除全形或半形括號及其內部所有文字 (例如: （車いす対応車両・車内販売）)
    cleaned = re.sub(r'（.*?）|\(.*?\)', '', raw_type)
    
    # 2. 移除「特急ひのとり」後面的「XX列車」字眼 (例如: 10列車)
    cleaned = re.sub(r'\d+列車', '', cleaned)
    
    # 3. 移除多餘的空白
    return cleaned.strip()

def parse_time(t_val):
    """處理時間欄位，應對整數或類似 '−' 的字串"""
    if isinstance(t_val, int):
        return t_val
    if isinstance(t_val, str):
        if t_val.isdigit():
            return int(t_val)
        # 應對各種全形/半形減號或空值
        if t_val in ["-", "−", "—", "", "－"]:
            return None
    return None

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

        arr = parse_time(stop.get("arr"))
        dep = parse_time(stop.get("dep"))
        
        # 補齊缺少的時間 (例如始發站只有出發時間)
        if arr is None and dep is not None: arr = dep
        if dep is None and arr is not None: dep = arr
        if arr is None and dep is None: arr, dep = 0, 0
        
        # 標記起訖點狀態
        if i == 0: v = 0
        elif i == len(stops) - 1: v = 3
        else: v = 1
            
        s_arr.append(st_id)
        t_arr.extend([arr, dep])
        v_arr.append(v)
        
    return {"id": seg_id, "s": s_arr, "t": t_arr, "v": v_arr}

def format_nankai_style(raw_train, station_map, train_idx, day_type):
    stop_data = raw_train.get("data", [])
    if not stop_data: return None

    # 過濾外網車站
    valid_stops = []
    for stop in stop_data:
        st_name = clean_station_name(stop["station"])
        if st_name in station_map:
            valid_stops.append(stop)
        elif st_name not in EXTERNAL_NETWORKS and st_name not in MISSING_STATIONS:
            MISSING_STATIONS.add(st_name)

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

    # 生成車次編號，加上 H (Holiday) 或 W (Weekday) 方便識別
    prefix = "W" if "平日" in day_type else "H"
    train_no = raw_train.get("no", f"1-{prefix}{train_idx:04d}")

    return {
        "no": train_no, 
        "type": clean_train_type(raw_train.get("type", "Unknown")), 
        "segments": segments
    }

def save_compact_json(data, output_path):
    """以一班車一行的緊湊格式寫入 JSON"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("[\n")
        for i, train in enumerate(data):
            train_json_str = json.dumps(train, ensure_ascii=False, separators=(',', ':'))
            f.write(f"  {train_json_str}")
            if i < len(data) - 1:
                f.write(",\n")
            else:
                f.write("\n")
        f.write("]\n")

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_dir = os.path.join(script_dir, '..', 'json')
    
    topology_path = os.path.join(json_dir, 'topology.json')
    # 讀取你同學抓下來的檔案
    input_file_path = os.path.join(json_dir, 'raw_timetable.json') 
    
    # 分別設定平日與假日的輸出路徑
    weekday_output_path = os.path.join(json_dir, 'timetable', 'timetable_weekday.json')
    holiday_output_path = os.path.join(json_dir, 'timetable', 'timetable_holiday.json')

    # 1. 載入 Topology
    print("📂 載入 Topology 資料...")
    try:
        with open(topology_path, 'r', encoding='utf-8') as f:
            topology_data = json.load(f)
        station_map = build_station_map(topology_data)
    except FileNotFoundError:
        print(f"❌ 找不到 topology.json，請確認路徑: {topology_path}")
        return

    # 2. 載入原始時刻表
    print(f"📂 載入原始時刻表: {input_file_path}")
    try:
        with open(input_file_path, 'r', encoding='utf-8') as f:
            raw_timetable = json.load(f)
    except FileNotFoundError:
        print(f"❌ 找不到原始資料，請確認檔案是否命名為 raw_timetable.json 並放在: {input_file_path}")
        return

    # 3. 開始轉換與分流
    print(f"🔄 開始轉換並分流 {len(raw_timetable)} 筆車次資料...")
    weekday_timetable = []
    holiday_timetable = []
    
    for idx, raw_train in enumerate(raw_timetable, start=1):
        # 讀取 date 欄位，預設視為平日
        date_type = raw_train.get("date", "平日")
        
        formatted_train = format_nankai_style(raw_train, station_map, idx, date_type)
        if formatted_train:
            # 依照 "平日" 或 "假日(土休日)" 進行分流
            if "平日" in date_type:
                weekday_timetable.append(formatted_train)
            else:
                holiday_timetable.append(formatted_train)

    # 4. 輸出檔案
    print("💾 正在寫入 平日 JSON 檔案...")
    save_compact_json(weekday_timetable, weekday_output_path)
    
    print("💾 正在寫入 假日 JSON 檔案...")
    save_compact_json(holiday_timetable, holiday_output_path)

    print(f"🎉 轉換完成！")
    print(f"   ▶ 平日車次: {len(weekday_timetable)} 班")
    print(f"   ▶ 假日車次: {len(holiday_timetable)} 班")

    if MISSING_STATIONS:
        print("\n" + "="*60)
        print("🚨 發現未匹配的站名！(可能是尚未登記的站，或需要補上翻譯蒟蒻)")
        for st in sorted(list(MISSING_STATIONS)):
            if st: print(f'    "{st}": "請填入 topology 中的站名",')
        print("="*60)

if __name__ == "__main__":
    main()