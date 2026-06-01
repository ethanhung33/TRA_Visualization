import json
import os
import re
import unicodedata
from collections import defaultdict

# ==========================================
# 🌟 路徑設定
# ==========================================
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
json_dir = os.path.join(project_dir, "json")

raw_data_path = os.path.join(json_dir, "data_new.json")
topo_path = os.path.join(json_dir, "topology.json")
output_dir = os.path.join(json_dir, "timetable")

# ==========================================
# 🛠️ 工具函數
# ==========================================
def clean_station_name(text):
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r'\[.*?\]|（.*?）|\(.*?\)|[†*※‡駅]', '', text)
    anomalies = {"大阪駅": "大阪", "京都駅": "京都"}
    return anomalies.get(text.strip(), text.strip())

def clean_train_type(type_str, name_str):
    clean_type = re.sub(r'[A-Za-z\uFF21-\uFF3A]+', '', type_str).replace(" ", "")
    clean_name = re.sub(r'[A-Za-z\uFF21-\uFF3A]+', '', name_str).replace(" ", "")
    clean_name = re.sub(r'[（）\(\)\[\]【】]', '', clean_name)
    clean_type = re.sub(r'[（）\(\)\[\]【】]', '', clean_type)
    clean_name = re.sub(r'\d+号|号', '', clean_name)
    
    if clean_type == "普通" and ("快速" in clean_name or "普通" in clean_name):
        return "普通"
    if clean_type and clean_type in clean_name:
        return clean_name
    if clean_name and clean_name in clean_type:
        return clean_type
    return f"{clean_type}{clean_name}"

def parse_japanese_dates(text, default_year=2026):
    """將日文的行駛日期字串，轉換為 YYYY-MM-DD 的標準陣列"""
    if not text: return []
    text = unicodedata.normalize('NFKC', text) # 轉為半形
    text = text.replace('運転', '').strip()
    
    dates = []
    parts = re.split(r'(\d+)月', text)
    
    for i in range(1, len(parts), 2):
        month = int(parts[i])
        days_str = parts[i+1].replace('日', '').strip('・')
        
        for part in days_str.split('・'):
            if not part: continue
            if '～' in part or '~' in part or '-' in part:
                bounds = re.split(r'[～~-]', part)
                if len(bounds) == 2 and bounds[0].isdigit() and bounds[1].isdigit():
                    for d in range(int(bounds[0]), int(bounds[1]) + 1):
                        dates.append(f"{default_year}-{month:02d}-{d:02d}")
            elif part.isdigit():
                dates.append(f"{default_year}-{month:02d}-{int(part):02d}")
                
    return sorted(list(set(dates)))

