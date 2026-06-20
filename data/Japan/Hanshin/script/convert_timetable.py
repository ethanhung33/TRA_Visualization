#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
convert_timetable.py — 阪神電気鉄道 raw → 本專案「車次為中心」格式

入力：json/raw_weekday.json、json/raw_holiday.json
輸出：json/timetable/timetable_weekday.json、timetable_holiday.json

本線・なんば線・武庫川線は大物（HS08）・武庫川（HS12）で交會 → compile_train で切分。
直通先（近鉄・山陽電鉄・神戸高速鉄道）の駅は拓樸外 → prefix/suffix を運営者ごとに
is_other segment へ分離。境界站（阪神拓樸内の交接駅）は station id で保存。
"""
import sys
import json
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

JSON_DIR = Path(__file__).parent.parent / "json"

# ─── 直通先（外運営者）の駅セットと運営者定義 ──────────────────────────
_KINTETSU = {
    "近鉄日本橋", "大阪上本町", "鶴橋", "今里", "布施", "河内永和", "河内小阪",
    "八戸ノ里", "若江岩田", "河内花園", "東花園", "瓢箪山", "枚岡", "額田",
    "石切", "生駒", "東生駒", "富雄", "学園前", "菖蒲池", "大和西大寺",
    "新大宮", "近鉄奈良",
}
_KOBE_KOSOKU = {"西元町", "高速神戸", "新開地", "大開", "高速長田", "西代"}
# 近鉄・神戸高速 以外の拓樸外站はすべて山陽電鉄（地理的に神戸高速の西側のみ）

# op キー → (system_name, system_path|None)
_OPS = {
    "kintetsu":    ("近鉄",         "data/Japan/Kintetsu/"),
    "kobe_kosoku": ("神戸高速鉄道", None),
    "sanyo":       ("山陽電鉄",     None),
}
_OP_SEG_ID = {"kintetsu": "kintetsu", "kobe_kosoku": "kobe_kosoku", "sanyo": "sanyo"}


def _operator_of(name):
    if name in _KINTETSU:
        return "kintetsu"
    if name in _KOBE_KOSOKU:
        return "kobe_kosoku"
    return "sanyo"


# 交會站挿入用の補助マップ（load_station_info で構築）
SEG_STATION_IDS = {}   # seg_id -> set(station id)
ID_INFO = {}           # station id -> {name, segments:[...], km:{seg:km}}


def load_station_info():
    with open(JSON_DIR / "topology.json", "r", encoding="utf-8") as f:
        topo = json.load(f)
    info = {}
    SEG_STATION_IDS.clear(); ID_INFO.clear()
    for seg in topo["segments"]:
        sid = seg["id"]
        SEG_STATION_IDS[sid] = set()
        for st in seg["stations"]:
            name, stid, km = st["name"], st["id"], st["km"]
            if name not in info:
                info[name] = {"id": stid, "segments": [], "km": {}}
            info[name]["segments"].append(sid)
            info[name]["km"][sid] = km
            SEG_STATION_IDS[sid].add(stid)
            if stid not in ID_INFO:
                ID_INFO[stid] = {"name": name, "segments": [], "km": {}}
            ID_INFO[stid]["segments"].append(sid)
            ID_INFO[stid]["km"][sid] = km
    return info


def _find_junction(a, b):
    """隣接する 2 停靠 a,b が共通 segment を持たないとき、両者の segment を繋ぐ
    交會站（segA と segB の両方に属す駅）を探して (id, segA, segB) を返す。なければ None。"""
    for segA in a["segs"]:
        for segB in b["segs"]:
            if segA == segB:
                continue
            common = SEG_STATION_IDS.get(segA, set()) & SEG_STATION_IDS.get(segB, set())
            common.discard(a["id"]); common.discard(b["id"])
            if common:
                jid = next(iter(common))
                return jid, segA, segB
    return None


def compile_train(raw, STATION_INFO):
    """阪神拓樸内の stops を複数 segment に切り分ける（交會站で接続）。"""
    valid = []
    for st in raw["stops"]:
        name = st["name"]
        if name in STATION_INFO:
            si = STATION_INFO[name]
            valid.append({"id": si["id"], "arr": st["arr"], "dep": st["dep"],
                          "segs": list(si["segments"]), "km": dict(si["km"]),
                          "is_pass": False})
    if len(valid) < 2:
        return []

    # 交會站が停靠表に無いまま段が変わる場合（例：快速急行が大物を通過して
    # 出来島→尼崎）、隣接 2 站に共通 segment が無い → 交會站を「通過」として挿入。
    i = 0
    while i < len(valid) - 1:
        a, b = valid[i], valid[i + 1]
        if not (set(a["segs"]) & set(b["segs"])):
            j = _find_junction(a, b)
            if j:
                jid, segA, segB = j
                jinfo = ID_INFO[jid]
                kmA = abs(jinfo["km"][segA] - a["km"][segA]) if segA in a.get("km", {}) else None
                kmB = abs(b["km"][segB] - jinfo["km"][segB]) if segB in b.get("km", {}) else None
                if kmA is not None and kmB is not None and (kmA + kmB) > 0:
                    frac = kmA / (kmA + kmB)
                else:
                    frac = 0.5
                jt = int(round(a["dep"] + frac * (b["arr"] - a["dep"])))
                valid.insert(i + 1, {"id": jid, "arr": jt, "dep": jt,
                                     "segs": list(jinfo["segments"]),
                                     "km": dict(jinfo["km"]), "is_pass": True})
        i += 1

    for i in range(len(valid)):
        cur = valid[i]["segs"]
        if i < len(valid) - 1:
            nxt = valid[i + 1]["segs"]
            common = [s for s in cur if s in nxt]
            if common:
                valid[i]["true_seg"] = common[0]
                continue
        if i > 0:
            prev = valid[i - 1].get("true_seg")
            if prev and prev in cur:
                valid[i]["true_seg"] = prev
                continue
        valid[i]["true_seg"] = cur[0]

    compiled = []
    cur_seg = valid[0]["true_seg"]
    s_ids, t_times, v_types = [], [], []
    n = len(valid)

    def vtype(i):
        if valid[i].get("is_pass"):
            return 2
        if i == 0:
            return 0
        if i == n - 1:
            return 3
        return 1

    for i in range(n):
        st = valid[i]
        v = vtype(i)
        if st["true_seg"] != cur_seg and cur_seg in st["segs"]:
            s_ids.append(st["id"]); t_times.extend([st["arr"], st["dep"]]); v_types.append(v)
            if len(s_ids) > 1:
                compiled.append({"id": cur_seg, "s": s_ids, "t": t_times, "v": v_types})
            cur_seg = st["true_seg"]
            s_ids, t_times, v_types = [st["id"]], [st["arr"], st["dep"]], [v]
        else:
            if st["true_seg"] != cur_seg:
                cur_seg = st["true_seg"]
            s_ids.append(st["id"]); t_times.extend([st["arr"], st["dep"]]); v_types.append(v)

    if len(s_ids) > 1:
        compiled.append({"id": cur_seg, "s": s_ids, "t": t_times, "v": v_types})
    return compiled


def _seg_from(run, op, STATION_INFO):
    """同一運営者の連続 stops（端に境界站を含みうる）から is_other segment を生成。"""
    n = len(run)
    if n < 2:
        return None
    sys_name, sys_path = _OPS[op]
    s = [STATION_INFO[st["name"]]["id"] if st["name"] in STATION_INFO else st["name"] for st in run]
    t = [v for st in run for v in (st["arr"], st["dep"])]
    v = [0] + [1] * (n - 2) + [3]
    seg = {"id": _OP_SEG_ID[op], "s": s, "t": t, "v": v,
           "is_other": True, "system_name": sys_name}
    if sys_path:
        seg["system_path"] = sys_path
    return seg


def _split_external(stops, STATION_INFO):
    """外運営者の連続 stops（端に境界站を含む）を運営者ごとに分割して segments を返す。
    境界站（拓樸内）の運営者は隣接外站から継承。"""
    n = len(stops)
    if n < 2:
        return []
    ops = [None] * n
    for i, st in enumerate(stops):
        if st["name"] not in STATION_INFO:
            ops[i] = _operator_of(st["name"])
    for i in range(n):
        if ops[i] is None:  # 境界站 → 隣接運営者を継承
            ops[i] = (ops[i + 1] if i + 1 < n and ops[i + 1] else None) or \
                     (ops[i - 1] if i - 1 >= 0 and ops[i - 1] else None)
    segs = []
    i = 0
    while i < n:
        j = i
        while j + 1 < n and ops[j + 1] == ops[i]:
            j += 1
        seg = _seg_from(stops[i:j + 1], ops[i], STATION_INFO) if ops[i] else None
        if seg:
            segs.append(seg)
        i = j + 1
    return segs


def process_train(raw, STATION_INFO):
    """直通区間（近鉄/山陽/神戸高速）を is_other に分離し、阪神区間を compile_train に渡す。"""
    stops = raw["stops"]
    first = next((i for i, s in enumerate(stops) if s["name"] in STATION_INFO), None)
    if first is None:
        return []
    last = next((i for i in range(len(stops) - 1, -1, -1) if stops[i]["name"] in STATION_INFO), first)

    prefix_segs = _split_external(stops[:first + 1], STATION_INFO) if first > 0 else []
    suffix_segs = _split_external(stops[last:], STATION_INFO) if last < len(stops) - 1 else []

    compiled = compile_train({"stops": stops[first:last + 1]}, STATION_INFO)
    if not compiled:
        return []
    return prefix_segs + compiled + suffix_segs


def convert_file(raw_name, out_name, STATION_INFO):
    raw_path = JSON_DIR / raw_name
    if not raw_path.exists():
        print(f"⏭️  スキップ（{raw_name} が見つかりません）")
        return
    with open(raw_path, "r", encoding="utf-8") as f:
        raw_list = json.load(f)

    trains, skipped = [], 0
    for raw in raw_list:
        segs = process_train(raw, STATION_INFO)
        if segs:
            trains.append({"no": raw["code"], "type": raw["type"], "segments": segs})
        else:
            skipped += 1
    trains.sort(key=lambda x: x["segments"][0]["t"][0])

    out_dir = JSON_DIR / "timetable"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / out_name, "w", encoding="utf-8") as f:
        f.write("[\n")
        for i, tr in enumerate(trains):
            f.write(json.dumps(tr, ensure_ascii=False, separators=(",", ":")) +
                    (",\n" if i < len(trains) - 1 else "\n"))
        f.write("]\n")
    print(f"🎉 {raw_name} → {out_name}：{len(trains)} 班（略過 {skipped} 班不足）")


def main():
    STATION_INFO = load_station_info()
    convert_file("raw_weekday.json", "timetable_weekday.json", STATION_INFO)
    convert_file("raw_holiday.json", "timetable_holiday.json", STATION_INFO)


if __name__ == "__main__":
    main()
