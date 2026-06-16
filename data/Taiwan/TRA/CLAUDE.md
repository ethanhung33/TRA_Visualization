# CLAUDE.md — 台灣鐵路 (TRA)

## 基本資訊

- **calendar_type**: `WEEKDAY_BITMAP`（1-7 代表星期，用於前端篩選班次）
- **view_type**: `CIRCULAR`（環島路線）、`LINEAR`（支線）
- **時刻表策略**: `DAILY_FILE`（每個日期一個 JSON 檔）

## 路線結構

環島幹線由數個 segment 組成，分岔點如下：

| 分岔站 | 連接的 segments |
|--------|----------------|
| 八堵 | north_main ↔ eastern_trunk |
| 竹南 | north_main ↔ mountain_line / sea_line |
| 彰化 | mountain_line ↔ sea_line（南端） |
| 追分/成功 | sea_line ↔ mountain_line（成追線） |
| 枋寮 | south_main ↔ eastern_trunk |

## 時刻表爬取

**腳本**: `script/timetable.py`

**資料來源**: 台鐵 TIP 官網 (`railway.gov.tw`)

**執行**:
```
py data/Taiwan/TRA/script/timetable.py
```

**兩階段流程**:

1. **階段一 — 掃描看板**: 對多個採樣站點（`station_list`）查詢每日發車資訊，建立 `unique_trains_to_fetch`（車次 → 出沒時間與日期）
2. **階段二 — 下載時刻**: 對每個不重複車次呼叫單獨的時刻表 URL，使用 `ThreadPoolExecutor(max_workers=3)` 並行下載

**跨夜處理**: 若到達時間 < 前站出發時間，自動 `+ 1440`（分鐘）

**幽靈車過濾**: 比對看板上的目擊時間與時刻表絕對時間，排除「只在跨夜後出現」的隔日車次

**防爬機制**: 遇到 WAF（回應無 tbody）時清除 cookie 並重新取得首頁 session，最多重試 3 次

**輸出**: `json/timetable/timetable_YYYYMMDD.json`（每天一檔，在 `main()` 的 `start_date`/`end_date` 設定範圍）

## 特殊邏輯

### 成追線自動內插 (`patch_chengzhui`)

台鐵看板不顯示成追線的追分/成功停靠，但前端繪圖需要這兩站才能正確切換 segment。

判斷條件：相鄰兩站一個在 `COAST_STATIONS`（海線），另一個在 `MOUNTAIN_STATIONS`（山線），則在中間插入通過的追分→成功（或反向）。時間以前後站時間的 40%/60% 線性插值。

### segment 分配演算法 (`compile_train_data`)

從停靠站序列自動判斷每一段屬於哪個 segment：
- 相鄰兩站有共同 segment → 使用該 segment
- 無共同 segment → 尋找交會分岔站，依里程比例插值分岔時間，切開為兩段

### 可用日期更新

```
py data/Taiwan/TRA/script/available_date.py
```

需手動執行，輸出至 `json/available_dates.json`。
