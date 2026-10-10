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
B. 沒有版面檔 → 約束圖排版（只用相對關係，不看地理距離；需要 scipy），見 layout() 的說明。
"""
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PORT_DIAG = 0.6          # 埠分配時用斜向的額外成本（弧度平方）：越大斜線越少
MIN_PIECE = 0.5          # 每段直線最短（站距）
REL_NEIGHBORS = 6        # 每個交會站與地理上最近的幾個交會站建立相對方位約束
REL_RATIO = 0.35         # 地理向量在某軸的分量佔多少以上，才在該軸加「左右／上下」約束
NODE_SEP = 1.5           # 相對方位約束的最小間距（站距）
SEG_SEP = 1.5            # 線段之間至少相隔（站距）
W_REL = 20.0             # 違反相對方位約束的成本（每站距）
W_SEP = 50.0             # 違反線段分離約束的成本（每站距）
W_SHAPE = 500.0          # 線段長度不足／反向（方向分配互相矛盾時才會發生）的成本
CG_ROUNDS = 10           # 交叉/重疊修正的最多重解次數
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
    """約束圖排版：只用「相對關係」決定座標，不用任何地理距離。

    1. 交會站與端點為關鍵節點，其間的站串成「鏈」。
    2. 埠分配：每個交會站把伸出的鏈分配到 8 個方向中互不相同的方向，並保持地理上的環繞順序
       （rotation system）——窮舉所有保序分配，取與地理出發方向偏差最小者（斜向另加成本）。
    3. 鏈的形狀由兩端的埠決定：同向為直線、差 45/90 度為 L 形、更大則加一段中間段成 ㄈ 形；
       轉角是自由點。
    4. 約束圖：形狀約束（水平段 y 相同、垂直段 x 相同、斜段 Δx = ±Δy、每條鏈總長 ≥ 站數），
       加上地理上相鄰交會站的相對方位（左右、上下）順序約束，以 LP 求總長最短的座標。
    5. 解出來若有線段交叉或重疊，依兩段在地理上的相對方位補上分開的約束後重解。
    回傳 (座標 {id: [x, y]}, 轉角 {"a|b": [[x, y], ...]})，y 向上，單位為站距。
    """
    from scipy.optimize import linprog
    from scipy.sparse import coo_matrix
    import numpy as np
    from itertools import combinations

    log = print if verbose else (lambda *a, **k: None)
    pos = planar_km(geo)
    nbrs, key, chains = extract_chains(topology, pos)
    split = []
    for ch in chains:                       # 自成一圈的鏈從中間切開
        if ch[0] == ch[-1] and len(ch) > 3:
            mid = len(ch) // 2
            key.add(ch[mid]); split += [ch[:mid + 1], ch[mid:]]
        else:
            split.append(ch)
    C = [{"st": ch, "u": ch[0], "v": ch[-1], "L": len(ch) - 1} for ch in split]
    log(f"   示意圖：{len(nbrs)} 站 → {len(key)} 個交會/端點、{len(C)} 條鏈")

    def geo_dir(node, ci):
        """鏈從 node 出發的地理方向（弧度）：取往鏈內約 1/3、至多 4 站處，避開站前的小彎。"""
        st = C[ci]["st"] if C[ci]["u"] == node else C[ci]["st"][::-1]
        far = st[max(1, min(4, len(st) // 3))]
        return math.atan2(pos[far][1] - pos[node][1], pos[far][0] - pos[node][0])

    # ---------- 1. 埠分配 ----------
    incident = defaultdict(list)            # node → [(鏈, 是否從 u 端)]
    for ci, c in enumerate(C):
        incident[c["u"]].append(ci)
        incident[c["v"]].append(ci)
    port = {}                               # (node, 鏈) → 0..7（0 = 東，逆時針每 45 度）

    def dev(angle, p):
        return abs((angle - p * math.pi / 4 + math.pi) % (2 * math.pi) - math.pi)

    for node, cis in incident.items():
        ends = sorted(cis, key=lambda ci: geo_dir(node, ci) % (2 * math.pi))
        angs = [geo_dir(node, ci) for ci in ends]
        k = len(ends)
        if k > 8:
            raise ValueError(f"{node} 連了 {k} 條線，超過 8 個方向")
        best, best_cost = None, math.inf
        for subset in combinations(range(8), k):        # 依逆時針順序取 k 個方向
            for r in range(k):                          # 旋轉對應：保持環繞順序
                assign = [subset[(i + r) % k] for i in range(k)]
                cost = sum(dev(a, p) ** 2 + (PORT_DIAG if p % 2 else 0) for a, p in zip(angs, assign))
                if cost < best_cost:
                    best, best_cost = assign, cost
        for ci, p in zip(ends, best):
            port[(node, ci)] = p

    # ---------- 2. 每條鏈的形狀（方向序列）----------
    pieces = []                              # (鏈, 第幾段, 方向)
    shape = {}
    for ci, c in enumerate(C):
        d0 = port[(c["u"], ci)]
        d1 = (port[(c["v"], ci)] + 4) % 8     # 抵達 v 時的行進方向
        turn = (d1 - d0) % 8
        if turn == 0:
            dirs = [d0]
        elif turn in (1, 2, 6, 7):
            dirs = [d0, d1]
        else:
            # 轉 135 度以上：加一段中間段。中間段必須跟整體同一個轉向（逆時針轉 135 度就只能
            # 先左轉 45/90 度），否則會先往反方向彎再繞回來，畫出迴旋；
            # 候選方向中取最接近地理上鏈中段走向者（迴轉 180 度時兩側都可，也由它決定）
            st = c["st"]
            a, b = st[len(st) // 3], st[2 * len(st) // 3]
            g = math.atan2(pos[b][1] - pos[a][1], pos[b][0] - pos[a][0])
            cands = {3: (1, 2), 4: (2, -2), 5: (-1, -2)}[turn]
            m = min(((d0 + k) % 8 for k in cands), key=lambda p: dev(g, p))
            dirs = [d0, m, d1]
        shape[ci] = dirs

    # ---------- 3. 變數：交會站 + 每條鏈的轉角 ----------
    vid = {}
    def var_of(k):
        if k not in vid:
            vid[k] = len(vid)
        return vid[k]
    chain_verts = {}
    for ci, c in enumerate(C):
        vs = [var_of(("n", c["u"]))] + [var_of(("c", ci, j)) for j in range(len(shape[ci]) - 1)] + [var_of(("n", c["v"]))]
        chain_verts[ci] = vs
    nv = len(vid)
    X = lambda v: v
    Y = lambda v: nv + v

    rows, lo, hi, cost = [], [], [], [0.0] * (2 * nv)

    def add(coefs, l=-math.inf, h=math.inf):
        rows.append(coefs); lo.append(l); hi.append(h)

    slack_cost = []
    def soft(coefs, l, weight):
        """coefs·z ≥ l，可用 slack 違反，每單位罰 weight。"""
        s = 2 * nv + len(slack_cost)
        slack_cost.append(weight)
        add({**coefs, s: 1}, l)

    DV = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
    seg_list = []                            # (鏈, a, b, 方向)
    for ci, c in enumerate(C):
        vs, dirs = chain_verts[ci], shape[ci]
        length_terms = defaultdict(float)
        for (a, b), d in zip(zip(vs, vs[1:]), dirs):
            dx, dy = DV[d]
            seg_list.append((ci, a, b, d))
            if dx == 0:
                add({X(b): 1, X(a): -1}, 0, 0)
                soft({Y(b): dy, Y(a): -dy}, MIN_PIECE, W_SHAPE)
                length_terms[Y(b)] += dy; length_terms[Y(a)] -= dy
            elif dy == 0:
                add({Y(b): 1, Y(a): -1}, 0, 0)
                soft({X(b): dx, X(a): -dx}, MIN_PIECE, W_SHAPE)
                length_terms[X(b)] += dx; length_terms[X(a)] -= dx
            else:
                add({X(b): dy, X(a): -dy, Y(b): -dx, Y(a): dx}, 0, 0)
                soft({X(b): dx, X(a): -dx}, MIN_PIECE / math.sqrt(2), W_SHAPE)
                length_terms[X(b)] += dx * math.sqrt(2); length_terms[X(a)] -= dx * math.sqrt(2)
        add(dict(length_terms), c["L"])          # 總長 ≥ 站數：站距至少 1
        for j, w in length_terms.items():
            cost[j] += w

    # ---------- 4. 相對方位：地理上相鄰的交會站 ----------
    knodes = sorted(key)
    def rel_constraint(a_var, b_var, ga, gb, weight):
        gx, gy = gb[0] - ga[0], gb[1] - ga[1]
        g = math.hypot(gx, gy)
        if g < 1e-9:
            return
        if abs(gx) >= REL_RATIO * g:
            sx = 1 if gx > 0 else -1
            soft({X(b_var): sx, X(a_var): -sx}, NODE_SEP, weight)
        if abs(gy) >= REL_RATIO * g:
            sy = 1 if gy > 0 else -1
            soft({Y(b_var): sy, Y(a_var): -sy}, NODE_SEP, weight)

    linked = {frozenset((c["u"], c["v"])) for c in C}
    pairs = set()
    for a in knodes:
        near = sorted((b for b in knodes if b != a), key=lambda b: math.dist(pos[a], pos[b]))[:REL_NEIGHBORS]
        pairs.update(frozenset((a, b)) for b in near)
    for pr in pairs - linked:                         # 有鏈直接相連的，方向已由埠決定
        a, b = sorted(pr)
        rel_constraint(var_of(("n", a)), var_of(("n", b)), pos[a], pos[b], W_REL)

    def solve():
        nvar = 2 * nv + len(slack_cost)
        r, cidx, val = [], [], []
        for i, coefs in enumerate(rows):
            for j, a in coefs.items():
                r.append(i); cidx.append(j); val.append(a)
        A = coo_matrix((val, (r, cidx)), shape=(len(rows), nvar)).tocsr()
        lo_a, hi_a = np.array(lo), np.array(hi)
        eq = lo_a == hi_a
        from scipy.sparse import vstack
        A_ub = vstack([A[~eq & np.isfinite(hi_a)], -A[~eq & np.isfinite(lo_a)]])
        b_ub = np.concatenate([hi_a[~eq & np.isfinite(hi_a)], -lo_a[~eq & np.isfinite(lo_a)]])
        c_all = cost + slack_cost
        bounds = [(None, None)] * (2 * nv) + [(0, None)] * len(slack_cost)
        bounds[X(0)] = (0, 0); bounds[Y(0)] = (0, 0)
        return linprog(c_all, A_ub=A_ub, b_ub=b_ub, A_eq=A[eq], b_eq=lo_a[eq], bounds=bounds, method="highs")

    # 地理上每段大約在哪：取那條鏈對應比例的車站
    def seg_geo(ci, j):
        st = C[ci]["st"]; n = len(shape[ci])
        a = st[int(len(st) * j / n)]; b = st[min(len(st) - 1, int(len(st) * (j + 1) / n))]
        return ((pos[a][0] + pos[b][0]) / 2, (pos[a][1] + pos[b][1]) / 2)

    seg_index = {}
    for ci in range(len(C)):
        for j in range(len(shape[ci])):
            seg_index[(ci, j)] = (chain_verts[ci][j], chain_verts[ci][j + 1])

    added = set()
    for rnd in range(CG_ROUNDS):
        res = solve()
        if res.status != 0:
            raise RuntimeError(f"約束圖無解：{res.message}")
        P = [(res.x[X(v)], res.x[Y(v)]) for v in range(nv)]
        segs = [(k, P[a], P[b]) for k, (a, b) in seg_index.items()]
        bad = []
        for i in range(len(segs)):
            (k1, p1, q1) = segs[i]
            for j in range(i + 1, len(segs)):
                (k2, p2, q2) = segs[j]
                if k1[0] == k2[0]:
                    continue
                if set(seg_index[k1]) & set(seg_index[k2]):
                    # 共用交會站：只在疊在一起時才算衝突
                    if overlap_len(p1, q1, p2, q2) < 1e-6:
                        continue
                elif seg_dist(p1, q1, p2, q2) >= SEG_SEP * 0.99:
                    continue
                pair = (min(k1, k2), max(k1, k2))
                if pair not in added:
                    bad.append(pair)
        log(f"   第 {rnd + 1} 次求解：{len(bad)} 對線段交叉或過近")
        if not bad:
            break
        for k1, k2 in bad:
            added.add((k1, k2))
            g1, g2 = seg_geo(*k1), seg_geo(*k2)
            gx, gy = g2[0] - g1[0], g2[1] - g1[1]
            (a1, b1), (a2, b2) = seg_index[k1], seg_index[k2]
            shared = {a1, b1} & {a2, b2}
            # 依地理相對方位，讓第二段整段在第一段的那一側
            axis = 0 if abs(gx) >= abs(gy) else 1
            sgn = 1 if (gx if axis == 0 else gy) > 0 else -1
            V = X if axis == 0 else Y
            for v1 in (a1, b1):
                for v2 in (a2, b2):
                    if v1 in shared or v2 in shared:
                        continue
                    soft({V(v2): sgn, V(v1): -sgn}, SEG_SEP, W_SEP)

    viol = [w for v, w in zip(res.x[2 * nv:], slack_cost) if v > 1e-6]
    n_shape = sum(1 for w in viol if w == W_SHAPE)
    if viol:
        log(f"   ⚠️ 無法同時滿足：相對方位/分離約束 {len(viol) - n_shape} 條、"
            f"線段方向 {n_shape} 段（各交會站的方向分配在幾何上互相矛盾）")

    coords, bends = {}, {}
    for ci, c in enumerate(C):
        place_along(c["st"], [P[v] for v in chain_verts[ci]], coords, bends)
    minx = min(p[0] for p in coords.values()); miny = min(p[1] for p in coords.values())
    r = lambda p: [round(p[0] - minx, 3), round(p[1] - miny, 3)]
    return ({sid: r(p) for sid, p in coords.items()},
            {k: [r(p) for p in v] for k, v in bends.items()})


def overlap_len(p, q, a, b):
    """兩線段共線時的重疊長度（不共線為 0）。"""
    ux, uy = q[0] - p[0], q[1] - p[1]
    L = math.hypot(ux, uy)
    if L < 1e-9:
        return 0.0
    ux, uy = ux / L, uy / L
    off = lambda r: (r[0] - p[0]) * uy - (r[1] - p[1]) * ux
    if abs(off(a)) > 1e-6 or abs(off(b)) > 1e-6:
        return 0.0
    proj = lambda r: (r[0] - p[0]) * ux + (r[1] - p[1]) * uy
    lo2, hi2 = sorted((proj(a), proj(b)))
    return max(0.0, min(L, hi2) - max(0.0, lo2))


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
