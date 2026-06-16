鐵道運行圖平台 (Railway Stringline Diagram)
============================================================

運行圖網址：https://ethanhung33.github.io/TRA_Visualization/
這是一個基於 Python (資料處理) 與 Web (Canvas/JS 渲染) 的通用鐵道運行圖視覺化系統。
本專案採用「資料驅動 (Data-driven)」架構，旨在支援不同國家、不同拓樸結構（如環狀線、分岔線）的鐵路系統。

有任何疑問或興趣，歡迎聯絡ethanhung33@gmail.com

------------------------------------------------------------
[1] 專案目錄架構 (Project Structure)
------------------------------------------------------------
本專案目前的實際結構如下：

```
TRA_Visualization/
├── index.html            # 前端頁面入口
├── main.js               # 前端渲染與互動邏輯
├── style.css             # 頁面樣式
├── README.md             # 專案說明文件
├── fonts/                # 字型資源
├── data/                 # 資料與腳本根目錄
│   ├── global.json       # 全域設定
│   ├── Japan/            # 日本路線資料
│   │   └── JR/           # JR 相關資料與腳本
|   |   ...
│   └── Taiwan/           # 台灣路線資料
│       ├── HSR/          # 台灣高鐵資料
│       └── TRA/          # 台鐵資料
│           ├── json/     # 台鐵視覺化設定與輸出 JSON
│           │   ├── available_dates.json
│           │   ├── setting.json
│           │   ├── topology.json
│           │   └── timetable/  # 編譯後時刻表
│           │       ├── timetable_20260415.json
│           │       ├── timetable_20260416.json
│           │       └── ...
│           └── script/   # 資料整理與轉換腳本
...
```

目前支援系統：
```
台灣
  - 台鐵
  - 高鐵
日本
  - 南海電鐵
  - 近鐵
  - 東北/北海道/北陸/上越新幹線
  - 山陽新幹線
  - JR西日本
```


------------------------------------------------------------
[2] 設定檔定義 (Configuration Definitions)
------------------------------------------------------------
1. topology.json (路線拓樸)
   只描述路線的實體結構，由 segments (路段) 組成，每段為一串帶里程的車站：
   - 車站清單與里程 (km)，前端據此計算 Y 軸座標。
   - 路段交會/分岔以「共用車站 ID」隱式表示：同一車站 ID 出現在多個 segment
     即為分岔點 (例如竹南 1250 同屬 north_main、mountain_line、sea_line)，
     前端 getProcessedSegments() 據此自動接合路段並處理方向翻轉。

2. setting.json (系統參數與視覺樣式)
   集中管理整個系統的設定，「時間分類方式」與各項系統參數都在此檔：
   - 系統識別：system_id、system_name。
   - data_fetch_strategy (時刻表檔案策略，決定產出幾份 JSON)：
       · DAILY_FILE   — 每個日期各一份檔 (timetable_YYYYMMDD.json)，如台鐵。
       · WEEKEND_FILE — 平日 / 假日各一份檔 (timetable_weekday.json、timetable_holiday.json)，如近鐵、JR 西日本。
   - calendar_type (前端日期選擇方式)：
       · WEEKDAY_BITMAP — 以日曆挑選任一日期 (再依星期 1-7、valid_until 等條件篩選班次)。
       · WEEKEND_SELECT — 只提供「平日 / 假日」兩個選項，不開放選日期。
   - view_presets：各視角預設 (路線組合、view_type 為 LINEAR / CIRCULAR、按鈕顏色)。
   - train_color：各車種對應的顏色代碼 (深色 / 淺色模式)。
   - 其他參數：timezone_offset (時區)、time_stretch_ratio (X 軸縮放)、show_train_id (是否顯示車次號) 等。

   註：data_fetch_strategy 與 calendar_type 為獨立兩軸，可自由組合。
   例如 JR 西日本採 WEEKEND_FILE + WEEKDAY_BITMAP：檔案分平假日，但仍用日曆選日期，
   以支援臨時 / 期間限定 (X月Y日まで運転) 等需要實際日期的班次。

3. timetable.json (標準化時刻表)
   由各路線 script/ 內的腳本產出，採以車次為中心 (Train-centric) 的結構：
   - 每班車含車次號 (no)、車種 (type)、運行類別 (operation) 與方向。
   - segments 陣列記錄各路段的車站序列 (s)、時間 (t，分鐘) 與停靠類型 (v：0 一般停靠 / 2 通過)。


------------------------------------------------------------
[3] 開發工作流 (Workflow)
------------------------------------------------------------
各路線系統的腳本與流程不統一（檔名、步驟皆因資料來源而異），都放在各自的
data/<國家>/<系統>/script/ 下。共通概念可分為三階段：

步驟 1. 建立拓樸 (Topology):
        多數系統以 script/build_topology.py 產生 topology.json (爬維基或官方里程，
        輸出車站清單與里程)；台鐵里程另由 mileage_data.py 維護。

步驟 2. 爬取與轉換時刻表 (Timetable):
        各系統各有腳本，輸出標準化時刻表 JSON，例如：
        - 台鐵     : script/timetable.py
        - 台灣高鐵 : script/fetch_and_transform_hsr.py
        - 日本各線 : script/timetable.py
                     (JR 西日本為兩步：先爬出 data_new.json，再用 convert_jrwest.py 轉檔)
        部分系統另有 available_date.py 更新可用日期、train_type.py 維護車種顏色。

步驟 3. 前端渲染 (Web Rendering):
        無離線編譯步驟。前端 main.js 直接讀取 topology.json + setting.json + 時刻表 JSON，
        在 HTML5 Canvas 上即時計算座標 (buildLookupY / getProcessedSegments) 並繪製運行圖。


------------------------------------------------------------
[4] 技術棧 (Tech Stack)
------------------------------------------------------------
- Backend: Python 3.x (Requests, BeautifulSoup, Pandas)
- Frontend: HTML5, Vanilla JavaScript, CSS3
- Graphics: HTML5 Canvas API (高效能密集線條渲染)