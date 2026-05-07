import requests
from bs4 import BeautifulSoup

def test_jreast_structure():
    # 我們拿最複雜、車種最多的「東京站」來當測試基準
    url = "https://www.jreast-timetable.jp/timetable/list1039.html"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    print(f"正在請求測試網址: {url}")
    res = requests.get(url, headers=headers)
    res.encoding = 'utf-8'
    soup = BeautifulSoup(res.text, 'html.parser')
    
    # 找出網頁中所有的發車時刻表區塊
    tables = soup.find_all('div', class_='rosentable')
    
    print(f"\n找到 {len(tables)} 個時刻表區塊，開始解析結構：\n")
    print("=" * 50)
    
    for i, table in enumerate(tables):
        # 1. 看看它前一個兄弟節點（通常是標題）長怎樣
        prev_sibling = table.find_previous_sibling()
        heading_text = prev_sibling.get_text(strip=True) if prev_sibling else "【找不到前置標題】"
        
        # 2. 看看這個表格裡面的前 3 個目的地是寫什麼
        links = table.find_all('a', class_='fortimeLink')
        sample_links = []
        for a in links[:3]:
            # 抓取連結所在的 <tr> 裡面的文字 (目的地)
            row_tr = a.find_parent('tr')
            row_text = row_tr.get_text(strip=True) if row_tr else "【無內容】"
            sample_links.append(row_text)
            
        print(f"📦 [區塊 {i+1}]")
        print(f"👉 標題文字: {heading_text}")
        print(f"👉 內部樣本 (前3筆):")
        for sample in sample_links:
            print(f"   - {sample}")
        print("-" * 50)

if __name__ == "__main__":
    test_jreast_structure()