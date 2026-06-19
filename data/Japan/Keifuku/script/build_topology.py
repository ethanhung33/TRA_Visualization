#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_topology.py — 京福電気鉄道（嵐電 / Randen）拓樸建構

2 segment：
  arashiyama_main 嵐山本線（四条大宮→嵐山、13 駅）
  kitano_line     北野線（北野白梅町→帷子ノ辻、10 駅）
交會站：帷子ノ辻（RD08）— 両線で同一 station id を共用（km は各線で異なる）。

里程來源：日本語Wikipedia 各線「駅一覧」の営業キロ。
站名は navitime 正規化後（〔嵐電〕・(京都府) 等の括號を除去）に合わせる。
"""
import sys
import json
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 嵐山本線：四条大宮→嵐山（13 駅、帷子ノ辻=RD08 は北野線との交會站）
ARASHIYAMA = [
    ("四条大宮",     0.0, "RD01"),
    ("西院",         1.4, "RD02"),
    ("西大路三条",   2.0, "RD03"),
    ("山ノ内",       2.8, "RD04"),
    ("嵐電天神川",   3.7, "RD05"),
    ("蚕ノ社",       3.9, "RD06"),
    ("太秦広隆寺",   4.4, "RD07"),
    ("帷子ノ辻",     5.2, "RD08"),
    ("有栖川",       5.7, "RD09"),
    ("車折神社",     6.2, "RD10"),
    ("鹿王院",       6.5, "RD11"),
    ("嵐電嵯峨",     6.9, "RD12"),
    ("嵐山",         7.2, "RD13"),
]

# 北野線：北野白梅町→帷子ノ辻（10 駅、帷子ノ辻=RD08 は嵐山本線と共用）
KITANO = [
    ("北野白梅町",                       0.0, "KT01"),
    ("等持院・立命館大学衣笠キャンパス前", 0.7, "KT02"),
    ("龍安寺",                           0.9, "KT03"),
    ("妙心寺",                           1.3, "KT04"),
    ("御室仁和寺",                       1.7, "KT05"),
    ("宇多野",                           2.1, "KT06"),
    ("鳴滝",                             2.6, "KT07"),
    ("常盤",                             2.9, "KT08"),
    ("撮影所前",                         3.5, "KT09"),
    ("帷子ノ辻",                         3.8, "RD08"),
]

SEGMENTS = [
    ("arashiyama_main", "嵐山本線", ARASHIYAMA),
    ("kitano_line",     "北野線",   KITANO),
]


def main():
    topology = {"operator_id": "Keifuku", "segments": []}
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
        print(f"   {seg_id:16s} {seg_name:6s} {len(stations):2d} 駅  {stations[0][0]}→{stations[-1][0]}")


if __name__ == "__main__":
    main()
