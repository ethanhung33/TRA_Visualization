import pandas as pd
import requests
import json
import os
import re
import unicodedata
from io import StringIO
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# ==========================================
# 基礎設定與路徑
# ==========================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_DIR = os.path.join(BASE_DIR, 'json')
os.makedirs(JSON_DIR, exist_ok=True)

JA_CATEGORY_URL = "https://ja.wikipedia.org/wiki/Category:西日本旅客鉄道の鉄道路線"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ==========================================
# 🗺️ 全域設定與紀錄器
# ==========================================
PREFIX_COUNTER = {}         
GLOBAL_STATION_ID_MAP = {}  

# 💡 新增：路線中文名對應英文 ID
LINE_NAME_EN = {
    "北陸本線": "hokuriku_main_line",
    "琵琶湖線": "biwako_line",
    "JR京都線": "jr_kyoto_line",
    "JR神戸線": "jr_kobe_line",
    "大阪環状線": "osaka_loop_line",
    "おおさか東線": "osaka_higashi_line",
    "関西本線": "kansai_main_line",
    "紀勢本線": "kisei_main_line",
    "呉線": "kure_line",
    "山陰本線": "sanin_main_line",
    "山陽本線": "sanyo_main_line",
    "高山本線": "takayama_main_line",
    "奈良線": "nara_line",
    "阪和線": "hanwa_line",
    "和歌山線": "wakayama_line",
    "因美線": "inbi_line",
    "宇野線": "uno_line",
    "宇部線": "ube_line",
    "越美北線": "etsumi_kita_line",
    "大糸線": "oito_line",
    "小野田線": "onoda_line",
    "小浜線": "obama_line",
    "加古川線": "kakogawa_line",
    "片町線": "katamachi_line",
    "可部線": "kabe_line",
    "関西空港線": "kansai_airport_line",
    "岩徳線": "gantoku_line",
    "姫新線": "kishin_line",
    "木次線": "kisuki_line",
    "吉備線": "kibi_line",
    "草津線": "kusatsu_line",
    "芸備線": "geibi_line",
    "湖西線": "kosei_line",
    "境線": "sakai_line",
    "嵯峨野線": "sagano_line",
    "桜井線": "sakurai_line",
    "桜島線": "sakurajima_line",
    "JR東西線": "jr_touzai_line",
    "城端線": "johana_line",
    "本四備讃線": "honshi_bisan_line",
    "津山線": "tsuyama_line",
    "七尾線": "nanao_line",
    "伯備線": "hakubi_line",
    "播但線": "bantan_line",
    "氷見線": "himi_line",
    "福塩線": "fukuen_line",
    "福知山線": "fukuchiyama_line",
    "舞鶴線": "maizuru_line",
    "美祢線": "mine_line",
    "山口線": "yamaguchi_line",
    "大和路線": "yamatoji_line",  
    "赤穂線": "ako_line", 
    "博多南線": "hakata_minami_line",
    "和田岬線": "wadamisaki_line",
    "仙崎支線": "senzaki_line",
    "羽衣線": "hagoromo_line",
}

