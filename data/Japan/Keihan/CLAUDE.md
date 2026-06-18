# CLAUDE.md — 京阪電氣鐵道 (Keihan)

## 基本資訊

- **calendar_type**: `WEEKEND_SELECT`（平日 / 土休日兩檔）
- **view_type**: `LINEAR`
- **時刻表策略**: `WEEKEND_FILE`（`timetable_weekday.json` / `timetable_holiday.json`）
- **範圍**: 京阪全 8 線。

## 路線結構（8 segment）

| segment | 路線 | 區間 | id 範圍 |
|---------|------|------|---------|
| `keihan_main` | 京阪本線 | 淀屋橋→三条 | KH01–KH40 |
| `oto_line` | 鴨東線 | 三条→出町柳 | KH40,KH41,KH42 |
| `nakanoshima_line` | 中之島線 | 中之島→天満橋 | KH54,KH53,KH52,KH51,KH03 |
| `katano_line` | 交野線 | 枚方市→私市 | KH21,KH61–KH67 |
| `uji_line` | 宇治線 | 中書島→宇治 | KH28,KH71–KH77 |
| `keishin_line` | 京津線 | 御陵→びわ湖浜大津 | KS01–KS06,OT12 |
| `ishiyama_line` | 石山坂本線 | 石山寺→坂本比叡山口 | OT01–OT21 |
| `cable_line` | 鋼索線 | ケーブル八幡宮口→山上 | CB01,CB02 |

**交會站（同一 id 跨 segment 共用，各段各自的 km）**：
三条(KH40 本線↔鴨東)、天満橋(KH03 本線↔中之島)、枚方市(KH21 本線↔交野)、
中書島(KH28 本線↔宇治)、びわ湖浜大津(OT12 京津↔石山坂本)。

**重要**：(1) 不重疊原則——每段實體路段只屬一個 segment，交會站只共用節點。
(2) 鋼索線下站為「ケーブル八幡宮口」（非石清水八幡宮）→ 與本線無共用站、獨立。
(3) 大津線群（京津＋石山坂本）為與京阪線群實體分離的獨立網，於びわ湖浜大津相接。

時刻表轉換採 TRA 式多 segment 切分（見下）。

## 資料來源與爬取

**里程**: 日本維基百科「京阪本線」「京阪鴨東線」駅一覧（営業キロ）。
腳本 `script/build_topology.py` 內嵌已校正的站名+里程清單，產生 `topology.json` 與 `station_name_to_id.json`。

**時刻表**: NAVITIME ダイヤグラム（`navitime.co.jp/diagram/`）。
- companyId `00000036`；掃描 8 條 lineId（`SCAN_LINES`）：本線 `00000285`、鴨東直通 `00000281`、中之島 `00001094`、交野 `00000283`、宇治 `00000280`、京津 `00000282`、石山坂本 `00000284`、鋼索 `00001088`。
- **直通車覆蓋**：中之島発/交野発/宇治発的直通車只掛在各自連絡線的 lineId，故必須掃這些線的端點站才抓得到（京阪首跑時漏掉中之島発約 105 班即此因）。每班 stops 必須用「該連結自身的 lineId」抓，再以內容簽章跨 lineId 去重。
- **navitime 特性**：非 JS 的 HTML 不依 URL date/updown 過濾，而是回傳一週池子，每班車自帶 `data-date`；故爬蟲以 `data-date` 篩營運日、以 stops 序列自身判斷方向。
- stops 詳情頁無列車番号/種別 → `no` 用 navitime 的 stopCode（故 setting 設 `show_train_id:false` 隱藏）、`type`（種別）從 timetable listing 的 `data-name` 帶下來。

**執行**:
```
py data/Japan/Keihan/script/build_topology.py      # 建拓樸（先跑）
py data/Japan/Keihan/script/timetable.py           # 爬 raw（平日+土休，限速約 4 分鐘）
py data/Japan/Keihan/script/convert_timetable.py   # 轉成本專案格式
py tools/validate_system.py data/Japan/Keihan       # 驗證
py tools/screenshot.py --init data/Japan/Keihan/ --out shots/keihan.png  # 視覺確認
```

**爬蟲兩階段** (`timetable.py`，比照 TRA)：
1. 掃描全幹線車站 timetable 頁，解析 `<li.time-frame>` 的 `data-*`，依 `data-date` 篩當日車次，蒐集去重 stopCode 與種別。
2. 對每個 stopCode 抓 `stops/{lineId}/{stopCode}/` 頁，解析 `<li.stops-list>` 各站 着/発 時刻。
原始結果存 `json/raw_weekday.json` / `raw_holiday.json`，再交給 `convert_timetable.py`。

## 特殊邏輯

- **多 segment 切分** (`convert_timetable.py::compile_train`，移植自 TRA `compile_train_data`)：依拓樸判斷每站所屬 segment，相鄰兩站取共同段；換段時於交會站切開（交會站同時為前段末站、後段首站）。
- **站名正規化** (`norm_name`)：NFKC + 去除「（…）」後綴與「駅」字（三条（京都府）→ 三条）。
- **跨夜**：stops 序列時間遞減則 +1440。
- **dwell 時刻**：停留站（待避/緩急接續）用 `dd.from-to-time`（着<br>発兩時刻），一般站用 `dd.time`；parser 兩者都收（否則該停靠點會整個漏掉）。
- **通過站**：navitime 只列停靠站、不標通過，故 `v` 不產生 2（PASS）；急行/特急直接畫停靠點間連線即為正確 Marey 行為。
- **支線區間車**：純支線往返車（如私市↔枚方市）切分後幹線片段不足 2 站會被捨棄。

## 注意事項

- navitime 為商業服務：爬蟲嚴格限速（每請求 sleep ≥1.1s）、低併發（3）、僅個人用途、尊重 robots.txt。
- 營運日代表日由 `timetable.py` 的 `--weekday` / `--holiday` 參數指定（預設週三 / 週六）；navitime 池子只涵蓋近一週，重跑需更新為近期日期。
