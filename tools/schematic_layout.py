"""示意路網圖排版（地鐵圖風格：水平/垂直長直線、同一條線站距一致）

用法：
    py tools/schematic_layout.py Taiwan/TRA

把示意座標寫回 json/stations_geo.json 的 "schematic"（{id: [x, y]}，y 向上）與 "schematic_bends"
（{"站A|站B": [[x, y], ...]}：兩站之間的轉角點，轉彎不必剛好落在車站上）。
tools/build_station_geo.py 產生座標後也會自動呼叫這裡。

兩種排法：
A. 有 json/schematic_spec.json → 照手寫版面排（仿 github.com/4960fh7/TRA 的做法）。
   版面以格點描述，y 向下（同螢幕）：
     {"lines": [
        {"route": [["north_main", "八堵", "樹林"]], "path": [[14, 0], [0, 0]]},   # 沿折線等距排站
        {"route": [["keelung", "八堵", "基隆"]], "dir": [0, -1], "step": 1}       # 支線：從已排好的首站直直伸出
     ]}
   route 為 [路段 id, 起站, 訖站] 的串接（站名或站 ID 皆可）；同一站被不同 line 排到不同位置會報錯。
B. 沒有版面檔 → 自動排出同樣風格的圖（建構式，不需求解器）：
   1. 交會站與端點為關鍵節點，其間的站串成「鏈」。
   2. 主環線：依地理位置找出路網最外圈的環，挑地理上最東北/西北/西南/東南的四站當角，排成矩形；
      每邊車站等距，矩形寬高比參考地理外形。沒有環的路網則把最長的路線沿地理主軸排成一直線。
   3. 「耳朵」：兩端都已排好、中間還沒排的路徑（如海線、成追線），從直線、L 形、ㄈ 形繞行中挑
      不碰撞、轉彎少、站距合理、且與地理上同一側的那條，車站沿折線等距排列。
   4. 支線：只有一端排好的鏈，從交會站直直伸出（撞到才轉一次彎），方向取最接近地理方向、每站 1 格。
   5. 不相連的子路網各自排好後，依地理位置由西到東並排。
"""
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SPACING = 1.0                  # 支線站距
MIN_GAP = 1.8                  # 不相鄰的線至少相距（站距），要留空間給站名
OFFSETS = [4, 6, 8, 11, 15]    # 耳朵 ㄈ 形繞行時外移距離的候選
ASPECT_KEEP = 0.6              # 主環矩形保留地理寬高比的程度（0 = 只看站數）
COMPONENT_GAP = 6.0            # 不相連子路網之間的間距

DIRS4 = [(1, 0), (0, 1), (-1, 0), (0, -1)]  # 東、北、西、南（y 向上）


def planar_km(geo):
    lons = [p[0] for p in geo.values()]
    lats = [p[1] for p in geo.values()]
    lon0, lat0 = sum(lons) / len(lons), sum(lats) / len(lats)
    k = math.cos(math.radians(lat0))
    return {sid: ((lon - lon0) * 111.32 * k, (lat - lat0) * 110.57) for sid, (lon, lat) in geo.items()}


def seg_dist(p1, p2, q1, q2):
    """兩線段最短距離（相交為 0）。"""
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    def pt_seg(p, a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = dx * dx + dy * dy
        t = 0 if L == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L))
        return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)

    d1, d2 = cross(q1, q2, p1), cross(q1, q2, p2)
    d3, d4 = cross(p1, p2, q1), cross(p1, p2, q2)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)) and d1 and d2 and d3 and d4:
        return 0.0
    return min(pt_seg(p1, q1, q2), pt_seg(p2, q1, q2), pt_seg(q1, p1, p2), pt_seg(q2, p1, p2))


