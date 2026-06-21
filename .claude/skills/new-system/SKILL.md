---
name: new-system
description: 自動化新增一條鐵路系統到視覺化專案——探勘資料源、爬時刻表與里程、轉成本專案格式、自動設定顏色/view、開瀏覽器截圖自我 debug。當使用者說「新增 XX 鐵路/路線」「加一條新系統」「爬某鐵路時刻表並接上」時使用。
---

# 新增鐵路系統 (new-system)

把一條全新的鐵路系統，從零接到本視覺化專案。整條流程設計成**可被機器驗證、可自我修正**：
每產出一份資料就用 `tools/validate_system.py` 把關，最後用 `tools/screenshot.py` 真正「看」渲染結果。

> 核心原則：**先找官方結構化資料源（API / GTFS），HTML 爬蟲當最後手段。** 結構化來源能省掉 90% 的麻煩與防爬對抗。

> 🚫 **絕對禁止在 `main.js` 做任何路線/系統特判。** `main.js` 是所有系統共用的通用渲染引擎，永遠只能讀 `topology.json` / `setting.json` / `timetable_*.json` 的**通用欄位**來決定行為——不可出現任何路線名、系統 id、站名、segment id 的硬編 if/switch（例：`if (system === 'Hankyu')`、`if (name === '扇町')` 一律禁止）。
> 某系統需要不同行為時，**一律改成資料驅動**：要嘛在 setting/topology 加一個通用旗標或參數讓引擎讀（如 `is_other`、`view_type`、`show_train_id`），要嘛在該系統的 `script/` 轉換階段把資料整成引擎已能正確處理的形狀（如交會站用拓樸 id 而非站名字串，讓既有 dedup 自然生效）。
> 判斷準則：若一段 `main.js` 邏輯換一個系統就會壞、或需要列舉特定名稱才能跑，就是特判，必須移到資料或參數層。引擎只認「能力旗標」，不認「是哪條線」。

## 資料契約（必讀，這是唯一真相）

前端 `main.js` 真正讀取的格式（注意：根目錄 CLAUDE.md 對時刻表的描述已過時）：

- **topology.json**: `{operator_id, segments:[{id, name, stations:[{id, name, km}]}]}`
- **setting.json**: `{system_id, system_name, data_fetch_strategy, calendar_type, timezone_offset, view_presets:{<key>:{name, lines, view_type, button_color:[c1,c2]}}, train_color}`
  - `view_type` 只能是 `LINEAR` 或 `CIRCULAR`
  - `lines` 元素可為 segment id 字串，或 `{id, start, end}`（start/end 為車站「名稱」做區間截取）
  - `train_color` 可扁平 `{type:[c1,c2]}`，或巢狀 `{group:{subtype:[c1,c2]}}`（日本線）
  - 可選 `search_example`（字串，如 `"台北~花蓮"`）：搜尋框 placeholder 的範例。省略時前端自動從拓樸取（第一個 view 起站~迄站，環狀/無 preset 時退用拓樸首末站）→ 一般不需設；只有環狀線等自動推導不理想時才明確指定。
- **時刻表 timetable_*.json**: `[{no, type, segments:[{id, s:[stationId...], t:[arr,dep,...], v:[0|1|2|3...]}]}]`
  - 列車主鍵是 `no`（**不是** `train_number`，也沒有 `direction`）
  - `t` 長度必為 `2*len(s)`；`v` 長度必為 `len(s)`
  - `v`: 0=起點 1=停靠 2=通過 3=終點；時間單位為「分鐘」（跨夜 +1440）

最可靠的學習方式：**挑一個既有系統當範本**。`data/Taiwan/TRA`（環狀+分岔最複雜）、`data/Japan/Nankai`（多支線 LINEAR + 巢狀顏色）、`data/Taiwan/HSR`（單線最簡）。

## 流程（六步，逐步驗證）

### 步驟 0 — 釐清與選範本
先問清楚：哪條鐵路？目標路線範圍？營運日類型（平日/假日 or 逐日）？
依形狀挑一個既有系統當骨架，整個新目錄 `data/<國家>/<系統>/{json,script}` 比照它。

### 步驟 1 — 探勘資料源（最難，優先 API）
依序嘗試，找到一個就停：
1. **官方開放資料 / API**：台灣→TDX (tdx.transportdata.gov.tw)；日本→ODPT (developer.odpt.org)。
2. **GTFS feed**：搜尋 `<鐵路名> GTFS`，`stops.txt`/`stop_times.txt`/`trips.txt` 直接對應我們的格式。
3. **官方時刻表頁面 (HTML)**：最後手段，比照 `data/Taiwan/TRA/script/timetable.py`（含 WAF 對抗、跨夜處理）。

