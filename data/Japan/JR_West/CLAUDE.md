# CLAUDE.md — 西日本旅客鉄道 (JR West)

## 基本資訊

- **calendar_type**: `WEEKDAY_BITMAP`
- **view_type**: 主要 `LINEAR`，大阪環状線為 `CIRCULAR`
- **時刻表策略**: `WEEKEND_FILE`（weekday / holiday 兩個固定檔）

## 路線結構

JR 西日本路網廣大，涵蓋東海道・山陽本線、山陰本線、紀勢本線等幹線及數十條支線。設有 `osaka_circular` view（大阪環状線 CIRCULAR 類型）。

智頭急行線（上郡–智頭）屬外部路網，在 `convert_jrwest.py` 中以 `OTHER_LINES` 字典臨時注入路線圖，輸出的 segment 會含 `is_other: true` 與 `system_path` 欄位。

## 時刻表爬取

**此系統分為兩步驟**，爬取與格式轉換分離：

### 步驟一：爬取原始資料

原始資料存放於 `json/data_new.json`（格式與腳本待確認），需先另行執行爬蟲取得。目前 `convert_jrwest.py` 直接讀取此檔，不包含下載邏輯。

### 步驟二：格式轉換

**腳本**: `script/convert_jrwest.py`

**執行**:
```
py data/Japan/JR_West/script/convert_jrwest.py
```

**輸出**:
- `json/timetable/timetable_weekday.json`
- `json/timetable/timetable_holiday.json`

## 特殊邏輯

### 大阪環状線 × 大和路線拓樸修補

大阪環状線（`osaka_loop_line`）與大和路線（`yamatoji_line`）在「今宮」站連通，但停靠清單中不一定有今宮。當偵測到相鄰兩站分屬這兩條線時，自動插入「今宮」通過站，依里程比例插值時間（`KM_MAP`）。

### 直通運轉配對

原始資料含 `直通運転` 欄位記錄接續車次號碼。轉換時逐一尋找接續車次，比對首末站是否相符，相符則在雙方的 `coupled_with` 中記錄 `action: "direct"` 與交會站 ID。

### 不規則日期解析 (`parse_japanese_dates`)

部分班次的運行日為日文字串（如「5月3日・4日・5日」或「6月1日～6月30日」），透過正規表示式解析月份與日期範圍，轉換為 `YYYY-MM-DD` 陣列。

### 空間分群防重複

同一 `no`（車次號碼）＋同一 `op_type` 的多段停靠（因多路線頁面重複）以「空間連通性」分群：車站集合有交集的 chunks 合併為同一班車，避免同班車被切成多個物件輸出。

### 輸出格式擴充

平日/假日分流依 `_is_wd`/`_is_we` 旗標判斷；irregular 班次保留 `dates` 陣列，其餘班次刪除。`coupled_with` 若為空陣列則刪除。
