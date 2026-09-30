"""
odekake.py — 從 JR おでかけネット 補抓只在 JR 西日本區間行駛的北陸新幹線列車（つるぎ）

JR 東日本的時刻表網站只列得到會開進 JR 東日本區間的列車；つるぎ全程在
富山／金沢～敦賀，只能從 JR 西日本抓。

流程：
1. 站時刻表 /station-timetable/{ID}?date=YYYYMMDD（ID = 站 4 碼 + 線別 3 碼 + 方向 3 碼，
   北陸新幹線線別 006；可從 /cgi-bin/mydia_sp.cgi?MD=3&EID=<駅ID> 查到）
   逐日掃描，只收車種標示為「つ」的列車連結
2. 列車頁 /train-timetable/{id} 取車次、停站時刻，以及月曆上的運轉日（drivingday-01）

回傳格式與 timetable.py 的 fetch_single_train_detail 相同（no/type/dates/data/url）。
"""
import re
import time
from datetime import date

import requests
from bs4 import BeautifulSoup

BASE = "https://timetable.jr-odekake.net"
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
SLEEP = 0.3

# 下行的つるぎ一定經過金沢（富山發或金沢發），上行的一定從敦賀發；
# 富山上下行用來補可能的富山～金沢區間車
STATION_TIMETABLES = {
    "2663006002": "金沢 福井・敦賀方面",
    "2635006001": "敦賀 金沢・富山・長野・東京方面",
    "2675006001": "富山 長野・東京方面",
    "2675006002": "富山 新高岡・金沢・敦賀方面",
}
TYPE_MARK = "つ"   # 站時刻表上的車種縮寫
TYPE_NAME = "つるぎ"

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def get_soup(url):
    for attempt in range(3):
        try:
            time.sleep(SLEEP)
            res = SESSION.get(url, timeout=15)
            if res.status_code == 200:
                res.encoding = "utf-8"
                return BeautifulSoup(res.text, "html.parser")
        except requests.RequestException:
            pass
        time.sleep(2 * (attempt + 1))
    return None


def available_dates(soup):
    """站時刻表頁的日期選單（今天起約 6 週），value 為 YYYYMMDD"""
    return [f"{v[:4]}-{v[4:6]}-{v[6:]}" for v in
            (o.get("value", "") for o in soup.select("select#date option")) if len(v) == 8]


def scan_station(st_id, date_str):
    """回傳該站該日「つ」列車的 train-timetable id 集合"""
    soup = get_soup(f"{BASE}/station-timetable/{st_id}?date={date_str.replace('-', '')}")
    if not soup:
        return set(), soup
    ids = set()
    for a in soup.select("a[href*='/train-timetable/']"):
        mark = a.select_one(".train-type")
        if mark and mark.get_text(strip=True) == TYPE_MARK:
            m = re.search(r"/train-timetable/(\d+)", a["href"])
            if m:
                ids.add(m.group(1))
    return ids, soup


def parse_calendar(soup, start_date, end_date):
    dates = set()
    for table in soup.select(".monthly-calendar table"):
        th = table.select_one("tr.month th")
        ym = re.search(r"(\d{4})年(\d{1,2})月", th.get_text() if th else "")
        if not ym:
            continue
        y, m = int(ym.group(1)), int(ym.group(2))
        for td in table.select("tr.day td.drivingday-01"):
            txt = td.get_text(strip=True)
            if txt.isdigit() and start_date <= date(y, m, int(txt)) <= end_date:
                dates.add(f"{y}-{m:02d}-{int(txt):02d}")
    return dates


def to_minutes(hh_mm):
    h, m = map(int, hh_mm.split(":"))
    return h * 60 + m


def fetch_train(train_id, date_str, start_date, end_date):
    url = f"{BASE}/train-timetable/{train_id}?date={date_str.replace('-', '')}"
    soup = get_soup(url)
    if not soup:
        return None

    info = {}
    for tr in soup.select("tbody.train-details tr"):
        th, td = tr.find("th"), tr.find("td")
        if th and td:
            info[th.get_text(strip=True)] = td.get_text(strip=True)
    name = info.get("列車名", "")
    if TYPE_NAME not in name:
        return None

    stops = []
    for tr in soup.select("tbody.time-details tr"):
        if "remarks" in (tr.get("class") or []):
            continue
        sta_td = tr.select_one("td.cell-fixed")
        time_td = tr.select_one("td.text")
        if not sta_td or not time_td:
            continue
        arr = dep = None
        for div in time_td.find_all("div"):
            t = re.search(r"(\d{2}:\d{2})", div.get_text())
            if not t:
                continue   # 「レ」= 通過
            if "着" in div.get_text():
                arr = to_minutes(t.group(1))
            else:
                dep = to_minutes(t.group(1))
        if arr is None and dep is None:
            continue
        stops.append({"sta": sta_td.get_text(strip=True),
                      "arr": arr if arr is not None else dep,
                      "dep": dep if dep is not None else arr})
    if len(stops) < 2:
        return None

    return {
        "no": info.get("列車番号", ""),
        "type": TYPE_NAME,
        "dates": parse_calendar(soup, start_date, end_date),
        "data": stops,
        "url": url,
        "variants": [],
    }


def fetch_tsurugi(start_date, end_date):
    print("\n🌊 JR おでかけネット：補抓つるぎ…")
    first_id = next(iter(STATION_TIMETABLES))
    _, soup = scan_station(first_id, date.today().isoformat())
    if not soup:
        print("❌ おでかけネット無法連線，略過つるぎ")
        return []
    scan_dates = [d for d in available_dates(soup)
                  if start_date <= date.fromisoformat(d) <= end_date]

    found = {}   # train-timetable id -> 第一次看到的日期
    for d in scan_dates:
        for st_id in STATION_TIMETABLES:
            ids, _ = scan_station(st_id, d)
            for i in ids:
                found.setdefault(i, d)
    print(f"   掃描 {len(scan_dates)} 天 × {len(STATION_TIMETABLES)} 個站時刻表，共 {len(found)} 個列車頁")

    # 同車次同停站的不同列車頁合併運轉日
    merged = {}
    for train_id, d in sorted(found.items()):
        t = fetch_train(train_id, d, start_date, end_date)
        if not t or not t["dates"]:
            continue
        sig = (t["no"], tuple((s["sta"], s["arr"], s["dep"]) for s in t["data"]))
        if sig in merged:
            merged[sig]["dates"] |= t["dates"]
        else:
            merged[sig] = t
    results = list(merged.values())
    print(f"   取得つるぎ {len(results)} 筆（{len({t['no'] for t in results})} 個車次）")
    return results
