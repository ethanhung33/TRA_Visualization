#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
timetable.py — 阪急電鐵 navitime 爬蟲（全 9 線）

兩階段（比照 Keihan timetable.py）：
  階段一 掃描：對全線車站抓 timetable 頁，解析 <li.time-frame> 的 data-* 屬性，
             依 data-date 篩出目標營運日，蒐集去重的 stopCode 與其種別。
  階段二 下載：對每個 stopCode 抓 stops 頁，解析 <li.stops-list> 取各站 着/発 時刻。
原始結果存成 json/raw_weekday.json / raw_holiday.json（再由 convert_timetable.py 轉成本專案格式）。

navitime 注意事項：
  - 非 JS 的 HTML 不依 URL 的 date/updown 過濾，而是回傳一週的池子，每班車自帶 data-date。
  - stops 詳情頁無列車番号/種別 → no 用 stopCode、type 從 timetable listing 帶下來。
  - 商業服務：嚴格限速（每請求 sleep ≥1s）、低併發、僅個人用途、尊重 robots.txt。

阪急特記事項：
  - 神戸本線と宝塚本線は 大阪梅田〜十三 を共用。十三は一方の lineId でのみ掃描するが、
    各線専用駅（神崎川, 三国 等）でその線の全列車を捕捉できるため問題なし。
  - 今津線は 宝塚〜西宮北口（北）と 西宮北口〜今津（南）に分かれるが、
    今津線専用駅（宝塚南口, 阪神国道 等）を掃描することで全列車を捕捉。
  - 千里線は 淡路 で京都本線と接続、天神橋筋六丁目では大阪メトロ谷町線と接続
    （大阪メトロ区間はトポロジー外 → convert 時に自動略過）。
"""
import sys
import json
import time
import re
import unicodedata
import argparse
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SCRIPT_DIR = Path(__file__).parent
JSON_DIR = SCRIPT_DIR.parent / "json"

# 阪急全 9 路線の lineId（navitime companyId: 00000056）
LINE_KOBE       = "00000654"  # 神戸本線（大阪梅田→神戸三宮）
LINE_TAKARAZUKA = "00000656"  # 宝塚本線（大阪梅田→宝塚）
LINE_KYOTO      = "00000651"  # 京都本線（大阪梅田→京都河原町）
LINE_IMAZU      = "00000653"  # 今津線（宝塚→西宮北口→今津）
LINE_ITAMI      = "00000650"  # 伊丹線（塚口→伊丹）
LINE_KOYO       = "00000652"  # 甲陽線（夙川→甲陽園）
LINE_SENRI      = "00000655"  # 千里線（天神橋筋六丁目→北千里）
LINE_MINOH      = "00000657"  # 箕面線（石橋阪大前→箕面）
LINE_ARASHIYAMA = "00000658"  # 嵐山線（桂→嵐山）

# 掃描順序：主要幹線を先にして共用駅（梅田/中津/十三/淡路/宝塚/西宮北口等）を
# 幹線側の lineId で登録、その後支線で固有駅を追加。
SCAN_LINES = [
    LINE_KOBE, LINE_TAKARAZUKA, LINE_KYOTO,
    LINE_IMAZU, LINE_ITAMI, LINE_KOYO,
    LINE_SENRI, LINE_MINOH, LINE_ARASHIYAMA,
]

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


# 阪急 navitime の種別略称 → 正式名称マッピング
# 時刻表リンクテキスト形式（スペースなし）：「通特41大阪梅田」「準特29大阪梅田」「50大阪梅田」
# 先頭の漢字略称 + 2桁分数 + 行先 で構成される。
_TYPE_ABBREV = {
    "快特": "快速特急",
    "準特": "準特急",
    "通特": "通勤特急",
    "直特": "直通特急",
    "快急": "快速急行",
    "通急": "通勤急行",
    "特":   "特急",
    "急":   "急行",
    "準":   "準急",
}


def _parse_type(link_text: str) -> str:
    """リンクテキストから種別を抽出。形式：[漢字略称][2桁分][行先]（スペースなし）。
    先頭が数字なら略称なし → 普通。"""
    text = link_text.strip()
    m = re.match(r"^([^\d]*)(\d{2})", text)
    if not m:
        return "普通"
    prefix = m.group(1)
    if not prefix:
        return "普通"
    return _TYPE_ABBREV.get(prefix, prefix)


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
    同一 node は最初に発見した lineId で登録（seen_nodes による去重）。"""
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


