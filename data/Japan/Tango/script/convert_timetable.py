#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
convert_timetable.py — navitime raw → 本專案「車次為中心」多 segment 格式

輸入：json/raw_weekday.json、json/raw_holiday.json（timetable.py 產生）
      每筆 = {code, type, stops:[{name, arr, dep}...]}（已跨夜處理；種別変更直通車另帶 direct_to/direct_at）
輸出：json/timetable/timetable_weekday.json、timetable_holiday.json

KTR 站：依拓樸多 segment 切分（移植自 TRA），於交會站（宮津）切開。
外運營商站（JR西日本 山陰本線 京都-綾部 等不在 KTR 拓樸的站）：比照 JR_West 的智頭急行作法，
  收進 `is_other:true` segment（system_name="JR西日本"），前端會在底部資訊面板以「JR西日本」標註
  並列出這些停靠站（不畫在運行圖上）。
種別変更直通車（特急はしだて→快速）：raw 帶 direct_to/direct_at → 產生 coupled_with 直通連結，
  前端會畫直通接駁並串接顯示。
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


def _compile_ktr_run(run, STATION_INFO):
    """一段連續的 KTR 停靠 → 依拓樸切成多 segment（交會站切開）。v 全填 1，最後由呼叫端修首末。"""
    valid = [{"id": STATION_INFO[st["name"]]["id"], "arr": st["arr"], "dep": st["dep"],
              "segs": list(STATION_INFO[st["name"]]["segments"])} for st in run]
    if len(valid) < 2:
        return []
    for i in range(len(valid)):
        cur = valid[i]["segs"]
        if i < len(valid) - 1:
            common = [s for s in cur if s in valid[i + 1]["segs"]]
            if common:
                valid[i]["true_seg"] = common[0]; continue
        if i > 0 and valid[i - 1].get("true_seg") in cur:
            valid[i]["true_seg"] = valid[i - 1]["true_seg"]; continue
        valid[i]["true_seg"] = cur[0]

    out = []
    cur_seg = valid[0]["true_seg"]
    s_ids, t_times, v_types = [], [], []
    for i, st in enumerate(valid):
        if st["true_seg"] != cur_seg and cur_seg in st["segs"]:
            s_ids.append(st["id"]); t_times.extend([st["arr"], st["dep"]]); v_types.append(1)
            if len(s_ids) > 1:
                out.append({"id": cur_seg, "s": s_ids, "t": t_times, "v": v_types})
            cur_seg = st["true_seg"]
            s_ids, t_times, v_types = [st["id"]], [st["arr"], st["dep"]], [1]
        else:
            if st["true_seg"] != cur_seg:
                cur_seg = st["true_seg"]
            s_ids.append(st["id"]); t_times.extend([st["arr"], st["dep"]]); v_types.append(1)
    if len(s_ids) > 1:
        out.append({"id": cur_seg, "s": s_ids, "t": t_times, "v": v_types})
    return out


def _other_segment(run):
    """一段連續的外運營商（JR西日本）停靠 → is_other segment（資訊面板顯示用，不畫運行圖）。"""
    s, t, v = [], [], []
    for st in run:
        s.append(st["name"]); t.extend([st["arr"], st["dep"]]); v.append(1)
    return {"id": "jr_sanin", "s": s, "t": t, "v": v, "is_other": True,
            "system_name": "JR西日本", "system_path": "data/Japan/JR_West/"}


def compile_train(raw, STATION_INFO):
    """把 stops 依「是否在 KTR 拓樸」切成連續區段：KTR 區段照拓樸切，外運營商區段收進 is_other。"""
    # 1) 分段成連續的 KTR / 外運營商 run
    runs = []  # (is_ktr, [stops])
    for st in raw["stops"]:
        is_ktr = st["name"] in STATION_INFO
        if runs and runs[-1][0] == is_ktr:
            runs[-1][1].append(st)
        else:
            runs.append((is_ktr, [st]))

    ktr_count = sum(len(r) for k, r in runs if k)
    if ktr_count < 2:
        return []  # 不是 KTR 的車（純 JR 等）→ 略過

    segments = []
    for is_ktr, run in runs:
        if is_ktr:
            segments.extend(_compile_ktr_run(run, STATION_INFO))
        elif len(run) >= 1:
            segments.append(_other_segment(run))

    if not segments:
        return []
    # 修首末 v：全車第一站 0(起)、最後一站 3(訖)
    segments[0]["v"][0] = 0
    segments[-1]["v"][-1] = 3
    return segments


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
        if not segs:
            skipped += 1
            continue
        train = {"no": raw["code"], "type": raw["type"], "segments": segs}
        # 種別変更直通：產生 coupled_with（變更站 direct_at 須為 KTR 站）
        if raw.get("direct_to") and raw.get("direct_at") in STATION_INFO:
            train["coupled_with"] = [{
                "train_id": raw["direct_to"],
                "station_id": STATION_INFO[raw["direct_at"]]["id"],
                "action": "direct",
            }]
        trains.append(train)

    # 以第一個非 is_other segment 的首發時刻排序（is_other 在前時取其首發亦可）
    trains.sort(key=lambda x: x["segments"][0]["t"][0])

    out_dir = JSON_DIR / "timetable"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / out_name, "w", encoding="utf-8") as f:
        f.write("[\n")
        for i, tr in enumerate(trains):
            f.write(json.dumps(tr, ensure_ascii=False, separators=(",", ":")) +
                    (",\n" if i < len(trains) - 1 else "\n"))
        f.write("]\n")
    print(f"🎉 {raw_name} → {out_name}：{len(trains)} 班（略過 {skipped} 班）")


def main():
    STATION_INFO = load_station_info()
    convert_file("raw_weekday.json", "timetable_weekday.json", STATION_INFO)
    convert_file("raw_holiday.json", "timetable_holiday.json", STATION_INFO)


if __name__ == "__main__":
    main()
