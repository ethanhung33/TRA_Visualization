#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
interpolate_passes.py — 在編譯後的時刻表中，沿拓樸實際路徑內插通過站 (v=2)

為什麼需要：時刻表只記「停靠站」，兩個相鄰停靠之間走哪條路要靠推斷。前端
`interpolatePassingStations()` 只在單一 segment 內、用 findIndex 找起訖站往下走，
遇到以下情況就會繞錯邊（列車線畫到反方向、甚至真正的停靠被丟掉）：
  - 環狀線：起站同時出現在段頭與段尾（山手線 東京 @0 / @34.5），findIndex 取到第一個
    → NEX 2235M 新宿→渋谷→東京 被畫成 渋谷→新宿→池袋→上野→東京。
  - 兩個相鄰停靠沒有共同 segment（特急長距離不停車、跨線直通）→ 前端只能畫直線。

作法（系統無關，只讀資料契約的通用欄位）：
  1. 由 topology 建圖：節點＝站 id，邊＝同一 segment 內相鄰兩站（權重＝里程差）。
  2. 每班車把「連續的本系統 segment」攤平成停靠序列（is_other 段是斷點，不跨越）。
  3. 相鄰停靠之間找路：
     - 兩站都在原派段內 → **只在該 segment 內**找最短路（保留各系統轉換腳本的派段
       決策；環狀線自然選較短的一側）。不可放寬成全圖最短路：並行複線的拓樸是近似的，
       全圖最短常會抄錯捷徑（NEX 渋谷→東京 會被抄成 中央線 代々木→四ツ谷）。
     - 否則（派段斷點）→ 全圖 Dijkstra，狀態 (站, segment)，換 segment 有懲罰。
  4. 沿路徑依里程比例內插通過時刻，依 segment 切回數段輸出；停靠 v 重算為
     段首 0 / 段中 1 / 段尾 3，原本就是通過站 (2) 者保持 2。

用法:
    py tools/interpolate_passes.py data/Japan/JR_East            # 就地改寫 timetable_*.json
    py tools/interpolate_passes.py data/Japan/JR_West --dry-run  # 只報告，不寫檔
