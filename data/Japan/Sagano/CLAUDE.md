# CLAUDE.md — 嵯峨野観光鉄道（嵐山小火車 / トロッコ列車）

## 基本資訊
- **system_id**: `Sagano`
- **路線**: 嵯峨野観光線（単一線・4 駅）トロッコ嵯峨→トロッコ嵐山→トロッコ保津峡→トロッコ亀岡（7.3 km）
- **車種**: トロッコ列車（1 種のみ。navitime 上は「普通」表示 → convert で `トロッコ` に統一）
- **view_type**: `LINEAR`
- **timezone_offset**: 9（JST）

## 営運日（重要・新方式 SINGLE_FILE）

全営業日で**同一ダイヤ**（平日/土休の別なし）。ただし定期運休あり：
- **毎週水曜運休**（行楽期・祝日は運行するが、簡易化のため全水曜を運休扱い）
- **冬季運休**（12/30〜2 月末）

→ 専用の表示方式を採用（既存の WEEKEND_FILE/DAILY_FILE では合わない）：
- `data_fetch_strategy: "SINGLE_FILE"` — 全年共用の単一ファイル `timetable/timetable_all.json` を読む
  （毎日同一ダイヤなので逐日ファイルは作らない）
- `calendar_type: "WEEKDAY_BITMAP"` — 月曆 UI を流用
- `available_dates.json` に**営業日のみ**を列挙 → flatpickr の `enable` で**公休日は月曆上で反灰・選択不可**
- `calendar_note`（setting.json）— 月曆下に「毎週水曜運休・冬季全休」の注記を表示（汎用フィールド）

`available_dates.json` は `script/available_date.py` が今日から約 13 ヶ月分を生成（水曜・冬季を除外）。

## 資料來源と爬取

**里程**: 日本語Wikipedia「嵯峨野観光線」駅一覧の営業キロ。`build_topology.py` に内蔵。

**時刻表**: NAVITIME ダイヤグラム。`lineId = 00000649`。
駅 node: トロッコ嵯峨=`00000090`、トロッコ嵐山=`00000092`、トロッコ保津峡=`00000091`、トロッコ亀岡=`00000089`。

navitime 注意事項：timetable listing は「サーバ当日から約 4 日」のプールを返す（阪急と同じ、URL の date 無視）。
本線は全日同一ダイヤのため曜日分けは不要 → プール内で**最も班次の多い 1 日を代表営業日**として採用し、
全 4 駅・上下両方向を掃描、stops 序列で方向判断、内容簽章で去重して単一 `raw_all.json` を出力。

**執行**:
```
py data/Japan/Sagano/script/build_topology.py
py data/Japan/Sagano/script/timetable.py --workers 4
py data/Japan/Sagano/script/convert_timetable.py
py data/Japan/Sagano/script/available_date.py
py tools/validate_system.py data/Japan/Sagano --timetable-sample 0
```

## 車種と色
| 種別 | 色（dark/light） |
|------|-----------------|
| トロッコ | #FF8A65 / #BF360C（復古橘紅） |
