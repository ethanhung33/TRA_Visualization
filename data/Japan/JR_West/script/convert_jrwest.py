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
        
    STA_MAP, LINE_MAP, KM_MAP = {}, {}, {} # 🌟 新增 KM_MAP
    for i, seg in enumerate(topo.get("segments", [])):
        seg_id = seg.get("id") or seg.get("line_id") or seg.get("name") or f"line_{i}"
        stations_in_seg = []
        for st in seg.get("stations", []):
            sta_name = clean_station_name(st.get("name", ""))
            STA_MAP[(seg_id, sta_name)] = st.get("id") or sta_name
            if sta_name not in STA_MAP:
                STA_MAP[sta_name] = st.get("id") or sta_name
                
            # 🌟 紀錄該站在路線上的里程數 (預設為 0.0)
            KM_MAP[(seg_id, sta_name)] = float(st.get("km", 0.0))
            
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
    STA_MAP[("chizu_express_line", "佐用")] = "佐用"
    STA_MAP[("chizu_express_line", "大原")] = "大原"
    STA_MAP[("chizu_express_line", "智頭")] = chizu_id
    
    # 將路線註冊進 LINE_MAP
    LINE_MAP["chizu_express_line"] = ["上郡", "佐用", "大原", "智頭"]

    OTHER_LINES = {
        "chizu_express_line": {
            "path": "data/Japan/Chizu_Express/",
            "name": "智頭急行線"
        }
    }
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
        original_no = train.get("列車番号", "未知")
        op_text = train.get("運転日", "")
        op_type = "daily"
        if "土曜・休日運休" in op_text or "平日運転" in op_text:
            op_type = "weekday"
        elif "土曜・休日運転" in op_text or "休日運転" in op_text:
            op_type = "holiday"
            
        stop_times, ordered_stops = [], []  # 🌟 改為平行陣列
        for s in train.get("data", []):
            sta_name = clean_station_name(s["sta"])
            arr, dep = s.get("arr", ""), s.get("dep", "")
            if arr == "": arr = dep
            if dep == "": dep = arr
            if arr == "" and dep == "": continue
            
            ordered_stops.append(sta_name)
            stop_times.append((arr, dep))  # 🌟 循序存入陣列，避免覆蓋
            
        if not ordered_stops: continue

        start_st_name = clean_station_name(train.get("data", [])[0]["sta"])
        start_st_id = STA_MAP.get(start_st_name, start_st_name)

        unique_no = f"{original_no}|{start_st_id}"
        
        all_chunks.append({
            "no": unique_no, "op_type": op_type,
            "type": clean_train_type(train.get("列車種別", ""), train.get("列車名", "")),
            "thru_link": train.get("直通運転"),
            "stops": stop_times,  # 🌟 這裡現在儲存的是陣列
            "ordered_stops": ordered_stops,
            "start_time": stop_times[0][1] if isinstance(stop_times[0][1], int) else 9999
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
        # 🌟 修正：改用平行陣列，並加入去重複機制
        full_ordered_stops = []
        full_ordered_times = []
        seen_chunks = set() # 🌟 防止相同區段疊加
        
        for seg in t_info["segments_data"]:
            # 排除完全重複的時刻表區塊
            chunk_hash = str(seg["ordered_stops"]) + str(seg["stops"])
            if chunk_hash in seen_chunks: continue
            seen_chunks.add(chunk_hash)
            
            for idx, st in enumerate(seg["ordered_stops"]): # 🌟 取得當前車站索引
                st_time = seg["stops"][idx] # 🌟 從對應的 Index 精準取得時間
                
                if not full_ordered_stops or full_ordered_stops[-1] != st:
                    full_ordered_stops.append(st)
                    full_ordered_times.append(st_time)
                else:
                    # 處理跨 Chunk 資料交界處的時間合併
                    prev_arr, prev_dep = full_ordered_times[-1]
                    new_arr, new_dep = st_time
                    full_ordered_times[-1] = (
                        prev_arr if prev_arr != "" else new_arr,
                        new_dep if new_dep != "" else prev_dep
                    )
        
        # 🌟 初始化 v 值陣列 (原始停靠站預設 1 = 停靠)
        full_ordered_v = [1] * len(full_ordered_stops)

        # ==========================================
        # 🌟 核心升級：拓樸斷層修復 (精準里程內插 + 通過站特判)
        # ==========================================
        fixed_stops, fixed_times, fixed_v = [], [], []
        
        for i in range(len(full_ordered_stops) - 1):
            s1 = full_ordered_stops[i]
            s2 = full_ordered_stops[i+1]
            t1 = full_ordered_times[i]
            t2 = full_ordered_times[i+1]
            v1 = full_ordered_v[i]
            
            fixed_stops.append(s1)
            fixed_times.append(t1)
            fixed_v.append(v1) # 寫入真實 v 值
            
            common_lines = [l_id for l_id, l_sts in LINE_MAP.items() if s1 in l_sts and s2 in l_sts]
            
            if not common_lines:
                s1_lines = [l_id for l_id, l_sts in LINE_MAP.items() if s1 in l_sts]
                s2_lines = [l_id for l_id, l_sts in LINE_MAP.items() if s2 in l_sts]
                
                is_loop_to_yamatoji = "osaka_loop_line" in s1_lines and "yamatoji_line" in s2_lines
                is_yamatoji_to_loop = "yamatoji_line" in s1_lines and "osaka_loop_line" in s2_lines
                
                if is_loop_to_yamatoji or is_yamatoji_to_loop:
                    intersection = "今宮"
                    fixed_stops.append(intersection)
                    fixed_v.append(2) # 🌟 關鍵：賦予橋樑站 v=2 (通過) 屬性
                    
                    # 🌟 透過里程精準內插時間
                    try:
                        dep1 = int(t1[1]) if t1[1] != "" else int(t1[0])
                        arr2 = int(t2[0]) if t2[0] != "" else int(t2[1])
                        
                        # 動態找出 s1 到 今宮，以及 今宮 到 s2 所屬的路線
                        l1 = next((l for l in s1_lines if intersection in LINE_MAP[l]), s1_lines[0])
                        l2 = next((l for l in s2_lines if intersection in LINE_MAP[l]), s2_lines[0])
                        
                        # 讀取里程並計算絕對距離
                        d1 = abs(KM_MAP.get((l1, intersection), 0.0) - KM_MAP.get((l1, s1), 0.0))
                        d2 = abs(KM_MAP.get((l2, s2), 0.0) - KM_MAP.get((l2, intersection), 0.0))
                        total_d = d1 + d2
                        
                        if total_d > 0:
                            # 依照物理距離比例，算出通過時間
                            ratio = d1 / total_d
                            mid_time = dep1 + (arr2 - dep1) * ratio
                            mid_time = int(round(mid_time))
                        else:
                            mid_time = (dep1 + arr2) // 2
                            
                        fixed_times.append((mid_time, mid_time)) 
                    except:
                        # 備用防呆：如果有資料毀損，才退回平均值
                        dep1 = int(t1[1]) if t1[1] != "" else int(t1[0])
                        arr2 = int(t2[0]) if t2[0] != "" else int(t2[1])
                        mid_time = (dep1 + arr2) // 2
                        fixed_times.append((mid_time, mid_time))
                        
        fixed_stops.append(full_ordered_stops[-1])
        fixed_times.append(full_ordered_times[-1])
        fixed_v.append(full_ordered_v[-1])
        
        # 覆蓋回原陣列，準備進行換軌判定
        full_ordered_stops = fixed_stops
        full_ordered_times = fixed_times
        full_ordered_v = fixed_v

        segs = []
        current_line = None
        current_seg_s, current_seg_t, current_seg_v = [], [], []

        for i in range(len(full_ordered_stops) - 1):
            s1 = full_ordered_stops[i]
            s2 = full_ordered_stops[i+1]
            t1 = full_ordered_times[i]   # 🌟 取得 s1 的時間
            t2 = full_ordered_times[i+1] # 🌟 取得 s2 的時間
            
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
                        segs[-1]["system_path"] = OTHER_LINES[current_line]["path"]
                        segs[-1]["system_name"] = OTHER_LINES[current_line]["name"]

                current_line = chosen_line
                st1_id = STA_MAP.get((current_line, s1)) or STA_MAP.get(s1, s1)
                
                current_seg_s, current_seg_t, current_seg_v = [st1_id], [t1[0], t1[1]], [full_ordered_v[i]]
                
            # 推進下一站
            st2_id = STA_MAP.get((current_line, s2)) or STA_MAP.get(s2, s2)
            current_seg_s.append(st2_id)
            
            # 🌟 改用 t2 讀取時間
            current_seg_t.extend([t2[0], t2[1]])
            current_seg_v.append(full_ordered_v[i+1])

        if current_line is not None:
            segs.append({"id": current_line, "s": current_seg_s, "t": current_seg_t, "v": current_seg_v})
            if current_line in OTHER_LINES:
                segs[-1]["is_other"] = True
                segs[-1]["system_path"] = OTHER_LINES[current_line]["path"]
                segs[-1]["system_name"] = OTHER_LINES[current_line]["name"]
            
        # 修補 v 值 (0=起點, 3=終點, 1=中間)
        if segs:
            if len(segs[0]["v"]) > 0:
                segs[0]["v"][0] = 0
            if len(segs[-1]["v"]) > 0:
                segs[-1]["v"][-1] = 3
        
        if not segs: continue
        
        processed_trains.append({
            "no": t_info["no"], "type": t_info["type"], "segments": segs, "coupled_with": [],
            "_first_sta": full_ordered_stops[0], "_last_sta": full_ordered_stops[-1],
            "_thru_links": t_info["thru_links"], "_is_wd": t_info["is_wd"], "_is_we": t_info["is_we"]
        })

    # 5. 直通運轉配對
    for t in processed_trains:
        for target_no in t["_thru_links"]:
            partners = [p for p in processed_trains if p["no"].split('|')[0] == target_no]
            
            for partner in partners:
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