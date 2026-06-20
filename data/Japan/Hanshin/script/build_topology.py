#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_topology.py — 阪神電気鉄道 拓樸建構

3 segment：
  main_line     本線（大阪梅田→元町、33 駅）
  namba_line    なんば線（大阪難波→大物、10 駅）
  mukogawa_line 武庫川線（武庫川→武庫川団地前、4 駅）
交會站：
  大物（HS08）  本線 ↔ なんば線
  武庫川（HS12）本線 ↔ 武庫川線

里程來源：日本語Wikipedia 各線「駅一覧」の営業キロ。
站名は navitime 正規化後（(阪神線)・〔近鉄・阪神線〕・(兵庫県) 等の括號除去）に合わせる。
"""
import sys
import json
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 本線：大阪梅田→元町（33 駅）
MAIN = [
    ("大阪梅田", 0.0, "HS01"), ("福島", 1.1, "HS02"), ("野田", 2.3, "HS03"),
    ("淀川", 3.3, "HS04"), ("姫島", 4.4, "HS05"), ("千船", 5.9, "HS06"),
    ("杭瀬", 6.8, "HS07"), ("大物", 8.0, "HS08"), ("尼崎", 8.9, "HS09"),
    ("出屋敷", 10.1, "HS10"), ("尼崎センタープール前", 10.8, "HS11"),
    ("武庫川", 12.0, "HS12"), ("鳴尾・武庫川女子大前", 13.2, "HS13"),
    ("甲子園", 14.1, "HS14"), ("久寿川", 14.8, "HS15"), ("今津", 15.4, "HS16"),
    ("西宮", 16.7, "HS17"), ("香櫨園", 17.8, "HS18"), ("打出", 19.0, "HS19"),
    ("芦屋", 20.2, "HS20"), ("深江", 21.5, "HS21"), ("青木", 22.6, "HS22"),
    ("魚崎", 23.8, "HS23"), ("住吉", 24.6, "HS24"), ("御影", 25.1, "HS25"),
    ("石屋川", 25.7, "HS26"), ("新在家", 26.6, "HS27"), ("大石", 27.6, "HS28"),
    ("西灘", 28.2, "HS29"), ("岩屋", 28.8, "HS30"), ("春日野道", 29.9, "HS31"),
    ("神戸三宮", 31.2, "HS32"), ("元町", 32.1, "HS33"),
]

# なんば線：大阪難波→大物（10 駅、大物=本線と共用）
NAMBA = [
    ("大阪難波", 0.0, "NB01"), ("桜川", 1.1, "NB02"), ("ドーム前", 1.9, "NB03"),
    ("九条", 2.5, "NB04"), ("西九条", 3.8, "NB05"), ("千鳥橋", 4.6, "NB06"),
    ("伝法", 5.3, "NB07"), ("福", 6.8, "NB08"), ("出来島", 7.8, "NB09"),
    ("大物", 9.2, "HS08"),
]

# 武庫川線：武庫川→武庫川団地前（4 駅、武庫川=本線と共用）
MUKOGAWA = [
    ("武庫川", 0.0, "HS12"), ("東鳴尾", 0.7, "MK01"),
    ("洲先", 1.1, "MK02"), ("武庫川団地前", 1.7, "MK03"),
]

SEGMENTS = [
    ("main_line",     "本線",     MAIN),
    ("namba_line",    "なんば線", NAMBA),
    ("mukogawa_line", "武庫川線", MUKOGAWA),
]


def main():
    topology = {"operator_id": "Hanshin", "segments": []}
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
        print(f"   {seg_id:14s} {seg_name:8s} {len(stations):2d} 駅  {stations[0][0]}→{stations[-1][0]}")


if __name__ == "__main__":
    main()
