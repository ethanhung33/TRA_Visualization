#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_topology.py — 智頭急行 智頭線 拓樸建構

単一線・14 駅（上郡→智頭、56.1 km）。
上郡で JR 山陽本線、智頭で JR 因美線と接続（特急スーパーはくと/いなばが直通）。
里程來源：日本語Wikipedia「智頭急行智頭線」駅一覧の営業キロ。
"""
import sys
import json
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 智頭線：上郡→智頭（14 駅、営業キロ）
CHIZU = [
    ("上郡",         0.0,  "CZ01"),
    ("苔縄",         4.8,  "CZ02"),
    ("河野原円心",   7.4,  "CZ03"),
    ("久崎",         12.2, "CZ04"),
    ("佐用",         17.2, "CZ05"),
    ("平福",         22.5, "CZ06"),
    ("石井",         27.1, "CZ07"),
    ("宮本武蔵",     30.6, "CZ08"),
    ("大原",         33.2, "CZ09"),
    ("西粟倉",       37.4, "CZ10"),
    ("あわくら温泉", 40.6, "CZ11"),
    ("山郷",         47.2, "CZ12"),
    ("恋山形",       50.0, "CZ13"),
    ("智頭",         56.1, "CZ14"),
]


def main():
    topology = {
        "operator_id": "Chizu_Express",
        "segments": [
            {
                "id": "chizu_line",
                "name": "智頭線",
                "stations": [
                    {"id": sid, "name": name, "km": round(km, 1)}
                    for name, km, sid in CHIZU
                ],
            }
        ],
    }

    json_dir = Path(__file__).parent.parent / "json"
    json_dir.mkdir(parents=True, exist_ok=True)
    with open(json_dir / "topology.json", "w", encoding="utf-8") as f:
        json.dump(topology, f, ensure_ascii=False, indent=2)

    print(f"🎉 topology.json：1 段、{len(CHIZU)} 駅  {CHIZU[0][0]}→{CHIZU[-1][0]}")


if __name__ == "__main__":
    main()
