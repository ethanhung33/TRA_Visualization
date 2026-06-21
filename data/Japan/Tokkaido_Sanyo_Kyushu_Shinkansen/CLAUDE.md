# CLAUDE.md — 東海道・山陽・九州・西九州新幹線

## 基本資訊
- **calendar_type**: `WEEKDAY_BITMAP`（月曆 + `available_dates.json`）
- **data_fetch_strategy**: `DAILY_FILE`（毎日ダイヤが異なる → 日付ごとに 1 ファイル）
- **show_train_id**: true / **show_train_type**: false
  → `no` に旅客向けの愛称＋号数（例「のぞみ1号」）を格納し、ラベルはそれだけ表示
  （`type` は「のぞみ」のまま＝色分け・車種フィルタ用）。号数は stops 頁の `<h2>` から取得。
- **timezone_offset**: 9

## 路線結構（4 segment、東海道+山陽+九州 は 1 本に連結）

| segment id | 区間 | 備考 |
|-----------|------|------|
| `tokaido_line` | 東京→新大阪（17 駅） | 新大阪=TOK17 |
| `sanyo_line` | 新大阪→博多（19 駅） | 新大阪=TOK17 共用、博多=SAN18 |
| `kyushu_line` | 博多→鹿児島中央（12 駅） | 博多=SAN18 共用 |
| `nishi_kyushu_line` | 武雄温泉→長崎（5 駅） | 独立（リレーかもめは在来線、未収録） |

**交會站（同一 id でまたぐ段）**：新大阪（`TOK17`）東海道↔山陽、博多（`SAN18`）山陽↔九州。
`main_line` view が `["tokaido_line","sanyo_line","kyushu_line"]` で東京→鹿児島中央を 1 本表示。
のぞみ（東京↔博多）・みずほ/さくら（新大阪↔鹿児島中央）等の直通車は交會站で segment 分割。

## 資料來源と爬取（navitime に移行）

**旧** JR Odekake (`timtable.py` + `station_route_shinkansen.json`) は廃止し、他システムと同じ
**NAVITIME ダイヤグラム**に統一。lineId：
| 線 | lineId |
|----|--------|
| 東海道新幹線 | `00000110` |
| 山陽新幹線 | `00000069` |
| 九州新幹線 | `00001017` |
| 西九州新幹線 | `00001278` |

里程は既存 `topology.json` を再利用（站名は navitime と完全一致を確認済み）。

navitime 注意事項：
- **任意日付の取得**：listing の `&time=YYYY-MM-DD` パラメータで任意日付のダイヤを取得できる
  （`year/month/day`・`searchDate`・cookie は無視されるが `time=` は効く。UI の日付ピッカー
  Vue コンポーネントが使う本物のパラメータ）。`timetable.py --start YYYY-MM-DD --days N` で
  今日から N 日分を逐日掃描。time= 未指定だと「今日・明日・次の土曜」の自然プールのみ。
- 各 stopCode の data-date を集合で蓄積し、**日付ごとに 1 ファイル** raw_YYYYMMDD.json を出力
  （各 code の stops は 1 回だけ取得し、走る全日付へ振り分け）。
- 直通のぞみ等は東海道・山陽の両 lineId に出る → 内容簽章（種別+始発+始発時刻+終着+停車数）で去重。
- 種別は `data-name`（のぞみ/ひかり/こだま/みずほ/さくら/つばめ/かもめ）。

**執行**:
```
py data/Japan/Tokkaido_Sanyo_Kyushu_Shinkansen/script/timetable.py --workers 6
py data/Japan/Tokkaido_Sanyo_Kyushu_Shinkansen/script/convert_timetable.py
py tools/validate_system.py data/Japan/Tokkaido_Sanyo_Kyushu_Shinkansen --timetable-sample 0
```
`convert_timetable.py` が `available_dates.json` も raw_*.json の日付から再生成。
（topology は `build_topology.py` で再生成可能だが、station_route 廃止後は手動メンテでも可）

## 車種と色
のぞみ（黄）・ひかり（紅）・こだま（青）・みずほ（橙）・さくら（桃）・つばめ（青綠）・かもめ（綠／西九州）。
