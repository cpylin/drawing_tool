# -*- coding: utf-8 -*-
"""自动布局。

手写坐标能得到最好效果，但规格文件作者往往只想描述"谁指向谁"。这里提供两种
轻量布局：

* :func:`layered` —— 分层布局（Sugiyama 的最简版）：按有向图的最长路径分层，
  同层水平均分，适合流程图、结构图、状态图。
* :func:`radial` —— 放射布局：中心节点 + 环状分支，适合思维导图。
* :func:`columns` —— 列布局：把节点按给定列分配、列内均分，适合顺序图/泳道图。
"""
from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

from .model import Diagram, Node


def layered(diagram: Diagram, x0: float = 120, y0: float = 120,
            dx: float = 260, dy: float = 130, center: bool = True) -> None:
    """按最长路径分层。已显式给出坐标的节点不参与。"""
    nodes = [n for n in diagram.nodes if n.meta.get("auto", True)]
    if not nodes:
        return
    ids = {n.id for n in nodes}
    incoming: Dict[str, int] = {n.id: 0 for n in nodes}
    adj: Dict[str, List[str]] = {n.id: [] for n in nodes}
    for e in diagram.edges:
        if e.src in ids and e.dst in ids:
            adj[e.src].append(e.dst)
            incoming[e.dst] += 1

    level: Dict[str, int] = {n.id: 0 for n in nodes}
    order = [n.id for n in nodes if incoming[n.id] == 0] or [n.id for n in nodes]
    seen = set(order)
    queue = list(order)
    guard = 0
    while queue and guard < 10000:
        guard += 1
        cur = queue.pop(0)
        for nxt in adj[cur]:
            if level[nxt] < level[cur] + 1:
                level[nxt] = level[cur] + 1
            incoming[nxt] -= 1
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)

    buckets: Dict[int, List[str]] = {}
    for nid, lv in level.items():
        buckets.setdefault(lv, []).append(nid)

    y = y0
    max_rows = max(buckets.values(), key=len) if buckets else []
    span = max(len(v) for v in buckets.values()) if buckets else 1
    for lv in sorted(buckets):
        row = buckets[lv]
        y = y0 + lv * dy
        total = len(row)
        for i, nid in enumerate(row):
            offset = (i - (total - 1) / 2) * dx
            node = diagram.node(nid)
            node.x = x0 + (span - 1) / 2 * dx + offset
            node.y = y
            node._geo = None


def radial(diagram: Diagram, cx: float = 620, cy: float = 460,
           radius: float = 300, inner: float = 170) -> None:
    """中心 + 放射分支。根节点取 meta['root'] 或第一个无线条的节点。"""
    roots = [n for n in diagram.nodes if n.meta.get("root")]
    if not roots:
        targets = {e.dst for e in diagram.edges}
        roots = [n for n in diagram.nodes if n.id not in targets] or diagram.nodes[:1]
    if not roots:
        return
    root = roots[0]
    root.x, root.y = cx, cy
    root._geo = None

    kids = [e.dst for e in diagram.edges if e.src == root.id]
    n = len(kids)
    for i, kid in enumerate(kids):
        ang = -1.5708 + 2 * 3.1415926 * i / max(1, n)
        node = diagram.node(kid)
        node.x = cx + radius * __import__("math").cos(ang)
        node.y = cy + radius * __import__("math").sin(ang)
        node._geo = None
        # 二级
        subs = [e.dst for e in diagram.edges if e.src == kid]
        m = len(subs)
        for j, sub in enumerate(subs):
            spread = 0.55
            a2 = ang - spread / 2 + (spread * j / max(1, m - 1) if m > 1 else 0)
            sn = diagram.node(sub)
            sn.x = cx + (radius + inner) * __import__("math").cos(a2)
            sn.y = cy + (radius + inner) * __import__("math").sin(a2)
            sn._geo = None


def columns(diagram: Diagram, x0: float = 160, gap: float = 240,
            y0: float = 140, dy: float = 100) -> None:
    """按 meta['col'] 分列、列内按 meta['row'] 排序。缺省按声明顺序排成一行。"""
    cols: Dict[int, List[Node]] = {}
    for n in diagram.nodes:
        if not n.meta.get("auto", True):
            continue
        cols.setdefault(int(n.meta.get("col", 0)), []).append(n)
    for c in sorted(cols):
        row = cols[c]
        row.sort(key=lambda n: n.meta.get("row", 0))
        for i, node in enumerate(row):
            node.x = x0 + c * gap
            node.y = y0 + i * dy
            node._geo = None


def grid(diagram: Diagram, x0: float = 160, y0: float = 140,
         dx: float = 280, dy: float = 150, per_row: int = 4) -> None:
    """等距网格，适合用例图、类图这类没有明显层级的图。"""
    i = 0
    for n in diagram.nodes:
        if not n.meta.get("auto", True):
            continue
        n.x = x0 + (i % per_row) * dx
        n.y = y0 + (i // per_row) * dy
        n._geo = None
        i += 1


LAYOUTS = {
    "layered": layered,
    "radial": radial,
    "columns": columns,
    "grid": grid,
    "none": lambda d: None,
}


def apply(diagram: Diagram, name: str, **kwargs) -> None:
    fn = LAYOUTS.get(name)
    if fn is None:
        raise ValueError("未知布局 %r，可选：%s" % (name, ", ".join(sorted(LAYOUTS))))
    fn(diagram, **kwargs)
