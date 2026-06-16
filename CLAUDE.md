# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 部署

**正式環境**：[https://ethanhung33.github.io/TRA_Visualization/](https://ethanhung33.github.io/TRA_Visualization/)
透過 GitHub Pages 部署，`main` branch 的內容即為線上版本。開發時在獨立 branch（如 `train-split`）進行，完成後才合併至 `main`。

## Commands

**啟動前端（本地開發用）**
直接用瀏覽器開啟 `index.html`，或透過任意 HTTP server 服務：
```
py -m http.server 8080
```
然後開啟 `http://localhost:8080`。

**爬取時刻表資料**（各路線腳本不同，需進入對應目錄執行）
```
# 台鐵
py data/Taiwan/TRA/script/timetable.py

# 高鐵
py data/Taiwan/HSR/script/fetch_and_transform_hsr.py

# 日本各路線
py data/Japan/<路線>/script/timetable.py
```

**更新可用日期清單**
```
py data/Taiwan/TRA/script/available_date.py
```

## 架構概覽

本專案採用三層資料驅動架構：

```
Python 腳本 → JSON 靜態資料 → 前端 Canvas 渲染
```

### 資料層 (`data/<國家>/<路線>/`)

每個路線目錄的結構：
- `json/topology.json` — 路線拓樸（車站清單、里程、分岔/環狀連通性）
- `json/setting.json` — 視覺設定（車種顏色、view presets、時區、日曆類型）
- `json/timetable/timetable_YYYYMMDD.json` — 每日編譯後時刻表（前端直接讀取）
- `json/available_dates.json` — 可用日期清單
- `script/` — 爬蟲與資料轉換腳本

`data/global.json` 定義所有國家與路線的入口清單（`is_active` 控制首頁是否顯示）。

### 前端層（`main.js`，單檔 ~5400 行）

整個前端為單一 `main.js`，主要區塊：

| 區塊 | 功能 |
|------|------|
| 全域變數 / CONFIG | Canvas 縮放、padding、攝影機座標 |
| `init(systemPath)` | 載入路線（讀取 topology + setting + timetable） |
| `buildLookupY()` | 將 topology segment 的里程轉換為 canvas Y 座標 |
| `drawFrame()` | Canvas 主繪製迴圈（分層：lines → trains → labels） |
| `getProcessedSegments()` | 根據 view preset 處理路線分岔/截取/反轉 |
| `calculateStationWeights()` | 計算各站停靠次數，用於站名 Greedy Label Placement |
| 互動事件（click/mousemove/touch） | 列車/車站選取、拖曳、縮放 |
| 搜尋系統 | 關鍵字搜尋列車與車站、SearchHistoryManager |
| 底部面板 | 選取列車/車站後的詳細資訊面板 |

### 時刻表 JSON 格式

編譯後的時刻表以「車次為中心」儲存：
```json
{
  "train_number": "1234",
  "type": "自強",
  "direction": "north",
  "segments": [
    {
      "id": "segment_id",
      "s": ["stationId1", "stationId2"],
      "t": [dep1, arr2, dep2, arr3],
      "v": [0, 0, 2]
    }
  ]
}
```
- `s`：車站 ID 陣列
- `t`：時間陣列（分鐘，每站兩個值：到達/出發），長度為 `s.length * 2`
- `v`：停靠類型（`0` = 一般停靠，`2` = 通過不停）

### 拓樸類型

`setting.json` 中 `view_presets` 的 `view_type`：
- `CIRCULAR`：環狀線（如台鐵環島），Y 軸首尾相接，`loopHeight` 控制一圈高度
- `LINEAR`：線性路線，Y 軸上下為終點站

分岔路線（如山線 + 海線）透過 `getProcessedSegments()` 自動偵測交會站並處理方向翻轉。

### 日曆類型

`setting.json` 的 `calendar_type`：
- `WEEKDAY_BITMAP`：以 1-7 代表星期幾篩選班次（台鐵）
- `SERVICE_GROUP`：以平日/假日群組篩選（高鐵）

### 新增路線

1. 在 `data/<國家>/<路線>/json/` 建立 `topology.json`、`setting.json`
2. 撰寫 `script/timetable.py` 產生 `timetable_YYYYMMDD.json`
3. 在 `data/global.json` 新增路線項目（`is_active: true`）
4. 前端 `index.html` 視需要新增對應按鈕，觸發 `init('data/<國家>/<路線>/')`

### 注意事項

- `KANJI_MAP` 統一處理日文漢字與繁體字轉換（用於搜尋正規化）
- `junctionCache` 快取分岔站的 Y 座標計算結果
- 列車 hit detection 透過 `_hitPoints` 麵包屑陣列（`null` 代表線段斷開）
- 所有時間單位為「分鐘」（0 = 凌晨 0:00，`TOTAL_MINUTES = 1560` 表示支援到隔日 26:00）
