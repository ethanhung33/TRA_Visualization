import requests
from bs4 import BeautifulSoup
import re
import unicodedata
import hashlib
from urllib.parse import urljoin
from datetime import date, timedelta

# ==========================================
# ⚙️ 基礎設定與工具
# ==========================================
START_DATE = date(2026, 5, 25)
END_DATE = date(2026, 9, 30)

def get_reference_sets():
    weekdays, weekends = set(), set()
    curr = START_DATE
    while curr <= END_DATE:
        d_str = curr.strftime("%Y-%m-%d")
        if curr.weekday() < 5: weekdays.add(d_str)
        else: weekends.add(d_str)
        curr += timedelta(days=1)
    return weekdays, weekends

REF_WEEKDAY, REF_WEEKEND = get_reference_sets()

def parse_calendar_logic(soup, current_url):
    current_dates = set()
    variant_urls = set()
    calendar_div = soup.find('div', class_='serviceDayCalendar')
    if not calendar_div: return current_dates, list(variant_urls)

    for table in calendar_div.find_all('table', class_='calendar-month'):
        caption = table.find('caption')
        if not caption: continue
        ym = re.search(r'(\d{4})年(\d{1,2})月', caption.text)
        if not ym: continue
        y, m = int(ym.group(1)), int(ym.group(2))
        
        for td in table.find_all('td'):
            classes = td.get('class', [])
            if 'invalid' in classes: continue
            
            a_tag = td.find('a')
            if a_tag:
                target_str = a_tag.get('href', '') + " " + a_tag.get('onclick', '')
                match = re.search(r"([a-zA-Z0-9_/]+\.html)", target_str)
                if match: variant_urls.add(urljoin(current_url, match.group(1)))
            elif 'none' not in classes:
                day_text = td.get_text(strip=True)
                if day_text.isdigit():
                    d = int(day_text)
                    if START_DATE <= date(y, m, d) <= END_DATE:
                        current_dates.add(f"{y}-{m:02d}-{d:02d}")
                        
    return current_dates, list(variant_urls)

def parse_japanese_dates(text, default_year=2026):
    if not text: return []
    text = unicodedata.normalize('NFKC', text)
    text = text.replace('運転', '').strip()
    dates = []
    parts = re.split(r'(\d+)月', text)
    for i in range(1, len(parts), 2):
        month = int(parts[i])
        days_str = parts[i+1].replace('日', '').strip('・')
        for part in days_str.split('・'):
            if not part: continue
            if '～' in part or '~' in part or '-' in part:
                bounds = re.split(r'[～~-]', part)
                if len(bounds) == 2 and bounds[0].isdigit() and bounds[1].isdigit():
                    for d in range(int(bounds[0]), int(bounds[1]) + 1):
                        dates.append(f"{default_year}-{month:02d}-{d:02d}")
            elif part.isdigit():
                dates.append(f"{default_year}-{month:02d}-{int(part):02d}")
    return sorted(list(set(dates)))

def fetch_train_from_url(url, target_no="3034B"):
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, 'html.parser')
        
        page_dates, variants = parse_calendar_logic(soup, url)
        train_div = soup.find('div', class_='trainlist')
        if not train_div: return None, variants
            
        table = train_div.find('table')
        train_nos, op_dates_text = [], {}
        
        for tr in table.find_all('tr'):
            th = tr.find('th')
            if not th: continue
            if '列車番号' in th.get_text(): 
                train_nos = [td.get_text().strip() for td in tr.find_all('td')]
            elif '運転日' in th.get_text(): 
                for idx, td in enumerate(tr.find_all('td')): op_dates_text[idx] = td.get_text().strip()

        for i, tno in enumerate(train_nos):
            if target_no in tno:
                op_text = op_dates_text.get(i, "")
                parsed_dates = parse_japanese_dates(op_text)
                
                is_implicit = False
                if parsed_dates:
                    assigned = set(parsed_dates)
                    reason = "文字指定"
                elif "土曜・休日" in op_text:
                    assigned = set(REF_WEEKEND)
                    reason = "文字指定 (假日)"
                elif "平日" in op_text:
                    assigned = set(REF_WEEKDAY)
                    reason = "文字指定 (平日)"
                elif page_dates:
                    assigned = set(page_dates)
                    reason = "日曆指定"
                else:
                    assigned = REF_WEEKDAY.union(REF_WEEKEND)
                    is_implicit = True
                    reason = "無文字無日曆 (隱含基本排班)"
                    
                return {"url": url, "dates": assigned, "is_implicit": is_implicit, "reason": reason}, variants
                
        return None, variants
    except Exception as e:
        return None, []

