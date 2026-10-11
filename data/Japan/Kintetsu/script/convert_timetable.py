"""
convert_timetable.py — 近鐵 raw → 本專案「車次為中心」格式

輸入：json/raw_weekday.json、json/raw_holiday.json（timetable.py 爬下來的原始資料）
輸出：json/timetable/timetable_weekday.json、timetable_holiday.json

- 站名對應 topology（STATION_MAPPING）；官網以括號標示的他社同名站（十条（京都地下鉄）、
  九条（阪神）…）保留括號，避免撞上近鐵自家的十条・九条・京都・松ヶ崎
- 直通外網（阪神・京都市営地下鉄・大阪メトロ）區間拆成 is_other segment，
  運行圖不畫，底部面板以業者名列出（同智頭急行・阪神）
"""
import json
import os
import re

# ==========================================
# 🛠️ 站名對應翻譯蒟蒻 (STATION_MAPPING)
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

# ==========================================
# 🛡️ 直通運轉外網車站 (EXTERNAL_OPERATORS)
# 這些站不畫在近鐵運行圖上，而是拆成 is_other segment，於底部面板以該業者名列出
# ==========================================
EXTERNAL_OPERATORS = {
    "hanshin": {
        "system_name": "阪神", "system_path": "data/Japan/Hanshin/",
        "stations": {
            "桜川", "ドーム前", "九条（阪神）", "西九条", "千鳥橋", "伝法", "福", "出来島", "大物", "尼崎",
            "尼崎センタープール前", "武庫川", "鳴尾・武庫川女子大前", "甲子園", "久寿川", "今津",
            "西宮", "香櫨園", "打出", "芦屋", "深江", "青木", "魚崎", "住吉", "御影", "石屋川",
            "新在家", "大石", "西灘", "岩屋", "神戸三宮", "元町",
        },
    },
    "kobe_kosoku": {
        "system_name": "神戸高速鉄道", "system_path": None,
        "stations": {"西代", "神戸高速"},
    },
    "kyoto_subway": {
        "system_name": "京都市営地下鉄", "system_path": None,
        "stations": {
            "国際会館", "松ヶ崎（京都地下鉄）", "北山", "北大路", "鞍馬口", "今出川", "丸太町", "烏丸御池",
            "四条", "五条", "京都（京都地下鉄）", "九条（京都地下鉄）", "十条（京都地下鉄）", "くいな橋",
        },
    },
    # 大阪 Metro 中央線（夢洲為 2025 年延伸開業站，けいはんな線直通列車會到此）
    "osaka_metro": {
        "system_name": "大阪メトロ", "system_path": None,
        "stations": {
            "コスモスクエア", "大阪港", "朝潮橋", "弁天町", "九条（大阪地下鉄）", "阿波座", "本町", "堺筋本町",
            "谷町四丁目", "森ノ宮", "緑橋", "深江橋", "高井田", "夢洲",
        },
    },
}
STATION_OPERATOR = {st: op for op, cfg in EXTERNAL_OPERATORS.items() for st in cfg["stations"]}

# 官網以括號標示他社同名站（例：十条（京都地下鉄）、九条（阪神）），
# 不能切掉括號，否則會撞上近鐵自家的十条・九条・京都・松ヶ崎
FOREIGN_OPERATOR_TAG = re.compile(r'（(?:京都地下鉄|大阪地下鉄|大阪メトロ|阪神)）')

MISSING_STATIONS = set()
TRUNCATED = []

def clean_station_name(name):
    """清理站名；免責聲明備註回傳 "SKIP_STATION"，他社同名站保留括號標註。"""
    if "ご覧ください" in name or "変更" in name:
        return "SKIP_STATION"
    if FOREIGN_OPERATOR_TAG.search(name):
        return name.replace('　', '').replace(' ', '').strip()
    name = re.sub(r'\[.*?\]', '', name)
    name = re.sub(r'（.*?）', '', name)
    name = name.replace('　', '').replace(' ', '')
    if name.endswith("駅"):
        name = name[:-1]
    name = name.strip()
    return STATION_MAPPING.get(name, name)