亦可在轉換腳本中 `from interpolate_passes import PassInterpolator` 直接呼叫。
"""
import sys
import json
import heapq
import argparse
from pathlib import Path
from collections import defaultdict, Counter

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SWITCH_COST = 0.5      # 換 segment 的懲罰（km 當量）：避免在並行複線間來回跳
OFF_PREF_COST = 0.02   # 斷點找路時，走「非原派段」每條邊的額外成本（平手時的偏好）
MAX_SPEED_KMH = 200    # 跨段找路的隱含速度上限：超過代表實際路線不在拓樸內（多半經他社線，
                       # 如 花輪線 盛岡→IGR→好摩→大更），只剩離譜的繞遠路 → 放棄、原樣斷開


class PassInterpolator:
    def __init__(self, topology, max_speed_kmh=MAX_SPEED_KMH):
        self.max_speed = max_speed_kmh
        self.seg_ids = set()
        self.adj = defaultdict(list)          # node → [(nbr, seg, km)]
        self.node_segs = defaultdict(set)     # node → {seg}
        self.name = {}
        for seg in topology["segments"]:
            sid = seg["id"]
            self.seg_ids.add(sid)
            st = seg["stations"]
            for x in st:
                self.node_segs[x["id"]].add(sid)
                self.name.setdefault(x["id"], x.get("name", x["id"]))
            for a, b in zip(st, st[1:]):
                if a["id"] == b["id"]:
                    continue
                d = abs((b.get("km") or 0) - (a.get("km") or 0))
                self.adj[a["id"]].append((b["id"], sid, d))
                self.adj[b["id"]].append((a["id"], sid, d))
        self._cache = {}
        self.stats = Counter()
        self.unreachable = Counter()
        self.implausible = Counter()

    # ------------------------------------------------------------------ 找路
    def route(self, a, b, pref):
        """a→b 的路徑 [(node, seg_of_edge_into_node), ...]（不含 a）；找不到回 None。"""
        key = (a, b, pref)
        if key not in self._cache:
            path = None
            if pref in self.node_segs.get(a, ()) and pref in self.node_segs.get(b, ()):
                path = self._dijkstra(a, b, pref, only=pref)
                self.stats["same_seg"] += 1
            if path is None:
                path = self._dijkstra(a, b, pref, only=None)
                self.stats["cross_seg"] += 1
            self._cache[key] = path
        return self._cache[key]

    def _dijkstra(self, a, b, pref, only):
        dist = {}
        heap = []
        starts = [only] if only else sorted(self.node_segs.get(a, ()))
        for s in starts:
            dist[(a, s)] = 0.0
            heap.append((0.0, a, s, None))
        heapq.heapify(heap)
        prev = {}
        found = None
        while heap:
            d, n, s, _ = heapq.heappop(heap)
            if d > dist.get((n, s), float("inf")):
                continue
            if n == b:
                found = (n, s)
                break
            for nb, es, km in self.adj.get(n, ()):
                if only and es != only:
                    continue
                nd = d + km + (SWITCH_COST if es != s else 0) + (0 if es == pref else OFF_PREF_COST)
                if nd < dist.get((nb, es), float("inf")) - 1e-9:
                    dist[(nb, es)] = nd
                    prev[(nb, es)] = (n, s)
                    heapq.heappush(heap, (nd, nb, es, None))
        if not found:
            return None
        path = []
        cur = found
        while cur in prev:
            path.append(cur)
            cur = prev[cur]
        path.reverse()
        return path

    # ------------------------------------------------------------------ 單班車
    def process_train(self, train):
        # segment 清單不保證依行車順序（新幹線系統 8072C 新潟→東京 卻先列 THK_line），
        # 攤平前先依首個時刻排序；前端本就不依賴清單順序。
        def t_start(seg):
            ts = [x for x in seg.get("t", []) if x is not None]
            return ts[0] if ts else float("inf")
        segs = sorted(train.get("segments") or [], key=t_start)
        out, chunk = [], []
        for seg in segs:
            if seg.get("is_other") or seg.get("id") not in self.seg_ids:
                out.extend(self._rebuild(chunk, train))
                chunk = []
                out.append(seg)
            else:
                chunk.append(seg)
        out.extend(self._rebuild(chunk, train))
        train["segments"] = out

    def _rebuild(self, chunk, train):
        if not chunk:
            return []
        # 攤平：[(id, arr, dep, v, 原派段)]，段交界的重複站合併
        pts = []
        for seg in chunk:
            for i, sid in enumerate(seg["s"]):
                arr, dep = seg["t"][2 * i], seg["t"][2 * i + 1]
                v = seg["v"][i]
                if pts and pts[-1][0] == sid:
                    p = pts[-1]
                    pts[-1] = (sid, p[1], dep if dep is not None else p[2],
                               2 if (p[3] == 2 and v == 2) else (1 if v != 2 else p[3]), p[4])
                    continue
                pts.append((sid, arr, dep, v, seg["id"]))
        if len(pts) < 2:                  # 單點畫不出線（找不到路的孤立停靠）→ 捨棄
            return []
        # 每個點記錄「進入該點時的邊所屬 segment」；首點用原派段
        seq = [(pts[0][0], pts[0][1], pts[0][2], pts[0][3], pts[0][4])]
        for k in range(1, len(pts)):
            a, b = pts[k - 1], pts[k]
            pref = b[4]
            path = self.route(a[0], b[0], pref) if a[0] in self.adj and b[0] in self.adj else None
            if path is None:
                self.unreachable[(self.name.get(a[0], a[0]), self.name.get(b[0], b[0]))] += 1
                # 找不到路：在此斷開（沿用原資料，讓前端維持原行為）
                seq.append(("__BREAK__", None, None, None, None))
                seq.append(b)
                continue
            t0 = a[2] if a[2] is not None else a[1]
            t1 = b[1] if b[1] is not None else b[2]
            total = 0.0
            legs = []
            prev_n = a[0]
            for n, s in path:
                km = min(k_ for nb, es, k_ in self.adj[prev_n] if nb == n and es == s)
                total += km
                legs.append((n, s, total))
                prev_n = n
            cross = len({s for _, s in path}) > 1 or path[-1][1] != pref
            if cross and t0 is not None and t1 is not None and total > 0 and                     (t1 <= t0 or total / ((t1 - t0) / 60) > self.max_speed):
                self.implausible[(self.name.get(a[0], a[0]), self.name.get(b[0], b[0]))] += 1
                seq.append(("__BREAK__", None, None, None, None))
                seq.append(b)
                continue
            for n, s, cum in legs[:-1]:
                tp = t0 if (t0 is None or t1 is None or total <= 0) else \
                    round(t0 + (t1 - t0) * cum / total, 2)
                seq.append((n, tp, tp, 2, s))
                self.stats["pass_added"] += 1
            last_seg = legs[-1][1]
            seq.append((b[0], b[1], b[2], b[3], last_seg))
        # 依邊所屬 segment 切段（交界站同時出現在前後兩段）
        runs, cur = [], None
        for i, p in enumerate(seq):
            if p[0] == "__BREAK__":
                if cur:
                    runs.append(cur)
                cur = None
                continue
            if cur is None:
                cur = {"id": p[4], "pts": [p]}
                continue
            if p[4] != cur["id"]:
                runs.append(cur)
                cur = {"id": p[4], "pts": [cur["pts"][-1], p]}
            else:
                cur["pts"].append(p)
        if cur:
            runs.append(cur)
        result = []
        for r in runs:
            pts_ = r["pts"]
            if len(pts_) < 2:
                continue
            s, t, v = [], [], []
            for j, p in enumerate(pts_):
                s.append(p[0])
                t.extend([p[1], p[2]])
                if p[3] == 2:
                    v.append(2)
                else:
                    v.append(0 if j == 0 else (3 if j == len(pts_) - 1 else 1))
            result.append({"id": r["id"], "s": s, "t": t, "v": v})
        return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("system_dir")
    ap.add_argument("--dry-run", action="store_true", help="只報告，不寫檔")
    ap.add_argument("--max-speed", type=float, default=MAX_SPEED_KMH,
                    help="跨段找路的隱含速度上限 km/h（新幹線系統請調高）")
    args = ap.parse_args()
    root = Path(args.system_dir)
    topo = json.load(open(root / "json" / "topology.json", encoding="utf-8"))
    files = sorted((root / "json" / "timetable").glob("timetable_*.json"))
    for f in files:
        data = json.load(open(f, encoding="utf-8"))
        trains = data if isinstance(data, list) else data.get("trains", [])
        ip = PassInterpolator(topo, args.max_speed)
        before = sum(len(sg["s"]) for tr in trains for sg in tr.get("segments", []))
        for tr in trains:
            ip.process_train(tr)
        after = sum(len(sg["s"]) for tr in trains for sg in tr.get("segments", []))
        print(f"📄 {f.name}: {len(trains)} 班，站點 {before} → {after}"
              f"（+{ip.stats['pass_added']} 通過站）")
        for label, cnt in (("拓樸上無路可通", ip.unreachable),
                           (f"隱含速度 >{ip.max_speed}km/h（實際路線不在拓樸內）", ip.implausible)):
            if cnt:
                print(f"   ⚠️  {label}的相鄰停靠 {len(cnt)} 種（原樣斷開）：")
                for (a, b), c in cnt.most_common(10):
                    print(f"      {c:5d}  {a} → {b}")
        if not args.dry_run:
            with open(f, "w", encoding="utf-8") as fp:
                json.dump(data, fp, ensure_ascii=False)


if __name__ == "__main__":
    main()
