#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_freshness.py — 檢查各路線時刻表資料的新鮮度

回答「哪些路線該重跑了？」不需要連網，純讀本地 JSON。

用法:
    py tools/check_freshness.py
    py tools/check_freshness.py --stale-days 14   # 自訂「過舊」門檻

判斷方式依 setting.json 的 data_fetch_strategy 而異：
    DAILY_FILE   逐日檔 → 看 available_dates.json 還剩幾天可用（剩 0 天＝前端等於沒資料）
    其他          固定檔 → 看時刻表檔案的修改時間距今幾天

退出碼: 0 = 全部正常，1 = 有路線需要更新
"""
import re
import sys
import json
import argparse
import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def iter_systems():
    """從 data/global.json 取出所有 is_active 的系統 (country_id, system_id, 中文名)。"""
    g = load_json(ROOT / "data" / "global.json") or {}
    for country in g.get("countries", []):
        groups = country.get("groups") or [{"systems": country.get("systems", [])}]
        for group in groups:
            for sysinfo in group.get("systems", []):
                if sysinfo.get("is_active"):
                    yield country["id"], sysinfo["id"], sysinfo.get("chinese_name", "")


def route_keys_from_update_script():
    """從 update.ps1 解析 {系統目錄名: 路線代號}，避免代號在兩處各記一份而走鐘。"""
    try:
        text = (ROOT / "update.ps1").read_text(encoding="utf-8")
    except Exception:
        return {}
    mapping = {}
    # 每個路線區塊以 Key = "xxx" 開頭，後面 Steps 內含 data/<國家>/<系統>/script/...
    for block in re.split(r'@\{\s*Key\s*=', text)[1:]:
        key = re.match(r'\s*"([^"]+)"', block)
        path = re.search(r'data/[^/]+/([^/]+)/script/', block)
        if key and path:
            mapping[path.group(1)] = key.group(1)
    return mapping


def newest_timetable_mtime(json_dir):
    files = list((json_dir / "timetable").glob("*.json"))
    if not files:
        return None
    newest = max(f.stat().st_mtime for f in files)
    return datetime.date.fromtimestamp(newest)


def check(country, system, name, stale_days, today, route_keys):
    json_dir = ROOT / "data" / country / system / "json"
    setting = load_json(json_dir / "setting.json") or {}
    strategy = setting.get("data_fetch_strategy", "?")
    key = route_keys.get(system)
    label = f"{name or system} [{key or system + ' ← update.cmd 未涵蓋'}]"

    if strategy == "DAILY_FILE":
        dates = load_json(json_dir / "available_dates.json") or []
        future = sorted(d for d in dates if d >= today)
        if not future:
            last = max(dates) if dates else "無"
            return "EXPIRED", label, strategy, f"可用日期 0 天（最後 {last}）→ 前端無資料可看", key
        remain = len(future)
        status = "STALE" if remain <= 7 else "OK"
        return status, label, strategy, f"還有 {remain} 天可用（到 {max(future)}）", key

    # WEEKEND_FILE / SINGLE_FILE 等固定檔：以檔案時間判斷
    mtime = newest_timetable_mtime(json_dir)
    if mtime is None:
        return "EXPIRED", label, strategy, "找不到任何時刻表檔", key
    age = (datetime.date.fromisoformat(today) - mtime).days
    status = "STALE" if age >= stale_days else "OK"
    return status, label, strategy, f"時刻表檔案為 {mtime}（{age} 天前）", key


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stale-days", type=int, default=30,
                    help="固定檔路線超過幾天未更新視為過舊（預設 30）")
    args = ap.parse_args()

    today = datetime.date.today().isoformat()
    route_keys = route_keys_from_update_script()
    print(f"📅 今天：{today}\n")

    rows = [check(c, s, n, args.stale_days, today, route_keys)
            for c, s, n in iter_systems()]
    order = {"EXPIRED": 0, "STALE": 1, "OK": 2}
    rows.sort(key=lambda r: order.get(r[0], 3))

    icon = {"EXPIRED": "❌", "STALE": "⚠️ ", "OK": "✅"}
    for status, label, strategy, detail, _ in rows:
        print(f"{icon.get(status, '  ')} {label:<44} {strategy:<14} {detail}")

    bad = [r for r in rows if r[0] != "OK"]
    print()
    if bad:
        keys = [r[4] for r in bad if r[4]]
        print(f"需要更新的路線共 {len(bad)} 條。")
        if keys:
            print(f"    update.cmd -Only {' '.join(keys)}")
            print("（提醒：navitime 系路線建議分批跑，連續密集重跑會被限流擋下）")
        if len(keys) < len(bad):
            print("    ※ 其餘路線 update.cmd 未涵蓋，需手動處理（如 JR 西日本缺爬蟲）")
        return 1
    print("全部路線資料都在有效期內 🎉")
    return 0


if __name__ == "__main__":
    sys.exit(main())