用 WebFetch/WebSearch 探勘端點與回傳結構；若是 JS 動態載入或有強防爬，請使用者協助貼一兩個關鍵 network request。把確定的資料源、端點、認證方式寫進該系統的 `CLAUDE.md`。

#### 日本通用來源：NAVITIME ダイヤグラム（已探勘確認）
`https://www.navitime.co.jp/diagram/` 對日本各鐵路都有時刻表，結構穩定，是日本線的預設 HTML 來源。
**注意**：navitime 為商業服務，務必尊重 robots.txt、嚴格限速（每請求 sleep ≥1s）、僅供個人用途。

端點鏈（與 TRA 兩階段爬法同構）：
| 階段 | 端點 | 取得 |
|------|------|------|
| 公司→路線 | `/diagram/company/{companyId}/` | 各路線 `lineId`（JR西=`00000002`、JR東=`00000004`、西鉄=`00000091`） |
| 路線→車站 | `/diagram/stationList?lineId={lineId}` | 車站順序 + 各站 `node` ID（在 href `?node=XXXX`） |
| 站→發車 | `/diagram/timetable?node={node}&lineId={lineId}&updown={0\|1}` | 該站某方向所有班次，每筆連到 stops 頁；**種別(快/特急…)只在此頁顯示** |
| 班次→停靠 | `/diagram/stops/{lineId}/{stopCode}/?node={node}&year=Y&month=M&day=D` | **單一列車完整停靠序列 + 各站 着/発 時刻**（黃金資料） |

爬法：① 掃幹線全部車站的 `timetable` 頁，解析 `<li.time-frame>` 蒐集 `stopCode`；② 對每個 `stopCode` 抓 `stops` 頁取完整停靠序列；③ 餵進轉換邏輯。可參考已完成的 `data/Japan/Keihan/script/{timetable.py,convert_timetable.py,build_topology.py}` 為範本。

