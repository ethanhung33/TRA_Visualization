#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
convert_timetable.py — 新幹線 raw_YYYYMMDD.json → timetable_YYYYMMDD.json（DAILY_FILE）

東海道+山陽+九州 は 新大阪(TOK17)・博多(SAN18) を共用 id で接続。直通車（のぞみ 東京↔博多、
みずほ/さくら 新大阪↔鹿児島中央 等）は交會站で segment 切り分け。交會站を通過する車には
里程内插で交會站を v=2 挿入。外運営者なし（全て JR 新幹線、拓樸内）。

available_dates.json も raw_*.json の日付から再生成。
"""
import sys
import json
import glob
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

JSON_DIR = Path(__file__).parent.parent / "json"

SEG_STATION_IDS = {}
ID_INFO = {}


def load_station_info():
    with open(JSON_DIR / "topology.json", "r", encoding="utf-8") as f:
        topo = json.load(f)
    info = {}
    SEG_STATION_IDS.clear(); ID_INFO.clear()
    for seg in topo["segments"]:
        sid = seg["id"]
        SEG_STATION_IDS[sid] = set()
        for st in seg["stations"]:
            name, stid, km = st["name"], st["id"], st["km"]
            if name not in info:
                info[name] = {"id": stid, "segments": [], "km": {}}
            info[name]["segments"].append(sid)
            info[name]["km"][sid] = km
            SEG_STATION_IDS[sid].add(stid)
            if stid not in ID_INFO:
                ID_INFO[stid] = {"name": name, "segments": [], "km": {}}
            ID_INFO[stid]["segments"].append(sid)
            ID_INFO[stid]["km"][sid] = km
    return info


def _find_junction(a, b):
    for segA in a["segs"]:
        for segB in b["segs"]:
            if segA == segB:
                continue
            common = SEG_STATION_IDS.get(segA, set()) & SEG_STATION_IDS.get(segB, set())
            common.discard(a["id"]); common.discard(b["id"])
            if common:
                return next(iter(common)), segA, segB
    return None


def compile_train(raw, STATION_INFO):
    valid = []
    for st in raw["stops"]:
        name = st["name"]
        if name in STATION_INFO:
            si = STATION_INFO[name]
            valid.append({"id": si["id"], "arr": st["arr"], "dep": st["dep"],
                          "segs": list(si["segments"]), "km": dict(si["km"]),
                          "is_pass": False})
    if len(valid) < 2:
        return []

    i = 0
    while i < len(valid) - 1:
        a, b = valid[i], valid[i + 1]
        if not (set(a["segs"]) & set(b["segs"])):
            j = _find_junction(a, b)
            if j:
                jid, segA, segB = j
                jinfo = ID_INFO[jid]
                kmA = abs(jinfo["km"][segA] - a["km"][segA]) if segA in a.get("km", {}) else None
                kmB = abs(b["km"][segB] - jinfo["km"][segB]) if segB in b.get("km", {}) else None
                frac = kmA / (kmA + kmB) if (kmA is not None and kmB is not None and (kmA + kmB) > 0) else 0.5
                jt = int(round(a["dep"] + frac * (b["arr"] - a["dep"])))
                valid.insert(i + 1, {"id": jid, "arr": jt, "dep": jt,
                                     "segs": list(jinfo["segments"]),
                                     "km": dict(jinfo["km"]), "is_pass": True})
        i += 1

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

    compiled = []
    cur_seg = valid[0]["true_seg"]
    s_ids, t_times, v_types = [], [], []
    n = len(valid)

    def vtype(i):
        if valid[i].get("is_pass"):
            return 2
        if i == 0:
            return 0
        if i == n - 1:
            return 3
        return 1

    for i in range(n):
        st = valid[i]
        v = vtype(i)
        if st["true_seg"] != cur_seg and cur_seg in st["segs"]:
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


def convert_file(raw_path, STATION_INFO):
    with open(raw_path, "r", encoding="utf-8") as f:
        raw_list = json.load(f)
    trains, skipped = [], 0
    for raw in raw_list:
        segs = compile_train(raw, STATION_INFO)
        if segs:
            # no は旅客向けの愛称＋号数（のぞみ1号）。無ければ stopCode に退避。
            trains.append({"no": raw.get("name") or raw["code"],
                           "type": raw["type"], "segments": segs})
        else:
            skipped += 1
    trains.sort(key=lambda x: x["segments"][0]["t"][0])

    date = raw_path.stem.replace("raw_", "")
    out_dir = JSON_DIR / "timetable"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / f"timetable_{date}.json", "w", encoding="utf-8") as f:
        f.write("[\n")
        for i, tr in enumerate(trains):
            f.write(json.dumps(tr, ensure_ascii=False, separators=(",", ":")) +
                    (",\n" if i < len(trains) - 1 else "\n"))
        f.write("]\n")
    print(f"🎉 {raw_path.name} → timetable_{date}.json：{len(trains)} 班（略過 {skipped}）")
    return date


def main():
    STATION_INFO = load_station_info()
    raws = sorted(JSON_DIR.glob("raw_*.json"))
    if not raws:
        print("⚠️  raw_*.json が見つかりません。先に timetable.py を実行してください。")
        return
    dates = []
    for rp in raws:
        d = convert_file(rp, STATION_INFO)
        # YYYYMMDD → YYYY-MM-DD
        dates.append(f"{d[:4]}-{d[4:6]}-{d[6:8]}")
    with open(JSON_DIR / "available_dates.json", "w", encoding="utf-8") as f:
        json.dump(sorted(dates), f, ensure_ascii=False)
    print(f"📅 available_dates.json：{sorted(dates)}")


if __name__ == "__main__":
    main()
