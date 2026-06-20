#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
convert_timetable.py — 智頭急行 raw → 本專案「車次為中心」格式

入力：json/raw_weekday.json、json/raw_holiday.json
輸出：json/timetable/timetable_weekday.json、timetable_holiday.json

単一線（智頭線）。特急スーパーはくと/いなばは 上郡以西の JR 山陽本線（岡山・京都方面）と
智頭以北の JR 因美線/山陰本線（鳥取・倉吉方面）へ直通 → 拓樸外区間を is_other(JR西日本) に分離。
境界站（上郡 CZ01 / 智頭 CZ14）は智頭急行の station id で保存。
JR_West 系統が `data/Japan/Chizu_Express/` を is_other 参照しているため、本系統からの
逆方向リンク（→ data/Japan/JR_West/）も成立する。
"""
import sys
import json
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

JSON_DIR = Path(__file__).parent.parent / "json"

_JR_WEST = {"name": "JR西日本", "path": "data/Japan/JR_West/"}

# 特急の愛称判定（navitime は「特急」一括 → 直通 JR 端点で区別）
# スーパーいなば：岡山↔鳥取／スーパーはくと：京都・大阪↔鳥取・倉吉
_INABA_ANCHORS = {"岡山"}
_HAKUTO_ANCHORS = {"大阪", "京都", "新大阪", "三ノ宮", "姫路", "倉吉"}


def classify_express(segs):
    """特急の is_other(JR) 区間の駅名から愛称を推定。判定不能なら None。"""
    ext = set()
    for s in segs:
        if s.get("is_other"):
            for stid in s["s"]:
                if not str(stid).startswith("CZ"):
                    ext.add(stid)
    if ext & _INABA_ANCHORS:
        return "特急スーパーいなば"
    if ext & _HAKUTO_ANCHORS:
        return "特急スーパーはくと"
    return None


def load_station_info():
    with open(JSON_DIR / "topology.json", "r", encoding="utf-8") as f:
        topo = json.load(f)
    info = {}
    for seg in topo["segments"]:
        for st in seg["stations"]:
            info[st["name"]] = {"id": st["id"], "seg": seg["id"]}
    return info


def _make_other_seg(stops, STATION_INFO):
    """連続する外運営者（JR西日本）停車（端に境界站を含む）から is_other segment を生成。
    境界站（智頭急行拓樸内）は station id、外站は站名字串。"""
    n = len(stops)
    if n < 2:
        return None
    s = [STATION_INFO[st["name"]]["id"] if st["name"] in STATION_INFO else st["name"] for st in stops]
    t = [v for st in stops for v in (st["arr"], st["dep"])]
    v = [0] + [1] * (n - 2) + [3]
    return {"id": "jr_west", "s": s, "t": t, "v": v,
            "is_other": True, "system_name": _JR_WEST["name"], "system_path": _JR_WEST["path"]}


def process_train(raw, STATION_INFO):
    stops = raw["stops"]
    first = next((i for i, s in enumerate(stops) if s["name"] in STATION_INFO), None)
    if first is None:
        return None
    last = next((i for i in range(len(stops) - 1, -1, -1) if stops[i]["name"] in STATION_INFO), first)

    prefix = _make_other_seg(stops[:first + 1], STATION_INFO) if first > 0 else None
    suffix = _make_other_seg(stops[last:], STATION_INFO) if last < len(stops) - 1 else None

    # 智頭急行区間（単一 segment chizu_line）
    inner = [st for st in stops[first:last + 1] if st["name"] in STATION_INFO]
    if len(inner) < 2:
        # 全線通過（智頭急行内に 2 駅以上停まらない）→ 直通のみ。chizu segment は作れない。
        segs = []
        if prefix:
            segs.append(prefix)
        if suffix:
            segs.append(suffix)
        return segs if segs else None
    m = len(inner)
    s = [STATION_INFO[st["name"]]["id"] for st in inner]
    t = [v for st in inner for v in (st["arr"], st["dep"])]
    v = [0] + [1] * (m - 2) + [3]
    chizu = {"id": "chizu_line", "s": s, "t": t, "v": v}

    return ([prefix] if prefix else []) + [chizu] + ([suffix] if suffix else [])


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
            ttype = raw["type"]
            if ttype == "特急":
                ttype = classify_express(segs) or "特急"
            trains.append({"no": raw["code"], "type": ttype, "segments": segs})
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
