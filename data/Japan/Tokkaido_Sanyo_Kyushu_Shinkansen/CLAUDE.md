# CLAUDE.md — 東海道・山陽・九州・西九州新幹線

## 基本資訊

- **calendar_type**: `WEEKDAY_BITMAP`
- **view_type**: `LINEAR`
- **時刻表策略**: `DAILY_FILE`（每個日期一個 JSON 檔）

## 路線結構

| segment id | 區間 |
|-----------|------|
| tokaido_line | 東京－新大阪 |
| sanyo_line | 新大阪－博多 |
| kyushu_line | 博多－鹿兒島中央 |
| nishi_kyushu_line | 武雄溫泉－長崎 |

## 時刻表爬取

**腳本**: `script/timtable.py`（注意：檔名少一個 'e'，是 typo）

**資料來源**: JR Odekake (`timetable.jr-odekake.net`)

**必要前置檔案**: `json/station_route_shinkansen.json`（路線入口定義，需手動維護或先行建立）

**執行**:
```
py data/Japan/Tokkaido_Sanyo_Kyushu_Shinkansen/script/timtable.py
```

在腳本底部設定 `target_date`（格式 `YYYYMMDD`），輸出至 `json/timetable/timetable_{target_date}.json`。

**兩階段流程**:
1. `fetch_and_parse_timetable`: 讀取 `station_route_shinkansen.json` 內的路線 ID → 對每條路線抓站別時刻表 → 正規表示式擷取 train ID → 下載各車次的 `<tbody class="train-details">` 與 `<tbody class="time-details">`
2. `convert_to_segments`: 比對 topology.json，以 `_s_set` 子集合去重邏輯過濾重疊段

**時間格式**: 所有時間為 `HH:MM` 直接轉分鐘，無跨夜補正（新幹線末班較早，無此問題）

## 特殊邏輯

### HTML 解析方式

使用純 regex（非 BeautifulSoup），從 `<tbody>` 中逐行比對 `<th>` 站名與 `<td>` 時間欄位（每班車佔 2 個 td：`着`/`発`）。跳過「レ」（通過）與「||」（未停）符號。

### 重疊路線去重

與 Nankai/Kintetsu 相同的 `_s_set` 子集合比對邏輯，但此處不需要 Tie-breaker（各新幹線路段無相同站數的重疊問題）。
