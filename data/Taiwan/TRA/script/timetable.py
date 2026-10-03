"""
台鐵時刻表：從交通部 ODS 開放資料下載每日 JSON 並轉檔
https://ods.railway.gov.tw/tra-ods-web/ods/download/dataResource/railway_schedule/JSON/list

一天一個檔（約 2 MB），只列停靠站；通過站 / 分岔站 / 成追線由 timetable_web 的編譯邏輯補上。
ODS 只提供約 60 天內的資料，更遠的日期可用 timetable_web.py（官網爬蟲）備援。
"""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from tqdm import tqdm

# 共用拓撲讀取、SSL session 與編譯邏輯
from timetable_web import (SESSION, STATION_INFO, JSON_DIR,
                           time_to_min, patch_chengzhui, compile_train_data)

ODS_BASE = "https://ods.railway.gov.tw"
LIST_URL = f"{ODS_BASE}/tra-ods-web/ods/download/dataResource/railway_schedule/JSON/list"

# CarClass → 車種（對應 setting.json 的 train_color）
CAR_CLASS_MAP = {
    "1101": "太魯閣",
    "1104": "自強",      # 1104/1106 官網標「自強(專)」，如環島之星
    "1107": "普悠瑪",
    "1106": "自強",
    "1108": "自強", "1109": "自強", "110A": "自強", "110F": "自強",
    "110G": "新自強", "110H": "新自強", "110K": "新自強", "110M": "新自強",
    "1110": "莒光", "1112": "莒光",  # 1112 官網標「莒光(專)」
    "1131": "區間", "1130": "區間", "1134": "區間",
    "1132": "區間快",
    "1150": "普快",
}
# 未知代碼依前三碼推測
CAR_CLASS_PREFIX = {"110": "自強", "111": "莒光", "112": "復興", "113": "區間", "114": "普快", "115": "普快"}

ID_TO_NAME = {info["id"]: name for name, info in STATION_INFO.items()}


def car_class_to_type(code, train_kind):
    if code in CAR_CLASS_MAP:
        t = CAR_CLASS_MAP[code]
    else:
        t = CAR_CLASS_PREFIX.get(code[:3], "區間")
        tqdm.write(f"⚠️ 未知 CarClass {code}，暫以「{t}」處理")
    if train_kind == "4":  # 專列（觀光、包車等，如海風號、藍皮解憂號）獨立成一個車種
        t += "專列"
    return t


def fetch_file_list():
    resp = SESSION.get(LIST_URL, timeout=30)
    resp.raise_for_status()
    files = re.findall(r'href="([^"]+)"[^>]*>\s*(\d{8})\.json', resp.text)
    return {date: ODS_BASE + href for href, date in files}


def convert_train(t):
    raw_stops, last_time = [], -1
    for ti in sorted(t["TimeInfos"], key=lambda x: int(x["Order"])):
        name = ID_TO_NAME.get(ti["Station"])
        if not name:
            continue  # 支線等拓撲外車站
        arr, dep = time_to_min(ti["ARRTime"]), time_to_min(ti["DEPTime"])
        if arr < last_time: arr += 1440
        if dep < arr: dep += 1440
        last_time = dep
        raw_stops.append({"name": name, "arr": arr, "dep": dep, "is_pass": False})

    if len(raw_stops) < 2:
        return None
    segments = compile_train_data(patch_chengzhui(raw_stops))
    if not segments:
        return None
    return {"no": t["Train"], "type": car_class_to_type(t["CarClass"], t["Type"]), "segments": segments}


def process_date(date, url, output_dir):
    resp = SESSION.get(url, timeout=60)
    resp.raise_for_status()
    data = json.loads(resp.content.decode("utf-8"))

    results = [r for r in (convert_train(t) for t in data["TrainInfos"]) if r]
    if not results:
        raise ValueError("轉檔後沒有任何車次")
    results.sort(key=lambda x: int(re.sub(r'\D', '', x["no"]) or 0))

    output_path = output_dir / f"timetable_{date}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("[\n")
        f.write(",\n".join(json.dumps(r, ensure_ascii=False, separators=(',', ':')) for r in results))
        f.write("\n]\n")
    return len(results)


def main():
    files = fetch_file_list()
    today = datetime.now().strftime("%Y%m%d")
    # 可指定日期：py timetable.py 20261001 20261002
    wanted = sys.argv[1:] or [d for d in files if d >= today]
    targets = sorted(d for d in wanted if d in files)
    missing = sorted(set(wanted) - set(files))
    if missing:
        print(f"⚠️ ODS 沒有這些日期：{missing}")
    if not targets:
        print("❌ 沒有可下載的日期，中止。")
        sys.exit(1)

    print(f"🗓️ ODS 下載 {targets[0]} ~ {targets[-1]}（共 {len(targets)} 天）")
    output_dir = JSON_DIR / "timetable"
    output_dir.mkdir(parents=True, exist_ok=True)

    errors = 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(process_date, d, files[d], output_dir): d for d in targets}
        for f in tqdm(as_completed(futures), total=len(futures), desc="下載與轉檔"):
            d = futures[f]
            try:
                f.result()
            except Exception as e:
                errors += 1
                tqdm.write(f"❌ {d} 失敗：{e!r}")

    print(f"\n🚀 完成 {len(targets) - errors}/{len(targets)} 天")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
