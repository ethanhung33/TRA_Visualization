#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_topology.py — 京阪電鐵 全 8 線拓樸建構

里程來源：日本維基百科各線「駅一覧」的営業キロ（navitime 不提供営業キロ）。

8 條 segment，交會站（junction）在多個 segment 共用「同一 station id」但各有自己的 km：
  三条(KH40)         本線 ↔ 鴨東線
  天満橋(KH03)       本線 ↔ 中之島線
  枚方市(KH21)       本線 ↔ 交野線
  中書島(KH28)       本線 ↔ 宇治線
  びわ湖浜大津(OT12) 京津線 ↔ 石山坂本線
鋼索線下站為「ケーブル八幡宮口」（非石清水八幡宮），與本線無共用站 → 獨立。
大津線群（京津線＋石山坂本線）為與京阪線群實體分離的獨立網。

★ 不重疊原則：每段實體路段只屬於一個 segment；交會站只共用「節點」，
  其相鄰路段（如淀屋橋–天満橋）只出現在本線、不重複出現在中之島線。
"""
import sys
import json
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 每段 (站名, 営業キロ)；交會站照常列出（會以本線 id 對應）
MAIN = [  # 京阪本線 淀屋橋→三条（KH01..KH40 依序）
    ("淀屋橋", 0.0), ("北浜", 0.5), ("天満橋", 1.3), ("京橋", 3.0), ("野江", 4.6),
    ("関目", 5.3), ("森小路", 6.2), ("千林", 6.8), ("滝井", 7.2), ("土居", 7.6),
    ("守口市", 8.3), ("西三荘", 9.4), ("門真市", 10.1), ("古川橋", 10.8), ("大和田", 12.0),
    ("萱島", 12.8), ("寝屋川市", 15.0), ("香里園", 17.6), ("光善寺", 19.1), ("枚方公園", 20.8),
    ("枚方市", 21.8), ("御殿山", 23.5), ("牧野", 25.5), ("樟葉", 27.7), ("橋本", 30.1),
    ("石清水八幡宮", 31.8), ("淀", 35.3), ("中書島", 39.7), ("伏見桃山", 40.6), ("丹波橋", 41.3),
    ("墨染", 42.3), ("藤森", 43.3), ("龍谷大前深草", 44.1), ("伏見稲荷", 44.6), ("鳥羽街道", 45.2),
    ("東福寺", 46.1), ("七条", 47.0), ("清水五条", 47.7), ("祇園四条", 48.6), ("三条", 49.3),
]
OTO = [("三条", 0.0), ("神宮丸太町", 1.0), ("出町柳", 2.3)]
NAKA = [("中之島", 0.0), ("渡辺橋", 0.9), ("大江橋", 1.4), ("なにわ橋", 2.0), ("天満橋", 3.0)]
KATANO = [("枚方市", 0.0), ("宮之阪", 1.0), ("星ヶ丘", 1.7), ("村野", 2.5), ("郡津", 3.4),
          ("交野市", 4.4), ("河内森", 6.1), ("私市", 6.9)]
UJI = [("中書島", 0.0), ("観月橋", 0.7), ("桃山南口", 2.3), ("六地蔵", 3.1), ("木幡", 3.9),
       ("黄檗", 5.4), ("三室戸", 7.2), ("宇治", 7.6)]
KEISHIN = [("御陵", 0.0), ("京阪山科", 1.5), ("四宮", 2.1), ("追分", 3.4), ("大谷", 5.0),
           ("上栄町", 6.7), ("びわ湖浜大津", 7.5)]
ISHIYAMA = [("石山寺", 0.0), ("唐橋前", 0.7), ("京阪石山", 1.6), ("粟津", 2.4), ("瓦ヶ浜", 2.8),
            ("中ノ庄", 3.3), ("膳所本町", 3.8), ("錦", 4.2), ("京阪膳所", 4.7), ("石場", 5.5),
            ("島ノ関", 6.0), ("びわ湖浜大津", 6.7), ("三井寺", 7.2), ("大津市役所前", 8.0),
            ("京阪大津京", 8.5), ("近江神宮前", 9.1), ("南滋賀", 10.0), ("滋賀里", 10.8),
            ("穴太", 12.3), ("松ノ馬場", 13.5), ("坂本比叡山口", 14.1)]
CABLE = [("ケーブル八幡宮口", 0.0), ("ケーブル八幡宮山上", 0.4)]

SEGMENTS = [
    ("keihan_main", "京阪本線", MAIN),
    ("oto_line", "鴨東線", OTO),
    ("nakanoshima_line", "中之島線", NAKA),
    ("katano_line", "交野線", KATANO),
    ("uji_line", "宇治線", UJI),
    ("keishin_line", "京津線", KEISHIN),
    ("ishiyama_line", "石山坂本線", ISHIYAMA),
    ("cable_line", "鋼索線", CABLE),
]

# 站名 → id 全域指派：本線 KH01..KH40 → 鴨東 KH41,KH42 → 各支線新站，交會站沿用既有 id。
NAME_TO_ID = {}


def assign(name, sid):
    if name not in NAME_TO_ID:
        NAME_TO_ID[name] = sid


def main():
    # 本線 KH01..KH40
    for i, (name, _) in enumerate(MAIN):
        assign(name, f"KH{i+1:02d}")
    # 鴨東線（三条已是 KH40）
    assign("神宮丸太町", "KH41")
    assign("出町柳", "KH42")
    # 中之島線（天満橋已是 KH03），官方編號 なにわ橋 KH51..中之島 KH54
    assign("なにわ橋", "KH51")
    assign("大江橋", "KH52")
    assign("渡辺橋", "KH53")
    assign("中之島", "KH54")
    # 交野線（枚方市已是 KH21）KH61..KH67
    for i, name in enumerate(["宮之阪", "星ヶ丘", "村野", "郡津", "交野市", "河内森", "私市"]):
        assign(name, f"KH{61+i}")
    # 宇治線（中書島已是 KH28）KH71..KH77
    for i, name in enumerate(["観月橋", "桃山南口", "六地蔵", "木幡", "黄檗", "三室戸", "宇治"]):
        assign(name, f"KH{71+i}")
    # 石山坂本線 OT01..OT21（びわ湖浜大津 = OT12，與京津線共用）
    for i, (name, _) in enumerate(ISHIYAMA):
        assign(name, f"OT{i+1:02d}")
    # 京津線（びわ湖浜大津已是 OT12）KS01..KS06
    for i, name in enumerate(["御陵", "京阪山科", "四宮", "追分", "大谷", "上栄町"]):
        assign(name, f"KS{i+1:02d}")
    # 鋼索線
    assign("ケーブル八幡宮口", "CB01")
    assign("ケーブル八幡宮山上", "CB02")

    topology = {"operator_id": "Keihan", "segments": []}
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

    total = sum(len(s[2]) for s in SEGMENTS)
    print(f"🎉 topology.json：{len(SEGMENTS)} 段、{len(NAME_TO_ID)} 個不重複站（含交會站）、列出 {total} 站次")
    for seg_id, seg_name, stations in SEGMENTS:
        print(f"   {seg_id:18s} {seg_name:8s} {len(stations)} 站  {stations[0][0]}→{stations[-1][0]}")


if __name__ == "__main__":
    main()
