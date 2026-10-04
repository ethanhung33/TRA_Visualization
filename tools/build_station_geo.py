"""產生路網圖用的車站座標檔 json/stations_geo.json

用法：
    py tools/build_station_geo.py Taiwan/TRA
    py tools/build_station_geo.py Taiwan/HSR

座標放在獨立檔案而非 topology.json：topology 由各系統的 build_topology.py 重新產生時會被整份覆寫。
topology 裡有、但資料源缺座標的車站（如新站），依同路段前後兩站的里程比例內插。
前端讀不到 stations_geo.json 時不顯示「路網圖」按鈕。
"""
import json
import sys
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


SOURCES = {
    "Taiwan/TRA": ("TDX", lambda: _fetch_tdx("https://tdx.transportdata.tw/api/basic/v3/Rail/TRA/Station?%24format=JSON")),
    "Taiwan/HSR": ("TDX", lambda: _fetch_tdx("https://tdx.transportdata.tw/api/basic/v2/Rail/THSR/Station?%24format=JSON")),
}


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
    key = sys.argv[1] if len(sys.argv) > 1 else None
    if key not in SOURCES:
        print(f"用法：py tools/build_station_geo.py <{'|'.join(SOURCES)}>")
        sys.exit(1)

    json_dir = ROOT / "data" / key / "json"
    topology = json.loads((json_dir / "topology.json").read_text(encoding="utf-8"))
    source_name, fetch = SOURCES[key]
    source = fetch()

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
