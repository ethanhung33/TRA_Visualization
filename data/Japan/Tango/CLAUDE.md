# CLAUDE.md — 京都丹後鉄道 (Tango / KTR)

## 基本資訊
- **calendar_type**: `WEEKEND_SELECT`（平日 / 土休日兩檔）
- **view_type**: `LINEAR`
- **時刻表策略**: `WEEKEND_FILE`
- 第三部門鐵道（WILLER TRAINS 營運），京都/兵庫北部。

## 路線結構（3 segment，宮津為 hub 交會）
| segment | 路線 | 區間 | id |
|---------|------|------|----|
| `miyamai_line` | 宮舞線 | 西舞鶴→宮津（7 站） | MM01–MM06, MZ |
| `miyatoyo_line` | 宮豊線 | 宮津→豊岡（13 站） | MZ, MT01–MT12 |
| `miyafuku_line` | 宮福線 | 宮津→福知山（14 站） | MZ, MF01–MF13 |

**交會站**：宮津（`MZ`，三線共用同一 id、各段各自 km）。宮豊線 km 由宮津線(西舞鶴起)減 24.7 換算為宮津起點。
福知山 / 西舞鶴 / 豊岡 為與 JR 的轉乘端點，亦屬 KTR 站。

## JR西日本 特急直通（はしだて 等）— 智頭急行式處理
JR西の特急（はしだて・たんごリレー等）由京都經山陰本線、福知山直通至天橋立/豊岡。
- **抓取**：這些直通車在 navitime 的 **KTR lineId 即可掃到**（已探勘確認，天橋立宮豊線頁含 11 班特急），故掃 KTR 三線就涵蓋，不需另掃 JR 線。
- **轉換**：其 JR 段（京都-綾部，山陰本線）的站不在 KTR 拓樸 → `convert_timetable.py` 自動略過，只留 KTR 段（福知山→大江→宮津→天橋立/豊岡），並在宮津交會站切成 宮福線＋宮豊線 兩段。此即「智頭急行」式作法（外運營商路段不入拓樸、前端/轉換自然略過）。
- navitime 對這些特急的 `data-name` 僅標「特急」，故目前 はしだて／丹後の海／たんごリレー 都歸為「特急」（紅色）。若要分色需另解析 stops 頁標題取列車名。

## 資料來源與爬取
- **里程**：維基百科「京都丹後鉄道宮津線」（西舞鶴-豊岡）+「京都丹後鉄道宮福線」（宮津-福知山）。`build_topology.py` 內嵌。
- **時刻表**：NAVITIME。companyId 京都丹後鉄道；lineId：宮舞線 `00001238`、宮豊線 `00000847`、宮福線 `00000848`。
- 腳本沿用 Keihan 範本：`convert_timetable.py` 完全未改，`timetable.py` 僅換 `SCAN_LINES`。

**執行**：
```
py data/Japan/Tango/script/build_topology.py
py data/Japan/Tango/script/timetable.py --workers 8
py data/Japan/Tango/script/convert_timetable.py
py tools/validate_system.py data/Japan/Tango --timetable-sample 0
```

## 注意事項
- 車種：普通 / 快速 / 特急（特急含 JR 直通 はしだて）。
- navitime 站名 `東雲(京都府)`、`牧(京都府)`、`大江(京都府)`、`豊岡(兵庫県)` 有括號後綴，由 `norm_name` 剝除。
- 其餘 navitime 實戰陷阱（node 不可空、dwell 着発、跨 lineId 去重、依 data-date 篩日）皆內建於沿用的爬蟲；詳見 SKILL.md。
