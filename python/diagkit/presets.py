# -*- coding: utf-8 -*-
"""各类图的预设构建器。

每个构建器接收普通 Python 数据（与 JSON 规格同构），返回 :class:`Diagram`。
调用方只描述"有哪些元件、怎么连"，坐标、分层、折行、激活条跨度都由这里决定，
因此同一份数据在不同主题、不同倍率下都能得到一致的版面。
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from . import layout
from .model import Diagram, Edge, Measurer, Node, label_of
from .text import Label, from_plain
from .theme import Theme

FLOW_SHAPES = {
    "start": "term", "end": "term", "term": "term",
    "process": "process", "proc": "process", "action": "process",
    "decision": "decision", "if": "decision", "branch": "decision",
    "io": "io", "input": "io", "output": "io",
    "predefined": "predefined", "subroutine": "predefined",
    "manual": "manual", "document": "document", "doc": "document",
    "database": "cylinder", "store": "store", "queue": "queue",
    "entity": "entity", "actor": "actor", "usecase": "usecase",
    "note": "note", "state": "state", "module": "module",
    "class": "class", "component": "component", "node": "node",
    "package": "package", "cloud": "cloud", "erd": "entity_erd",
}

RELATION_ARROWS = {
    "association": ("solid", "none"),
    "generalization": ("solid", "hollow"),
    "realization": ("dashed", "hollow"),
    "dependency": ("dashed", "open"),
    "composition": ("solid", "diamond"),
    "aggregation": ("solid", "diamond_h"),
    "directed": ("solid", "open"),
    "link": ("solid", "none"),
}


def _diagram(title: Optional[str], theme: str, subtitle: Optional[str] = None,
             margin: int = 56) -> Diagram:
    return Diagram(title=title, subtitle=subtitle, theme=Theme.get(theme),
                   margin=margin, auto_crop=True)


def _node(kind: str, text, x: float = 0, y: float = 0, nid: str = "",
          attrs: Optional[Sequence[str]] = None, meths: Optional[Sequence[str]] = None,
          auto: bool = True, **meta) -> Node:
    node = Node(kind=kind, label=label_of(text), x=x, y=y, id=nid,
                attrs=list(attrs or []), meths=list(meths or []))
    node.meta.update(meta)
    node.meta["auto"] = auto
    return node


def _edge(src: str, dst: str, label=None, arrow: str = "filled",
          style: str = "solid", src_side: str = "b", dst_side: str = "t",
          start_arrow: str = "none", route=None, label_at=None) -> Edge:
    return Edge(src=src, dst=dst, src_side=src_side, dst_side=dst_side,
                label=label_of(label) if label else None,
                style=style, arrow=arrow, start_arrow=start_arrow,
                route=route, label_at=label_at)


# ==================================================================== 流程图
def flowchart(items: Sequence[dict], links: Sequence[dict],
              title: Optional[str] = None, theme: str = "light",
              direction: str = "down", **kw) -> Diagram:
    """通用流程图 / 活动图。``items`` 每项含 id/text/shape，``links`` 含 from/to/label。"""
    d = _diagram(title, theme)
    for it in items:
        shape = FLOW_SHAPES.get(str(it.get("shape", "process")).lower(), "process")
        d.add(_node(shape, it.get("text", ""), nid=str(it["id"]),
                    auto="x" not in it or "y" not in it,
                    **{k: it[k] for k in ("col", "row") if k in it}))
    for lk in links:
        arrow = lk.get("arrow", "filled")
        style = lk.get("style", "solid")
        d.connect(_edge(str(lk["from"]), str(lk["to"]), lk.get("label"),
                        arrow=arrow, style=style,
                        src_side=lk.get("src_side", "b" if direction == "down" else "r"),
                        dst_side=lk.get("dst_side", "t" if direction == "down" else "l"),
                        route=lk.get("route"), label_at=lk.get("label_at")))
    _apply_layout(d, kw.get("layout", "layered"),
                  direction=direction, **kw.get("layout_options", {}))
    return d


# ======================================================================= DFD
def dfd(entities: Sequence[dict], processes: Sequence[dict],
        stores: Sequence[dict], flows: Sequence[dict],
        title: Optional[str] = None, theme: str = "light",
        layout_mode: str = "auto", **kw) -> Diagram:
    """数据流图。实体在左、加工居中、数据存储在右，构成三栏。"""
    d = _diagram(title, theme)
    for e in entities:
        d.add(_node("entity", e.get("text", e["id"]), nid=str(e["id"]),
                    auto="x" not in e))
    for p in processes:
        d.add(_node("dfd_process", p.get("text", p["id"]), nid=str(p["id"]),
                    auto="x" not in p))
    for s in stores:
        d.add(_node("store", s.get("text", s["id"]), nid=str(s["id"]),
                    auto="x" not in s))

    columns: List[List[Node]] = [
        [n for n in d.nodes if n.kind == "entity"],
        [n for n in d.nodes if n.kind == "dfd_process"],
        [n for n in d.nodes if n.kind == "store"],
    ]
    flows_with_edges = []
    for f in flows:
        edge = _edge(str(f["from"]), str(f["to"]), f.get("label"),
                     arrow="filled", src_side="r", dst_side="l",
                     route=f.get("route"), label_at=f.get("label_at"))
        d.connect(edge)
        flows_with_edges.append((f, edge))

    # 三栏内部的纵向顺序用重心法（barycenter / 中位数启发式）反复扫描：
    # 让每个节点尽量靠近与它相连的节点，能显著减少跨栏连线的交叉。
    # 这是 Sugiyama 分层布局里标准的 crossing reduction 步骤。
    # 只保留"确实减少相邻栏交叉数"的那一版——否则声明顺序更符合阅读习惯。
    best = [list(col) for col in columns]
    best_cost = _adjacent_crossings(best, d.edges)
    for _ in range(4):
        for left, right in ((0, 1), (1, 2), (2, 1), (1, 0)):
            ref = {n.id: i for i, n in enumerate(columns[left])}
            columns[right] = _barycenter(columns[right], d.edges, set(ref), ref)
            cost = _adjacent_crossings(columns, d.edges)
            # 只有明显更好（至少少 2 处）才采用：小图里 1 处的差别
            # 抵不上打乱声明顺序带来的阅读成本。
            if cost + 1 < best_cost:
                best = [list(col) for col in columns]
                best_cost = cost
    columns = best

    gap, x0 = kw.get("gap", 420), kw.get("x0", 200)
    y0, dy = kw.get("y0", 160), kw.get("dy", 150)
    for c, order in enumerate(columns):
        for i, n in enumerate(order):
            if not n.meta.get("auto", True):
                continue        # 显式坐标优先
            n.x = x0 + c * gap
            n.y = y0 + i * dy
            n._geo = None

    row = {n.id: i for order in columns for i, n in enumerate(order)}
    col = {n.id: c for c, order in enumerate(columns) for n in order}
    m = Measurer(d.theme, 1.0)
    store_right = max((n.geometry(m)["right"] for n in columns[2]),
                      default=None)
    for f, edge in flows_with_edges:
        if "src_side" not in f and "dst_side" not in f and edge.route is None:
            # 跨两行以上进入最右栏（数据存储）的长流：沿存储栏右侧的
            # 页边通道绕入。只改锚点还不够——A* 仍可能为了省路从中间
            # 缝隙穿过；显式走外侧才能在任何字体宽度下都不压中间层的流。
            if col.get(edge.dst) == 2 and abs(row.get(edge.dst, 0) - row.get(edge.src, 0)) >= 2 \
                    and store_right is not None:
                gs = d.node(edge.src).geometry(m)
                gd = d.node(edge.dst).geometry(m)
                channel = store_right + 36
                # 横向出口放在源节点所在整行的下方，避免擦到同排其它框
                row_bottom = max(
                    (n.geometry(m)["bottom"] for n in columns[0] + columns[1]
                     if row.get(n.id) == row.get(edge.src)),
                    default=gs["bottom"],
                )
                y_exit = row_bottom + 20
                edge.route = [(gs["x"], gs["bottom"]), (gs["x"], y_exit),
                              (channel, y_exit), (channel, gd["y"]),
                              (gd["right"], gd["y"])]
                edge.src_side = edge.dst_side = "c"
            else:
                edge.src_side, edge.dst_side = "r", "l"
        else:
            edge.src_side = f.get("src_side", "r")
            edge.dst_side = f.get("dst_side", "l")
    return d


# =================================================================== 结构图
def structure(tree: dict, title: Optional[str] = None, theme: str = "light",
              dx: float = 220, dy: float = 130, **kw) -> Diagram:
    """软件结构图。``tree`` 形如 ``{"name": "顶层", "children": [...]}``。"""
    d = _diagram(title, theme)
    counter = {"n": 0}

    def walk(item: dict, depth: int, parent: Optional[str]) -> str:
        counter["n"] += 1
        nid = item.get("id") or "n%d" % counter["n"]
        kind = "module_top" if depth == 0 else "module"
        node = _node(kind, item.get("name", ""), nid=nid,
                     auto=False, depth=depth)
        d.add(node)
        if parent:
            d.connect(_edge(parent, nid, item.get("label"), arrow="filled",
                            src_side="b", dst_side="t"))
        children = item.get("children") or []
        for child in children:
            walk(child, depth + 1, nid)
        return nid

    walk(tree, 0, None)

    # 树形布局：按层分 y，同层均分 x，父在子中点
    layers: Dict[int, List[Node]] = {}
    for n in d.nodes:
        layers.setdefault(int(n.meta.get("depth", 0)), []).append(n)
    total_w = max(len(v) for v in layers.values()) * dx if layers else dx
    for depth, row in sorted(layers.items()):
        for i, node in enumerate(row):
            node.x = 200 + (total_w - len(row) * dx) / 2 + i * dx + dx / 2
            node.y = 120 + depth * dy
            node._geo = None
    # 父节点对齐子节点中点
    for node in reversed(d.nodes):
        kids = [d.node(e.dst) for e in d.edges if e.src == node.id]
        if kids:
            node.x = sum(k.x for k in kids) / len(kids)
            node._geo = None

    # 结构图的连线走"母线"：父节点垂直下到层间，横移到子节点 x，再垂直落到子节点。
    # 这是软件结构图的传统画法，也彻底避免兄弟连线互相交叉 / 贴边框。
    m = Measurer(d.theme, 1.0)
    for n in d.nodes:
        n._geo = None
        n.geometry(m)
    for e in d.edges:
        a, b = d.node(e.src), d.node(e.dst)
        ga, gb = a.geometry(m), b.geometry(m)
        if abs(ga["x"] - gb["x"]) < 0.5:
            e.route = [(ga["x"], ga["bottom"]), (gb["x"], gb["top"])]
        else:
            bus_y = (ga["y"] + gb["y"]) / 2
            e.route = [(ga["x"], ga["bottom"]), (ga["x"], bus_y),
                       (gb["x"], bus_y), (gb["x"], gb["top"])]
    return d


# =================================================================== 用例图
def usecase(actors: Sequence[dict], cases: Sequence[dict], links: Sequence[dict],
            boundary: str = "系统边界", title: Optional[str] = None,
            theme: str = "light", per_row: int = 2, **kw) -> Diagram:
    d = _diagram(title, theme)
    case_nodes: List[Node] = []
    for c in cases:
        node = _node("usecase", c.get("text", c["id"]), nid=str(c["id"]), auto=False)
        case_nodes.append(node)
        d.add(node)

    # 用例网格
    col_w, row_h = 250, 130
    x0, y0 = 460, 190
    for i, node in enumerate(case_nodes):
        node.x = x0 + (i % per_row) * col_w
        node.y = y0 + (i // per_row) * row_h
        node._geo = None

    n_rows = (len(case_nodes) + per_row - 1) // per_row or 1
    left_actors, right_actors = [], []
    for a in actors:
        side = a.get("side", "left")
        node = _node("actor", a.get("text", a["id"]), nid=str(a["id"]), auto=False)
        (left_actors if side == "left" else right_actors).append(node)
        d.add(node)

    def stack(nodes: List[Node], x: float) -> None:
        for i, node in enumerate(nodes):
            node.x = x
            node.y = y0 + i * ((n_rows * row_h) / max(1, len(nodes)))
            node._geo = None

    stack(left_actors, 150)
    stack(right_actors, x0 + per_row * col_w + 60)

    bw = per_row * col_w + 120
    bh = n_rows * row_h + 60
    m = Measurer(d.theme, 1.0)
    # 边界框按用例的实际外接矩形推算，保证标题与椭圆不重叠
    if case_nodes:
        for n in case_nodes:
            n._geo = None
            n.geometry(m)
        left = min(n.x - n.w / 2 for n in case_nodes) - 90
        right = max(n.x + n.w / 2 for n in case_nodes) + 90
        top = min(n.y - n.h / 2 for n in case_nodes) - 100
        bottom = max(n.y + n.h / 2 for n in case_nodes) + 70
    else:
        left, right = x0 - 160, x0 - 160 + bw
        top, bottom = y0 - 70, y0 - 70 + bh
    d.groups.append(dict(title=boundary, x=left, y=top,
                         w=right - left, h=bottom - top))

    # 参与者与用例之间的连线走"通道"：先横出到参与者与边界之间的竖通道，
    # 再竖直对齐目标用例的中心，最后横进入椭圆。这样多条关联线互相平行、不交叉。
    case_left = min((n.x - n.w / 2) for n in case_nodes) if case_nodes else x0
    case_right = max((n.x + n.w / 2) for n in case_nodes) if case_nodes else x0
    has_left = bool(left_actors)
    has_right = bool(right_actors)
    lane_left = (150 + case_left) / 2 if has_left else case_left - 80
    lane_right = (case_right + (x0 + per_row * col_w + 60)) / 2 if has_right \
        else case_right + 80

    for lk in links:
        rel = str(lk.get("type", "association"))
        style, arrow = RELATION_ARROWS.get(rel, ("solid", "none"))
        a, b = d.node(str(lk["from"])), d.node(str(lk["to"]))
        a_case = a.kind == "usecase"
        b_case = b.kind == "usecase"
        route = None
        if a_case != b_case:
            actor, case = (b, a) if a_case else (a, b)
            leftward = actor.x <= case.x
            mx = lane_left if leftward else lane_right
            start_x = actor.x + (actor.w or 120) / 2 if mx > actor.x \
                else actor.x - (actor.w or 120) / 2
            g = case.geometry(m)
            entry_x = g["left"] if leftward else g["right"]
            # 同一行里若还隔着别的用例，直接横扫会从椭圆中间穿过去；
            # 改为先走到该行上方/下方的空通道，再竖直接进入椭圆。
            blocked = False
            lo, hi = (mx, entry_x) if mx <= entry_x else (entry_x, mx)
            for other in case_nodes:
                if other is case:
                    continue
                go = other.geometry(m)
                if go["top"] - 4 <= case.y <= go["bottom"] + 4 \
                        and min(hi, go["right"]) - max(lo, go["left"]) > 1:
                    blocked = True
                    break
            if blocked:
                above = actor.y <= case.y
                channel = g["top"] - 18 if above else g["bottom"] + 18
                entry_y = g["top"] if above else g["bottom"]
                route = [(start_x, actor.y), (mx, actor.y),
                         (mx, channel), (case.x, channel), (case.x, entry_y)]
            else:
                route = [(start_x, actor.y), (mx, actor.y),
                         (mx, case.y), (entry_x, case.y)]
            # 用自绘折线时，锚点不再参与计算
            src_side, dst_side = "c", "c"
        else:
            src_side, dst_side = ("r", "l") if a.x <= b.x else ("l", "r")
        edge = _edge(str(lk["from"]), str(lk["to"]), lk.get("label"),
                     arrow=arrow, style=style, src_side=src_side, dst_side=dst_side)
        if route:
            edge.route = route
        d.connect(edge)
    return d


# ===================================================================== 类图
def class_diagram(classes: Sequence[dict], relations: Sequence[dict],
                  title: Optional[str] = None, theme: str = "light",
                  per_row: int = 3, **kw) -> Diagram:
    """UML 类图。relations[].type 支持六种关系，多重度写在 mul 里。"""
    d = _diagram(title, theme)
    for c in classes:
        node = _node("class", c.get("name", c["id"]), nid=str(c["id"]),
                     attrs=c.get("attrs"), meths=c.get("meths"), auto=False)
        d.add(node)

    nodes = [d.node(str(c["id"])) for c in classes]
    for i, node in enumerate(nodes):
        # 保持同排居中对齐：类图里轻微错位会让连线从框下穿过，比共线更难看。
        # 同排多关系共线属于已知限制（见 docs/DETAIL.md），可通过 per_row 规避。
        node.x = 300 + (i % per_row) * 420
        node.y = 170 + (i // per_row) * 260
        node._geo = None

    for r in relations:
        rel = str(r.get("type", "association"))
        style, arrow = RELATION_ARROWS.get(rel, ("solid", "none"))
        src_id, dst_id = str(r["from"]), str(r["to"])
        # 组合/聚集的菱形紧贴"整体"。关系按 (整体 -> 部分) 书写，
        # 因此把连线方向反过来画，使箭头落在"部分"、菱形落在"整体"。
        if rel in ("composition", "aggregation"):
            src_id, dst_id = dst_id, src_id
        a, b = d.node(src_id), d.node(dst_id)
        horizontal = abs(a.x - b.x) >= abs(a.y - b.y)
        if horizontal:
            start, end = ("r", "l") if a.x <= b.x else ("l", "r")
        else:
            start, end = ("b", "t") if a.y <= b.y else ("t", "b")
        label = r.get("label")
        if r.get("mul"):
            label = "%s  %s" % (r["mul"], label or "")
        d.connect(_edge(src_id, dst_id, label, arrow=arrow,
                        style=style, src_side=start, dst_side=end))
    return d


# =================================================================== 顺序图
def sequence(participants: Sequence[dict], messages: Sequence[dict],
             title: Optional[str] = None, theme: str = "light",
             gap: float = 230, top: float = 110, step: float = 62,
             activate: bool = True, **kw) -> Diagram:
    """UML 顺序图。接收消息自动开激活条，返回（虚线）消息自动收到该条之前。"""
    d = _diagram(title, theme)
    xs: Dict[str, float] = {}
    for i, p in enumerate(participants):
        pid = str(p["id"])
        x = 190 + i * gap
        xs[pid] = x
        d.add(_node("lifeline", p.get("text", pid), x=x, y=top, nid=pid, auto=False))

    y = top + 100
    opens: Dict[str, int] = {}
    spans: List[Tuple[str, float, float]] = []

    for m in messages:
        src, dst = str(m["from"]), str(m["to"])
        text = m.get("text", "")
        dashed = bool(m.get("dashed", False))
        y += step
        if src == dst:
            # 自消息：向右出再折回
            x = xs[src]
            pts = [(x, y), (x + 70, y), (x + 70, y + 30), (x, y + 30)]
            d.edges.append(Edge(src=src, dst=dst, route=pts, arrow="filled",
                                label=label_of(text), label_at=(x + 40, y - 14)))
            y += 30
        else:
            x1, x2 = xs[src], xs[dst]
            pts = [(x1, y), (x2, y)]
            d.edges.append(Edge(
                src=src, dst=dst, route=pts,
                arrow="open" if dashed else "filled",
                style="dashed" if dashed else "solid",
                label=label_of(text), label_at=((x1 + x2) / 2, y - 16)))

        if activate:
            if dashed and dst in opens:
                spans.append((dst, opens.pop(dst), y))
            if not dashed and dst not in opens:
                opens[dst] = y

    bottom = y + 40
    for pid, start in opens.items():
        spans.append((pid, start, bottom))

    for pid in xs:
        node = d.node(pid)
        node.h = bottom - top
        # 生命线的 y 是"头部顶端"，几何计算按中心点处理，这里补上半径
        node.y = top + node.h / 2
        node._geo = None
    for i, (pid, y1, y2) in enumerate(spans):
        d.add(Node(kind="activation", label=Label(), x=xs[pid], y=(y1 + y2) / 2,
                   w=16, h=max(20, y2 - y1), id="act%d" % i))
    return d


# =================================================================== 活动图
def activity(lanes: Sequence[dict], items: Sequence[dict], links: Sequence[dict],
             title: Optional[str] = None, theme: str = "light",
             col_gap: float = 380, row_gap: float = 120, **kw) -> Diagram:
    """带泳道的活动图。``lanes`` 为泳道名列表；``items`` 需给 lane 字段。"""
    d = _diagram(title, theme)
    lane_titles = [str(l.get("title", l)) if isinstance(l, dict) else str(l) for l in lanes]
    for it in items:
        shape = FLOW_SHAPES.get(str(it.get("shape", "process")).lower(), "process")
        d.add(_node(shape, it.get("text", ""), nid=str(it["id"]), auto=False,
                    lane=int(it.get("lane", 0)), col=int(it.get("col", 0)),
                    row=int(it.get("row", 0))))
    for lk in links:
        d.connect(_edge(str(lk["from"]), str(lk["to"]), lk.get("label"),
                        arrow=lk.get("arrow", "filled"),
                        style=lk.get("style", "solid"),
                        src_side=lk.get("src_side", "b"),
                        dst_side=lk.get("dst_side", "t"),
                        route=lk.get("route")))
    # 位置：泳道为列，行号决定 y
    x0, y0 = 200, 230
    for n in d.nodes:
        if n.kind in ("start", "stop", "fork", "join"):
            n.x = x0 + int(n.meta.get("lane", 0)) * col_gap
            n.y = y0 + int(n.meta.get("row", 0)) * row_gap
            n._geo = None
        else:
            n.x = x0 + int(n.meta.get("lane", 0)) * col_gap
            n.y = y0 + (int(n.meta.get("row", 0)) + 1) * row_gap
            n._geo = None

    depth = 0
    for n in d.nodes:
        depth = max(depth, int(n.meta.get("row", 0)))
    height = y0 + (depth + 2) * row_gap
    for i, t in enumerate(lane_titles):
        d.lanes.append(dict(title=t, x=40 + i * col_gap, y=110,
                            w=col_gap, h=height - 110))
    return d


# =================================================================== 状态图
def state_machine(states: Sequence[dict], transitions: Sequence[dict],
                  title: Optional[str] = None, theme: str = "light",
                  direction: str = "right", **kw) -> Diagram:
    d = _diagram(title, theme)
    for s in states:
        kind = str(s.get("shape", "state"))
        if kind in ("initial", "start"):
            node = _node("start", "", nid=str(s["id"]), auto=False,
                         w=34, h=34)
        elif kind in ("final", "stop"):
            node = _node("stop", "", nid=str(s["id"]), auto=False, w=40, h=40)
        else:
            node = _node("state", s.get("text", s["id"]), nid=str(s["id"]), auto=False)
        d.add(node)

    for t in transitions:
        d.connect(_edge(str(t["from"]), str(t["to"]), t.get("label"),
                        arrow="filled", style=t.get("style", "solid"),
                        src_side=t.get("src_side", "r"),
                        dst_side=t.get("dst_side", "l"),
                        route=t.get("route"), label_at=t.get("label_at")))

    # 分层排布：从初态沿转移边做最长路径分层，同层纵向散开。
    # 必须放在连线之后 —— 布局依赖 d.edges。
    # 这样"待确认→已完成/已关闭/纠纷中"这类分支会画成真正的分叉，而不是排成一条直线。
    ids = {n.id for n in d.nodes}
    out_edges: Dict[str, List[str]] = {nid: [] for nid in ids}
    indeg: Dict[str, int] = {nid: 0 for nid in ids}
    for e in d.edges:
        if e.src in ids and e.dst in ids:
            out_edges[e.src].append(e.dst)
            indeg[e.dst] += 1

    level: Dict[str, int] = {nid: 0 for nid in ids}
    seeds = [n.id for n in d.nodes if n.kind == "start"] or \
            [nid for nid, deg in indeg.items() if deg == 0] or list(ids)
    queue = list(seeds)
    guard = 0
    while queue and guard < 5000:
        guard += 1
        cur = queue.pop(0)
        for nxt in out_edges[cur]:
            if level[nxt] < level[cur] + 1:
                level[nxt] = level[cur] + 1
                queue.append(nxt)

    finals = [n.id for n in d.nodes if n.kind == "stop"]
    last = max(level.values()) if level else 0
    for nid in finals:
        level[nid] = last + 1

    span = kw.get("gap", 300)
    dy = kw.get("row_gap", 150)
    buckets: Dict[int, List[str]] = {}
    for nid, lv in level.items():
        buckets.setdefault(lv, []).append(nid)
    for lv in sorted(buckets):
        row = buckets[lv]
        for i, nid in enumerate(row):
            node = d.node(nid)
            node.x = 240 + lv * span
            node.y = 340 + (i - (len(row) - 1) / 2) * dy
            node._geo = None

    # 同层/跨层转移的接入点错开：指向右上方的用左上角、指向右下方的用左下角，
    # 避免多条转移挤在同一个左中点、箭头重叠。
    for e in d.edges:
        a, b = d.node(e.src), d.node(e.dst)
        dyv = b.y - a.y
        if abs(dyv) < 60:
            e.src_side, e.dst_side = "r", "l"
        elif dyv < 0:
            e.src_side, e.dst_side = "r", "bl"
        else:
            e.src_side, e.dst_side = "r", "tl"
    return d


# ===================================================================== ERD
def erd(entities: Sequence[dict], relations: Sequence[dict],
        title: Optional[str] = None, theme: str = "light",
        per_row: int = 3, **kw) -> Diagram:
    d = _diagram(title, theme)
    for e in entities:
        d.add(_node("entity_erd", e.get("name", e["id"]), nid=str(e["id"]),
                    attrs=e.get("attrs"), auto=False))
    nodes = [d.node(str(e["id"])) for e in entities]
    for i, n in enumerate(nodes):
        n.x = 320 + (i % per_row) * 460
        n.y = 200 + (i // per_row) * 320
        n._geo = None
    for r in relations:
        a, b = d.node(str(r["from"])), d.node(str(r["to"]))
        horizontal = abs(a.x - b.x) >= abs(a.y - b.y)
        src_side, dst_side = (("r", "l") if a.x <= b.x else ("l", "r")) if horizontal \
            else (("b", "t") if a.y <= b.y else ("t", "b"))
        d.connect(_edge(str(r["from"]), str(r["to"]), r.get("label"),
                        arrow=r.get("arrow", "bar"), style=r.get("style", "solid"),
                        src_side=src_side, dst_side=dst_side))
    return d


# =================================================================== 思维导图
def mindmap(root: str, branches: Sequence[dict], title: Optional[str] = None,
            theme: str = "light", **kw) -> Diagram:
    """思维导图：左右双向树形布局。

    相比放射布局，树形布局的间距由"子树高度"决定，节点再多也不会重叠，
    而且阅读顺序稳定（自上而下、左右分列）。
    """
    d = _diagram(title, theme)
    cx = kw.get("cx", 700)
    cy = kw.get("cy", 520)
    branch_dx = kw.get("branch_dx", 300)
    leaf_dx = kw.get("leaf_dx", 300)
    leaf_gap = kw.get("leaf_gap", 82)
    branch_gap = kw.get("branch_gap", 150)

    root_node = Node(kind="term", label=label_of(root), x=cx, y=cy, id="root",
                     w=240, h=76)
    root_node.meta["root"] = True
    d.add(root_node)

    half = (len(branches) + 1) // 2
    sides = [("right", list(branches[:half])), ("left", list(branches[half:]))]

    for side, group in sides:
        sign = 1 if side == "right" else -1
        heights = [max(1, len(b.get("children") or [])) * leaf_gap for b in group]
        total = sum(heights) + branch_gap * max(0, len(group) - 1)
        y = cy - total / 2
        for b, h in zip(group, heights):
            by = y + h / 2
            bid = str(b.get("id") or "b%d" % len(d.nodes))
            d.add(Node(kind="process", label=label_of(b.get("name", "")), id=bid,
                       x=cx + sign * branch_dx, y=by, w=210, h=66,
                       meta={"auto": False}))
            d.connect(_edge("root", bid, arrow="none", style="solid",
                            src_side="r" if sign > 0 else "l",
                            dst_side="l" if sign > 0 else "r"))
            kids = b.get("children") or []
            for j, child in enumerate(kids):
                text = child.get("name") if isinstance(child, dict) else child
                cid = str((child.get("id") if isinstance(child, dict) else None)
                          or "%s_c%d" % (bid, j))
                ly = by - (len(kids) - 1) * leaf_gap / 2 + j * leaf_gap
                d.add(Node(kind="term", label=label_of(text), id=cid,
                           x=cx + sign * (branch_dx + leaf_dx), y=ly,
                           w=200, h=54, meta={"auto": False}))
                d.connect(_edge(bid, cid, arrow="none", style="solid",
                                src_side="r" if sign > 0 else "l",
                                dst_side="l" if sign > 0 else "r"))
            y += h + branch_gap
    return d


# =================================================================== 分层架构
def architecture(layers: Sequence[dict], title: Optional[str] = None,
                 theme: str = "light", box_gap: float = 210,
                 band_h: float = 130, width: float = 900, **kw) -> Diagram:
    """分层架构图：每个 layer 是一条横带，带内并排若干方框。"""
    d = _diagram(title, theme)
    y = 140
    for i, layer in enumerate(layers):
        items = layer.get("items") or []
        n = max(1, len(items))
        span = min(box_gap, (width - 120) / n)
        x_start = 120 + (width - span * n) / 2 + span / 2
        d.groups.append(dict(title=layer.get("title", ""), x=100, y=y - 34,
                             w=width, h=band_h))
        for j, item in enumerate(items):
            text = item.get("name") if isinstance(item, dict) else item
            nid = str((item.get("id") if isinstance(item, dict) else None)
                      or "L%d_%d" % (i, j))
            d.add(_node("module", text, x=x_start + j * span, y=y + 40,
                        nid=nid, auto=False))
        y += band_h + 50
    for rel in kw.get("relations", []) or []:
        d.connect(_edge(str(rel["from"]), str(rel["to"]), rel.get("label"),
                        arrow=rel.get("arrow", "open"),
                        style=rel.get("style", "dashed"),
                        src_side=rel.get("src_side", "b"),
                        dst_side=rel.get("dst_side", "t")))
    return d


# =================================================================== 业务流程图
BIZ_SHAPES = {
    "subject": "term", "主体": "term",
    "doc": "manual", "单据": "manual", "form": "manual",
    "process": "process", "处理": "process",
    "store": "store", "数据存储": "store",
}


def bizflow(steps: Sequence[dict], title: Optional[str] = None,
            theme: str = "light", per_row: int = 4, dx: float = 300,
            dy: float = 240, **kw) -> Diagram:
    """业务流程图：五种基本图元的链式流程，按行折返。"""
    d = _diagram(title, theme)
    for i, st in enumerate(steps):
        kind = BIZ_SHAPES.get(str(st.get("shape", "process")), "process")
        row, col = divmod(i, per_row)
        left_to_right = row % 2 == 0
        c = col if left_to_right else per_row - 1 - col
        d.add(_node(kind, st.get("text", ""), x=200 + c * dx,
                    y=160 + row * dy, nid=str(st["id"]), auto=False))
    # 折返式流程：奇数行自右向左，箭头方向随之翻转，避免箭头逆着阅读方向
    for i in range(len(steps) - 1):
        a, b = str(steps[i]["id"]), str(steps[i + 1]["id"])
        row = i // per_row
        same_row = row == (i + 1) // per_row
        left_to_right = row % 2 == 0
        if same_row:
            src_side = "r" if left_to_right else "l"
            dst_side = "l" if left_to_right else "r"
        else:
            src_side, dst_side = "b", "t"
        d.connect(_edge(a, b, arrow="filled", src_side=src_side, dst_side=dst_side))
    return d


# ==================================================================== 工具
def _apply_layout(d: Diagram, name: str, direction: str = "down", **opts) -> None:
    if name == "none":
        return
    if name == "layered":
        if direction == "right":
            # 横向：x0 是第一层横坐标、y0 是垂直中线，dx 为层间隙、dy 为同层行距
            layout.layered(d, x0=200, y0=320, dx=170, dy=110,
                           orientation="horizontal")
        else:
            # 纵向：x0 是水平中线、y0 是第一层纵坐标，dx 为同层列距、dy 为层间隙
            layout.layered(d, x0=360, y0=140, dx=90, dy=120)
        return
    layout.apply(d, name, **opts)


def _adjacent_crossings(columns: Sequence[Sequence[Node]],
                        edges: Sequence[Edge]) -> int:
    """相邻两栏之间、按直线连接时的交叉数（Sugiyama 的标准计数）。"""
    pos = {n.id: (c, i) for c, order in enumerate(columns)
           for i, n in enumerate(order)}
    pairs = []
    for e in edges:
        a, b = pos.get(e.src), pos.get(e.dst)
        if a is None or b is None or a[0] == b[0]:
            continue
        if a[0] > b[0]:
            a, b = b, a
        if b[0] - a[0] == 1:
            pairs.append((a[0], a[1], b[1]))
    count = 0
    for i in range(len(pairs)):
        for j in range(i + 1, len(pairs)):
            c1, r1a, r1b = pairs[i]
            c2, r2a, r2b = pairs[j]
            if c1 == c2 and (r1a - r2a) * (r1b - r2b) < 0:
                count += 1
    return count


def _barycenter(order: List[Node], edges: Sequence[Edge],
                ref_ids: set, ranks: Dict[str, int]) -> List[Node]:
    """按相邻栏邻居的平均位置重排一栏；没有邻居的节点保持原位。

    这是 Sugiyama 分层布局的经典重心法（barycenter heuristic），
    每轮左右、右左各扫描一次，几轮后交叉数就会稳定下来。
    """
    current = {n.id: i for i, n in enumerate(order)}
    keys: Dict[str, tuple] = {}
    for n in order:
        positions = []
        for e in edges:
            if e.src == n.id and e.dst in ref_ids:
                positions.append(ranks[e.dst])
            elif e.dst == n.id and e.src in ref_ids:
                positions.append(ranks[e.src])
        if positions:
            keys[n.id] = (sum(positions) / len(positions), current[n.id])
        else:
            keys[n.id] = (current[n.id], current[n.id])
    return sorted(order, key=lambda n: keys[n.id])
