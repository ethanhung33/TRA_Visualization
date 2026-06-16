import pandas as pd
import requests
import json
import re
import os
from io import StringIO

# ==========================================
# 🌟 1. 定義法定起點站 (解決路線重疊問題)
# 格式: "ID": ("路線名", "網址", "法定起點站")
# ==========================================
TARGET_LINES = {
    "THK": ("東北新幹線", "https://ja.wikipedia.org/wiki/%E6%9D%B1%E5%8C%97%E6%96%B0%E5%B9%B9%E7%B7%9A", "東京"),
    "HKD": ("北海道新幹線", "https://ja.wikipedia.org/wiki/%E5%8C%97%E6%B5%B7%E9%81%93%E6%96%B0%E5%B9%B9%E7%B7%9A", "新青森"),
    "JTS": ("上越新幹線", "https://ja.wikipedia.org/wiki/%E4%B8%8A%E8%B6%8A%E6%96%B0%E5%B9%B9%E7%B7%9A", "大宮"),
    "HRK": ("北陸新幹線", "https://ja.wikipedia.org/wiki/%E5%8C%97%E9%99%B8%E6%96%B0%E5%B9%B9%E7%B7%9A", "高崎"),
    "AKT": ("秋田新幹線", "https://ja.wikipedia.org/wiki/%E7%A7%8B%E7%94%B0%E6%96%B0%E5%B9%B9%E7%B7%9A", "盛岡"),
    "YMG": ("山形新幹線", "https://ja.wikipedia.org/wiki/%E5%B1%B1%E5%BD%A2%E6%96%B0%E5%B9%B9%E7%B7%9A", "福島")
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def clean_station_name(text):
    if pd.isna(text): return ""
    text = str(text)
    
    # 移除括號與註解
    text = re.sub(r'\[.*?\]', '', text) 
    text = re.sub(r'（.*?）', '', text) 
    text = re.sub(r'\(.*?\)', '', text) 
    text = re.sub(r'[†*※‡]', '', text)
    text = text.replace(' ', '').replace('　', '').replace('駅', '')
    
    # 都區市內例外處理
    anomalies = {
        "東京山区": "東京", "東京都区": "東京",
        "上野山区": "上野", "上野都区": "上野",
        "仙台仙": "仙台", "仙台仙内": "仙台",
        "札幌札": "札幌", "札幌札内": "札幌"
    }
    
    if text in anomalies:
        text = anomalies[text]
        
    text = re.sub(r'(山区|都区|仙内|札内|仙|札)$', '', text)
    return text.strip()

def parse_km(km_str):
    if pd.isna(km_str): return None
    km_str = str(km_str).replace(',', '')
    km_str = re.sub(r'\[.*?\]', '', km_str)
    km_str = re.sub(r'（.*?）', '', km_str) 
    match = re.search(r'(\d+\.?\d*)', km_str)
    return float(match.group(1)) if match else None

def main():
    topology_data = {"segments": []}
    global_station_map = {} 

    # 解包時加入 start_station
    for sys_id, (name, url, start_station) in TARGET_LINES.items():
        print(f"🚄 正在前往勘測 {name} ...")
        try:
            response = requests.get(url, headers=HEADERS)
            response.raise_for_status()
            
            html_content = StringIO(response.text)
            dfs = pd.read_html(html_content)
            
            best_df = None
            best_len = 0
            best_name_col = None
            best_km_col = None
            
            for df in dfs:
                if isinstance(df.columns, pd.MultiIndex):
                    flat_cols = []
                    for col in df.columns:
                        cleaned = [str(lvl) for lvl in col if "Unnamed" not in str(lvl)]
                        flat_cols.append('_'.join(cleaned) if cleaned else "Unnamed")
                    df.columns = flat_cols
                else:
                    df.columns = [str(c) for c in df.columns]
                    
                cols = df.columns
                name_col = next((c for c in cols if "駅" in c and "長" not in c and "間" not in c and "周辺" not in c), None)
                
                km_col = None
                for kw in ["東京から", "累計", "東京起点", "実キロ"]:
                    matches = [c for c in cols if kw in c and "間" not in c]
                    if matches: 
                        km_col = matches[0]
                        break
                
                if not km_col:
                    for kw in ["営業キロ", "キロ"]:
                        matches = [c for c in cols if kw in c and "間" not in c]
                        if matches: 
                            km_col = matches[0]
                            break
                            
                if name_col and km_col:
                    if len(df) > best_len:
                        best_len = len(df)
                        best_df = df
                        best_name_col = name_col
                        best_km_col = km_col

            if best_df is None:
                print(f"  ❌ 找不到 {name} 的有效車站與里程表格")
                continue

            stations = []
            st_idx = 1
            base_km_offset = None 
            
            # 🌟 2. 啟動「尋找起點」旗標
            has_reached_start = False 
            
            for _, row in best_df.iterrows():
                st_name = clean_station_name(row[best_name_col])
                km_val = parse_km(row[best_km_col])
                
                if not st_name or st_name == "駅名" or "計" in st_name or km_val is None:
                    continue
                
                # 🌟 3. 排除信號場與車輛基地
                if "信号" in st_name or "基地" in st_name or "車両" in st_name:
                    continue
                    
                if len(st_name) > 10 or "停車" in st_name or "列車" in st_name or "すべて" in st_name:
                    continue

                # 🌟 4. 攔截器：如果還沒遇到法定起點站，就一直跳過！
                if not has_reached_start:
                    if st_name == start_station:
                        has_reached_start = True
                    else:
                        continue # 略過東京~大宮等重疊區間
                    
                if stations and stations[-1]["name"] == st_name:
                    continue

                # 🌟 5. (重要提醒) 這裡的里程計算方式
                if base_km_offset is None:
                    base_km_offset = km_val
                    
                adjusted_km = round(km_val - base_km_offset, 1)

                if st_name in global_station_map:
                    final_st_id = global_station_map[st_name]
                else:
                    final_st_id = f"{sys_id}{st_idx:02d}"
                    global_station_map[st_name] = final_st_id
                    st_idx += 1

                stations.append({
                    "id": final_st_id,
                    "name": st_name,
                    "km": adjusted_km 
                })
                
            topology_data["segments"].append({
                "id": f"{sys_id}_line",
                "name": name,
                "stations": stations
            })
            print(f"  ✅ 成功測繪 {len(stations)} 站！")
            
        except Exception as e:
            print(f"  ❌ 發生錯誤: {e}")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    system_dir = os.path.dirname(script_dir)
    json_dir = os.path.join(system_dir, "json")
    os.makedirs(json_dir, exist_ok=True)
    
    output_filename = os.path.join(json_dir, 'topology.json')
    
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(topology_data, f, ensure_ascii=False, indent=2)
        
    print(f"\n🎉 完美大功告成！已將東日本/北海道新幹線實體里程存入：\n👉 {output_filename}")

if __name__ == "__main__":
    main()