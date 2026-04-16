import requests
from bs4 import BeautifulSoup
import json
import re
from pathlib import Path

import mileage_data 

def extract_segment(ring_dict, start_station, end_station=None):
    segment_dict = {}
    recording = False
    base_dist = 0
    
    for name, dist in ring_dict.items():
        # 注意：我們比對起點和終點時，也要考慮使用者可能在起終點加了標記
        clean_name = name.replace("(終)", "").replace("（終）", "").strip()
        
        if clean_name == start_station and not recording:
            recording = True
            base_dist = dist
            
        if recording:
            segment_dict[name] = dist - base_dist
            
            if end_station and clean_name == end_station:
                break
                
    return segment_dict

RAW_DATA_MAP = {
    "north_main": extract_segment(mileage_data.ring_mountain, '八堵', '竹南'),
    "mountain_line": extract_segment(mileage_data.ring_mountain, '竹南', '彰化'),
    "sea_line": extract_segment(mileage_data.ring_sea, '竹南', '彰化'),
    "south_main": extract_segment(mileage_data.ring_mountain, '彰化', '枋寮'),
    "eastern_trunk": extract_segment(mileage_data.ring_mountain, '枋寮', None)
}

LINE_NAMES = {
    "north_main": "縱貫線北段", "mountain_line": "山線",
    "sea_line": "海線", "south_main": "縱貫線南段", "eastern_trunk": "東部幹線"
}

def fetch_official_ids():
    print("🌐 正在連線台鐵抓替代碼...")
    res = requests.get("https://www.railway.gov.tw/tra-tip-web/tip/tip001/tip111/view", headers={"User-Agent": "Mozilla"})
    soup = BeautifulSoup(res.text, "html.parser")
    name_to_id = {}
    for name_el, code_el in zip(soup.find_all('div', class_=re.compile(r'traincode_name\d?')), soup.find_all('div', class_=re.compile(r'traincode_code\d?'))):
        name, code = name_el.text.strip(), code_el.text.strip()
        if code.isdigit() and len(code) == 4:
            name_to_id[name] = name_to_id[name.replace("臺", "台")] = name_to_id[name.replace("台", "臺")] = code
    name_to_id["蘇澳新"] = name_to_id.get("蘇澳新", "7130") 
    name_to_id["鳳鳴"] = name_to_id.get("鳳鳴", "1075")
    return name_to_id

def main():
    name_to_id = fetch_official_ids()
    topology_data = {"operator_id": "TRA", "segments": []}
    
    print("\n⚙️ 開始進行動態切片與拓樸建構：")
    for line_id, dist_dict in RAW_DATA_MAP.items():
        if not dist_dict:
            print(f" ⚠️ 警告：區段 {line_id} 切片失敗，請檢查資料檔！")
            continue
            
        segment_name = LINE_NAMES.get(line_id)
        segment = {"id": line_id, "name": segment_name, "stations": []}
        
        for st_name, raw_dist in dist_dict.items():
            # 🌟 核心防呆：自動過濾掉結尾的 (終)，還原真實站名
            clean_st_name = st_name.replace("(終)", "").replace("（終）", "").strip()
            
            segment["stations"].append({
                "id": name_to_id.get(clean_st_name, "UNKNOWN"),
                "name": clean_st_name,  # 寫入 JSON 的是乾淨的站名
                "km": raw_dist / 10.0
            })
            
        topology_data["segments"].append(segment)
        print(f" ✔️ 生成區段：{segment_name} (共 {len(segment['stations'])} 站)")

    current_dir = Path(__file__).parent
    json_dir = current_dir.parent / "json"
    json_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = json_dir / "topology.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(topology_data, f, ensure_ascii=False, indent=2)
        
    print(f"\n🎉 檔案已寫入：\n   👉 {output_path.resolve()}")

if __name__ == "__main__":
    main()