# tools/ — 自動化鷹架

讓 Claude 能在無人監督下新增鐵路系統並自我除錯的工具。完整流程見 `.claude/skills/new-system/SKILL.md`（或對 Claude 說 `/new-system`）。

## validate_system.py — 資料契約驗證器

檢查一個系統目錄是否符合前端 `main.js` 真正讀取的格式（拓樸/設定/時刻表的交叉引用、`t`/`v` 陣列長度、view_preset 引用等）。是自動化流程的「機器回饋」來源。

```
py tools/validate_system.py data/Taiwan/TRA                  # 抽查 2 個時刻表檔
py tools/validate_system.py data/Japan/Nankai --timetable-sample 0   # 全量檢查
```

- 退出碼 0 = 無 ERROR（可能有 WARNING），1 = 有 ERROR，2 = 檔案問題。
- **ERROR** = 前端會壞，必修。**WARNING** = 渲染不完整但可運作（如拓樸外車站、缺色車種）。
- **全站覆蓋檢查**：用 `--timetable-sample 0`（檢查全部時刻表檔）時，會驗證拓樸中每站是否都有列車停靠；有空站會列出（多半是站名對照漏掉，如 navitime 的 `〔京阪線〕` 後綴）。抽查模式不做此檢查以免誤報。

## interpolate_passes.py — 沿拓樸內插通過站

時刻表只記停靠站；兩個相鄰停靠之間走哪條路，若交給前端 `interpolatePassingStations()` 猜，環狀線（山手線 東京 同在段頭段尾）與無共同 segment 的斷點都會繞錯邊。本工具在轉換階段就把路徑定下來：

1. 以拓樸建圖（節點＝站 id、邊＝同 segment 相鄰站，權重＝里程差）。
2. 每班車依時刻排序 segment，把連續的本系統 segment 攤平（`is_other` 段是斷點，不跨越）。
3. 相鄰停靠：同在原派段內 → 只在該段內找最短路（保留派段決策、環狀線自動選近側）；否則全圖 Dijkstra（換段懲罰）。隱含速度超過上限（預設 200 km/h）者放棄、原樣斷開。
4. 依里程比例內插 `v=2` 通過站，依路徑重切 segment。

```
py tools/interpolate_passes.py data/Japan/JR_West --dry-run     # 只看報告
py tools/interpolate_passes.py data/Japan/JR_East               # 就地改寫 timetable_*.json
```
建議在各系統轉換腳本中直接 `from interpolate_passes import PassInterpolator` 呼叫（見 JR_East）。前端遇到「每對相鄰停靠在拓樸上都相鄰」的 segment 會跳過自己的補站。

## screenshot.py — 視覺除錯（給 Claude 一雙眼睛）

自起臨時 HTTP server、headless Chromium 載入 `index.html`、呼叫前端 `init()` 載入指定系統、截圖成 PNG，Claude 再用 Read 工具「看」結果。會印出 console 錯誤與頁面例外。

```
py tools/screenshot.py --init data/Taiwan/TRA/ --out shots/tra.png --wait 3500
py tools/screenshot.py --init data/Japan/Nankai/ --click "南海本線" --out shots/nankai.png
```

首次需安裝瀏覽器：`py -m playwright install chromium`（playwright 套件已安裝）。
截圖輸出在 `shots/`（已 gitignore）。

## build_station_geo.py — 路網圖車站座標

產生 `json/stations_geo.json`（`{"stations": {id: [lon, lat]}}`），供前端「🗺️ 從路網圖選線」繪製地理路網圖。沒有這個檔的系統不會顯示該按鈕。

```
py tools/build_station_geo.py Taiwan/TRA
py tools/build_station_geo.py Taiwan/HSR
```

- 資料源寫在 `SOURCES`（目前台鐵/高鐵皆為 TDX 免註冊 Station API）；新增系統時加一個回傳 `{station_id: (lon, lat)}` 的函式即可。
- topology 有、資料源沒有的車站（如新站）依同路段前後兩站的里程比例內插，列在輸出的 `interpolated`。

## schematic_layout.py — 示意路網圖

把車站排成地鐵圖風格的示意座標，寫進 `stations_geo.json` 的 `schematic`（座標）與 `schematic_bends`（兩站之間的轉角點）。前端路網圖預設顯示示意圖，可切回地理圖。`build_station_geo.py` 會自動呼叫。

```
py tools/schematic_layout.py Taiwan/TRA
```

- **有 `json/schematic_spec.json`（建議）**：照手寫版面排，仿 [4960fh7/TRA](https://github.com/4960fh7/TRA) 的拓樸圖。每條 line 是「路段切片串接 + 格點折線」，車站沿折線等距排列；支線用 `dir` 從已排好的交會站直直伸出。台鐵的版面是環島矩形 + 平行海線 + 直線支線，見 `data/Taiwan/TRA/json/schematic_spec.json`。
- **沒有版面檔**：自動排出同樣風格的圖（建構式，零點幾秒）：找出地理上最外圈的環排成矩形、四角挑最東北/西北/西南/東南的非交會站；兩端已排好的路徑（如海線、成追線）以直線 / L 形 / ㄈ 形繞行，先排長的；支線從交會站直直伸出。沒有環的路網把最長路線沿地理主軸排成一直線。可調參數在檔頭：`MIN_GAP`（線與線最小間距）、`OFFSETS`（ㄈ 形外移距離）、`ASPECT_KEEP`（矩形保留地理寬高比的程度）。
