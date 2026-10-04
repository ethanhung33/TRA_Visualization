"""產生路網圖用的車站座標檔 json/stations_geo.json

用法：
    py tools/build_station_geo.py Taiwan/TRA
    py tools/build_station_geo.py Taiwan/HSR
    py tools/build_station_geo.py Japan/JR_East      # 日本各系統皆可（Wikidata）
    py tools/build_station_geo.py Japan/Hankyu Japan/Hanshin ...   # 可一次多個

座標放在獨立檔案而非 topology.json：topology 由各系統的 build_topology.py 重新產生時會被整份覆寫。
topology 裡有、但資料源缺座標的車站（如新站），依同路段前後兩站的里程比例內插。
前端讀不到 stations_geo.json 時不顯示「路網圖」按鈕。
"""
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
HEADERS = {"User-Agent": "Mozilla/5.0"}


def _fetch_tdx(url):
    """TDX 免註冊模式；每日額度有限，只打一次。"""
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    data = r.json()
    stations = data["Stations"] if isinstance(data, dict) else data
    return {
        s["StationID"]: (s["StationPosition"]["PositionLon"], s["StationPosition"]["PositionLat"])
        for s in stations
        if s.get("StationPosition")
    }


WIKIDATA = "https://query.wikidata.org/sparql"
WD_HEADERS = {"User-Agent": "TRA_Visualization station-geo (https://github.com/ethanhung33/TRA_Visualization)"}


_WD_CACHE = {}


def _wikidata(query):
    """同一次執行中相同的查詢只打一次（一次處理多個日本系統時，全日本車站清單只抓一次）。"""
    if query in _WD_CACHE:
        return _WD_CACHE[query]
    _WD_CACHE[query] = _wikidata_fetch(query)
    return _WD_CACHE[query]


def _wikidata_fetch(query):
    r = requests.get(WIKIDATA, params={"query": query, "format": "json"}, headers=WD_HEADERS, timeout=300)
    r.raise_for_status()
    out = []
    for row in r.json()["results"]["bindings"]:
        m = re.match(r"Point\(([-\d.eE]+) ([-\d.eE]+)\)", row["coord"]["value"])
        if m:
            out.append((row["label"]["value"], float(m[1]), float(m[2])))
    return out


def _norm_ja(name):
    """站名正規化：去掉「駅」與括號註記（如「大久保駅 (東京都)」），ヶ/ケ 視為相同。"""
    name = re.sub(r"[（(].*?[)）]", "", name).strip()
    name = re.sub(r"駅$", "", name)
    return name.replace("ヶ", "ケ").replace("ヵ", "ケ").replace("　", "").replace(" ", "")


def _fetch_wikidata_japan(topology):
    """Wikidata 的日本車站座標，依站名比對。

    同名車站很多（大久保、追分……），先定下唯一的，再讓同名的挑最靠近已定鄰站的那個，反覆到穩定。
    """
    cands = defaultdict(set)
    for label, lon, lat in _wikidata("""
        SELECT ?label ?coord WHERE {
          VALUES ?cls { wd:Q55488 wd:Q55678 wd:Q1793804 wd:Q4663385 wd:Q928830 wd:Q2175765 wd:Q1339195 }
          ?s wdt:P31 ?cls; wdt:P17 wd:Q17; wdt:P625 ?coord; rdfs:label ?label FILTER(lang(?label) = "ja")
        }"""):
        cands[_norm_ja(label)].add((lon, lat))

    names = {st["id"]: st["name"] for seg in topology["segments"] for st in seg["stations"]}
    # 不在車站類別裡的（大型轉乘站、BRT 化的區間等）改用站名直接查，不限類別；有「〇〇駅」就只用它
    lost = sorted({_norm_ja(n) for n in names.values() if _norm_ja(n) not in cands})
    _add_by_label(cands, lost)

    chosen, far = _resolve(topology, names, cands)
    if far:
        # 離所有鄰站都很遠：多半是只查到別處的同名站（如北海道的北浜）。不限類別再查一次同名站，
        # 從全部候選中挑最靠近鄰站的
        _add_by_label(cands, sorted({_norm_ja(names[s]) for s in far}), merge=True)
        chosen, far = _resolve(topology, names, cands)
    if far:
        print(f"   ⚠️ 座標離鄰站太遠、改用內插：{', '.join(names[s] for s in far)}")
    return {sid: c for sid, c in chosen.items() if sid not in far}


def _add_by_label(cands, lost, merge=False):
    """依站名查 Wikidata（不限類別）補候選；有「〇〇駅」標籤的優先。"""
    if lost:
        labels = " ".join(f'"{v}{suffix}"@ja' for n in lost for v in {n, n.replace("ケ", "ヶ")} for suffix in ("駅", ""))
        by_name = defaultdict(lambda: {"駅": set(), "": set()})
        for label, lon, lat in _wikidata(
                "SELECT ?label ?coord WHERE { VALUES ?label { %s } ?s rdfs:label ?label; wdt:P17 wd:Q17; wdt:P625 ?coord. }" % labels):
            by_name[_norm_ja(label)]["駅" if label.endswith("駅") else ""].add((lon, lat))
        for n, groups in by_name.items():
            found = groups["駅"] or groups[""]
            cands[n] = (cands[n] | found) if merge else found


