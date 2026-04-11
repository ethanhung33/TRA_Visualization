import pandas as pd
import requests
from io import StringIO
import re
import json

WIKI_URLS = {
    "南海本線": "https://ja.wikipedia.org/wiki/南海本線",
    "空港線": "https://ja.wikipedia.org/wiki/南海空港線",
    "加太線": "https://ja.wikipedia.org/wiki/南海加太線",
    "多奈川線": "https://ja.wikipedia.org/wiki/南海多奈川線",
    "和歌山港線": "https://ja.wikipedia.org/wiki/南海和歌山港線",
    "高師浜線": "https://ja.wikipedia.org/wiki/南海高師浜線",
    "高野線": "https://ja.wikipedia.org/wiki/南海高野線",
    "泉北線": "https://ja.wikipedia.org/wiki/泉北高速鉄道線",
    "高野線（汐見橋方面）": "https://ja.wikipedia.org/wiki/南海汐見橋線",
    "高野山ケーブル": "https://ja.wikipedia.org/wiki/南海鋼索線"
}

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
global_distances = {line: {} for line in WIKI_URLS.keys()}

def clean_station_name(name):
    if pd.isna(name): return name
    # 1. 移除維基百科的引用備註，如 [* 1]
    name = re.sub(r'\[.*?\]', '', str(name))
    
    # 2. 移除所有類型的括號及其內容 (包含和歌山大學前的「（ふじと台）」)
    # 這裡同時處理半形 () 與全形 （）
    name = re.sub(r'\(.*?\)', '', name) 
    name = re.sub(r'（.*?）', '', name) 
    
    # 3. 移除「駅」字、待避站符號「#」並修剪空白
    name = name.replace("駅", "").replace("#", "").strip()
    return name

print("🚀 開始爬取南海全家族里程 (已過濾待避符號與特定站名)...\n")

for line_name, url in WIKI_URLS.items():
    print(f"正在掃描: {line_name} ...")
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status() 
        tables = pd.read_html(StringIO(response.text))
        
        target_df = None
        for df in tables:
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
                
                # 專屬南海本線的實體過濾器：移除今宮戎、萩ノ茶屋
                if line_name == "南海本線" and st_name in ["今宮戎", "萩ノ茶屋"]:
                    # 注意：雖然不錄入，但如果維基提供的距離是「站間距離」，
                    # 邏輯上仍需累加該站距離才能讓下一站的里程正確。
                    # 幸好這兩站在維基的本線表格通常本來就不計入，或以「全線共通」方式呈現。
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
output_file = "Japan/Nankai/All_Nankai_Distances_Nested.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(global_distances, f, ensure_ascii=False, indent=4)

print(f"\n🎉 處理完畢！")
print(f"1. 所有的 '#' 已移除。")
print(f"2. 南海本線已剔除 今宮戎、萩ノ茶屋。")
print(f"3. 和歌山大学前 已移除副站名內容。")