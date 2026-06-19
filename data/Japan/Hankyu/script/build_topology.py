#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_topology.py — 阪急電鐵 全 11 segment 拓樸建構

里程來源：日本維基百科各線「駅一覧」の営業キロ。

11 條 segment，交會站（junction）在多個 segment 共用「同一 station id」但各有自己的 km：
  umeda_juso（共用幹線） 大阪梅田(HK01)〜中津(HK02)〜十三(HK03)：神戸・宝塚・京都三線共用
  十三(HK03)    umeda_juso と 神戸本線・宝塚本線・京都本線 の境界（全線共用）
  塚口(KO03)    神戸本線 ↔ 伊丹線
  西宮北口(KO05) 神戸本線 ↔ 今津線（南北）
  夙川(KO06)    神戸本線 ↔ 甲陽線
  宝塚(TZ16)    宝塚本線 ↔ 今津線（北）
  石橋阪大前(TZ08) 宝塚本線 ↔ 箕面線
  淡路(KY02)    京都本線 ↔ 千里線
  桂(KY20)      京都本線 ↔ 嵐山線
"""
import sys
import json
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ─── 各線駅一覧 (駅名, 営業キロ) ─────────────────────────────────────
# 三線共用区間：大阪梅田→十三（3 駅）
UMEDA_JUSO = [
    ("大阪梅田", 0.0), ("中津", 0.9), ("十三", 2.4),
]

# 神戸本線：十三→神戸三宮（14 駅、十三は umeda_juso との境界）
KOBE = [
    ("十三", 2.4), ("神崎川", 4.1),
    ("園田", 7.2), ("塚口", 10.2), ("武庫之荘", 12.3), ("西宮北口", 15.6),
    ("夙川", 18.3), ("芦屋川", 21.0), ("岡本", 23.4), ("御影", 25.6),
    ("六甲", 27.4), ("王子公園", 29.2), ("春日野道", 30.7), ("神戸三宮", 32.3),
]

# 宝塚本線：十三→宝塚（17 駅、十三は umeda_juso との境界）
TAKARAZUKA = [
    ("十三", 2.4), ("三国", 4.4),
    ("庄内", 6.0), ("服部天神", 7.5), ("曽根", 8.7), ("岡町", 9.5),
    ("豊中", 10.5), ("蛍池", 11.9), ("石橋阪大前", 13.5), ("池田", 15.9),
    ("川西能勢口", 17.2), ("雲雀丘花屋敷", 18.2), ("山本", 19.7),
    ("中山観音", 21.5), ("売布神社", 22.4), ("清荒神", 23.3), ("宝塚", 24.5),
]

# 京都本線：十三→京都河原町（27 駅、十三は umeda_juso との境界）
# km は大阪梅田からの営業キロ（十三=2.4km 起算で整合）
KYOTO = [
    ("十三", 2.4), ("南方", 4.3), ("崇禅寺", 5.0), ("淡路", 6.6), ("上新庄", 8.7),
    ("相川", 9.6), ("正雀", 11.8), ("摂津市", 13.3), ("南茨木", 15.3),
    ("茨木市", 17.2), ("総持寺", 18.6), ("富田", 19.7), ("高槻市", 23.0),
    ("上牧", 27.3), ("水無瀬", 28.1), ("大山崎", 30.1), ("西山天王山", 32.6),
    ("長岡天神", 34.1), ("西向日", 36.0), ("東向日", 37.4), ("洛西口", 38.7),
    ("桂", 40.4), ("西京極", 42.5), ("西院", 44.3), ("大宮", 45.7),
    ("烏丸", 46.8), ("京都河原町", 47.7),
]

# 今津線北：宝塚→西宮北口（8 駅）
IMAZU_NORTH = [
    ("宝塚", 0.0), ("宝塚南口", 0.9), ("逆瀬川", 1.8), ("小林", 2.8),
    ("仁川", 4.5), ("甲東園", 5.4), ("門戸厄神", 6.4), ("西宮北口", 7.7),
]

# 今津線南：西宮北口→今津（3 駅）
IMAZU_SOUTH = [
    ("西宮北口", 0.0), ("阪神国道", 0.7), ("今津", 1.6),
]

# 伊丹線：塚口→伊丹（4 駅）
ITAMI = [
    ("塚口", 0.0), ("稲野", 1.4), ("新伊丹", 2.2), ("伊丹", 3.1),
]

# 甲陽線：夙川→甲陽園（3 駅）
KOYO = [
    ("夙川", 0.0), ("苦楽園口", 0.9), ("甲陽園", 2.2),
]

# 千里線：天神橋筋六丁目→北千里（11 駅、淡路は京都本線と共用）
SENRI = [
    ("天神橋筋六丁目", 0.0), ("柴島", 2.2), ("淡路", 3.5), ("下新庄", 4.4),
    ("吹田", 6.0), ("豊津", 6.9), ("関大前", 7.8), ("千里山", 8.6),
    ("南千里", 10.2), ("山田", 11.6), ("北千里", 13.6),
]

# 箕面線：石橋阪大前→箕面（4 駅）
MINOH = [
    ("石橋阪大前", 0.0), ("桜井", 1.6), ("牧落", 2.7), ("箕面", 4.0),
]

# 嵐山線：桂→嵐山（4 駅）
ARASHIYAMA = [
    ("桂", 0.0), ("上桂", 1.4), ("松尾大社", 2.8), ("嵐山", 4.1),
]

SEGMENTS = [
    ("umeda_juso",      "大阪梅田〜十三（三線共用）", UMEDA_JUSO),
    ("kobe_main",       "神戸本線",   KOBE),
    ("takarazuka_main", "宝塚本線",   TAKARAZUKA),
    ("kyoto_main",      "京都本線",   KYOTO),
    ("imazu_north",     "今津線（北）", IMAZU_NORTH),
    ("imazu_south",     "今津線（南）", IMAZU_SOUTH),
    ("itami_line",      "伊丹線",     ITAMI),
    ("koyo_line",       "甲陽線",     KOYO),
    ("senri_line",      "千里線",     SENRI),
    ("minoh_line",      "箕面線",     MINOH),
    ("arashiyama_line", "嵐山線",     ARASHIYAMA),
]

# ─── 駅 ID 指派 ──────────────────────────────────────────────────────
NAME_TO_ID: dict[str, str] = {}


def assign(name: str, sid: str):
    if name not in NAME_TO_ID:
        NAME_TO_ID[name] = sid


def main():
    # 三幹線共用区間（umeda_juso segment）
    assign("大阪梅田", "HK01")
    assign("中津",     "HK02")
    assign("十三",     "HK03")  # umeda_juso と各本線の境界

    # 神戸本線 固有駅（十三以降）
    for name, prefix_n in [
        ("神崎川", "KO01"), ("園田", "KO02"), ("塚口", "KO03"),
        ("武庫之荘", "KO04"), ("西宮北口", "KO05"), ("夙川", "KO06"),
        ("芦屋川", "KO07"), ("岡本", "KO08"), ("御影", "KO09"),
        ("六甲", "KO10"), ("王子公園", "KO11"), ("春日野道", "KO12"),
        ("神戸三宮", "KO13"),
    ]:
        assign(name, prefix_n)

    # 宝塚本線 固有駅（十三以降）
    for name, sid in [
        ("三国", "TZ01"), ("庄内", "TZ02"), ("服部天神", "TZ03"),
        ("曽根", "TZ04"), ("岡町", "TZ05"), ("豊中", "TZ06"),
        ("蛍池", "TZ07"), ("石橋阪大前", "TZ08"), ("池田", "TZ09"),
        ("川西能勢口", "TZ10"), ("雲雀丘花屋敷", "TZ11"), ("山本", "TZ12"),
        ("中山観音", "TZ13"), ("売布神社", "TZ14"), ("清荒神", "TZ15"),
        ("宝塚", "TZ16"),
    ]:
        assign(name, sid)

    # 京都本線 固有駅（十三=HK03 以降、南方から）
    for name, sid in [
        ("南方", "KY01"), ("崇禅寺", "KY01A"), ("淡路", "KY02"), ("上新庄", "KY03"),
        ("相川", "KY04"), ("正雀", "KY05"), ("摂津市", "KY06"),
        ("南茨木", "KY07"), ("茨木市", "KY08"), ("総持寺", "KY09"),
        ("富田", "KY10"), ("高槻市", "KY11"), ("上牧", "KY12"),
        ("水無瀬", "KY13"), ("大山崎", "KY14"), ("西山天王山", "KY15"),
        ("長岡天神", "KY16"), ("西向日", "KY17"), ("東向日", "KY18"),
        ("洛西口", "KY19"), ("桂", "KY20"), ("西京極", "KY21"),
        ("西院", "KY22"), ("大宮", "KY23"), ("烏丸", "KY24"),
        ("京都河原町", "KY25"),
    ]:
        assign(name, sid)

    # 今津線 固有駅（宝塚=TZ16、西宮北口=KO05 は既存）
    for name, sid in [
        ("宝塚南口", "IM01"), ("逆瀬川", "IM02"), ("小林", "IM03"),
        ("仁川", "IM04"), ("甲東園", "IM05"), ("門戸厄神", "IM06"),
        ("阪神国道", "IM07"), ("今津", "IM08"),
    ]:
        assign(name, sid)

    # 伊丹線 固有駅（塚口=KO03 は既存）
    for name, sid in [
        ("稲野", "IT01"), ("新伊丹", "IT02"), ("伊丹", "IT03"),
    ]:
        assign(name, sid)

    # 甲陽線 固有駅（夙川=KO06 は既存）
    for name, sid in [
        ("苦楽園口", "SY01"), ("甲陽園", "SY02"),
    ]:
        assign(name, sid)

    # 千里線 固有駅（淡路=KY02 は既存）
    for name, sid in [
        ("天神橋筋六丁目", "SE01"), ("柴島", "SE02"),
        ("下新庄", "SE03"), ("吹田", "SE04"), ("豊津", "SE05"),
        ("関大前", "SE06"), ("千里山", "SE07"), ("南千里", "SE08"),
        ("山田", "SE09"), ("北千里", "SE10"),
    ]:
        assign(name, sid)

    # 箕面線 固有駅（石橋阪大前=TZ08 は既存）
    for name, sid in [
        ("桜井", "MN01"), ("牧落", "MN02"), ("箕面", "MN03"),
    ]:
        assign(name, sid)

    # 嵐山線 固有駅（桂=KY20 は既存）
    for name, sid in [
        ("上桂", "AS01"), ("松尾大社", "AS02"), ("嵐山", "AS03"),
    ]:
        assign(name, sid)

    # ─── topology.json 出力 ───────────────────────────────────────────
    topology = {"operator_id": "Hankyu", "segments": []}
    for seg_id, seg_name, stations in SEGMENTS:
        topology["segments"].append({
            "id": seg_id,
            "name": seg_name,
            "stations": [
                {"id": NAME_TO_ID[n], "name": n, "km": round(km, 1)}
                for n, km in stations
            ],
        })

    json_dir = Path(__file__).parent.parent / "json"
    json_dir.mkdir(parents=True, exist_ok=True)
    with open(json_dir / "topology.json", "w", encoding="utf-8") as f:
        json.dump(topology, f, ensure_ascii=False, indent=2)
    with open(json_dir / "station_name_to_id.json", "w", encoding="utf-8") as f:
        json.dump(NAME_TO_ID, f, ensure_ascii=False, indent=2)

    total = sum(len(s[2]) for s in SEGMENTS)
    print(f"🎉 topology.json：{len(SEGMENTS)} 段、{len(NAME_TO_ID)} 個不重複站、列出 {total} 站次")
    for seg_id, seg_name, stations in SEGMENTS:
        print(f"   {seg_id:20s} {seg_name:10s} {len(stations):2d} 駅  {stations[0][0]}→{stations[-1][0]}")


if __name__ == "__main__":
    main()
