# CLAUDE.md — 叡山電鉄 (Eizan)

## 基本資訊
- **calendar_type**: `WEEKEND_SELECT`（平日 / 土休日兩檔）
- **view_type**: `LINEAR`
- **時刻表策略**: `WEEKEND_FILE`（`timetable_weekday.json` / `timetable_holiday.json`）
- 京都的小型 2 線系統。叡山ケーブル/ロープウェイ屬京福電鉄，不在此系統。

## 路線結構（2 segment）
| segment | 路線 | 區間 | id |
|---------|------|------|----|
| `eizan_main` | 叡山本線 | 出町柳→八瀬比叡山口（8 站） | E01–E08 |
| `kurama_line` | 鞍馬線 | 宝ヶ池→鞍馬（10 站） | E06,E09–E17 |

**交會站**：宝ヶ池（E06，兩段共用同一 id、各自 km：本線 3.8 / 鞍馬 0.0）。出町柳→鞍馬的直通車在宝ヶ池切成 eizan_main + kurama_line 兩段。路段不重疊。

## 資料來源與爬取
- **里程**：日本維基百科「叡山電鉄叡山本線」「叡山電鉄鞍馬線」駅一覧（営業キロ）。`build_topology.py` 內嵌。
- **時刻表**：NAVITIME（同 Keihan 那套，見 `.claude/skills/new-system` SKILL.md）。companyId `00000023`；lineId：本線 `00000259`、鞍馬線 `00000258`。
- 腳本 `script/{build_topology,timetable,convert_timetable}.py` 沿用 Keihan 範本：`convert_timetable.py` 完全未改（通用多 segment 切分）；`timetable.py` 僅改 `SCAN_LINES`。

**執行**：
```
py data/Japan/Eizan/script/build_topology.py
py data/Japan/Eizan/script/timetable.py --workers 8     # 小系統，數十秒
py data/Japan/Eizan/script/convert_timetable.py
py tools/validate_system.py data/Japan/Eizan --timetable-sample 0
py tools/screenshot.py --init data/Japan/Eizan/ --out shots/eizan.png
```

## 注意事項
- 全車種皆為「普通」（navitime 未細分快速/観光列車きらら）。
- 站名 `茶山・京都芸術大学`、`宝ヶ池`（小ヶ）與 navitime 一致，已用全站覆蓋檢查確認。
- navitime 實戰陷阱（node 不可空、各式括號正規化、dwell 着発、跨 lineId 去重、依 data-date 篩日）皆已內建於沿用的爬蟲；詳見 SKILL.md。