line_id_map = {
    # === 都會區 A 區段大動脈 ===
    "北陸本線": "JRW_Kansai_A",   
    "琵琶湖線": "JRW_Kansai_A",   
    "JR京都線": "JRW_Kansai_A",   
    "JR神戸線": "JRW_Kansai_A",   
    "赤穂線": "JRW_Kansai_A", 

    # === 獨立短路線與三大支線 ===
    "博多南線": "JRW_HakataMinami_",
    "和田岬線": "JRW_KWadamisaki_",
    "仙崎支線": "JRW_Senzaki_",
    "羽衣線": "JRW_Hagoromo_",

    # === 其他主要與地方路線 ===
    "関西本線": "JRW_Kansai_V",
    "おおさか東線": "JRW_Kansai_H",
    "紀勢本線": "JRW_Kansai_W",
    "大阪環状線": "JRW_Kansai_O",
    "呉線": "JRW_Chugoku_Y",
    "山陰本線": "JRW_Sanin_",
    "山陽本線": "JRW_Sanyo_",
    "高山本線": "JRW_Takayama_",
    "奈良線": "JRW_Kansai_D",
    "阪和線": "JRW_Kansai_R",
    "和歌山線": "JRW_Kansai_T",
    "因美線": "JRW_Sanin_B",
    "宇野線": "JRW_Chugoku_L",
    "宇部線": "JRW_Ube_",
    "越美北線": "JRW_Etsumi_",
    "大糸線": "JRW_Oito_",
    "小野田線": "JRW_Onoda_",
    "小浜線": "JRW_Obama_",
    "加古川線": "JRW_Kansai_I",
    "片町線": "JRW_Kansai_H",
    "可部線": "JRW_Chugoku_B",
    "関西空港線": "JRW_Kansai_S",
    "岩徳線": "JRW_Gantoku_",
    "姫新線": "JRW_Kansai_K",
    "木次線": "JRW_Sanin_E",
    "吉備線": "JRW_Chugoku_U",
    "草津線": "JRW_Kansai_C",
    "芸備線": "JRW_Chugoku_P",
    "湖西線": "JRW_Kansai_B",
    "境線": "JRW_Sanin_C",
    "嵯峨野線": "JRW_Kansai_E",
    "桜井線": "JRW_Kansai_U",
    "桜島線": "JRW_Kansai_P",
    "JR東西線": "JRW_Kansai_H",
    "城端線": "JRW_Johana_",
    "本四備讃線": "JRW_Chugoku_M",
    "津山線": "JRW_Chugoku_T",
    "七尾線": "JRW_Nanao_",
    "伯備線": "JRW_Chugoku_V",
    "播但線": "JRW_Kansai_J",
    "氷見線": "JRW_Himi_",
    "福塩線": "JRW_Fukuen_",
    "福知山線": "JRW_Kansai_G",
    "舞鶴線": "JRW_Kansai_L",
    "美祢線": "JRW_Mine_",
    "山口線": "JRW_Yamaguchi_",
    "大和路線": "JRW_Kansai_Q",
}

SAME_NAME_STATIONS = {
    "大和路線": {"柏原": "柏原_大和"},
    "福知山線": {"柏原": "柏原_福知山"},
    "山陽本線": {"下松": "下松_山陽"},
    "阪和線": {"下松": "下松_阪和"}
}

SKIP_STATIONS = {
    "おおさか東線": ["大阪"],
    "琵琶湖線": ["長浜", "田村", "坂田"],
    "山陰本線": ["下関", "仙崎"],
    "赤穂線": ["姫路", "手柄山平和公園", "英賀保", "はりま勝原", "網干", "竜野", "高島", "西川原", "岡山"],
    "湖西線": ["京都", "敦賀", "新疋田"],
    "可部線": ["広島", "新白島"],
    "岩徳線": ["徳山"],
    "芸備線": ["新見", "布原"],
    "越美北線": ["福井"],
    "七尾線": ["金沢", "東金沢", "森本"]
}

# ==========================================
# 清洗工具函式
# ==========================================
# ==========================================
# 清洗工具函式
# ==========================================
def clean_station_name(text):
    text = unicodedata.normalize('NFKC', str(text))
    text = re.sub(r'\[.*?\]|（.*?）|\(.*?\)|[†*※‡#]', '', text)
    text = text.replace(' ', '').replace(' ', '')
    text = re.sub(r'駅.*$', '', text) 
    text = text.strip()
    
    # 💡 修正：取消 len <= 1 的限制，改為過濾空字串與無效排版符號
    # 這樣「鳳」、「吳」、「灘」等單字車站就能順利通過了！
    if not text or text in ['-', '—', '＝', '∥', '・']: 
        return None
        
    return text

def clean_station_code(text):
    text = str(text)
    match = re.search(r'([A-Z0-9\-]+)', text)
    return match.group(1) if match else None

