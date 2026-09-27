#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
convert_timetable.py — 把 raw_timetable.json 轉成前端讀取的格式

輸入：json/raw_timetable.json（timetable.py 的產出）
輸出：json/timetable/timetable_weekday.json、timetable_holiday.json

核心是「派段」：把一班車的停靠序列切成 topology 的 segment。做法是走訪相鄰停靠對，
取兩站共同所屬的 segment，並貪婪地讓同一 segment 延伸到不能再延伸為止 —— 這樣
跨線直通車（如 湘南新宿ライン 走 東海道→山手貨物→東北）會自然被切成數個 segment，
且不會像「對每個 segment 取站名交集」那樣在並行複線上把同一班車重複輸出。

用法：
    py data/Japan/JR_East/script/convert_timetable.py
"""
import sys
import re
import json
import unicodedata
from pathlib import Path
from collections import defaultdict, Counter
from datetime import date

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent))
from station_name import clean_station_name   # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tools"))
from interpolate_passes import PassInterpolator   # noqa: E402
from build_setting import P, SYSTEM_ONLY_PRESETS, SYSTEM_LABEL, span_km   # noqa: E402

JSON_DIR = Path(__file__).parent.parent / "json"
OUT_DIR = JSON_DIR / "timetable"

# 新幹線已有獨立系統（東北・北海道・上越・北陸 / 東海道・山陽・九州），此處排除。
SKIP_TYPES = {"新幹線"}

# ==========================================================================
# 直通進入的他社路網。這些站不在本系統拓樸內，但不該直接丟掉：包成
# is_other segment，前端不畫在運行圖上，而是在底部資訊面板以該 operator 名列出。
# 依站名判斷 operator；未收錄者歸為「他社線」。
# ==========================================================================
OTHER_OPERATORS = {
    "相模鉄道": {
        "羽沢横浜国大", "西谷", "二俣川", "鶴ケ峰", "希望ケ丘", "三ツ境", "瀬谷",
        "相模大塚", "さがみ野", "かしわ台", "海老名", "星川", "天王町", "和田町",
        "上星川", "いずみ野", "いずみ中央", "ゆめが丘", "湘南台", "南万騎が原",
        "緑園都市", "弥生台", "西横浜", "平沼橋",
    },
    "東京臨海高速鉄道": {
        "品川シーサイド", "天王洲アイル", "東京テレポート", "国際展示場",
        "東雲", "新木場",
    },
    "仙台空港鉄道": {"杜せきのした", "美田園", "仙台空港"},
    # 常磐緩行線→千代田線、中央・総武緩行線→東西線 的直通
    "東京メトロ": {
        "北千住", "町屋", "千駄木", "根津", "湯島", "新御茶ノ水", "大手町",
        "二重橋前", "日比谷", "霞ケ関", "国会議事堂前", "赤坂", "乃木坂",
        "表参道", "明治神宮前", "代々木公園", "代々木上原",
        "落合", "高田馬場", "早稲田", "神楽坂", "九段下", "竹橋", "日本橋",
        "茅場町", "門前仲町", "木場", "東陽町", "南砂町", "葛西", "浦安",
        "南行徳", "行徳", "妙典", "原木中山",
    },
    "小田急電鉄": {
        "東北沢", "下北沢", "世田谷代田", "梅ヶ丘", "豪徳寺", "経堂",
        "千歳船橋", "祖師ヶ谷大蔵", "成城学園前", "喜多見", "和泉多摩川",
        "登戸", "向ヶ丘遊園", "生田", "読売ランド前", "百合ケ丘", "新百合ケ丘",
        "柿生", "鶴川", "玉川学園前", "町田", "相模大野", "小田急相模原",
        "本厚木", "伊勢原", "秦野", "新松田", "小田原",
    },
    "えちごトキめき鉄道": {
        "春日山", "高田", "南高田", "上越妙高", "北新井", "新井", "二本木",
        "関山", "妙高高原", "谷浜", "有間川", "名立", "筒石", "能生", "浦本",
    },
    "伊豆急行": {
        "南伊東", "川奈", "富戸", "城ケ崎海岸", "城ヶ崎海岸", "伊豆高原",
        "伊豆大川", "伊豆北川", "伊豆熱川", "片瀬白田", "今井浜海岸", "河津",
        "稲梓", "蓮台寺", "伊豆急下田",
    },
    "東武鉄道": {
        "下今市", "東武日光", "鬼怒川温泉", "新藤原", "新鹿沼", "板荷", "明神",
        "下小代", "大桑", "今市", "上今市", "栃木", "新大平下", "静和", "藤岡",
    },
    "富士山麓電気鉄道": {
        "富士山", "河口湖", "都留文科大学前", "三つ峠", "寿", "葭池温泉前",
        "下吉田", "月江寺", "富士急ハイランド", "田野倉", "禾生", "赤坂",
    },
    "IGRいわて銀河鉄道": {"厨川", "巣子", "滝沢", "渋民", "好摩", "岩手川口", "沼宮内"},
    "青い森鉄道": {"目時", "三戸", "諏訪ノ平", "剣吉", "苫米地", "北高岩", "八戸",
                  "陸奥市川", "小繋", "乙供", "上北町", "野辺地", "浅虫温泉"},
    "しなの鉄道": {"上田", "戸倉", "屋代", "坂城", "西上田", "信濃国分寺"},
    "北越急行": {"うらがわら", "大池いこいの森", "くびき", "犀潟"},
    "会津鉄道": {"西若松", "芦ノ牧温泉", "湯野上温泉", "会津田島"},
    "JR東海": {"三島", "沼津", "静岡", "浜松", "名古屋", "御殿場", "甲府", "富士"},
    "JR西日本": {"岡山", "京都", "新大阪", "大阪", "神戸", "新神戸", "高松", "出雲市",
                "米子", "松江", "糸魚川", "直江津"},
}
STATION_TO_OPERATOR = {st: op for op, sts in OTHER_OPERATORS.items() for st in sts}

# ==========================================================================
# 同名跨運營商的站 (AMBIGUOUS)：站名同時存在於本系統與他社。
# 例：りんかい線也有「大井町」，與 JR 京浜東北線的大井町不同站。埼京線直通
# りんかい線的車若把它當成 JR 大井町，就會與 大崎 形成假的派段斷點。
# 判準：該停靠的前後若出現該他社的專屬站，就視為他社的同名站。
#   {站名: (operator, 該 operator 的指標站集合)}
# ==========================================================================
AMBIGUOUS = {
    "大井町": ("東京臨海高速鉄道",
              {"品川シーサイド", "天王洲アイル", "東京テレポート",
               "国際展示場", "東雲", "新木場"}),
    # IGR 青山（盛岡旁）≠ 越後線 青山（新潟）。花輪線直通 IGR 的車曾把 盛岡↔青山
    # 誤認為本系統相鄰停靠，前端因而沿拓樸繞路 盛岡→…→新潟。
    "青山": ("IGRいわて銀河鉄道", {"厨川", "巣子", "滝沢", "渋民"}),
    # 相鉄 大和 ≠ 水戸線 大和；東葉高速 村上 ≠ 羽越本線 村上
    "大和": ("相模鉄道", {"瀬谷", "相模大塚", "さがみ野", "三ツ境", "鶴間"}),
    "村上": ("東葉高速鉄道", {"東葉勝田台", "八千代中央", "八千代緑が丘"}),
}


def resolve_ambiguous(stops):
    """把同名他社站標記為 _other，使其不被當成本系統拓樸站。"""
    names = [s["sta"] for s in stops]
    for i, s in enumerate(stops):
        info = AMBIGUOUS.get(s["sta"])
        if not info:
            continue
        op, markers = info
        neigh = set(names[max(0, i - 2):i + 3])
        if neigh & markers:
            s["_other_op"] = op

TODAY = date.today()


# ------------------------------------------------------------------ 運転日解析
def zen2han(s):
    return unicodedata.normalize("NFKC", s)


def parse_dates(text):
    """從『９月５日運転』『８月１５・１６日運転』等抓出 YYYY-MM-DD 清單。"""
    t = zen2han(text)
    out = []
    for m in re.finditer(r"(\d{1,2})月((?:\d{1,2}[・､、,]?)+)日", t):
        mon = int(m.group(1))
        for d in re.findall(r"\d{1,2}", m.group(2)):
            year = TODAY.year if mon >= TODAY.month else TODAY.year + 1
            try:
                out.append(date(year, mon, int(d)).isoformat())
            except ValueError:
                pass
    return sorted(set(out))


def classify_operation(opday):
    """回傳 (operation, dates)。operation ∈ daily/weekday/weekend/irregular。"""
    t = zen2han(opday or "").strip()
    if not t:
        return "daily", []
    has_dates = bool(re.search(r"\d{1,2}月\d{1,2}日", t))
    is_weekend = ("土曜" in t or "休日運転" in t)
    is_weekday = "平日" in t

    # 『土曜・休日運転９月５日は運休』→ 仍屬假日班，只是特定日運休（前端無此粒度，
    # 視為假日班）。『９月５日運転』→ 純特定日 → irregular。
    if has_dates and not (is_weekend or is_weekday):
        if "運休" in t:
            return "daily", []
        return "irregular", parse_dates(t)
    if is_weekend:
        return "weekend", []
    if is_weekday:
        return "weekday", []
    return "daily", []


# -------------------------------------------------------------------- 派段邏輯
def build_segment_index(topo):
    """station name → set(segment id)；segment id → {name: index}。"""
    name2segs = defaultdict(set)
    seg_order = {}
    for seg in topo["segments"]:
        idx = {}
        for i, st in enumerate(seg["stations"]):
            name2segs[st["name"]].add(seg["id"])
            idx[st["name"]] = i
        seg_order[seg["id"]] = idx
    return name2segs, seg_order


def find_gaps(stops, runs, name2id):
    """找出「相鄰停靠都在拓樸內、卻沒被任何 run 覆蓋」的斷點。

    這種洞很危險：前端會自行沿拓樸補出兩站之間的實體路徑，若兩站只在別處有共同
    路徑，就會把列車**繞錯邊**（實例：湘南新宿ライン 2860Y 因 武蔵小杉↔大崎 缺
    連絡段，被繞成 品川→東京→上野→池袋，真正停靠的 大崎/恵比寿/渋谷/新宿 全被丟掉）。
    回傳 [(前站, 後站), ...]。
    """
    covered = set()
    for _, sub in runs:
        for a, b in zip(sub, sub[1:]):
            covered.add((id(a), id(b)))
    gaps = []
    for a, b in zip(stops, stops[1:]):
        if (id(a), id(b)) in covered:
            continue
        if is_own(a, name2id) and is_own(b, name2id):
            gaps.append((a["sta"], b["sta"]))
    return gaps


def is_own(stop, name2id):
    """這個停靠是否算「本系統拓樸內的站」（他社同名站不算）。"""
    return stop["sta"] in name2id and not stop.get("_other_op")


def assign_segments(stops, name2segs, seg_order):
    """把停靠序列切成 [(segment_id, [stop, ...]), ...]。"""
    # 標記為他社同名站者不參與派段（見 AMBIGUOUS）
    cand = [set() if s.get("_other_op") else name2segs.get(s["sta"], set())
            for s in stops]
    runs = []
    i = 0
    n = len(stops)
    while i < n - 1:
        common = cand[i] & cand[i + 1]
        if not common:
            i += 1
            continue

        # 選能一路延伸最遠的 segment；平手時取兩站索引距離最小者（避免繞遠線）
        def reach(seg):
            j = i + 1
            while j + 1 < n and seg in cand[j + 1]:
                j += 1
            return j

        # 排序鍵：能延伸最遠 → 兩站索引距離最小（避免繞遠線）→ segment id。
        # 最後一項是為了**決定性**：common 是 set，迭代順序受字串 hash 隨機化影響，
        # 少了它會讓平手時的選擇每次執行都不同（曾造成 segment 有無列車忽上忽下）。
        best = max(sorted(common),
                   key=lambda s: (reach(s),
                                  -abs(seg_order[s][stops[i]["sta"]]
                                       - seg_order[s][stops[i + 1]["sta"]])))
        j = reach(best)
        runs.append((best, stops[i:j + 1]))
        i = j
    return runs


def other_segments(stops, name2id):
    """把「連續落在拓樸外」的停靠包成 is_other segment。

    依 skill 規範：段內真正的他社站用**站名字串**，但頭尾的境界站（同時屬於本系統
    拓樸的交接站，如 羽沢横浜国大 相鄰的 武蔵小杉）必須用**本系統的拓樸 id**，
    否則前端資訊面板會把境界站誤畫進他社框、與相鄰本系統段重複列出。
    """
    out = []
    n = len(stops)
    i = 0
    while i < n:
        if is_own(stops[i], name2id):
            i += 1
            continue
        j = i
        while j + 1 < n and not is_own(stops[j + 1], name2id):
            j += 1
        lo = i - 1 if i > 0 else i          # 含前境界站
        hi = j + 1 if j + 1 < n else j      # 含後境界站
        block = stops[lo:hi + 1]
        ops = Counter(s.get("_other_op") or STATION_TO_OPERATOR.get(s["sta"], "")
                      for s in block if not is_own(s, name2id))
        ops.pop("", None)
        op_name = ops.most_common(1)[0][0] if ops else "他社線"

        s_list, t_list, v_list = [], [], []
        for k, x in enumerate(block):
            # 境界站用本系統拓樸 id；真正的他社站（含同名站）用站名字串
            s_list.append((x.get("_sid") or name2id[x["sta"]])
                          if is_own(x, name2id) else x["sta"])
            t_list.extend([x["arr"], x["dep"]])
            v_list.append(0 if k == 0 else (3 if k == len(block) - 1 else 1))
        out.append({"id": f"other_{op_name}", "s": s_list, "t": t_list,
                    "v": v_list, "is_other": True, "system_name": op_name})
        i = j + 1
    return out


def uniquify_train_no(out):
    """JR 東日本的列車番号只在各支社內唯一，全系統撞號（441M 就有 福島→米沢、大月→長野、
    長岡→新潟…共 7 班）。前端以 `no` 為主鍵（選取、直通配對、搜尋），撞號會讓點 A 車、
    面板卻顯示 B 車。依引擎既有慣例（JR_West 同法）改成 `號碼|首站id`，`|` 之後只作
    唯一鍵、前端不顯示。仍撞者再加首站發車時刻、序號。coupled_with 的 train_id 一併回填。
    """
    groups = defaultdict(list)
    for item in out:
        groups[item["no"]].append(item)
    new_no = {}
    for no, items in groups.items():
        if len(items) == 1:
            new_no[items[0]["_rid"]] = no
            continue
        keys = {}
        for item in items:
            own = [sg for sg in item["segments"] if not sg.get("is_other")] or item["segments"]
            first = min(own, key=lambda sg: sg["t"][0] if sg["t"][0] is not None else 1e9)
            keys[item["_rid"]] = f"{no}|{first['s'][0]}"
        cnt = Counter(keys.values())
        for item in items:
            k = keys[item["_rid"]]
            if cnt[k] > 1:
                own = [sg for sg in item["segments"] if not sg.get("is_other")] or item["segments"]
                k = f"{k}_{int(min(sg['t'][0] for sg in own if sg['t'][0] is not None))}"
            keys[item["_rid"]] = k
        seen = Counter()
        for item in items:
            k = keys[item["_rid"]]
            seen[k] += 1
            new_no[item["_rid"]] = k if seen[k] == 1 else f"{k}_{seen[k]}"
    dropped = 0
    for item in out:
        item["no"] = new_no[item["_rid"]]
        if "coupled_with" not in item:
            continue
        kept = []
        for c in item["coupled_with"]:
            rid = c.pop("_partner")
            if rid in new_no:
                c["train_id"] = new_no[rid]
                kept.append(c)
            else:
                # 對象整班跑在他社線、未輸出：留著舊號碼會誤配到另一班同號的車
                dropped += 1
        if kept:
            item["coupled_with"] = kept
        else:
            del item["coupled_with"]
    for item in out:
        del item["_rid"]
    n = sum(1 for items in groups.values() if len(items) > 1)
    print(f"🔢 撞號 {n} 個列車番号 → 已改為 `號碼|首站id` 唯一鍵；"
          f"移除對象未輸出的配對 {dropped} 筆")


def build_system_sets(topo):
    """SYSTEM_LABEL 各 preset → (系統名, 站 id 集合, 總長 km)。"""
    seg_by_id = {s["id"]: s for s in topo["segments"]}
    out = []
    for key, name, vt, lines, btn in P + SYSTEM_ONLY_PRESETS:
        if key not in SYSTEM_LABEL:
            continue
        ids = set()
        for l in lines:
            sid = l if isinstance(l, str) else l["id"]
            sts = seg_by_id[sid]["stations"]
            names = [x["name"] for x in sts]
            i, j = 0, len(sts) - 1
            if isinstance(l, dict):
                i = names.index(l["start"]) if "start" in l else 0
                j = names.index(l["end"]) if "end" in l else len(sts) - 1
            i, j = min(i, j), max(i, j)
            ids.update(x["id"] for x in sts[i:j + 1])
        out.append((SYSTEM_LABEL[key], ids, span_km(lines, seg_by_id)))
    return out


def needs_system_label(futsu):
    """哪些普通車需要標系統名：只有「同一段路上普通車停站模式不同」處才需要。

    中央本線 大月–長野 的普通全都站站停，標「中央線」沒有資訊量；山手線視圖裡則同時有
    站站停的山手線/京浜東北線、與只停其中幾站的東海道線/宇都宮線普通，才需要區分。
    以「(站, segment)」為單位判定：M = 同一 segment 上有普通停、也有普通通過 (v=2) 的站。
    （不能只看站：秋葉原 在東北本線上被宇都宮線通過，但各駅停車停的是総武線上的秋葉原，
    兩者停站模式互不相干。）符合任一者即需標註：
      1. 停靠了 M 中的站（本身是站站停的那方：山手線停 有楽町）；
      2. 通過了 M 中的站（本身是跳站的那方：東海道線過 有楽町）；
      3. 相鄰兩停靠站的區間，與另一班「中間通過 M 站」的普通相同（高崎線 東京–上野
         走自己的 segment、資料上沒有通過站，但與宇都宮線跳過 神田/秋葉原/御徒町 的區間相同）。
    """
    def own_points(item):
        return [((x, sg["id"]), v) for sg in item["segments"] if not sg.get("is_other")
                for x, v in zip(sg["s"], sg["v"])]

    # 停、通過都要有一定份量才算（各至少 MIN_MIXED 班、且至少為另一方的 MIN_RATIO）：
    # 零星例外（武蔵野線 西浦和 約 480 班停、僅十餘班むさしの号 通過）不該讓整條線都被標註
    MIN_MIXED, MIN_RATIO = 10, 0.1
    stopped, passed = Counter(), Counter()
    for item in futsu:
        for x, v in own_points(item):
            (passed if v == 2 else stopped)[x] += 1
    M = {x for x in stopped
         if min(stopped[x], passed[x]) >= max(MIN_MIXED, MIN_RATIO * max(stopped[x], passed[x]))}

    skip_pairs = set()          # 中間通過 M 站的相鄰停靠對
    for item in futsu:
        pts = own_points(item)
        last, between = None, False
        for x, v in pts:
            if v == 2:
                between |= x in M
                continue
            if last is not None and last[0] != x[0] and between:
                skip_pairs.add(frozenset((last[0], x[0])))
            last, between = x, False

    need = set()
    for item in futsu:
        pts = own_points(item)
        if any(x in M for x, _ in pts):
            need.add(id(item))
            continue
        stops = [x[0] for x, v in pts if v != 2]
        if any(frozenset(p) in skip_pairs for p in zip(stops, stops[1:]) if p[0] != p[1]):
            need.add(id(item))
    return need


def classify_system(item, system_sets):
    """普通車所屬的運行系統名；判定不了回 None（維持「普通」）。

    1. 包含該車**全部**本系統停靠站的 preset 中，取總長最短者（最具體的系統）。
       例：山手線的車同時被 山手線(34.5km) 與 埼京線(大崎–池袋 經由新宿) 包含 → 山手線。
    2. 否則依路線判定跨系統直通：走 東北本線別線 → 埼京線；走 大崎支線/赤羽線 → 湘南新宿ライン。
    3. 否則取覆蓋率（停靠站落在該 preset 的比例）≥ 60% 者中最高的（平手取較短）：
       頭尾稍微超出系統範圍的直通車（横浜線 橋本→桜木町、常磐線 土浦→品川、
       上野東京ライン 前橋→国府津）。
    """
    own = [sg for sg in item["segments"] if not sg.get("is_other")]
    stops = {sid for sg in own for sid, v in zip(sg["s"], sg["v"]) if v != 2}
    if not stops:
        return None
    cands = [(km, label) for label, ids, km in system_sets if stops <= ids]
    if cands:
        return min(cands)[1]
    used = {sg["id"] for sg in own}
    if "tohoku_branch_saikyo" in used:
        return "埼京線"
    if used & {"osaki_hinkaku_branch", "akabane_line"}:
        return "湘南新宿ライン"
    best = max(((len(stops & ids) / len(stops), -km, label)
                for label, ids, km in system_sets), default=None)
    if best and best[0] >= 0.6:
        return best[2]
    return None


def main():
    topo = json.load(open(JSON_DIR / "topology.json", encoding="utf-8"))
    raw = json.load(open(JSON_DIR / "raw_timetable.json", encoding="utf-8"))
    # 再正規化一次（idempotent）：舊的 raw 檔可能是未套用異體字轉換前爬的，
    # 這樣不必為了「文挾→文挟」之類的修正重爬 19,000 頁。
    for t in raw:
        for s in t["stops"]:
            s["sta"] = clean_station_name(s["sta"])

    # 站名→id：同名異站（build_topology.py::HOMONYMS）在不同 segment 有不同 id，
    # 故派段後一律以「該 segment 內的站名→id」輸出；全域表只作「是否本系統站」判斷
    # 與境界站/配對站的後備（先出現者優先）。
    seg_name2id = {seg["id"]: {st["name"]: st["id"] for st in seg["stations"]}
                   for seg in topo["segments"]}
    name2id = {}
    for seg in topo["segments"]:
        for st in seg["stations"]:
            name2id.setdefault(st["name"], st["id"])
    name2segs, seg_order = build_segment_index(topo)

    print(f"📥 raw {len(raw)} 班次 / topology {len(topo['segments'])} segment "
          f"/ {len(name2id)} 站")

    # ---- 去重：同一班車可能出現在多個詳情頁（直通配對頁共用） ----
    seen, uniq = set(), []
    for t in raw:
        if t["type"] in SKIP_TYPES:
            continue
        st = t["stops"]
        key = (t["no"], st[0]["sta"], st[0]["dep"], st[-1]["sta"], t["type"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(t)
    print(f"🔁 去重後 {len(uniq)} 班次（排除新幹線 / 重複頁）")

    # ---- 直通配對：同頁相鄰欄位，前車某站標「直通」→ 與下一欄接續 ----
    by_page = defaultdict(dict)
    for t in uniq:
        by_page[t["url"]][t["col"]] = t
    couples = defaultdict(list)   # train key → [{train_id, station_id, action}]

    def link(a, b, sta, action):
        sid = name2id.get(sta, sta)
        # _partner：撞號改名（見 uniquify_train_no）後再回填成最終的 train_id
        couples[id(a)].append({"train_id": b["no"], "station_id": sid,
                               "action": action, "_partner": id(b)})
        couples[id(b)].append({"train_id": a["no"], "station_id": sid,
                               "action": action, "_partner": id(a)})

    n_direct = n_split = 0
    for cols in by_page.values():
        for c in sorted(cols):
            t, nxt = cols[c], cols.get(c + 1)
            if not nxt:
                continue

            # (1) 直通：頁面在某站印「直通」→ 與下一欄的車次無縫接續
            #     （如 相鉄直通 特急3120 → 普通120M）
            ds = next((s for s in t["stops"] if s.get("direct")), None)
            if ds:
                link(t, nxt, ds["sta"], "direct")
                n_direct += 1
                continue

            # (2) 併結分離：同一頁、**同一列車名**的兩欄，是同一實體列車在某站
            #     分割/併結的兩個編成（如 成田エクスプレス 50号 在東京分成
            #     大船行 2050M 與 新宿行 2250M）。頁面沒有「直通」標記，
            #     故以「共同停靠站且時刻相近」推斷交會站。
            #     少了這個連結，分割後的那一段看起來就像「憑空從東京發車」。
            if t.get("name") and t["name"] == nxt.get("name"):
                shared = [(a, b) for a in t["stops"] for b in nxt["stops"]
                          if a["sta"] == b["sta"]]
                if shared:
                    a, b = min(shared, key=lambda p: abs(p[0]["dep"] - p[1]["dep"]))
                    if abs(a["dep"] - b["dep"]) <= 15:
                        link(t, nxt, a["sta"], "split")
                        n_split += 1
    print(f"🔗 直通配對 {n_direct} 組、併結/分離配對 {n_split} 組")

    # ---- 轉換 ----
    out, stats = [], Counter()
    dropped_stations = Counter()
    gap_pairs = Counter()
    for t in uniq:
        stops = t["stops"]
        resolve_ambiguous(stops)
        runs = assign_segments(stops, name2segs, seg_order)
        if not runs:
            stats["no_segment"] += 1
            for s in stops:
                if s["sta"] not in name2id:
                    dropped_stations[s["sta"]] += 1
            continue

        segments = []
        for seg_id, sub in runs:
            s_list = [seg_name2id[seg_id][x["sta"]] for x in sub]
            for x, sid in zip(sub, s_list):
                x["_sid"] = sid           # 供 other_segments 的境界站沿用同一 id
            t_list = []
            for x in sub:
                t_list.extend([x["arr"], x["dep"]])
            v_list = [0 if k == 0 else (3 if k == len(sub) - 1 else 1)
                      for k in range(len(sub))]
            segments.append({"id": seg_id, "s": s_list, "t": t_list, "v": v_list})

        # 沒被任何 run 涵蓋的本系統停靠（多在列車首尾：むさしの号 北朝霞→大宮 的 大宮）
        # 以單點段交給 PassInterpolator 找路接上；找不到合理路徑時它會丟掉單點段，
        # 結果與修正前相同。
        covered = {id(x) for _, sub in runs for x in sub}
        for x in stops:
            if id(x) not in covered and is_own(x, name2id):
                sg = sorted(name2segs[x["sta"]])[0]
                segments.append({"id": sg, "s": [seg_name2id[sg][x["sta"]]],
                                 "t": [x["arr"], x["dep"]], "v": [1]})

        for g in find_gaps(stops, runs, name2id):
            gap_pairs[g] += 1

        segments.extend(other_segments(stops, name2id))

        for s in stops:
            if s["sta"] not in name2id:
                dropped_stations[s["sta"]] += 1

        op, dates = classify_operation(t["opday"])
        # 種別標籤：具名列車做成「種別＋愛称」（特急ひたち・快速アーバン），與 JR_West
        # 的 train_color 命名一致；号數（ひたち 3号）去掉以免每個号數各自一色。
        label = t["type"] or "普通"
        nm = re.sub(r"\s*\d+\s*号.*$", "", zen2han(t.get("name") or "")).strip()
        if nm and t["type"] in ("特急", "寝台特急", "快速", "急行", "特別快速"):
            label = f"{t['type']}{nm}"

        item = {"no": t["no"], "type": label, "operation": op,
                "segments": segments, "_rid": id(t)}
        if couples.get(id(t)):
            item["coupled_with"] = couples[id(t)]
        if op == "irregular":
            if not dates:
                op = item["operation"] = "daily"
            else:
                item["dates"] = dates
        out.append(item)
        stats[op] += 1

    # ---- 沿拓樸實際路徑內插通過站 (v=2) ----
    # 不補的話前端只能自己猜兩個停靠之間走哪條路，環狀線與派段斷點都會繞錯邊
    # （NEX 2235M 渋谷→東京 曾被畫成 新宿→池袋→上野 繞一大圈）。見 tools/interpolate_passes.py。
    ip = PassInterpolator(topo)
    for item in out:
        ip.process_train(item)

    # ---- 普通車細分運行系統（東京圈共用車站的 山手線/京浜東北線/東海道線…）----
    system_sets = build_system_sets(topo)
    futsu = [item for item in out if item["type"] == "普通"]
    need = needs_system_label(futsu)
    sys_count = Counter()
    for item in futsu:
        if id(item) not in need:
            continue
        label = classify_system(item, system_sets)
        if label:
            item["type"] = label
            sys_count[label] += 1
    print(f"🚉 普通車細分系統：{dict(sys_count.most_common())}"
          f"（其餘 {sum(1 for i in out if i['type'] == '普通')} 班維持「普通」）")
    print(f"🧭 內插通過站 {ip.stats['pass_added']} 個"
          f"（段內找路 {ip.stats['same_seg']} 種、跨段找路 {ip.stats['cross_seg']} 種）")
    if ip.unreachable:
        print(f"   ⚠️  拓樸上無路可通的相鄰停靠 {len(ip.unreachable)} 種（原樣斷開）")
    if ip.implausible:
        print(f"   ⚠️  隱含速度過高而放棄找路 {len(ip.implausible)} 種（多半實際經他社線，原樣斷開）："
              f"{[f'{a}→{b}' for a, b in ip.implausible]}")

    # ---- 列車番号撞號 → 唯一鍵 ----
    uniquify_train_no(out)

    # ---- 分流輸出 ----
    wd = [t for t in out if t["operation"] in ("daily", "weekday", "irregular")]
    hd = [t for t in out if t["operation"] in ("daily", "weekend", "irregular")]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for fname, data in (("timetable_weekday.json", wd),
                        ("timetable_holiday.json", hd)):
        with open(OUT_DIR / fname, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        print(f"📄 {fname}: {len(data)} 班次")

    print(f"\n📊 operation 分佈：{dict(stats)}")
    topo_ids = {s["id"] for s in topo["segments"]}
    seg_count = Counter(s["id"] for t in out for s in t["segments"])
    used = [i for i in seg_count if i in topo_ids]
    print(f"   有列車的 segment：{len(used)}/{len(topo_ids)}"
          f"（另有 {len(seg_count) - len(used)} 個他社 is_other 段）")
    empty = sorted(topo_ids - set(used))
    if empty:
        print(f"   ⚠️  無列車的 segment {len(empty)}：{empty}")
    if gap_pairs:
        # 斷點已由 PassInterpolator 以全圖最短路補上；列出實際採用的路徑供人工核對，
        # **與實際走法不符**時才需補連絡段（或修拓樸的假邊）。
        print(f"\n🔀 派段斷點 {len(gap_pairs)} 種（無共同 segment，中途斷點已沿拓樸最短路補通過站；位於列車首尾者該站仍被略過）：")
        for (a, b), c in gap_pairs.most_common():
            path = ip.route(name2id[a], name2id[b], None) or []
            via = []
            for _, sg in path:
                if not via or via[-1] != sg:
                    via.append(sg)
            print(f"     {c:6d}  {a} ↔ {b}  經 {' → '.join(via) or '（無路）'}")
    else:
        print("\n✅ 無派段斷點（所有相鄰停靠都落在同一 segment 內）")

    if dropped_stations:
        print(f"\n⚠️  拓樸外站（略過）共 {len(dropped_stations)} 種，前 20：")
        for n, c in dropped_stations.most_common(20):
            print(f"     {c:6d}  {n}")


if __name__ == "__main__":
    main()
