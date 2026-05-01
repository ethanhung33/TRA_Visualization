import json
import os

def extract_unique_train_types():
    # 動態取得 JSON 檔案的資料夾路徑
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_dir = os.path.join(script_dir, '..', 'json', 'timetable')
    
    # 你要檢查的檔案清單
    target_files = ['timetable_weekday.json', 'timetable_holiday.json']
    
    all_unique_types = set()

    print("🔍 開始掃描時刻表尋找所有車種...\n")

    for filename in target_files:
        file_path = os.path.join(json_dir, filename)
        
        if not os.path.exists(file_path):
            print(f"⚠️ 找不到檔案: {filename}，跳過掃描。")
            continue
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                timetable_data = json.load(f)
                
                # 遍歷每一班車，把 "type" 加入 Set 集合中 (Set 會自動排除重複)
                for train in timetable_data:
                    train_type = train.get("type", "Unknown")
                    all_unique_types.add(train_type)
                    
            print(f"✅ 已成功掃描 {filename}")
        except Exception as e:
            print(f"❌ 讀取 {filename} 時發生錯誤: {e}")

    # 將 Set 轉換為 List 並排序，讓輸出看起來更整齊
    sorted_types = sorted(list(all_unique_types))

    print("\n" + "="*50)
    print(f"🏆 掃描完成！共發現 {len(sorted_types)} 種不同的列車類型：")
    print("="*50 + "\n")
    
    # 逐行印出車種，順便幫你產生成 Python 字典的格式，方便你後續直接複製去配對顏色
    print("train_color_mapping = {")
    for t in sorted_types:
        print(f'    "{t}": "#FFFFFF",  # 請替換為你想要的色碼')
    print("}")
    
    print("\n" + "="*50)

if __name__ == "__main__":
    extract_unique_train_types()