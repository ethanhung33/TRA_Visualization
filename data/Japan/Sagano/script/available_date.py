#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
available_date.py — 嵯峨野観光鉄道の営業日リスト生成

定期運休：毎週水曜（行楽期・祝日除くが、ここでは簡易化して全水曜を運休扱い）+
          冬季（12/30〜2 月末）全休。
今日から約 13 ヶ月分の営業日を json/available_dates.json に書き出す。
※ 祝日に当たる水曜の特別運行などの細かな例外は反映しない近似。
"""
import sys
import json
import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

JSON_DIR = Path(__file__).parent.parent / "json"

WEDNESDAY = 2  # Monday=0 ... Wednesday=2


def is_winter(d):
    """冬季運休：12/30〜2 月末（年跨ぎ）。"""
    if d.month == 12 and d.day >= 30:
        return True
    if d.month in (1, 2):
        return True
    return False


def is_operating(d):
    if d.weekday() == WEDNESDAY:
        return False
    if is_winter(d):
        return False
    return True


def main():
    today = datetime.date.today()
    end = today + datetime.timedelta(days=400)
    dates = []
    d = today
    while d <= end:
        if is_operating(d):
            dates.append(d.isoformat())
        d += datetime.timedelta(days=1)

    with open(JSON_DIR / "available_dates.json", "w", encoding="utf-8") as f:
        json.dump(dates, f, ensure_ascii=False, indent=0)
    print(f"🎉 available_dates.json：{len(dates)} 営業日（{dates[0]} 〜 {dates[-1]}）")


if __name__ == "__main__":
    main()
