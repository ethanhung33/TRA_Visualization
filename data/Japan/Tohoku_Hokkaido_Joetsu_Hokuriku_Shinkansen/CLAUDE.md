# CLAUDE.md — 東北・北海道・上越・北陸新幹線

## 基本資訊

- **calendar_type**: `WEEKDAY_BITMAP`
- **view_type**: `LINEAR`
- **時刻表策略**: `WEEKEND_FILE`（weekday / holiday 兩個固定檔）

## 路線結構

| segment id | 區間 |
|-----------|------|
| THK_line | 東京－新青森 |
| HKD_line | 新青森－新函館北斗 |
| JTS_line | 大宮－新潟（上越） |
| HRK_line | 高崎－敦賀（北陸） |
| YMG_line | 福島－新庄（山形） |
| AKT_line | 盛岡－秋田（秋田） |

つばさ（山形）與こまち（秋田）在運行時與主線列車併結（連結/分離），需處理 `coupled_with` 邏輯。

## 時刻表爬取

**腳本**: `script/timetable.py`

**資料來源**: `jreast-timetable.jp` / `timetables.jreast.co.jp`

**執行**:
```
py data/Japan/Tohoku_Hokkaido_Joetsu_Hokuriku_Shinkansen/script/timetable.py
```

在腳本頂部設定 `START_DATE` / `END_DATE`（Python `date` 物件），決定運行日期範圍。輸出 `timetable_weekday.json` 與 `timetable_holiday.json`。

**三階段流程**:
1. 從 `TERMINAL_STATIONS`（端點站 ID 清單）的清單頁面，用 CSS class 與文字過濾只取「東北等新幹線」的按鈕連結（排除東海道），取前 2 個（純文字時刻，不取數位版）
2. 從每個子頁面收集 `/train/` 連結為 seed URLs，遞迴追蹤變體（`variants`，不同運行日的同一班車）
3. 解析每班車的停靠時間、運行日曆、併結資訊

**並行**: 20 workers

**輸出格式**: 含 `operation` 欄位（`daily`/`weekday`/`weekend`/`irregular`），irregular 班次額外含 `dates` 陣列。

## 特殊邏輯

### 車種白名單過濾 (`VALID_SHINKANSEN_NAMES`)

自動排除のぞみ、ひかり、こだま（東海道）及維修車（車次以 A/K 結尾）。

### 運行日解析 (`parse_calendar_logic`)

讀取 `div.serviceDayCalendar` 中的月曆 HTML，比對 `START_DATE`–`END_DATE` 範圍內的有效日期。若頁面有連結按鈕（variant），則加入下一輪遞迴抓取。

### 併結運轉處理 (`apply_coupling_logic`)

時刻表頁面的「併結運転」欄位記錄了與哪班車連結，但不一定有交會站資訊。`apply_coupling_logic` 使用「時空推論」：對兩班車的停靠站集合取交集，再依奇偶律（單數＝下行＝末端解連，雙數＝上行＝前端匯合）決定正確的分離/合併站。

最終在 `coupled_with` 陣列中儲存：`{"train_id": "...", "station_id": "...", "action": "split" | "direct"}`

### 直通標記 (`is_direct`)

頁面儲存格含「直通」文字或「└」符號時標記，表示此班車在該站與下一欄位的車次無縫接續（非物理上的同一輛車）。
