import json
import os
import re
import unicodedata
from collections import OrderedDict

# ==========================================
# 🌟 路徑設定 (完美對應你的資料夾架構)
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
    """清理車站名稱，包含全半形轉換與去除多餘符號"""
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r'\[.*?\]|（.*?）|\(.*?\)|[†*※‡駅]', '', text)
    anomalies = {"大阪駅": "大阪", "京都駅": "京都"}
    return anomalies.get(text.strip(), text.strip())

def clean_train_type(type_str, name_str):
    """智慧清洗車種名稱，過濾全半形字母、括號與號數"""
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
    
    # 1. 讀取 Topology
    with open(topo_path, 'r', encoding='utf-8') as f:
        topo = json.load(f)
        
    STA_MAP, LINE_MAP = {}, {}
    for i, seg in enumerate(topo.get("segments", [])):
        seg_id = seg.get("id") or seg.get("line_id") or seg.get("name") or f"line_{i}"
        stations_in_seg = []
        for st in seg.get("stations", []):
            sta_name = clean_station_name(st.get("name", ""))
            STA_MAP[sta_name] = st.get("id") or sta_name
            stations_in_seg.append(sta_name)
        LINE_MAP[seg_id] = stations_in_seg

    # 2. 讀取 JR 西日本原始資料並過濾新幹線
    with open(raw_data_path, 'r', encoding='utf-8') as f:
        raw_trains = json.load(f)

    valid_trains = []
    for train in raw_trains:
        route_list = train.get("route", [])
        train_type = train.get("列車種別", "")
        if "新幹線" in train_type or any("新幹線" in r for r in route_list):
            continue
        valid_trains.append(train)

    # 3. 緩衝區：合併「相同車次號碼」且「行駛路線相同」的段落
    train_buffer = {}
    for train in valid_trains:
        no = train.get("列車番号", "未知")
        route_list = train.get("route", [])
        
        # 🌟 核心修正：利用路線產生複合鍵，防止不同路線的同名車次混在一起
        route_key = "_".join(sorted(route_list))
        unique_id = f"{no}::{route_key}"
        
        if unique_id not in train_buffer:
            train_buffer[unique_id] = {
                "no": no,  # 保留真實的車次號碼，供後續直通關聯使用
                "type": clean_train_type(train.get("列車種別", ""), train.get("列車名", "")),
                "is_wd": False,
                "is_we": False,
                "segments_data": [],
                "thru_links": set()
            }
            
        op_text = train.get("運転日", "")
        if "土曜・休日運休" in op_text or "平日運転" in op_text or "毎日" in op_text or not op_text:
            train_buffer[unique_id]["is_wd"] = True
        if "土曜・休日運転" in op_text or "毎日" in op_text or not op_text:
            train_buffer[unique_id]["is_we"] = True

        thru = train.get("直通運転")
        if thru and thru != no:
            train_buffer[unique_id]["thru_links"].add(thru)

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

        if ordered_stops:
            start_time = stop_dict[ordered_stops[0]][1]
            train_buffer[unique_id]["segments_data"].append({
                "stops": stop_dict,
                "ordered_stops": ordered_stops,
                "start_time": start_time if isinstance(start_time, int) else 9999
            })

    # 4. 基礎轉換與拓樸映射
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
                s_list.append(STA_MAP.get(s_name, s_name))
                t_list.extend([merged_stops[s_name][0], merged_stops[s_name][1]])
                v_list.append(0 if i == 0 else (3 if i == len(intersect)-1 else 1))
            segs.append({"id": l_id, "s": s_list, "t": t_list, "v": v_list})
            
        if not segs: continue
        
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

    # ==========================================
    # 🌟 核心修正：嚴格的空間直通配對
    # ==========================================
    for t in processed_trains:
        for target_no in t["_thru_links"]:
            # 抓出所有符合該車次號碼的候選車 (例如所有的 430Y)
            partners = [p for p in processed_trains if p["no"] == target_no]
            
            for partner in partners:
                # 只有當「終點接上起點」時，才認定為真正的直通對象！
                junction_name = None
                if t["_last_sta"] == partner["_first_sta"]:
                    junction_name = t["_last_sta"]
                elif t["_first_sta"] == partner["_last_sta"]:
                    junction_name = t["_first_sta"]
                    
                if junction_name:
                    junction_id = STA_MAP.get(junction_name, junction_name)
                    
                    if not any(c["train_id"] == partner["no"] and c["action"] == "direct" for c in t["coupled_with"]):
                        t["coupled_with"].append({
                            "train_id": partner["no"],
                            "station_id": junction_id,
                            "action": "direct"
                        })
                    if not any(c["train_id"] == t["no"] and c["action"] == "direct" for c in partner["coupled_with"]):
                        partner["coupled_with"].append({
                            "train_id": t["no"],
                            "station_id": junction_id,
                            "action": "direct"
                        })

    # 5. 清理暫存特徵並分流
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

    # 6. 輸出存檔
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