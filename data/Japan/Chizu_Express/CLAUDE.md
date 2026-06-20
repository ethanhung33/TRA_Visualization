# CLAUDE.md — 智頭急行 (Chizu Express)

## 基本資訊
- **system_id**: `Chizu_Express`（JR_West が is_other で `data/Japan/Chizu_Express/` を参照するため、この id 固定）
- **路線**: 智頭線（上郡→智頭、14 駅、56.1 km）単一線
- **車種**: 普通 / 特急（navitime は「特急」一括。convert で直通 JR 端点から愛称を推定
  → 岡山行=スーパーいなば、大阪・京都・倉吉行=スーパーはくと）
- **view_type**: `LINEAR`
- **calendar_type**: `WEEKEND_SELECT` / **data_fetch_strategy**: `WEEKEND_FILE`（全営業日ほぼ同ダイヤ）
- **timezone_offset**: 9（JST）

## 直通運転（is_other）

特急スーパーはくと/いなばは智頭急行を貫通し、両端で JR 西日本へ直通：
- **上郡以西**：JR 山陽本線（岡山・姫路・三ノ宮・大阪・京都 方面）
- **智頭以北**：JR 因美線・山陰本線（鳥取・倉吉 方面、郡家 等）

`convert_timetable.py` がこれらの拓樸外区間を `is_other` segment（id `jr_west`、
`system_name:"JR西日本"`、`system_path:"data/Japan/JR_West/"`）に分離。境界站
上郡(`CZ01`)・智頭(`CZ14`)は智頭急行 id で保存。**JR_West ↔ Chizu_Express は相互に
is_other 参照**しており（JR_West 側は `chizu_express_line`→`data/Japan/Chizu_Express/`）、
両系統が存在するため底部面板からの相互ジャンプが成立する。

## 資料來源と爬取

**里程**: 日本語Wikipedia「智頭急行智頭線」駅一覧の営業キロ。`build_topology.py` に内蔵。

**時刻表**: NAVITIME ダイヤグラム。companyId `00000105`、lineId `00000753`。

navitime 注意事項：
- timetable listing は「サーバ当日から約 4 日」プール（URL date 無視）。
- **本線は毎日ほぼ同ダイヤ → 同一 stopCode が複数日に再利用される**。よって各 code の
  data-date を**単一値ではなく集合**で蓄積し、代表日（平日/土休）がその集合に含まれるかで
  分桶する（単純な first-date 去重だと片方の桶が激減する。実際 5 班まで落ちた）。
- 種別は `data-name`（普通 / 特急）。方向は stops 序列で判断。

**執行**:
```
py data/Japan/Chizu_Express/script/build_topology.py
py data/Japan/Chizu_Express/script/timetable.py --workers 6
py data/Japan/Chizu_Express/script/convert_timetable.py
py tools/validate_system.py data/Japan/Chizu_Express --timetable-sample 0
```

## 車種と色
| 種別 | 色（dark/light） |
|------|-----------------|
| 特急スーパーはくと | #9CCC65 / #558B2F（綠；HOT7000 系イメージ） |
| 特急スーパーいなば | #FF7B7B / #C62828（紅） |
| 特急（愛称判定不能の保険） | #FFA270 / #E64A19（橙） |
| 普通 | #B0B0B0 / #969696（灰） |
