from pathlib import Path
import requests
import json

# 設定你要抓取的日期 (格式: YYYY-MM-DD)
date_str = "2026-04-30" 
url = f"https://tdx.transportdata.tw/api/basic/v2/Rail/THSR/DailyTimetable/TrainDate/{date_str}?%24format=JSON"

SCRIPT_DIR = Path(__file__).parent
JSON_DIR = SCRIPT_DIR.parent / "json"

# 【關鍵】偽裝成一般瀏覽器，破解 TDX 的未註冊阻擋機制
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
}

print(f"正在以免註冊模式下載 {date_str} 的 TDX 高鐵資料...")
response = requests.get(url, headers=headers)

if response.status_code == 200:
    data = response.json()
    file_name = JSON_DIR / f"raw_data/timetable_{date_str}.json"

    # 將資料存成本地 JSON 檔，方便你的運行圖程式重複讀取
    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        
    print(f"✅ 下載成功！共抓到 {len(data)} 筆車次資料，已存入 {file_name}")
else:
    print(f"❌ 下載失敗，狀態碼: {response.status_code}")