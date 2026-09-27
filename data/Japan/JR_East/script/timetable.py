#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
timetable.py — 東日本旅客鉄道 (JR East) 官方時刻表爬蟲

資料源：JR 東日本官方時刻表站 https://www.jreast-timetable.jp/
（列車詳情頁在 timetables.jreast.co.jp，與新幹線系統同源）

比 navitime 好的地方：有**真正的列車番号與列車種別**、有「直通」標記、
且是官方資料無商業服務的限速顧慮。三階段（比照既有新幹線腳本）：

  階段一 路線→車站：/cgi-bin/st_search.cgi?rosen={id} 取得該線各站的 list{ID}.html
  階段二 車站→方向：車站頁每個「路線・方面」列有 平日 / 土曜・休日 兩個純文字時刻表連結
                    （class=fortimeLink 的前 2 個；後面的「デジタル時刻表」不取）
  階段三 方向→列車：方向頁的 /train/ 連結即該站該方向所有班次（含普通車）
  階段四 列車詳情：矩陣式表格，一班車占 2 個 td，含 列車種別/列車名/列車番号/運転日
                    與各站 着/発 時刻

輸出：json/raw_timetable.json（原始資料，供 convert_timetable.py 轉換）

用法：
    py data/Japan/JR_East/script/timetable.py              # 全 71 條線
    py data/Japan/JR_East/script/timetable.py --lines 66,24 # 只跑指定 rosen id
    py data/Japan/JR_East/script/timetable.py --workers 8
