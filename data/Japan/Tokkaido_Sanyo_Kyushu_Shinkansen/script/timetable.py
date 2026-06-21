#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
timetable.py — 東海道・山陽・九州・西九州新幹線 navitime 爬蟲（DAILY_FILE）

旧 timtable.py（JR Odekake）を置き換える navitime 版。topology.json は既存を再利用
（東海道+山陽+九州 は 新大阪(TOK17)・博多(SAN18) を共用 id で接続、西九州は独立）。

新幹線は毎日ダイヤが異なる → DAILY_FILE。navitime の listing プールは
「今日・明日・次の土曜」等の数日分を返す（連続とは限らない）。各 stopCode の
data-date を集合で蓄積し、**日付ごとに 1 ファイル** timetable_YYYYMMDD.json を出力。
各 code の stops は 1 回だけ取得し、その code が走る全日付のファイルへ振り分ける。
種別は data-name（のぞみ/ひかり/こだま/みずほ/さくら/つばめ/かもめ…）。
"""
import sys
import json
import time
import re
import unicodedata
import argparse
from pathlib import Path
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

JSON_DIR = Path(__file__).parent.parent / "json"

# 4 新幹線（navitime）
LINE_TOKAIDO     = "00000110"
LINE_SANYO       = "00000069"
LINE_KYUSHU      = "00001017"
LINE_NISHIKYUSHU = "00001278"
SCAN_LINES = [LINE_TOKAIDO, LINE_SANYO, LINE_KYUSHU, LINE_NISHIKYUSHU]

BASE = "https://www.navitime.co.jp"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
SLEEP = 1.1

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def norm_name(name):
    name = unicodedata.normalize("NFKC", name).strip()
    name = re.sub(r"[(（〔【\[].*?[)）〕】\]]", "", name)
    name = name.replace("駅", "").strip()
    return name


def get_soup(url, retries=3):
    for attempt in range(retries):
        try:
            time.sleep(SLEEP)
            r = SESSION.get(url, timeout=20)
            r.raise_for_status()
            return BeautifulSoup(r.text, "html.parser")
        except Exception:
            if attempt == retries - 1:
                return None
            time.sleep(3)
    return None


def build_scan_targets():
    seen_nodes = {}
    targets = []
    for line in SCAN_LINES:
        soup = get_soup(f"{BASE}/diagram/stationList?lineId={line}")
        if not soup:
            continue
        for a in soup.select("a[href*='node=']"):
            m = re.search(r"node=([0-9A-Za-z]+)", a.get("href", ""))
            if not m:
                continue
            node = m.group(1)
            if node in seen_nodes:
                continue
            seen_nodes[node] = True
            targets.append((norm_name(a.get_text(strip=True)), node, line))
    return targets


def scan_station(node, scan_line, date_str=None):
    """{stopCode: (種別, code_lineId, ref_node, set(運行日))}。
    date_str を指定すると `&time=YYYY-MM-DD` でその日のダイヤを取得（navitime は
    listing の time= パラメータで任意日付に対応。year/month/day や searchDate は無視される）。"""
    found = {}
    tparam = f"&time={date_str}" if date_str else ""
    for updown in [0, 1]:
        url = f"{BASE}/diagram/timetable?node={node}&lineId={scan_line}&updown={updown}{tparam}"
        soup = get_soup(url)
        if not soup:
            continue
        for li in soup.select("li.time-frame"):
            a = li.select_one("a[href*='/diagram/stops/']")
            if not a:
                continue
            m = re.search(r"/diagram/stops/([^/]+)/([^/]+)/", a.get("href", ""))
            if not m:
                continue
            code_line, stop_code = m.group(1), m.group(2)
            dd = li.get("data-date", "")
            if stop_code not in found:
                found[stop_code] = (li.get("data-name") or "", code_line, node, set())
            if dd:
                found[stop_code][3].add(dd)
    return found


def fetch_stops(stop_code, ttype, code_line, ref_node, date_tuple):
    y, mth, d = date_tuple
    url = f"{BASE}/diagram/stops/{code_line}/{stop_code}/?node={ref_node}&year={y}&month={mth:02d}&day={d:02d}"
    soup = get_soup(url)
    if not soup:
        return None
    # 列車愛称＋号数（旅客向け表示用）。stops 頁の見出しに「のぞみ1号」等がある。
    train_name = None
    h2 = soup.select_one("h2")
    htext = h2.get_text(strip=True) if h2 else soup.get_text(" ", strip=True)
    mnum = re.search(r"(\d+)\s*号", htext)
    if mnum:
        train_name = f"{ttype}{mnum.group(1)}号"
    stops = []
    for row in soup.select("li.stops-list"):
        name_el = row.select_one("dt.station-name")
        time_el = row.select_one("dd.time, dd.from-to-time")
        if not name_el or not time_el:
            continue
        name = norm_name(name_el.get_text(strip=True))
        ttext = time_el.get_text(" ", strip=True)
        arr = dep = None
        am = re.search(r"(\d{1,2}):(\d{2})\s*着", ttext)
        dm = re.search(r"(\d{1,2}):(\d{2})\s*発", ttext)
        if am:
            arr = int(am.group(1)) * 60 + int(am.group(2))
        if dm:
            dep = int(dm.group(1)) * 60 + int(dm.group(2))
        if arr is None and dep is None:
            tm = re.search(r"(\d{1,2}):(\d{2})", ttext)
            if tm:
                arr = dep = int(tm.group(1)) * 60 + int(tm.group(2))
        if arr is None:
            arr = dep
        if dep is None:
            dep = arr
        if arr is None:
            continue
        stops.append({"name": name, "arr": arr, "dep": dep})
    if len(stops) < 2:
        return None
    last = -1
    for st in stops:
        if st["arr"] < last:
            st["arr"] += 1440
        if st["dep"] < st["arr"]:
            st["dep"] += 1440
        last = st["dep"]
    return {"code": stop_code, "type": ttype, "name": train_name, "stops": stops}


def run(max_workers=3, dates=None):
    print("🗺️  掃描目標を構築中…", flush=True)
    targets = build_scan_targets()
    print(f"   {len(targets)} 駅を取得", flush=True)

    # dates 未指定なら listing の自然プール（time= なし）を 1 回だけ掃描
    scan_dates = dates if dates else [None]

    print(f"🔍 [第一段階] {len(targets)} 駅 × {len(scan_dates)} 日 を掃描（time= で各日付）…", flush=True)
    all_codes = {}
    for di, dstr in enumerate(scan_dates):
        label = dstr or "(自然プール)"
        for i, (name, node, scan_line) in enumerate(targets):
            codes = scan_station(node, scan_line, dstr)
            for c, info in codes.items():
                if c not in all_codes:
                    all_codes[c] = info
                else:
                    all_codes[c][3].update(info[3])
        print(f"   [{di+1}/{len(scan_dates)}] {label} 掃描完了（累計 code {len(all_codes)}）", flush=True)

    date_count = Counter()
    for info in all_codes.values():
        for dd in info[3]:
            date_count[dd] += 1
    print(f"✅ {len(all_codes)} 個の stopCode。日付別班数: {dict(sorted(date_count.items()))}", flush=True)
    if not date_count:
        print("⚠️  班次なし", flush=True)
        return
    # dates 指定時はその全日付を出力、未指定時は最多日の 50% 未満の端日付を除外
    if dates:
        use_dates = sorted(d for d in date_count if d in set(dates))
    else:
        maxc = max(date_count.values())
        use_dates = sorted(d for d, c in date_count.items() if c >= maxc * 0.5)
    print(f"📅 出力対象日: {use_dates}", flush=True)

    print(f"⚡ [第二段階] {len(all_codes)} 班の停車順序をダウンロード（各 code 1 回）…", flush=True)
    fetched = {}  # code -> train dict
    none_count = 0

    def _one(c):
        ty, line, node, dates = all_codes[c]
        y, m, d = map(int, sorted(dates)[0].split("-"))
        return c, fetch_stops(c, ty, line, node, (y, m, d))

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = [ex.submit(_one, c) for c in all_codes]
        done = 0
        for f in as_completed(futs):
            done += 1
            c, res = f.result()
            if res:
                fetched[c] = res
            else:
                none_count += 1
            if done % 200 == 0:
                print(f"   {done}/{len(futs)}…（失敗 {none_count}）", flush=True)
    print(f"   取得 {len(fetched)}、失敗 {none_count}", flush=True)

    out_dir = JSON_DIR / "timetable"
    out_dir.mkdir(parents=True, exist_ok=True)
    written_dates = []
    for dd in use_dates:
        # その日に走る code を集め、内容簽章で去重（跨 lineId 重複対策）
        deduped = {}
        for c, info in all_codes.items():
            if dd not in info[3] or c not in fetched:
                continue
            r = fetched[c]
            sig = (r["type"], r["stops"][0]["name"], r["stops"][0]["dep"],
                   r["stops"][-1]["name"], len(r["stops"]))
            deduped.setdefault(sig, r)
        trains = sorted(deduped.values(), key=lambda r: r["stops"][0]["dep"])
        fname = f"raw_{dd.replace('-', '')}.json"
        with open(JSON_DIR / fname, "w", encoding="utf-8") as f:
            f.write("[\n")
            for i, r in enumerate(trains):
                f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) +
                        (",\n" if i < len(trains) - 1 else "\n"))
            f.write("]\n")
        written_dates.append(dd)
        print(f"🎉 {dd}: {len(trains)} 班 → {fname}", flush=True)

    with open(JSON_DIR / "_scraped_dates.json", "w", encoding="utf-8") as f:
        json.dump(written_dates, f, ensure_ascii=False)
    print(f"✅ 完了。{len(written_dates)} 日分。", flush=True)


def main():
    import datetime
    global SLEEP
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--sleep", type=float, default=SLEEP)
    ap.add_argument("--start", help="開始日 YYYY-MM-DD（省略時は今日）")
    ap.add_argument("--days", type=int, default=0,
                    help="開始日から何日分を time= で逐日掃描するか（0=自然プールのみ）")
    ap.add_argument("--dates", help="カンマ区切りで明示指定 YYYY-MM-DD,YYYY-MM-DD…")
    args = ap.parse_args()
    SLEEP = args.sleep

    dates = None
    if args.dates:
        dates = [d.strip() for d in args.dates.split(",") if d.strip()]
    elif args.days > 0:
        start = datetime.date.fromisoformat(args.start) if args.start else datetime.date.today()
        dates = [(start + datetime.timedelta(days=i)).isoformat() for i in range(args.days)]
    run(max_workers=args.workers, dates=dates)


if __name__ == "__main__":
    main()
