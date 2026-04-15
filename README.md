Universal Railway Stringline Generator (通用鐵道運行圖生成平台)
============================================================

這是一個基於 Python (資料處理) 與 Web (Canvas/JS 渲染) 的通用鐵道運行圖視覺化系統。
本專案採用「資料驅動 (Data-driven)」架構，旨在支援不同國家、不同拓樸結構（如環狀線、分岔線）的鐵路系統。

------------------------------------------------------------
[1] 專案目錄架構 (Project Structure)
------------------------------------------------------------
本專案將核心邏輯與各系統資料完全分離，結構如下：

railway-stringline/
├── data/
│   ├── Taiwan/
│   │   └── TRA/
│   │       ├── route.json          # [系統規則] fetch_strategy: "DAILY_FILE"
│   │       ├── option.json
│   │       ├── distance.json
│   │       ├── crawl_tra.py
│   │       └── timetables/         # 📁 [新增] 專屬收納庫：原始時刻表
│   │           ├── raw_2026-04-14.json
│   │           └── raw_2026-04-15.json
│   └── Japan/
│       └── Nankai/
│           ├── route.json          # [系統規則] fetch_strategy: "PATTERN_FILE"
│           ├── ...
│           └── timetables/         # 📁 [新增] 專屬收納庫
│               ├── raw_weekday.json
│               └── raw_holiday.json
│
├── scripts/
│   └── compiler.py
│
└── web/
    ├── index.html
    └── public/                     # 前端 fetch 的唯一入口
        ├── TRA/                    # 📁 [新增] 按系統分類的編譯結果
        │   ├── render_2026-04-14.json
        │   └── render_2026-04-15.json
        └── Nankai/
            ├── render_weekday.json
            └── render_holiday.json


------------------------------------------------------------
[2] 設定檔定義 (Configuration Definitions)
------------------------------------------------------------
1. route.json (系統特徵)
   定義該鐵路系統的獨特屬性：
   - Topology: 定義分岔節點 (Split/Merge) 與環狀連通性。
   - Temporal Policy: 定義時間分類方式 (WEEKDAY_BITMAP 1-7 或 SERVICE_GROUP 平假日)。
   - System Metadata: 系統名稱、預設視角、是否隱藏車次 ID。

2. option.json (視覺樣式)
   控制圖表呈現細節：
   - Train Styles: 各車種 (如自強、Rap:t) 對應的顏色代碼與線條屬性。
   - Grid Layout: X 軸 (時間) 與 Y 軸 (距離) 的預設縮放比例。

3. timetable.json (標準化時刻表)
   由 crawl_timetable.py 產出，採用以車次為中心 (Train-centric) 的語意化結構：
   - 包含每班車的 train_number, type, direction。
   - 包含 stops 陣列，記錄每站的 arr (到達) 與 dep (出發) 分鐘數。


------------------------------------------------------------
[3] 開發工作流 (Workflow)
------------------------------------------------------------
步驟 1. 資料爬取 (Data Collection):
        執行各別資料夾下的 crawl_*.py，取得最新的時刻表與里程。

步驟 2. 邏輯編譯 (Logical Compilation):
        使用 compiler.py 根據 route.json 的拓樸規則，將時刻表轉換為前端 Canvas 座標。

步驟 3. 前端渲染 (Web Rendering):
        網頁讀取編譯後的 JSON，透過 renderer.js 在 HTML5 Canvas 上繪製運行圖。


------------------------------------------------------------
[4] 技術棧 (Tech Stack)
------------------------------------------------------------
- Backend: Python 3.x (Requests, BeautifulSoup, Pandas)
- Frontend: HTML5, Vanilla JavaScript, CSS3
- Graphics: HTML5 Canvas API (高效能密集線條渲染)