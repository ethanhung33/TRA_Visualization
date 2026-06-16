# CLAUDE.md — 南海電鐵 (Nankai)

## 基本資訊

- **calendar_type**: `WEEKEND_SELECT`（平日/土休日兩檔案）
- **view_type**: 全部為 `LINEAR`
- **時刻表策略**: `WEEKEND_FILE`（weekday / holiday 兩個固定檔）

## 路線結構

以 `難波` 為起點輻射出兩條主軸：
- **本線系統**: main_line → airport_line（泉佐野分岔）、kada_line（和歌山市分岔）
- **高野線系統**: koya_line → 高師浜線、多奈川線（各支線）

segment 間重疊的站（如 難波–天下茶屋 同時屬於本線與高野線）由子集合去重邏輯處理。

## 時刻表爬取

**腳本**: `script/timetable.py`

**資料來源**: `nankai.co.jp` 官網車站時刻表頁面

**執行**:
```
py data/Japan/Nankai/script/timetable.py
```

**三階段流程**:
1. 掃描 `CORE_STATION_URLS`（約 34 站）的 HTML，收集 T5 目錄連結
2. 解析 T5 頁面取得所有 T7 列車連結（包含 `tx` 參數與平日/土休日分類）
3. 並行下載 T7 頁面（`#ekt` table），解析各站停靠時間

**並行**: 收集 T5 用 10 workers，下載 T7 用 15 workers；HTTP 呼叫統一透過 `@lru_cache` 避免重複請求

**輸出**:
- `json/timetable/timetable_weekday.json`
- `json/timetable/timetable_holiday.json`

## 特殊邏輯

### 跨夜時間處理

`time_to_minutes(time_str, prev_mins)` 使用前一站時間作為基準，若計算出的分鐘數比 `prev_mins - 300` 還小，則累加 1440，直到合理為止。必須以「預處理（Pre-calculation）」方式先對整班車所有停靠站按序算出絕對時間，再進行 segment 切分。

### 重疊路線去重 (`filtered_segments`)

針對難波–天下茶屋等「本線與高野線共用站」區間，使用 `_s_set` 子集合比對刪除較短的重複段。當兩段車站數相同時（Tie），用車種名稱配分決定哪條路線才是正確歸屬（空港急行/サザン → 本線；こうや/りんかん → 高野線）。

### 車種識別

依 `PREFIX_LIST` 前綴比對（如「ラα」→「特急ラピートα」），未匹配的車種會印出警告，需補充到 PREFIX_LIST。
