"""
近鐵時刻表爬蟲 → json/raw_weekday.json、json/raw_holiday.json（原始資料，不做站名對應）

站名清洗、直通外網切段（is_other）、路線切分都在 convert_timetable.py，
之後要改轉換規則只需重跑 convert，不必重爬。

流程：
  1. 掃描各站時刻表頁（T5）→ 每個車次 tx 在哪些站出現（sf 候選）
  2. 抓車次頁（T7）。注意 T7 只列出 sf 站「之後」的停靠站（表頭仍寫 始発駅），
     若隨便取一個 sf 會得到被截頭的車次，所以：
     先以任一 sf 抓一次並記錄 sf→站名；首站不是最前面時，改用更上游的 sf 重抓，
     直到停靠站不再變長。
"""
import requests
from bs4 import BeautifulSoup
import json
import re
from urllib.parse import urlparse, parse_qs
from tqdm import tqdm
import concurrent.futures
import os

WORKERS = 30
JSON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'json')
HEADERS = {'User-Agent': 'Mozilla/5.0'}


def convert_to_minutes(time_str):
    if not time_str or time_str.strip() == "": return time_str
    match = re.search(r'(\d{1,2})[:：](\d{2})', time_str)
    if match: return int(match.group(1)) * 60 + int(match.group(2))
    return time_str

def get_all_station_urls(d_val):
    urls = []
    
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=350-0&d=1&dw={d_val}")
    for k in range(1, 23): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=350-{k}&d=2&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=350-23&d=1&dw={d_val}")
    for k in range(1, 23): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=350-{23-k}&d=1&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=350-0&d=2&dw={d_val}")
    
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=360-0&d=1&dw={d_val}")
    for k in range(1, 25): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=360-{k}&d=2&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=361-0&d=1&dw={d_val}")
    for k in range(1, 16): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=361-{k}&d=2&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=361-16&d=1&dw={d_val}")
    for k in range(1, 16): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=361-{16-k}&d=1&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=360-25&d=1&dw={d_val}")
    for k in range(1, 25): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=360-{25-k}&d=1&dw={d_val}")
    
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=352-0&d=1&dw={d_val}")
    for k in range(1, 7): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=352-{k}&d=2&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=352-7&d=1&dw={d_val}")
    for k in range(1, 7): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=352-{7-k}&d=1&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=352-0&d=2&dw={d_val}")
    
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=356-0&d=1&dw={d_val}")
    for k in range(1, 47): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=356-{k}&d=2&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=356-47&d=1&dw={d_val}")
    for k in range(1, 47): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=356-{47-k}&d=1&dw={d_val}")

    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=413-1&d=1&dw={d_val}")
    for k in range(2, 44): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=413-{k}&d=2&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=413-44&d=1&dw={d_val}")
    for k in range(2, 44): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=413-{45-k}&d=1&dw={d_val}")
    
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=349-0&d=1&dw={d_val}")
    for k in range(1, 27): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=349-{k}&d=2&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=373-0&d=1&dw={d_val}")
    for k in range(1, 15): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=373-{k}&d=2&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=373-15&d=1&dw={d_val}")
    for k in range(1, 15): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=373-{15-k}&d=1&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=349-27&d=1&dw={d_val}")
    for k in range(1, 27): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=349-{27-k}&d=1&dw={d_val}")

    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=357-0&d=1&dw={d_val}")
    for k in range(1, 11): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=357-{k}&d=2&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=357-11&d=1&dw={d_val}")
    for k in range(1, 11): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=357-{11-k}&d=1&dw={d_val}")

    other_lines = [
        ("H", 354, 3), ("I", 353, 7), ("J", 358, 2), ("K", 409, 10, True), 
        ("L", 415, 5, True), ("N", 351, 2), ("O", 355, 7), ("P", 359, 3)
    ]
    for line_info in other_lines:
        code = line_info[1]
        max_k = line_info[2]
        is_one_based = len(line_info) > 3 and line_info[3]
        start = 1 if is_one_based else 0
        urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode={code}-{start}&d=1&dw={d_val}")
        for k in range(start + 1, max_k):
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode={code}-{k}&d=2&dw={d_val}")
        urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode={code}-{max_k}&d=1&dw={d_val}")
        for k in range(start + 1, max_k):
            back_idx = max_k - k if not is_one_based else (max_k + 1) - k
            urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode={code}-{back_idx}&d=1&dw={d_val}")

    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=452-1&d=1&dw={d_val}")
    for k in range(2, 14): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=452-{k}&d=2&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=453-1&d=1&dw={d_val}")
    for k in range(2, 5): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=453-{k}&d=2&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=454-1&d=1&dw={d_val}")
    for k in range(2, 16): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=454-{k}&d=2&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=454-16&d=1&dw={d_val}")
    for k in range(2, 16): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=454-{17-k}&d=1&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=453-5&d=1&dw={d_val}")
    for k in range(2, 5): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=453-{6-k}&d=1&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=452-14&d=1&dw={d_val}")
    for k in range(2, 14): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=452-{15-k}&d=1&dw={d_val}")

    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=665-0&d=1&dw={d_val}")
    for k in range(1, 4): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=665-{k}&d=2&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=665-4&d=1&dw={d_val}")
    for k in range(1, 4): urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=665-{4-k}&d=1&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=666-0&d=1&dw={d_val}")
    urls.append(f"https://eki.kintetsu.co.jp/norikae/T5?USR=PC&slCode=666-1&d=1&dw={d_val}")

    return urls