# ==========================================
# 🚀 主程式
# ==========================================
def main():
    print("🚀 開始解析 JR 西日本原始時刻表...")
    
    with open(topo_path, 'r', encoding='utf-8') as f:
        topo = json.load(f)
        
    STA_MAP, LINE_MAP, KM_MAP = {}, {}, {}
    for i, seg in enumerate(topo.get("segments", [])):
        seg_id = seg.get("id") or seg.get("line_id") or seg.get("name") or f"line_{i}"
        stations_in_seg = []
        for st in seg.get("stations", []):
            sta_name = clean_station_name(st.get("name", ""))
            STA_MAP[(seg_id, sta_name)] = st.get("id") or sta_name
            if sta_name not in STA_MAP:
                STA_MAP[sta_name] = st.get("id") or sta_name
                
            KM_MAP[(seg_id, sta_name)] = float(st.get("km", 0.0))
            stations_in_seg.append(sta_name)
        LINE_MAP[seg_id] = stations_in_seg

    # 智頭急行線注入
    kamigori_id = STA_MAP.get("上郡", "上郡")
    chizu_id = STA_MAP.get("智頭", "智頭")
    STA_MAP["佐用"] = "Chizu_Sayo"
    STA_MAP["大原"] = "Chizu_Ohara"
    STA_MAP[("chizu_express_line", "上郡")] = kamigori_id
    STA_MAP[("chizu_express_line", "佐用")] = "佐用"
    STA_MAP[("chizu_express_line", "大原")] = "大原"
    STA_MAP[("chizu_express_line", "智頭")] = chizu_id
    LINE_MAP["chizu_express_line"] = ["上郡", "佐用", "大原", "智頭"]

    OTHER_LINES = {
        "chizu_express_line": {
            "path": "data/Japan/Chizu_Express/",
            "name": "智頭急行線"
        }
    }

    with open(raw_data_path, 'r', encoding='utf-8') as f:
        raw_trains = json.load(f)

    valid_trains = []
    for train in raw_trains:
        if "新幹線" in train.get("列車種別", "") or any("新幹線" in r for r in train.get("route", [])):
            continue
        valid_trains.append(train)

    # 3. 資料碎解 (Chunks)
    all_chunks = []
    for train in valid_trains:
        original_no = train.get("列車番号", "未知")
        op_text = train.get("運転日", "")
        
        op_type = "daily"
        dates = []
        
        if "土曜・休日運休" in op_text or "平日運転" in op_text:
            op_type = "weekday"
        elif "土曜・休日運転" in op_text or "休日運転" in op_text:
            op_type = "holiday"
        elif "月" in op_text and ("日" in op_text or "・" in op_text):
            op_type = "irregular"
            dates = parse_japanese_dates(op_text, 2026)
            
        stop_times, ordered_stops = [], [] 
        for s in train.get("data", []):
            sta_name = clean_station_name(s["sta"])
            arr, dep = s.get("arr", ""), s.get("dep", "")
            if arr == "": arr = dep
            if dep == "": dep = arr
            if arr == "" and dep == "": continue
            
            ordered_stops.append(sta_name)
            stop_times.append((arr, dep)) 
            
        if not ordered_stops: continue

        start_st_name = clean_station_name(train.get("data", [])[0]["sta"])
        start_st_id = STA_MAP.get(start_st_name, start_st_name)
        unique_no = f"{original_no}|{start_st_id}"
        
        all_chunks.append({
            "no": unique_no, 
            "op_type": op_type,
            "operation": op_type, 
            "dates": dates,       
            "type": clean_train_type(train.get("列車種別", ""), train.get("列車名", "")),
            "thru_link": train.get("直通運転"),
            "stops": stop_times,  
            "ordered_stops": ordered_stops,
            "start_time": stop_times[0][1] if isinstance(stop_times[0][1], int) else 9999
        })
            
    # 4. 空間連通性分群
    grouped_chunks = defaultdict(list)
    for chunk in all_chunks:
        # 🌟 核心升級防護網：加入 date_signature，防止不同日期的臨時列車被錯誤縫合成科學怪人！
        date_signature = "".join(chunk.get("dates", []))
        group_key = f'{chunk["no"]}::{chunk["op_type"]}::{date_signature}'
        grouped_chunks[group_key].append(chunk)

    train_buffer = {}
    buffer_idx = 0
    for key, chunks in grouped_chunks.items():
        instances = []
        for chunk in chunks:
            chunk_stations = set(chunk["ordered_stops"])
            matched_idxs = [i for i, instance in enumerate(instances) if chunk_stations.intersection(set(s for c in instance for s in c["ordered_stops"]))]
            
            if not matched_idxs:
                instances.append([chunk])
            else:
                new_instance = [chunk]
                for i in sorted(matched_idxs, reverse=True):
                    new_instance.extend(instances.pop(i))
                instances.append(new_instance)
                
        for instance in instances:
            unique_id = f"train_{buffer_idx}"
            buffer_idx += 1
            train_buffer[unique_id] = {
                "no": instance[0]["no"], 
                "type": instance[0]["type"],
                "is_wd": instance[0]["op_type"] in ["daily", "weekday", "irregular"],
                "is_we": instance[0]["op_type"] in ["daily", "holiday", "irregular"],
                "operation": instance[0]["operation"], 
                "dates": instance[0]["dates"],         
                "segments_data": instance,
                "thru_links": set(c["thru_link"] for c in instance if c["thru_link"] and c["thru_link"] != instance[0]["no"])
            }

    # 5. 邊遍歷演算法 (Stop-by-Stop Edge Mapping)
    processed_trains = []
    for unique_id, t_info in train_buffer.items():
        t_info["segments_data"].sort(key=lambda x: x["start_time"])
        
        full_ordered_stops = []
        full_ordered_times = []
        seen_chunks = set() 
        
        for seg in t_info["segments_data"]:
            chunk_hash = str(seg["ordered_stops"]) + str(seg["stops"])
            if chunk_hash in seen_chunks: continue
            seen_chunks.add(chunk_hash)
            
            for idx, st in enumerate(seg["ordered_stops"]):
                st_time = seg["stops"][idx]
                
                if not full_ordered_stops or full_ordered_stops[-1] != st:
                    full_ordered_stops.append(st)
                    full_ordered_times.append(st_time)
                else:
                    prev_arr, prev_dep = full_ordered_times[-1]
                    new_arr, new_dep = st_time
                    full_ordered_times[-1] = (
                        prev_arr if prev_arr != "" else new_arr,
                        new_dep if new_dep != "" else prev_dep
                    )
        
        full_ordered_v = [1] * len(full_ordered_stops)

        # 今宮 patch 只適用於經過阪和線/関西空港線的直通列車（如 はるか、くろしお）
        # 天王寺是 hanwa_line 起點，但也屬於 osaka_loop_line，必須排除；
        # 只計算純阪和線/関西空港線的中間站（如 日根野、関西空港、和泉府中 等）
        def _on_hanwa_or_kansai(st):
            st_lines = {l for l, sts in LINE_MAP.items() if st in sts}
            return ("hanwa_line" in st_lines or "kansai_airport_line" in st_lines) \
                   and "osaka_loop_line" not in st_lines
        is_haruka_style = any(_on_hanwa_or_kansai(st) for st in full_ordered_stops)

        # 拓樸斷層修復
        # fixed_preferred[i]: 第 i 段邊（i→i+1）的強制路線，None 表示自動選
        fixed_stops, fixed_times, fixed_v, fixed_preferred = [], [], [], []

        for i in range(len(full_ordered_stops) - 1):
            s1 = full_ordered_stops[i]
            s2 = full_ordered_stops[i+1]
            t1 = full_ordered_times[i]
            t2 = full_ordered_times[i+1]
            v1 = full_ordered_v[i]

            fixed_stops.append(s1)
            fixed_times.append(t1)
            fixed_v.append(v1)
            fixed_preferred.append(None)
            
            common_lines = [l_id for l_id, l_sts in LINE_MAP.items() if s1 in l_sts and s2 in l_sts]
            s1_lines = [l_id for l_id, l_sts in LINE_MAP.items() if s1 in l_sts]
            s2_lines = [l_id for l_id, l_sts in LINE_MAP.items() if s2 in l_sts]

            # 今宮 patch：osaka_loop_line → yamatoji_line 切換
            # 需在 common_lines 檢查之外執行，因為大阪/天王寺同屬 osaka_loop_line，
            # 但 Haruka 等列車實際走大和路線支線，必須經過今宮換線。
            # "yamatoji_line" not in s1_lines 避免今宮本身（同時屬兩線）再觸發。
            is_loop_to_yamatoji = ("osaka_loop_line" in s1_lines and "yamatoji_line" in s2_lines
                                   and "yamatoji_line" not in s1_lines)
            is_yamatoji_to_loop = ("yamatoji_line" in s1_lines and "osaka_loop_line" in s2_lines
                                   and "yamatoji_line" not in s2_lines)

            is_hanwa_to_kansai = "hanwa_line" in s1_lines and "kansai_airport_line" in s2_lines
            is_kansai_to_hanwa = "kansai_airport_line" in s1_lines and "hanwa_line" in s2_lines

            if (is_loop_to_yamatoji or is_yamatoji_to_loop) and (not common_lines or is_haruka_style):
                intersection = "今宮"
                # 反向（yamatoji→loop）：s1（天王寺）→今宮 這段 edge 已被 append 進 fixed_preferred
                # 但 preferred=None 會 fallback 到 possible_lines[0]=osaka_loop_line（定義順序較早）
                # 需回寫強制 yamatoji_line，否則偶數班次天王寺→今宮 會繞環狀線
                if is_yamatoji_to_loop:
                    fixed_preferred[-1] = "yamatoji_line"
                fixed_stops.append(intersection)
                fixed_v.append(2)
                # 今宮→下一站：正向走 yamatoji_line（今宮→天王寺），反向走 osaka_loop_line（今宮→大阪）
                fixed_preferred.append("yamatoji_line" if is_loop_to_yamatoji else "osaka_loop_line")

                try:
                    dep1 = int(t1[1]) if t1[1] != "" else int(t1[0])
                    arr2 = int(t2[0]) if t2[0] != "" else int(t2[1])

                    # 正向（loop→yamatoji）：s1 走 osaka_loop_line 到今宮，今宮 走 yamatoji_line 到 s2
                    # 反向（yamatoji→loop）：s1 走 yamatoji_line 到今宮，今宮 走 osaka_loop_line 到 s2
                    # 若用 next() 選第一條，因拓撲順序偏早兩者都選 osaka_loop_line，
                    # 導致 19.5 km 的全環被誤用於 yamatoji 的 2.2 km 段
                    l1 = "osaka_loop_line" if is_loop_to_yamatoji else "yamatoji_line"
                    l2 = "yamatoji_line"   if is_loop_to_yamatoji else "osaka_loop_line"

                    d1 = abs(KM_MAP.get((l1, intersection), 0.0) - KM_MAP.get((l1, s1), 0.0))
                    d2 = abs(KM_MAP.get((l2, s2), 0.0) - KM_MAP.get((l2, intersection), 0.0))
                    total_d = d1 + d2

                    if total_d > 0:
                        ratio = d1 / total_d
                        mid_time = dep1 + (arr2 - dep1) * ratio
                        mid_time = int(round(mid_time))
                    else:
                        mid_time = (dep1 + arr2) // 2

                    fixed_times.append((mid_time, mid_time))
                except:
                    dep1 = int(t1[1]) if t1[1] != "" else int(t1[0])
                    arr2 = int(t2[0]) if t2[0] != "" else int(t2[1])
                    mid_time = (dep1 + arr2) // 2
                    fixed_times.append((mid_time, mid_time))

            elif not common_lines and (is_hanwa_to_kansai or is_kansai_to_hanwa):
                # はるか等直通列車跳過日根野，需補插此分岔站
                intersection = "日根野"
                fixed_stops.append(intersection)
                fixed_v.append(2)
                fixed_preferred.append(None)  # 下一段只有 kansai_airport_line 可選，不需強制

                try:
                    dep1 = int(t1[1]) if t1[1] != "" else int(t1[0])
                    arr2 = int(t2[0]) if t2[0] != "" else int(t2[1])

                    l1 = next((l for l in s1_lines if intersection in LINE_MAP[l]), s1_lines[0])
                    l2 = next((l for l in s2_lines if intersection in LINE_MAP[l]), s2_lines[0])

                    d1 = abs(KM_MAP.get((l1, intersection), 0.0) - KM_MAP.get((l1, s1), 0.0))
                    d2 = abs(KM_MAP.get((l2, s2), 0.0) - KM_MAP.get((l2, intersection), 0.0))
                    total_d = d1 + d2

                    if total_d > 0:
                        ratio = d1 / total_d
                        mid_time = dep1 + (arr2 - dep1) * ratio
                        mid_time = int(round(mid_time))
                    else:
                        mid_time = (dep1 + arr2) // 2

                    fixed_times.append((mid_time, mid_time))
                except:
                    dep1 = int(t1[1]) if t1[1] != "" else int(t1[0])
                    arr2 = int(t2[0]) if t2[0] != "" else int(t2[1])
                    mid_time = (dep1 + arr2) // 2
                    fixed_times.append((mid_time, mid_time))
                        
        fixed_stops.append(full_ordered_stops[-1])
        fixed_times.append(full_ordered_times[-1])
        fixed_v.append(full_ordered_v[-1])
        fixed_preferred.append(None)

        full_ordered_stops = fixed_stops
        full_ordered_times = fixed_times
        full_ordered_v = fixed_v
        full_ordered_preferred = fixed_preferred

        segs = []
        current_line = None
        current_seg_s, current_seg_t, current_seg_v = [], [], []

        for i in range(len(full_ordered_stops) - 1):
            s1 = full_ordered_stops[i]
            s2 = full_ordered_stops[i+1]
            t1 = full_ordered_times[i]   
            t2 = full_ordered_times[i+1] 
            
            possible_lines = [l_id for l_id, l_sts in LINE_MAP.items() if s1 in l_sts and s2 in l_sts]
            if not possible_lines: continue

            preferred = full_ordered_preferred[i]
            if preferred and preferred in possible_lines:
                chosen_line = preferred
            else:
                chosen_line = current_line if current_line in possible_lines else possible_lines[0]
                
            if chosen_line != current_line:
                if current_line is not None:
                    segs.append({"id": current_line, "s": current_seg_s, "t": current_seg_t, "v": current_seg_v})
                    if current_line in OTHER_LINES:
                        segs[-1]["is_other"] = True
                        segs[-1]["system_path"] = OTHER_LINES[current_line]["path"]
                        segs[-1]["system_name"] = OTHER_LINES[current_line]["name"]

                current_line = chosen_line
                st1_id = STA_MAP.get((current_line, s1)) or STA_MAP.get(s1, s1)
                
                current_seg_s, current_seg_t, current_seg_v = [st1_id], [t1[0], t1[1]], [full_ordered_v[i]]
                
            st2_id = STA_MAP.get((current_line, s2)) or STA_MAP.get(s2, s2)
            current_seg_s.append(st2_id)
            current_seg_t.extend([t2[0], t2[1]])
            current_seg_v.append(full_ordered_v[i+1])

        if current_line is not None:
            segs.append({"id": current_line, "s": current_seg_s, "t": current_seg_t, "v": current_seg_v})
            if current_line in OTHER_LINES:
                segs[-1]["is_other"] = True
                segs[-1]["system_path"] = OTHER_LINES[current_line]["path"]
                segs[-1]["system_name"] = OTHER_LINES[current_line]["name"]
            
        if segs:
            if len(segs[0]["v"]) > 0:
                segs[0]["v"][0] = 0
            if len(segs[-1]["v"]) > 0:
                segs[-1]["v"][-1] = 3
        
        if not segs: continue
        
        processed_trains.append({
            "no": t_info["no"], 
            "type": t_info["type"], 
            "operation": t_info["operation"], 
            "dates": t_info["dates"],         
            "segments": segs, 
            "coupled_with": [],
            "_first_sta": full_ordered_stops[0], "_last_sta": full_ordered_stops[-1],
            "_thru_links": t_info["thru_links"], "_is_wd": t_info["is_wd"], "_is_we": t_info["is_we"]
        })

    # 直通運轉配對
    for t in processed_trains:
        for target_no in t["_thru_links"]:
            partners = [p for p in processed_trains if p["no"].split('|')[0] == target_no]
            
            for partner in partners:
                j_name = t["_last_sta"] if t["_last_sta"] == partner["_first_sta"] else (t["_first_sta"] if t["_first_sta"] == partner["_last_sta"] else None)
                if j_name:
                    j_id = STA_MAP.get(j_name, j_name)
                    if not any(c["train_id"] == partner["no"] for c in t["coupled_with"]): t["coupled_with"].append({"train_id": partner["no"], "station_id": j_id, "action": "direct"})
                    if not any(c["train_id"] == t["no"] for c in partner["coupled_with"]): partner["coupled_with"].append({"train_id": t["no"], "station_id": j_id, "action": "direct"})

    # 6. 分流與清理
    wd_final, we_final = [], []
    for t in processed_trains:
        is_wd = t.pop("_is_wd", False)
        is_we = t.pop("_is_we", False)
        
        t.pop("_first_sta", None)
        t.pop("_last_sta", None)
        t.pop("_thru_links", None)
        
        if "coupled_with" in t and not t["coupled_with"]:
            del t["coupled_with"]

        if t.get("operation") != "irregular" and "dates" in t:
            del t["dates"]
            
        if is_wd: wd_final.append(t)
        if is_we: we_final.append(t)

    os.makedirs(output_dir, exist_ok=True)
    def save(file_path, train_list):
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("[\n" + ",\n".join("  " + json.dumps(t, ensure_ascii=False, separators=(',', ':')) for t in train_list) + "\n]")
            
    save(os.path.join(output_dir, "timetable_weekday.json"), wd_final)
    save(os.path.join(output_dir, "timetable_holiday.json"), we_final)
    
    print(f"\n🎉 轉換完成！平日：{len(wd_final)} 班 | 假日：{len(we_final)} 班")

if __name__ == "__main__":
    main()