import requests
from bs4 import BeautifulSoup
import csv
import time

# 直搗黃龍：往 豊岡・京都・大阪 方面的真實時刻表網址
url = "https://timetable.jr-odekake.net/station-timetable/3220024002"
headers = {"User-Agent": "Mozilla/5.0"}

print("開始獲取城崎溫泉站時刻表...")
response = requests.get(url, headers=headers)
response.encoding = "utf-8"
soup = BeautifulSoup(response.text, "html.parser")

# 鎖定包含完整資訊的「手機版排版區塊」
sp_wrap = soup.find("div", class_="sp-time-tbl-wrap")

# 在這個區塊內，每一班列車的資訊都被包在 class 為 'minute-item' 的 div 裡
trains = sp_wrap.find_all("div", class_="minute-item")

# 使用 utf-8-sig 編碼，確保用 Excel 打開 CSV 時日文漢字不會變成亂碼
with open("kinosaki_timetable_final.csv", mode="w", encoding="utf-8-sig", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(tuple(("發車時間", "車種與列車名", "目的地")))

    for train in trains:
        # 根據你提供的 HTML 結構，精準抓取對應的 class
        time_tag = train.find("div", class_="departure-time")
        type_tag = train.find("div", class_="train-name")
        dest_tag = train.find("div", class_="destination")

        # 確保三個標籤都有抓到，才進行文字清理與寫入
        if time_tag and type_tag and dest_tag:
            departure_time = time_tag.text.strip()
            # 將車種內多餘的空白或換行濾掉
            train_type = type_tag.text.strip().replace("\n", "").replace(" ", "")
            destination = dest_tag.text.strip()
            
            writer.writerow(tuple((departure_time, train_type, destination)))

print("✅ 爬取完成！已成功儲存為 'kinosaki_timetable_final.csv'")
time.sleep(2)