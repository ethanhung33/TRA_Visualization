import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

# 這是 157B 在 5/1 的專屬網址
url = "https://timetables.jreast.co.jp/2605/train/025/029872.html"
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

print(f"🚀 正在抓取測試網址: {url}\n" + "="*50)
res = requests.get(url, headers=HEADERS)
res.encoding = res.apparent_encoding
soup = BeautifulSoup(res.text, 'html.parser')

calendar_div = soup.find('div', class_='serviceDayCalendar')
if not calendar_div:
    print("❌ 找不到日曆區塊！(可能是網頁結構變更，或被伺服器阻擋)")
else:
    print("✅ 成功找到日曆區塊！開始分析 5 月份的每一天...\n")
    for table in calendar_div.find_all('table', class_='calendar-month'):
        caption = table.find('caption')
        if caption and "5月" in caption.text:
            for td in table.find_all('td'):
                day_text = td.get_text(strip=True)
                if not day_text.isdigit(): 
                    continue
                
                a_tag = td.find('a')
                if a_tag:
                    href = a_tag.get('href', '')
                    onclick = a_tag.get('onclick', '')
                    target_str = f"href=\"{href}\" | onclick=\"{onclick}\""
                    print(f"🔍 [5月{day_text.zfill(2)}日] 有連結 -> {target_str}")
                    
                    # 測試：原本的正則表達式
                    match1 = re.search(r"([a-zA-Z0-9_/]+\.html)", target_str)
                    # 測試：放寬條件的正則表達式 (允許 . 和 -)
                    match2 = re.search(r"['\"]([^'\"]*\.html)['\"]", target_str)
                    
                    if not match1:
                        print(f"   ⚠️ 原本的正則：抓取失敗！")
                    if match2:
                        print(f"   ✅ 放寬的正則：{urljoin(url, match2.group(1))}")
                    print("-" * 50)
                else:
                    print(f"⚪ [5月{day_text.zfill(2)}日] 無連結 (當前頁面或無營運)")