#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
station_name.py — 站名正規化（build_topology / timetable / convert_timetable 共用）

必須三邊共用同一套規則，否則維基（拓樸）與官方時刻表的站名對不上，該站的停靠
就會被整批丟掉。實際踩到的案例：日光線「文挾」——官方時刻表用舊字體「挾」，
維基條目用新字體「挟」，NFKC 不會轉換，導致該站 40 班車全部落空。
"""
import re
import unicodedata

# 舊字體 → 新字體（NFKC 不處理這類異體字）
KANJI_VARIANTS = str.maketrans({
    "挾": "挟",   # 文挾 → 文挟（日光線）
    "邊": "辺", "邉": "辺", "澤": "沢", "濱": "浜", "瀧": "滝", "嶋": "島",
    "舘": "館", "眞": "真", "峯": "峰", "圓": "円", "學": "学", "榮": "栄",
    "淸": "清", "龍": "竜", "內": "内", "壽": "寿", "驛": "駅", "槇": "槙",
    "曾": "曽", "齊": "斉", "齋": "斎", "凉": "涼", "堯": "尭",
})


def clean_station_name(text):
    """站名正規化：NFKC → 去括號註記/註腳 → 砍掉「駅」及其後記號 → 舊字體轉新字體。

    維基車站表的站名常帶記號（無空白分隔）：
      '東京駅山区' → 東京（山区＝特定都区市内記号）
      '川崎駅浜'   → 川崎（浜＝横浜市内）
      '塩尻駅◇'   → 塩尻（◇◆■＝接續/電化圖例）
    JR 東日本無任何站名內含「駅」字，故以「駅」切斷最安全。
    """
    t = unicodedata.normalize("NFKC", str(text)).strip()
    t = re.sub(r"[(（〔【\[].*?[)）〕】\]]", "", t)
    t = re.sub(r"[†*※‡#]", "", t)
    t = t.split("駅")[0]
    t = t.split()[0] if t.split() else ""
    return t.strip().translate(KANJI_VARIANTS)
