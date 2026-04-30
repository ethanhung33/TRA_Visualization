import pandas as pd
import requests
from io import StringIO
import re
import json
import os
from bs4 import BeautifulSoup

WIKI_URLS = {
    "南海本線": "https://ja.wikipedia.org/wiki/南海本線",
    "空港線": "https://ja.wikipedia.org/wiki/南海空港線",
    "加太線": "https://ja.wikipedia.org/wiki/南海加太線",
    "多奈川線": "https://ja.wikipedia.org/wiki/南海多奈川線",
    "和歌山港線": "https://ja.wikipedia.org/wiki/南海和歌山港線",
    "高師浜線": "https://ja.wikipedia.org/wiki/南海高師浜線",
    "高野線": "https://ja.wikipedia.org/wiki/南海高野線",
    "泉北線": "https://ja.wikipedia.org/wiki/泉北高速鉄道線",
    "高野線（汐見橋方面）": "https://ja.wikipedia.org/wiki/南海高野線#汐見橋線",
    "高野山ケーブル": "https://ja.wikipedia.org/wiki/南海鋼索線"
}

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
global_distances = {line: {} for line in WIKI_URLS.keys()}

def clean_name_or_id(name):
    if pd.isna(name): return name
    # 1. 移除維基百科的引用備註，如 [* 1]
    name = re.sub(r'\[.*?\]', '', str(name))
    
    # 2. 移除所有類型的括號及其內容
    name = re.sub(r'\(.*?\)', '', name) 
    name = re.sub(r'（.*?）', '', name) 
    
    # 3. 移除「駅」字、待避站符號「#」並修剪空白
    name = name.replace("駅", "").replace("#", "").strip()
    return name

print("🚀 開始爬取南海全家族里程 (包含官方車站代碼)...\n")

for line_name, url in WIKI_URLS.items():
    print(f"正在掃描: {line_name} ...")
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status() 
        
        # 💡 放棄尋找 HTML 標籤，直接用「指紋」過濾表格
        if line_name == "高野線（汐見橋方面）":
            try:
                tables = pd.read_html(StringIO(response.text), match="芦原町")
            except ValueError:
                print("  ❌ 找不到包含「芦原町」的專屬表格")
                tables = []
        else:
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
        
        # 🌟 尋找官方車站編號欄位 (駅番号)
        id_col = next((c for c in target_df.columns if "駅番号" in c), None)
        
        is_cumulative = False
        if not dist_col:
            dist_col = next((c for c in target_df.columns if "キロ" in c), None)
            is_cumulative = True
            
        count = 0
        current_cumulative_dist = 0.0 
        
        for index, row in target_df.iterrows():
            raw_st = row[st_col]
            st_name = clean_name_or_id(raw_st)
            dist_val = row[dist_col]
            
            if pd.notna(st_name) and st_name != "nan":
                if "駅名" in st_name or st_name == "": continue
                
                # 號誌站殺手 (全線通用)
                if "信号" in st_name:
                    continue

                # 加太線專屬過濾器
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
                    
                    # 🌟 優先取得官方代碼 (如 NK01)，若無則退回使用站名
                    st_id = st_name
                    if id_col and pd.notna(row[id_col]):
                        cleaned_id = clean_name_or_id(row[id_col])
                        if cleaned_id and cleaned_id != "nan":
                            st_id = cleaned_id
                            
                    global_distances[line_name][st_name] = {
                        "id": st_id,
                        "km": round(current_cumulative_dist, 1)
                    }
                    count += 1
                    
                except ValueError:
                    pass 
                    
        print(f"  ✅ 成功抓取並累加 {count} 個車站！")
        
    except Exception as e:
        print(f"  ❌ 請求 {line_name} 失敗: {e}")

# ==========================================
# 轉換為你的專屬 topology.json 標準格式
# ==========================================
topology_data = {
    "operator_id": "Nankai", 
    "segments": []
}

# 定義各路線的英文或拼音 ID
line_id_mapping = {
    "南海本線": "nankai_main",
    "空港線": "nankai_airport",
    "加太線": "nankai_kada",
    "多奈川線": "nankai_tanagawa",
    "和歌山港線": "nankai_wakayamako",
    "高師浜線": "nankai_takashinohama",
    "高野線": "nankai_koya",
    "泉北線": "semboku_rapid",
    "高野線（汐見橋方面）": "nankai_shiomibashi",
    "高野山ケーブル": "nankai_cable"
}

for line_name, stations_dict in global_distances.items():
    if not stations_dict: 
        continue 
        
    segment = {
        "id": line_id_mapping.get(line_name, "unknown_line"),
        "name": line_name,
        "stations": []
    }
    
    for st_name, data in stations_dict.items():
        segment["stations"].append({
            "id": data["id"],   # 🌟 現在會優先使用如 NK01 的官方代碼
            "name": st_name,
            "km": data["km"]
        })
        
    topology_data["segments"].append(segment)

# 🌟 自動定位儲存路徑
script_dir = os.path.dirname(os.path.abspath(__file__))
output_file = os.path.join(os.path.dirname(script_dir), "json", "topology.json")

os.makedirs(os.path.dirname(output_file), exist_ok=True)

with open(output_file, "w", encoding="utf-8") as f:
    json.dump(topology_data, f, ensure_ascii=False, indent=4)

print(f"\n🎉 處理完畢！")
print(f"1. 所有的 '#' 已移除。")
print(f"2. 南海本線已剔除 今宮戎、萩ノ茶屋。")
print(f"3. 🌟 已成功從維基百科擷取官方 Station ID (駅番号)！")
print(f"4. 檔案已儲存至: {output_file}")