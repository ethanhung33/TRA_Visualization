#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_topology.py — 東日本旅客鉄道 (JR East) 拓樸建置

資料源：日文維基百科各「法定路線」條目的駅一覧表格（站名 + 累計営業キロ）。

為什麼用法定路線而不是官方時刻表的營運路線名？
  官方時刻表站（jreast-timetable.jp）的路線是**營運系統名**（宇都宮線・京浜東北線・
  埼京線・湘南新宿ライン…），彼此大量重疊（宇都宮線 ⊂ 東北本線、京浜東北線 ⊂
  東北本線+東海道本線）。topology 的 segment 必須**互不重疊**，否則 convert 階段
  以「站名交集」派段時，同一班車會被複製到多個 segment。
  因此：topology = 法定路線（互不重疊地分割路網），營運系統名只用在 setting.json
  的 view_presets（可用 {id, start, end} 組合出宇都宮線・山手線環狀等視圖）。

共用站 id：以「站名」為鍵全域共用（GLOBAL_STATION_ID_MAP），使跨線直通車在前端
能正確接續、分岔站能被偵測（比照 JR_West / TRA 作法）。

輸出：json/topology.json
"""
import sys
import re
import json
import time
import unicodedata
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))
from wikitable import table_to_grid, flat_columns

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

JSON_DIR = Path(__file__).parent.parent / "json"
JSON_DIR.mkdir(parents=True, exist_ok=True)

WIKI = "https://ja.wikipedia.org/wiki/"
HEADERS = {"User-Agent": "TRA-Visualization/1.0 (personal railway diagram project)"}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# ==========================================================================
# 法定路線清單： (segment_id, 日文線名, 維基條目, 站 id 前綴)
# 順序 = id 指派優先序：先幹線，共用站由幹線取得 id。
# ==========================================================================
LINES = [
    # --- 關東幹線 ---
    # 東北本線 東京–黒磯 的車站表在維基是掛在「宇都宮線」條目（本線條目只列黒磯以北），
    # 奥羽本線 福島–新庄 同理掛在「山形線」。故拆成兩筆、依南→北順序取 id。
    ("tohoku_main_line_s",  "東北本線(東京-黒磯)", "宇都宮線",   "TOH"),
    ("tohoku_main_line",    "東北本線",   "東北本線",            "TOH"),
    ("tokaido_main_line",   "東海道本線", "東海道線 (JR東日本)", "TKD"),
    # 同理：中央本線 東京–高尾 在「中央線快速」條目，総武本線 東京–千葉 在
    # 「横須賀・総武快速線」條目（本線條目只從東千葉起算）。
    ("chuo_main_line_e",    "中央本線(東京-高尾)", "中央線快速", "CHU"),
    ("chuo_main_line",      "中央本線",   "中央本線",            "CHU"),
    # 総武本線 東京側需兩個來源：快速線的地下區間（東京-錦糸町：新日本橋・馬喰町）
    # 與緩行線的各駅停車區間（御茶ノ水-千葉：秋葉原・両国・亀戸…）。兩表都含更多
    # 無關區間，故用 TRIM_RANGE 裁到需要的範圍。
    ("sobu_main_line_w",    "総武本線(東京-錦糸町)",   "横須賀・総武快速線", "SOB"),
    ("sobu_main_line_c",    "総武本線(御茶ノ水-千葉)", "中央・総武緩行線",   "SOB"),
    ("sobu_main_line",      "総武本線",   "総武本線",            "SOB"),
    ("joban_line",          "常磐線",     "常磐線",              "JOB"),
    ("takasaki_line",       "高崎線",     "高崎線",              "TKS"),
    ("joetsu_line",         "上越線",     "上越線",              "JET"),
    ("shinetsu_main_line",  "信越本線",   "信越本線",            "SIN"),
    ("uetsu_main_line",     "羽越本線",   "羽越本線",            "UET"),
    ("ou_main_line_s",      "奥羽本線(福島-新庄)", "山形線",     "OU"),
    ("ou_main_line",        "奥羽本線",   "奥羽本線",            "OU"),
    # --- 東京近郊 ---
    ("yamanote_line",       "山手線",     "山手線",              "YAM"),
    ("akabane_line",        "赤羽線",     "赤羽線",              "AKB"),
    # 埼京線走的「東北本線別線」（赤羽–武蔵浦和–大宮）自成一條路廊，
    # 車站（北赤羽・浮間舟渡・戸田・武蔵浦和・中浦和…）只在埼京線條目有。
    ("tohoku_branch_saikyo", "東北本線別線(赤羽-大宮)", "埼京線",  "SKY"),
    # 品鶴線（品川–西大井–武蔵小杉–新川崎–横浜）：横須賀線・湘南新宿ライン走的路廊。
    # 與東海道本線（川崎經由）是**實體分離**的路線，不可聯集進 tokaido_main_line，
    # 否則 西大井/武蔵小杉/新川崎 會出現在 京浜東北線・東海道線 視圖裡。
    # 法定終點是鶴見，但横須賀線在鶴見無月台、此後以自己的線路並行到横浜，
    # 故以 横浜 為段尾交會站（横須賀・総武快速線表的里程，東京起算後歸零）。
    ("hinkaku_line",        "品鶴線(品川-横浜)", "横須賀・総武快速線", "HNK"),
    # 大崎支線（大崎–西大井）：湘南新宿ライン・埼京線・相鉄直通 進出品鶴線的連絡線。
    # 少了這段，大崎 與 西大井/武蔵小杉 沒有共同 segment → 派段會斷開，列車被
    # 「繞錯邊」（經 品川→東京→上野→池袋 而非 大崎→渋谷→新宿）。
    ("osaki_hinkaku_branch", "大崎支線(大崎-西大井)", "湘南新宿ライン", "OSK"),
    ("keiyo_line",          "京葉線",     "京葉線",              "KEY"),
    ("musashino_line",      "武蔵野線",   "武蔵野線",            "MSN"),
    ("nambu_line",          "南武線",     "南武線",              "NAM"),
    ("tsurumi_line",        "鶴見線",     "鶴見線",              "TRM"),
    ("yokohama_line",       "横浜線",     "横浜線",              "YKH"),
    ("negishi_line",        "根岸線",     "根岸線",              "NEG"),
    ("yokosuka_line",       "横須賀線",   "横須賀線",            "YKS"),
    ("sagami_line",         "相模線",     "相模線",              "SGM"),
    ("ome_line",            "青梅線",     "青梅線",              "OME"),
    ("itsukaichi_line",     "五日市線",   "五日市線",            "ITK"),
    ("hachiko_line",        "八高線",     "八高線",              "HCK"),
    ("kawagoe_line",        "川越線",     "川越線",              "KWG"),
    ("ito_line",            "伊東線",     "伊東線",              "ITO"),
    # --- 千葉 ---
    ("sotobo_line",         "外房線",     "外房線",              "STB"),
    ("uchibo_line",         "内房線",     "内房線",              "UCB"),
    ("togane_line",         "東金線",     "東金線",              "TGN"),
    ("kururi_line",         "久留里線",   "久留里線",            "KRR"),
    ("narita_line",         "成田線",     "成田線",              "NRT"),
    ("kashima_line",        "鹿島線",     "鹿島線",              "KSM"),
    # --- 北關東 ---
    ("ryomo_line",          "両毛線",     "両毛線",              "RYM"),
    ("agatsuma_line",       "吾妻線",     "吾妻線",              "AGT"),
    ("nikko_line",          "日光線",     "日光線",              "NKK"),
    ("karasuyama_line",     "烏山線",     "烏山線",              "KRS"),
    ("mito_line",           "水戸線",     "水戸線",              "MIT"),
    ("suigun_line",         "水郡線",     "水郡線",              "SUG"),
    # --- 甲信越 ---
    ("shinonoi_line",       "篠ノ井線",   "篠ノ井線",            "SNI"),
    ("koumi_line",          "小海線",     "小海線",              "KUM"),
    ("iiyama_line",         "飯山線",     "飯山線",              "IIY"),
    ("oito_line",           "大糸線",     "大糸線",              "OIT"),
    ("echigo_line",         "越後線",     "越後線",              "ECH"),
    ("hakushin_line",       "白新線",     "白新線",              "HKS"),
    ("yahiko_line",         "弥彦線",     "弥彦線",              "YHK"),
    ("tadami_line",         "只見線",     "只見線",              "TDM"),
    # --- 東北 ---
    ("yonesaka_line",       "米坂線",     "米坂線",              "YNS"),
    ("banetsu_west_line",   "磐越西線",   "磐越西線",            "BNW"),
    ("banetsu_east_line",   "磐越東線",   "磐越東線",            "BNE"),
    ("senzan_line",         "仙山線",     "仙山線",              "SNZ"),
    ("senseki_line",        "仙石線",     "仙石線",              "SNS"),
    # 仙石東北ライン連絡線（塩釜–松島–高城町）：東北本線與仙石線的實體接點。
    # 少了它，塩釜↔高城町 沒有共同 segment → 前端補路徑會繞經 仙台 大迴圈。
    ("senseki_tohoku_conn", "仙石東北ライン(塩釜-高城町)", "仙石東北ライン", "SNT"),
    ("ishinomaki_line",     "石巻線",     "石巻線",              "ISM"),
    ("kesennuma_line",      "気仙沼線",   "気仙沼線",            "KSN"),
    ("ofunato_line",        "大船渡線",   "大船渡線",            "OFN"),
    ("kamaishi_line",       "釜石線",     "釜石線",              "KMS"),
    ("yamada_line",         "山田線",     "山田線",              "YMD"),
    ("hanawa_line",         "花輪線",     "花輪線",              "HNW"),
    ("kitakami_line",       "北上線",     "北上線",              "KTK"),
    ("tazawako_line",       "田沢湖線",   "田沢湖線",            "TZW"),
    ("oga_line",            "男鹿線",     "男鹿線",              "OGA"),
    ("gono_line",           "五能線",     "五能線",              "GON"),
    ("tsugaru_line",        "津軽線",     "津軽線",              "TSG"),
    ("ominato_line",        "大湊線",     "大湊線",              "OMN"),
    ("hachinohe_line",      "八戸線",     "八戸線",              "HCN"),
    ("rikuu_east_line",     "陸羽東線",   "陸羽東線",            "RKE"),
    ("rikuu_west_line",     "陸羽西線",   "陸羽西線",            "RKW"),
    ("aterazawa_line",      "左沢線",     "左沢線",              "ATZ"),
]

# 某些條目同頁含多條線的表格 → 只採包含此關鍵站名的表格
REQUIRE_STATION = {
    "赤羽線": "十条",
    "横須賀線": "久里浜",
    "山手線": "目黒",
}

# 來源表格含多餘區間時，裁到指定的起訖站（含頭含尾）並重新以起站為 0 起算里程。
TRIM_RANGE = {
    "sobu_main_line_w": ("東京", "錦糸町"),      # 快速線表其實是 久里浜→千葉 全走廊
    "sobu_main_line_c": ("御茶ノ水", "千葉"),    # 緩行線表是 三鷹→千葉
    # 埼京線表按「正式路線名」分段換算里程原點（品川から→池袋から→赤羽から），
    # 故東北本線別線那段的 run 從北赤羽起算（大宮=18.0 正是赤羽起算值）。
    # 交會站赤羽用 PREPEND_STATION 補回，里程 0 與該段座標系一致。
    "tohoku_branch_saikyo": ("北赤羽", "大宮"),
    # 湘南新宿ライン表是 新宿→逗子 全走廊，只取連絡段（大崎 8.6 / 西大井 14.2，
    # 新宿起算）→ 裁切後歸零為 0 / 5.6（營業キロ，見 KM_OVERRIDE）
    "osaki_hinkaku_branch": ("大崎", "西大井"),
    "hinkaku_line": ("品川", "横浜"),              # 横須賀・総武快速線表是 久里浜→千葉 全走廊
    # 仙石東北ライン表是 仙台→女川 全程；只取連絡段
    # （塩釜 13.4 / 松島 23.4 / 高城町 23.7，仙台起算）
    "senseki_tohoku_conn": ("塩釜", "高城町"),
}

# ==========================================================================
# 手動宣告的 segment：來源表格不足 3 列會被 extract_station_tables 濾掉
# （維基的 2 站支線表就是如此），但這些連絡線對「派段連通性」是必要的。
# 里程為営業キロ。
# ==========================================================================
MANUAL_SEGMENTS = [
    # 京葉線二俣支線／高谷支線：武蔵野線的列車經此進出京葉線。
    # 少了它們，西船橋↔南船橋・西船橋↔市川塩浜 沒有共同 segment，
    # 前端補路徑會繞經 総武線→千葉→蘇我 的超大迴圈。
    {"id": "keiyo_branch_futamata", "name": "京葉線二俣支線(西船橋-南船橋)",
     "prefix": "KEY", "stations": [("西船橋", 0.0), ("南船橋", 5.4)]},
    {"id": "keiyo_branch_koya", "name": "京葉線高谷支線(西船橋-市川塩浜)",
     "prefix": "KEY", "stations": [("西船橋", 0.0), ("市川塩浜", 5.9)]},
    # 武蔵野線 北小金支線／馬橋支線：維基把兩條自 南流山 分出的支線攤平成
    # 南流山–北小金–馬橋 一條鏈，憑空造出「北小金–馬橋 0.8km」的假邊
    # （tools/interpolate_passes.py 找路時常磐線列車會抄這條捷徑）。拆成兩段。
    {"id": "musashino_branch_kitakogane", "name": "武蔵野線北小金支線(南流山-北小金)",
     "prefix": "MSN", "stations": [("南流山", 0.0), ("北小金", 2.9)]},
    {"id": "musashino_branch_mabashi", "name": "武蔵野線馬橋支線(南流山-馬橋)",
     "prefix": "MSN", "stations": [("南流山", 0.0), ("馬橋", 3.7)]},
]

# 在裁切後的區間前端補上交會站（name, km）——用於來源表缺少起點交會站的情況。
# 里程與該 run 的座標系一致（之後會統一以首站重新歸零）。
PREPEND_STATION = {
    "tohoku_branch_saikyo": [("赤羽", 0.0)],
    # 大川支線法定為 武蔵白石–大川，但列車實際自 安善 分歧（武蔵白石不停），
    # 不補上 安善 就沒有任何一班車能同時落在本段與鶴見線本線 → 整段空白。
    "tsurumi_line_3": [("安善", -0.6)],
}

# 維基表格產生的偽區間（貨物支線/舊線），無旅客列車且會在拓樸留下孤立段。
DROP_SEGMENTS = {"joban_line_3",       # 三河島–隅田川–南千住（常磐貨物線）
                 "musashino_line_4"}   # 南流山–北小金–馬橋（改由 MANUAL_SEGMENTS 拆成兩條支線）

# 里程覆寫 {segment id: {站名: km}}：來源表的里程是**營業キロ**而非實際路線長，
# 且會誤導 tools/interpolate_passes.py 的最短路時才用。
#   大崎–西大井 在湘南新宿ライン表為 5.6，是「經品川」的運費里程（實際經蛇窪信号場
#   直行，約 3.4 km 近似值）。不修的話 渋谷→武蔵小杉 直達車會被繞成 大崎→品川→品鶴線。
#   本段無 view preset 引用，改值不影響任何視圖的座標。
KM_OVERRIDE = {
    "osaki_hinkaku_branch": {"西大井": 3.4},
}

# 環狀線閉合：維基山手線表只到 有楽町(33.7)，缺收尾的 有楽町→東京 一段。
# 前端 CIRCULAR 以 segment 里程跨距總和當一圈高度，不補的話 loopKm=33.7，
# 有楽町 會直接疊在 東京 上。段尾補回起站（東京 @34.5），詳見 CLAUDE.md。
#   {segment id: (起站名, 最後一站→起站 的站間 km)}
CLOSE_LOOP = {"yamanote_line": ("東京", 0.8)}

# ==========================================================================
# 並行複線的車站聯集 (MERGE_SOURCES)
#
# 東京圈的幹線是「電車線＋列車線」雙複線：同一法定路線上，各駅停車（京浜東北線・
# 中央総武緩行線）與快速/中距離電車（宇都宮線・東海道線快速）**停靠不同的站集合**，
# 維基把它們寫在不同條目。若只取其中一邊，另一邊的專屬站（大井町・王子・飯田橋…）
# 就不在拓樸裡，那些列車的停靠會整批掉光。
#
# 解法：同一 segment 取兩邊的**聯集**，依里程排序。快速車自然只停其子集，
# 在運行圖上畫成斜率較大、跳過中間站的線——這正是真實運行圖的樣子。
#
# 額外來源的里程原點常與主表不同（京浜東北表是「大宮から」，主表是「東京から」），
# 故以兩表的共用站做兩點線性對位，把額外站的里程換算到主表座標系。
#   {segment_id: [(維基條目, 裁切起站, 裁切迄站), ...]}
# ==========================================================================
MERGE_SOURCES = {
    # 東北本線 東京–大宮：列車線(宇都宮線) ∪ 電車線(京浜東北線 王子・東十条・川口…)
    "tohoku_main_line_s": [("京浜東北・根岸線", "東京", "大宮")],
    # 東海道本線 東京–大船：列車線 ∪ 電車線(大井町・大森・蒲田…) ∪ 横須賀線 横浜–大船
    # (保土ケ谷・東戸塚：同一路廊的並行線)。品川–横浜 的品鶴線另成 hinkaku_line。
    "tokaido_main_line": [("京浜東北・根岸線", "東京", "横浜"),
                          ("横須賀・総武快速線", "横浜", "大船")],
    # 中央本線 東京–高尾：快速線 ∪ 緩行線(飯田橋・市ケ谷・信濃町…)
    "chuo_main_line_e": [("中央・総武緩行線", "三鷹", "御茶ノ水")],
}

SKIP_STATIONS = {}   # 目前無需排除；BAD_TOKENS 已濾掉信号場/貨物駅等非旅客站

BAD_TOKENS = ("信号場", "操車場", "貨物", "廃止", "臨時", "分岐", "起点", "終点", "区間")
NUM_RE = re.compile(r"\d+(?:\.\d+)?")   # 不加錨點：需能從『東京から39.2』抓出 39.2

GLOBAL_STATION_ID_MAP = {}
PREFIX_COUNTER = {}

# 同名異站 (HOMONYMS)：站 id 以站名全域共用，同名但實體不同的站會被併成同一個 id
# （曾造成 根岸線 的列車在 只見線 視圖的「根岸」列畫出一整排停靠點）。
# 列在這裡的 (prefix, 站名) 另編獨立 id；站名（顯示用）不變。
HOMONYMS = {
    ("OU", "大久保"),    # 奥羽本線（秋田） ≠ 中央線 大久保（東京）
    ("OU", "大沢"),      # 奥羽本線（山形線 米沢市） ≠ 上越線 大沢（新潟）
    ("TDM", "根岸"),     # 只見線（福島） ≠ 根岸線 根岸（横浜）
}


from station_name import clean_station_name   # noqa: E402  三支腳本共用同一規則


def parse_km(s):
    """取出格內第一個數字。維基常在起點站的累計格寫成『東京から39.2』
    （総武本線 千葉站即如此），純數字比對會整列漏掉。"""
    m = NUM_RE.search(str(s).replace(",", ""))
    return float(m.group(0)) if m else None


def get_soup(title):
    for attempt in range(3):
        try:
            r = SESSION.get(WIKI + title, timeout=30)
            r.raise_for_status()
            return BeautifulSoup(r.text, "html.parser")
        except Exception:
            if attempt == 2:
                return None
            time.sleep(2)
    return None


def extract_station_tables(soup, jp_name):
    """回傳所有合格車站表解析出的 [(name, km)] 清單（依文件順序，一表一組）。"""
    out = []
    need = REQUIRE_STATION.get(jp_name)
    for tb in soup.find_all("table", class_="wikitable"):
        raw = tb.get_text()
        if "駅名" not in raw:
            continue
        if need and need not in raw:
            continue
        grid, is_th = table_to_grid(tb)
        if len(grid) < 3:
            continue
        cols, depth = flat_columns(grid, is_th)

        nm = [i for i, c in enumerate(cols) if "駅名" in c]
        if not nm:
            continue
        cum = [i for i, c in enumerate(cols)
               if ("営業キロ" in c or "キロ" in c) and "累計" in c]
        gap = [i for i, c in enumerate(cols)
               if ("営業キロ" in c or "キロ" in c) and "駅間" in c]
        plain = [i for i, c in enumerate(cols) if "営業キロ" in c or "キロ程" in c]

        if cum:
            kind, kidx = "cum", cum[0]
        elif [i for i in plain if i not in gap]:
            kind, kidx = "cum", [i for i in plain if i not in gap][0]
        elif gap:
            kind, kidx = "gap", gap[0]
        else:
            continue

        rows, running = [], 0.0
        for r in range(depth, len(grid)):
            row = grid[r]
            if max(kidx, nm[0]) >= len(row):
                continue
            name = clean_station_name(row[nm[0]])
            if not name or any(b in row[nm[0]] for b in BAD_TOKENS):
                continue
            if name in SKIP_STATIONS.get(jp_name, ()):  # noqa: E713
                continue
            km = parse_km(row[kidx])
            if km is None:
                continue
            if kind == "gap":
                running += km
                km = round(running, 2)
            rows.append((name, km))

        if len(rows) >= 3:
            out.append(rows)
    return out


def dedupe_keep_order(rows):
    seen, out = set(), []
    for name, km in rows:
        if name in seen:
            continue
        seen.add(name)
        out.append((name, km))
    return out


def split_monotonic(rows):
    """把 (name, km) 序列切成單調遞增的連續段。
    多區間路線（信越本線 高崎-横川 / 篠ノ井-長野 / 直江津-新潟）在維基是分開的表格，
    里程各自從 0 起算 → 合併後不單調，須切段。"""
    runs, cur = [], []
    for item in rows:
        if cur and item[1] < cur[-1][1]:
            if len(cur) >= 2:
                runs.append(cur)
            cur = [item]
        else:
            cur.append(item)
    if len(cur) >= 2:
        runs.append(cur)
    return runs


def merge_extra(primary, extra):
    """把 extra 的車站聯集進 primary（皆為 [(name, km)]，km 原點可不同）。

    以兩表共用站做兩點線性對位：km_primary ≈ a * km_extra + b。共用站取 primary 的
    里程為準，extra 獨有的站用換算後的里程插入，最後依里程排序。
    共用站不足 2 個時無法對位 → 放棄合併（回傳 primary 原樣）。
    """
    pmap = dict(primary)
    shared = [(pmap[n], km) for n, km in extra if n in pmap]
    if len(shared) < 2:
        return primary, 0
    (p1, e1), (p2, e2) = shared[0], shared[-1]
    if e2 == e1:
        return primary, 0
    a = (p2 - p1) / (e2 - e1)
    b = p1 - a * e1

    merged = dict(primary)
    added = 0
    for n, km in extra:
        if n in merged:
            continue
        merged[n] = round(a * km + b, 2)
        added += 1
    rows = sorted(merged.items(), key=lambda kv: kv[1])
    # 對位後里程若落在主表範圍外一大截，視為對位失敗
    lo, hi = min(pmap.values()), max(pmap.values())
    if rows[0][1] < lo - 5 or rows[-1][1] > hi + 5:
        return primary, 0
    return rows, added


def trim_runs(runs, start, end):
    """只留下同時含 start 與 end 的那個 run，並裁成 start..end（含）。"""
    for run in runs:
        names = [n for n, _ in run]
        if start in names and end in names:
            i, j = names.index(start), names.index(end)
            if i > j:
                i, j = j, i
            return [run[i:j + 1]]
    return []


def assign_id(prefix, name):
    """站 id 全域以站名共用；未見過才新編號。HOMONYMS 內的同名異站另立鍵。"""
    key = f"{name}@{prefix}" if (prefix, name) in HOMONYMS else name
    if key in GLOBAL_STATION_ID_MAP:
        return GLOBAL_STATION_ID_MAP[key]
    PREFIX_COUNTER[prefix] = PREFIX_COUNTER.get(prefix, 0) + 1
    sid = f"JRE_{prefix}_{PREFIX_COUNTER[prefix]:03d}"
    GLOBAL_STATION_ID_MAP[key] = sid
    return sid


def main():
    print(f"🗺️  建置 JR 東日本拓樸（{len(LINES)} 條法定路線）\n")

    # 併發抓維基（限速友善：8 workers）
    pages = {}
    extra_titles = {w for srcs in MERGE_SOURCES.values() for w, _, _ in srcs}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(get_soup, wiki): seg for seg, jp, wiki, pre in LINES}
        futs.update({ex.submit(get_soup, w): "extra:" + w for w in extra_titles})
        for f in as_completed(futs):
            pages[futs[f]] = f.result()

    segments, report = [], []
    for seg_id, jp, wiki, prefix in LINES:      # 依 LINES 順序處理，保證 id 優先序
        soup = pages.get(seg_id)
        if soup is None:
            report.append((jp, "FETCH_FAIL", 0))
            continue

        tables = extract_station_tables(soup, jp)
        if not tables:
            report.append((jp, "NO_TABLE", 0))
            continue

        # 每張合格表格＝一個連續區間；**不跨表去重**，因為分岔/支線的交會站
        # （如成田線 我孫子支線的「成田」）本來就該同時出現在兩個 segment 裡，
        # 前端正是靠共用站 id 偵測分岔。只在表格內部去重、再切單調段。
        runs = []
        for t in tables:
            runs.extend(split_monotonic(dedupe_keep_order(t)))
        if not runs:
            report.append((jp, "NOT_MONOTONIC", 0))
            continue

        # 丟掉「站集合被更長 run 完全包含」的冗餘 run（維基常有貨物支線/舊線小表）。
        # 以長度序判斷包含關係，但輸出仍保留原本的文件順序（里程/ id 才會南→北遞增）。
        order = {id(r): i for i, r in enumerate(runs)}
        kept = []
        for run in sorted(runs, key=len, reverse=True):
            names = {n for n, _ in run}
            if any(names <= {n for n, _ in k} for k in kept):
                continue
            kept.append(run)
        runs = sorted(kept, key=lambda r: order[id(r)])

        if seg_id in TRIM_RANGE:
            runs = trim_runs(runs, *TRIM_RANGE[seg_id])
            if not runs:
                report.append((jp, "TRIM_MISS", 0))
                continue

        # 並行複線：把電車線/緩行線的專屬站聯集進來（只作用在最長的 run）
        merged_note = ""
        if seg_id in MERGE_SOURCES and runs:
            main_i = max(range(len(runs)), key=lambda i: len(runs[i]))
            for wiki_extra, s_from, s_to in MERGE_SOURCES[seg_id]:
                esoup = pages.get("extra:" + wiki_extra)
                if esoup is None:
                    continue
                etabs = extract_station_tables(esoup, wiki_extra)
                eruns = []
                for t in etabs:
                    eruns.extend(split_monotonic(dedupe_keep_order(t)))
                picked = trim_runs(eruns, s_from, s_to)
                if not picked:
                    continue
                runs[main_i], n_add = merge_extra(runs[main_i], picked[0])
                merged_note += f"+{n_add}"

        total = 0
        for i, run in enumerate(runs):
            sid = seg_id if len(runs) == 1 else f"{seg_id}_{i + 1}"
            if sid in DROP_SEGMENTS:
                continue
            if sid in PREPEND_STATION:          # 以最終 segment id 為鍵
                run = PREPEND_STATION[sid] + run
            if sid in CLOSE_LOOP:               # 環狀線：段尾補回起站使鏈閉合
                back_to, leg = CLOSE_LOOP[sid]
                run = run + [(back_to, run[-1][1] + leg)]
            name = jp if len(runs) == 1 else f"{jp}({run[0][0]}-{run[-1][0]})"
            base = run[0][1]
            stations = [{"id": assign_id(prefix, n),
                         "name": n,
                         "km": round(km - base, 2)} for n, km in run]
            for st in stations:
                st["km"] = KM_OVERRIDE.get(sid, {}).get(st["name"], st["km"])
            segments.append({"id": sid, "name": name, "stations": stations})
            total += len(stations)
        report.append((jp, f"OK x{len(runs)}{merged_note}", total))

    for ms in MANUAL_SEGMENTS:
        segments.append({
            "id": ms["id"], "name": ms["name"],
            "stations": [{"id": assign_id(ms["prefix"], n), "name": n, "km": km}
                         for n, km in ms["stations"]],
        })
        report.append((ms["name"], "OK manual", len(ms["stations"])))

    topo = {"operator_id": "JR_East", "segments": segments}
    out = JSON_DIR / "topology.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(topo, f, ensure_ascii=False, indent=1)

    ok = [r for r in report if r[1].startswith("OK")]
    bad = [r for r in report if not r[1].startswith("OK")]
    print(f"✅ {len(ok)}/{len(LINES) + len(MANUAL_SEGMENTS)} 路線成功｜"
          f"segment {len(segments)} 個｜"
          f"唯一車站 {len(GLOBAL_STATION_ID_MAP)} 個")
    for jp, st, n in report:
        flag = "  " if st.startswith("OK") else "❌"
        print(f"  {flag} {jp:8s} {st:14s} {n:3d} 站")
    if bad:
        print(f"\n⚠️  {len(bad)} 條線需檢查：{[b[0] for b in bad]}")
    print(f"\n📄 已輸出 {out}")


if __name__ == "__main__":
    main()
