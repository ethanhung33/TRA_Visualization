import urllib.request
import re
import json
import os
from datetime import datetime

# 替換成你的實際路徑
ROUTE_PATH = r"D:\鐵路\TRA_Visualization\data\Japan\Tokkaido_Sanyo_Kyushu_Shinkansen\json\station_route_shinkansen.json"
HEADERS = {'User-Agent': 'Mozilla/5.0'}
# 使用今天的日期，避免 Odekake 網站拒絕未來的查詢
TARGET_DATE = datetime.now().strftime("%Y%m%d") 

def clean_text(text):
    return "".join(re.sub(r'<[^>]+>', '', text).split())

def run_verification():
    print("🌊 階段 1：讀取路線 JSON，自動尋找北陸新幹線 ID...")
    with open(ROUTE_PATH, 'r', encoding='utf-8') as f:
        routes = json.load(f)
        
    r_id = None
    for r in routes:
        if "北陸" in r.get("route", "") and "本線" not in r.get("route", ""):
            r_id = r.get("id")
            print(f"✅ 找到北陸新幹線的站點 ID: {r_id}")
            break
            
    if not r_id:
        print("❌ 找不到北陸新幹線的 ID，請檢查 JSON。")
        return
        
    url = f"https://timetable.jr-odekake.net/station-timetable/{r_id}?date={TARGET_DATE}"
    print(f"🔗 正在請求: {url}")
    
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8')
            train_ids = list(set(re.findall(r'href="/train-timetable/(\d+)\?date=', html)))
    except Exception as e:
        print(f"❌ 網路請求失敗: {e}")
        return
        
    if not train_ids:
        print("❌ 找不到車次連結。")
        return
        
    t_id = train_ids[0]
    t_url = f"https://timetable.jr-odekake.net/train-timetable/{t_id}?date={TARGET_DATE}"
    print(f"\n🚄 階段 2：成功抽測單一車次，正在解析網頁...")
    print(f"🔗 車次網址: {t_url}")
    
    req = urllib.request.Request(t_url, headers=HEADERS)
    with urllib.request.urlopen(req) as response:
        html = response.read().decode('utf-8')
        
        # 1. 檢查表頭 (看車種是不是叫 "列車名")
        details_match = re.search(r'<tbody class="train-details">(.*?)</tbody>', html, re.DOTALL)
        if details_match:
            print("\n🔍 [表頭欄位解析測試]")
            rows = re.findall(r'<tr>(.*?)</tr>', details_match.group(1), re.DOTALL)
            for row in rows:
                th_match = re.search(r'<th.*?>(.*?)</th>', row, re.DOTALL)
                if th_match:
                    key = clean_text(th_match.group(1))
                    tds = re.findall(r'<td.*?>(.*?)</td>', row, re.DOTALL)
                    val = clean_text(tds[0]) if tds else ""
                    print(f"   ▶ {key}: {val}")
                    
        # 2. 檢查時刻表 (看時間的 HTML 格式長怎樣)
        time_match = re.search(r'<tbody class="time-details">(.*?)</tbody>', html, re.DOTALL)
        if not time_match:
            print("❌ 找不到時刻表主體")
            return
            
        time_rows = re.findall(r'<tr>(.*?)</tr>', time_match.group(1), re.DOTALL)
        print("\n🔍 [時刻表時間解析測試 (前 3 站)]")
        for row in time_rows[:3]:
            sta_match = re.search(r'<td class="cell-fixed">(.*?)</td>', row, re.DOTALL)
            if not sta_match: continue
            
            sta_name = clean_text(sta_match.group(1))
            data_cells = re.findall(r'<td.*?>(.*?)</td>', row, re.DOTALL)[1:]
            raw_cell = data_cells[0] if data_cells else ""
            
            times = re.findall(r'(\d{2}:\d{2})', raw_cell)
            print(f"   ▶ 站名: {sta_name:5s} | 抓到的時間: {times}")
            print(f"     原始 HTML: {raw_cell.strip()[:60]}...")

if __name__ == "__main__":
    run_verification()