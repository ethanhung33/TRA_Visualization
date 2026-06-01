# CLAUDE.md — 近畿日本鐵道 (Kintetsu)

## 基本資訊

- **calendar_type**: `WEEKEND_SELECT`（平日/土休日兩檔案）
- **view_type**: 全部為 `LINEAR`
- **時刻表策略**: `WEEKEND_FILE`

## 路線結構

日本最大私鐵，路線代碼如下（對應 `route_dict`）：

| 代碼 | segment id | 路線 |
|------|-----------|------|
| A | namba_nara | 難波線（大阪難波－布施） |
| B | kyoto_kashihara | 京都線・橿原線 |
| C | keihanna | けいはんな線 |
| E | nagoya | 名古屋線 |
| F | minamiosaka_yoshino | 南大阪線・吉野線 |
| M | yamada_toba_shima | 山田線・鳥羽線・志摩線 |

全路線皆有直通運轉（阪神、大阪 Metro 等），爬蟲限定在近鐵 topology 範圍內。

## 時刻表爬取

**腳本**: `script/timetable.py`

**資料來源**: `eki.kintetsu.co.jp`（**Shift-JIS 編碼**，需 `response.encoding = 'shift_jis'`）

**執行**:
```
py data/Japan/Kintetsu/script/timetable.py
```

**兩階段流程**:
1. 依 `slCode` 規律遍歷所有路線的 T5 頁面（清單寫在 `get_all_station_urls(d_val)` 內，`d_val=0` 為平日，`d_val=1` 為土休日）
2. 從 T5 取得 T7 連結（每班車一個 `tx` 參數），並行抓取詳細時刻

**並行**: 30 workers（`WORKERS = 30`）

**測試模式**: 設 `TEST_MODE = True` 可抽樣 150 班快速驗證

**輸出**:
- `json/timetable/timetable_weekday.json`
- `json/timetable/timetable_holiday.json`（`TEST_MODE=False` 時才生成）

## 特殊邏輯

### 站名對應 (`STATION_MAPPING`)

近鐵與其他業者共用站名不同，如「難波」→「大阪難波」、「奈良」→「近鉄奈良」。需在 `STATION_MAPPING` 維護對應表，若爬到未知站名且不在 `EXTERNAL_NETWORKS` 黑名單中，腳本會印出警告。

### 直通運轉過濾 (`EXTERNAL_NETWORKS`)

阪神電鐵、京都市營地下鐵、大阪 Metro 中央線等外部路網車站列入黑名單，只保留近鐵境內停靠紀錄。若某班車在近鐵境內停靠不到 2 站則直接丟棄。

### Segment 切分

透過「相鄰兩站共同路線集合的交集」逐站推進，交集為空時即切開為新 segment。切分後同樣以子集合去重邏輯移除重疊段。

### 物理指紋去重

同一班車可能在不同路線頁面出現多次，使用 `signature = f"{day}_{type}_{起站}_{發車時間}_{末站}_{到達時間}"` 確保每班車只輸出一次。