def scan_station(node, scan_line, date_tuple):
    """一駅の時刻表を上下両方向取得し {stopCode: (種別, code_lineId, ref_node)} を返す。

    阪急 navitime の時刻表ページは Keihan 同様に約1週間分のプールを返す。
    ただし data-date 属性ではなく、stops URL に日付が埋め込まれている：
      /diagram/stops/{lineId}/{code}/?node=...&year=Y&month=M&day=D
    → stops href に目標日付文字列が含まれるものだけを採用してフィルタリング。
    上り下りは別ページのため updown=0/1 両方取得する。
    """
    y, mth, d = date_tuple
    target_date = f"year={y}&month={mth:02d}&day={d:02d}"
    found = {}
    for updown in [0, 1]:
        url = f"{BASE}/diagram/timetable?node={node}&lineId={scan_line}&updown={updown}"
        soup = get_soup(url)
        if not soup:
            continue
        for a in soup.select("a[href*='/diagram/stops/']"):
            href = a.get("href", "")
            if target_date not in href:
                continue  # 目標日以外の班次はスキップ
            m = re.search(r"/diagram/stops/([^/]+)/([^/]+)/", href)
            if not m:
                continue
            code_line, stop_code = m.group(1), m.group(2)
            if stop_code not in found:
                ttype = _parse_type(a.get_text(strip=True))
                found[stop_code] = (ttype, code_line, node)
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
    # 跨夜処理
    last = -1
    for st in stops:
        if st["arr"] < last:
            st["arr"] += 1440
        if st["dep"] < st["arr"]:
            st["dep"] += 1440
        last = st["dep"]
    return {"code": stop_code, "type": ttype, "stops": stops}


def run(target_date_str, date_tuple, out_name, max_workers=3):
    print(f"\n🗓️  目標営業日 {target_date_str}（{date_tuple}）→ {out_name}", flush=True)
    print("🗺️  掃描目標を構築中…", flush=True)
    targets = build_scan_targets()
    print(f"   {len(targets)} 駅を取得", flush=True)

    print("🔍 [第一段階] 全駅の時刻表を掃描、当日列車を収集…", flush=True)
    all_codes = {}
    code_stations = defaultdict(set)
    for i, (name, node, scan_line) in enumerate(targets):
        codes = scan_station(node, scan_line, date_tuple)
        for c, info in codes.items():
            all_codes.setdefault(c, info)
            code_stations[c].add(name)
        print(f"   [{i+1}/{len(targets)}] {name}: +{len(codes)}（累計 {len(all_codes)}）", flush=True)
    print(f"✅ {len(all_codes)} 個の stopCode を収集", flush=True)

    print("⚡ [第二段階] 各列車の停車順序をダウンロード…", flush=True)
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

    # 跨 lineId 去重：同一実体列車（種別+始発駅+始発時刻+終着駅+停車数が同一）は一件のみ
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
    print(f"🎉 {len(fetched)} 班取得（失敗 {none_count}）、去重後 {len(results)} 班 → {out}", flush=True)


def main():
    global SLEEP
    ap = argparse.ArgumentParser()
    ap.add_argument("--weekday", default="2026-06-17", help="平日代表日 YYYY-MM-DD（預設週三）")
    ap.add_argument("--holiday", default="2026-06-21", help="土休代表日 YYYY-MM-DD（預設週六）")
    ap.add_argument("--only", choices=["weekday", "holiday"], help="只跑其中一種")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--sleep", type=float, default=SLEEP)
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
