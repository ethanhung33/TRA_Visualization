#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_system.py — 鐵路系統資料契約驗證器

驗證一個系統目錄 (data/<國家>/<系統>/) 的 JSON 是否符合前端 main.js 真正會讀取的格式。
這是讓 Claude 在無人監督下能「自我修正」的回饋來源：每產生一份資料就跑一次，
有 ERROR 就代表前端會壞，必須修；WARNING 代表可疑但前端仍可運作。

用法:
    py tools/validate_system.py data/Taiwan/TRA
    py tools/validate_system.py data/Japan/Nankai --timetable-sample 3

退出碼:  0 = 無 ERROR (可能有 warning)，1 = 有 ERROR，2 = 找不到檔案/無法解析
"""
import sys
import json
import argparse
import glob
import os
from pathlib import Path

# Windows 主控台預設 cp950，強制 UTF-8 以正確輸出中文與表情符號
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# main.js 真正接受的列舉值（依實際程式碼，非 CLAUDE.md 文件）
KNOWN_VIEW_TYPES = {"LINEAR", "CIRCULAR"}
KNOWN_CALENDAR_TYPES = {"WEEKDAY_BITMAP", "SERVICE_GROUP", "WEEKEND_SELECT"}
KNOWN_FETCH_STRATEGIES = {"DAILY_FILE", "WEEKEND_FILE", "WEEKDAY_WEEKEND_FILE", "SINGLE_FILE"}
KNOWN_V_TYPES = {0, 1, 2, 3}  # 0=START 1=STOP 2=PASS 3=END

errors = []
warnings = []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def is_hex_color(s):
    return isinstance(s, str) and s.startswith("#") and len(s) in (4, 7)


def load_json(path, label):
    if not path.exists():
        err(f"[{label}] 檔案不存在: {path}")
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        err(f"[{label}] JSON 解析失敗 ({path.name}): {e}")
        return None


def flatten_train_colors(train_color):
    """train_color 可能是扁平 {type: [c1,c2]} 或巢狀 {group: {subtype: [c1,c2]}}（日本線）。
    回傳所有合法的列車種別 key 集合。"""
    keys = set()
    if not isinstance(train_color, dict):
        return keys
    for k, v in train_color.items():
        if isinstance(v, list):
            keys.add(k)
        elif isinstance(v, dict):
            keys.update(v.keys())
    return keys


def validate_topology(topo):
    """回傳 (seg_id -> set(station_id)), (all_station_ids), (seg_id -> {name->id})"""
    seg_stations = {}
    all_station_ids = set()
    seg_name_to_id = {}
    if not isinstance(topo, dict):
        err("[topology] 根節點必須是 object")
        return seg_stations, all_station_ids, seg_name_to_id
    if "operator_id" not in topo:
        warn("[topology] 缺少 operator_id")
    segs = topo.get("segments")
    if not isinstance(segs, list) or not segs:
        err("[topology] segments 必須是非空陣列")
        return seg_stations, all_station_ids, seg_name_to_id

    seen_seg_ids = set()
    for i, seg in enumerate(segs):
        sid = seg.get("id")
        if not sid:
            err(f"[topology] segments[{i}] 缺少 id")
            continue
        if sid in seen_seg_ids:
            err(f"[topology] segment id 重複: {sid}")
        seen_seg_ids.add(sid)
        if not seg.get("name"):
            warn(f"[topology] segment '{sid}' 缺少 name")
        stations = seg.get("stations")
        if not isinstance(stations, list) or not stations:
            err(f"[topology] segment '{sid}' 的 stations 必須是非空陣列")
            continue
        seg_stations[sid] = set()
        seg_name_to_id.setdefault(sid, {})
        last_km = None
        for j, st in enumerate(stations):
            st_id = st.get("id")
            st_name = st.get("name")
            km = st.get("km")
            if st_id is None:
                err(f"[topology] segment '{sid}' stations[{j}] 缺少 id")
                continue
            st_id = str(st_id)
            if not st_name:
                warn(f"[topology] segment '{sid}' 車站 {st_id} 缺少 name")
            if not isinstance(km, (int, float)):
                err(f"[topology] segment '{sid}' 車站 {st_id}({st_name}) 的 km 必須是數字，實際為 {km!r}")
            else:
                if last_km is not None and km < last_km:
                    warn(f"[topology] segment '{sid}' 里程非遞增: {st_name} km={km} < 前站 {last_km}（若刻意反向可忽略）")
                last_km = km
            seg_stations[sid].add(st_id)
            all_station_ids.add(st_id)
            if st_name:
                seg_name_to_id[sid][st_name] = st_id
    return seg_stations, all_station_ids, seg_name_to_id


def validate_setting(setting, seg_stations, seg_name_to_id):
    if not isinstance(setting, dict):
        err("[setting] 根節點必須是 object")
        return set()
    for req in ("system_id", "system_name"):
        if not setting.get(req):
            err(f"[setting] 缺少必要欄位 {req}")

    cal = setting.get("calendar_type")
    if cal and cal not in KNOWN_CALENDAR_TYPES:
        warn(f"[setting] calendar_type '{cal}' 不在已知集合 {KNOWN_CALENDAR_TYPES}（前端可能無法篩選班次）")
    fetch = setting.get("data_fetch_strategy")
    if fetch and fetch not in KNOWN_FETCH_STRATEGIES:
        warn(f"[setting] data_fetch_strategy '{fetch}' 不在已知集合 {KNOWN_FETCH_STRATEGIES}")
    if not isinstance(setting.get("timezone_offset"), (int, float)):
        warn("[setting] timezone_offset 缺少或非數字")

    presets = setting.get("view_presets")
    if not isinstance(presets, dict) or not presets:
        # HSR 沒有 view_presets（單線），允許但提醒
        warn("[setting] 沒有 view_presets（單線系統可接受，否則前端無路線可選）")
    else:
        for key, p in presets.items():
            if not p.get("name"):
                warn(f"[setting] view_preset '{key}' 缺少 name")
            vt = p.get("view_type")
            if vt not in KNOWN_VIEW_TYPES:
                err(f"[setting] view_preset '{key}' view_type '{vt}' 必須是 {KNOWN_VIEW_TYPES}")
            bc = p.get("button_color")
            if not (isinstance(bc, list) and len(bc) == 2 and all(is_hex_color(c) for c in bc)):
                warn(f"[setting] view_preset '{key}' button_color 應為兩個 hex 顏色，實際 {bc!r}")
            lines = p.get("lines")
            if not isinstance(lines, list) or not lines:
                err(f"[setting] view_preset '{key}' lines 必須是非空陣列")
                continue
            for ln in lines:
                if isinstance(ln, str):
                    if ln not in seg_stations:
                        err(f"[setting] view_preset '{key}' 引用不存在的 segment '{ln}'")
                elif isinstance(ln, dict):
                    lid = ln.get("id")
                    if lid not in seg_stations:
                        err(f"[setting] view_preset '{key}' 引用不存在的 segment '{lid}'")
                        continue
                    for endpoint in ("start", "end"):
                        nm = ln.get(endpoint)
                        if nm and nm not in seg_name_to_id.get(lid, {}):
                            err(f"[setting] view_preset '{key}' 的 {endpoint}='{nm}' 不是 segment '{lid}' 上的車站名")
                else:
                    err(f"[setting] view_preset '{key}' lines 含非法項目 {ln!r}")

    tc = setting.get("train_color")
    if not isinstance(tc, dict) or not tc:
        warn("[setting] 缺少 train_color（列車將以預設色繪製）")
    return flatten_train_colors(tc or {})


def validate_timetable_file(path, seg_stations, all_station_ids, color_keys, served=None):
    data = load_json(path, "timetable")
    if data is None:
        return 0
    if not isinstance(data, list):
        err(f"[timetable] {path.name} 根節點必須是陣列")
        return 0
    n_trains = 0
    unknown_stations = {}  # station_id -> 出現次數（聚合，避免洗版）
    unknown_segments = {}  # seg_id -> 出現次數
    missing_color_types = set()
    for idx, train in enumerate(data):
        n_trains += 1
        tno = train.get("no", train.get("train_no", train.get("id")))
        if tno is None:
            err(f"[timetable] {path.name} 第 {idx} 班缺少 no/train_no/id")
        ttype = train.get("type")
        if ttype is not None and color_keys and ttype not in color_keys:
            missing_color_types.add(ttype)
        segs = train.get("segments")
        if not isinstance(segs, list) or not segs:
            err(f"[timetable] {path.name} 車次 {tno} segments 必須是非空陣列")
            continue
        for seg in segs:
            seg_id = seg.get("id")
            if seg_id not in seg_stations:
                unknown_segments[seg_id] = unknown_segments.get(seg_id, 0) + 1
            s = seg.get("s")
            t = seg.get("t")
            v = seg.get("v")
            if not (isinstance(s, list) and isinstance(t, list) and isinstance(v, list)):
                err(f"[timetable] {path.name} 車次 {tno} segment '{seg_id}' 的 s/t/v 必須都是陣列")
                continue
            if len(t) != 2 * len(s):
                err(f"[timetable] {path.name} 車次 {tno} segment '{seg_id}': len(t)={len(t)} 必須等於 2*len(s)={2*len(s)}")
            if len(v) != len(s):
                err(f"[timetable] {path.name} 車次 {tno} segment '{seg_id}': len(v)={len(v)} 必須等於 len(s)={len(s)}")
            for st_id in s:
                if str(st_id) not in all_station_ids:
                    unknown_stations[str(st_id)] = unknown_stations.get(str(st_id), 0) + 1
                elif served is not None:
                    served.add(str(st_id))
            for vv in v:
                if vv not in KNOWN_V_TYPES:
                    err(f"[timetable] {path.name} 車次 {tno} segment '{seg_id}' 非法停靠類型 v={vv}（須為 {KNOWN_V_TYPES}）")

    # 聚合報告：未知 segment / 車站（前端 getProcessedSegments 會 return null 略過，不致命）與缺色車種
    if unknown_segments:
        detail = ", ".join(f"{sid}×{cnt}" for sid, cnt in
                           sorted(unknown_segments.items(), key=lambda x: -x[1])[:8])
        warn(f"[timetable] {path.name} 含 {len(unknown_segments)} 種拓樸外 segment（前端會略過該段不繪製）: {detail}")
    if unknown_stations:
        detail = ", ".join(f"{sid}×{cnt}" for sid, cnt in
                           sorted(unknown_stations.items(), key=lambda x: -x[1])[:8])
        warn(f"[timetable] {path.name} 含 {len(unknown_stations)} 種拓樸外車站（前端會略過該停靠點）: {detail}")
    if missing_color_types:
        warn(f"[timetable] {path.name} 有 {len(missing_color_types)} 種列車 type 在 train_color 無對應色: "
             f"{', '.join(sorted(missing_color_types))}")
    return n_trains


def main():
    ap = argparse.ArgumentParser(description="鐵路系統資料契約驗證器")
    ap.add_argument("system_dir", help="系統目錄，如 data/Taiwan/TRA")
    ap.add_argument("--timetable-sample", type=int, default=2,
                    help="抽查幾個 timetable 檔（0=全部，預設 2）")
    args = ap.parse_args()

    root = Path(args.system_dir)
    json_dir = root / "json"
    if not json_dir.exists():
        print(f"❌ 找不到 {json_dir}", file=sys.stderr)
        sys.exit(2)

    topo = load_json(json_dir / "topology.json", "topology")
    setting = load_json(json_dir / "setting.json", "setting")
    if topo is None or setting is None:
        _report()
        sys.exit(2 if errors else 1)

    seg_stations, all_station_ids, seg_name_to_id = validate_topology(topo)
    color_keys = validate_setting(setting, seg_stations, seg_name_to_id)

    tt_dir = json_dir / "timetable"
    tt_files = sorted(glob.glob(str(tt_dir / "*.json")))
    if not tt_files:
        warn("[timetable] 找不到任何 timetable 檔（若尚未爬取可忽略）")
    else:
        sample = tt_files if args.timetable_sample == 0 else tt_files[:args.timetable_sample]
        total_trains = 0
        served = set()  # 所有時刻表中有列車停靠的車站 id
        for f in sample:
            total_trains += validate_timetable_file(Path(f), seg_stations, all_station_ids,
                                                    color_keys, served)
        print(f"ℹ️  抽查 {len(sample)}/{len(tt_files)} 個時刻表檔，共 {total_trains} 班列車")

        # 全站覆蓋檢查：拓樸中每站都應至少有一班車停靠。
        # 僅在「檢查了全部時刻表檔」時才判定，否則抽查會誤報。
        if len(sample) == len(tt_files):
            unserved = all_station_ids - served
            if unserved:
                id_to_name = {st["id"]: st["name"]
                              for seg in topo["segments"] for st in seg["stations"]}
                listing = ", ".join(f"{id_to_name.get(i, '?')}({i})" for i in sorted(unserved))
                warn(f"[coverage] {len(unserved)} 個車站沒有任何列車停靠（可能是站名對照或爬取遺漏）: {listing}")
        else:
            print(f"ℹ️  （未做全站覆蓋檢查：僅抽查 {len(sample)}/{len(tt_files)} 檔，"
                  f"請加 --timetable-sample 0 檢查全站是否都有車停靠）")

    print(f"ℹ️  拓樸: {len(seg_stations)} 個 segment、{len(all_station_ids)} 個車站；"
          f"view_presets: {len(setting.get('view_presets', {}))} 個；"
          f"train_color: {len(color_keys)} 種列車")
    _report()
    sys.exit(1 if errors else 0)


def _report():
    print()
    for w in warnings:
        print(f"⚠️  WARNING {w}")
    for e in errors:
        print(f"❌ ERROR   {e}")
    print()
    if errors:
        print(f"❌ 驗證失敗：{len(errors)} 個 ERROR、{len(warnings)} 個 WARNING")
    elif warnings:
        print(f"✅ 通過（有 {len(warnings)} 個 WARNING 可檢視）")
    else:
        print("✅ 完美通過，無任何問題")


if __name__ == "__main__":
    main()
