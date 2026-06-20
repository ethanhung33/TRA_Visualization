# CLAUDE.md — 阪神電気鉄道 (Hanshin)

## 基本資訊
- **system_id**: `Hanshin`
- **calendar_type**: `WEEKEND_SELECT`（平日 / 土休）
- **data_fetch_strategy**: `WEEKEND_FILE`
- **timezone_offset**: 9（JST）

## 路線結構（3 segment）

| segment | 路線 | 区間 | 備考 |
|---------|------|------|------|
| `main_line` | 本線 | 大阪梅田→元町（33 駅） | 大物=なんば線・武庫川=武庫川線と交會 |
| `namba_line` | なんば線 | 大阪難波→大物（10 駅） | 大物=本線と共用 |
| `mukogawa_line` | 武庫川線 | 武庫川→武庫川団地前（4 駅） | 武庫川=本線と共用 |

**交會站（同一 id でまたぐ段）**:
- 大物（`HS08`）: 本線 ↔ なんば線
- 武庫川（`HS12`）: 本線 ↔ 武庫川線

`namba` view は `["namba_line", {"id":"main_line","start":"大物","end":"神戸三宮"}]` で
大阪難波→神戸三宮の直通ルートを 1 本の LINEAR として表示。

## 直通運転（is_other）

`convert_timetable.py` が prefix/suffix の拓樸外区間を運営者ごとに `is_other` segment へ分離
（境界站は阪神 station id で保存）。運営者は駅名セットで判定（`_KINTETSU` / `_KOBE_KOSOKU` /
それ以外＝山陽電鉄）。

| 直通先 | seg id | system_path | 例 |
|--------|--------|-------------|----|
| 近鉄（なんば線→大阪難波） | `kintetsu` | `data/Japan/Kintetsu/`（建置済→リンク可） | 近鉄奈良・大和西大寺 方面 |
| 神戸高速鉄道（本線→元町以西） | `kobe_kosoku` | なし（未建置→「尚未建置」通知） | 高速神戸・新開地 |
| 山陽電鉄（神戸高速の更に西） | `sanyo` | なし（未建置） | 山陽姫路・須磨浦公園 方面（直通特急） |

直通特急は 元町以西で 神戸高速→山陽 と運営者が変わるため、1 本の suffix が
`kobe_kosoku` + `sanyo` の 2 segment に分割される。

## 資料來源と爬取

**里程**: 日本語Wikipedia 各線「駅一覧」の営業キロ。`build_topology.py` に内蔵。

**時刻表**: NAVITIME ダイヤグラム。companyId `00000058`。
| 路線 | lineId |
|------|--------|
| 本線 | `00000663` |
| なんば線 | `00000661` |
| 武庫川線 | `00000662` |

navitime 注意事項：timetable listing は「サーバ当日から約 4 日」プール（URL date 無視）。
各班 `data-date` の曜日で平日/土休に分桶し、各カテゴリの「最多班次の代表日」を採用
（水〜日に実行すると平日・週末を両方含む）。種別は `data-name`。方向は stops 序列で判断。
站名は NFKC 後に `(阪神線)`・`〔近鉄・阪神線〕`・`(兵庫県)`・`(大阪府)` 等の括號を除去。

**執行**:
```
py data/Japan/Hanshin/script/build_topology.py
py data/Japan/Hanshin/script/timetable.py --workers 6
py data/Japan/Hanshin/script/convert_timetable.py
py tools/validate_system.py data/Japan/Hanshin --timetable-sample 0
```

## 車種と色
| 種別 | 色（dark/light） |
|------|-----------------|
| 直通特急 | #FF6E9C / #AD1457（桃紅） |
| 特急 | #FF5252 / #C62828（紅） |
| Ｓ特急 | #C77DFF / #6A1B9A（紫） |
| 区間特急 | #FF8A65 / #E64A19（珊瑚） |
| 快速急行 | #FFCA5F / #EF6C00（金） |
| 急行 | #FF9472 / #D84315（橙） |
| 区間急行 | #8FC9FF / #1565C0（淺藍） |
| 準急 | #86D98A / #2E7D32（綠） |
| 区間準急 | #5BD1C4 / #00796B（青綠） |
| 普通 | #B0B0B0 / #969696（灰） |