def parse_km(km_str):
    s = str(km_str).strip()
    if s in ['', '-', '−', 'nan']: return None
    val = re.sub(r'[^\d.]', '', s.replace(',', ''))
    try: return float(val)
    except: return None

# ==========================================
# 🚀 終極統一解析器 (Unified Parser)
# ==========================================
def parse_route(name, url):
    res = requests.get(url, headers=HEADERS, timeout=10)
    soup = BeautifulSoup(res.text, 'html.parser')
    
    stations = []
    seen_stations = set()
    line_id_in_map = (name in line_id_map)
    prefix = line_id_map.get(name, f"{name}_")
    
    for table in soup.find_all('table', class_='wikitable'):
        
        table_html_str = str(table)
        
        # 📌 紀勢本線特判 (避開 JR 東海)
        if name == "紀勢本線":
            section_header = table.find_previous(['h2', 'h3', 'h4'])
            if section_header and "東海旅客鉄道" in section_header.get_text():
                continue
                
        # 💡 【支線精準特徵定位】：無視標題，直接檢查表格內部是否包含該支線的專屬站名
        if name == "和田岬線" and "和田岬" not in table_html_str:
            continue
        if name == "仙崎支線" and "仙崎" not in table_html_str:
            continue
        if name == "羽衣線" and "東羽衣" not in table_html_str:
            continue
                
        try:
            df = pd.read_html(StringIO(table_html_str))[0]
        except ValueError:
            continue
            
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = ['_'.join(map(str, c)) for c in df.columns]
            
        cols = [str(c) for c in df.columns]
        c_cands = [i for i, c in enumerate(cols) if "駅ナンバー" in c or "駅番号" in c]
        n_cands = [i for i, c in enumerate(cols) if "駅名" in c and "シンボル" not in c and "フラワー" not in c]
        
        k_cands = [i for i, c in enumerate(cols) if "累計" in c]
        if not k_cands:
            k_cands = [i for i, c in enumerate(cols) if "営業" in c or "キロ" in c]
            
        # 🌟 精準特判：針對會跨越法定路線、導致里程歸零的營業路線，強制鎖定連續里程欄位
        if name == "JR神戸線":
            # 只要欄位名稱包含「大阪」且跟里程有關，就強制鎖定
            osaka_cands = [i for i, c in enumerate(cols) if "大阪" in c and ("累計" in c or "キロ" in c)]
            if osaka_cands:
                k_cands = osaka_cands
                print(f"    🎯 成功鎖定 JR 神戶線『大阪起算』欄位: {cols[k_cands[0]]}")

        if n_cands and k_cands:
            code_idx = c_cands[0] if c_cands else -1
            name_idx = n_cands[0]
            km_idx = k_cands[0]

            if name in ["北陸本線", "琵琶湖線"]:
                df = df.iloc[::-1].reset_index(drop=True)

            tsuruga_km = None
            if name == "北陸本線":
                for _, row in df.iterrows():
                    st_name_check = clean_station_name(row.iloc[name_idx])
                    if st_name_check == "敦賀":
                        tsuruga_km = parse_km(row.iloc[km_idx])
                        break

            for _, row in df.iterrows():
                st_name = clean_station_name(row.iloc[name_idx])
                if not st_name or "信号場" in st_name or "貨物" in st_name or "操車場" in st_name:
                    continue
                
                if st_name in SKIP_STATIONS.get(name, []):
                    continue
                    
                km_val = parse_km(row.iloc[km_idx])
                if km_val is None: continue

                if name == "北陸本線" and tsuruga_km is not None:
                    km_val = round(abs(tsuruga_km - km_val), 2)
                
                if st_name in seen_stations:
                    continue
                seen_stations.add(st_name)
                
                search_key = SAME_NAME_STATIONS.get(name, {}).get(st_name, st_name)
                
                if search_key in GLOBAL_STATION_ID_MAP:
                    st_id = GLOBAL_STATION_ID_MAP[search_key]
                else:
                    official_code = clean_station_code(row.iloc[code_idx]) if code_idx != -1 else ""
                    
                    if name == "赤穂線" and official_code and "N" in official_code:
                        clean_n_code = official_code.replace("JR-", "")
                        st_id = f"JRW_Chugoku_{clean_n_code}"
                    else:
                        if line_id_in_map:
                            if prefix not in PREFIX_COUNTER:
                                PREFIX_COUNTER[prefix] = 0
                            PREFIX_COUNTER[prefix] += 1
                            st_id = f"{prefix}{str(PREFIX_COUNTER[prefix]).zfill(2)}"
                        else:
                            if official_code:
                                st_id = official_code
                            else:
                                local_prefix = f"{name}_"
                                if local_prefix not in PREFIX_COUNTER:
                                    PREFIX_COUNTER[local_prefix] = 0
                                PREFIX_COUNTER[local_prefix] += 1
                                st_id = f"{local_prefix}{str(PREFIX_COUNTER[local_prefix]).zfill(2)}"
                    
                    GLOBAL_STATION_ID_MAP[search_key] = st_id
                
                stations.append({"id": st_id, "name": st_name, "km": km_val})
                
                if name == "本四備讃線" and st_name == "児島":
                    return stations 
            
            if name not in ["紀勢本線", "赤穂線", "山陽本線", "山陰本線", "和田岬線", "仙崎支線", "羽衣線", "高山本線", "大糸線"]:
                break

    if name == "高山本線":
        try:
            # 找到豬谷的索引位置
            target_idx = [s['name'] for s in stations].index("猪谷")
            # 直接切片，只保留豬谷以後的車站
            stations = stations[target_idx:] 

            if len(stations) > 1:
                base_km = stations[0]['km']
                next_km = stations[1]['km']
                
                # 狀況 A：如果維基百科第二站(楡原)是 7.0，代表它已經是相對里程，我們只要把猪谷強制改為 0 即可
                if next_km < base_km:
                    stations[0]['km'] = 0.0
                # 狀況 B (防呆)：如果維基百科未來改成絕對里程 (196.2)，就把全線平移扣除 base_km
                else:
                    for st in stations:
                        st['km'] = round(st['km'] - base_km, 2)

            print(f"✂️ 高山本線已成功截斷，忽略猪谷之前的所有車站。")
        except ValueError:
            print(f"⚠️ 找不到猪谷站，無法截斷高山本線。")

    if name == "大糸線":
        try:
            # 找到南小谷的索引位置
            target_idx = [s['name'] for s in stations].index("南小谷")
            # 直接切片，只保留南小谷以後的車站
            stations = stations[target_idx:] 
            if len(stations) > 1:
                base_km = stations[0]['km']
                next_km = stations[1]['km']
                
                # 狀況 A：如果維基百科第二站(楡原)是 7.0，代表它已經是相對里程，我們只要把猪谷強制改為 0 即可
                if next_km < base_km:
                    stations[0]['km'] = 0.0
                # 狀況 B (防呆)：如果維基百科未來改成絕對里程 (196.2)，就把全線平移扣除 base_km
                else:
                    for st in stations:
                        st['km'] = round(st['km'] - base_km, 2)
            print(f"✂️ 大糸線已成功截斷，忽略南小谷之前的所有車站。")
        except ValueError:
            print(f"⚠️ 找不到南小谷站，無法截斷大糸線。")

    if name == "伯備線":
        try:
            # 找到倉敷的索引位置
            target_idx = [s['name'] for s in stations].index("倉敷")
            # 直接切片，只保留倉敷以後的車站
            stations = stations[target_idx:] 
            print(f"✂️ 伯備線已成功截斷，忽略倉敷之前的所有車站。")
            
            # 找到伯耆大山的索引位置
            target_idx = [s['name'] for s in stations].index("伯耆大山")
            # 直接切片，只保留伯耆大山以前的車站
            stations = stations[:target_idx + 1]
            print(f"✂️ 伯備線已成功截斷，忽略伯耆大山以後的所有車站。")

        except ValueError:
            print(f"⚠️ 找不到倉敷站、伯耆大山站，無法截斷伯備線。")
            
    if name == "福知山線":
        try:
            # 找到尼崎的索引位置
            target_idx = [s['name'] for s in stations].index("尼崎")
            # 直接切片，只保留尼崎以後的車站
            stations = stations[target_idx:] 
            print(f"✂️ 福知山線已成功截斷，忽略尼崎之前的所有車站。")
        except ValueError:
            print(f"⚠️ 找不到尼崎站，無法截斷福知山線。")

    if name == "呉線":
        try:
            # 找到海田市的索引位置
            target_idx = [s['name'] for s in stations].index("海田市")
            # 直接切片，只保留海田市以前的車站
            stations = stations[:target_idx + 1]
            print(f"✂️ 呉線已成功截斷，忽略海田市以後的所有車站。")
        except ValueError:
            print(f"⚠️ 找不到海田市站，無法截斷呉線。")
    if name == "仙崎支線":
        stations = [
            {"id": "JRW_Sanin_124", "name": "長門市", "km": 0.0},
            {"id": "JRW_Senzaki_01", "name": "仙崎", "km": 2.2}
        ]
        print("    🎯 成功攔截並修正「仙崎支線」的車站與里程資料！")

    return stations

