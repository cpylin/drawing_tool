# -*- coding: utf-8 -*-
"""渲染器：把 :class:`diagkit.model.Diagram` 画成位图。

坐标约定
--------
* 布局始终用**设计像素**计算（``measurer.scale = 1``）。
* 绘制时几何对象一次性换算成**图像像素**（``(x + offset) * scale``），画笔拿到的
  ``geo`` 已经是图像像素，因此画笔里不需要再乘倍率。
* 字号、线宽、圆角、箭头也统一乘 ``scale``，这样超采样只提升清晰度、不改变版面比例。

同一个 Diagram 可以重复渲染（换主题、换倍率），因为几何只在渲染开始时重新计算。
"""
from __future__ import annotations

import math
import copy
from typing import Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw

from . import shapes
from .model import Diagram, Edge, Measurer, Node
from .routing import Router
from .text import Label

Point = Tuple[float, float]

_POS = ("x", "y", "left", "right", "top", "bottom")
_SIZE = ("w", "h")

#: 同侧有多条连线时，锚点沿该边分散的比例（相对边长）。
#: 圆、椭圆、菱形、云等图形不在表里——它们的边不是一个平面，只能取中点。
_SPREAD = {
    "process": 0.72, "predefined": 0.72, "entity": 0.72, "store": 0.72,
    "module": 0.72, "module_top": 0.72, "class": 0.82, "entity_erd": 0.82,
    "component": 0.72, "node": 0.72, "package": 0.72, "artifact": 0.72,
    "note": 0.72, "queue": 0.62, "state": 0.45, "term": 0.35,
    "manual": 0.45, "io": 0.45, "document": 0.5,
}
#: 只有左右两边是平直边的图形（上/下是圆角或波浪边，锚点只能取中点）。
_SPREAD_SIDES_ONLY = {"term", "document"}


