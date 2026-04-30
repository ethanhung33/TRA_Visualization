import json
from pathlib import Path

date = "2026-04-29"  # 你抓到的 TDX 資料日期

def time_to_minutes(time_str):
    """將 HH:MM 格式轉換為從凌晨 0 點開始算的分鐘數"""
    if not time_str:
        return 0
    h, m = map(int, time_str.split(':'))
    
    # 處理跨夜的情況 (假設清晨 0 點~3點 代表隔天的 24~27)
    # 確保運行圖跨越午夜時，線條不會往回折
    if h < 4:
        h += 24
    return h * 60 + m

def generate_compact_json(data, output_path):
    """
    客製化 JSON 輸出器：
    外層保持換行與縮排，但將 segments 內的每一個路段強制壓縮成一行。
    """
    # 確保輸出的資料夾存在 (防呆機制)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("[\n")
        for i, train in enumerate(data):
            f.write('  {\n')
            f.write(f'    "no": "{train["no"]}",\n')
            f.write(f'    "type": "{train["type"]}",\n')
            f.write('    "segments": [\n')
            
            # 將每一個 segment 轉換為無空格的一行 JSON 字串
            seg_lines = []
            for seg in train["segments"]:
                # separators=(',', ':') 可以去除 JSON 序列化時產生的多餘空格
                seg_str = json.dumps(seg, ensure_ascii=False, separators=(',', ':'))
                seg_lines.append(f'      {seg_str}')
            
            # 將壓縮好的 string 用換行符號連接寫入
            f.write(",\n".join(seg_lines) + "\n")
            f.write('    ]\n')
            
            if i < len(data) - 1:
                f.write('  },\n')
            else:
                f.write('  }\n')
        f.write("]\n")

def convert_thsr_timetable(input_json_path, output_json_path):
    # 讀取 TDX 高鐵原始時刻表
    print(f"正在讀取原始資料: {input_json_path}")
    with open(input_json_path, 'r', encoding='utf-8') as f:
        tdx_data = json.load(f)

    formatted_data = []
    
    # 遍歷每一班車
    for t in tdx_data:
        train_info = t.get('DailyTrainInfo', {})
        train_no = train_info.get('TrainNo', '')
        
        # 1. 將車種設定為車次的前兩位
        train_type = train_no[:2] if len(train_no) >= 2 else train_no
        
        s_list = []  # 車站 ID
        t_list = []  # 分鐘數 (到站, 離站)
        v_list = []  # 站點屬性 (0=起站, 1=中途, 3=終點)
        
        # 確保停靠站照順序排列
        stops = sorted(t.get('StopTimes', []), key=lambda x: x.get('StopSequence', 0))
        
        for i, stop in enumerate(stops):
            station_id = stop.get('StationID')
            s_list.append(station_id)
            
            arr = time_to_minutes(stop.get('ArrivalTime'))
            dep = time_to_minutes(stop.get('DepartureTime'))
            t_list.extend([arr, dep])
            
            # 判斷站點屬性
            if i == 0:
                v_list.append(0)  # 起站
            elif i == len(stops) - 1:
                v_list.append(3)  # 終點站
            else:
                v_list.append(1)  # 中途停靠站
                
        # 建立這班車的 segments (高鐵本線)
        segment = {
            "id": "thsr_main", # 對應 topology.json 的 ID
            "s": s_list,
            "t": t_list,
            "v": v_list
        }
        
        formatted_data.append({
            "no": train_no,
            "type": train_type,
            "segments": [segment]
        })
        
    # 2. 呼叫客製化的寫檔器，讓 segments 變成單行
    generate_compact_json(formatted_data, output_json_path)
    
    print(f"✅ 轉換完成！總共處理了 {len(formatted_data)} 班列車。")
    print(f"✅ 已成功將資料存入: {output_json_path}")

if __name__ == "__main__":
    # 使用 pathlib 處理路徑
    SCRIPT_DIR = Path(__file__).parent
    JSON_DIR = SCRIPT_DIR.parent / "json"
    
    # 使用你自訂的路徑結構 (raw_data -> timetable)
    input_file = JSON_DIR / "raw_data" / f"timetable_{date}.json"
    remove_dash_date = date.replace("-", "")
    output_file = JSON_DIR / "timetable" / f"timetable_{remove_dash_date}.json"
    
    # 執行轉換
    convert_thsr_timetable(input_file, output_file)