def clean_train_type(train_type):
    """車種名から設備・サービス註記と列車番号を除去し、setting.json の train_color キーに揃える。

      「特急ひのとり7列車（車いす対応車両）」            → 「特急ひのとり」
      「観光特急しまかぜ（京都発着）（車いす対応車両・車内販売）」→ 「観光特急しまかぜ」
    """
    if not train_type:
        return "Unknown"
    train_type = re.sub(r'（[^）]*(?:車いす|車内販売|発着)[^）]*）', '', train_type)
    train_type = re.sub(r'\d+列車', '', train_type)
    return train_type.strip()

def origin_of(raw_train):
    match = re.search(r'始発駅[：:]\s*([^）\)]+)', raw_train.get("dir", ""))
    return clean_station_name(match.group(1)) if match else None

def parse_time(t_val):
    """處理時間欄位，應對整數或類似 '−' 的字串"""
    if isinstance(t_val, int):
        return t_val
    if isinstance(t_val, str) and t_val.isdigit():
        return int(t_val)
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

def stop_times(stop):
    arr, dep = parse_time(stop.get("arr")), parse_time(stop.get("dep"))
    if arr is None: arr = dep
    if dep is None: dep = arr
    return [arr or 0, dep or 0]

def build_segment_dict(seg_id, stops, station_map):
    s_arr = [station_map.get(stop["clean_name"], {}).get("id", "Unknown") for stop in stops]
    t_arr = [t for stop in stops for t in stop_times(stop)]
    v_arr = [0] + [1] * (len(stops) - 2) + [3] if len(stops) > 1 else [0]
    return {"id": seg_id, "s": s_arr, "t": t_arr, "v": v_arr}

def build_other_segment(stops, op, station_map):
    """同一業者的連續停靠（端點可含近鐵境界站）→ is_other segment。
    境界站存 station id，外站存去掉業者標註的站名（十条（京都地下鉄）→ 十条）。"""
    if len(stops) < 2:
        return None
    cfg = EXTERNAL_OPERATORS[op]
    s_arr = [station_map[st["clean_name"]]["id"] if st["clean_name"] in station_map
             else FOREIGN_OPERATOR_TAG.sub('', st["clean_name"]) for st in stops]
    t_arr = [t for st in stops for t in stop_times(st)]
    v_arr = [0] + [1] * (len(stops) - 2) + [3]
    seg = {"id": op, "s": s_arr, "t": t_arr, "v": v_arr,
           "is_other": True, "system_name": cfg["system_name"]}
    if cfg["system_path"]:
        seg["system_path"] = cfg["system_path"]
    return seg

def split_external(stops, station_map):
    """首站前／末站後的外網停靠依業者切段；境界站繼承相鄰外站的業者，未知站名略過。"""
    stops = [st for st in stops if st["clean_name"] in station_map or st["clean_name"] in STATION_OPERATOR]
    ops = [STATION_OPERATOR.get(st["clean_name"]) for st in stops]
    n = len(stops)
    for i in range(n):
        if ops[i] is None:
            ops[i] = (ops[i + 1] if i + 1 < n else None) or (ops[i - 1] if i > 0 else None)
    segs = []
    i = 0
    while i < n:
        j = i
        while j + 1 < n and ops[j + 1] == ops[i]:
            j += 1
        seg = build_other_segment(stops[i:j + 1], ops[i], station_map) if ops[i] else None
        if seg:
            segs.append(seg)
        i = j + 1
    return segs