def _resolve(topology, names, cands):
    """先定下唯一的，再讓同名的挑最靠近已定鄰站的那個，反覆到穩定。回傳 (選定座標, 離鄰站太遠的站)。"""
    nbrs = defaultdict(set)
    line_km = {}
    for seg in topology["segments"]:
        sts = seg["stations"]
        for a, b in zip(sts, sts[1:]):
            nbrs[a["id"]].add(b["id"]); nbrs[b["id"]].add(a["id"])
            line_km[(a["id"], b["id"])] = line_km[(b["id"], a["id"])] = abs(b["km"] - a["km"])

    options = {sid: sorted(cands.get(_norm_ja(n), ())) for sid, n in names.items()}
    chosen = {sid: opts[0] for sid, opts in options.items() if len(opts) == 1}
    pending = [sid for sid, opts in options.items() if len(opts) > 1]
    while pending:
        progress, rest = False, []
        for sid in pending:
            anchors = [chosen[n] for n in nbrs[sid] if n in chosen]
            if not anchors:
                rest.append(sid)
                continue
            chosen[sid] = min(options[sid], key=lambda c: sum(math.dist(c, a) for a in anchors))
            progress = True
        if not progress:
            # 一整段都是同名站、沒有任何已定的鄰站（如京阪的淀屋橋—北浜—天満橋，各有京阪、地下鐵兩筆，
            # 北浜在北海道也有一個）：取最靠近已定車站中位位置的候選，帶動其他站
            if chosen:
                xs = sorted(c[0] for c in chosen.values()); ys = sorted(c[1] for c in chosen.values())
                center = (xs[len(xs) // 2], ys[len(ys) // 2])
                chosen[rest[0]] = min(options[rest[0]], key=lambda c: math.dist(c, center))
            else:
                chosen[rest[0]] = options[rest[0]][0]
            rest = rest[1:]
        pending = rest

    # 跟每個鄰站的直線距離都遠超過營業里程的，多半是比對到別處的同名站（如偏了 16 km 的另一個「新宿」）
    def ground_km(p, q):
        k = math.cos(math.radians((p[1] + q[1]) / 2))
        return math.hypot((p[0] - q[0]) * 111.32 * k, (p[1] - q[1]) * 110.57)

    far = [sid for sid, c in chosen.items()
           if nbrs[sid] and all(n in chosen and ground_km(c, chosen[n]) > max(3 * line_km[(sid, n)], line_km[(sid, n)] + 8)
                                for n in nbrs[sid])]
    return chosen, far


SOURCES = {
    "Taiwan/TRA": ("TDX", lambda topo: _fetch_tdx("https://tdx.transportdata.tw/api/basic/v3/Rail/TRA/Station?%24format=JSON")),
    "Taiwan/HSR": ("TDX", lambda topo: _fetch_tdx("https://tdx.transportdata.tw/api/basic/v2/Rail/THSR/Station?%24format=JSON")),
}


def source_for(key):
    if key in SOURCES:
        return SOURCES[key]
    if key and key.startswith("Japan/"):
        return ("Wikidata", _fetch_wikidata_japan)
    return None


def interpolate_missing(topology, coords):
    """缺座標的車站：同一路段中往前、往後各找最近有座標的站，依里程比例內插。"""
    filled = {}
    for seg in topology["segments"]:
        sts = seg["stations"]
        for i, st in enumerate(sts):
            if st["id"] in coords or st["id"] in filled:
                continue
            prev = next((sts[j] for j in range(i - 1, -1, -1) if sts[j]["id"] in coords), None)
            nxt = next((sts[j] for j in range(i + 1, len(sts)) if sts[j]["id"] in coords), None)
            if prev and nxt and nxt["km"] != prev["km"]:
                r = (st["km"] - prev["km"]) / (nxt["km"] - prev["km"])
                (x1, y1), (x2, y2) = coords[prev["id"]], coords[nxt["id"]]
                filled[st["id"]] = (x1 + (x2 - x1) * r, y1 + (y2 - y1) * r)
            elif prev or nxt:
                filled[st["id"]] = coords[(prev or nxt)["id"]]
    return filled


def main():
    keys = sys.argv[1:]
    if not keys or not all(source_for(k) for k in keys):
        print(f"用法：py tools/build_station_geo.py <{'|'.join(SOURCES)}|Japan/<路線>> [...]")
        sys.exit(1)
    for key in keys:
        print(f"== {key}")
        build(key)


def build(key):

    json_dir = ROOT / "data" / key / "json"
    topology = json.loads((json_dir / "topology.json").read_text(encoding="utf-8"))
    source_name, fetch = source_for(key)
    source = fetch(topology)

    topo_ids = {st["id"] for seg in topology["segments"] for st in seg["stations"]}
    coords = {sid: source[sid] for sid in topo_ids if sid in source}
    filled = interpolate_missing(topology, coords)
    coords.update(filled)

    missing = sorted(topo_ids - coords.keys())
    out = {
        "source": source_name,
        "interpolated": sorted(filled),
        "stations": {sid: [round(lon, 5), round(lat, 5)] for sid, (lon, lat) in sorted(coords.items())},
    }
    from schematic_layout import build_schematic
    out["schematic"], out["schematic_bends"] = build_schematic(json_dir, topology, out["stations"])
    out_path = json_dir / "stations_geo.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print(f"✅ {out_path.relative_to(ROOT)}：{len(coords)}/{len(topo_ids)} 站")
    if filled:
        print(f"   依里程內插：{', '.join(sorted(filled))}")
    if missing:
        print(f"   ⚠️ 仍缺座標（路網圖上不畫）：{', '.join(missing)}")


if __name__ == "__main__":
    main()
