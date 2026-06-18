#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
convert_timetable.py — navitime raw → 本專案「車次為中心」多 segment 格式

輸入：json/raw_weekday.json、json/raw_holiday.json（timetable.py 產生）
      每筆 = {code, type, stops:[{name, arr, dep}...]}（stops 已為行進順序、已跨夜處理）
輸出：json/timetable/timetable_weekday.json、timetable_holiday.json

多 segment 切分（移植自 TRA compile_train_data）：依拓樸判斷每站屬於哪些 segment，
相鄰兩站取共同 segment；換段時於交會站切開（交會站同時作為前段末站與後段首站）。
navitime 無通過站 → v 僅 0(起)/1(停)/3(訖)，不產生 2(通過)。
不在任何 segment 的站會被略過；切到只剩 <2 站的整段捨棄（如純支線區間車掃到的非幹線片段）。
"""
import sys
import json
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

JSON_DIR = Path(__file__).parent.parent / "json"


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
    """把一班車的 stops 切成多 segment。回傳 segments 陣列或 []。"""
    valid = []
    for st in raw["stops"]:
        name = st["name"]
        if name in STATION_INFO:
            si = STATION_INFO[name]
            valid.append({"id": si["id"], "arr": st["arr"], "dep": st["dep"],
                          "segs": list(si["segments"]), "km_map": si["km_map"]})
    if len(valid) < 2:
        return []

    # 1) 決定每站的 true_seg（與下一站的共同段優先；否則沿用前站；否則自身第一段）
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

    # 2) 走訪、換段時於交會站切開
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
            # 交會站：同時收尾前段、開啟後段
            s_ids.append(st["id"]); t_times.extend([st["arr"], st["dep"]]); v_types.append(v)
            if len(s_ids) > 1:
                compiled.append({"id": cur_seg, "s": s_ids, "t": t_times, "v": v_types})
            cur_seg = st["true_seg"]
            s_ids, t_times, v_types = [st["id"]], [st["arr"], st["dep"]], [v]
        else:
            if st["true_seg"] != cur_seg:
                # 罕見：換段但非交會站（navitime 幾乎不會發生）→ 直接續用，避免漏站
                cur_seg = st["true_seg"]
            s_ids.append(st["id"]); t_times.extend([st["arr"], st["dep"]]); v_types.append(v)

    if len(s_ids) > 1:
        compiled.append({"id": cur_seg, "s": s_ids, "t": t_times, "v": v_types})
    return compiled


def convert_file(raw_name, out_name, STATION_INFO):
    raw_path = JSON_DIR / raw_name
    if not raw_path.exists():
        print(f"⏭️  跳過（找不到 {raw_name}）")
        return
    with open(raw_path, "r", encoding="utf-8") as f:
        raw_list = json.load(f)

    trains, skipped = [], 0
    for raw in raw_list:
        segs = compile_train(raw, STATION_INFO)
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
