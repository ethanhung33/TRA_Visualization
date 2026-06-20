#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_topology.py — 山陽電気鉄道 拓樸建構

2 segment：
  main_line   本線（西代→山陽姫路、43 駅）
  aboshi_line 網干線（飾磨→山陽網干、7 駅）
交會站：飾磨（SY40）本線 ↔ 網干線

里程來源：日本語Wikipedia 各線「駅一覧」の営業キロ。
站名は navitime 正規化後（(兵庫県) 等の括號除去）に合わせる。
"""
import sys
import json
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 本線：西代→山陽姫路（43 駅）
MAIN = [
    ("西代", 0.0, "SY01"), ("板宿", 1.0, "SY02"), ("東須磨", 1.8, "SY03"),
    ("月見山", 2.6, "SY04"), ("須磨寺", 3.3, "SY05"), ("山陽須磨", 3.7, "SY06"),
    ("須磨浦公園", 5.1, "SY07"), ("山陽塩屋", 6.8, "SY08"), ("滝の茶屋", 7.8, "SY09"),
    ("東垂水", 8.6, "SY10"), ("山陽垂水", 9.6, "SY11"), ("霞ヶ丘", 10.7, "SY12"),
    ("舞子公園", 11.5, "SY13"), ("西舞子", 12.4, "SY14"), ("大蔵谷", 14.3, "SY15"),
    ("人丸前", 14.9, "SY16"), ("山陽明石", 15.7, "SY17"), ("西新町", 16.9, "SY18"),
    ("林崎松江海岸", 18.4, "SY19"), ("藤江", 20.4, "SY20"), ("中八木", 21.8, "SY21"),
    ("江井ヶ島", 23.5, "SY22"), ("西江井ヶ島", 24.9, "SY23"), ("山陽魚住", 25.6, "SY24"),
    ("東二見", 27.3, "SY25"), ("西二見", 28.6, "SY26"), ("播磨町", 29.9, "SY27"),
    ("別府", 32.2, "SY28"), ("浜の宮", 34.1, "SY29"), ("尾上の松", 35.5, "SY30"),
    ("高砂", 37.3, "SY31"), ("荒井", 38.5, "SY32"), ("伊保", 39.7, "SY33"),
    ("山陽曽根", 41.3, "SY34"), ("大塩", 42.8, "SY35"), ("的形", 44.2, "SY36"),
    ("八家", 46.2, "SY37"), ("白浜の宮", 47.6, "SY38"), ("妻鹿", 49.0, "SY39"),
    ("飾磨", 50.9, "SY40"), ("亀山", 52.3, "SY41"), ("手柄", 53.4, "SY42"),
    ("山陽姫路", 54.7, "SY43"),
]

# 網干線：飾磨→山陽網干（7 駅、飾磨=本線と共用）
ABOSHI = [
    ("飾磨", 0.0, "SY40"), ("西飾磨", 2.4, "AB01"), ("夢前川", 3.6, "AB02"),
    ("広畑", 4.7, "AB03"), ("山陽天満", 5.6, "AB04"), ("平松", 7.3, "AB05"),
    ("山陽網干", 8.5, "AB06"),
]

SEGMENTS = [
    ("main_line",   "本線",   MAIN),
    ("aboshi_line", "網干線", ABOSHI),
]


def main():
    topology = {"operator_id": "Sanyo", "segments": []}
    for seg_id, seg_name, stations in SEGMENTS:
        topology["segments"].append({
            "id": seg_id,
            "name": seg_name,
            "stations": [
                {"id": sid, "name": name, "km": round(km, 1)}
                for name, km, sid in stations
            ],
        })

    json_dir = Path(__file__).parent.parent / "json"
    json_dir.mkdir(parents=True, exist_ok=True)
    with open(json_dir / "topology.json", "w", encoding="utf-8") as f:
        json.dump(topology, f, ensure_ascii=False, indent=2)

    uniq = {sid for _, _, sts in SEGMENTS for _, _, sid in sts}
    print(f"🎉 topology.json：{len(SEGMENTS)} 段、{len(uniq)} 個不重複站")
    for seg_id, seg_name, stations in SEGMENTS:
        print(f"   {seg_id:12s} {seg_name:6s} {len(stations):2d} 駅  {stations[0][0]}→{stations[-1][0]}")


if __name__ == "__main__":
    main()
