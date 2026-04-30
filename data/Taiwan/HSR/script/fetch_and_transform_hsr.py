import json
import requests
from pathlib import Path

from datetime import datetime, timedelta

# ---------------------------------------------------------
# 🌟 新增：日期區間產生器
# ---------------------------------------------------------
def generate_date_range(start_date_str, end_date_str):
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    
    delta = end_date - start_date
    date_list = []
    
    # 包含結束日期的每一天都產生出來
    for i in range(delta.days + 1):
        day = start_date + timedelta(days=i)
        date_list.append(day.strftime("%Y-%m-%d"))
        
    return date_list

# ---------------------------------------------------------
# 1. 核心轉換與寫檔函數 (維持你原本的完美壓縮格式)
# ---------------------------------------------------------
def time_to_minutes(time_str):
    """將 HH:MM 轉換為分鐘數，處理跨夜邏輯"""
    if not time_str:
        return 0
    h, m = map(int, time_str.split(':'))
    if h < 4:
        h += 24
    return h * 60 + m

def generate_compact_json(data, output_path):
    """產生客製化壓縮格式的 JSON"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("[\n")
        for i, train in enumerate(data):
            f.write('  {\n')
            f.write(f'    "no": "{train["no"]}",\n')
            f.write(f'    "type": "{train["type"]}",\n')
            f.write('    "segments": [\n')
            
            seg_lines = []
            for seg in train["segments"]:
                seg_str = json.dumps(seg, ensure_ascii=False, separators=(',', ':'))
                seg_lines.append(f'      {seg_str}')
            
            f.write(",\n".join(seg_lines) + "\n")
            f.write('    ]\n')
            
            if i < len(data) - 1:
                f.write('  },\n')
            else:
                f.write('  }\n')
        f.write("]\n")

# ---------------------------------------------------------
# 2. 一條龍處理主邏輯：下載 -> 轉換 -> 存檔
# ---------------------------------------------------------
def process_date(date_str, json_dir):
    url = f"https://tdx.transportdata.tw/api/basic/v2/Rail/THSR/DailyTimetable/TrainDate/{date_str}?%24format=JSON"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
    }

    print(f"\n--- 處理日期: {date_str} ---")
    print(f"📡 正在以免註冊模式從 TDX 抓取資料...")
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"❌ 下載失敗，狀態碼: {response.status_code}")
        return False

    tdx_data = response.json()
    if not tdx_data:
        print(f"⚠️ {date_str} 沒有查到任何資料。")
        return False
        
    # 保存原始資料
    raw_dir = json_dir / "raw_data"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_file = raw_dir / f"timetable_{date_str}.json"
    with open(raw_file, "w", encoding="utf-8") as f:
        json.dump(tdx_data, f, ensure_ascii=False, indent=4)
    print(f"📥 原始資料已存入 {raw_file.name} (共 {len(tdx_data)} 筆)")

    # 轉換格式
    print(f"🔄 正在轉換成運行圖專用格式...")
    formatted_data = []
    for t in tdx_data:
        train_info = t.get('DailyTrainInfo', {})
        train_no = train_info.get('TrainNo', '')
        train_type = train_no[:2] if len(train_no) >= 2 else train_no
        
        s_list = []
        t_list = []
        v_list = []
        
        stops = sorted(t.get('StopTimes', []), key=lambda x: x.get('StopSequence', 0))
        for i, stop in enumerate(stops):
            s_list.append(stop.get('StationID'))
            arr = time_to_minutes(stop.get('ArrivalTime'))
            dep = time_to_minutes(stop.get('DepartureTime'))
            t_list.extend([arr, dep])
            
            if i == 0: v_list.append(0)
            elif i == len(stops) - 1: v_list.append(3)
            else: v_list.append(1)
                
        segment = {
            "id": "thsr_main",
            "s": s_list,
            "t": t_list,
            "v": v_list
        }
        
        formatted_data.append({
            "no": train_no,
            "type": train_type,
            "segments": [segment]
        })
        
    # 去除破折號並存檔
    remove_dash_date = date_str.replace("-", "")
    output_file = json_dir / "timetable" / f"timetable_{remove_dash_date}.json"
    generate_compact_json(formatted_data, output_file)
    print(f"✅ 轉換成功！已輸出至 {output_file.name}")
    
    return True

# ---------------------------------------------------------
# 3. 執行入口：選取多日期批量處理
# ---------------------------------------------------------
if __name__ == "__main__":
    SCRIPT_DIR = Path(__file__).parent
    JSON_DIR = SCRIPT_DIR.parent / "json"
    
    # 🌟 在這裡設定你想要的「開始日期」與「結束日期」
    start_date = "2026-04-30"
    end_date   = "2026-05-01"
    
    # 程式會自動幫你展開成 ['2026-04-25', '2026-04-26', ..., '2026-05-10']
    dates_to_fetch = generate_date_range(start_date, end_date)
    
    print(f"準備抓取從 {start_date} 到 {end_date} 共 {len(dates_to_fetch)} 天的資料...")
    
    successful_dates = []
    
    for d in dates_to_fetch:
        success = process_date(d, JSON_DIR)
        if success:
            successful_dates.append(d)
            
    # 自動更新 available_dates.json
    if successful_dates:
        dates_file = JSON_DIR / "available_dates.json"
        
        existing_dates = []
        if dates_file.exists():
            with open(dates_file, 'r', encoding='utf-8') as f:
                existing_dates = json.load(f)
                
        # 合併並排序日期，確保不重複
        all_dates = sorted(list(set(existing_dates + successful_dates)))
        
        with open(dates_file, 'w', encoding='utf-8') as f:
            json.dump(all_dates, f, indent=4)
        print(f"\n📅 已自動將剛抓好的日期更新至 available_dates.json")
        print(f"🎉 任務全數完成！目前高鐵系統共有 {len(all_dates)} 個日期可供查看。")