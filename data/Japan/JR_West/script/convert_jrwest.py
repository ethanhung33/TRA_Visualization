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

# ==========================================
# 🚀 主程式
# ==========================================
def main():
    print("🚀 開始解析 JR 西日本原始時刻表...")
    
    # 1. 讀取 Topology (使用複合鍵防止同名覆蓋)
    with open(topo_path, 'r', encoding='utf-8') as f:
        topo = json.load(f)
        
    STA_MAP, LINE_MAP = {}, {}
    for i, seg in enumerate(topo.get("segments", [])):
        seg_id = seg.get("id") or seg.get("line_id") or seg.get("name") or f"line_{i}"
        stations_in_seg = []
        for st in seg.get("stations", []):
            sta_name = clean_station_name(st.get("name", ""))
            STA_MAP[(seg_id, sta_name)] = st.get("id") or sta_name
            if sta_name not in STA_MAP:
                STA_MAP[sta_name] = st.get("id") or sta_name
            stations_in_seg.append(sta_name)
        LINE_MAP[seg_id] = stations_in_seg

    # ==========================================
    # 🌟 專屬特判：為「特急 スーパーはくと」手動注入智頭急行線
    # ==========================================
    # 動態取得上郡(山陽本線)與智頭(因美線)的既有 ID，讓軌道無縫接軌
    kamigori_id = STA_MAP.get("上郡", "上郡")
    chizu_id = STA_MAP.get("智頭", "智頭")
    
    # 建立中間站的虛擬 ID
    STA_MAP["佐用"] = "Chizu_Sayo"
    STA_MAP["大原"] = "Chizu_Ohara"
    
    # 將這條虛擬路線註冊進複合鍵字典
    STA_MAP[("chizu_express_line", "上郡")] = kamigori_id
    STA_MAP[("chizu_express_line", "佐用")] = "Chizu_Sayo"
    STA_MAP[("chizu_express_line", "大原")] = "Chizu_Ohara"
    STA_MAP[("chizu_express_line", "智頭")] = chizu_id
    
    # 將路線註冊進 LINE_MAP
    LINE_MAP["chizu_express_line"] = ["上郡", "佐用", "大原", "智頭"]

    OTHER_LINES = {"chizu_express_line"}
    # ==========================================

    # 2. 讀取與過濾原始資料
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
        no = train.get("列車番号", "未知")
        op_text = train.get("運転日", "")
        op_type = "daily"
        if "土曜・休日運休" in op_text or "平日運転" in op_text:
            op_type = "weekday"
        elif "土曜・休日運転" in op_text or "休日運転" in op_text:
            op_type = "holiday"
            
        stop_dict, ordered_stops = {}, []
        for s in train.get("data", []):
            sta_name = clean_station_name(s["sta"])
            arr, dep = s.get("arr", ""), s.get("dep", "")
            if arr == "": arr = dep
            if dep == "": dep = arr
            if arr == "" and dep == "": continue
            stop_dict[sta_name] = (arr, dep)
            ordered_stops.append(sta_name)
            
        if not ordered_stops: continue
        
        all_chunks.append({
            "no": no, "op_type": op_type,
            "type": clean_train_type(train.get("列車種別", ""), train.get("列車名", "")),
            "thru_link": train.get("直通運転"),
            "stops": stop_dict, "ordered_stops": ordered_stops,
            "start_time": stop_dict[ordered_stops[0]][1] if isinstance(stop_dict[ordered_stops[0]][1], int) else 9999
        })

    # 4. 空間連通性分群
    grouped_chunks = defaultdict(list)
    for chunk in all_chunks:
        grouped_chunks[f'{chunk["no"]}::{chunk["op_type"]}'].append(chunk)

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
                "no": instance[0]["no"], "type": instance[0]["type"],
                "is_wd": instance[0]["op_type"] in ["daily", "weekday"],
                "is_we": instance[0]["op_type"] in ["daily", "holiday"],
                "segments_data": instance,
                "thru_links": set(c["thru_link"] for c in instance if c["thru_link"] and c["thru_link"] != instance[0]["no"])
            }

    # ==========================================
    # 🌟 核心修正：邊遍歷演算法 (Stop-by-Stop Edge Mapping)
    # ==========================================
    processed_trains = []
    for unique_id, t_info in train_buffer.items():
        t_info["segments_data"].sort(key=lambda x: x["start_time"])
        
        merged_stops, full_ordered_stops = {}, []
        for seg in t_info["segments_data"]:
            for st in seg["ordered_stops"]:
                if st not in full_ordered_stops: full_ordered_stops.append(st)
                if st not in merged_stops:
                    merged_stops[st] = seg["stops"][st]
                else:
                    merged_stops[st] = (merged_stops[st][0] if merged_stops[st][0] != "" else seg["stops"][st][0],
                                        seg["stops"][st][1] if seg["stops"][st][1] != "" else merged_stops[st][1])

        segs = []
        current_line = None
        current_seg_s, current_seg_t, current_seg_v = [], [], []

        for i in range(len(full_ordered_stops) - 1):
            s1 = full_ordered_stops[i]
            s2 = full_ordered_stops[i+1]
            
            # 尋找同時包含這相鄰兩站的路線
            possible_lines = [l_id for l_id, l_sts in LINE_MAP.items() if s1 in l_sts and s2 in l_sts]
            if not possible_lines: continue
                
            # 路線決策：慣性定律
            chosen_line = current_line if current_line in possible_lines else possible_lines[0]
                
            # 換線處理
            if chosen_line != current_line:
                if current_line is not None:
                    segs.append({"id": current_line, "s": current_seg_s, "t": current_seg_t, "v": current_seg_v})
                    if current_line in OTHER_LINES:
                        segs[-1]["is_other"] = True

                current_line = chosen_line
                st1_id = STA_MAP.get((current_line, s1)) or STA_MAP.get(s1, s1)
                current_seg_s, current_seg_t, current_seg_v = [st1_id], [merged_stops[s1][0], merged_stops[s1][1]], [0]
                
            # 推進下一站
            st2_id = STA_MAP.get((current_line, s2)) or STA_MAP.get(s2, s2)
            current_seg_s.append(st2_id)
            current_seg_t.extend([merged_stops[s2][0], merged_stops[s2][1]])
            current_seg_v.append(1)

        if current_line is not None:
            segs.append({"id": current_line, "s": current_seg_s, "t": current_seg_t, "v": current_seg_v})
            if current_line in OTHER_LINES:
                segs[-1]["is_other"] = True
            
        # 修補 v 值 (0=起點, 3=終點, 1=中間)
        for seg in segs:
            if len(seg["v"]) > 0:
                seg["v"][0], seg["v"][-1] = 0, 3
        
        if not segs: continue
        
        processed_trains.append({
            "no": t_info["no"], "type": t_info["type"], "segments": segs, "coupled_with": [],
            "_first_sta": full_ordered_stops[0], "_last_sta": full_ordered_stops[-1],
            "_thru_links": t_info["thru_links"], "_is_wd": t_info["is_wd"], "_is_we": t_info["is_we"]
        })

    # 5. 直通運轉配對
    for t in processed_trains:
        for target_no in t["_thru_links"]:
            for partner in [p for p in processed_trains if p["no"] == target_no]:
                j_name = t["_last_sta"] if t["_last_sta"] == partner["_first_sta"] else (t["_first_sta"] if t["_first_sta"] == partner["_last_sta"] else None)
                if j_name:
                    j_id = STA_MAP.get(j_name, j_name)
                    if not any(c["train_id"] == partner["no"] for c in t["coupled_with"]): t["coupled_with"].append({"train_id": partner["no"], "station_id": j_id, "action": "direct"})
                    if not any(c["train_id"] == t["no"] for c in partner["coupled_with"]): partner["coupled_with"].append({"train_id": t["no"], "station_id": j_id, "action": "direct"})

    # ==========================================
    # 6. 分流與清理
    # ==========================================
    wd_final, we_final = [], []
    for t in processed_trains:
        # 提取並移除平假日標記
        is_wd = t.pop("_is_wd", False)
        is_we = t.pop("_is_we", False)
        
        # 安全移除暫存欄位
        t.pop("_first_sta", None)
        t.pop("_last_sta", None)
        t.pop("_thru_links", None)
        
        # 安全移除空的 coupled_with (使用 in 判斷避免 KeyError)
        if "coupled_with" in t and not t["coupled_with"]:
            del t["coupled_with"]
            
        # 進行分流
        if is_wd: wd_final.append(t)
        if is_we: we_final.append(t)

    # 輸出存檔
    os.makedirs(output_dir, exist_ok=True)
    def save(file_path, train_list):
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("[\n" + ",\n".join("  " + json.dumps(t, ensure_ascii=False, separators=(',', ':')) for t in train_list) + "\n]")
            
    save(os.path.join(output_dir, "timetable_weekday.json"), wd_final)
    save(os.path.join(output_dir, "timetable_holiday.json"), we_final)
    
    print(f"\n🎉 轉換完成！平日：{len(wd_final)} 班 | 假日：{len(we_final)} 班")

if __name__ == "__main__":
    main()