import pandas as pd
import requests
import json
import re
import os
from io import StringIO

TARGET_LINES = {
    "tokaido": ("東海道新幹線", "https://ja.wikipedia.org/wiki/%E6%9D%B1%E6%B5%B7%E9%81%93%E6%96%B0%E5%B9%B9%E7%B7%9A"),
    "sanyo": ("山陽新幹線", "https://ja.wikipedia.org/wiki/%E5%B1%B1%E9%99%BD%E6%96%B0%E5%B9%B9%E7%B7%9A"),
    "kyushu": ("九州新幹線", "https://ja.wikipedia.org/wiki/%E4%B9%9D%E5%B7%9E%E6%96%B0%E5%B9%B9%E7%B7%9A"),
    "nishi_kyushu": ("西九州新幹線", "https://ja.wikipedia.org/wiki/%E8%A5%BF%E4%B9%9D%E5%B7%9E%E6%96%B0%E5%B9%B9%E7%B7%9A")
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def clean_station_name(text):
    if pd.isna(text): return ""
    text = str(text)
    
    text = re.sub(r'\[.*?\]', '', text) 
    text = re.sub(r'（.*?）', '', text) 
    text = re.sub(r'\(.*?\)', '', text) 
    text = re.sub(r'[†*※‡]', '', text)
    text = re.sub(r'[\s　]+(山区|都区|浜内|名内|京内|阪内|神内|広内|九内|福内|仙内|札内|山|区|浜|名|京|阪|神|広|九|福|仙|札)$', '', text)
    text = text.replace(' ', '').replace('　', '').replace('駅', '')
    
    anomalies = {
        "東京山区": "東京", "東京都区": "東京",
        "品川山区": "品川", "品川都区": "品川",
        "新横浜浜": "新横浜", "新横浜浜内": "新横浜",
        "名古屋名": "名古屋", "名古屋名内": "名古屋",
        "京都京": "京都", "京都京内": "京都",
        "新大阪阪": "新大阪", "新大阪阪内": "新大阪",
        "新神戸神": "新神戸", "新神戸神内": "新神戸",
        "広島広": "広島", "広島広内": "広島",
        "小倉九": "小倉", "小倉九内": "小倉",
        "博多福": "博多", "博多福内": "博多"
    }
    
    if text in anomalies:
        text = anomalies[text]
            
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
    
    # ==========================================
    # 🌟 核心新增：全域車站 ID 註冊表
    # ==========================================
    global_station_map = {} 

    for sys_id, (name, url) in TARGET_LINES.items():
        print(f"🚄 正在前往勘測 {name} ...")
        try:
            response = requests.get(url, headers=HEADERS)
            response.raise_for_status()
            
            html_content = StringIO(response.text)
            dfs = pd.read_html(html_content)
            
            valid_dfs = []
            for df in dfs:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = ['_'.join(str(lvl) for lvl in col if "Unnamed" not in str(lvl)) for col in df.columns]
                
                cols = [str(c) for c in df.columns]
                if any("駅" in c for c in cols) and any("キロ" in c for c in cols):
                    valid_dfs.append(df)
                    
            if not valid_dfs:
                print(f"  ❌ 找不到 {name} 的車站表格")
                continue
                
            target_df = max(valid_dfs, key=len)

            name_col = next((c for c in target_df.columns if "駅" in str(c)), None)
            
            km_col = None
            for kw in ["新大阪から", "博多から", "累計", "営業"]:
                matches = [c for c in target_df.columns if kw in str(c) and "駅間" not in str(c) and "東京から" not in str(c)]
                if matches:
                    km_col = matches[0]
                    break
            
            if not km_col:
                fallback_matches = [c for c in target_df.columns if "キロ" in str(c) and "駅間" not in str(c)]
                if fallback_matches:
                    km_col = fallback_matches[0]

            if not name_col or not km_col:
                print(f"  ❌ 找不到 {name} 的欄位")
                continue

            stations = []
            st_idx = 1
            base_km_offset = None 
            
            for _, row in target_df.iterrows():
                st_name = clean_station_name(row[name_col])
                km_val = parse_km(row[km_col])
                
                if not st_name or st_name == "駅名" or "計" in st_name or km_val is None:
                    continue
                    
                if len(st_name) > 10 or "停車" in st_name or "列車" in st_name or "すべて" in st_name:
                    continue
                    
                if stations and stations[-1]["name"] == st_name:
                    continue

                if base_km_offset is None:
                    base_km_offset = km_val
                    
                adjusted_km = round(km_val - base_km_offset, 1)

                # ==========================================
                # 🌟 核心修復：發配 ID 前先查戶口名簿
                # ==========================================
                if st_name in global_station_map:
                    # 如果別的路線已經註冊過這個站，強制沿用舊的 ID！
                    final_st_id = global_station_map[st_name]
                else:
                    # 如果是新朋友，核發新的系統專屬 ID 並登記
                    st_id_prefix = sys_id.split('_')[0].upper()[:3]
                    final_st_id = f"{st_id_prefix}{st_idx:02d}"
                    global_station_map[st_name] = final_st_id
                    st_idx += 1
                # ==========================================

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
        
    print(f"\n🎉 完美大功告成！已將新幹線實體里程存入：\n👉 {output_filename}")

if __name__ == "__main__":
    main()