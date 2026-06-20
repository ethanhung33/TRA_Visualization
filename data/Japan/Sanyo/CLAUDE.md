# CLAUDE.md — 山陽電気鉄道 (Sanyo)

## 基本資訊
- **system_id**: `Sanyo`
- **calendar_type**: `WEEKEND_SELECT` / **data_fetch_strategy**: `WEEKEND_FILE`
- **timezone_offset**: 9（JST）

## 路線結構（2 segment）

| segment | 路線 | 区間 | 備考 |
|---------|------|------|------|
| `main_line` | 本線 | 西代→山陽姫路（43 駅） | 飾磨=網干線と交會 |
| `aboshi_line` | 網干線 | 飾磨→山陽網干（7 駅） | 飾磨=本線と共用 |

**交會站**：飾磨（`SY40`）本線 ↔ 網干線。

## 直通運転（is_other）

直通特急・特急・Ｓ特急は西代以東へ直通 → `convert_timetable.py` が prefix/suffix の拓樸外区間を
運営者ごとに `is_other` segment へ分離（境界站は山陽 station id で保存）。1 本の直通 suffix が
神戸高速→阪神 と運営者を跨ぐため 2 segment に分割される。

| 直通先 | seg id | system_path | 駅 |
|--------|--------|-------------|----|
| 神戸高速鉄道 | `kobe_kosoku` | なし（未建置→「尚未建置」通知） | 大開・高速長田・新開地・高速神戸・花隈・西元町 |
| 阪神電気鉄道 | `hanshin` | `data/Japan/Hanshin/`（建置済→リンク可） | 元町・神戸三宮・…・大阪梅田 |

**Hanshin ↔ Sanyo**：阪神側も山陽直通を is_other で持つ（阪神の `sanyo` segment）。阪神側の
system_path を `data/Japan/Sanyo/` に更新すれば相互リンクが完成する（未対応なら片方向）。

判定は駅名セット（`_KOBE_KOSOKU` ＝神戸高速、それ以外＝阪神）。神戸高速の東側のみが
拓樸外に出るため、デフォルト阪神で安全。

## 資料來源と爬取

**里程**: 日本語Wikipedia 各線「駅一覧」の営業キロ。`build_topology.py` に内蔵。

**時刻表**: NAVITIME ダイヤグラム。companyId `00000066`。
| 路線 | lineId |
|------|--------|
| 本線 | `00000675` |
| 網干線 | `00000676` |

navitime 注意事項：timetable listing は「サーバ当日から約 4 日」プール（URL date 無視）。
各 stopCode の data-date を**集合**で蓄積し、代表日（平日/土休）が集合に含まれるかで分桶。
種別は `data-name`（普通 / 特急 / 直通特急 / Ｓ特急）。方向は stops 序列で判断。
站名は NFKC 後に `(兵庫県)` 等の括號を除去。

**執行**:
```
py data/Japan/Sanyo/script/build_topology.py
py data/Japan/Sanyo/script/timetable.py --workers 6
py data/Japan/Sanyo/script/convert_timetable.py
py tools/validate_system.py data/Japan/Sanyo --timetable-sample 0
```

## 車種と色
| 種別 | 色（dark/light） |
|------|-----------------|
| 直通特急 | #FF8C42 / #E65100（橙） |
| 特急 | #FF5252 / #C62828（紅） |
| Ｓ特急 | #C77DFF / #6A1B9A（紫） |
| 普通 | #B0B0B0 / #666666（灰；淺色模式色比照 JR西日本） |