**實戰確認的關鍵行為（京阪首跑挖出，務必照做）**：
- **任意日付は `&time=YYYY-MM-DD` で取得可**（重要、新發現）：timetable listing は `year/month/day`・`searchDate`・cookie を**無視**するが、**`&time=YYYY-MM-DD` だけは効く**（UI 的日期ピッカー Vue 元件が使う本物のパラメータ）。`...&updown=0&time=2026-07-18` でその日のダイヤだけが返る。→ **逐日 DAILY_FILE が必要なら `time=` で各日を明示掃描**（範本：`data/Japan/Tokkaido_Sanyo_Kyushu_Shinkansen/script/timetable.py --start --days`，各 stopCode の data-date を集合蓄積、stops は code 毎に 1 回だけ取得して全日付へ振り分け）。`time=` 省略時は「今日・明日・次の土曜」等の**自然プール（数日分、連續とは限らない）**のみ。
- **`time=` 不要なケース（平日/土休だけで足りる私鐵）**：每班 `<li.time-frame>` 自帶 `data-date`(運行日)、`data-name`(種別)、`data-dest`、`data-node`。自然プールの `data-date` の曜日で平日/土休に分桶し各カテゴリの最多日を採る（水〜日に実行すれば両方含む。月・火は週末を欠く）。**絕對不可用 `year/month/day`/href 的日期字串篩**（無視されるので錯日付になる）。種別優先取 `data-name`。方向由 stops 序列自身判斷（不靠 updown）。
- **stops 必須用「該連結自身的 lineId」抓**，不可全部硬套同一條：直通車在不同站的 timetable 連結會掛在不同 lineId（如京阪本線站=`00000285`、鴨東線站=`00000281`）；用錯 lineId 會抓到空頁。→ 掃描時連同 `href` 的 lineId 一起記錄，下載時各用各的。
- **跨 lineId 去重**：同一實體班次會在不同 lineId 各有一個 stopCode → 以內容簽章（首站+首發時刻+末站+種別）去重。
- **dwell 時刻**：停留站（待避/緩急接續）用 `dd.from-to-time`（着<br>発兩時刻），一般站用 `dd.time` → parser 兩者都要收，否則該停靠點整個漏掉。
- **站名正規化**：navitime 會加各式括號註記（`三条（京都府）`、`守口市〔京阪線〕`、`【…】`）→ NFKC 後把 `（）()〔〕【】［］` 內容全剝除再去「駅」字，否則對不上拓樸而被當幹線外站丟掉。
- **stops 頁的 node 參數不可留空**：`stops/{lineId}/{code}/?node=...` 的 node 對「部分車次」留空會回 **HTTP 400**（京阪約 40% 車次因此被靜默丟掉，包含整批ライナー）→ 必須帶一個「該車路線上的有效站 node」，最簡單就是用掃描時發現該 code 的車站 node。爬完務必看「失敗數」，>幾 % 就是哪裡不對。
- **種別変更直通車**（如京丹後 特急はしだて→快速）：同一編成不同列車番号、彼此直通；navitime 用**兩個 stopCode** 表示，每個 stops 頁都顯示**全程且時刻相同、僅種別不同** → 直接畫會變兩條全程線重疊（同一班同時是特急又是快速）。處理：掃描時記錄**每個 stopCode 被列在哪些站**（種別只在自己的區間出現），偵測「站序+時刻相同、種別不同」的成對 entry，依出沒站邊界推斷變更站，把每筆**裁成自己的區間**使其端對端相接。再用 **`coupled_with:[{train_id, station_id, action:"direct"}]`** 在交接站把兩段標為直通（前端畫直通接駁並串接）。見 `data/Japan/Tango/script/{timetable.py::split_henko_through, convert_timetable.py}`。
- **外運營商直通段（智頭急行式）**：直通車跑進別家公司的區間（如 JR西特急直通京丹後、或反向 JR 跑進智頭急行）。那些站不在本系統拓樸 → **不要丟掉**，收進 `{"id":..., "s":[...], "t":[...], "v":[...], "is_other":true, "system_name":"JR西日本", "system_path":"data/Japan/JR_West/"}` segment。前端**不畫在運行圖**，但會在底部資訊面板以該 operator 名標註並列出停靠站（可點 system_path 跳系統）。validator 會對 is_other 的段/站出 WARNING（如同 JR_West 的智頭），屬正常。
  - **`s` 的 id 規則（重要，踩過坑）**：is_other 段的「真正外站」（本系統拓樸沒有的，如大阪メトロ扇町）用**站名字串**即可；但 is_other 段頭尾的**境界站**（同時屬於本系統拓樸的交接站，如阪急天神橋筋六丁目、JR上郡）**必須用本系統的拓樸 id**，不可用站名字串。否則前端底部面板會：① 把境界站誤畫進外運營商藍框、② 與相鄰本系統段的同一站去重失敗而印兩次、③ 點擊時用站名去搜時刻表跳出假發車動態。轉換腳本作法：產生 is_other 段時，凡站名在本系統 `STATION_INFO` 中就改填其拓樸 id。前端僅以「id 是否存在於 topology」判斷一個站是本系統站還是外站，故同名跨運營商的站（如 JR 佐用 vs 別線佐用）不會誤判。
- navitime 為商業服務：限速 `sleep≈1.1s`、併發 `--workers` 預設 3（實測 8 仍可），僅個人用途。

**兩個資料缺口**：(a) `stops` 頁不含列車番号/種別 → `no` 用 `stopCode`（setting 設 `show_train_id:false` 隱藏）、`type` 從 timetable listing 的 `data-name` 帶過來；(b) navitime **沒有里程(営業キロ)** → 步驟 3 的 km 仍須從維基百科取得；navitime 也不標通過站，故 `v` 不需 2=PASS。

### 步驟 2 — 爬 raw 時刻表
寫 `script/timetable.py`（或 `fetch_*.py`）抓原始時刻表，**先存原始 JSON**再轉換（方便重跑轉換不必重爬）。並行抓取記得限速、加 User-Agent。

### 步驟 3 — 爬車站與里程（建拓樸）
寫 `script/build_topology.py`：通常從維基百科路線條目的車站表抓「站名 + 營業里程(km)」。
比照既有 `build_topology.py`。產出 `json/topology.json`。站名需與時刻表來源一致（必要時建對照表，參考 TRA 的 `KANJI_MAP` 思路）。

### 步驟 4 — 轉換成本專案格式
寫轉換邏輯：把 raw 時刻表 → 以「車次為中心」的 segments 結構。
分岔/跨線處理參考 TRA `compile_train_data()`（相鄰站找共同 segment，無共同則找交會站依里程插值切段）。產出 `json/timetable/timetable_*.json`。

**立刻驗證**：
```
py tools/validate_system.py data/<國家>/<系統>
```
有 ERROR 必修（前端會壞）；WARNING 檢視（多半是拓樸外站/缺色，可接受）。改完重跑直到無 ERROR。