def fetch_station_page(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    found_trains = []
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'shift_jis'
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'T7?' in href:
                    params = parse_qs(urlparse(href).query)
                    tx = params.get('tx', [None])[0]
                    dw = params.get('dw', [None])[0]
                    sf = params.get('sf', [None])[0]
                    if tx:
                        found_trains.append({"tx": tx, "dw": dw, "sf": sf})
    except Exception:
        pass
    return found_trains


def fetch_train_detail(tx, sf, dw):
    url = f"https://eki.kintetsu.co.jp/norikae/T7?sf={sf}&tx={tx}&dw={dw}"
    for _ in range(3):
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.encoding = 'shift_jis'
            if response.status_code != 200:
                continue
            soup = BeautifulSoup(response.text, 'html.parser')
            header_cell = soup.find('td', {'bgcolor': '#FFB334', 'colspan': '3'})
            if not header_cell:
                return None
            header_text = header_cell.get_text(strip=True)
            meta_match = re.search(r'(.*?)\s+(.*?行き.*?)\s+(.*)のダイヤ', header_text)
            if meta_match:
                train_type, direction, date_type = (g.strip() for g in meta_match.groups())
            else:
                train_type, direction, date_type = "Unknown", header_text, "Unknown"

            stop_data = []
            for row in soup.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) != 3:
                    continue
                station_text = cells[0].get_text(strip=True)
                if station_text in ["停車駅", ""]:
                    continue
                stop_data.append({
                    "station": station_text,
                    "arr": convert_to_minutes(cells[1].get_text(strip=True).replace('\xa0', '')),
                    "dep": convert_to_minutes(cells[2].get_text(strip=True).replace('\xa0', '')),
                })
            return {"no": tx, "type": train_type, "dir": direction, "date": date_type, "data": stop_data}
        except Exception:
            continue
    return None


def origin_of(train):
    match = re.search(r'始発駅[：:]\s*([^）\)]+)', train.get("dir", ""))
    return match.group(1).strip() if match else None


def run_parallel(fn, jobs, desc):
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(fn, *job): job for job in jobs}
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc=desc):
            results[futures[future]] = future.result()
    return results


def scrape(d_val, output_filename):
    day_name = "Weekday" if d_val == 0 else "Weekend/Holiday"
    print(f"\n🚀 [{day_name}] 1/3 掃描車站獲取車次清單...")

    pages = run_parallel(fetch_station_page, [(u,) for u in get_all_station_urls(d_val)], "掃描中")
    candidates = {}  # tx -> {sf: dw}
    for trains in pages.values():
        for t in trains:
            candidates.setdefault(t['tx'], {})[t['sf']] = t['dw']

    print(f"\n🚀 [{day_name}] 2/3 抓取 {len(candidates)} 班車...")
    jobs = [(tx, next(iter(sfs)), next(iter(sfs.values()))) for tx, sfs in candidates.items()]
    trains = {job[0]: res for job, res in run_parallel(fetch_train_detail, jobs, "抓取中").items() if res}

    # T7 以 sf 站為首站 → 由此得到 sf→站名
    sf_name = {}
    for (tx, sf, dw) in jobs:
        tr = trains.get(tx)
        if tr and tr["data"]:
            sf_name[sf] = tr["data"][0]["station"]

    print(f"\n🚀 [{day_name}] 3/3 補回被截頭的車次...")
    for rnd in range(1, 11):
        refetch = []
        for tx, tr in trains.items():
            seen = {st["station"] for st in tr["data"]}
            # 站名未知的 sf（常是終點站：從沒被當成第一次抓取的 sf）也可能在上游，抓一次就知道
            upstream = [sf for sf in candidates[tx] if sf_name.get(sf) not in seen]
            if not upstream:
                continue
            # 優先：始発駅的 sf → 站名未知的 sf → 任一已知上游站（下一輪再繼續往前）
            origin = origin_of(tr)
            best = (next((sf for sf in upstream if sf_name.get(sf) == origin), None)
                    or next((sf for sf in upstream if sf not in sf_name), None)
                    or upstream[0])
            refetch.append((tx, best, candidates[tx][best]))
        if not refetch:
            break
        fixed = 0
        for (tx, sf, dw), res in run_parallel(fetch_train_detail, refetch, f"第 {rnd} 輪").items():
            if res and res["data"]:
                sf_name[sf] = res["data"][0]["station"]
            if res and len(res["data"]) > len(trains[tx]["data"]):
                trains[tx] = res
                fixed += 1
            else:
                # 抓不到或沒變長：把這個 sf 從候選移除，避免無限重抓
                candidates[tx].pop(sf, None)
        print(f"   第 {rnd} 輪：重抓 {len(refetch)} 班，延長 {fixed} 班")

    result = sorted(trains.values(), key=lambda x: x["no"])
    output_path = os.path.join(JSON_DIR, f'{output_filename}.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("[\n")
        for i, train in enumerate(result):
            f.write("  " + json.dumps(train, ensure_ascii=False, separators=(',', ':')))
            f.write(",\n" if i < len(result) - 1 else "\n")
        f.write("]\n")
    print(f"🎉 [{day_name}] {len(result)} 班 → {os.path.abspath(output_path)}")


if __name__ == "__main__":
    print("⚡ 啟動近鐵時刻表爬蟲 ⚡")
    scrape(0, "raw_weekday")
    print("-" * 60)
    scrape(1, "raw_holiday")
    print("\n🏆 所有作業執行完畢！接著執行 convert_timetable.py")
