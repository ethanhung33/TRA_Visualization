#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_topology.py — 叡山電鉄 拓樸建構（叡山本線＋鞍馬線）

里程來源：日本維基百科「叡山電鉄叡山本線」「叡山電鉄鞍馬線」駅一覧（営業キロ）。
2 段，交會站 宝ヶ池（E06）兩段共用同一 id、各自 km；路段不重疊。
叡山ケーブル/ロープウェイ屬京福電鉄，不屬叡山電鉄，排除。
"""
import sys
import json
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# (站名, 営業キロ)
MAIN = [  # 叡山本線 出町柳→八瀬比叡山口
    ("出町柳", 0.0), ("元田中", 0.9), ("茶山・京都芸術大学", 1.4), ("一乗寺", 2.1),
    ("修学院", 2.9), ("宝ヶ池", 3.8), ("三宅八幡", 4.4), ("八瀬比叡山口", 5.6),
]
KURAMA = [  # 鞍馬線 宝ヶ池→鞍馬（宝ヶ池為交會站）
    ("宝ヶ池", 0.0), ("八幡前", 0.9), ("岩倉", 1.7), ("木野", 2.7), ("京都精華大前", 3.5),
    ("二軒茶屋", 4.1), ("市原", 5.3), ("二ノ瀬", 6.6), ("貴船口", 7.6), ("鞍馬", 8.8),
]

SEGMENTS = [
    ("eizan_main", "叡山本線", MAIN),
    ("kurama_line", "鞍馬線", KURAMA),
]

NAME_TO_ID = {}


def assign(name, sid):
    if name not in NAME_TO_ID:
        NAME_TO_ID[name] = sid


def main():
    # 本線 E01..E08（宝ヶ池=E06）
    for i, (name, _) in enumerate(MAIN):
        assign(name, f"E{i+1:02d}")
    # 鞍馬線非交會站 E09..E17（宝ヶ池沿用 E06）
    for i, name in enumerate(["八幡前", "岩倉", "木野", "京都精華大前", "二軒茶屋",
                              "市原", "二ノ瀬", "貴船口", "鞍馬"]):
        assign(name, f"E{9+i:02d}")

    topology = {"operator_id": "Eizan", "segments": []}
    for seg_id, seg_name, stations in SEGMENTS:
        topology["segments"].append({
            "id": seg_id,
            "name": seg_name,
            "stations": [{"id": NAME_TO_ID[n], "name": n, "km": round(km, 1)} for n, km in stations],
        })

    json_dir = Path(__file__).parent.parent / "json"
    json_dir.mkdir(parents=True, exist_ok=True)
    with open(json_dir / "topology.json", "w", encoding="utf-8") as f:
        json.dump(topology, f, ensure_ascii=False, indent=2)
    with open(json_dir / "station_name_to_id.json", "w", encoding="utf-8") as f:
        json.dump(NAME_TO_ID, f, ensure_ascii=False, indent=2)

    print(f"🎉 topology.json：{len(SEGMENTS)} 段、{len(NAME_TO_ID)} 個不重複站")
    for seg_id, seg_name, stations in SEGMENTS:
        print(f"   {seg_id:14s} {seg_name:6s} {len(stations)} 站  {stations[0][0]}→{stations[-1][0]}")


if __name__ == "__main__":
    main()