### 步驟 5 — 自動設定顏色 / view / 參數
寫 `json/setting.json`：
- `train_color`：依該系統車種列出，用既有系統的色票風格（`[深色模式色, 淺色模式色]`；深色模式取 [0]，故 [0] 要夠亮/粉）。
  **日本線通用種別正規色（跨系統統一，請沿用）**：普通/各駅停車 `["#B0B0B0","#969696"]`（灰）、準急系 `["#86D98A","#2E7D32"]`（綠）、急行 `["#FF9472","#D84315"]`（橙）、快速急行/通勤快急 `["#FFCA5F","#EF6C00"]`（金）、区間急行 `["#8FC9FF","#1565C0"]`（淺藍）、特急 `["#FF7B7B","#C62828"]`（紅）、快速特急 `["#FF6E9C","#AD1457"]`（桃紅）、ライナー `["#B98EFF","#6A1B9A"]`（紫）、快速 `["#5BD1C4","#00796B"]`（青綠）。**具名特急/観光/Shinkansen 列車（サザン、こうや、ひのとり、しまかぜ、のぞみ…）維持各自獨立色，不套通用色。**
- `view_presets`：每條可選路線一個 preset。幹線環狀用 `CIRCULAR`，支線用 `LINEAR`。`button_color` 從既有調色盤挑。
- `calendar_type` / `data_fetch_strategy` / `timezone_offset` 依該系統營運日與時區設定。
  - **`data_fetch_strategy` 選項**：`DAILY_FILE`（逐日檔 `timetable_YYYYMMDD.json`，配 `available_dates.json` 月曆）、`WEEKEND_FILE`（平假日兩檔 `timetable_weekday/holiday.json`，配 `WEEKDAY_BITMAP` 自動推算或 `WEEKEND_SELECT` 手動切換）、`SINGLE_FILE`（**全年共用一份 `timetable_all.json`**，配 `WEEKDAY_BITMAP` 月曆 + `available_dates.json` 限定營運日）。
  - **觀光線/季節性公休**（如嵐山小火車：每日同班表，但週三+冬季公休）→ 用 `SINGLE_FILE`：只產一份 `timetable_all.json`（不必造 365 份重複逐日檔），`available_date.py` 只列營運日 → 月曆自動把公休日反灰不可選。可加通用欄位 `calendar_note`（字串）在月曆下顯示公休說明。範本見 `data/Japan/Sagano/`。
- 在 `data/global.json` 對應國家下新增 `{id, chinese_name, is_active:true}`。國家可扁平用 `systems:[...]`（如臺灣），或用可選的 `groups:[{id, chinese_name, systems:[...]}]` 分組顯示（如日本：新幹線 / 關西）→ 新系統放進對應 group 的 `systems`。分組純為首頁顯示,**不影響資料路徑**（仍是 `data/<國家>/<系統>/`）。

改完**再次驗證**（步驟 4 的指令），確保 view_presets 的 segment 引用、區間 start/end 站名都對得上。

### 步驟 6 — 開瀏覽器視覺 debug（自我閉環）
```
py tools/screenshot.py --init data/<國家>/<系統>/ --out shots/<系統>.png --wait 3500
```
然後用 Read 工具讀那張 PNG「看」結果，檢查：
- 路線形狀對不對（環狀首尾相接？支線方向？里程比例？）
- 列車線有沒有正確斜率、有沒有斷裂或亂跳
- 顏色有沒有套對、有沒有 console 錯誤（腳本會印出來）

要看特定 view preset：`--click "<按鈕文字>"`。要跑互動：`--eval "<JS>"`。
發現問題 → 回對應步驟修 → 重新驗證 + 截圖，直到畫面正確。

> 開圖時鏡頭預設對準「現在時刻」；但若現在落在班表時間範圍外（如觀光線只跑白天、深夜截圖會一片空白），引擎會自動改以**班表時間中央**為視窗中心（通用，非特判）。故限定時段營運的線在任何時刻截圖都看得到車。

## 收尾
- 寫 `data/<國家>/<系統>/CLAUDE.md`：記錄資料源、爬蟲流程、特殊邏輯（比照 TRA 那份）。
- 視需要寫 `script/available_date.py` 產生 `available_dates.json`。
- 跑最終全量驗證：`py tools/validate_system.py data/<國家>/<系統> --timetable-sample 0`。

## 何時該停下來問人
- 步驟 1 找不到任何結構化來源、且 HTML 有強防爬 → 請使用者貼 network request 或確認來源。
- 站名在時刻表與維基對不上、無法自動對應 → 請使用者確認對照。
- 截圖明顯不對但成因不明 → 附上截圖與 console 輸出問使用者。
