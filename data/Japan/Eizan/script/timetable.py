#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
timetable.py — 京阪電鐵 navitime 爬蟲（幹線 淀屋橋—出町柳）

兩階段（比照 TRA timetable.py）：
  階段一 掃描：對幹線全部車站抓 timetable 頁，解析 <li.time-frame> 的 data-* 屬性，
             依 data-date 篩出目標營運日（平日 / 土休），蒐集去重的 stopCode 與其種別。
  階段二 下載：對每個 stopCode 抓 stops 頁，解析 <li.stops-list> 取各站 着/発 時刻。
原始結果存成 json/raw_weekday.json / raw_holiday.json（再由 convert_timetable.py 轉成本專案格式）。

navitime 注意事項：
  - 非 JS 的 HTML 不依 URL 的 date/updown 過濾，而是回傳一週的池子，每班車自帶 data-date。
  - stops 詳情頁無列車番号/種別 → no 用 stopCode、type 從 timetable listing 帶下來。
  - 商業服務：嚴格限速（每請求 sleep ≥1s）、低併發、僅個人用途、尊重 robots.txt。
"""
import sys
import json
import time
import re
import unicodedata
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SCRIPT_DIR = Path(__file__).parent
JSON_DIR = SCRIPT_DIR.parent / "json"

LINE_MAIN = "00000259"     # 叡山本線（出町柳→八瀬比叡山口）
LINE_KURAMA = "00000258"   # 鞍馬線（宝ヶ池→鞍馬）
# 掃描來源：兩條線都掃。出町柳→鞍馬的直通車掛在哪條 lineId 由連結自身決定，
# 故掃描時連同 href 的 lineId 一起記錄，下載時各用各的、再以內容簽章去重。
SCAN_LINES = [LINE_MAIN, LINE_KURAMA]

BASE = "https://www.navitime.co.jp"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
SLEEP = 1.1  # 每請求間隔（禮貌限速）

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def norm_name(name):
    """站名正規化：NFKC、去各式括號後綴與「駅」字。
    三条（京都府）→ 三条；守口市〔京阪線〕→ 守口市。
    navitime 會用（…）/〔…〕/【…】 等加註，全部剝除。"""
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
    """從兩條線的 stationList 組出掃描目標：[(站名, node, 掃描用 lineId)]。
    本線站用 00000285、鴨東線專屬站（出町柳/神宮丸太町）用 00000281；同站重複時以本線優先。"""
    seen_nodes = {}
    targets = []
    for line in SCAN_LINES:  # 本線/鴨東優先，再加連絡線
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


def scan_station(node, scan_line, target_date):
    """抓一站的 timetable，回傳 {stopCode: (種別, code_lineId, ref_node)}（只取 data-date == target_date）。
    code_lineId 取自連結本身；ref_node 為「發現此車的車站 node」——stops 頁的 node 參數需給一個
    在該車路線上的有效站，否則回 HTTP 400（空 node 對部分車次會失敗 → 整班被丟掉）。"""
    soup = get_soup(f"{BASE}/diagram/timetable?node={node}&lineId={scan_line}&updown=0")
    if not soup:
        return {}
    found = {}
    for li in soup.select("li.time-frame"):
        if li.get("data-date") != target_date:
            continue
        a = li.select_one("a[href*='/diagram/stops/']")
        if not a:
            continue
        m = re.search(r"/diagram/stops/([^/]+)/([^/]+)/", a.get("href", ""))
        if m:
            found[m.group(2)] = (li.get("data-name") or "普通", m.group(1), node)
    return found


def fetch_stops(stop_code, ttype, code_line, ref_node, date_tuple):
    """抓單一車次 stops 頁，回傳 {code, type, stops:[{name, arr, dep}]}。
    ref_node 須為該車路線上的有效站 node（空 node 對部分車次回 400）。"""
    y, mth, d = date_tuple
    url = f"{BASE}/diagram/stops/{code_line}/{stop_code}/?node={ref_node}&year={y}&month={mth:02d}&day={d:02d}"
    soup = get_soup(url)
    if not soup:
        return None
    stops = []
    for row in soup.select("li.stops-list"):
        name_el = row.select_one("dt.station-name")
        # 一般站用 dd.time（單一時刻）；停留站（待避/緩急接續）用 dd.from-to-time（着<br>発兩個時刻）
        time_el = row.select_one("dd.time, dd.from-to-time")
        if not name_el or not time_el:
            continue
        name = norm_name(name_el.get_text(strip=True))
        ttext = time_el.get_text(" ", strip=True)
        # ttext 例："05:00発" 或 "05:01着" 或 "10:12着 10:19発"（停留站）
        arr = dep = None
        am = re.search(r"(\d{1,2}):(\d{2})\s*着", ttext)
        dm = re.search(r"(\d{1,2}):(\d{2})\s*発", ttext)
        if am:
            arr = int(am.group(1)) * 60 + int(am.group(2))
        if dm:
            dep = int(dm.group(1)) * 60 + int(dm.group(2))
        if arr is None and dep is None:
            # 沒有着/発標記，取任意時刻
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
    # 跨夜處理：時間遞減則 +1440
    last = -1
    for st in stops:
        if st["arr"] < last:
            st["arr"] += 1440
        if st["dep"] < st["arr"]:
            st["dep"] += 1440
        last = st["dep"]
    return {"code": stop_code, "type": ttype, "stops": stops}


def run(target_date_str, date_tuple, out_name, max_workers=3):
    print(f"\n🗓️  目標營運日 {target_date_str}（{date_tuple}）→ {out_name}", flush=True)
    print("🗺️  建立掃描目標（站名/node/lineId）…", flush=True)
    targets = build_scan_targets()
    print(f"   取得 {len(targets)} 站", flush=True)

    print("🔍 [階段一] 掃描全幹線車站，蒐集當日車次…", flush=True)
    all_codes = {}  # code -> (type, code_lineId, ref_node)
    for i, (name, node, scan_line) in enumerate(targets):
        codes = scan_station(node, scan_line, target_date_str)
        for c, info in codes.items():
            all_codes.setdefault(c, info)
        print(f"   [{i+1}/{len(targets)}] {name}: +{len(codes)}（累計 {len(all_codes)}）", flush=True)
    print(f"✅ 掃得 {len(all_codes)} 個 stopCode（含跨 lineId 重複，稍後去重）", flush=True)

    print("⚡ [階段二] 下載各車次停靠序列…", flush=True)
    fetched = []
    none_count = 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(fetch_stops, c, info[0], info[1], info[2], date_tuple): c
                for c, info in all_codes.items()}
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

    # 跨 lineId 去重：同一實體班次（首站+首發時刻+末站+種別相同）只留一份
    deduped = {}
    for r in fetched:
        sig = (r["type"], r["stops"][0]["name"], r["stops"][0]["dep"],
               r["stops"][-1]["name"], len(r["stops"]))
        deduped.setdefault(sig, r)
    results = list(deduped.values())

    out = JSON_DIR / out_name
    with open(out, "w", encoding="utf-8") as f:
        f.write("[\n")
        for i, r in enumerate(results):
            line = json.dumps(r, ensure_ascii=False, separators=(",", ":"))
            f.write(line + (",\n" if i < len(results) - 1 else "\n"))
        f.write("]\n")
    print(f"🎉 抓到 {len(fetched)} 班（失敗 {none_count}）、去重後 {len(results)} 班 → {out}", flush=True)


def main():
    global SLEEP
    ap = argparse.ArgumentParser()
    ap.add_argument("--weekday", default="2026-06-17", help="平日代表日 YYYY-MM-DD（預設週三）")
    ap.add_argument("--holiday", default="2026-06-20", help="土休代表日 YYYY-MM-DD（預設週六）")
    ap.add_argument("--only", choices=["weekday", "holiday"], help="只跑其中一種")
    ap.add_argument("--workers", type=int, default=3,
                    help="階段二下載併發數（預設 3；調高加速但對 navitime 較不禮貌、有被限流風險）")
    ap.add_argument("--sleep", type=float, default=SLEEP,
                    help=f"每請求間隔秒數（預設 {SLEEP}）")
    args = ap.parse_args()

    SLEEP = args.sleep

    def to_tuple(s):
        y, m, d = s.split("-")
        return (int(y), int(m), int(d))

    if args.only != "holiday":
        run(args.weekday, to_tuple(args.weekday), "raw_weekday.json", max_workers=args.workers)
    if args.only != "weekday":
        run(args.holiday, to_tuple(args.holiday), "raw_holiday.json", max_workers=args.workers)


if __name__ == "__main__":
    main()