def extract_chains(topology, pos):
    """車站圖 → 關鍵節點（交會站/端點）與其間的鏈。"""
    nbrs = defaultdict(set)
    for seg in topology["segments"]:
        ids = [s["id"] for s in seg["stations"]]
        for a, b in zip(ids, ids[1:]):
            if a != b:
                nbrs[a].add(b); nbrs[b].add(a)
    missing = [s for s in nbrs if s not in pos]
    if missing:
        raise ValueError(f"缺地理座標：{missing[:10]}")

    key = {v for v in nbrs if len(nbrs[v]) != 2}
    seen = set()
    for v in nbrs:  # 沒有任何交會站/端點的純環狀線，隨便挑一站當關鍵節點
        if v in seen:
            continue
        comp, stack = [], [v]
        seen.add(v)
        while stack:
            x = stack.pop(); comp.append(x)
            for y in nbrs[x]:
                if y not in seen:
                    seen.add(y); stack.append(y)
        if not key & set(comp):
            key.add(min(comp))

    chains, used = [], set()
    for k in sorted(key):
        for n in sorted(nbrs[k]):
            if (k, n) in used:
                continue
            chain = [k, n]
            used.update({(k, n), (n, k)})
            while chain[-1] not in key:
                cur, prev = chain[-1], chain[-2]
                nxt = next(x for x in nbrs[cur] if x != prev)
                used.update({(cur, nxt), (nxt, cur)})
                chain.append(nxt)
            chains.append(chain)
    return nbrs, key, chains


