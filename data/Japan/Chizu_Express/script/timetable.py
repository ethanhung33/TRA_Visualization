#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
timetable.py — 智頭急行 navitime 爬蟲（智頭線）

平日/土休の 2 ファイルを出力。navitime の timetable listing は「サーバ当日から約 4 日」の
プールを返し URL の date は無視されるため、各班 data-date の曜日で平日/土休に分桶し、
各カテゴリの「最多班次の代表日」を採用（水〜日に実行すれば両方含む）。

種別は data-name（普通 / 特急）。特急（スーパーはくと/いなば）は上郡以西の JR 山陽本線、
智頭以北の JR 因美線/山陰本線へ直通 → 拓樸外駅は stops に残し convert で is_other(JR西日本) に。
方向は stops 序列で判断。商業服務：限速 sleep≥1s、低併発、個人利用のみ。
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

LINE_CHIZU = "00000753"  # 智頭線（navitime companyId: 00000105）
# 14 駅の node（stationList より）
STATION_NODES = ["00003939", "00005498", "00001088", "00001604", "00002798",
                 "00008097", "00005002", "00001670", "00005581", "00004707",
                 "00000019", "00003105", "00009058", "00005935"]

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


def scan_station(node):
    """{stopCode: (種別, code_lineId, ref_node, set(運行日))}。
    智頭急行は同一 stopCode が複数日に再利用される（毎日同ダイヤ）ため、
    日付は単一値ではなく集合で蓄積する（後で代表日が集合に含まれるかで分桶）。"""
    found = {}
    for updown in [0, 1]:
        url = f"{BASE}/diagram/timetable?node={node}&lineId={LINE_CHIZU}&updown={updown}"
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
                found[stop_code] = (li.get("data-name") or "普通", code_line, node, set())
            if dd:
                found[stop_code][3].add(dd)
    return found


def fetch_stops(stop_code, ttype, code_line, ref_node, date_tuple):
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
        for f in as_completed(futs):
            res = f.result()
            if res:
                fetched.append(res)
            else:
                none_count += 1

    deduped = {}
    for r in fetched:
        sig = (r["type"], r["stops"][0]["name"], r["stops"][0]["dep"],
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
    """各 code は運行日の集合を持つ。目標カテゴリ（平日/土休）に属す日付のうち
    最も多くの code が走る日を代表日として選び、その日に走る code を抽出。
    info[3] は集合 → 戻り値の info は代表日（単一文字列）に置換して返す。"""
    import datetime
    date_codes = defaultdict(list)  # date -> [code...]
    for c, info in all_codes.items():
        for dd in info[3]:
            date_codes[dd].append(c)
    cand = {}
    for dd, codes in date_codes.items():
        try:
            y, m, d = map(int, dd.split("-"))
            is_weekend = datetime.date(y, m, d).weekday() >= 5
        except Exception:
            continue
        if is_weekend == want_weekend:
            cand[dd] = codes
    if not cand:
        return None, {}
    rep_date, codes = max(cand.items(), key=lambda kv: len(kv[1]))
    bucket = {c: (all_codes[c][0], all_codes[c][1], all_codes[c][2], rep_date)
              for c in codes}
    return rep_date, bucket


def run(max_workers=3, only=None):
    print("🔍 [第一段階] 全 14 駅の時刻表を掃描（4日プール全件、data-date 付き）…", flush=True)
    all_codes = {}
    for i, node in enumerate(STATION_NODES):
        codes = scan_station(node)
        for c, info in codes.items():
            if c not in all_codes:
                all_codes[c] = info
            else:
                all_codes[c][3].update(info[3])  # 運行日集合を merge
        print(f"   [{i+1}/{len(STATION_NODES)}] node={node}: +{len(codes)}（累計 {len(all_codes)}）", flush=True)

    dist = Counter()
    for info in all_codes.values():
        for dd in info[3]:
            dist[dd] += 1
    print(f"✅ {len(all_codes)} 個の stopCode を収集。運行日別の班数: {dict(dist)}", flush=True)

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
    ap.add_argument("--only", choices=["weekday", "holiday"])
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--sleep", type=float, default=SLEEP)
    args = ap.parse_args()
    SLEEP = args.sleep
    run(max_workers=args.workers, only=args.only)


if __name__ == "__main__":
    main()
