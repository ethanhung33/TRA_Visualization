# CLAUDE.md — 阪急電気鉄道 (Hankyu)

## 基本資訊
- **calendar_type**: `WEEKEND_SELECT`（平日 / 土休日兩檔）
- **view_type**: `LINEAR`（全線）
- **時刻表策略**: `WEEKEND_FILE`
- **companyId（navitime）**: `00000056`

## 路線結構（11 segment）

| segment | 路線 | 区間 | 備考 |
|---------|------|------|------|
| `umeda_juso` | 三線共用幹線 | 大阪梅田→十三（3 駅） | 神戸・宝塚・京都 三線共用 |
| `kobe_main` | 神戸本線 | 十三→神戸三宮（14 駅） | umeda_juso と接続 |
| `takarazuka_main` | 宝塚本線 | 十三→宝塚（17 駅） | umeda_juso と接続 |
| `kyoto_main` | 京都本線 | 十三→京都河原町（27 駅） | umeda_juso と接続；淡路で千里線と接続 |
| `imazu_north` | 今津線（北） | 宝塚→西宮北口（8 駅） | 宝塚=宝塚本線と共用 |
| `imazu_south` | 今津線（南） | 西宮北口→今津（3 駅） | 西宮北口=神戸本線と共用 |
| `itami_line` | 伊丹線 | 塚口→伊丹（4 駅） | 塚口=神戸本線と共用 |
| `koyo_line` | 甲陽線 | 夙川→甲陽園（3 駅） | 夙川=神戸本線と共用 |
| `senri_line` | 千里線 | 天神橋筋六丁目→北千里（11 駅） | 淡路=京都本線と共用 |
| `minoh_line` | 箕面線 | 石橋阪大前→箕面（4 駅） | 石橋阪大前=宝塚本線と共用 |
| `arashiyama_line` | 嵐山線 | 桂→嵐山（4 駅） | 桂=京都本線と共用 |

**主要交会站（同一 ID でまたぐ段）**:
- 大阪梅田(HK01)〜中津(HK02)〜十三(HK03): umeda_juso（三線共用独立 segment）
- 十三(HK03): umeda_juso と kobe/takarazuka/kyoto_main の境界
- 塚口(KO03): 神戸本線 ↔ 伊丹線
- 西宮北口(KO05): 神戸本線 ↔ 今津線（南北）
- 夙川(KO06): 神戸本線 ↔ 甲陽線
- 宝塚(TZ16): 宝塚本線 ↔ 今津線（北）
- 石橋阪大前(TZ08): 宝塚本線 ↔ 箕面線
- 淡路(KY02): 京都本線 ↔ 千里線
- 桂(KY20): 京都本線 ↔ 嵐山線

## 資料來源と爬取

**里程**: 日本語Wikipedia 各線「駅一覧」の営業キロ。`build_topology.py` に内蔵。

**時刻表**: NAVITIME ダイヤグラム。各線 lineId：
| 路線 | lineId |
|------|--------|
| 神戸本線 | `00000654` |
| 宝塚本線 | `00000656` |
| 京都本線 | `00000651` |
| 今津線 | `00000653` |
| 伊丹線 | `00000650` |
| 甲陽線 | `00000652` |
| 千里線 | `00000655` |
| 箕面線 | `00000657` |
| 嵐山線 | `00000658` |

**執行**:
```
py data/Japan/Hankyu/script/build_topology.py
py data/Japan/Hankyu/script/timetable.py --workers 8
py data/Japan/Hankyu/script/convert_timetable.py
py tools/validate_system.py data/Japan/Hankyu --timetable-sample 0
```

## navitime 特記事項

- **神戸・宝塚・京都 共用区間**（梅田〜十三）：同一 node が三線の stationList に出現するが、
  `seen_nodes` 去重により神戸本線側で一度だけ掃描。十三以降の専用駅で各線の全列車を捕捉できるため問題なし。
  拓樸上は `umeda_juso` という独立 segment として切り出し、三線 view_preset が `"lines":["umeda_juso","..."]` で共有。
- **千里線/京都線 大阪メトロ直通**：天神橋筋六丁目を越えて堺筋線（天下茶屋方面）に直通する列車あり。
  convert_timetable.py で `_METRO_SAKAISUJI` セットを使って prefix/suffix を `is_other` segment（osaka_metro_sakaisuji）に分離。
- **神戸線 神戸高速鉄道直通（直通特急）**：神戸三宮を越えて花隈・高速神戸・新開地へ直通する列車あり。
  `_KOBE_KOSOKU` セットで後綴を `is_other` segment（kobe_kosoku）に分離。
- **今津線（北南分断）**：西宮北口で南北に分かれ、1984 年以降直通なし。
  今津線専用駅（宝塚南口・阪神国道 等）を掃描することで南北双方の列車を捕捉。

## 車種と色

| 種別 | 色（dark/light） |
|------|-----------------|
| 快速特急 | #FF6E9C / #AD1457（桃紅） |
| 特急 / 通勤特急 | #FF7B7B / #C62828（紅） |
| 直通特急 | #FF9BAA / #B71C1C（淡紅） |
| 快速急行 / 通勤快急 | #FFCA5F / #EF6C00（金） |
| 急行 / 通勤急行 | #FF9472 / #D84315（橙） |
| 準急 | #86D98A / #2E7D32（綠） |
| 普通 | #B0B0B0 / #969696（灰） |
