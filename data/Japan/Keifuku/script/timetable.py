#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
timetable.py — 京福電気鉄道（嵐電）navitime 爬蟲（嵐山本線 + 北野線）

平日/土休で班数が僅かに異なる（北野線）ため、平日/土休の 2 ファイルを出力する。
navitime の timetable listing は「サーバ当日から約 4 日」のプールを返し URL の date は無視されるため、
各班 <li.time-frame> の data-date の曜日で平日/土休に分桶し、各カテゴリの「最多班次の代表日」を採用。
（水〜日に実行すると 4 日窗口に平日・週末が両方含まれる。）

種別は data-name（普通のみ）。方向は stops 序列自身で判断（updown は当てにならない）。
商業服務：限速 sleep≥1s、低併発、個人利用のみ。
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

# 嵐電 2 路線（navitime companyId: 00000040）
LINE_ARASHIYAMA = "00000300"  # 嵐山本線
LINE_KITANO     = "00000299"  # 北野線
SCAN_LINES = [LINE_ARASHIYAMA, LINE_KITANO]

BASE = "https://www.navitime.co.jp"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
SLEEP = 1.1

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def norm_name(name):
    """站名正規化：NFKC、去各式括號後綴與「駅」字。"""
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
    """全路線の stationList から掃描目標 [(駅名, node, lineId)] を構築。
    同一 node は最初に発見した lineId で登録（seen_nodes 去重）。"""
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


def scan_station(node, scan_line):
    """一駅の時刻表を上下両方向取得し {stopCode: (種別, code_lineId, ref_node, data_date)} を返す。"""
    found = {}
    for updown in [0, 1]:
        url = f"{BASE}/diagram/timetable?node={node}&lineId={scan_line}&updown={updown}"
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
            if stop_code in found:
                continue
            data_date = li.get("data-date", "")
            ttype = li.get("data-name") or "普通"
            found[stop_code] = (ttype, code_line, node, data_date)
    return found


def fetch_stops(stop_code, ttype, code_line, ref_node, date_tuple):
    """単一列車の stops ページを取得し {code, type, stops:[{name, arr, dep}]} を返す。"""
    y, mth, d = date_tuple
    url = f"{BASE}/diagram/stops/{code_line}/{stop_code}/?node={ref_node}&year={y}&month={mth:02d}&day={d:02d}"
    soup = get_soup(url)
    if not soup:
        return None
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
    # 跨夜処理（嵐電は深夜なしだが念のため）
    last = -1
    for st in stops:
        if st["arr"] < last:
            st["arr"] += 1440
        if st["dep"] < st["arr"]:
            st["dep"] += 1440
        last = st["dep"]
    return {"code": stop_code, "type": ttype, "stops": stops}


def _date_tuple(s):
    y, m, d = s.split("-")
    return (int(y), int(m), int(d))


def _fetch_bucket(codes, out_name, max_workers):
    print(f"⚡ [第二段階] {out_name}：{len(codes)} 班の停車順序をダウンロード…", flush=True)
    fetched, none_count = [], 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(fetch_stops, c, info[0], info[1], info[2], _date_tuple(info[3])): c
                for c, info in codes.items()}
        done = 0
        for f in as_completed(futs):
            done += 1
            res = f.result()
            if res:
                fetched.append(res)
            else:
                none_count += 1
            if done % 50 == 0:
                print(f"   {done}/{len(futs)}…（失敗 {none_count}）", flush=True)

    # 跨 lineId 去重（始発駅+始発時刻+終着駅+停車数）
    deduped = {}
    for r in fetched:
        sig = (r["stops"][0]["name"], r["stops"][0]["dep"],
               r["stops"][-1]["name"], len(r["stops"]))
        deduped.setdefault(sig, r)
    results = list(deduped.values())
    results.sort(key=lambda r: r["stops"][0]["dep"])

    out = JSON_DIR / out_name
    with open(out, "w", encoding="utf-8") as f:
        f.write("[\n")
        for i, r in enumerate(results):
            f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) +
                    (",\n" if i < len(results) - 1 else "\n"))
        f.write("]\n")
    print(f"🎉 {len(fetched)} 班取得（失敗 {none_count}）、去重後 {len(results)} 班 → {out}", flush=True)


def _pick_representative(all_codes, want_weekend):
    """data-date の曜日で振り分け、目標カテゴリ内で最多班次の日を代表日として codes を返す。"""
    import datetime
    by_date = defaultdict(dict)
    for c, info in all_codes.items():
        if info[3]:
            by_date[info[3]][c] = info
    cand = {}
    for dd, codes in by_date.items():
        try:
            y, m, d = map(int, dd.split("-"))
            is_weekend = datetime.date(y, m, d).weekday() >= 5
        except Exception:
            continue
        if is_weekend == want_weekend:
            cand[dd] = codes
    if not cand:
        return None, {}
    return max(cand.items(), key=lambda kv: len(kv[1]))


def run(max_workers=3, only=None):
    print("🗺️  掃描目標を構築中…", flush=True)
    targets = build_scan_targets()
    print(f"   {len(targets)} 駅を取得", flush=True)

    print("🔍 [第一段階] 全駅の時刻表を掃描（4日プール全件、data-date 付き）…", flush=True)
    all_codes = {}
    for i, (name, node, scan_line) in enumerate(targets):
        codes = scan_station(node, scan_line)
        for c, info in codes.items():
            all_codes.setdefault(c, info)
        print(f"   [{i+1}/{len(targets)}] {name}: +{len(codes)}（累計 {len(all_codes)}）", flush=True)

    dist = Counter(info[3] for info in all_codes.values())
    print(f"✅ {len(all_codes)} 個の stopCode を収集。日付分布:", flush=True)
    for dd in sorted(dist):
        print(f"     {dd}: {dist[dd]}", flush=True)

    if only != "holiday":
        wd_date, wd_codes = _pick_representative(all_codes, want_weekend=False)
        if wd_codes:
            print(f"🗓️  平日代表日 = {wd_date}（{len(wd_codes)} 班）", flush=True)
            _fetch_bucket(wd_codes, "raw_weekday.json", max_workers)
        else:
            print("⚠️  プール内に平日が見つかりません（水〜日に実行してください）", flush=True)
    if only != "weekday":
        hd_date, hd_codes = _pick_representative(all_codes, want_weekend=True)
        if hd_codes:
            print(f"🗓️  土休代表日 = {hd_date}（{len(hd_codes)} 班）", flush=True)
            _fetch_bucket(hd_codes, "raw_holiday.json", max_workers)
        else:
            print("⚠️  プール内に土休日が見つかりません（水〜日に実行してください）", flush=True)


def main():
    global SLEEP
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["weekday", "holiday"], help="只跑其中一種")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--sleep", type=float, default=SLEEP)
    args = ap.parse_args()
    SLEEP = args.sleep
    run(max_workers=args.workers, only=args.only)


if __name__ == "__main__":
    main()
