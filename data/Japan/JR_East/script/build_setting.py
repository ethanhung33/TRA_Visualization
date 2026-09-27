#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_setting.py — 產生 json/setting.json

兩件事：
  1. view_presets：以「營運系統名」（山手線・京浜東北線・埼京線…）組合法定路線
     segment。topology 是法定路線切分（互不重疊），營運線視圖靠 {id,start,end} 截取拼接。
  2. train_color：讀已轉換好的 timetable_*.json，蒐集實際出現的所有種別標籤，
     確保**每個標籤都有顏色**（validator 會對缺色種別出 WARNING）。
     通用種別用日本線統一色票；具名特急用 NAMED_COLORS，未收錄者依序自動配色。

用法（需先跑 convert_timetable.py）：
    py data/Japan/JR_East/script/build_setting.py
"""
import sys
import json
from pathlib import Path
from collections import Counter

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

JSON_DIR = Path(__file__).parent.parent / "json"

# ==========================================================================
# view_presets：(key, 顯示名, view_type, lines, button_color)
# lines 元素：segment id 字串，或 {"id":…, "start":站名, "end":站名} 做區間截取
# ==========================================================================
P = [
    # ---- 東京圈 ----
    ("yamanote", "山手線 (環狀)", "CIRCULAR",
     ["yamanote_line"], ["#9ACD32", "#6B8E23"]),
    ("keihin_tohoku", "京浜東北・根岸線 (大宮-大船)", "LINEAR",
     [{"id": "tohoku_main_line_s", "start": "大宮", "end": "東京"},
      {"id": "tokaido_main_line", "start": "東京", "end": "横浜"},
      "negishi_line"], ["#00BFFF", "#0080BF"]),
    ("chuo", "中央線 (東京-塩尻)", "LINEAR",
     ["chuo_main_line_e", "chuo_main_line_1"], ["#FF8C00", "#CC6600"]),
    ("chuo_sobu_local", "中央・総武線各駅停車 (三鷹-千葉)", "LINEAR",
     [{"id": "chuo_main_line_e", "start": "三鷹", "end": "御茶ノ水"},
      {"id": "sobu_main_line_c", "start": "御茶ノ水", "end": "千葉"}], ["#FFEA00", "#B8A200"]),
    ("sobu", "総武線 (東京-銚子)", "LINEAR",
     ["sobu_main_line_w",
      {"id": "sobu_main_line_c", "start": "錦糸町", "end": "千葉"},
      "sobu_main_line"], ["#FFD700", "#BFA000"]),
    # 上野東京ライン：東海道線と宇都宮線／高崎線を東京で直結した直通系統
    ("ueno_tokyo_utsunomiya", "上野東京ライン (熱海-宇都宮)", "LINEAR",
     [{"id": "tokaido_main_line", "start": "熱海", "end": "東京"},
      {"id": "tohoku_main_line_s", "start": "東京", "end": "宇都宮"}], ["#FFA726", "#E65100"]),
    ("ueno_tokyo_takasaki", "上野東京ライン (熱海-高崎)", "LINEAR",
     [{"id": "tokaido_main_line", "start": "熱海", "end": "東京"},
      "takasaki_line"], ["#FFB74D", "#EF6C00"]),
    ("yokosuka", "横須賀線 (東京-久里浜)", "LINEAR",
     # 品川–横浜 走品鶴線（西大井・武蔵小杉・新川崎），不是東海道本線（川崎經由）
     [{"id": "tokaido_main_line", "start": "東京", "end": "品川"},
      {"id": "hinkaku_line", "start": "品川", "end": "横浜"},
      {"id": "tokaido_main_line", "start": "横浜", "end": "大船"},
      "yokosuka_line"], ["#4169E1", "#27408B"]),
    ("utsunomiya", "宇都宮線 (東京-黒磯)", "LINEAR",
     ["tohoku_main_line_s"], ["#FF69B4", "#C71585"]),
    ("takasaki", "高崎線 (東京-高崎)", "LINEAR",
     ["takasaki_line"], ["#DAA520", "#8B6914"]),
    ("joban", "常磐線 (日暮里-仙台)", "LINEAR",
     # 綠（JR 常磐線線色）。不可用青綠：與「快速」種別色 #5BD1C4 撞色，
     # 取手–土浦 的站站停普通會被看成快速
     ["joban_line_1", "joban_line_2"], ["#4CD37A", "#1B8A45"]),
    # 常磐線各駅停車（千代田線直通）：與 上野發著的中距離普通 停站不同（亀有・金町・北松戸…）
    ("joban_local", "常磐線各駅停車 (綾瀬-取手)", "LINEAR",
     [{"id": "joban_line_1", "start": "綾瀬", "end": "取手"}], ["#8FBC8F", "#556B2F"]),
    ("saikyo", "埼京線 (大崎-大宮)", "LINEAR",
     [{"id": "yamanote_line", "start": "大崎", "end": "池袋"},
      "akabane_line", "tohoku_branch_saikyo"], ["#2E8B57", "#1F5F3C"]),
    ("keiyo", "京葉線 (東京-蘇我)", "LINEAR",
     ["keiyo_line"], ["#DC143C", "#A00E2C"]),
    ("musashino", "武蔵野線 (府中本町-西船橋)", "LINEAR",
     ["musashino_line_1"], ["#FF6347", "#C24B36"]),
    ("nambu", "南武線 (川崎-立川)", "LINEAR",
     ["nambu_line_1"], ["#FFD54F", "#C9A227"]),
    ("yokohama", "横浜線 (東神奈川-八王子)", "LINEAR",
     ["yokohama_line"], ["#32CD32", "#228B22"]),
    ("tsurumi", "鶴見線 (鶴見-扇町)", "LINEAR",
     ["tsurumi_line_1"], ["#87CEEB", "#4682B4"]),
    ("ome", "青梅線 (立川-奥多摩)", "LINEAR",
     ["ome_line"], ["#B0C4DE", "#6A7F9E"]),
    ("itsukaichi", "五日市線 (拝島-武蔵五日市)", "LINEAR",
     ["itsukaichi_line"], ["#9370DB", "#5D3FA8"]),
    ("hachiko", "八高線 (八王子-高崎)", "LINEAR",
     ["hachiko_line_1", "hachiko_line_2"], ["#CD853F", "#8B5A2B"]),
    ("kawagoe", "川越線 (大宮-高麗川)", "LINEAR",
     ["kawagoe_line_1", "kawagoe_line_2"], ["#66CDAA", "#3E8E75"]),
    ("sagami", "相模線 (茅ケ崎-橋本)", "LINEAR",
     ["sagami_line"], ["#40E0D0", "#2A968C"]),
    ("ito", "伊東線 (熱海-伊東)", "LINEAR",
     ["ito_line"], ["#FFA07A", "#C2765A"]),
    # ---- 千葉 ----
    ("sotobo", "外房線 (千葉-安房鴨川)", "LINEAR",
     ["sotobo_line"], ["#FF4500", "#B33000"]),
    ("uchibo", "内房線 (蘇我-安房鴨川)", "LINEAR",
     ["uchibo_line"], ["#1E90FF", "#1565C0"]),
    # 空港支線（成田–成田空港 10km）夾在兩段中間時，其站名會被第二個「成田」擠掉 → 拆成兩個視圖
    ("narita", "成田線 (千葉-銚子)", "LINEAR",
     [{"id": "narita_line_1", "start": "千葉", "end": "成田"},
      "narita_line_2"], ["#8FBC8F", "#5F7F5F"]),
    ("narita_airport", "成田線 (千葉-成田空港)", "LINEAR",
     ["narita_line_1"], ["#FF6E9C", "#AD1457"]),
    ("narita_abiko", "成田線 (成田-我孫子)", "LINEAR",
     ["narita_line_3"], ["#A9BA9D", "#6E7D64"]),
    ("kashima", "鹿島線 (香取-鹿島)", "LINEAR",
     ["kashima_line"], ["#DEB887", "#9C7A4F"]),
    ("togane", "東金線 (大網-成東)", "LINEAR",
     ["togane_line"], ["#F4A460", "#B87333"]),
    ("kururi", "久留里線 (木更津-上総亀山)", "LINEAR",
     ["kururi_line"], ["#BDB76B", "#8B864E"]),
    # ---- 北關東 ----
    ("ryomo", "両毛線 (小山-高崎)", "LINEAR",
     ["ryomo_line"], ["#FFB6C1", "#CD8C95"]),
    ("mito", "水戸線 (小山-友部)", "LINEAR",
     ["mito_line"], ["#7FFFD4", "#4FA98D"]),
    ("suigun", "水郡線 (水戸-郡山)", "LINEAR",
     ["suigun_line_1"], ["#98FB98", "#5FA85F"]),
    ("nikko", "日光線 (宇都宮-日光)", "LINEAR",
     ["nikko_line"], ["#C71585", "#8B0A50"]),
    ("karasuyama", "烏山線 (宝積寺-烏山)", "LINEAR",
     ["karasuyama_line"], ["#DDA0DD", "#9B599B"]),
    ("agatsuma", "吾妻線 (渋川-大前)", "LINEAR",
     ["agatsuma_line"], ["#B22222", "#7D1818"]),
    # ---- 甲信越 ----
    ("joetsu", "上越線 (高崎-長岡)", "LINEAR",
     ["joetsu_line"], ["#6A5ACD", "#483D8B"]),
    ("shinonoi", "篠ノ井線 (塩尻-長野)", "LINEAR",
     ["shinonoi_line"], ["#4682B4", "#2F5C80"]),
    ("shinetsu", "信越本線 (直江津-新潟)", "LINEAR",
     ["shinetsu_main_line_3"], ["#5F9EA0", "#3D6A6B"]),
    ("shinetsu_yokokawa", "信越本線 (高崎-横川)", "LINEAR",
     ["shinetsu_main_line_1"], ["#778899", "#4F5A66"]),
    ("koumi", "小海線 (小淵沢-小諸)", "LINEAR",
     ["koumi_line"], ["#48D1CC", "#2E8B87"]),
    ("iiyama", "飯山線 (豊野-越後川口)", "LINEAR",
     ["iiyama_line"], ["#8FBC8F", "#5B7F5B"]),
    ("oito", "大糸線 (松本-南小谷)", "LINEAR",
     ["oito_line_1"], ["#00CED1", "#008B8B"]),
    ("echigo", "越後線 (柏崎-新潟)", "LINEAR",
     ["echigo_line"], ["#F08080", "#B35A5A"]),
    ("hakushin", "白新線 (新潟-新発田)", "LINEAR",
     ["hakushin_line"], ["#E9967A", "#A96A55"]),
    ("yahiko", "弥彦線 (弥彦-東三条)", "LINEAR",
     ["yahiko_line"], ["#D8BFD8", "#9A899A"]),
    ("tadami", "只見線 (会津若松-小出)", "LINEAR",
     ["tadami_line"], ["#708090", "#4A5560"]),
    # ---- 東北 ----
    ("tohoku_north", "東北本線 (黒磯-盛岡)", "LINEAR",
     ["tohoku_main_line_1", "tohoku_main_line_2"], ["#FF1493", "#B0106C"]),
    ("ou", "奥羽本線 (福島-青森)", "LINEAR",
     ["ou_main_line_s", "ou_main_line_1", "ou_main_line_2"],
     ["#9932CC", "#6A22A0"]),
    ("uetsu", "羽越本線 (新津-秋田)", "LINEAR",
     ["uetsu_main_line"], ["#00BFA5", "#00897B"]),
    ("banetsu_west", "磐越西線 (郡山-新津)", "LINEAR",
     ["banetsu_west_line_2", "banetsu_west_line_1"], ["#FFA500", "#BF7C00"]),
    ("banetsu_east", "磐越東線 (いわき-郡山)", "LINEAR",
     ["banetsu_east_line"], ["#FF8C69", "#C2694F"]),
    ("yonesaka", "米坂線 (米沢-坂町)", "LINEAR",
     ["yonesaka_line"], ["#BC8F8F", "#8B6969"]),
    ("senzan", "仙山線 (仙台-山形)", "LINEAR",
     ["senzan_line"], ["#7B68EE", "#5546A5"]),
    ("senseki", "仙石線 (あおば通-石巻)", "LINEAR",
     ["senseki_line_1", "senseki_line_2"], ["#00FA9A", "#00A86B"]),
    ("ishinomaki", "石巻線 (小牛田-女川)", "LINEAR",
     ["ishinomaki_line"], ["#AFEEEE", "#76A8A8"]),
    ("kesennuma", "気仙沼線 (前谷地-気仙沼)", "LINEAR",
     ["kesennuma_line_1", "kesennuma_line_2"], ["#FFE4B5", "#BFA97F"]),
    ("ofunato", "大船渡線 (一ノ関-盛)", "LINEAR",
     ["ofunato_line_1", "ofunato_line_2"], ["#D2B48C", "#8B7355"]),
    ("kamaishi", "釜石線 (花巻-釜石)", "LINEAR",
     ["kamaishi_line"], ["#DA70D6", "#9B4E97"]),
    ("yamada", "山田線 (盛岡-宮古)", "LINEAR",
     ["yamada_line"], ["#6B8E23", "#4A6318"]),
    ("hanawa", "花輪線 (好摩-大館)", "LINEAR",
     ["hanawa_line"], ["#FF7F24", "#C25E1B"]),
    ("kitakami", "北上線 (北上-横手)", "LINEAR",
     ["kitakami_line"], ["#9AC0CD", "#6C8792"]),
    ("tazawako", "田沢湖線 (盛岡-大曲)", "LINEAR",
     ["tazawako_line"], ["#EEC900", "#A89000"]),
    ("oga", "男鹿線 (追分-男鹿)", "LINEAR",
     ["oga_line"], ["#FF6EB4", "#C2537F"]),
    ("gono", "五能線 (東能代-弘前)", "LINEAR",
     ["gono_line"], ["#00B2EE", "#007DA8"]),
    ("tsugaru", "津軽線 (青森-三厩)", "LINEAR",
     ["tsugaru_line"], ["#7EC0EE", "#5887A8"]),
    ("ominato", "大湊線 (野辺地-大湊)", "LINEAR",
     ["ominato_line"], ["#B4CDCD", "#7E9090"]),
    ("hachinohe", "八戸線 (八戸-久慈)", "LINEAR",
     ["hachinohe_line"], ["#CDC5BF", "#8B8378"]),
    ("rikuu_east", "陸羽東線 (小牛田-新庄)", "LINEAR",
     ["rikuu_east_line"], ["#C1FFC1", "#87A987"]),
    ("rikuu_west", "陸羽西線 (新庄-酒田)", "LINEAR",
     ["rikuu_west_line"], ["#FFDAB9", "#BF9F82"]),
    ("aterazawa", "左沢線 (北山形-左沢)", "LINEAR",
     ["aterazawa_line"], ["#EED5B7", "#A89681"]),
]

# ==========================================================================
# 運行系統標籤 (SYSTEM_LABEL)：東京圈的「普通」由多個系統共用車站（山手線視圖裡同時有
# 山手線・京浜東北線・東海道線・宇都宮/高崎線…的普通），種別都是「普通」無法分開。
# convert_timetable.py 把普通車的 type 換成所屬系統名：取「包含該車全部停靠站」的 preset
# 中總長最短者（見 classify_system）。系統名作為「普通」群組下的子車種 → 可在車種篩選中
# 單獨開關，顏色沿用該 preset 的 button_color。
# ==========================================================================
SYSTEM_LABEL = {
    "yamanote": "山手線",
    "keihin_tohoku": "京浜東北線",
    "tokaido": "東海道線",
    "yokosuka": "横須賀線",
    "utsunomiya": "宇都宮線",
    "takasaki": "高崎線",
    "ueno_tokyo_utsunomiya": "上野東京ライン",
    "ueno_tokyo_takasaki": "上野東京ライン",
    "joban": "常磐線",
    "joban_local": "常磐線各駅停車",
    "chuo": "中央線",
    "chuo_sobu_local": "中央・総武線各駅停車",
    "sobu": "総武線",
    "saikyo": "埼京線",
    "keiyo": "京葉線",
    "musashino": "武蔵野線",
    "nambu": "南武線",
    "yokohama": "横浜線",
}
# 只用於系統判定、不出現在路線選單的定義（格式同 P）：
#   東海道線 東京–熱海 已被 上野東京ライン 兩個視圖完整涵蓋，故不另設視圖；但東京發著、
#   不直通的東海道線普通車仍需判成「東海道線」而非「上野東京ライン」。
SYSTEM_ONLY_PRESETS = [
    ("tokaido", "東海道線 (東京-熱海)", "LINEAR",
     ["tokaido_main_line"], ["#FF7F50", "#CC5A33"]),
]
# 不被任何單一 preset 完整包含、但可由路線判定的系統（見 convert_timetable.classify_system）
EXTRA_SYSTEM_COLOR = {
    "湘南新宿ライン": ["#E57CF5", "#8E24AA"],   # 避開成田エクスプレス的粉紅（同在山手線視圖）
}

# 日本線通用種別色（skill 規範，跨系統統一）：[深色模式, 淺色模式]
GENERIC = {
    "普通":        ["#B0B0B0", "#666666"],
    "各駅停車":     ["#B0B0B0", "#666666"],
    "快速":        ["#5BD1C4", "#00796B"],
    "特別快速":     ["#7FE3D4", "#00695C"],
    "中央特快":     ["#4FC3F7", "#0277BD"],
    "青梅特快":     ["#81D4FA", "#0288D1"],
    "通勤快速":     ["#FFCA5F", "#EF6C00"],
    "通勤特別快速":  ["#FFB74D", "#E65100"],
    "特急":        ["#FF7B7B", "#C62828"],
    "急行":        ["#FF9472", "#D84315"],
    "準急":        ["#86D98A", "#2E7D32"],
    "寝台特急":     ["#FFDAB9", "#CD853F"],
    "ライナー":     ["#B98EFF", "#6A1B9A"],
}

# 具名列車專屬色（維持各自獨立，不套通用色）
NAMED = {
    "特急成田エクスプレス":  ["#FF6E9C", "#AD1457"],
    "特急ひたち":         ["#FF7B7B", "#C62828"],
    "特急ときわ":         ["#FFA07A", "#D84315"],
    "特急あずさ":         ["#B39DFF", "#4527A0"],
    "特急かいじ":         ["#9FA8DA", "#283593"],
    "特急富士回遊":        ["#90CAF9", "#1565C0"],
    "特急踊り子":         ["#FF8A80", "#C62828"],
    "特急サフィール踊り子": ["#80DEEA", "#00838F"],
    "特急湘南":          ["#FFAB91", "#BF360C"],
    "特急スワローあかぎ":   ["#FFCC80", "#E65100"],
    "特急あかぎ":         ["#FFD180", "#EF6C00"],
    "特急草津・四万":      ["#A5D6A7", "#2E7D32"],
    "特急しおさい":        ["#81C784", "#1B5E20"],
    "特急わかしお":        ["#4DD0E1", "#00695C"],
    "特急さざなみ":        ["#4FC3F7", "#01579B"],
    "特急日光":          ["#CE93D8", "#6A1B9A"],
    "特急きぬがわ":        ["#F48FB1", "#AD1457"],
    "特急スペーシア日光":   ["#FFF176", "#F9A825"],
    "特急いなほ":         ["#7986CB", "#303F9F"],
    "特急つがる":         ["#4DB6AC", "#00796B"],
    "特急あけぼの":        ["#B0BEC5", "#455A64"],
    "特急やまびこ":        ["#AED581", "#558B2F"],
    "寝台特急カシオペア":   ["#FFE082", "#FF8F00"],
    "快速アーバン":        ["#8FC9FF", "#1565C0"],
    "快速ラビット":        ["#FFCA5F", "#EF6C00"],
    "快速しもうさ":        ["#A5D6A7", "#388E3C"],
    "快速むさしの":        ["#CE93D8", "#7B1FA2"],
    "快速なのはな":        ["#FFF59D", "#F9A825"],
    "快速リゾートしらかみ": ["#80CBC4", "#00695C"],
}

# 自動配色池（NAMED / GENERIC 都沒收錄的種別依序取用，確保不缺色）
FALLBACK = [
    ["#F5B7B1", "#943126"], ["#AED6F1", "#1A5276"], ["#A9DFBF", "#196F3D"],
    ["#F9E79F", "#9A7D0A"], ["#D7BDE2", "#5B2C6F"], ["#F5CBA7", "#A04000"],
    ["#A3E4D7", "#0E6251"], ["#FADBD8", "#922B21"], ["#D6EAF8", "#21618C"],
    ["#D5F5E3", "#1D8348"], ["#FCF3CF", "#B7950B"], ["#E8DAEF", "#6C3483"],
]


def group_of(label):
    """train_color 巢狀分組鍵。"""
    for g in ("寝台特急", "特急", "急行", "準急"):
        if label.startswith(g):
            return "寝台" if g == "寝台特急" else g
    for g in ("通勤特別快速", "通勤快速", "中央特快", "青梅特快", "特別快速", "快速"):
        if label.startswith(g):
            return "快速"
    return "普通"


def span_km(lines, seg_by_id):
    """一個 view preset 的總長度（km）：各段（含 start/end 截取）里程跨距相加。"""
    total = 0.0
    for l in lines:
        sid = l if isinstance(l, str) else l["id"]
        sts = seg_by_id[sid]["stations"]
        kms = [s["km"] for s in sts]
        if isinstance(l, dict) and ("start" in l or "end" in l):
            names = [s["name"] for s in sts]
            try:
                i = names.index(l["start"]) if "start" in l else 0
                j = names.index(l["end"]) if "end" in l else len(sts) - 1
            except ValueError:
                i, j = 0, len(sts) - 1
            i, j = min(i, j), max(i, j)
            kms = kms[i:j + 1]
        total += max(kms) - min(kms) if kms else 0
    return total


def main():
    tt_dir = JSON_DIR / "timetable"
    labels = Counter()
    for fn in ("timetable_weekday.json", "timetable_holiday.json"):
        p = tt_dir / fn
        if not p.exists():
            print(f"⚠️  找不到 {p}（請先跑 convert_timetable.py）")
            continue
        for t in json.load(open(p, encoding="utf-8")):
            labels[t["type"]] += 1
    print(f"🎨 時刻表出現 {len(labels)} 種種別")

    system_color = dict(EXTRA_SYSTEM_COLOR)
    for key, name, vt, lines, btn in P + SYSTEM_ONLY_PRESETS:
        if key in SYSTEM_LABEL:
            system_color.setdefault(SYSTEM_LABEL[key], btn)

    train_color, fb = {}, 0
    for label, cnt in labels.most_common():
        g = group_of(label)
        if label in system_color:
            col = system_color[label]
        elif label in NAMED:
            col = NAMED[label]
        elif label in GENERIC:
            col = GENERIC[label]
        else:
            col = FALLBACK[fb % len(FALLBACK)]
            fb += 1
            print(f"   ・自動配色 {label}（{cnt} 班）")
        train_color.setdefault(g, {})[label] = col

    topo = json.load(open(JSON_DIR / "topology.json", encoding="utf-8"))
    seg_by_id = {s["id"]: s for s in topo["segments"]}
    presets = {}
    for key, name, vt, lines, btn in P:
        missing = [m for m in (l if isinstance(l, str) else l["id"] for l in lines)
                   if m not in seg_by_id]
        if missing:
            print(f"❌ preset {key} 引用不存在的 segment: {missing}")
            continue
        d = {"name": name, "lines": lines, "view_type": vt, "button_color": btn}
        if vt == "CIRCULAR":
            d["loopHeight"] = 1600
        # 時間軸伸縮比：LINEAR 視圖的 scaleY = 畫面高 / 總km，引擎令 scaleX = scaleY * ratio，
        # 故列車線斜率 ∝ 速度(km/分) / ratio，畫面可見時間 ∝ 總km / ratio。
        # 取 總km/120 讓短線也能看到約 3 小時；但上限 1.0（≈ 在來線典型速度 1 km/分）：
        # 否則長線（中央線 222km 曾為 1.85）只看得到 3 小時，普通車被拉成近乎水平的線。
        d["time_stretch_ratio"] = round(min(1.0, max(0.35, span_km(lines, seg_by_id) / 120)), 2)
        presets[key] = d

    setting = {
        "system_id": "JR_East",
        "system_name": "東日本旅客鉄道",
        "data_fetch_strategy": "WEEKEND_FILE",
        "calendar_type": "WEEKDAY_BITMAP",
        "time_stretch_ratio": 0.4,     # 全域預設；各 preset 依長度覆寫（見 span_km）
        "show_train_id": True,
        "timezone_offset": 9,
        "view_presets": presets,
        "train_color": train_color,
    }
    out = JSON_DIR / "setting.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(setting, f, ensure_ascii=False, indent=1)
    print(f"\n✅ {len(presets)} 個 view_preset、"
          f"{sum(len(v) for v in train_color.values())} 個種別顏色")
    print(f"📄 {out}")


if __name__ == "__main__":
    main()
