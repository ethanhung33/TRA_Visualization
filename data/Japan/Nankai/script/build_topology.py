import pandas as pd
import requests
from io import StringIO
import re
import json
import os

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

def clean_station_name(name):
    if pd.isna(name): return name
    name = re.sub(r'\[.*?\]', '', str(name))
    name = re.sub(r'\(.*?\)', '', name) 
    name = re.sub(r'（.*?）', '', name) 
    name = name.replace("駅", "").replace("#", "").strip()
    return name

print("🚀 開始爬取南海里程 (基於你的版本進行對齊修正)...\n")

# ... (前面的 WIKI_URLS 與 clean_station_name 函數維持不變)

for line_name, url in WIKI_URLS.items():
    print(f"正在掃描: {line_name} ...")
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status() 
        tables = pd.read_html(StringIO(response.text))
            
        target_df = None
        st_col = dist_col = id_col = None 
        is_cumulative = False

        for df in tables:
            # 1. 壓平多層表頭 (完全模擬你 test.py 的邏輯)
            df.columns = ['_'.join(str(c) for c in col).strip() if isinstance(col, tuple) else str(col) for col in df.columns]
            df = df.loc[:, ~df.columns.duplicated()]
            
            col_list = df.columns.tolist()

            # 🌟 策略 A：高野線 (主線) - 精準鎖定 Index 13
            if line_name == "高野線":
                # 診斷顯示：這張表有 '営業キロ_難波 から' 這個特定欄位
                if "営業キロ_難波 から" in col_list:
                    target_df = df
                    st_col = "駅名_駅名" 
                    dist_col = "営業キロ_難波 から" # 🎯 鎖定此欄，岸里玉出才是 3.9km
                    id_col = "駅番号_駅番号"
                    is_cumulative = True
                    break

            # 🌟 策略 B：汐見橋支線 - 精準鎖定 Index 14
            elif line_name == "高野線（汐見橋方面）":
                # 診斷顯示：內容有 '芦原町' 且欄位名很單純
                if "駅名" in col_list and df.stack().astype(str).str.contains('芦原町').any():
                    # 額外檢查：確保這不是 Index 13 那張大表
                    if "営業キロ_難波 から" not in col_list:
                        target_df = df
                        st_col = "駅名"
                        dist_col = "営業キロ"
                        id_col = "駅番号"
                        is_cumulative = True
                        break

            # 🌟 策略 C：其他一般線路
            elif "駅名" in "".join(col_list) and "キロ" in "".join(col_list):
                target_df = df
                st_col = next((c for c in df.columns if "駅名" in c), None)
                dist_col = next((c for c in df.columns if "駅間" in c and "キロ" in c), None)
                id_col = next((c for c in df.columns if "駅番号" in c), None)
                is_cumulative = False
                if not dist_col:
                    dist_col = next((c for c in df.columns if "キロ" in c or "距離" in c), None)
                    is_cumulative = True
                break
                
        if target_df is None:
            print(f"  ❌ 找不到 {line_name} 的符合表格")
            continue
            
        count = 0
        current_cumulative_dist = 0.0 
        
        for index, row in target_df.iterrows():
            raw_st = row[st_col] 
            st_name = clean_station_name(raw_st)

            
            if pd.notna(st_name) and st_name != "nan":
                if "駅名" in st_name or st_name == "": continue
                if "信号" in st_name: continue
                if "分岐点" in st_name: continue
                if "分界点" in st_name: continue

                # 共線段過濾邏輯
                if line_name == "南海本線" and st_name in ["今宮戎", "萩ノ茶屋"]:
                    try:
                        val_str = str(row[dist_col]).replace("km", "").strip()
                        if val_str not in ["-", "−", "", "nan"]:
                            current_cumulative_dist += float(val_str)
                    except: pass
                    continue
                
                try:
                    val_str = str(row[dist_col]).replace("km", "").strip().replace("−", "-")
                    # 處理維基百科的引用標記 [* 1]
                    val = 0.0 if val_str in ["-", "", "nan"] else float(re.sub(r'[^\d.]', '', val_str))
                    
                    if not is_cumulative:
                        current_cumulative_dist += val
                    else:
                        current_cumulative_dist = val 
                    
                    st_id = st_name
                    if id_col and pd.notna(row[id_col]):
                        cleaned_id = clean_station_name(row[id_col])
                        if cleaned_id and cleaned_id != "nan":
                            st_id = cleaned_id
                            
                    global_distances[line_name][st_name] = {
                        "id": st_id,
                        "km": round(current_cumulative_dist, 1)
                    }
                    count += 1
                except:
                    pass 
                    
        print(f"  ✅ 成功抓取並累加 {count} 個車站！")
        
    except Exception as e:
        print(f"  ❌ 請求 {line_name} 失敗: {e}")

# ... (JSON 儲存邏輯)
# ... (後續儲存 topology.json 的邏輯)

# ==========================================
# 輸出 Topology JSON
# ==========================================
topology_data = {"operator_id": "Nankai", "segments": []}
line_id_mapping = {
    "南海本線": "main_line", "空港線": "airport_line", "加太線": "kada_line",
    "多奈川線": "tanagawa_line", "和歌山港線": "wakayamako_line", "高師浜線": "takashinohama_line",
    "高野線": "koya_line", "泉北線": "semboku_line", "高野線（汐見橋方面）": "shiomibashi_line",
    "高野山ケーブル": "koyayama_ropeway"
}

for line_name, stations_dict in global_distances.items():
    if not stations_dict: continue
    segment = {"id": line_id_mapping.get(line_name, "unknown"), "name": line_name, "stations": []}
    for st_name, data in stations_dict.items():
        segment["stations"].append({"id": data["id"], "name": st_name, "km": data["km"]})
    topology_data["segments"].append(segment)

script_dir = os.path.dirname(os.path.abspath(__file__))
output_file = os.path.join(os.path.dirname(script_dir), "json", "topology.json")
os.makedirs(os.path.dirname(output_file), exist_ok=True)
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(topology_data, f, ensure_ascii=False, indent=4)

print(f"\n🎉 完美大功告成！檔案存於: {output_file}")