class Renderer:
    """一次渲染的上下文。"""

    def __init__(self, diagram: Diagram, scale: float = 2.0):
        if scale <= 0:
            raise ValueError("scale 必须为正数")
        self.diagram = diagram
        self.scale = float(scale)
        # 画笔统一读 r.theme.line_width / edge_width / radius，这里给一份"已乘倍率"的浅拷贝，
        # 画笔就不必关心 scale 了。
        theme = copy.copy(diagram.theme)
        theme.line_width = max(1, int(round(diagram.theme.line_width * self.scale)))
        theme.edge_width = max(1, int(round(diagram.theme.edge_width * self.scale)))
        theme.radius = diagram.theme.radius * self.scale
        self.theme = theme
        self.measurer = Measurer(theme, 1.0)
        self.offset: Point = (0.0, 0.0)
        self.geos: Dict[int, dict] = {}
        self.edge_anchors: Dict[int, dict] = {}
        self._label_jobs: List[Tuple[Label, List[Point], Optional[Point]]] = []
        self.placed_labels: List[Tuple[float, float, float, float]] = []
        self.placed_label_items: List[Tuple[str, Tuple[float, float, float, float]]] = []
        self.img: Optional[Image.Image] = None
        self.draw: Optional[ImageDraw.ImageDraw] = None
        self.width = 100.0
        self.height = 100.0

        self.lw = theme.line_width
        self.ew = theme.edge_width
        self.radius = theme.radius

    # ------------------------------------------------------------ 换算
    def sx(self, v: float) -> float:
        return (v + self.offset[0]) * self.scale

    def sy(self, v: float) -> float:
        return (v + self.offset[1]) * self.scale

    def gp(self, p: Point) -> Point:
        return (self.sx(p[0]), self.sy(p[1]))

    def geo(self, node: Node) -> dict:
        return self.geos[id(node)]

    def _scaled_geo(self, g: dict) -> dict:
        out = {}
        for k, v in g.items():
            if k in _POS:
                out[k] = (v + self.offset[0] if k in ("x", "left", "right") else
                          v + self.offset[1]) * self.scale
            elif k in _SIZE:
                out[k] = v * self.scale
            else:
                out[k] = v
        return out

    # ------------------------------------------------------------ 字体
    def font(self, kind: str, size: Optional[int] = None):
        return self.measurer.font(kind, size)

    def pick_kind(self, text: str, prefer: str = "serif") -> str:
        """含中日韩字符时选中文字体，否则用 prefer 指定族。"""
        if not text:
            return prefer
        return "cn" if any(ord(ch) > 0x2E80 for ch in text) else prefer

    def _line_height(self, kind: str) -> float:
        return 1.42 * self.measurer.size_of(kind) * self.scale

    def line_height(self, kind: str) -> float:
        """图像像素下的行高，供画笔使用。"""
        return self._line_height(kind)

    # ------------------------------------------------------------ 文字
    def draw_text_line(self, text: str, center: Point, kind: str = "cn",
                       anchor: str = "mm", font=None):
        """``center`` 是图像像素坐标。"""
        if not text:
            return
        f = font or self.font(kind)
        self.draw.text(center, text, font=f, fill=self.theme.palette.ink, anchor=anchor)

    def text(self, label: Label, geo: dict, align: str = "center"):
        """在图像像素的 geo 内居中绘制多行混排文字。"""
        if label is None or label.empty:
            return
        rows = label.measured_lines(self.measurer)
        if not rows:
            return
        heights = [max((self._line_height(k) for _, k in row), default=0.0) for row in rows]
        total = sum(heights)
        y = geo["y"] - total / 2
        for row, h in zip(rows, heights):
            width = sum(self.measurer.textlength(t, self.font(k)) for t, k in row)
            if align == "left":
                x = geo["left"] + 10 * self.scale
            else:
                x = geo["x"] - width / 2
            for text, kind in row:
                f = self.font(kind)
                self.draw.text((x, y + h / 2), text, font=f,
                               fill=self.theme.palette.ink, anchor="lm")
                x += self.measurer.textlength(text, f)
            y += h

    # ------------------------------------------------------------ 主流程
    def render(self) -> Image.Image:
        d = self.diagram
        # 1) 设计像素几何
        self.measurer.scale = 1.0
        base: Dict[int, dict] = {}
        for i, n in enumerate(d.nodes):
            n._geo = None
            base[i] = dict(n.geometry(self.measurer))
        min_x, min_y, max_x, max_y = self._bounds(base)

        margin = d.margin
        self.offset = (margin - min_x, margin - min_y + (56.0 if d.title else 0.0))
        self.width = (max_x - min_x) + margin * 2
        self.height = (max_y - min_y) + margin * 2 + (56.0 if d.title else 0.0)
        # 布局完成，切换到绘制倍率：此后字体按 size*scale 打开，度量返回图像像素
        self.measurer.scale = self.scale

        # 2) 画布
        self.img = Image.new("RGB",
                             (max(1, int(self.width * self.scale)),
                              max(1, int(self.height * self.scale))),
                             self.theme.palette.canvas)
        self.draw = ImageDraw.Draw(self.img)

        # 3) 换算后的几何
        for i, n in enumerate(d.nodes):
            self.geos[id(n)] = self._scaled_geo(base[i])

        # 3.5) 端口分配：同一侧的多条边沿边分散锚点，避免所有线挤在一个点上
        self.edge_anchors = self._assign_anchors()

        # 4) 底图
        for lane in d.lanes:
            self._lane(lane)
        for group in d.groups:
            self._group(group)

        # 5) 图题
        if d.title:
            self._title(d.title, d.subtitle)

        # 6) 连线（路由器与坐标统一用图像像素）
        blocked = [self._bbox(n) for n in d.nodes if n.kind not in
                   ("lifeline", "activation", "start", "stop", "fork", "join")]
        # 给绕行通道留出页边距之内的空间：超出画布的路由与标签会被裁掉。
        pad = margin * self.scale * 0.35
        ext_x = (max([b[2] for b in blocked] or [self.width * self.scale - pad])) + pad
        ext_y = (max([b[3] for b in blocked] or [self.height * self.scale - pad])) + pad
        router = Router(ext_x, ext_y, step=max(4, int(self.theme.grid * self.scale)))
        self._label_jobs = []
        for edge in d.edges:
            self._edge(edge, router, blocked)

        # 7) 图元
        for n in d.nodes:
            painter = shapes.SHAPES.get(n.kind, shapes.SHAPES["process"])
            painter(self, n, self.geos[id(n)])

        # 7.5) 连线标签最后画：先排的标签占位，后排放到空处；画在图元之上，
        # 顺序图的消息文字才不会被激活条盖住。
        self._draw_edge_labels(blocked)

        # 8) 注释与图例
        for note in d.notes:
            self._note(note)
        if d.legend:
            self._legend(d.legend, d.legend_y or (self.height - margin * 0.8))
        return self.img

    # ------------------------------------------------------------ 内部
    def _bounds(self, base: dict) -> Tuple[float, float, float, float]:
        d = self.diagram
        xs: List[float] = []
        ys: List[float] = []
        for g in base.values():
            xs += [g["left"], g["right"]]
            ys += [g["top"], g["bottom"]]
        for box in list(d.lanes) + list(d.groups):
            xs += [box["x"], box["x"] + box["w"]]
            ys += [box["y"], box["y"] + box["h"]]
        for note in d.notes:
            xs.append(note["x"])
            ys.append(note["y"])
        if not xs:
            return 0.0, 0.0, 100.0, 100.0
        return min(xs), min(ys), max(xs), max(ys)

    def _bbox(self, node: Node) -> Tuple[float, float, float, float]:
        g = self.geos[id(node)]
        return g["left"], g["top"], g["right"], g["bottom"]

    def _assign_anchors(self) -> Dict[int, dict]:
        """给每条边分配起止锚点；同一侧的多条边按对端位置排序后分散。

        这就是绘图库里的“端口分配”（port assignment）：一条公共边上的不同
        连接点能显著减少连线在节点附近互相压线、交叉。
        """
        d = self.diagram
        groups: Dict[tuple, List[tuple]] = {}
        owners: Dict[tuple, Node] = {}
        for index, edge in enumerate(d.edges):
            if edge.route is not None or edge.src == edge.dst:
                continue
            src, dst = d.node(edge.src), d.node(edge.dst)
            for role, node, side, other in (("src", src, edge.src_side, dst),
                                            ("dst", dst, edge.dst_side, src)):
                horizontal = side in ("l", "r")
                # 水平边按对端的 y 排序，竖直边按对端的 x 排序
                key = (id(node), side)
                groups.setdefault(key, []).append(
                    (other.y if horizontal else other.x, index, edge, role))
                owners[key] = node

        anchors: Dict[int, dict] = {}
        for key, items in groups.items():
            items.sort(key=lambda item: (item[0], item[1]))
            points = self._side_anchor_points(owners[key], key[1], len(items))
            for (_order, _index, edge, role), point in zip(items, points):
                anchors.setdefault(id(edge), {})[role] = point

        for edge in d.edges:
            entry = anchors.setdefault(id(edge), {})
            if edge.route is not None:
                continue
            entry.setdefault("src", self._anchor(d.node(edge.src), edge.src_side))
            entry.setdefault("dst", self._anchor(d.node(edge.dst), edge.dst_side))
        return anchors

    def _side_anchor_points(self, node: Node, side: str, count: int) -> List[Point]:
        default = self._anchor(node, side)
        fraction = _SPREAD.get(node.kind)
        if count <= 1 or fraction is None or side not in ("l", "r", "t", "b"):
            return [default] * count
        if side in ("t", "b") and node.kind in _SPREAD_SIDES_ONLY:
            return [default] * count
        g = self.geos[id(node)]
        horizontal = side in ("l", "r")
        span = (g["h"] if horizontal else g["w"]) * fraction
        # 单侧边太短时不分散，免得锚点落到圆角或边框外
        if span < count * 8 * self.scale:
            return [default] * count
        start = (g["y"] if horizontal else g["x"]) - span / 2
        step = span / (count - 1)
        points: List[Point] = []
        for i in range(count):
            offset = start + i * step
            if horizontal:
                points.append((g["right"] if side == "r" else g["left"], offset))
            else:
                points.append((offset, g["bottom"] if side == "b" else g["top"]))
        return points

    def _anchor(self, node: Node, side: str) -> Point:
        g = self.geos[id(node)]
        if node.kind == "lifeline":
            table = {"l": (g["left"], g["top"] + 28 * self.scale),
                     "r": (g["right"], g["top"] + 28 * self.scale),
                     "t": (g["x"], g["top"]), "b": (g["x"], g["bottom"]),
                     "c": (g["x"], g["y"])}
            return table.get(side, table["c"])
        table = {
            "l": (g["left"], g["y"]), "r": (g["right"], g["y"]),
            "t": (g["x"], g["top"]), "b": (g["x"], g["bottom"]),
            "c": (g["x"], g["y"]),
            "tl": (g["left"], g["top"]), "tr": (g["right"], g["top"]),
            "bl": (g["left"], g["bottom"]), "br": (g["right"], g["bottom"]),
        }
        if side not in table:
            raise ValueError("未知锚点 %r" % side)
        return table[side]

    def _lane(self, lane: dict):
        d = self.draw
        p = self.theme.palette
        x, y = self.sx(lane["x"]), self.sy(lane["y"])
        w, h = lane["w"] * self.scale, lane["h"] * self.scale
        d.rectangle([x, y, x + w, y + h], outline=p.grid, width=self.lw)
        head = 42 * self.scale
        d.rectangle([x, y, x + w, y + head], fill=p.fill_lane, outline=p.grid, width=self.lw)
        f = self.font("cnb")
        d.text((x + w / 2, y + head / 2), lane["title"], font=f, fill=p.band, anchor="mm")

    def _group(self, group: dict):
        d = self.draw
        p = self.theme.palette
        x, y = self.sx(group["x"]), self.sy(group["y"])
        w, h = group["w"] * self.scale, group["h"] * self.scale
        d.rectangle([x, y, x + w, y + h], outline=p.outline_entity, width=self.lw)
        if group.get("title"):
            f = self.font("cnb")
            d.text((x + w / 2, y + 20 * self.scale), group["title"], font=f,
                   fill=p.band, anchor="mm")

    def _title(self, title: str, subtitle: Optional[str]):
        p = self.theme.palette
        cx = self.width * self.scale / 2
        f = self.font("cnb", self.theme.fonts.size_title)
        self.draw.text((cx, 30 * self.scale), title, font=f, fill=p.title, anchor="mm")
        if subtitle:
            fs = self.font("cn")
            self.draw.text((cx, 60 * self.scale), subtitle, font=fs, fill=p.muted,
                           anchor="mm")

    def _edge(self, edge: Edge, router: Router, blocked):
        src, dst = self.diagram.node(edge.src), self.diagram.node(edge.dst)
        anchor = self.edge_anchors.get(id(edge), {})
        start = anchor.get("src") or self._anchor(src, edge.src_side)
        end = anchor.get("dst") or self._anchor(dst, edge.dst_side)
        # 路由在图像像素上进行，起点终点都已是图像像素
        if edge.route:
            pts = [self.gp(p) for p in edge.route]
        else:
            pts = router.route(start, end, blocked, (edge.src_side, edge.dst_side))
        color = self.theme.palette.ink
        if edge.style == "dashed":
            shapes.draw_dashed(self.draw, pts, self.ew, color, 12 * self.scale, 9 * self.scale)
        elif edge.style == "dotted":
            shapes.draw_dotted(self.draw, pts, self.ew, color, 3 * self.scale, 6 * self.scale)
        else:
            self.draw.line(pts, fill=color, width=self.ew, joint="curve")
        if edge.arrow and edge.arrow != "none":
            shapes.draw_head(self.draw, pts[-2], pts[-1], edge.arrow, self.ew, color, self.scale)
        if edge.start_arrow and edge.start_arrow != "none":
            shapes.draw_head(self.draw, pts[1], pts[0], edge.start_arrow, self.ew, color,
                             self.scale)
        if edge.label is not None and not edge.label.empty:
            self._label_jobs.append((edge.label, pts, edge.label_at))
        # 登记这条线的通道：后面的线会绕开它，而不是直接压过去
        router.occupy(pts)

    # ------------------------------------------------------------ 标签放置
    def _draw_edge_labels(self, blocked):
        """贪心标签避让：先放先占位，后来者换候选位置。"""
        placed: List[Tuple[float, float, float, float]] = []
        items: List[Tuple[str, Tuple[float, float, float, float]]] = []
        # 生命线/激活条是贯穿整列的容器，不能当成标签障碍，否则消息标签无处可放
        node_boxes = [self._bbox(n) for n in self.diagram.nodes
                      if n.kind not in ("lifeline", "activation", "group")]
        for label, pts, at in self._label_jobs:
            text = label.text()
            if not text:
                continue
            # 含中日韩字符时必须用中文字体，否则衬线字体会渲染成方块
            kind = self.pick_kind(text, "serif")
            f = self.font(kind)
            tw = self.measurer.textlength(text, f)
            th = self._line_height(kind)
            candidates = self._label_candidates(pts, at, tw, th)
            anchor_x, anchor_y = self._label_anchor(pts, at)
            best = None
            best_score = None
            for cx, cy in candidates:
                box = (cx - tw / 2 - 2 * self.scale, cy - th / 2 - 2 * self.scale,
                       cx + tw / 2 + 2 * self.scale, cy + th / 2 + 2 * self.scale)
                overlap = sum(_overlap_area(box, other) for other in placed)
                overlap += sum(_overlap_area(box, other) for other in node_boxes)
                # 先保证不压字/不压框，同等条件下选离线段中点最近的
                dist = (cx - anchor_x) ** 2 + (cy - anchor_y) ** 2
                score = (overlap, dist)
                if best_score is None or score < best_score:
                    best, best_score = (cx, cy, box), score
            if best is None:
                continue
            cx, cy, box = best
            # 画布边缘的标签往里收一点，避免像 ERD 底部那样被裁掉半截
            half_w = tw / 2 + 2 * self.scale
            half_h = th / 2 + 2 * self.scale
            edge_pad = 4 * self.scale
            cx = min(max(cx, half_w + edge_pad),
                     self.width * self.scale - half_w - edge_pad)
            cy = min(max(cy, half_h + edge_pad),
                     self.height * self.scale - half_h - edge_pad)
            box = (cx - half_w, cy - half_h, cx + half_w, cy + half_h)
            self.draw.text((cx, cy), text, font=f,
                           fill=self.theme.palette.ink, anchor="mm")
            placed.append(box)
            items.append((text, box))
        self.placed_labels = placed
        self.placed_label_items = items

    def _label_anchor(self, pts: Sequence[Point], at: Optional[Point]) -> Point:
        if at is not None:
            return self.gp(at)
        if not pts:
            return (0.0, 0.0)
        best, best_len = (pts[0], pts[0]), 0.0
        for a, b in zip(pts, pts[1:]):
            length = abs(b[0] - a[0]) + abs(b[1] - a[1])
            if length > best_len:
                best, best_len = (a, b), length
        return ((best[0][0] + best[1][0]) / 2, (best[0][1] + best[1][1]) / 2)

    def _label_candidates(self, pts: Sequence[Point], at: Optional[Point],
                          tw: float, th: float) -> List[Point]:
        scale = self.scale
        near, far = 6.0 * scale, 18.0 * scale
        candidates: List[Point] = []
        if at is not None:
            candidates.append(self.gp(at))
        segment = None
        best_len = 0.0
        for a, b in zip(pts, pts[1:]):
            length = abs(b[0] - a[0]) + abs(b[1] - a[1])
            if length > best_len:
                segment, best_len = (a, b), length
        if segment is None:
            return candidates or [(0.0, 0.0)]
        (ax, ay), (bx, by) = segment
        horizontal = abs(ay - by) < 1
        for t in (0.5, 0.4, 0.6, 0.3, 0.7):
            x, y = ax + (bx - ax) * t, ay + (by - ay) * t
            if horizontal:
                for off in (near + th / 2, -(near + th / 2),
                            far + th / 2, -(far + th / 2)):
                    candidates.append((x, y + off))
            else:
                for off in (near + tw / 2, -(near + tw / 2),
                            far + tw / 2, -(far + tw / 2)):
                    candidates.append((x + off, y))
        # 端点外侧：竖线夹在两个方框之间时，侧边往往放不下，
        # 此时把标签放到线段两端之外通常就有空位。
        if horizontal:
            for x in (ax, bx):
                for off in (near + tw / 2, -(near + tw / 2)):
                    candidates.append((x + off, ay))
        else:
            for y in (ay, by):
                for off in (near + th / 2, -(near + th / 2)):
                    candidates.append((ax, y + off))
        # 显式位置若被占，也在它附近找空位
        if at is not None:
            px, py = self.gp(at)
            for off in (12 * scale, -12 * scale, 24 * scale, -24 * scale):
                candidates.append((px, py + off))
                candidates.append((px + off, py))
        return candidates

    def _note(self, note: dict):
        f = self.font("cn")
        self.draw.text((self.sx(note["x"]), self.sy(note["y"])), note["text"],
                       font=f, fill=self.theme.palette.muted,
                       anchor=note.get("anchor", "lm"))

    def _legend(self, items: Sequence[dict], y: float):
        x = 60.0
        size = 86.0
        f = self.font("cn")
        for item in items:
            kind = item["kind"]
            g = self._scaled_geo(dict(x=x, y=y, w=size, h=40,
                                      left=x, right=x + size,
                                      top=y - 20, bottom=y + 20))
            probe = Node(kind="process", w=size, h=40, x=x, y=y)
            painter = shapes.SHAPES.get(kind, shapes.SHAPES["process"])
            painter(self, probe, g)
            label = item.get("text", "")
            tw = self.measurer.textlength(label, f)
            self.draw.text((self.sx(x + size + 14), self.sy(y)), label,
                           font=f, fill=self.theme.palette.ink, anchor="lm")
            x += size + (14 + tw / self.scale) + 44

    # ------------------------------------------------------------ 输出
    def save(self, path: str) -> str:
        img = self.render()
        if not path.lower().endswith(".png"):
            path += ".png"
        img.save(path, dpi=(220, 220))
        return path


def _overlap_area(a, b) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if w > 0 and h > 0 else 0.0


def render(diagram: Diagram, scale: float = 2.0) -> Image.Image:
    return Renderer(diagram, scale).render()