# ==========================================
# 🧠 測試主程式
# ==========================================
# ==========================================
# 🧠 測試主程式
# ==========================================
def test_all_variants_and_deduce(start_url, target_no="3034B"):
    first_data, variant_urls = fetch_train_from_url(start_url, target_no)
    all_urls_to_visit = list(set([start_url] + variant_urls))
    
    print(f"🔍 總共發現 {len(all_urls_to_visit)} 個變體網頁，開始走訪...\n")
    collected_data = []
    for idx, url in enumerate(all_urls_to_visit):
        print(f"  [{idx+1}/{len(all_urls_to_visit)}] 抓取中...", end="\r")
        data, _ = fetch_train_from_url(url, target_no)
        if data: collected_data.append(data)
            
    # 🌟 模擬主程式的扣除引擎 🌟
    explicit_dates = set()
    for d in collected_data:
        if not d["is_implicit"]: explicit_dates.update(d["dates"])
            
    for d in collected_data:
        if d["is_implicit"]: d["dates"] = d["dates"] - explicit_dates

    final_data = [d for d in collected_data if len(d["dates"]) > 0]

    print("\n\n" + "="*50)
    print("📊 【第一階段：剛爬下來的原始分配狀態】")
    print("="*50)
    for idx, d in enumerate(collected_data):
        flag = "🔴 隱含排班 (將被扣除)" if d["is_implicit"] else "🟢 明確排班 (優先保留)"
        print(f"變體 {idx+1} | 天數: {len(d['dates']):>3} | {flag} | 理由: {d['reason']}")
        print(f"  🔗 網址: {d['url']}\n") # 🌟 新增：印出網址

    print("="*50)
    print("✨ 【第二階段：經過扣除引擎校正後的狀態與日期透視】")
    print("="*50)
    
    for idx, d in enumerate(final_data):
        flag = "🔴 隱含排班 (扣剩餘額)" if d["is_implicit"] else "🟢 明確排班 (完整保留)"
        days_list = sorted(list(d['dates']))
        
        # 計算這組日期的 Hash 密碼
        dates_hash = hashlib.md5(str(days_list).encode()).hexdigest()[:6]
        
        print(f"變體 {idx+1} | 天數: {len(days_list):>3} | 🔑特徵碼: [{dates_hash}] | {flag}")
        print(f"  🔗 網址: {d['url']}") # 🌟 新增：印出網址
        
        # 印出具體日期
        if len(days_list) <= 6:
            print(f"  🗓️ {days_list}\n")
        else:
            print(f"  🗓️ {days_list[:3]} ... ({len(days_list)-6}天省略) ... {days_list[-3:]}\n")

    # 🌟 模擬主程式的去重引擎 🌟
    print("="*50)
    print("🧹 【第三階段：啟動去重引擎 (Deduplication)】")
    print("="*50)
    
    unique_data = []
    seen_sigs = set()
    
    for d in final_data:
        days_list = sorted(list(d['dates']))
        sig = tuple(days_list) # 以日期陣列作為唯一特徵
        
        if sig not in seen_sigs:
            seen_sigs.add(sig)
            unique_data.append(d)
        else:
            print(f"  🗑️ 攔截到幽靈分身！(網址: {d['url']}) 當場銷毀！") # 🌟 順便印出被殺掉的是哪個網址

    total_days = sum(len(d['dates']) for d in unique_data)
    
    print("-" * 50)
    print(f"✅ 去重完成！從 {len(final_data)} 個變體中，銷毀了 {len(final_data) - len(unique_data)} 個幽靈分身。")
    print(f"✅ 最終只留下 {len(unique_data)} 個真正獨立的排班時刻表！")
    print(f"📅 {target_no} 總營運天數 (無重複): {total_days} 天")

if __name__ == "__main__":
    test_all_variants_and_deduce("https://timetables.jreast.co.jp/2606/train/050/051804.html", "3034B")