# -*- coding: utf-8 -*-
"""图模型：度量器、节点、连线、图。

这一层只表达"图里有什么"，不含任何绘制指令；渲染器与导出器都读同一份模型，
因此未来加 SVG 导出或改用其他后端时不必改模型。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .text import Label, from_plain
from .theme import Theme

# ------------------------------------------------------------------ 度量
class Measurer:
    """把主题解析成可度量的字体集合，并缓存字形宽度。"""

    def __init__(self, theme: Theme, scale: float = 1.0):
        self.theme = theme
        self.scale = scale
        self._fonts: Dict[tuple, object] = {}
        self._wrap = None
        self._width_cache: Dict[tuple, float] = {}
        self.size_of_kind = {
            "cn": theme.fonts.size_base,
            "cnb": theme.fonts.size_bold,
            "code": theme.fonts.size_code,
            "serif": theme.fonts.size_serif,
        }

    # 需要一个只用于度量的 draw 对象
    def _draw(self):
        if self._wrap is None:
            from PIL import Image, ImageDraw
            self._wrap = ImageDraw.Draw(Image.new("RGB", (8, 8), "white"))
        return self._wrap

    def font_of(self, kind: str):
        size = self.size_of(kind)
        return self.theme.font(kind, max(1, int(round(size * self.scale))), self._fonts)

    def size_of(self, kind: str) -> int:
        return self.size_of_kind.get(kind, self.theme.fonts.size_base)

    def textlength(self, text: str, font) -> float:
        if not text:
            return 0.0
        key = (id(font), text)
        hit = self._width_cache.get(key)
        if hit is not None:
            return hit
        w = self._draw().textlength(text, font=font)
        if len(self._width_cache) > 20000:
            self._width_cache.clear()
        self._width_cache[key] = w
        return w

    def font(self, kind: str, size: Optional[int] = None):
        """取指定像素字号的字体（图题、图例等用）。"""
        px = size if size is not None else self.size_of(kind)
        return self.theme.font(kind, max(1, int(round(px * self.scale))), self._fonts)


# ------------------------------------------------------------ 尺寸策略
#: kind -> (最小宽, 最小高, 水平留白, 垂直留白)
SIZE_TABLE: Dict[str, Tuple[float, float, float, float]] = {
    "process":     (160, 62, 52, 30),
    "term":        (120, 52, 92, 24),
    "io":          (160, 62, 60, 30),
    "predefined":  (160, 62, 62, 30),
    "manual":      (160, 62, 62, 30),
    "document":    (170, 70, 60, 34),
    "decision":    (180, 120, 70, 54),      # 特殊：菱形按文字宽的两倍留白
    "entity":      (150, 70, 70, 34),
    "store":       (170, 66, 66, 30),
    "dfd_process": (170, 110, 66, 52),
    "module":      (150, 62, 54, 28),
    "actor":       (120, 118, 44, 0),
    "usecase":     (200, 92, 96, 58),
    "state":       (140, 64, 70, 34),
    "start":       (36, 36, 0, 0),
    "stop":        (40, 40, 0, 0),
    "fork":        (220, 14, 0, 0),
    "note":        (240, 90, 56, 40),
    "cylinder":    (160, 96, 56, 56),
    "queue":       (190, 70, 56, 34),
    "cloud":       (190, 110, 64, 60),
    "component":   (190, 80, 56, 40),
    "node":        (190, 96, 56, 52),
    "artifact":    (150, 90, 48, 50),
    "package":     (200, 120, 60, 60),
    "class":       (230, 96, 52, 34),
    "lifeline":    (150, 56, 46, 20),
    "activation":  (16, 90, 0, 0),
    "entity_erd":  (230, 90, 44, 30),
    "group":       (200, 120, 40, 40),
}

DEFAULT_SIZE = (160, 66, 52, 30)


@dataclass
class Node:
    """一个图元。

    ``x``/``y`` 是**中心点**（``lifeline``/``group`` 等容器型元件的 ``y`` 是顶边）。
    ``w``/``h`` 为 ``None`` 时按文字与 :data:`SIZE_TABLE` 自动推算。
    """

    kind: str
    label: Label = field(default_factory=Label)
    x: float = 0.0
    y: float = 0.0
    w: Optional[float] = None
    h: Optional[float] = None
    id: str = ""
    attrs: List[str] = field(default_factory=list)
    meths: List[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    _geo: Optional[dict] = None

    # ---------------------------------------------------------- 尺寸
    def auto_size(self, measurer: Measurer) -> Tuple[float, float]:
        if self.kind in ("class", "entity_erd", "table"):
            return self._class_size(measurer)
        min_w, min_h, pad_x, pad_y = SIZE_TABLE.get(self.kind, DEFAULT_SIZE)
        if self.kind in ("start", "stop", "fork", "join", "activation"):
            return self.w or min_w, self.h or min_h
        tw, th = self.label.size(measurer)
        if self.kind == "actor":
            # 小人图形固定 96 高，名字画在下方，需要额外留出文字高度
            return max(min_w, tw + pad_x), 96 + th + 6
        if self.kind == "decision":
            return (max(min_w, tw * 2.0 + pad_x), max(min_h, th * 1.55 + pad_y))
        return (max(min_w, tw + pad_x), max(min_h, th + pad_y))

    def _class_size(self, measurer: Measurer) -> Tuple[float, float]:
        tw, _ = self.label.size(measurer)
        code = measurer.font("code")
        cn_font = measurer.font("cn")
        widest = tw
        for row in list(self.attrs) + list(self.meths):
            # 含中日韩字符的行会用中文字体绘制，按该字体估宽，避免溢出
            font = cn_font if any(ord(ch) > 0x2E80 for ch in row) else code
            widest = max(widest, measurer.textlength(row, font))
        rows = (1 if self.attrs else 0) + (1 if self.meths else 0)
        body = len(self.attrs) + len(self.meths)
        # 行高取两种字体中较大者，保证任何一行都放得下
        lh = max(measurer.size_of("cn"), measurer.size_of("code")) * 1.32
        h = 34 + body * lh + rows * 6 + 18
        return max(230, widest + 48), max(96, h)

    def geometry(self, measurer: Measurer) -> dict:
        if self._geo is not None:
            return self._geo
        w, h = (self.w, self.h)
        if w is None or h is None:
            aw, ah = self.auto_size(measurer)
            w = w if w is not None else aw
            h = h if h is not None else ah
        self.w, self.h = w, h
        self._geo = dict(
            x=self.x, y=self.y, w=w, h=h,
            left=self.x - w / 2, right=self.x + w / 2,
            top=self.y - h / 2, bottom=self.y + h / 2,
        )
        return self._geo

    # ---------------------------------------------------------- 锚点
    def anchor(self, side: str, measurer: Measurer) -> Tuple[float, float]:
        g = self.geometry(measurer)
        if self.kind == "lifeline":
            # 生命线用「头部框」的左右边 + 任意高度
            if side == "l":
                return g["left"], g["top"] + g["h"] * 0.5
            if side == "r":
                return g["right"], g["top"] + g["h"] * 0.5
            if side == "t":
                return g["x"], g["top"]
            return g["x"], g["bottom"]
        table = {
            "l": (g["left"], g["y"]),
            "r": (g["right"], g["y"]),
            "t": (g["x"], g["top"]),
            "b": (g["x"], g["bottom"]),
            "c": (g["x"], g["y"]),
            "tl": (g["left"], g["top"]),
            "tr": (g["right"], g["top"]),
            "bl": (g["left"], g["bottom"]),
            "br": (g["right"], g["bottom"]),
        }
        if side not in table:
            raise ValueError("未知锚点 %r，可用：%s" % (side, ", ".join(sorted(table))))
        return table[side]

    def bbox(self, measurer: Measurer) -> Tuple[float, float, float, float]:
        g = self.geometry(measurer)
        return g["left"], g["top"], g["right"], g["bottom"]


@dataclass
class Edge:
    """一条连线。``arrow`` 描述终点箭头，``start_arrow`` 描述起点箭头。"""

    src: str
    dst: str
    src_side: str = "b"
    dst_side: str = "t"
    label: Optional[Label] = None
    label_at: Optional[Tuple[float, float]] = None
    style: str = "solid"              # solid | dashed | dotted
    arrow: str = "filled"             # filled|hollow|open|diamond|diamond_h|circle|none
    start_arrow: str = "none"
    route: Optional[List[Tuple[float, float]]] = None


@dataclass
class Shape:
    """不属于图元网络的自由图元（图例、装饰文字、分隔线）。"""

    x: float
    y: float
    w: float
    h: float
    kind: str = "rect"
    text: str = ""
    color: Optional[Tuple[int, int, int]] = None


@dataclass
class Diagram:
    """图容器。坐标单位是设计像素。"""

    width: float = 1200
    height: float = 800
    title: Optional[str] = None
    subtitle: Optional[str] = None
    theme: Theme = field(default_factory=Theme)
    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)
    lanes: List[dict] = field(default_factory=list)      # {title,x,y,w,h}
    groups: List[dict] = field(default_factory=list)     # {title,x,y,w,h}
    notes: List[dict] = field(default_factory=list)      # {x,y,text,anchor,kind}
    legend: List[dict] = field(default_factory=list)     # {kind,text}
    legend_y: float = 0.0
    auto_crop: bool = True
    margin: int = 40

    _index: Dict[str, Node] = field(default_factory=dict, repr=False)

    # ---------------------------------------------------------- 组装
    def add(self, node: Node) -> Node:
        if node.id:
            if node.id in self._index:
                raise ValueError("节点 id 重复：%r" % node.id)
            self._index[node.id] = node
        self.nodes.append(node)
        return node

    def node(self, node_id: str) -> Node:
        try:
            return self._index[node_id]
        except KeyError:
            raise KeyError("找不到节点 %r" % node_id) from None

    def connect(self, edge: Edge) -> Edge:
        if edge.src not in self._index:
            raise KeyError("连线引用了不存在的节点 %r" % edge.src)
        if edge.dst not in self._index:
            raise KeyError("连线引用了不存在的节点 %r" % edge.dst)
        self.edges.append(edge)
        return edge

    # ---------------------------------------------------------- 查询
    def bounds(self, measurer: Measurer) -> Tuple[float, float, float, float]:
        """内容包围盒（含泳道/分组/图题）。"""
        xs: List[float] = []
        ys: List[float] = []
        for n in self.nodes:
            l, t, r, b = n.bbox(measurer)
            xs += [l, r]
            ys += [t, b]
        for box in list(self.lanes) + list(self.groups):
            xs += [box["x"], box["x"] + box["w"]]
            ys += [box["y"], box["y"] + box["h"]]
        if not xs:
            return 0.0, 0.0, self.width, self.height
        return min(xs), min(ys), max(xs), max(ys)


def label_of(value) -> Label:
    """把任意输入转成标签。"""
    return from_plain(value)
