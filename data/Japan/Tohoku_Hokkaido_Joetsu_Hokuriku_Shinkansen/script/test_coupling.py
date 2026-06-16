import requests
from bs4 import BeautifulSoup
import re

# 使用你提供的 2026/05 有效網址
TEST_URL = "https://timetables.jreast.co.jp/2605/train/030/033751.html" 
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def test_semantic_logic():
    print(f"🚀 [Unit Test] 正在驗證『語義解析法』...")
    
    try:
        res = requests.get(TEST_URL, headers=HEADERS, timeout=10)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, 'html.parser')
        
        train_div = soup.find('div', class_='trainlist')
        table = train_div.find('table')
        
        # --- 1. 抓取車次編號與索引 ---
        train_nos = []
        for tr in table.find_all('tr'):
            if '列車番号' in tr.get_text():
                train_nos = [td.get_text().strip() for td in tr.find_all('td')]
                break
        print(f"📋 偵測到車次清單：{train_nos}")

        # --- 2. 抓取『併結運転』欄位資訊 ---
        coupling_info_raw = {}
        for tr in table.find_all('tr'):
            th = tr.find('th')
            if th and '併結運転' in th.get_text():
                tds = tr.find_all('td')
                for idx, td in enumerate(tds):
                    coupling_info_raw[idx] = td.get_text().strip()
                break

        if not coupling_info_raw:
            print("❌ 錯誤：找不到『併結運転』欄位。")
            return

        # --- 3. 模擬 153B 與 153M 的解析流程 ---
        for idx, no in enumerate(train_nos):
            if no not in ["153B", "153M"]: continue
            
            info_text = coupling_info_raw.get(idx, "")
            print(f"\n🔍 正在分析車次 {no} 的文字：'{info_text}'")
            
            # 使用正則表達式提取目標車次與車站
            # 1. 提取目標車次 (例如 153M)
            target_no_match = re.search(r'(\d+[A-Z])', info_text)
            # 2. 提取解連車站 (例如從 "東京－福島" 提取 "福島")
            station_match = re.search(r'－([^は]+)', info_text)
            
            if target_no_match and station_match:
                target_no = target_no_match.group(1)
                split_sta = station_match.group(1)
                print(f"   ✅ 解析成功！")
                print(f"   🔗 伴侶車次：{target_no}")
                print(f"   🚉 解連車站：{split_sta}")
            else:
                print("   ❌ 無法從文字中解析併結資訊。")

    except Exception as e:
        print(f"🔥 測試發生異常: {e}")

if __name__ == "__main__":
    test_semantic_logic()