# ==========================================
# 主程式
# ==========================================
def main():
    print(f"🌐 掃描分類頁...")
    try:
        res = requests.get(JA_CATEGORY_URL, headers=HEADERS)
        soup = BeautifulSoup(res.text, 'html.parser')
    except Exception as e:
        print(f"❌ 連線失敗: {e}")
        return
    
    exclude_list = ["瀬戸大橋線", "なにわ筋線", "片奈連絡線", "梅田貨物線"] 
    
    lines = {li.get_text().strip(): urljoin("https://ja.wikipedia.org/", li.get('href', '')) 
             for li in soup.select('.mw-category-group li a') 
             if li.get_text().strip().endswith('線') 
             and (not any(k in li.get_text() for k in ["新幹線", "鉄道", "会社", "図"]) or li.get_text().strip() == "博多南線")
             and li.get_text().strip() not in exclude_list}
    
    # 💡 更新：和田岬線擁有自己的專屬頁面
    lines["和田岬線"] = "https://ja.wikipedia.org/wiki/%E5%92%8C%E7%94%B0%E5%B2%AC%E7%B7%9A"
    lines["仙崎支線"] = "https://ja.wikipedia.org/wiki/%E5%B1%B1%E9%99%B0%E6%9C%AC%E7%B7%9A"
    lines["羽衣線"] = "https://ja.wikipedia.org/wiki/%E9%98%AA%E5%92%8C%E7%B7%9A"

    print(f"🎯 鎖定 {len(lines)} 條路線。\n")
    topology_data = {"segments": []}

    priority_order = ["北陸本線", "琵琶湖線", "JR京都線", "JR神戸線"]
    ordered_line_names = priority_order + [name for name in lines.keys() if name not in priority_order]

    for name in ordered_line_names:
        url = lines[name]
        print(f"🔬 勘測: {name}")
        try:
            stations = parse_route(name, url)
            
            if stations and len(stations) > 1:
                # 💡 取得英文 ID，若找不到則使用預設格式
                line_id = LINE_NAME_EN.get(name, name.replace("線", "_line").lower())
                
                topology_data["segments"].append({
                    "id": line_id,      # 💡 加入英文 ID
                    "name": name, 
                    "stations": stations
                })
                print(f"    ✅ 成功抓取 {len(stations)} 站。")
            else:
                print(f"    ⚠️ 跳過: 找不到正確的車站列表")
        except Exception as e:
            print(f"    ❌ 錯誤: {e}")

    out_path = os.path.join(JSON_DIR, 'topology.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(topology_data, f, ensure_ascii=False, indent=2)
    print(f"\n🎉 執行完成！請檢查檔案: {out_path}")

if __name__ == "__main__":
    main()