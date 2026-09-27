#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wikitable.py — 把維基百科 HTML <table> 展開成矩形 grid（正確處理 rowspan / colspan），
並攤平多層表頭。

為何不用 pandas.read_html：本機 Windows 應用程式控制原則封鎖了 numpy/pandas 的原生
.pyd（ImportError: DLL load failed ... 應用程式控制原則已封鎖此檔案），因此改用純
BeautifulSoup 實作。維基的車站表大量使用 rowspan（所在地、路線名跨多列），若直接以
tr.find_all('td') 的索引取值會整列錯位，故必須先展開成 grid。
"""
import re


def table_to_grid(table):
    """展開表格為 (grid, is_th)：grid[r][c] 是文字，is_th[r][c] 標記該格是否 <th>。"""
    grid, is_th = [], []
    pending = {}  # (row, col) -> (text, is_th)，由 rowspan 帶到下方列的格子

    for r, tr in enumerate(table.find_all("tr")):
        _ensure_row(grid, is_th, r)
        c = 0
        for cell in tr.find_all(["th", "td"]):
            while (r, c) in pending:  # 先讓上方 rowspan 占位
                txt, th = pending.pop((r, c))
                _put(grid, is_th, r, c, txt, th)
                c += 1
            cs = _span(cell.get("colspan"), 50)
            rs = _span(cell.get("rowspan"), 200)
            txt = re.sub(r"\s+", "", cell.get_text(" ", strip=True))
            th = cell.name == "th"
            for dc in range(cs):
                _put(grid, is_th, r, c + dc, txt, th)
                for dr in range(1, rs):
                    pending[(r + dr, c + dc)] = (txt, th)
            c += cs
        while (r, c) in pending:  # 列尾殘餘
            txt, th = pending.pop((r, c))
            _put(grid, is_th, r, c, txt, th)
            c += 1

    for (r, c), (txt, th) in sorted(pending.items()):
        _put(grid, is_th, r, c, txt, th)

    width = max((len(row) for row in grid), default=0)
    for row, trow in zip(grid, is_th):
        row.extend([""] * (width - len(row)))
        trow.extend([False] * (width - len(trow)))
    return grid, is_th


def _span(v, cap):
    try:
        return max(1, min(int(v), cap))
    except (TypeError, ValueError):
        return 1


def _ensure_row(grid, is_th, r):
    while len(grid) <= r:
        grid.append([])
        is_th.append([])


def _put(grid, is_th, r, c, txt, th):
    _ensure_row(grid, is_th, r)
    row, trow = grid[r], is_th[r]
    while len(row) <= c:
        row.append("")
        trow.append(False)
    if row[c] == "":       # 先到先占（rowspan 不覆蓋既有內容）
        row[c] = txt
        trow[c] = th


def header_depth(grid, is_th, max_depth=3):
    """猜表頭列數：開頭連續幾列幾乎全是 <th>。"""
    depth = 0
    for r in range(min(max_depth, len(grid))):
        if not is_th[r]:
            break
        if sum(1 for v in is_th[r] if v) / len(is_th[r]) >= 0.8:
            depth = r + 1
        else:
            break
    return max(1, depth)


def flat_columns(grid, is_th, depth=None):
    """攤平多層表頭成欄位名（如 営業キロ_累計），回傳 (cols, depth)。"""
    if depth is None:
        depth = header_depth(grid, is_th)
    width = len(grid[0]) if grid else 0
    cols = []
    for c in range(width):
        parts = []
        for r in range(depth):
            v = grid[r][c] if c < len(grid[r]) else ""
            if v and (not parts or parts[-1] != v):
                parts.append(v)
        cols.append("_".join(parts))
    return cols, depth
