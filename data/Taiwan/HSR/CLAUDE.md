# CLAUDE.md — 台灣高鐵 (HSR)

## 基本資訊

- **calendar_type**: `WEEKDAY_BITMAP`
- **view_type**: `LINEAR`（南北單一主線）
- **時刻表策略**: `DAILY_FILE`（每個日期一個 JSON 檔）

## 路線結構

單一 segment `thsr_main`，從南港到左營共 12 站，無分岔。

`train_color` 以車次號碼前兩碼分類（如 `"01"` 代表 01xx 車次）。

## 時刻表爬取

**腳本**: `script/fetch_and_transform_hsr.py`

**資料來源**: TDX 交通資料平台 API（免登入）
```
https://tdx.transportdata.tw/api/basic/v2/Rail/THSR/DailyTimetable/TrainDate/{date}?$format=JSON
```

**執行**:
```
py data/Taiwan/HSR/script/fetch_and_transform_hsr.py
```

在腳本底部設定 `start_date` / `end_date`，會自動展開為逐日處理。

**流程**:
1. 下載原始 TDX JSON → 存至 `json/raw_data/timetable_{date}.json`（備份用）
2. 轉換格式：`ArrivalTime`/`DepartureTime` (`HH:MM`) → 分鐘數，小於 4 點視為跨夜加 1440
3. `v` 值：首站 `0`、末站 `3`、中間站 `1`（注意：TRA 腳本用 `PASS=2`，HSR 只用 `0/1/3`）
4. 輸出至 `json/timetable/timetable_YYYYMMDD.json`
5. **自動更新** `json/available_dates.json`（merge + 排序去重）

## 注意事項

- HSR 不需要處理分岔，所有車次只有一個 segment
- `show_train_type: false`：前端不顯示車種文字，改以車次號碼前兩碼的顏色區分