"""
import sys
import re
import json
import time
import argparse
import unicodedata
from pathlib import Path
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

JSON_DIR = Path(__file__).parent.parent / "json"
JSON_DIR.mkdir(parents=True, exist_ok=True)

BASE = "https://www.jreast-timetable.jp/"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
SLEEP = 0.08          # 每請求輕微間隔（官方站，仍保持禮貌）

# 官方時刻表的 rosen id → 線名（排除 5 條新幹線，已有獨立系統）
ROSEN = {
    "1": "吾妻線", "3": "左沢線", "4": "飯山線", "5": "石巻線", "6": "五日市線",
    "7": "伊東線", "9": "羽越本線", "10": "内房線", "11": "越後線", "12": "奥羽本線",
    "13": "青梅線", "14": "大糸線", "15": "大船渡線", "16": "大湊線", "17": "男鹿線",
    "18": "鹿島線", "19": "釜石線", "20": "烏山線", "21": "川越線", "22": "北上線",
    "23": "久留里線", "24": "京浜東北線", "25": "京葉線", "26": "気仙沼線", "27": "小海線",
    "28": "五能線", "29": "埼京線", "30": "相模線", "31": "篠ノ井線", "32": "上越線",
    "33": "常磐・成田線", "34": "常磐線", "35": "信越本線", "36": "水郡線", "37": "仙山線",
    "38": "仙石線", "39": "総武線", "40": "総武線快速", "41": "総武本線", "42": "外房線",
    "43": "高崎線", "44": "田沢湖線", "45": "只見線", "46": "中央本線", "47": "津軽線",
    "48": "鶴見線", "49": "東海道線", "50": "東金線", "51": "東北本線", "52": "成田線",
    "53": "南武線", "54": "日光線", "55": "根岸線", "56": "白新線", "57": "八高線",
    "58": "八戸線", "59": "花輪線", "60": "磐越西線", "61": "磐越東線", "62": "水戸線",
    "63": "武蔵野線", "64": "弥彦線", "65": "山田線", "66": "山手線", "67": "横須賀線",
    "68": "横浜線", "69": "米坂線", "70": "陸羽西線", "71": "陸羽東線", "72": "両毛線",
    "78": "仙石東北ライン", "82": "宇都宮線",
}

PASS_MARKS = ("||", "‖", "レ", "===", "↓", "‐", "−")
TIME_RE = re.compile(r"(\d{1,2}):(\d{2})")

SESSION = requests.Session()
SESSION.headers.update(HEADERS)
_stats = {"fail": 0}


sys.path.insert(0, str(Path(__file__).parent))
from station_name import clean_station_name   # noqa: E402  與拓樸端共用同一規則


def get_soup(url, retries=3):
    for attempt in range(retries):
        try:
            time.sleep(SLEEP)
            r = SESSION.get(url, timeout=25)
            r.raise_for_status()
            r.encoding = r.apparent_encoding
            return BeautifulSoup(r.text, "html.parser")
        except Exception:
            if attempt == retries - 1:
                _stats["fail"] += 1
                return None
            time.sleep(2)
    return None


# ---------------------------------------------------------------- 階段一 / 二
def fetch_station_pages(rosen_ids):
    """路線 → 該線所有車站頁 URL（跨線去重：一個車站頁含其所有路線方向）。"""
    pages = {}
    for rid in rosen_ids:
        sp = get_soup(f"{BASE}cgi-bin/st_search.cgi?rosen={rid}")
        if not sp:
            print(f"  ⚠️  路線 {rid} ({ROSEN.get(rid, '?')}) 車站清單抓取失敗")
            continue
        n = 0
        for a in sp.find_all("a", href=re.compile(r"list\d+\.html")):
            url = urljoin(BASE, a["href"])
            if url not in pages:
                pages[url] = clean_station_name(a.get_text(strip=True))
                n += 1
        print(f"  {ROSEN.get(rid, rid):10s} +{n:3d} 新車站頁（累計 {len(pages)}）")
    return pages


def fetch_direction_links(station_url):
    """車站頁 → 各「路線・方面」列的 平日 / 土曜・休日 純文字時刻表連結。
    每列的 fortimeLink 前 2 個是純文字版，之後是「デジタル時刻表」→ 不取。"""
    sp = get_soup(station_url)
    if not sp:
        return []
    out = []
    for tr in sp.find_all("tr"):
        links = tr.find_all("a", class_="fortimeLink")
        if not links:
            continue
        for a in links[:2]:
            label = a.get_text(strip=True)
            if "デジタル" in label:
                continue
            kind = "holiday" if ("土曜" in label or "休日" in label) else "weekday"
            out.append((urljoin(station_url, a["href"]), kind))
    return out


def fetch_train_links(dir_url):
    """方向頁 → 該站該方向所有班次的詳情頁 URL。"""
    sp = get_soup(dir_url)
    if not sp:
        return []
    out = []
    for a in sp.find_all("a", href=re.compile(r"/train/")):
        u = urljoin(dir_url, a["href"]).replace(
            "www.jreast-timetable.jp", "timetables.jreast.co.jp")
        out.append(u)
    return out


# ------------------------------------------------------------------- 階段四
def to_minutes(hhmm, prev):
    """HH:MM → 分鐘；跨夜時累加 1440 使序列單調遞增。"""
    h, m = int(hhmm[0]), int(hhmm[1])
    v = h * 60 + m
    while prev is not None and v < prev:
        v += 1440
    return v


def parse_train_page(url):
    """解析列車詳情頁；一頁可能含多班（直通接續會並排）。"""
    sp = get_soup(url)
    if not sp:
        return []
    div = sp.find("div", class_="trainlist")
    if not div:
        return []
    table = div.find("table")
    if not table:
        return []

    types, names, nos, opdays = [], [], [], {}
    for tr in table.find_all("tr"):
        th = tr.find("th")
        if not th:
            continue
        label = th.get_text(strip=True)
        tds = tr.find_all("td")
        if "列車種別" in label:
            types = [td.get_text(strip=True) for td in tds]
        elif "列車名" in label:
            names = [td.get_text(strip=True) for td in tds]
        elif "列車番号" in label:
            nos = [td.get_text(strip=True) for td in tds]
        elif "運転日" in label:
            for i, td in enumerate(tds):
                opdays[i] = td.get_text(strip=True)

    count = max(len(types), len(names), len(nos))
    if not count:
        return []

    # 每班車占 2 個 td（時刻固定在 i*2）
    stops = {i: [] for i in range(count)}
    for tr in table.find_all("tr"):
        th = tr.find("th")
        tds = tr.find_all("td")
        if not th or not tds:
            continue
        label = th.get_text(strip=True)
        if any(k in label for k in ("列車種別", "列車名", "列車番号", "運転日",
                                    "併結", "駅名", "設備", "備考")):
            continue
        sta = clean_station_name(label)
        if not sta:
            continue
        for i in range(count):
            idx = i * 2
            if idx >= len(tds):
                continue
            cell = tds[idx].get_text(" ", strip=True)
            if not cell or any(p in cell for p in PASS_MARKS):
                continue
            times = TIME_RE.findall(cell)
            if not times:
                continue
            prev = stops[i][-1]["dep"] if stops[i] else None
            arr = to_minutes(times[0], prev)
            dep = to_minutes(times[-1], arr)
            stops[i].append({"sta": sta, "arr": arr, "dep": dep,
                             "direct": "直通" in cell})

    out = []
    for i in range(count):
        if len(stops[i]) < 2:
            continue
        raw_name = names[i] if i < len(names) else ""
        raw_type = types[i] if i < len(types) else ""
        out.append({
            "no": (nos[i] if i < len(nos) else "") or f"?{i}",
            "type": raw_type,
            "name": raw_name,
            "opday": opdays.get(i, ""),
            "stops": stops[i],
            "url": url,
            "col": i,
        })
    return out


# ----------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lines", default="", help="只跑這些 rosen id（逗號分隔）")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--limit-stations", type=int, default=0,
                    help="除錯用：只掃前 N 個車站頁")
    args = ap.parse_args()

    rosen_ids = [r.strip() for r in args.lines.split(",") if r.strip()] or list(ROSEN)
    W = args.workers

    t0 = time.time()
    print(f"🚉 階段一/二：{len(rosen_ids)} 條路線 → 車站頁")
    station_pages = fetch_station_pages(rosen_ids)
    st_urls = list(station_pages)
    if args.limit_stations:
        st_urls = st_urls[:args.limit_stations]
    print(f"   共 {len(st_urls)} 個唯一車站頁\n")

    print("🧭 階段二：車站頁 → 方向頁")
    dir_links = {}
    with ThreadPoolExecutor(max_workers=W) as ex:
        futs = {ex.submit(fetch_direction_links, u): u for u in st_urls}
        for k, f in enumerate(as_completed(futs), 1):
            for url, kind in f.result():
                dir_links.setdefault(url, kind)
            if k % 200 == 0:
                print(f"   {k}/{len(st_urls)} 車站頁 → {len(dir_links)} 方向頁")
    print(f"   共 {len(dir_links)} 個方向頁\n")

    print("🚃 階段三：方向頁 → 列車詳情連結")
    train_urls = set()
    with ThreadPoolExecutor(max_workers=W) as ex:
        futs = {ex.submit(fetch_train_links, u): u for u in dir_links}
        for k, f in enumerate(as_completed(futs), 1):
            train_urls.update(f.result())
            if k % 500 == 0:
                print(f"   {k}/{len(dir_links)} 方向頁 → {len(train_urls)} 班次")
    print(f"   共 {len(train_urls)} 個唯一列車詳情頁\n")

    print("⏱️  階段四：解析列車詳情")
    trains = []
    with ThreadPoolExecutor(max_workers=W) as ex:
        futs = {ex.submit(parse_train_page, u): u for u in train_urls}
        for k, f in enumerate(as_completed(futs), 1):
            trains.extend(f.result())
            if k % 500 == 0:
                el = time.time() - t0
                print(f"   {k}/{len(train_urls)} 頁 → {len(trains)} 班次"
                      f"（{el/60:.1f} 分，失敗 {_stats['fail']}）")

    out = JSON_DIR / "raw_timetable.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(trains, f, ensure_ascii=False)

    print(f"\n🎉 完成：{len(trains)} 班次 / {len(train_urls)} 詳情頁"
          f"｜失敗請求 {_stats['fail']}｜耗時 {(time.time()-t0)/60:.1f} 分")
    print(f"📄 {out}")


if __name__ == "__main__":
    main()
