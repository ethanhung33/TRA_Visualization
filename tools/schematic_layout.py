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
B. 沒有版面檔 → 格點路由自動排版（仿 LOOM：Bast, Brosi & Storandt, "Metro Maps on Octilinear Grid Graphs"）：
   1. 交會站與端點為關鍵節點，其間的站串成「鏈」。
   2. 預排：以 stress majorization 讓交會站之間的距離正比於站數，並往地理位置拉
      （站密的都心自動撐開、偏遠長線收短，方位仍與地理一致）。
   3. 格點路由：長的線先排，每條線在格點上以 Dijkstra 找路，成本 = 步數 + 轉彎 + 斜線（很貴）；
      用過的格點與格邊不能再用，所以線不會疊在一起，斜線也不會在格子中央交叉。
      未定位的交會站可落在預排位置附近幾格內最划算的空格點。
   4. 車站沿各自的路徑等距排列，路徑的轉角記為 schematic_bends。
"""
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

STATIONS_PER_CELL = 2.0  # 一格約幾個站距（格子越粗，平行線間距越大、站名越不擠）
CELL = 2.0               # 輸出時一格的長度（站距單位），與 STATIONS_PER_CELL 一致則站距約為 1
PRELAYOUT_ITERS = 300    # 預排的迭代次數
GEO_ANCHOR = 0.15        # 預排時往地理位置拉的力道（0 = 只看站數，越大越像地理圖）
SNAP_RADIUS = 3          # 交會站可以偏離預排位置幾格
GRID_MARGIN = 12         # 格子在預排範圍外多留幾格可以繞路
W_MOVE = 1.0             # 交會站偏離預排位置，每格
DIAG_STEP = 1.414 + 3.0  # 斜走一格的成本（含斜線懲罰：盡量只用水平垂直）
BEND_COST = [0.0, 2.0, 4.0, 12.0]   # 轉 0/45/90/135 度的成本（180 度不准）
W_CROSS = 80.0           # 不得已穿過別條線的格點（交叉）
W_OVERLAP = 500.0        # 無路可走時與別條線共用格邊（重疊），最後手段
COMPONENT_GAP = 6.0      # 不相連子路網之間的間距


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
    """格點路由排版（仿 LOOM：Bast, Brosi & Storandt, "Metro Maps on Octilinear Grid Graphs"）。

    回傳 (座標 {id: [x, y]}, 轉角 {"a|b": [[x, y], ...]})，y 向上，單位約為一個站距。
    """
    log = print if verbose else (lambda *a, **k: None)
    pos = planar_km(geo)
    nbrs, key, chains = extract_chains(topology, pos)

    # 自成一圈的鏈（兩端是同一站）從中間切開，格點上的路徑才有起訖
    split = []
    for ch in chains:
        if ch[0] == ch[-1] and len(ch) > 3:
            mid = len(ch) // 2
            key.add(ch[mid])
            split += [ch[:mid + 1], ch[mid:]]
        else:
            split.append(ch)
    C = [{"st": ch, "u": ch[0], "v": ch[-1], "L": len(ch) - 1} for ch in split]
    log(f"   示意圖：{len(nbrs)} 站 → {len(key)} 個交會/端點、{len(C)} 條鏈")

    incident = defaultdict(list)
    for ci, c in enumerate(C):
        incident[c["u"]].append(ci); incident[c["v"]].append(ci)

    # ---------- 子路網 ----------
    comps, seen = [], set()
    for n0 in sorted(key):
        if n0 in seen:
            continue
        comp, stack = [], [n0]
        seen.add(n0)
        while stack:
            n = stack.pop(); comp.append(n)
            for ci in incident[n]:
                for m in (C[ci]["u"], C[ci]["v"]):
                    if m not in seen:
                        seen.add(m); stack.append(m)
        comps.append(comp)

    coords, bends = {}, {}
    boxes = []
    for comp in sorted(comps, key=lambda cm: -len(cm)):
        cset = set(comp)
        cis = sorted({ci for n in comp for ci in incident[n]})
        target = prelayout(comp, [C[ci] for ci in cis], pos)
        paths = route_on_grid(comp, cis, C, target, log)
        before = set(coords)
        for ci, path in paths.items():
            place_along(C[ci]["st"], [(x * CELL, y * CELL) for x, y in path], coords, bends)
        new = [s for s in coords if s not in before]
        # 子路網依地理位置由西到東並排
        bx = [coords[s][0] for s in new]; by = [coords[s][1] for s in new]
        gx = sum(pos[s][0] for s in new) / len(new)
        if boxes:
            east = gx >= sum(b[4] for b in boxes) / len(boxes)
            dx = (max(b[1] for b in boxes) + COMPONENT_GAP - min(bx)) if east else (min(b[0] for b in boxes) - COMPONENT_GAP - max(bx))
            dy = sum(b[2] for b in boxes) / len(boxes) - min(by)
            for s in new:
                coords[s] = (coords[s][0] + dx, coords[s][1] + dy)
            for k in list(bends):
                if k.split("|")[0] in new:
                    bends[k] = [[x + dx, y + dy] for x, y in bends[k]]
            bx = [coords[s][0] for s in new]; by = [coords[s][1] for s in new]
        boxes.append((min(bx), max(bx), min(by), max(by), gx))

    minx = min(p[0] for p in coords.values()); miny = min(p[1] for p in coords.values())
    r = lambda p: [round(p[0] - minx, 3), round(p[1] - miny, 3)]
    return ({sid: r(p) for sid, p in coords.items()},
            {k: [r(p) for p in v] for k, v in bends.items()})


def prelayout(nodes, chains, pos):
    """交會站預排：距離正比於站數（格數），並往地理位置拉。

    以 stress majorization（SMACOF）求解，額外加一項往「縮放後地理位置」的錨定：
    站密的都心會被撐開、偏遠長線收短，但整體方位仍跟地理一致。回傳 {node: (x, y)}（格）。
    """
    idx = {n: i for i, n in enumerate(nodes)}
    n = len(nodes)
    if n == 1:
        return {nodes[0]: (0.0, 0.0)}
    INF = math.inf
    adj = defaultdict(list)
    for c in chains:
        w = max(c["L"] / STATIONS_PER_CELL, 1.0)
        adj[c["u"]].append((c["v"], w)); adj[c["v"]].append((c["u"], w))
    import heapq
    D = []
    for s in nodes:
        dist = {s: 0.0}
        h = [(0.0, s)]
        while h:
            d, x = heapq.heappop(h)
            if d > dist[x]:
                continue
            for y, w in adj[x]:
                if d + w < dist.get(y, INF):
                    dist[y] = d + w; heapq.heappush(h, (d + w, y))
        D.append([dist.get(t, INF) for t in nodes])

    # 地理位置縮放到格數：取各鏈「格數 / 直線距離」的中位數
    ratios = sorted((max(c["L"] / STATIONS_PER_CELL, 1.0)) / max(math.dist(pos[c["u"]], pos[c["v"]]), 1e-3)
                    for c in chains if c["u"] != c["v"])
    f = ratios[len(ratios) // 2] if ratios else 1.0
    G = [(pos[t][0] * f, pos[t][1] * f) for t in nodes]
    X = [list(g) for g in G]
    for _ in range(PRELAYOUT_ITERS):
        for i in range(n):
            sx = sy = sw = 0.0
            xi, yi = X[i]
            for j in range(n):
                d = D[i][j]
                if i == j or d == INF:
                    continue
                w = 1.0 / (d * d)
                dx, dy = xi - X[j][0], yi - X[j][1]
                L = math.hypot(dx, dy) or 1e-6
                sx += w * (X[j][0] + d * dx / L)
                sy += w * (X[j][1] + d * dy / L)
                sw += w
            a = GEO_ANCHOR * sw / n if sw else 1.0
            X[i] = [(sx + a * G[i][0]) / (sw + a), (sy + a * G[i][1]) / (sw + a)]
    return {t: tuple(X[idx[t]]) for t in nodes}


DIRS8 = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]


def route_on_grid(nodes, cis, C, target, log):
    """在格點上逐條找路。用過的格點、格邊都不能再用，所以線不會重疊；斜線不能在格子中央交叉。

    回傳 {鏈 index: [格點 (x, y), ...]}（從 u 到 v）。
    """
    import heapq
    place = {}            # 交會站 → 格點
    used_nodes = set()    # 被路徑經過或被交會站佔用的格點
    used_edges = set()    # frozenset({p, q})
    xs = [p[0] for p in target.values()]; ys = [p[1] for p in target.values()]
    lo_x, hi_x = math.floor(min(xs)) - GRID_MARGIN, math.ceil(max(xs)) + GRID_MARGIN
    lo_y, hi_y = math.floor(min(ys)) - GRID_MARGIN, math.ceil(max(ys)) + GRID_MARGIN

    def candidates(node, radius=SNAP_RADIUS):
        """還沒定位的交會站可以落在預排位置附近的空格點，離越遠越貴。"""
        tx, ty = target[node]
        out = {}
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                p = (round(tx) + dx, round(ty) + dy)
                if p not in used_nodes:
                    out[p] = W_MOVE * math.dist(p, (tx, ty))
        return out

    def search(src, goals, level):
        """src 出發到 goals（{格點: 額外成本}）的最低成本路徑；狀態含最後一步方向以計算轉彎。
        level 0：不碰任何已用的格點/格邊；1：可穿過別條線（交叉）；2：連格邊都可共用（重疊，最後手段）。"""
        start = (src, 8)
        dist = {start: 0.0}
        prev = {}
        heap = [(0.0, 0, src, 8)]
        tie = 1
        while heap:
            g, _, p, d = heapq.heappop(heap)
            if d == -1:     # 抵達終點的虛擬狀態
                path = [p]
                s = prev[(p, -1)]
                while s != start:
                    path.append(s[0]); s = prev[s]
                path.append(src)
                return path[::-1], g
            if g > dist.get((p, d), math.inf):
                continue
            for m, (mx, my) in enumerate(DIRS8):
                q = (p[0] + mx, p[1] + my)
                if not (lo_x <= q[0] <= hi_x and lo_y <= q[1] <= hi_y):
                    continue
                e = frozenset((p, q))
                cost = 0.0
                if e in used_edges:
                    if level < 2:
                        continue
                    cost += W_OVERLAP
                diag = m % 2 == 1
                if diag and frozenset(((p[0] + mx, p[1]), (p[0], p[1] + my))) in used_edges:
                    if level < 2:
                        continue                  # 斜線不能在格子中央交叉
                    cost += W_CROSS
                cost += (DIAG_STEP if diag else 1.0)
                if d != 8:
                    t = min((m - d) % 8, (d - m) % 8)
                    if t == 4:
                        continue
                    cost += BEND_COST[t]
                is_goal = q in goals
                if q in used_nodes and not is_goal:
                    if level == 0 or (level == 1 and q in placed_pts):
                        continue
                    cost += W_CROSS                # 不得已才穿過別條線（交叉）
                ng = g + cost
                if is_goal:
                    gg = ng + goals[q]
                    if gg < dist.get((q, -1), math.inf):
                        dist[(q, -1)] = gg; prev[(q, -1)] = (p, d)
                        heapq.heappush(heap, (gg, tie, q, -1)); tie += 1
                    continue
                if ng < dist.get((q, m), math.inf):
                    dist[(q, m)] = ng; prev[(q, m)] = (p, d)
                    heapq.heappush(heap, (ng, tie, q, m)); tie += 1
        return None, math.inf

    def commit(path):
        for a, b in zip(path, path[1:]):
            used_edges.add(frozenset((a, b)))
        used_nodes.update(path)

    # 起點：連最多線的交會站，放在預排位置
    first = max(nodes, key=lambda n: (sum(1 for ci in cis if n in (C[ci]["u"], C[ci]["v"])), n))
    place[first] = (round(target[first][0]), round(target[first][1]))
    used_nodes.add(place[first])
    placed_pts = {place[first]}

    paths, todo, crossings, forced = {}, set(cis), 0, 0
    while todo:
        frontier = [ci for ci in todo if C[ci]["u"] in place or C[ci]["v"] in place]
        if not frontier:     # 理論上不會發生（同一子路網必然相連）
            n0 = next(C[ci]["u"] for ci in todo)
            place[n0] = (round(target[n0][0]), round(target[n0][1])); used_nodes.add(place[n0]); placed_pts.add(place[n0])
            continue
        # 從核心往外長：離起點近的線先排（站密的都心先拿到好位置，偏遠長線後排有的是空間）；
        # 距離相同時長的先排
        def order(c):
            m = C[c]["u"] if C[c]["u"] in place else C[c]["v"]
            return (math.dist(target[m], target[first]), -C[c]["L"], c)
        ci = min(frontier, key=order)
        c = C[ci]
        rev = c["u"] not in place
        a, b = (c["v"], c["u"]) if rev else (c["u"], c["v"])
        path = None
        for level in (0, 1, 2):
            goals = {place[b]: 0.0} if b in place else candidates(b, SNAP_RADIUS * (2 if level == 2 else 1))
            path, _ = search(place[a], goals, level)
            if path:
                break
        if level == 2:
            forced += 1
        if path is None:
            raise RuntimeError(f"格點上找不到路：{c['u']} → {c['v']}")
        crossings += sum(1 for p in path[1:-1] if p in used_nodes)
        if b not in place:
            place[b] = path[-1]
            placed_pts.add(path[-1])
        commit(path)
        paths[ci] = path[::-1] if rev else path
        todo.discard(ci)
    if crossings or forced:
        log(f"   ⚠️ 不得已的交叉 {crossings} 處、與別條線共用格邊的線 {forced} 條")
    return paths


def place_along(stations, pts, coords, bends):
    """車站沿折線等距排列；兩站之間經過的折線頂點記為轉角。"""
    clean = [pts[0]]
    for p in pts[1:]:
        if math.dist(p, clean[-1]) > 1e-9:
            clean.append(p)
    # 去掉共線的中間點，只留真正的轉角
    pts = [clean[0]]
    for k in range(1, len(clean) - 1):
        a, b, c = pts[-1], clean[k], clean[k + 1]
        if abs((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])) > 1e-9:
            pts.append(b)
    if len(clean) > 1:
        pts.append(clean[-1])
    cum = [0.0]
    for a, b in zip(pts, pts[1:]):
        cum.append(cum[-1] + math.dist(a, b))
    n = len(stations) - 1

    def at(d):
        for k in range(len(pts) - 1):
            if d <= cum[k + 1] + 1e-9 or k == len(pts) - 2:
                t = 0 if cum[k + 1] == cum[k] else (d - cum[k]) / (cum[k + 1] - cum[k])
                (x1, y1), (x2, y2) = pts[k], pts[k + 1]
                return (x1 + (x2 - x1) * t, y1 + (y2 - y1) * t)
        return pts[0]

    arcs = [cum[-1] * i / n for i in range(n + 1)]
    for sid, d in zip(stations, arcs):
        coords.setdefault(sid, at(d))
    for (a, da), (b, db) in zip(zip(stations, arcs), zip(stations[1:], arcs[1:])):
        inner = [pts[k] for k in range(1, len(pts) - 1) if da + 1e-9 < cum[k] < db - 1e-9]
        if inner:
            bends[f"{a}|{b}"] = [list(p) for p in inner]


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
