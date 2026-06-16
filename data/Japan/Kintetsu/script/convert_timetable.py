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
    "桜川", "ドーム前", "九条（阪神）", "西九条", "千鳥橋", "伝法", "福", "出来島", "大物", "尼崎",
    "尼崎センタープール前", "武庫川", "鳴尾・武庫川女子大前", "甲子園", "久寿川", "今津", 
    "西宮", "香櫨園", "打出", "芦屋", "深江", "青木", "魚崎", "住吉", "御影", "石屋川", 
    "新在家", "大石", "西灘", "岩屋", "西代", "神戸三宮", "元町", "神戸高速",
    "国際会館", "松ヶ崎（京都地下鉄）", "北山", "北大路", "鞍馬口", "今出川", "丸太町", "烏丸御池", 
    "四条", "五条", "京都（京都地下鉄）", "九条（京都地下鉄）", "十条（京都地下鉄）", "くいな橋",
    "コスモスクエア", "大阪港", "朝潮橋", "弁天町", "阿波座", "本町", "堺筋本町", 
    "谷町四丁目", "森ノ宮", "緑橋", "深江橋", "高井田",
    "「観光特急あをによし」の運行日はこちらをご覧ください。特急の車種は予告なく変更する場合があります。",
    "「観光特急しまかぜ」の運行日はこちらをご覧ください。特急の車種は予告なく変更する場合があります。",
    "夢洲"
}

MISSING_STATIONS = set()

def clean_station_name(name):
    """
    清理站名：
    1. 提早攔截：如果是免責聲明備註或未通車車站，直接回傳 "SKIP_STATION"。
    2. 特判保護：防止「九条（阪神）」的括號被誤刪，導致與近鐵九条(B29)撞名。
    3. 清洗多餘的備註與空白，並套用 STATION_MAPPING。
    """
    if "ご覧ください" in name or "変更" in name:
        return "SKIP_STATION"
    if name == "夢洲":
        return "SKIP_STATION"
        
    # ==========================================
    # 🛡️ 新增：外網專屬防護罩 (這一步非常關鍵！)
    # 在這裡提前把地下鐵保送出去，絕對不能讓底下的 re.sub 切掉它們的括號！
    # ==========================================
    if "（京都地下鉄）" in name or "（大阪メトロ）" in name:
        return name

    # 原本的阪神九条保護也可以留著
    if "九条（阪神）" in name or "九条(阪神)" in name:
        return "九条（阪神）"

    # ==========================================
    # ✂️ 這裡才是切括號的刀子
    # ==========================================
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
        # ✅ 直接讀取剛剛存入的乾淨站名
        st_name = stop["clean_name"]
        st_id = station_map.get(st_name, {}).get("id", "Unknown")

        arr = parse_time(stop.get("arr"))
        dep = parse_time(stop.get("dep"))
        
        if arr is None and dep is not None: arr = dep
        if dep is None and arr is not None: dep = arr
        if arr is None and dep is None: arr, dep = 0, 0
        
        if i == 0: v = 0
        elif i == len(stops) - 1: v = 3
        else: v = 1
            
        s_arr.append(st_id)
        t_arr.extend([arr, dep])
        v_arr.append(v)
        
    return {"id": seg_id, "s": s_arr, "t": t_arr, "v": v_arr}


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

