# CLAUDE.md — 京福電気鉄道（嵐電 / Randen）

## 基本資訊
- **system_id**: `Keifuku`
- **路線**: 嵐山本線（四条大宮→嵐山、13 駅）、北野線（北野白梅町→帷子ノ辻、10 駅）
- **車種**: 普通（路面電車、1 種のみ。色は嵐電の京紫イメージで紫）
- **view_type**: `LINEAR`（両線）
- **calendar_type**: `WEEKEND_SELECT`（平日/土休で班数が僅かに異なる）
- **data_fetch_strategy**: `WEEKEND_FILE`
- **timezone_offset**: 9（JST）

## 路線結構（2 segment）

| segment | 路線 | 区間 | 備考 |
|---------|------|------|------|
| `arashiyama_main` | 嵐山本線 | 四条大宮→嵐山（13 駅） | 帷子ノ辻=北野線と交會 |
| `kitano_line` | 北野線 | 北野白梅町→帷子ノ辻（10 駅） | 帷子ノ辻=嵐山本線と共用 |

**交會站**: 帷子ノ辻（`RD08`）— 両 segment で同一 station id を共用（km は本線 5.2 / 北野線 3.8）。
北野線↔嵐山本線の直通車（少数）は compile 時に帷子ノ辻で 2 segment に切り分けられる。

## 資料來源と爬取

**里程**: 日本語Wikipedia「京福電気鉄道嵐山本線 / 北野線」駅一覧の営業キロ。`build_topology.py` に内蔵。

**時刻表**: NAVITIME ダイヤグラム。companyId `00000040`。
| 路線 | lineId |
|------|--------|
| 嵐山本線 | `00000300` |
| 北野線 | `00000299` |

navitime 注意事項：timetable listing は「サーバ当日から約 4 日」プール（URL date 無視）。
各班 `data-date` の曜日で平日/土休に分桶し、各カテゴリの「最多班次の代表日」を採用
（水〜日に実行すると 4 日窗口に平日・週末が両方含まれる）。種別は `data-name`（普通のみ）。
方向は stops 序列で判断。站名は NFKC 後に `〔嵐電〕`・`(京都府)` 等の括號を除去して拓樸と整合。

**執行**:
```
py data/Japan/Keifuku/script/build_topology.py
py data/Japan/Keifuku/script/timetable.py --workers 6
py data/Japan/Keifuku/script/convert_timetable.py
py tools/validate_system.py data/Japan/Keifuku --timetable-sample 0
```

## 車種と色
| 種別 | 色（dark/light） |
|------|-----------------|
| 普通 | #B98EFF / #6A1B9A（京紫） |
