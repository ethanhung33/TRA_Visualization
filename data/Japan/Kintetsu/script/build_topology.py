import os
import json
import requests
from bs4 import BeautifulSoup
import time
import re

def scrape_wikipedia_kintetsu():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_dir = os.path.join(script_dir, '..', 'json')
    os.makedirs(json_dir, exist_ok=True)
    output_path = os.path.join(json_dir, 'topology.json')

    wiki_lines = [
        {"id": "namba_line", "name": "難波線", "url": "https://ja.wikipedia.org/wiki/近鉄難波線"},
        {"id": "osaka_line", "name": "大阪線", "url": "https://ja.wikipedia.org/wiki/近鉄大阪線"},
        {"id": "nara_line", "name": "奈良線", "url": "https://ja.wikipedia.org/wiki/近鉄奈良線"},
        {"id": "ikoma_line", "name": "生駒線", "url": "https://ja.wikipedia.org/wiki/近鉄生駒線"},
        {"id": "keihanna_line", "name": "けいはんな線", "url": "https://ja.wikipedia.org/wiki/近鉄けいはんな線"},
        {"id": "kyoto_line", "name": "京都線", "url": "https://ja.wikipedia.org/wiki/近鉄京都線"},
        {"id": "kashihara_line", "name": "橿原線", "url": "https://ja.wikipedia.org/wiki/近鉄橿原線"},
        {"id": "tenri_line", "name": "天理線", "url": "https://ja.wikipedia.org/wiki/近鉄天理線"},
        {"id": "tawaramoto_line", "name": "田原本線", "url": "https://ja.wikipedia.org/wiki/近鉄田原本線"},
        {"id": "shigi_line", "name": "信貴線", "url": "https://ja.wikipedia.org/wiki/近鉄信貴線"},
        {"id": "nagoya_line", "name": "名古屋線", "url": "https://ja.wikipedia.org/wiki/近鉄名古屋線"},
        {"id": "yunoyama_line", "name": "湯の山線", "url": "https://ja.wikipedia.org/wiki/近鉄湯の山線"},
        {"id": "suzuka_line", "name": "鈴鹿線", "url": "https://ja.wikipedia.org/wiki/近鉄鈴鹿線"},
        {"id": "yamada_line", "name": "山田線", "url": "https://ja.wikipedia.org/wiki/近鉄山田線"},
        {"id": "toba_line", "name": "鳥羽線", "url": "https://ja.wikipedia.org/wiki/近鉄鳥羽線"},
        {"id": "shima_line", "name": "志摩線", "url": "https://ja.wikipedia.org/wiki/近鉄志摩線"},
        {"id": "minamiosaka_line", "name": "南大阪線", "url": "https://ja.wikipedia.org/wiki/近鉄南大阪線"},
        {"id": "yoshino_line", "name": "吉野線", "url": "https://ja.wikipedia.org/wiki/近鉄吉野線"},
        {"id": "domyoji_line", "name": "道明寺線", "url": "https://ja.wikipedia.org/wiki/近鉄道明寺線"},
        {"id": "nagano_line", "name": "長野線", "url": "https://ja.wikipedia.org/wiki/近鉄長野線"},
        {"id": "gose_line", "name": "御所線", "url": "https://ja.wikipedia.org/wiki/近鉄御所線"},
        # ★ 新增：兩條鋼索線 (纜車)
        {"id": "ikoma_cable", "name": "生駒鋼索線", "url": "https://ja.wikipedia.org/wiki/近鉄生駒鋼索線"},
        {"id": "nishishigi_cable", "name": "西信貴鋼索線", "url": "https://ja.wikipedia.org/wiki/近鉄西信貴鋼索線"}
    ]

    headers = {"User-Agent": "Mozilla/5.0"}

    topology = {
        "operator_id": "Kintetsu",
        "segments": []
    }

    global_stations = {}

    print(f"開始爬取維基百科資料，預計輸出至: {output_path}\n")

    for line in wiki_lines:
        print(f"正在抓取: {line['name']} ...")
        try:
            response = requests.get(line['url'], headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            tables = soup.find_all('table', class_='wikitable')
            target_table = None
            
            for table in tables:
                headers_text = [th.text.strip() for th in table.find_all('th')]
                if any("駅名" in h for h in headers_text) and any("キロ" in h for h in headers_text):
                    target_table = table
                    break
            
            if not target_table:
                print(f"  ⚠️ 找不到 {line['name']} 的車站列表表格。")
                continue

            # === Phase 1: 初步解析該路線所有車站 ===
            temp_stations = []
            running_km = 0.0

            rows = target_table.find_all('tr')
            for row in rows:
                cols = row.find_all(['th', 'td'])
                if not cols or not row.find('td'): 
                    continue

                # 1. 抓車站編號 (★ 修正：擴寬到 A-Z，才能抓到生駒纜車的 Y 還有西信貴的 Z)
                codes = []
                for i, col in enumerate(cols):
                    if i < 3: 
                        codes.extend(re.findall(r'([A-Z]\d{2})', col.get_text(separator=' ')))
                codes = list(set(codes))

                # 2. 抓車站名稱
                station_name = "Unknown"
                for a_tag in row.find_all('a'):
                    if '駅' in a_tag.get('title', ''):
                        station_name = a_tag.text.strip()
                        break
                
                if station_name == "Unknown" and len(cols) > 1:
                    potential_name = cols[1].text.strip()
                    if not re.match(r'^[\d\.]+$', potential_name):
                        station_name = potential_name

                station_name = re.sub(r'\[.*?\]', '', station_name)
                station_name = re.sub(r'（.*?）', '', station_name)
                if station_name.endswith("駅"):
                    station_name = station_name[:-1]
                station_name = station_name.strip()

                exclude_words = ["駅名", "駅番号", "所在地", "累計キロ", "営業キロ", "接続路線", "備考"]
                if station_name in exclude_words or not station_name or station_name == "Unknown":
                    continue
                if "信号場" in station_name or "分界点" in station_name or "検車区" in station_name:
                    continue

                # 3. 抓取絕對里程數
                td_floats = []
                for i, col in enumerate(cols):
                    if i > 4: 
                        break
                    text = col.get_text(separator=' ', strip=True)
                    if '°' in text or '′' in text or '″' in text:
                        continue
                    for m in re.finditer(r'(?<!\d)(\d+\.\d+)(?!\d)', text):
                        td_floats.append(float(m.group(1)))
                
                if td_floats:
                    km_val = td_floats[-1]
                    running_km = km_val 
                else:
                    km_val = running_km

                temp_stations.append({
                    "codes": codes,
                    "name": station_name,
                    "km": km_val
                })

            # === Phase 2: 分岔邏輯過濾 (只保留全新車站與交會的端點) ===
            for stat in temp_stations:
                stat['is_new'] = stat['name'] not in global_stations

            kept_stations = []
            for i, stat in enumerate(temp_stations):
                keep = False
                if stat['is_new']:
                    keep = True
                elif i < len(temp_stations) - 1 and temp_stations[i+1]['is_new']:
                    keep = True
                elif i > 0 and temp_stations[i-1]['is_new']:
                    keep = True
                    
                if keep:
                    kept_stations.append(stat)

            # === Phase 2.5: 里程相對化 (第一站強制變 0.0) ===
            if kept_stations:
                base_km = kept_stations[0]['km']
                for stat in kept_stations:
                    stat['km'] = round(stat['km'] - base_km, 1)

            # === Phase 3: 全域編號合併與 JSON 生成 ===
            segment = {
                "id": line["id"],
                "name": line["name"],
                "stations": []
            }

            for stat in kept_stations:
                name = stat['name']
                codes = stat['codes']
                km = stat['km']
                
                if name not in global_stations:
                    global_stations[name] = {"ids": set(), "instances": []}
                
                for c in codes:
                    global_stations[name]["ids"].add(c)
                
                if global_stations[name]["ids"]:
                    merged_id = "_".join(sorted(list(global_stations[name]["ids"])))
                else:
                    merged_id = "Unknown"
                
                final_dict = {
                    "id": merged_id,
                    "name": name,
                    "km": km
                }
                
                for instance in global_stations[name]["instances"]:
                    instance["id"] = merged_id
                
                global_stations[name]["instances"].append(final_dict)
                segment["stations"].append(final_dict)
            
            if len(segment["stations"]) > 0:
                topology["segments"].append(segment)

            time.sleep(1)

        except Exception as e:
            print(f"  ❌ 抓取 {line['name']} 時發生錯誤: {e}")

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(topology, f, ensure_ascii=False, indent=4)
        print(f"\n✅ 爬取完成！所有路線已成功儲存至: {os.path.abspath(output_path)}")
    except Exception as e:
        print(f"❌ 寫入 JSON 檔案時發生錯誤: {e}")

if __name__ == "__main__":
    scrape_wikipedia_kintetsu()