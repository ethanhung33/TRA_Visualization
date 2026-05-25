import json
import os
import re
import unicodedata
from collections import OrderedDict, defaultdict

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

# ==========================================
# 🚀 主程式
# ==========================================
def main():
    print("🚀 開始解析 JR 西日本原始時刻表...")
    
    with open(topo_path, 'r', encoding='utf-8') as f:
        topo = json.load(f)
        
    STA_MAP, LINE_MAP = {}, {}
    for i, seg in enumerate(topo.get("segments", [])):
        seg_id = seg.get("id") or seg.get("line_id") or seg.get("name") or f"line_{i}"
        stations_in_seg = []
        for st in seg.get("stations", []):
            sta_name = clean_station_name(st.get("name", ""))
            
            # 🌟 核心修正：使用 (路線ID, 站名) 當作複合鍵，避免同名覆蓋
            STA_MAP[(seg_id, sta_name)] = st.get("id") or sta_name
            
            # 依然保留純站名，供直通運轉尋找交會大站使用
            if sta_name not in STA_MAP:
                STA_MAP[sta_name] = st.get("id") or sta_name
                
            stations_in_seg.append(sta_name)
        LINE_MAP[seg_id] = stations_in_seg

    with open(raw_data_path, 'r', encoding='utf-8') as f:
        raw_trains = json.load(f)

    valid_trains = []
    for train in raw_trains:
        route_list = train.get("route", [])
        train_type = train.get("列車種別", "")
        if "新幹線" in train_type or any("新幹線" in r for r in route_list):
            continue
        valid_trains.append(train)

    # ==========================================
    # 🌟 核心修正 1：將所有資料碎解為獨立段落 (Chunks)
    # ==========================================
    all_chunks = []
    for train in valid_trains:
        no = train.get("列車番号", "未知")
        op_text = train.get("運転日", "")
        op_type = "daily"
        if "土曜・休日運休" in op_text or "平日運転" in op_text:
            op_type = "weekday"
        elif "土曜・休日運転" in op_text or "休日運転" in op_text:
            op_type = "holiday"
            
        stop_dict = {}
        ordered_stops = []
        for s in train.get("data", []):
            sta_name = clean_station_name(s["sta"])
            arr, dep = s.get("arr", ""), s.get("dep", "")
            if arr == "": arr = dep
            if dep == "": dep = arr
            if arr == "" and dep == "": continue
            stop_dict[sta_name] = (arr, dep)
            ordered_stops.append(sta_name)
            
        if not ordered_stops: continue
        start_time = stop_dict[ordered_stops[0]][1]
        
        all_chunks.append({
            "no": no,
            "op_type": op_type,
            "type": clean_train_type(train.get("列車種別", ""), train.get("列車名", "")),
            "thru_link": train.get("直通運転"),
            "stops": stop_dict,
            "ordered_stops": ordered_stops,
            "start_time": start_time if isinstance(start_time, int) else 9999
        })

    # ==========================================
    # 🌟 核心修正 2：利用「空間連通性」進行智慧分群
    # ==========================================
    grouped_chunks = defaultdict(list)
    for chunk in all_chunks:
        grouped_chunks[f'{chunk["no"]}::{chunk["op_type"]}'].append(chunk)

    train_buffer = {}
    buffer_idx = 0
    
    for key, chunks in grouped_chunks.items():
        instances = []
        # 將擁有相同車次號碼的積木，嘗試用「共用車站」接合起來
        for chunk in chunks:
            chunk_stations = set(chunk["ordered_stops"])
            matched_idxs = []
            for i, instance in enumerate(instances):
                instance_stations = set(s for c in instance for s in c["ordered_stops"])
                if chunk_stations.intersection(instance_stations):
                    matched_idxs.append(i)
            
            # 如果這塊積木接不上任何已知的同號碼列車，它就是一台全新的獨立列車！
            if not matched_idxs:
                instances.append([chunk])
            else:
                new_instance = [chunk]
                for i in sorted(matched_idxs, reverse=True):
                    new_instance.extend(instances.pop(i))
                instances.append(new_instance)
                
        # 將接合完成的獨立列車存入 Buffer
        for instance in instances:
            no = instance[0]["no"]
            op_type = instance[0]["op_type"]
            t_type = instance[0]["type"]
            thru_links = set(c["thru_link"] for c in instance if c["thru_link"] and c["thru_link"] != no)
            
            unique_id = f"train_{buffer_idx}"
            buffer_idx += 1
            
            train_buffer[unique_id] = {
                "no": no,
                "type": t_type,
                "is_wd": op_type in ["daily", "weekday"],
                "is_we": op_type in ["daily", "holiday"],
                "segments_data": instance,
                "thru_links": thru_links
            }

    # ==========================================
    # 轉換與拓樸映射
    # ==========================================
    processed_trains = []
    for unique_id, t_info in train_buffer.items():
        t_info["segments_data"].sort(key=lambda x: x["start_time"])
        
        merged_stops = {}
        full_ordered_stops = []
        for seg in t_info["segments_data"]:
            for st in seg["ordered_stops"]:
                if st not in full_ordered_stops:
                    full_ordered_stops.append(st)
                if st not in merged_stops:
                    merged_stops[st] = seg["stops"][st]
                else:
                    old_arr, old_dep = merged_stops[st]
                    new_arr, new_dep = seg["stops"][st]
                    final_arr = old_arr if old_arr != "" else new_arr
                    final_dep = new_dep if new_dep != "" else old_dep
                    merged_stops[st] = (final_arr, final_dep)

        segs = []
        for l_id, l_sts in LINE_MAP.items():
            intersect = [sta for sta in full_ordered_stops if sta in l_sts]
            if len(intersect) < 2: continue
            s_list, t_list, v_list = [], [], []
            for i, s_name in enumerate(intersect):
                st_id = STA_MAP.get((l_id, s_name)) or STA_MAP.get(s_name, s_name)
                
                s_list.append(st_id)
                t_list.extend([merged_stops[s_name][0], merged_stops[s_name][1]])
                v_list.append(0 if i == 0 else (3 if i == len(intersect)-1 else 1))
            segs.append({"id": l_id, "s": s_list, "t": t_list, "v": v_list})
            
        if not segs: continue
        
        segs.sort(key=lambda x: x["t"][0])
        
        processed_trains.append({
            "no": t_info["no"],
            "type": t_info["type"],
            "segments": segs,
            "coupled_with": [],
            "_first_sta": full_ordered_stops[0] if full_ordered_stops else None,
            "_last_sta": full_ordered_stops[-1] if full_ordered_stops else None,
            "_thru_links": t_info["thru_links"],
            "_is_wd": t_info["is_wd"],
            "_is_we": t_info["is_we"]
        })

    # 直通運轉配對
    for t in processed_trains:
        for target_no in t["_thru_links"]:
            partners = [p for p in processed_trains if p["no"] == target_no]
            for partner in partners:
                junction_name = None
                if t["_last_sta"] == partner["_first_sta"]:
                    junction_name = t["_last_sta"]
                elif t["_first_sta"] == partner["_last_sta"]:
                    junction_name = t["_first_sta"]
                    
                if junction_name:
                    junction_id = STA_MAP.get(junction_name, junction_name)
                    if not any(c["train_id"] == partner["no"] and c["action"] == "direct" for c in t["coupled_with"]):
                        t["coupled_with"].append({"train_id": partner["no"], "station_id": junction_id, "action": "direct"})
                    if not any(c["train_id"] == t["no"] and c["action"] == "direct" for c in partner["coupled_with"]):
                        partner["coupled_with"].append({"train_id": t["no"], "station_id": junction_id, "action": "direct"})

    # 分流與清理
    wd_final, we_final = [], []
    for t in processed_trains:
        is_wd = t.pop("_is_wd")
        is_we = t.pop("_is_we")
        t.pop("_first_sta", None)
        t.pop("_last_sta", None)
        t.pop("_thru_links", None)
        
        if not t["coupled_with"]:
            del t["coupled_with"]
            
        if is_wd: wd_final.append(t)
        if is_we: we_final.append(t)

    # 輸出存檔
    os.makedirs(output_dir, exist_ok=True)
    def save_one_train_per_line(file_path, train_list):
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("[\n")
            for i, train in enumerate(train_list):
                line = json.dumps(train, ensure_ascii=False, separators=(',', ':'))
                f.write("  " + line + (",\n" if i < len(train_list)-1 else "\n"))
            f.write("]")

    save_one_train_per_line(os.path.join(output_dir, "timetable_weekday.json"), wd_final)
    save_one_train_per_line(os.path.join(output_dir, "timetable_holiday.json"), we_final)

    print(f"\n🎉 轉換與直通優化大功告成！")
    print(f"👉 平日：{len(wd_final)} 班次 | 假日：{len(we_final)} 班次")

if __name__ == "__main__":
    main()