def layout(topology, geo, verbose=True):
    """自動排出「主環矩形 + 耳朵繞行 + 直線支線」的示意圖。回傳 (座標, 轉角)，y 向上。"""
    log = print if verbose else (lambda *a, **k: None)
    pos = planar_km(geo)
    nbrs, key, chains = extract_chains(topology, pos)
    C = [{"st": ch, "u": ch[0], "v": ch[-1], "L": len(ch) - 1} for ch in chains]
    log(f"   示意圖：{len(nbrs)} 站 → {len(key)} 個交會/端點、{len(C)} 條鏈")

    incident = defaultdict(list)
    for ci, c in enumerate(C):
        incident[c["u"]].append(ci)
        if c["v"] != c["u"]:
            incident[c["v"]].append(ci)

    def stations_of(ci, fwd):
        return C[ci]["st"] if fwd else C[ci]["st"][::-1]

    def area(points):
        return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1])) / 2

    # ---------- 子路網 ----------
    comps, seen = [], set()
    for ci in range(len(C)):
        if ci in seen:
            continue
        comp, stack = [], [ci]
        seen.add(ci)
        while stack:
            x = stack.pop(); comp.append(x)
            for n in (C[x]["u"], C[x]["v"]):
                for y in incident[n]:
                    if y not in seen:
                        seen.add(y); stack.append(y)
        comps.append(comp)

    def two_core(cis):
        alive = set(cis)
        while True:
            deg = defaultdict(int)
            for ci in alive:
                deg[C[ci]["u"]] += 1; deg[C[ci]["v"]] += 1
            drop = {ci for ci in alive if deg[C[ci]["u"]] == 1 or deg[C[ci]["v"]] == 1}
            if not drop:
                return alive
            alive -= drop

    def outer_cycle(core):
        """以地理位置描出所有面，取面積最大的（外圈），再從中取站數最多的簡單環。"""
        out = defaultdict(list)
        for ci in core:
            for fwd in (True, False):
                st = stations_of(ci, fwd)
                ang = math.atan2(pos[st[1]][1] - pos[st[0]][1], pos[st[1]][0] - pos[st[0]][0])
                out[st[0]].append((ang, ci, fwd))
        for n in out:
            out[n].sort()
        idx = {(ci, fwd): k for n in out for k, (_, ci, fwd) in enumerate(out[n])}

        def nxt(h):
            ci, fwd = h
            w = stations_of(ci, fwd)[-1]
            k = idx[(ci, not fwd)]
            _, c2, f2 = out[w][(k - 1) % len(out[w])]
            return (c2, f2)

        best, best_area, visited = None, -1, set()
        for start in idx:
            if start in visited:
                continue
            face, h = [], start
            while h not in visited:
                visited.add(h); face.append(h); h = nxt(h)
            pts = [pos[s] for ci, fwd in face for s in stations_of(ci, fwd)[:-1]]
            a = abs(area(pts))
            if a > best_area:
                best, best_area = face, a
        # 外圈可能經過橋接的鏈兩次，拆成簡單環後取站數最多的
        cycles, stack = [], []
        for h in best:
            start_node = stations_of(*h)[0]
            names = [stations_of(*x)[0] for x in stack]
            if start_node in names:
                k = names.index(start_node)
                cycles.append(stack[k:]); stack = stack[:k]
            stack.append(h)
        if stack:
            first = stations_of(*stack[0])[0]
            last = stations_of(*stack[-1])[-1]
            names = [stations_of(*x)[0] for x in stack]
            if last in names:
                cycles.append(stack[names.index(last):])
        return max(cycles, key=lambda cyc: sum(C[ci]["L"] for ci, _ in cyc))

    # ---------- 共用狀態 ----------
    coords, bends = {}, {}
    drawn = []         # 已畫的線段 (p, q)
    done = set()       # 已排好的鏈

    def lay_polyline(stations, pts):
        """車站沿折線 pts 等距排列（已排好的站不動），折線頂點記為轉角，並登記線段。"""
        clean = [pts[0]]
        for p in pts[1:]:
            if math.dist(p, clean[-1]) > 1e-9:
                clean.append(p)
        cum = [0.0]
        for a, b in zip(clean, clean[1:]):
            cum.append(cum[-1] + math.dist(a, b))
        n = len(stations) - 1

        def at(d):
            for k in range(len(clean) - 1):
                if d <= cum[k + 1] + 1e-9 or k == len(clean) - 2:
                    t = 0 if cum[k + 1] == cum[k] else (d - cum[k]) / (cum[k + 1] - cum[k])
                    (x1, y1), (x2, y2) = clean[k], clean[k + 1]
                    return (x1 + (x2 - x1) * t, y1 + (y2 - y1) * t)
            return clean[0]

        arcs = [cum[-1] * i / n for i in range(n + 1)]
        for sid, d in zip(stations, arcs):
            coords.setdefault(sid, at(d))
        for (a, da), (b, db) in zip(zip(stations, arcs), zip(stations[1:], arcs[1:])):
            inner = [clean[k] for k in range(1, len(clean) - 1) if da + 1e-9 < cum[k] < db - 1e-9]
            if inner:
                bends[f"{a}|{b}"] = [list(p) for p in inner]
        drawn.extend(zip(clean, clean[1:]))

    def collisions(pts, anchors):
        """候選折線與已畫線段的衝突數；只允許在 anchors（起訖站）上以不重疊的角度接上。"""
        hits = 0
        for p, q in zip(pts, pts[1:]):
            for a, b in drawn:
                if seg_dist(p, q, a, b) >= MIN_GAP:
                    continue
                shared = [s for s in anchors if min(math.dist(s, p), math.dist(s, q)) < 1e-9
                          and min(math.dist(s, a), math.dist(s, b)) < 1e-9]
                if shared:
                    s = shared[0]
                    o1 = q if math.dist(s, p) < 1e-9 else p
                    o2 = b if math.dist(s, a) < 1e-9 else a
                    v1 = (o1[0] - s[0], o1[1] - s[1]); v2 = (o2[0] - s[0], o2[1] - s[1])
                    n1, n2 = math.hypot(*v1), math.hypot(*v2)
                    if n1 and n2 and (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2) < 0.99:
                        # 只在接點相碰：再確認其餘部分沒有太近
                        if seg_dist(p, q, a, b) == 0 and _near_only_at(p, q, a, b, s):
                            continue
                hits += 1
        return hits

    def side_penalty(stations, pts, PA, PB):
        """耳朵在地理上位於 A–B 的哪一側，示意圖上也要在同一側。"""
        inner = stations[1:-1] or stations
        g = [sum(pos[s][i] for s in inner) / len(inner) for i in (0, 1)]
        gm = [(pos[stations[0]][i] + pos[stations[-1]][i]) / 2 for i in (0, 1)]
        vg = (g[0] - gm[0], g[1] - gm[1])
        segs = list(zip(pts, pts[1:]))
        tot = sum(math.dist(a, b) for a, b in segs) or 1
        c = [sum((a[i] + b[i]) / 2 * math.dist(a, b) for a, b in segs) / tot for i in (0, 1)]
        vs = (c[0] - (PA[0] + PB[0]) / 2, c[1] - (PA[1] + PB[1]) / 2)
        ng, ns = math.hypot(*vg), math.hypot(*vs)
        if ng < 1e-6 or ns < 1e-6:
            return 0.0
        return (1 - (vg[0] * vs[0] + vg[1] * vs[1]) / (ng * ns)) * 3

    def best_route(stations, cands, PA, PB):
        n = len(stations) - 1
        best, best_score = None, math.inf
        for pts in cands:
            length = sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
            if length < 1e-9:
                continue
            spacing = length / n
            score = (collisions(pts, [PA, PB]) * 100
                     + (len(pts) - 2) * 1.5
                     + max(0, 0.7 - spacing) * 20 + max(0, spacing - 2.5) * 2
                     + 0.02 * length
                     + side_penalty(stations, pts, PA, PB))
            if score < best_score:
                best, best_score = pts, score
        return best

    def route_ear(path):
        stations = []
        for ci, fwd in path:
            st = stations_of(ci, fwd)
            stations += st[1:] if stations else st
        PA, PB = coords[stations[0]], coords[stations[-1]]
        (xa, ya), (xb, yb) = PA, PB
        cands = []
        if stations[0] == stations[-1]:   # 掛在單一站上的環：畫成方框
            s = max(2.0, len(stations) / 4)
            for sx in (1, -1):
                for sy in (1, -1):
                    cands.append([PA, (xa + sx * s, ya), (xa + sx * s, ya + sy * s), (xa, ya + sy * s), PA])
        else:
            if abs(xa - xb) < 1e-9 or abs(ya - yb) < 1e-9:
                cands.append([PA, PB])
            cands += [[PA, (xb, ya), PB], [PA, (xa, yb), PB]]
            for d in OFFSETS:
                for X in (min(xa, xb) - d, max(xa, xb) + d):
                    cands.append([PA, (X, ya), (X, yb), PB])
                for Y in (min(ya, yb) - d, max(ya, yb) + d):
                    cands.append([PA, (xa, Y), (xb, Y), PB])
        lay_polyline(stations, best_route(stations, cands, PA, PB))
        done.update(ci for ci, _ in path)

    def route_branch(ci):
        c = C[ci]
        fwd = c["u"] in coords
        stations = stations_of(ci, fwd)
        PA = coords[stations[0]]
        n = len(stations) - 1
        gx, gy = (pos[stations[-1]][i] - pos[stations[0]][i] for i in (0, 1))
        best, best_score = None, math.inf
        for k1, (dx, dy) in enumerate(DIRS4):
            # 直線，或撞到時在第 2、3 站或一半處轉一次彎
            for k2, h in [(None, 0)] + [(k, h) for k in ((k1 + 1) % 4, (k1 + 3) % 4)
                                        for h in sorted({2, 3, max(1, n // 2)}) if h < n]:
                if k2 is None:
                    pts = [PA, (PA[0] + dx * n * SPACING, PA[1] + dy * n * SPACING)]
                else:
                    h *= SPACING
                    ex, ey = DIRS4[k2]
                    mid = (PA[0] + dx * h, PA[1] + dy * h)
                    pts = [PA, mid, (mid[0] + ex * (n * SPACING - h), mid[1] + ey * (n * SPACING - h))]
                vx, vy = pts[-1][0] - PA[0], pts[-1][1] - PA[1]
                cosv = (vx * gx + vy * gy) / ((math.hypot(vx, vy) * math.hypot(gx, gy)) or 1)
                score = collisions(pts, [PA]) * 100 + (len(pts) - 2) * 3 + (1 - cosv) * 2
                if score < best_score:
                    best, best_score = pts, score
        lay_polyline(stations, best)
        done.add(ci)

    def find_ear(cis):
        """耳朵：從已排好的站、只經過未排的站、走到另一個已排好的站的路徑。
        每對端點取最短的那條，再從中挑最長的先排：大的環先定型（如山線），小的連接線（如成追線）最後補。"""
        best = None
        for A in {n for ci in cis for n in (C[ci]["u"], C[ci]["v"]) if n in coords}:
            dist, prev, heap = {A: 0}, {}, [(0, A)]
            import heapq
            while heap:
                d, n = heapq.heappop(heap)
                if d > dist[n]:
                    continue
                if n != A and n in coords:
                    if best is None or d > best[0]:
                        path, x = [], n
                        while x != A:
                            path.append(prev[x]); x = path[-1][2]
                        best = (d, [(ci, fwd) for ci, fwd, _ in reversed(path)])
                    continue
                for ci in incident[n]:
                    if ci not in cis:
                        continue
                    for fwd in (True, False):
                        st = stations_of(ci, fwd)
                        if st[0] != n:
                            continue
                        m = st[-1]
                        if m == A and n == A and d == 0:      # 掛在 A 上的單鏈環
                            if best is None or C[ci]["L"] > best[0]:
                                best = (C[ci]["L"], [(ci, fwd)])
                            continue
                        nd = d + C[ci]["L"]
                        if (m not in coords or m != n) and nd < dist.get(m, math.inf):
                            dist[m] = nd; prev[m] = (ci, fwd, n)
                            heapq.heappush(heap, (nd, m))
        return best[1] if best else None

    # ---------- 逐個子路網排版 ----------
    placed_boxes = []
    for comp in sorted(comps, key=lambda cm: -sum(C[ci]["L"] for ci in cm)):
        before = set(coords)
        drawn_before = len(drawn)
        core = two_core(comp)
        if core:
            cyc = outer_cycle(core)
            seq = []
            for ci, fwd in cyc:
                seq += stations_of(ci, fwd)[:-1]
            if area([pos[s] for s in seq]) < 0:      # 統一逆時針
                cyc = [(ci, not fwd) for ci, fwd in reversed(cyc)]
                seq = []
                for ci, fwd in cyc:
                    seq += stations_of(ci, fwd)[:-1]
            N = len(seq)
            P = [pos[s] for s in seq]
            # 四個角取地理上最東北/西北/西南/東南的站；差不多遠時優先挑非交會站，
            # 角上的站兩個方向都被環線佔走，支線會沒地方伸出去
            span = math.dist(*[(f(p[0] for p in P), g(p[1] for p in P)) for f, g in ((min, min), (max, max))])

            def corner(score, stations):
                best = max(score(pos[s]) for s in stations)
                ok = [i for i, s in enumerate(stations) if score(pos[s]) >= best - 0.03 * span]
                plain = [i for i in ok if stations[i] not in key]
                return max(plain or ok, key=lambda i: score(pos[stations[i]]))

            ne = corner(lambda q: q[0] + q[1], seq)
            rot = seq[ne:] + seq[:ne]
            P = [pos[s] for s in rot]
            nw = corner(lambda q: -q[0] + q[1], rot)
            sw = corner(lambda q: -q[0] - q[1], rot)
            se = corner(lambda q: q[0] - q[1], rot)
            if not (0 < nw < sw < se < N):           # 角的順序不對（如細長的環）就均分四邊
                nw, sw, se = N // 4, N // 2, 3 * N // 4
            n_top, n_left, n_bot, n_right = nw, sw - nw, se - sw, N - se
            xs = [p[0] for p in P]; ys = [p[1] for p in P]
            r = max(max(xs) - min(xs), 1e-6) / max(max(ys) - min(ys), 1e-6)
            H = max(n_left, n_right, 1)
            W = max(n_top, n_bot, 1, H * r * ASPECT_KEEP)
            H = max(H, W / r * ASPECT_KEEP)
            corners = [(W, H), (0, H), (0, 0), (W, 0), (W, H)]
            bounds = [0, nw, sw, se, N]
            for side in range(4):
                (x1, y1), (x2, y2) = corners[side], corners[side + 1]
                cnt = bounds[side + 1] - bounds[side]
                for k in range(cnt):
                    t = k / cnt
                    coords[rot[bounds[side] + k]] = (x1 + (x2 - x1) * t, y1 + (y2 - y1) * t)
            ring = rot + rot[:1]
            drawn.extend(zip([coords[s] for s in ring], [coords[s] for s in ring[1:]]))
            done.update(ci for ci, _ in cyc)
        else:
            # 沒有環：最長的路線沿地理主軸排成一直線
            ends = [n for ci in comp for n in (C[ci]["u"], C[ci]["v"]) if len(nbrs[n]) == 1] or [C[comp[0]]["u"]]

            def farthest(src):
                dist, prev, stack = {src: 0}, {}, [src]
                while stack:
                    n = stack.pop()
                    for ci in incident[n]:
                        if ci not in comp:
                            continue
                        m = C[ci]["v"] if C[ci]["u"] == n else C[ci]["u"]
                        if m not in dist:
                            dist[m] = dist[n] + C[ci]["L"]; prev[m] = (ci, n); stack.append(m)
                far = max(dist, key=dist.get)
                path, x = [], far
                while x != src:
                    ci, p = prev[x]; path.append((ci, C[ci]["u"] == p)); x = p
                return far, path[::-1]

            a, _ = farthest(ends[0])
            _, path = farthest(a)
            stations = []
            for ci, fwd in path:
                st = stations_of(ci, fwd)
                stations += st[1:] if stations else st
            gx, gy = (pos[stations[-1]][i] - pos[stations[0]][i] for i in (0, 1))
            d = (1 if gx >= 0 else -1, 0) if abs(gx) >= abs(gy) else (0, 1 if gy >= 0 else -1)
            n = len(stations) - 1
            coords[stations[0]] = (0.0, 0.0)
            lay_polyline(stations, [(0.0, 0.0), (d[0] * n * SPACING, d[1] * n * SPACING)])
            done.update(ci for ci, _ in path)

        while True:
            rest = [ci for ci in comp if ci not in done]
            if not rest:
                break
            ear = find_ear(set(rest))
            if ear:
                route_ear(ear)
                continue
            frontier = [ci for ci in rest if C[ci]["u"] in coords or C[ci]["v"] in coords]
            route_branch(max(frontier, key=lambda ci: C[ci]["L"]))

        # 子路網依地理位置由西到東並排
        new = [s for s in coords if s not in before]
        bx = [coords[s][0] for s in new]; by = [coords[s][1] for s in new]
        if placed_boxes:
            gx = sum(pos[s][0] for s in new) / len(new)
            east = gx >= sum(b[4] for b in placed_boxes) / len(placed_boxes)
            edge = max(b[1] for b in placed_boxes) + COMPONENT_GAP - min(bx) if east \
                else min(b[0] for b in placed_boxes) - COMPONENT_GAP - max(bx)
            dy = sum(b[2] for b in placed_boxes) / len(placed_boxes) - min(by)
            for s in new:
                coords[s] = (coords[s][0] + edge, coords[s][1] + dy)
            for k in list(bends):
                a = k.split("|")[0]
                if a in new:
                    bends[k] = [[x + edge, y + dy] for x, y in bends[k]]
            for i in range(drawn_before, len(drawn)):
                (p1, p2) = drawn[i]
                drawn[i] = ((p1[0] + edge, p1[1] + dy), (p2[0] + edge, p2[1] + dy))
            bx = [coords[s][0] for s in new]; by = [coords[s][1] for s in new]
        placed_boxes.append((min(bx), max(bx), min(by), max(by), sum(pos[s][0] for s in new) / len(new)))

    minx = min(p[0] for p in coords.values()); miny = min(p[1] for p in coords.values())
    r = lambda p: [round(p[0] - minx, 3), round(p[1] - miny, 3)]
    return ({sid: r(p) for sid, p in coords.items()},
            {k: [r(p) for p in v] for k, v in bends.items()})


def _near_only_at(p, q, a, b, s):
    """兩線段在 s 相接時，離開 s 一小段後是否就分開（不是沿著同一條線走）。"""
    def along(u, v, t):
        o = v if math.dist(s, u) < 1e-9 else u
        L = math.dist(s, o) or 1
        return (s[0] + (o[0] - s[0]) * min(1, t / L), s[1] + (o[1] - s[1]) * min(1, t / L))
    return math.dist(along(p, q, MIN_GAP), along(a, b, MIN_GAP)) >= MIN_GAP * 0.7


def route_stations(topology, route):
    """[[路段 id, 起站, 訖站], ...] → 依序的車站 ID（相鄰路段的交會站只算一次）。"""
    ids = []
    for seg_id, a, b in route:
        seg = next((sg for sg in topology["segments"] if sg["id"] == seg_id), None)
        if seg is None:
            raise ValueError(f"找不到路段 {seg_id}")
        sts = seg["stations"]
        find = lambda key: next((i for i, st in enumerate(sts) if key in (st["id"], st["name"])), None)
        i, j = find(a), find(b)
        if i is None or j is None:
            raise ValueError(f"路段 {seg_id} 找不到 {a if i is None else b}")
        part = [st["id"] for st in (sts[i:j + 1] if i <= j else sts[j:i + 1][::-1])]
        ids += part[1:] if ids and ids[-1] == part[0] else part
    return ids


def layout_from_spec(topology, spec):
    """照手寫版面排站。回傳 (座標 {id: [x, y]} y 向上, 轉角 {"a|b": [[x, y], ...]})。"""
    pos, bends = {}, {}

    def place(sid, x, y, where):
        if sid in pos and math.dist(pos[sid], (x, y)) > 1e-6:
            raise ValueError(f"{where}：{sid} 已排在 {pos[sid]}，又被排到 {(x, y)}")
        pos[sid] = (x, y)

    default_step = spec.get("step", 1)
    for n, line in enumerate(spec["lines"]):
        ids = route_stations(topology, line["route"])
        where = f"lines[{n}]"
        if "path" in line:
            pts = [tuple(p) for p in line["path"]]
            cum = [0.0]
            for a, b in zip(pts, pts[1:]):
                cum.append(cum[-1] + math.dist(a, b))
            total = cum[-1]

            def at(d):
                for k in range(len(pts) - 1):
                    if d <= cum[k + 1] + 1e-9 or k == len(pts) - 2:
                        t = 0 if cum[k + 1] == cum[k] else (d - cum[k]) / (cum[k + 1] - cum[k])
                        (x1, y1), (x2, y2) = pts[k], pts[k + 1]
                        return x1 + (x2 - x1) * t, y1 + (y2 - y1) * t

            arcs = [total * i / (len(ids) - 1) for i in range(len(ids))]
            for sid, d in zip(ids, arcs):
                place(sid, *at(d), where)
            # 兩站之間經過的折線頂點 = 轉角
            for (a, da), (b, db) in zip(zip(ids, arcs), zip(ids[1:], arcs[1:])):
                inner = [pts[k] for k in range(1, len(pts) - 1) if da + 1e-9 < cum[k] < db - 1e-9]
                if inner:
                    bends[f"{a}|{b}"] = [list(p) for p in inner]
        else:
            if ids[0] not in pos:
                raise ValueError(f"{where}：支線起點 {ids[0]} 要先在前面的 line 排好")
            (x0, y0), (dx, dy), step = pos[ids[0]], line["dir"], line.get("step", default_step)
            for i, sid in enumerate(ids[1:], 1):
                place(sid, x0 + dx * step * i, y0 + dy * step * i, where)

    all_ids = {st["id"] for sg in topology["segments"] for st in sg["stations"]}
    missing = sorted(all_ids - pos.keys())
    if missing:
        print(f"   ⚠️ 版面沒排到的車站（路網圖上不畫）：{', '.join(missing)}")
    flip = lambda p: [round(p[0], 3), round(-p[1], 3)]
    return ({sid: flip(p) for sid, p in pos.items()},
            {k: [flip(p) for p in v] for k, v in bends.items()})


def build_schematic(json_dir, topology, geo):
    """有 schematic_spec.json 照版面排，否則自動排。回傳 (座標, 轉角)。"""
    spec_path = Path(json_dir) / "schematic_spec.json"
    if spec_path.exists():
        print(f"   示意圖：依 {spec_path.name} 排版")
        return layout_from_spec(topology, json.loads(spec_path.read_text(encoding="utf-8")))
    return layout(topology, geo)


def main():
    if len(sys.argv) < 2:
        print("用法：py tools/schematic_layout.py <國家>/<路線>")
        sys.exit(1)
    json_dir = ROOT / "data" / sys.argv[1] / "json"
    topology = json.loads((json_dir / "topology.json").read_text(encoding="utf-8"))
    geo_path = json_dir / "stations_geo.json"
    data = json.loads(geo_path.read_text(encoding="utf-8"))
    data["schematic"], data["schematic_bends"] = build_schematic(json_dir, topology, data["stations"])
    geo_path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"✅ 示意座標已寫入 {geo_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
