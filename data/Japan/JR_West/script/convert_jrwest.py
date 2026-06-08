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

def parse_couple_text(text):
    """解析 '日根野－天王寺は4584Hを併結' → ('4584H', '日根野', '天王寺')
    忽略含有〔〕或「間」的複雜特急格式（サンライズ、ひだ 等非 topology 範圍）"""
    if not text:
        return None
    if '〔' in text or ('間' in text and 'は' not in text):
        return None
    m = re.match(r'([^－–－]+)[－–－]([^は]+)は([^をに〔（\s]+)[をに]併結', text)
    if m:
        return (m.group(3).strip(), m.group(1).strip(), m.group(2).strip())
    return None

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
        _bus_info = None
        _extra_exclude = []

        # 先決定基本運行類型（weekday / holiday / irregular / daily）
        if "土曜・休日運休" in op_text or "土曜・休日は運休" in op_text or "平日運転" in op_text:
            op_type = "weekday"
        elif "土曜・休日運転" in op_text or "土曜・休日は運転" in op_text or "休日運転" in op_text:
            op_type = "holiday"
        elif "月" in op_text and ("日" in op_text or "・" in op_text) \
                and "バス代行" not in op_text and "代行輸送" not in op_text:
            _norm_op = unicodedata.normalize('NFKC', op_text)
            _excl_m = re.search(r'((?:\d+月[\d・]+日[\s・]*)+)は運休', _norm_op)
            if _excl_m and "土曜" not in _norm_op and "休日" not in _norm_op:
                # "X月Y日は運休" = 毎日運転だが特定日のみ除外
                op_type = "daily"
                _extra_exclude = parse_japanese_dates(_excl_m.group(1), 2026)
            else:
                op_type = "irregular"
                dates = parse_japanese_dates(op_text, 2026)

        # バス代行の解析は op_type と独立して実行（土曜・休日運休との共存も対応）
        if "バス代行" in op_text or "代行輸送" in op_text:
            _norm = unicodedata.normalize('NFKC', op_text)
            # Pattern 1: 部分区間代行 "X月Y日はA－B間運休・同区間バス代行"
            # [\s・]* allows "・" between multi-month date groups e.g. "5月22・29日・6月5日"
            _bm = re.search(r'((?:\d+月[\d・]+日[\s・]*)+)は(.+?)[－\-](.+?)間運休', _norm)
            if _bm:
                _bus_dates = parse_japanese_dates(_bm.group(1), 2026)
                _bus_from = clean_station_name(_bm.group(2).strip())
                _bus_to   = clean_station_name(_bm.group(3).strip())
                if _bus_dates:
                    _bus_info = (_bus_dates, _bus_from, _bus_to)
            else:
                # Pattern 2: 全線代行 "X月Y日は運休・バス代行" → bus 範囲は首尾站
                _bm2 = re.search(r'((?:\d+月[\d・]+日[\s・]*)+)は運休', _norm)
                if _bm2:
                    _bus_dates = parse_japanese_dates(_bm2.group(1), 2026)
                    if _bus_dates:
                        _bus_info = (_bus_dates, None, None)  # None = 全線，後で首尾站を使う
            
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
        
        # 代行がある日は元の列車を exclude（Pattern 1・2 共通）
        _chunk_exclude = (_bus_info[0] if _bus_info else []) + _extra_exclude

        all_chunks.append({
            "no": unique_no,
            "op_type": op_type,
            "operation": op_type,
            "dates": dates,
            "exclude_dates": _chunk_exclude,
            "type": clean_train_type(train.get("列車種別", ""), train.get("列車名", "")),
            "thru_link": train.get("直通運転"),
            "couple_text": train.get("併結運転"),
            "stops": stop_times,
            "ordered_stops": ordered_stops,
            "start_time": stop_times[0][1] if isinstance(stop_times[0][1], int) else 9999
        })

        if _bus_info:
            bus_dates, bus_from, bus_to = _bus_info
            try:
                if bus_from is None:
                    # Pattern 2: 全線代行 → バスのみ（元列車は exclude_dates で消える）
                    fi, ti = 0, len(ordered_stops) - 1
                    bus_stops = ordered_stops[fi:ti + 1]
                    bus_times = stop_times[fi:ti + 1]
                    bus_start_id = STA_MAP.get(bus_stops[0], bus_stops[0])
                    all_chunks.append({
                        "no": f"{original_no}_B|{bus_start_id}",
                        "op_type": "irregular", "operation": "irregular",
                        "dates": bus_dates, "exclude_dates": [],
                        "type": "バス",
                        "thru_link": None, "couple_text": None,
                        "stops": bus_times, "ordered_stops": bus_stops,
                        "start_time": bus_times[0][1] if isinstance(bus_times[0][1], int) else 9999
                    })
                else:
                    # Pattern 1: 部分区間代行 → 截短普通車 + バス、直通連結
                    fi = ordered_stops.index(bus_from)
                    ti = ordered_stops.index(bus_to)
                    if fi < ti:
                        train_type = clean_train_type(train.get("列車種別", ""), train.get("列車名", ""))
                        last_idx   = len(ordered_stops) - 1
                        bus_no      = f"{original_no}_B|{STA_MAP.get(bus_from, bus_from)}"
                        trunc_pre_no  = f"{original_no}_T|{start_st_id}"
                        trunc_post_no = f"{original_no}_T2|{STA_MAP.get(ordered_stops[ti], ordered_stops[ti])}"

                        # ① バス前段普通車（fi > 0 のときのみ）: 首站 → 代行開始站
                        if fi > 0:
                            all_chunks.append({
                                "no": trunc_pre_no,
                                "display_no": original_no,  # 表示用は元の車番
                                "op_type": "irregular", "operation": "irregular",
                                "dates": bus_dates, "exclude_dates": [],
                                "type": train_type,
                                "thru_link": original_no + "_B",
                                "couple_text": None,
                                "stops": stop_times[:fi + 1],
                                "ordered_stops": ordered_stops[:fi + 1],
                                "start_time": stop_times[0][1] if isinstance(stop_times[0][1], int) else 9999
                            })

                        # ② バス：代行開始站 → 代行終點站
                        bus_thru = (original_no + "_T2") if ti < last_idx else train.get("直通運転")
                        all_chunks.append({
                            "no": bus_no,
                            "display_no": original_no,  # 表示用は元の車番
                            "op_type": "irregular", "operation": "irregular",
                            "dates": bus_dates, "exclude_dates": [],
                            "type": "バス",
                            "thru_link": bus_thru,
                            "couple_text": None,
                            "stops": stop_times[fi:ti + 1],
                            "ordered_stops": ordered_stops[fi:ti + 1],
                            "start_time": stop_times[fi][1] if isinstance(stop_times[fi][1], int) else 9999
                        })

                        # ③ バス後段普通車（ti < last_idx のときのみ）: 代行終點站 → 終着站
                        if ti < last_idx:
                            all_chunks.append({
                                "no": trunc_post_no,
                                "display_no": original_no,  # 表示用は元の車番
                                "op_type": "irregular", "operation": "irregular",
                                "dates": bus_dates, "exclude_dates": [],
                                "type": train_type,
                                "thru_link": train.get("直通運転"),
                                "couple_text": None,
                                "stops": stop_times[ti:],
                                "ordered_stops": ordered_stops[ti:],
                                "start_time": stop_times[ti][1] if isinstance(stop_times[ti][1], int) else 9999
                            })
            except (ValueError, IndexError):
                pass

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
                "exclude_dates": instance[0].get("exclude_dates", []),
                "display_no": instance[0].get("display_no"),
                "segments_data": instance,
                "thru_links": set(c["thru_link"] for c in instance if c["thru_link"] and c["thru_link"] != instance[0]["no"]),
                "couple_texts": list({c["couple_text"] for c in instance if c.get("couple_text")})
            }

    # 5. 邊遍歷演算法 (Stop-by-Stop Edge Mapping)
    processed_trains = []
    for unique_id, t_info in train_buffer.items():
        # 時間相同時，站數多的（完整版）優先處理，避免截短版先被展開後完整版又重複
        t_info["segments_data"].sort(key=lambda x: (x["start_time"], -len(x["ordered_stops"])))

        full_ordered_stops = []
        full_ordered_times = []
        seen_chunks = set()

        for seg in t_info["segments_data"]:
            chunk_hash = str(seg["ordered_stops"]) + str(seg["stops"])
            if chunk_hash in seen_chunks: continue
            seen_chunks.add(chunk_hash)

            # 若此 chunk 與已建路線有相同起始站＋起始時間，代表是同班車的截短版，跳過
            if (full_ordered_stops and seg["ordered_stops"] and
                    seg["ordered_stops"][0] == full_ordered_stops[0] and
                    seg["stops"][0] == full_ordered_times[0]):
                continue
            
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

            # 大和路線⇔おおさか東線：中轉站為久宝寺（9023M 等）
            is_yamatoji_to_higashi = (
                "yamatoji_line" in s1_lines and "osaka_higashi_line" not in s1_lines and
                "osaka_higashi_line" in s2_lines and "yamatoji_line" not in s2_lines
            )
            is_higashi_to_yamatoji = (
                "osaka_higashi_line" in s1_lines and "yamatoji_line" not in s1_lines and
                "yamatoji_line" in s2_lines and "osaka_higashi_line" not in s2_lines
            )

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
                    else:
                        mid_time = (dep1 + arr2) / 2

                    fixed_times.append((mid_time, mid_time))
                except:
                    dep1 = int(t1[1]) if t1[1] != "" else int(t1[0])
                    arr2 = int(t2[0]) if t2[0] != "" else int(t2[1])
                    mid_time = (dep1 + arr2) / 2
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
                    else:
                        mid_time = (dep1 + arr2) / 2

                    fixed_times.append((mid_time, mid_time))
                except:
                    dep1 = int(t1[1]) if t1[1] != "" else int(t1[0])
                    arr2 = int(t2[0]) if t2[0] != "" else int(t2[1])
                    mid_time = (dep1 + arr2) / 2
                    fixed_times.append((mid_time, mid_time))

            elif not common_lines and (is_yamatoji_to_higashi or is_higashi_to_yamatoji):
                # 9023M 等大和路線⇔おおさか東線直通列車：強制經由久宝寺換線，並內插通過時間
                intersection = "久宝寺"
                l1 = "yamatoji_line"      if is_yamatoji_to_higashi else "osaka_higashi_line"
                l2 = "osaka_higashi_line" if is_yamatoji_to_higashi else "yamatoji_line"
                fixed_preferred[-1] = l1   # 強制前段邊（s1→久宝寺）使用正確路線
                fixed_stops.append(intersection)
                fixed_v.append(2)
                fixed_preferred.append(l2)  # 久宝寺→s2 使用後段路線

                try:
                    dep1 = int(t1[1]) if t1[1] != "" else int(t1[0])
                    arr2 = int(t2[0]) if t2[0] != "" else int(t2[1])

                    d1 = abs(KM_MAP.get((l1, intersection), 0.0) - KM_MAP.get((l1, s1), 0.0))
                    d2 = abs(KM_MAP.get((l2, s2), 0.0) - KM_MAP.get((l2, intersection), 0.0))
                    total_d = d1 + d2

                    if total_d > 0:
                        ratio = d1 / total_d
                        mid_time = dep1 + (arr2 - dep1) * ratio
                    else:
                        mid_time = (dep1 + arr2) / 2

                    fixed_times.append((mid_time, mid_time))
                except:
                    dep1 = int(t1[1]) if t1[1] != "" else int(t1[0])
                    arr2 = int(t2[0]) if t2[0] != "" else int(t2[1])
                    mid_time = (dep1 + arr2) / 2
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
        
        train_obj = {
            "no": t_info["no"],
            "type": t_info["type"],
            "operation": t_info["operation"],
            "dates": t_info["dates"],
            "segments": segs,
            "coupled_with": [],
            "_first_sta": full_ordered_stops[0], "_last_sta": full_ordered_stops[-1],
            "_thru_links": t_info["thru_links"],
            "_couple_texts": t_info.get("couple_texts", []),
            "_is_wd": t_info["is_wd"], "_is_we": t_info["is_we"]
        }
        if t_info.get("exclude_dates"):
            train_obj["exclude_dates"] = t_info["exclude_dates"]
        if t_info.get("display_no"):
            train_obj["display_no"] = t_info["display_no"]
        processed_trains.append(train_obj)

    def _op_compat(a, b):
        """兩班車有至少一個共同運行日（平日或假日）才算相容"""
        return (a["_is_wd"] and b["_is_wd"]) or (a["_is_we"] and b["_is_we"])

    # 直通運轉配對
    for t in processed_trains:
        for target_no in t["_thru_links"]:
            partners = [p for p in processed_trains if p["no"].split('|')[0] == target_no and _op_compat(t, p)]
            
            for partner in partners:
                j_name = t["_last_sta"] if t["_last_sta"] == partner["_first_sta"] else (t["_first_sta"] if t["_first_sta"] == partner["_last_sta"] else None)
                if j_name:
                    j_id = STA_MAP.get(j_name, j_name)
                    # 單向直通：只在「前段→後段」方向寫入 coupled_with（t 是前段，partner 是後段）
                    if not any(c["train_id"] == partner["no"] for c in t["coupled_with"]): t["coupled_with"].append({"train_id": partner["no"], "station_id": j_id, "action": "direct"})

    # ==========================================
    # 🌟 併結配對（split / merge 智慧拓樸版 - 終極修正版）
    # ==========================================
    def get_clean_stations(train_obj):
        # 取得乾淨、無相鄰重複的車站名單
        st_list = []
        for seg in train_obj.get("segments", []):
            for s in seg["s"]:
                sid = str(s)
                if not st_list or st_list[-1] != sid:
                    st_list.append(sid)
        return st_list

    for t in processed_trains:
        for couple_text in t.get("_couple_texts", []):
            parsed = parse_couple_text(couple_text)
            if not parsed:
                continue
            partner_no, sta1, sta2 = parsed

            partners = [p for p in processed_trains if p["no"].split('|')[0] == partner_no and _op_compat(t, p)]
            for partner in partners:
                t_stations = get_clean_stations(t)
                p_stations = get_clean_stations(partner)
                
                # 🌟 1. 優先使用 JSON 文本中解析出的真實交會站 (例如：日根野)
                junction_id = None
                for sta_name in [clean_station_name(sta1), clean_station_name(sta2)]:
                    sid = str(STA_MAP.get(sta_name, sta_name))
                    if sid in t_stations and sid in p_stations:
                        junction_id = sid
                        break

                couple_action = "split" # 預設保底

                if junction_id:
                    # 🌟 2. 找到交會站在各自路線中的位置
                    idx_t = t_stations.index(junction_id)
                    idx_p = p_stations.index(junction_id)
                    
                    # ==========================================
                    # 🌟 3. 起終點生死定理 (精準破解 JR 資料截斷)
                    # ==========================================
                    # 狀況 A：如果是某台車的「起點」，代表它從這裡分離誕生 ➔ Split
                    if idx_t == 0 or idx_p == 0:
                        couple_action = "split"
                        
                    # 狀況 B：如果是某台車的「終點」，代表它到這裡併入主線 ➔ Merge
                    elif idx_t == len(t_stations) - 1 or idx_p == len(p_stations) - 1:
                        couple_action = "merge"
                        
                    # 狀況 C：如果兩台車都有前後站 (沒有被截斷)，才比對鄰站
                    else:
                        shares_before = (t_stations[idx_t - 1] == p_stations[idx_p - 1])
                        shares_after = (t_stations[idx_t + 1] == p_stations[idx_p + 1])

                        if shares_after and not shares_before:
                            couple_action = "merge"    # 半路殺出，匯合後一起走
                        elif shares_before and not shares_after:
                            couple_action = "split"    # 黏在一起走，到這裡分岔
                        else:
                            couple_action = "split"    # 保底預設
                else:
                    # 4. 防呆：如果文本解析不出站名，用全域起終點來盲猜
                    shared = [s for s in t_stations if s in p_stations]
                    if not shared:
                        continue
                    if t_stations[-1] == p_stations[-1] and t_stations[0] != p_stations[0]:
                        couple_action = "merge"
                        junction_id = shared[0] 
                    else:
                        couple_action = "split"
                        junction_id = shared[-1]

                # 5. 寫入雙向關係
                if not any(c["train_id"] == partner["no"] for c in t["coupled_with"]):
                    t["coupled_with"].append({"train_id": partner["no"], "station_id": junction_id, "action": couple_action})
                if not any(c["train_id"] == t["no"] for c in partner["coupled_with"]):
                    partner["coupled_with"].append({"train_id": t["no"], "station_id": junction_id, "action": couple_action})

    # 6a. バス代行 suffix 除去（_B / _T / _T2 を no と coupled_with.train_id から削除）
    _suffix_re = re.compile(r'_(?:B|T2?)\|')
    no_remap = {}
    for t in processed_trains:
        old = t["no"]
        new = _suffix_re.sub('|', old)
        if new != old:
            no_remap[old] = new
    for t in processed_trains:
        t["no"] = no_remap.get(t["no"], t["no"])
        for c in t.get("coupled_with", []):
            c["train_id"] = no_remap.get(c["train_id"], c["train_id"])
        t.pop("display_no", None)  # no 已是乾淨車番，display_no 欄位不需輸出

    # 6. 分流與清理
    wd_final, we_final = [], []
    for t in processed_trains:
        is_wd = t.pop("_is_wd", False)
        is_we = t.pop("_is_we", False)

        t.pop("_first_sta", None)
        t.pop("_last_sta", None)
        t.pop("_thru_links", None)
        t.pop("_couple_texts", None)
        
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