import json
from pathlib import Path

output_dir = Path(__file__).parent.parent / "json"
timetable_dir = output_dir / "timetable"
if not timetable_dir.exists():
    print(f"⚠️ 時刻表資料夾不存在：{timetable_dir}")
all_files = timetable_dir.glob("timetable_*.json")
available_dates = []

for f in all_files:
    # 從檔名 timetable_20260420.json 萃取出 2026-04-20
    date_str = f.stem.split('_')[1]
    if len(date_str) == 8:
        formatted = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        available_dates.append(formatted)
        
# 排序日期 (由舊到新)
available_dates.sort()

with open(output_dir / "available_dates.json", "w", encoding="utf-8") as f:
    json.dump(available_dates, f)
    
print(f"📅 已更新可用日期清單：{available_dates}")