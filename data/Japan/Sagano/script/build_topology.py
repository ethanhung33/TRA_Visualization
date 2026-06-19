#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_topology.py — 嵯峨野観光鉄道（嵐山小火車 / トロッコ列車）拓樸建構

単一線・4 駅。里程來源：日本語Wikipedia「嵯峨野観光線」駅一覧の営業キロ。
"""
import sys
import json
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 嵯峨野観光線：トロッコ嵯峨→トロッコ亀岡（4 駅、営業キロ）
SAGANO = [
    ("トロッコ嵯峨",   0.0, "SG01"),
    ("トロッコ嵐山",   1.0, "SG02"),
    ("トロッコ保津峡", 3.4, "SG03"),
    ("トロッコ亀岡",   7.3, "SG04"),
]


def main():
    topology = {
        "operator_id": "Sagano",
        "segments": [
            {
                "id": "sagano_line",
                "name": "嵯峨野観光線",
                "stations": [
                    {"id": sid, "name": name, "km": round(km, 1)}
                    for name, km, sid in SAGANO
                ],
            }
        ],
    }

    json_dir = Path(__file__).parent.parent / "json"
    json_dir.mkdir(parents=True, exist_ok=True)
    with open(json_dir / "topology.json", "w", encoding="utf-8") as f:
        json.dump(topology, f, ensure_ascii=False, indent=2)

    print(f"🎉 topology.json：1 段、{len(SAGANO)} 駅  "
          f"{SAGANO[0][0]}→{SAGANO[-1][0]}")


if __name__ == "__main__":
    main()