def format_nankai_style(raw_train, station_map, train_idx, day_type):
    stop_data = raw_train.get("data", [])
    if not stop_data: return None

    # ==========================================
    # 🧹 階段 A：全面清洗站名與過濾
    # ==========================================
    valid_stops = []
    for stop in stop_data:
        st_name = clean_station_name(stop["station"])
        if st_name == "SKIP_STATION":
            continue
            
        stop["clean_name"] = st_name
        if st_name in station_map:
            valid_stops.append(stop)
        elif st_name not in EXTERNAL_NETWORKS and st_name not in MISSING_STATIONS:
            MISSING_STATIONS.add(st_name)

    if len(valid_stops) < 2:
        return None

    # ==========================================
    # 🛡️ 階段 A-2：剔除「下游截短」的殘骸車次
    # ==========================================
    first_station = valid_stops[0]["clean_name"]
    dir_str = raw_train.get("dir", "")
    match = re.search(r'始発駅[：:]\s*([^）\)]+)', dir_str)
    
    if match:
        clean_origin = clean_station_name(match.group(1))
        if clean_origin in station_map and first_station != clean_origin:
            return None

    # ==========================================
    # 🧩 階段 B：打包 Segments (✅ 放手交給前端縫合)
    # ==========================================
    segments = []
    current_segment_stops = []
    current_possible_lines = set()

    for i in range(len(valid_stops)):
        stop = valid_stops[i]
        st_name = stop["clean_name"] 
        st_lines = station_map.get(st_name, {}).get("lines", set())
        
        if not current_segment_stops:
            current_segment_stops.append(stop)
            current_possible_lines = set(st_lines)
        else:
            new_possible_lines = current_possible_lines.intersection(st_lines)
            
            # 🛑 強制切斷「折返 (Switchback)」路線
            if len(current_segment_stops) > 1 and current_segment_stops[-1]["clean_name"] == "近鉄奈良":
                new_possible_lines = set() 
                
            if new_possible_lines:
                current_segment_stops.append(stop)
                current_possible_lines = new_possible_lines
            else:
                # 1. 結算上一段路線
                seg_id = list(current_possible_lines)[0] if current_possible_lines else "unknown_line"
                segments.append(build_segment_dict(seg_id, current_segment_stops, station_map))
                
                # 2. 準備下一段路線
                last_stop = current_segment_stops[-1]
                last_st_name = last_stop["clean_name"]
                last_st_lines = station_map.get(last_st_name, {}).get("lines", set())
                
                # 🛑 核心修復：嚴格檢查「上一站」是否真的存在於「這站」的路線上！
                shared_lines = last_st_lines.intersection(st_lines)
                
                if shared_lines:
                    # 👉 正常交會站 (如: 西大寺)：它存在於兩條線上，合法傳承
                    current_segment_stops = [last_stop, stop]
                    current_possible_lines = shared_lines
                else:
                    # 👉 斷層直通車 (如: 津 -> 鶴橋)：沒有共同路線，拒絕硬塞！
                    # 讓這個 Segment 乾淨地從「鶴橋」開始，把造橋的工作交給前端
                    current_segment_stops = [stop]
                    current_possible_lines = set(st_lines)

    # 結算最後一段
    if len(current_segment_stops) > 1:
        seg_id = list(current_possible_lines)[0] if current_possible_lines else "unknown_line"
        segments.append(build_segment_dict(seg_id, current_segment_stops, station_map))

    prefix = "W" if "平日" in day_type else "H"
    train_no = raw_train.get("no", f"1-{prefix}{train_idx:04d}")

    formatted_train = {
        "no": train_no, 
        "type": clean_train_type(raw_train.get("type", "Unknown")), 
        "segments": segments
    }
    
    # ==========================================
    # 🧬 階段 C：升級版「唯一身分證」
    # ==========================================
    first_dep = parse_time(valid_stops[0].get("dep"))
    signature = (dir_str, first_station, first_dep)

    return formatted_train, len(valid_stops), signature

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_dir = os.path.join(script_dir, '..', 'json')
    
    topology_path = os.path.join(json_dir, 'topology.json')
    input_file_path = os.path.join(json_dir, 'raw_timetable.json') 
    
    weekday_output_path = os.path.join(json_dir, 'timetable', 'timetable_weekday.json')
    holiday_output_path = os.path.join(json_dir, 'timetable', 'timetable_holiday.json')

    print("📂 載入 Topology 資料...")
    try:
        with open(topology_path, 'r', encoding='utf-8') as f:
            topology_data = json.load(f)
        station_map = build_station_map(topology_data)
    except FileNotFoundError:
        print(f"❌ 找不到 topology.json，請確認路徑")
        return

    print(f"📂 載入原始時刻表: {input_file_path}")
    try:
        with open(input_file_path, 'r', encoding='utf-8') as f:
            raw_timetable = json.load(f)
    except FileNotFoundError:
        print(f"❌ 找不到原始資料")
        return

    print(f"🔄 開始轉換、去重並分流 {len(raw_timetable)} 筆車次資料...")
    
    # 使用 Dictionary 來做去重：Key 是簽名，Value 是 {車次資料, 站點數}
    weekday_dict = {}
    holiday_dict = {}
    
    for idx, raw_train in enumerate(raw_timetable, start=1):
        date_type = raw_train.get("date", "平日")
        
        result = format_nankai_style(raw_train, station_map, idx, date_type)
        if not result:
            continue
            
        formatted_train, stop_count, signature = result
        target_dict = weekday_dict if "平日" in date_type else holiday_dict
        
        # 👑 核心去重邏輯：如果沒看過這班車就存起來；如果看過，只保留停站數最多的！
        if signature not in target_dict:
            target_dict[signature] = {"data": formatted_train, "count": stop_count}
        else:
            if stop_count > target_dict[signature]["count"]:
                target_dict[signature] = {"data": formatted_train, "count": stop_count}

    # 把 Dictionary 轉回乾淨的 List
    weekday_timetable = [v["data"] for v in weekday_dict.values()]
    holiday_timetable = [v["data"] for v in holiday_dict.values()]

    print("💾 正在寫入 平日 JSON 檔案...")
    save_compact_json(weekday_timetable, weekday_output_path)
    
    print("💾 正在寫入 假日 JSON 檔案...")
    save_compact_json(holiday_timetable, holiday_output_path)

    print(f"🎉 轉換與去重完成！")
    print(f"   ▶ 平日去重後車次: {len(weekday_timetable)} 班")
    print(f"   ▶ 假日去重後車次: {len(holiday_timetable)} 班")

    if MISSING_STATIONS:
        print("\n" + "="*60)
        print("🚨 發現未匹配的站名！(可能是尚未登記的站，或需要補上翻譯蒟蒻)")
        for st in sorted(list(MISSING_STATIONS)):
            if st: print(f'    "{st}": "請填入 topology 中的站名",')
        print("="*60)

if __name__ == "__main__":
    main()