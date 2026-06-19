#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
timetable.py — 嵯峨野観光鉄道（嵐山小火車）navitime 爬蟲

単一線・4 駅・1 車種（トロッコ列車）。全営業日で同一ダイヤ（平日/土休の別なし）。
→ プール内の「最も班次の多い 1 日」を代表営業日として採用し、単一ファイル raw_all.json を出力。

navitime 注意事項（阪急で確認済み）：
  - timetable listing は「サーバ当日から約 4 日」のプールを返し、URL の date は無視される。
    各班 <li.time-frame> の data-date が実運行日 → ここでは曜日分けは不要（全日同一ダイヤ）なので
    代表日 1 日分のみ採用する。
  - 方向は updown が当てにならないため stops 序列自身で判断（嵯峨→亀岡 / 亀岡→嵯峨）。
  - 商業服務：限速 sleep≥1s、低併発、個人利用のみ。
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

LINE_SAGANO = "00000649"  # 嵯峨野観光線（navitime lineId）
# 4 駅の node（stationList より）
STATION_NODES = ["00000090", "00000092", "00000091", "00000089"]

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


def scan_station(node):
    """一駅の時刻表を上下両方向取得し {stopCode: (code_line, node, data_date)} を返す。"""
    found = {}
    for updown in [0, 1]:
        url = f"{BASE}/diagram/timetable?node={node}&lineId={LINE_SAGANO}&updown={updown}"
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
            found[stop_code] = (code_line, node, li.get("data-date", ""))
    return found


def fetch_stops(stop_code, code_line, ref_node, date_tuple):
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
    # 跨夜処理（トロッコは深夜運行なしだが念のため）
    last = -1
    for st in stops:
        if st["arr"] < last:
            st["arr"] += 1440
        if st["dep"] < st["arr"]:
            st["dep"] += 1440
        last = st["dep"]
    # 種別は観光トロッコ列車に統一（navitime は「普通」と表示）
    return {"code": stop_code, "type": "トロッコ", "stops": stops}


def run(max_workers=3):
    print("🔍 [第一段階] 全 4 駅の時刻表を掃描（プール全件、data-date 付き）…", flush=True)
    all_codes = {}
    for i, node in enumerate(STATION_NODES):
        codes = scan_station(node)
        for c, info in codes.items():
            all_codes.setdefault(c, info)
        print(f"   [{i+1}/{len(STATION_NODES)}] node={node}: +{len(codes)}（累計 {len(all_codes)}）", flush=True)

    # 代表営業日 = プール内で最も班次の多い日付（全日同一ダイヤなので 1 日で十分）
    dist = Counter(info[2] for info in all_codes.values())
    print(f"✅ {len(all_codes)} 個の stopCode を収集。日付分布: {dict(dist)}", flush=True)
    if not dist:
        print("⚠️  班次が見つかりません", flush=True)
        return
    rep_date = dist.most_common(1)[0][0]
    rep_codes = {c: info for c, info in all_codes.items() if info[2] == rep_date}
    y, m, d = map(int, rep_date.split("-"))
    print(f"🗓️  代表営業日 = {rep_date}（{len(rep_codes)} 班）", flush=True)

    print("⚡ [第二段階] 各列車の停車順序をダウンロード…", flush=True)
    fetched, none_count = [], 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(fetch_stops, c, info[0], info[1], (y, m, d)): c
                for c, info in rep_codes.items()}
        for f in as_completed(futs):
            res = f.result()
            if res:
                fetched.append(res)
            else:
                none_count += 1

    # 同一実体列車の去重（始発駅+始発時刻+終着駅+停車数）
    deduped = {}
    for r in fetched:
        sig = (r["stops"][0]["name"], r["stops"][0]["dep"],
               r["stops"][-1]["name"], len(r["stops"]))
        deduped.setdefault(sig, r)
    results = list(deduped.values())
    results.sort(key=lambda r: r["stops"][0]["dep"])

    out = JSON_DIR / "raw_all.json"
    with open(out, "w", encoding="utf-8") as f:
        f.write("[\n")
        for i, r in enumerate(results):
            f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) +
                    (",\n" if i < len(results) - 1 else "\n"))
        f.write("]\n")
    print(f"🎉 {len(fetched)} 班取得（失敗 {none_count}）、去重後 {len(results)} 班 → {out}", flush=True)


def main():
    global SLEEP
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--sleep", type=float, default=SLEEP)
    args = ap.parse_args()
    SLEEP = args.sleep
    run(max_workers=args.workers)


if __name__ == "__main__":
    main()
