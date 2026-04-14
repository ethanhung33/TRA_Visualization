import pandas as pd
import requests
from io import StringIO
import re
import json
from bs4 import BeautifulSoup  # 💡 新增匯入 BeautifulSoup

WIKI_URLS = {
    "南海本線": "https://ja.wikipedia.org/wiki/南海本線",
    "空港線": "https://ja.wikipedia.org/wiki/南海空港線",
    "加太線": "https://ja.wikipedia.org/wiki/南海加太線",
    "多奈川線": "https://ja.wikipedia.org/wiki/南海多奈川線",
    "和歌山港線": "https://ja.wikipedia.org/wiki/南海和歌山港線",
    "高師浜線": "https://ja.wikipedia.org/wiki/南海高師浜線",
    "高野線": "https://ja.wikipedia.org/wiki/南海高野線",
    "泉北線": "https://ja.wikipedia.org/wiki/泉北高速鉄道線",
    
    # 💡 修正：換回日文維基百科的網址！(日文版的錨點一樣叫 汐見橋線)
    "高野線（汐見橋方面）": "https://ja.wikipedia.org/wiki/南海高野線#汐見橋線",
    
    "高野山ケーブル": "https://ja.wikipedia.org/wiki/南海鋼索線"
}

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
global_distances = {line: {} for line in WIKI_URLS.keys()}

def clean_station_name(name):
    if pd.isna(name): return name
    # 1. 移除維基百科的引用備註，如 [* 1]
    name = re.sub(r'\[.*?\]', '', str(name))
    
    # 2. 移除所有類型的括號及其內容 (包含和歌山大學前的「（ふじと台）」)
    name = re.sub(r'\(.*?\)', '', name) 
    name = re.sub(r'（.*?）', '', name) 
    
    # 3. 移除「駅」字、待避站符號「#」並修剪空白
    name = name.replace("駅", "").replace("#", "").strip()
    return name

print("🚀 開始爬取南海全家族里程 (已整合汐見橋線精準抓取)...\n")

for line_name, url in WIKI_URLS.items():
    print(f"正在掃描: {line_name} ...")
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status() 
        
        # 💡 終極解法：放棄尋找 HTML 標籤，直接用「指紋」過濾表格！
        if line_name == "高野線（汐見橋方面）":
            try:
                # 叫 pandas 直接掃描全網頁，只挑出裡面含有「芦原町」這個專屬站名的表格！
                tables = pd.read_html(StringIO(response.text), match="芦原町")
            except ValueError:
                print("  ❌ 找不到包含「芦原町」的專屬表格")
                tables = []
        else:
            # 其他路線維持原本的抓法
            tables = pd.read_html(StringIO(response.text))
            
        target_df = None
        for df in tables:
            # ... (下面維持你原本壓平表頭的邏輯) ...
            # 壓平多層表頭並解決欄位重複問題
            df.columns = ['_'.join(str(c) for c in col).strip() if isinstance(col, tuple) else str(col) for col in df.columns]
            df = df.loc[:, ~df.columns.duplicated()]
            
            col_str = "".join(df.columns)
            if "駅名" in col_str and "キロ" in col_str:
                target_df = df
                break
                
        if target_df is None:
            print(f"  ❌ 找不到 {line_name} 的車站表格")
            continue
            
        st_col = next((c for c in target_df.columns if "駅名" in c), None)
        dist_col = next((c for c in target_df.columns if "駅間" in c and "キロ" in c), None)
        is_cumulative = False
        
        if not dist_col:
            dist_col = next((c for c in target_df.columns if "キロ" in c), None)
            is_cumulative = True
            
        count = 0
        current_cumulative_dist = 0.0 
        
        for index, row in target_df.iterrows():
            raw_st = row[st_col]
            st_name = clean_station_name(raw_st)
            dist_val = row[dist_col]
            
            if pd.notna(st_name) and st_name != "nan":
                if "駅名" in st_name or st_name == "": continue
                
                # 💡 新增 1：號誌站殺手 (全線通用)
                # 只要站名裡面有「信号」兩個字 (例如 梶取信号所)，直接跳過不抓！
                if "信号" in st_name:
                    continue

                # 💡 新增 2：加太線專屬過濾器
                # 把直通運轉的「和歌山市」踢掉，讓里程乖乖從「紀ノ川」的 0.0 開始算
                if line_name == "加太線" and st_name == "和歌山市":
                    continue

                # 專屬南海本線的實體過濾器：移除今宮戎、萩ノ茶屋
                if line_name == "南海本線" and st_name in ["今宮戎", "萩ノ茶屋"]:
                    try:
                        val_str = str(dist_val).replace("km", "").strip()
                        if val_str not in ["-", "−", "", "nan"]:
                            current_cumulative_dist += float(val_str)
                    except: pass
                    continue
                
                try:
                    val_str = str(dist_val).replace("km", "").strip()
                    if val_str in ["-", "−", "", "nan"]:
                        val = 0.0
                    else:
                        val = float(val_str)
                    
                    if not is_cumulative:
                        current_cumulative_dist += val
                    else:
                        current_cumulative_dist = val 
                        
                    global_distances[line_name][st_name] = round(current_cumulative_dist, 1)
                    count += 1
                    
                except ValueError:
                    pass 
                    
        print(f"  ✅ 成功抓取並累加 {count} 個車站！")
        
    except Exception as e:
        print(f"  ❌ 請求 {line_name} 失敗: {e}")

# 輸出最終 JSON
output_file = "Japan/Nankai/distance.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(global_distances, f, ensure_ascii=False, indent=4)

print(f"\n🎉 處理完畢！")
print(f"1. 所有的 '#' 已移除。")
print(f"2. 南海本線已剔除 今宮戎、萩ノ茶屋。")
print(f"3. 汐見橋線已成功避開本線表格，精準抓取！")