def save_compact_json(data, output_path):
    """以一班車一行的緊湊格式寫入 JSON"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("[\n")
        for i, train in enumerate(data):
            f.write("  " + json.dumps(train, ensure_ascii=False, separators=(',', ':')))
            f.write(",\n" if i < len(data) - 1 else "\n")
        f.write("]\n")

def format_train(raw_train, station_map):
    stops = []
    for stop in raw_train.get("data", []):
        st_name = clean_station_name(stop["station"])
        if st_name != "SKIP_STATION":
            stops.append({**stop, "clean_name": st_name})

    # ==========================================
    # 🧹 階段 A：只留近鐵境內的站（記下位置，用來切出前後的直通外網區間）
    # ==========================================
    valid_stops, valid_idx = [], []
    for i, stop in enumerate(stops):
        st_name = stop["clean_name"]
        if st_name in station_map:
            valid_stops.append(stop)
            valid_idx.append(i)
        elif st_name not in STATION_OPERATOR:
            MISSING_STATIONS.add(st_name)

    if len(valid_stops) < 2:
        return None

    origin = origin_of(raw_train)
    if origin in station_map and stops[0]["clean_name"] != origin:
        TRUNCATED.append(f'{raw_train.get("no")} {raw_train.get("dir")}：首站 {stops[0]["clean_name"]}')

    # ==========================================
    # 🧩 階段 B：依 topology 路線切段（交給前端縫合）
    # ==========================================
    segments = []
    current_segment_stops = []
    current_possible_lines = set()

    for stop in valid_stops:
        st_name = stop["clean_name"]
        st_lines = station_map.get(st_name, {}).get("lines", set())

        if not current_segment_stops:
            current_segment_stops.append(stop)
            current_possible_lines = set(st_lines)
            continue

        new_possible_lines = current_possible_lines.intersection(st_lines)

        # 🛑 強制切斷「折返 (Switchback)」路線
        if len(current_segment_stops) > 1 and current_segment_stops[-1]["clean_name"] == "近鉄奈良":
            new_possible_lines = set()

        if new_possible_lines:
            current_segment_stops.append(stop)
            current_possible_lines = new_possible_lines
            continue

        seg_id = list(current_possible_lines)[0] if current_possible_lines else "unknown_line"
        segments.append(build_segment_dict(seg_id, current_segment_stops, station_map))

        last_stop = current_segment_stops[-1]
        last_st_lines = station_map.get(last_stop["clean_name"], {}).get("lines", set())
        shared_lines = last_st_lines.intersection(st_lines)
        if shared_lines:
            # 正常交會站 (如: 西大寺)：同時在兩條線上，合法傳承
            current_segment_stops = [last_stop, stop]
            current_possible_lines = shared_lines
        else:
            # 斷層直通車 (如: 津 -> 鶴橋)：沒有共同路線，讓前端造橋
            current_segment_stops = [stop]
            current_possible_lines = set(st_lines)

    if len(current_segment_stops) > 1:
        seg_id = list(current_possible_lines)[0] if current_possible_lines else "unknown_line"
        segments.append(build_segment_dict(seg_id, current_segment_stops, station_map))

    # ==========================================
    # 🚇 階段 C：直通外網區間（含境界站）→ is_other
    # ==========================================
    first, last = valid_idx[0], valid_idx[-1]
    prefix = split_external(stops[:first + 1], station_map) if first > 0 else []
    suffix = split_external(stops[last:], station_map) if last < len(stops) - 1 else []

    return {
        "no": raw_train.get("no", "Unknown"),
        "type": clean_train_type(raw_train.get("type")),
        "segments": prefix + segments + suffix,
    }

def convert_file(raw_name, out_name, station_map, json_dir):
    raw_path = os.path.join(json_dir, raw_name)
    if not os.path.exists(raw_path):
        print(f"⏭️  跳過（找不到 {raw_name}）")
        return
    with open(raw_path, 'r', encoding='utf-8') as f:
        raw_list = json.load(f)

    # 同一車次只保留停站最多的一筆
    by_no = {}
    for raw in raw_list:
        train = format_train(raw, station_map)
        if not train:
            continue
        n = sum(len(sg["s"]) for sg in train["segments"])
        if train["no"] not in by_no or n > by_no[train["no"]][1]:
            by_no[train["no"]] = (train, n)

    trains = sorted((t for t, _ in by_no.values()), key=lambda x: x["no"])
    save_compact_json(trains, os.path.join(json_dir, 'timetable', out_name))
    print(f"💾 {raw_name} → {out_name}：{len(trains)} 班")

def main():
    json_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'json')
    with open(os.path.join(json_dir, 'topology.json'), 'r', encoding='utf-8') as f:
        station_map = build_station_map(json.load(f))

    convert_file('raw_weekday.json', 'timetable_weekday.json', station_map, json_dir)
    convert_file('raw_holiday.json', 'timetable_holiday.json', station_map, json_dir)

    if TRUNCATED:
        print(f"\n⚠️ {len(TRUNCATED)} 班的首站不是始発駅（爬蟲沒補齊），例：")
        for line in TRUNCATED[:10]:
            print("   ", line)
    MISSING_STATIONS.discard("")
    if MISSING_STATIONS:
        print("\n🚨 未匹配的站名（請補 STATION_MAPPING 或 EXTERNAL_OPERATORS）：")
        for st in sorted(MISSING_STATIONS):
            print(f'    "{st}"')

if __name__ == "__main__":
    main()
