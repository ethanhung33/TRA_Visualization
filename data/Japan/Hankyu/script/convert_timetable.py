#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
convert_timetable.py — navitime raw → 本專案「車次為中心」多 segment 格式

輸入：json/raw_weekday.json、json/raw_holiday.json（timetable.py 產生）
      每筆 = {code, type, stops:[{name, arr, dep}...]}
輸出：json/timetable/timetable_weekday.json、timetable_holiday.json

多 segment 切分（移植自 TRA compile_train_data）：依拓樸判斷每站屬於哪些 segment，
相鄰兩站取共同 segment；換段時於交會站切開（交會站同時作為前段末站與後段首站）。
navitime 無通過站 → v 僅 0(起)/1(停)/3(訖)，不產生 2(通過)。
不在任何 segment 的站会被略過；切到只剩 <2 站の整段捨棄。
"""
import sys
import json
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

JSON_DIR = Path(__file__).parent.parent / "json"

# 外運営者の駅セット（阪急ネットワーク外）
_METRO_SAKAISUJI = {
    "扇町", "南森町", "北浜", "堺筋本町", "長堀橋",
    "日本橋", "恵美須町", "動物園前", "天下茶屋",
}
_KOBE_KOSOKU = {"花隈", "高速神戸", "新開地"}


def load_station_info():
    """從 topology.json 建 name → {id, segments:[...], km_map:{seg:km}}。"""
    with open(JSON_DIR / "topology.json", "r", encoding="utf-8") as f:
        topo = json.load(f)
    info = {}
    for seg in topo["segments"]:
        sid = seg["id"]
        for st in seg["stations"]:
            name = st["name"]
            if name not in info:
                info[name] = {"id": st["id"], "segments": [], "km_map": {}}
            info[name]["segments"].append(sid)
            info[name]["km_map"][sid] = st["km"]
    return info


def compile_train(raw, STATION_INFO):
    """一班車の stops を複数 segment に切り分ける。"""
    valid = []
    for st in raw["stops"]:
        name = st["name"]
        if name in STATION_INFO:
            si = STATION_INFO[name]
            valid.append({"id": si["id"], "arr": st["arr"], "dep": st["dep"],
                          "segs": list(si["segments"]), "km_map": si["km_map"]})
    if len(valid) < 2:
        return []

    # 1) 各駅の true_seg を決定（隣駅との共通 segment を優先）
    for i in range(len(valid)):
        cur = valid[i]["segs"]
        if i < len(valid) - 1:
            nxt = valid[i + 1]["segs"]
            common = [s for s in cur if s in nxt]
            if common:
                valid[i]["true_seg"] = common[0]
                continue
        if i > 0:
            prev = valid[i - 1].get("true_seg")
            if prev and prev in cur:
                valid[i]["true_seg"] = prev
                continue
        valid[i]["true_seg"] = cur[0]

    # 2) 換段時に接続駅で切り分ける
    compiled = []
    cur_seg = valid[0]["true_seg"]
    s_ids, t_times, v_types = [], [], []
    n = len(valid)

    def vtype(i):
        if i == 0:
            return 0
        if i == n - 1:
            return 3
        return 1

    for i in range(n):
        st = valid[i]
        v = vtype(i)
        if st["true_seg"] != cur_seg and cur_seg in st["segs"]:
            # 接続駅：前 segment を閉じて後 segment を開始
            s_ids.append(st["id"]); t_times.extend([st["arr"], st["dep"]]); v_types.append(v)
            if len(s_ids) > 1:
                compiled.append({"id": cur_seg, "s": s_ids, "t": t_times, "v": v_types})
            cur_seg = st["true_seg"]
            s_ids, t_times, v_types = [st["id"]], [st["arr"], st["dep"]], [v]
        else:
            if st["true_seg"] != cur_seg:
                cur_seg = st["true_seg"]
            s_ids.append(st["id"]); t_times.extend([st["arr"], st["dep"]]); v_types.append(v)

    if len(s_ids) > 1:
        compiled.append({"id": cur_seg, "s": s_ids, "t": t_times, "v": v_types})
    return compiled


def _make_other_seg(stops, STATION_INFO=None):
    """連続する外運営者停車リストから is_other segment を生成する。
    境界站（阪急拓樸内の站）は名字ではなく阪急 ID で保存し、
    前端的 dedup が正常に動くようにする。"""
    n = len(stops)
    if n < 2:
        return None
    names = {st["name"] for st in stops}
    if names & _METRO_SAKAISUJI:
        seg_id, system_name = "osaka_metro_sakaisuji", "大阪メトロ堺筋線"
    elif names & _KOBE_KOSOKU:
        seg_id, system_name = "kobe_kosoku", "神戸高速鉄道"
    else:
        seg_id, system_name = "other_through", "直通区間"

    def _sid(st):
        if STATION_INFO and st["name"] in STATION_INFO:
            return STATION_INFO[st["name"]]["id"]
        return st["name"]

    s = [_sid(st) for st in stops]
    t = [v for st in stops for v in (st["arr"], st["dep"])]
    v = [0] + [1] * (n - 2) + [3]
    return {"id": seg_id, "s": s, "t": t, "v": v,
            "is_other": True, "system_name": system_name}


def process_train(raw, STATION_INFO):
    """大阪メトロ区間を is_other として分離し、阪急区間を compile_train に渡す。"""
    stops = raw["stops"]

    # 阪急内の最初・最後の駅インデックス
    first = next((i for i, s in enumerate(stops) if s["name"] in STATION_INFO), None)
    if first is None:
        return []
    last = next((i for i in range(len(stops) - 1, -1, -1) if stops[i]["name"] in STATION_INFO), first)

    # 地鐵前綴：stops[0..first]（含交接站，用阪急 ID 保存）
    prefix_seg = _make_other_seg(stops[:first + 1], STATION_INFO) if first > 0 else None
    # 地鐵後綴：stops[last..]（含交接站，用阪急 ID 保存）
    suffix_seg = _make_other_seg(stops[last:], STATION_INFO) if last < len(stops) - 1 else None

    hankyu_raw = {"code": raw["code"], "type": raw["type"],
                  "stops": stops[first:last + 1]}
    compiled = compile_train(hankyu_raw, STATION_INFO)
    if not compiled:
        return []

    return ([prefix_seg] if prefix_seg else []) + compiled + ([suffix_seg] if suffix_seg else [])


def convert_file(raw_name, out_name, STATION_INFO):
    raw_path = JSON_DIR / raw_name
    if not raw_path.exists():
        print(f"⏭️  スキップ（{raw_name} が見つかりません）")
        return
    with open(raw_path, "r", encoding="utf-8") as f:
        raw_list = json.load(f)

    trains, skipped = [], 0
    for raw in raw_list:
        segs = process_train(raw, STATION_INFO)
        if segs:
            trains.append({"no": raw["code"], "type": raw["type"], "segments": segs})
        else:
            skipped += 1
    trains.sort(key=lambda x: x["segments"][0]["t"][0])

    out_dir = JSON_DIR / "timetable"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / out_name, "w", encoding="utf-8") as f:
        f.write("[\n")
        for i, tr in enumerate(trains):
            f.write(json.dumps(tr, ensure_ascii=False, separators=(",", ":")) +
                    (",\n" if i < len(trains) - 1 else "\n"))
        f.write("]\n")
    print(f"🎉 {raw_name} → {out_name}：{len(trains)} 班（略過 {skipped} 班不足）")


def main():
    STATION_INFO = load_station_info()
    convert_file("raw_weekday.json", "timetable_weekday.json", STATION_INFO)
    convert_file("raw_holiday.json", "timetable_holiday.json", STATION_INFO)


if __name__ == "__main__":
    main()
