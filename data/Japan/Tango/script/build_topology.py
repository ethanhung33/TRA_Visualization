#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_topology.py — 京都丹後鉄道 拓樸建構（宮舞線＋宮豊線＋宮福線）

里程來源：日本維基百科「京都丹後鉄道宮津線」「京都丹後鉄道宮福線」駅一覧（営業キロ）。
3 段於 宮津 交會（hub）；宮豊線 km 由宮津線(西舞鶴起)減 24.7 換算為宮津起點。
JR西日本特急（はしだて等）直通至天橋立 → 由 navitime 在 KTR lineId 即可掃到，
其 JR 段（京都-福知山，山陰本線）的站不在 KTR 拓樸內，convert 會自動略過（同智頭急行作法）。
福知山/西舞鶴/豊岡 為與 JR 的轉乘端點，亦屬 KTR 站。
"""
import sys
import json
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# (站名, 営業キロ)；交會站 宮津 各段各自 km
MIYAMAI = [  # 宮舞線 西舞鶴→宮津
    ("西舞鶴", 0.0), ("四所", 5.4), ("東雲", 8.9), ("丹後神崎", 12.7),
    ("丹後由良", 14.4), ("栗田", 20.2), ("宮津", 24.7),
]
MIYATOYO = [  # 宮豊線 宮津→豊岡（km 自宮津起）
    ("宮津", 0.0), ("天橋立", 4.4), ("岩滝口", 8.1), ("与謝野", 11.0), ("京丹後大宮", 18.0),
    ("峰山", 23.6), ("網野", 30.8), ("夕日ヶ浦木津温泉", 36.4), ("小天橋", 41.8),
    ("かぶと山", 45.0), ("久美浜", 47.3), ("コウノトリの郷", 55.9), ("豊岡", 58.9),
]
MIYAFUKU = [  # 宮福線 宮津→福知山
    ("宮津", 0.0), ("宮村", 1.5), ("喜多", 3.1), ("辛皮", 9.1), ("大江山口内宮", 12.8),
    ("二俣", 15.0), ("大江高校前", 17.0), ("大江", 17.9), ("公庄", 20.4), ("下天津", 22.8),
    ("牧", 25.3), ("荒河かしの木台", 27.5), ("福知山市民病院口", 28.9), ("福知山", 30.4),
]

SEGMENTS = [
    ("miyamai_line", "宮舞線", MIYAMAI),
    ("miyatoyo_line", "宮豊線", MIYATOYO),
    ("miyafuku_line", "宮福線", MIYAFUKU),
]

NAME_TO_ID = {}


def assign(name, sid):
    if name not in NAME_TO_ID:
        NAME_TO_ID[name] = sid


def main():
    assign("宮津", "MZ")  # hub 交會站先給固定 id
    for i, (name, _) in enumerate([s for s in MIYAMAI if s[0] != "宮津"]):
        assign(name, f"MM{i+1:02d}")
    for i, (name, _) in enumerate([s for s in MIYATOYO if s[0] != "宮津"]):
        assign(name, f"MT{i+1:02d}")
    for i, (name, _) in enumerate([s for s in MIYAFUKU if s[0] != "宮津"]):
        assign(name, f"MF{i+1:02d}")

    topology = {"operator_id": "Tango", "segments": []}
    for seg_id, seg_name, stations in SEGMENTS:
        topology["segments"].append({
            "id": seg_id, "name": seg_name,
            "stations": [{"id": NAME_TO_ID[n], "name": n, "km": round(km, 1)} for n, km in stations],
        })

    json_dir = Path(__file__).parent.parent / "json"
    json_dir.mkdir(parents=True, exist_ok=True)
    with open(json_dir / "topology.json", "w", encoding="utf-8") as f:
        json.dump(topology, f, ensure_ascii=False, indent=2)
    with open(json_dir / "station_name_to_id.json", "w", encoding="utf-8") as f:
        json.dump(NAME_TO_ID, f, ensure_ascii=False, indent=2)

    print(f"🎉 topology.json：{len(SEGMENTS)} 段、{len(NAME_TO_ID)} 個不重複站（宮津為三線交會）")
    for seg_id, seg_name, stations in SEGMENTS:
        print(f"   {seg_id:15s} {seg_name:5s} {len(stations)} 站  {stations[0][0]}→{stations[-1][0]}")


if __name__ == "__main__":
    main()
