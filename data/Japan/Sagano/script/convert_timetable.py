#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
convert_timetable.py — 嵯峨野観光鉄道 raw → 本專案「車次為中心」格式

単一線・全駅停車のため、各班を 1 segment（sagano_line）に変換するだけ。
入力：json/raw_all.json   出力：json/timetable/timetable_all.json
全営業日で同一ダイヤのため単一ファイル（data_fetch_strategy: SINGLE_FILE）。
"""
import sys
import json
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

JSON_DIR = Path(__file__).parent.parent / "json"


def load_name_to_id():
    with open(JSON_DIR / "topology.json", "r", encoding="utf-8") as f:
        topo = json.load(f)
    name_to_id = {}
    for seg in topo["segments"]:
        for st in seg["stations"]:
            name_to_id[st["name"]] = st["id"]
    return name_to_id


def main():
    name_to_id = load_name_to_id()
    with open(JSON_DIR / "raw_all.json", "r", encoding="utf-8") as f:
        raw_list = json.load(f)

    trains, skipped = [], 0
    for raw in raw_list:
        stops = [st for st in raw["stops"] if st["name"] in name_to_id]
        if len(stops) < 2:
            skipped += 1
            continue
        n = len(stops)
        s = [name_to_id[st["name"]] for st in stops]
        t = [v for st in stops for v in (st["arr"], st["dep"])]
        v = [0] + [1] * (n - 2) + [3]
        trains.append({
            "no": raw["code"],
            "type": raw["type"],
            "segments": [{"id": "sagano_line", "s": s, "t": t, "v": v}],
        })

    trains.sort(key=lambda x: x["segments"][0]["t"][0])

    out_dir = JSON_DIR / "timetable"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "timetable_all.json", "w", encoding="utf-8") as f:
        f.write("[\n")
        for i, tr in enumerate(trains):
            f.write(json.dumps(tr, ensure_ascii=False, separators=(",", ":")) +
                    (",\n" if i < len(trains) - 1 else "\n"))
        f.write("]\n")
    print(f"🎉 raw_all.json → timetable_all.json：{len(trains)} 班（略過 {skipped} 班不足）")


if __name__ == "__main__":
    main()
