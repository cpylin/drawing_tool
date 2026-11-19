# -*- coding: utf-8 -*-
"""图元画笔与箭头。

约定
----
* 画笔签名统一为 ``paint(r, node, geo)``；``geo`` 已经是**图像像素**坐标。
* 所有"细节尺寸"（折角、内嵌线、小人肢体）都要乘 ``r.scale``，否则超采样时
  细节会显得过小。线宽直接用 ``r.theme.line_width``（渲染器已乘过倍率）。
* 新增图元：写一个函数并用 ``@shape("kind")`` 登记，``presets`` 与规格解析器
  自动支持。
"""
from __future__ import annotations

import math
from typing import Callable, Dict, List, Sequence, Tuple

Point = Tuple[float, float]

SHAPES: Dict[str, Callable] = {}


def shape(*kinds: str):
    def deco(fn):
        for kind in kinds:
            SHAPES[kind] = fn
        return fn
    return deco


def _u(r, v: float) -> float:
    """设计像素 -> 图像像素。"""
    return v * r.scale


def _box(geo) -> List[float]:
    return [geo["left"], geo["top"], geo["right"], geo["bottom"]]


def _poly(draw, pts: Sequence[Point], fill, outline, width):
    draw.polygon(pts, fill=fill)
    draw.line(list(pts) + [pts[0]], fill=outline, width=width, joint="curve")


# ---------------------------------------------------------------- 流程图
@shape("process", "module", "module_top")
def _process(r, node, geo):
    p = r.theme.palette
    fill = p.fill_term if node.kind == "module_top" else p.fill_process
    outline = p.outline_term if node.kind == "module_top" else p.line
    r.draw.rectangle(_box(geo), fill=fill, outline=outline, width=r.theme.line_width)
    r.text(node.label, geo)


@shape("term")
def _term(r, node, geo):
    p = r.theme.palette
    r.draw.rounded_rectangle(_box(geo), radius=geo["h"] / 2, fill=p.fill_term,
                             outline=p.outline_term, width=r.theme.line_width)
    r.text(node.label, geo)


@shape("decision")
def _decision(r, node, geo):
    p = r.theme.palette
    pts = [(geo["x"], geo["top"]), (geo["right"], geo["y"]),
           (geo["x"], geo["bottom"]), (geo["left"], geo["y"])]
    _poly(r.draw, pts, p.fill_decision, p.outline_decision, r.theme.line_width)
    r.text(node.label, geo)


@shape("io")
def _io(r, node, geo):
    p = r.theme.palette
    skew = min(_u(r, 26), geo["w"] * 0.08)
    pts = [(geo["left"] + skew, geo["top"]), (geo["right"], geo["top"]),
           (geo["right"] - skew, geo["bottom"]), (geo["left"], geo["bottom"])]
    _poly(r.draw, pts, (255, 251, 240), p.line, r.theme.line_width)
    r.text(node.label, geo)


@shape("predefined")
def _predefined(r, node, geo):
    p = r.theme.palette
    d = r.draw
    d.rectangle(_box(geo), fill=(248, 248, 252), outline=p.line, width=r.theme.line_width)
    for x in (geo["left"] + _u(r, 20), geo["right"] - _u(r, 20)):
        d.line([(x, geo["top"]), (x, geo["bottom"])], fill=p.line, width=r.theme.line_width)
    r.text(node.label, geo)


@shape("manual")
def _manual(r, node, geo):
    p = r.theme.palette
    k = _u(r, 18)
    pts = [(geo["left"], geo["top"]), (geo["right"], geo["top"]),
           (geo["right"] - k, geo["bottom"]), (geo["left"] + k, geo["bottom"])]
    _poly(r.draw, pts, (250, 250, 250), p.line, r.theme.line_width)
    r.text(node.label, geo)


@shape("document")
def _document(r, node, geo):
    p = r.theme.palette
    d = r.draw
    wave = _u(r, 14)
    l, t, rr, b = geo["left"], geo["top"], geo["right"], geo["bottom"] - wave
    d.rectangle([l, t, rr, b], fill=p.fill_process, outline=p.line, width=r.theme.line_width)
    d.arc([l, b - wave, rr, geo["bottom"] + wave], 0, 180, fill=p.line,
          width=r.theme.line_width)
    r.text(node.label, dict(geo, y=geo["y"] - wave / 2))


# -------------------------------------------------------------------- DFD
@shape("entity")
def _entity(r, node, geo):
    p = r.theme.palette
    d = r.draw
    d.rectangle(_box(geo), fill=p.fill_entity, outline=p.outline_entity,
                width=r.theme.line_width)
    k = _u(r, 6)
    d.rectangle([geo["left"] + k, geo["top"] + k, geo["right"] - k, geo["bottom"] - k],
                outline=p.outline_entity, width=max(1, r.theme.line_width - 1))
    r.text(node.label, geo)


@shape("store")
def _store(r, node, geo):
    p = r.theme.palette
    d = r.draw
    d.rectangle(_box(geo), fill=p.fill_store, outline=p.outline_store,
                width=r.theme.line_width)
    x = geo["left"] + _u(r, 34)
    d.line([(x, geo["top"]), (x, geo["bottom"])], fill=p.outline_store,
           width=r.theme.line_width)
    r.text(node.label, dict(geo, x=(x + geo["right"]) / 2))


@shape("dfd_process")
def _dfd_process(r, node, geo):
    p = r.theme.palette
    r.draw.ellipse(_box(geo), fill=(255, 253, 245), outline=p.outline_decision,
                   width=r.theme.line_width)
    r.text(node.label, geo)


@shape("cylinder")
def _cylinder(r, node, geo):
    p = r.theme.palette
    d = r.draw
    k = min(geo["h"] * 0.28, geo["w"] * 0.22)
    l, rr, t, b = geo["left"], geo["right"], geo["top"], geo["bottom"]
    d.rectangle([l, t + k / 2, rr, b - k / 2], fill=p.fill_store, outline=p.outline_store,
                width=r.theme.line_width)
    d.ellipse([l, t, rr, t + k], fill=p.fill_store, outline=p.outline_store,
              width=r.theme.line_width)
    d.arc([l, b - k, rr, b], 0, 180, fill=p.outline_store, width=r.theme.line_width)
    r.text(node.label, dict(geo, y=geo["y"] + k * 0.25))


@shape("queue")
def _queue(r, node, geo):
    p = r.theme.palette
    d = r.draw
    d.rectangle(_box(geo), fill=p.fill_store, outline=p.outline_store,
                width=r.theme.line_width)
    k = _u(r, 26)
    d.ellipse([geo["right"] - k, geo["top"], geo["right"] + k * 0.4, geo["bottom"]],
              fill=p.fill_store, outline=p.outline_store, width=r.theme.line_width)
    r.text(node.label, dict(geo, x=geo["x"] - _u(r, 8)))


@shape("cloud")
def _cloud(r, node, geo):
    p = r.theme.palette
    d = r.draw
    w, h = geo["w"], geo["h"]
    bumps = [(0.22, 0.32), (0.46, 0.20), (0.72, 0.30), (0.85, 0.58),
             (0.62, 0.76), (0.34, 0.74)]
    for fx, fy in bumps:
        rad = min(w, h) * 0.30
        cx, cy = geo["left"] + w * fx, geo["top"] + h * fy
        d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad],
                  fill=p.fill_entity, outline=p.outline_entity, width=r.theme.line_width)
    r.text(node.label, geo)


# ------------------------------------------------------------------- 结构
@shape("component")
def _component(r, node, geo):
    p = r.theme.palette
    d = r.draw
    d.rectangle(_box(geo), fill=(246, 249, 254), outline=p.line, width=r.theme.line_width)
    tab_w, tab_h = _u(r, 30), _u(r, 16)
    d.rectangle([geo["left"], geo["top"], geo["left"] + tab_w, geo["top"] + tab_h],
                fill=(255, 255, 255), outline=p.line, width=r.theme.line_width)
    r.text(node.label, dict(geo, x=geo["x"] + tab_w / 4))


@shape("node")
def _node3d(r, node, geo):
    p = r.theme.palette
    d = r.draw
    off = _u(r, 12)
    d.polygon([(geo["left"] + off, geo["top"]), (geo["right"], geo["top"]),
               (geo["right"], geo["bottom"] - off), (geo["left"], geo["bottom"] - off)],
              fill=(246, 249, 254), outline=p.line)
    d.rectangle([geo["left"], geo["top"] + off, geo["right"] - off, geo["bottom"]],
                fill=(255, 255, 255), outline=p.line, width=r.theme.line_width)
    r.text(node.label, dict(geo, y=geo["y"] + off / 2, x=geo["x"] - off / 2))


@shape("artifact")
def _artifact(r, node, geo):
    p = r.theme.palette
    d = r.draw
    fold = _u(r, 18)
    pts = [(geo["left"], geo["top"]), (geo["right"] - fold, geo["top"]),
           (geo["right"], geo["top"] + fold), (geo["right"], geo["bottom"]),
           (geo["left"], geo["bottom"])]
    _poly(d, pts, (250, 250, 252), p.line, r.theme.line_width)
    d.line([(geo["right"] - fold, geo["top"]), (geo["right"] - fold, geo["top"] + fold),
            (geo["right"], geo["top"] + fold)], fill=p.line, width=r.theme.line_width)
    r.text(node.label, geo)


@shape("package")
def _package(r, node, geo):
    p = r.theme.palette
    d = r.draw
    tab_h = _u(r, 26)
    d.rectangle([geo["left"], geo["top"], geo["left"] + geo["w"] * 0.42, geo["top"] + tab_h],
                fill=(236, 242, 252), outline=p.line, width=r.theme.line_width)
    d.rectangle([geo["left"], geo["top"] + tab_h, geo["right"], geo["bottom"]],
                fill=(255, 255, 255), outline=p.line, width=r.theme.line_width)
    r.text(node.label, dict(geo, y=geo["top"] + tab_h + (geo["h"] - tab_h) / 2))


@shape("note")
def _note(r, node, geo):
    p = r.theme.palette
    d = r.draw
    fold = _u(r, 16)
    pts = [(geo["left"] + fold, geo["top"]), (geo["right"], geo["top"]),
           (geo["right"], geo["bottom"] - fold), (geo["right"] - fold, geo["bottom"]),
           (geo["left"], geo["bottom"]), (geo["left"], geo["top"] + fold)]
    _poly(d, pts, p.fill_note, p.outline_note, r.theme.line_width)
    d.line([(geo["left"] + fold, geo["top"]), (geo["right"] - fold, geo["bottom"])],
           fill=p.outline_note, width=max(1, r.theme.line_width - 1))
    r.text(node.label, geo)


# ------------------------------------------------------------------- UML
@shape("actor")
def _actor(r, node, geo):
    p = r.theme.palette
    d = r.draw
    cx = geo["x"]
    head_r = _u(r, 15)
    top = geo["top"] + _u(r, 2)
    d.ellipse([cx - head_r, top, cx + head_r, top + 2 * head_r], outline=p.line,
              width=r.theme.line_width)
    neck = top + 2 * head_r
    d.line([(cx, neck), (cx, neck + _u(r, 34))], fill=p.line, width=r.theme.line_width)
    d.line([(cx - _u(r, 30), neck + _u(r, 14)), (cx + _u(r, 30), neck + _u(r, 14))],
           fill=p.line, width=r.theme.line_width)
    d.line([(cx, neck + _u(r, 34)), (cx - _u(r, 22), neck + _u(r, 62))],
           fill=p.line, width=r.theme.line_width)
    d.line([(cx, neck + _u(r, 34)), (cx + _u(r, 22), neck + _u(r, 62))],
           fill=p.line, width=r.theme.line_width)
    rows = node.label.measured_lines(r.measurer)
    text_h = sum(max(r.line_height(k) for _, k in row) if row else 0 for row in rows)
    label_geo = dict(geo, y=geo["bottom"] - text_h / 2 - _u(r, 4))
    r.text(node.label, label_geo)


@shape("usecase")
def _usecase(r, node, geo):
    p = r.theme.palette
    r.draw.ellipse(_box(geo), fill=p.fill_actor, outline=p.outline_actor,
                   width=r.theme.line_width)
    r.text(node.label, geo)


@shape("state")
def _state(r, node, geo):
    p = r.theme.palette
    r.draw.rounded_rectangle(_box(geo), radius=r.theme.radius, fill=p.fill_state,
                             outline=p.outline_state, width=r.theme.line_width)
    r.text(node.label, geo)


@shape("state_initial", "start")
def _start(r, node, geo):
    p = r.theme.palette
    r.draw.ellipse(_box(geo), fill=p.ink, outline=p.ink)


@shape("state_final", "stop")
def _stop(r, node, geo):
    p = r.theme.palette
    r.draw.ellipse(_box(geo), outline=p.ink, width=max(2, r.theme.line_width))
    inset = _u(r, 6)
    r.draw.ellipse([geo["left"] + inset, geo["top"] + inset,
                    geo["right"] - inset, geo["bottom"] - inset], fill=p.ink)


@shape("fork", "join")
def _fork(r, node, geo):
    r.draw.rectangle(_box(geo), fill=(70, 80, 100), outline=(70, 80, 100))


@shape("lifeline")
def _lifeline(r, node, geo):
    p = r.theme.palette
    d = r.draw
    head_h = _u(r, 56)
    d.rectangle([geo["left"], geo["top"], geo["right"], geo["top"] + head_h],
                fill=p.fill_term, outline=p.outline_term, width=r.theme.line_width)
    d.line([(geo["x"], geo["top"] + head_h), (geo["x"], geo["bottom"])],
           fill=p.muted, width=max(1, r.theme.line_width - 1))
    r.text(node.label, dict(geo, y=geo["top"] + head_h / 2, h=head_h))


@shape("activation")
def _activation(r, node, geo):
    r.draw.rectangle(_box(geo), fill=r.theme.palette.fill_activation,
                     outline=r.theme.palette.outline_term, width=max(1, r.theme.line_width - 1))


@shape("group")
def _group(r, node, geo):
    p = r.theme.palette
    r.draw.rectangle(_box(geo), outline=p.outline_entity, width=r.theme.line_width)
    if node.label is not None and not node.label.empty:
        r.text(node.label, dict(geo, y=geo["top"] + _u(r, 22), h=_u(r, 44)))


# --------------------------------------------------------------- 类图 / ERD
def _compartment(r, node, geo, header_h, body_rows, head_fill, outline):
    """类框/表框的通用画法：标题栏 + 分隔线 + 逐行文字。

    行内文字按内容选字体：ASCII 用等宽（对齐 `- name: type`），含中文的行改用
    中文字体，避免等宽西文字体缺字形渲染成方块。
    """
    p = r.theme.palette
    d = r.draw
    l, t, rr, b = geo["left"], geo["top"], geo["right"], geo["bottom"]
    d.rectangle([l, t, rr, b], fill=p.canvas, outline=outline, width=r.theme.line_width)
    d.rectangle([l, t, rr, t + header_h], fill=head_fill, outline=outline,
                width=r.theme.line_width)
    title = node.label.text() if node.label.lines else ""
    r.draw_text_line(title, (geo["x"], t + header_h / 2), "cnb")
    y = t + header_h
    for group in body_rows:
        if not group:
            continue
        d.line([(l, y), (rr, y)], fill=outline, width=max(1, r.theme.line_width - 1))
        for row in group:
            kind = r.pick_kind(row, "code")
            lh = r.line_height(kind)
            r.draw_text_line(row, (l + _u(r, 12), y + lh / 2), kind,
                             anchor="lm", font=r.font(kind))
            y += lh


@shape("class")
def _class(r, node, geo):
    p = r.theme.palette
    _compartment(r, node, geo, _u(r, 34), [node.attrs, node.meths],
                 p.fill_class_header, p.outline_class)


@shape("entity_erd", "table")
def _entity_erd(r, node, geo):
    p = r.theme.palette
    _compartment(r, node, geo, _u(r, 30), [node.attrs],
                 p.fill_store, p.outline_store)


# ------------------------------------------------------------------ 箭头
def draw_head(draw, a: Point, b: Point, kind: str, width: int, color, zoom: float = 1.0):
    """在 ``b`` 处画箭头。``zoom`` 是渲染倍率，用于放大箭头本身。"""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy) or 1.0
    ux, uy = dx / length, dy / length
    px, py = -uy, ux

    def tri(size, fill):
        size *= zoom
        bx, by = b[0] - ux * size, b[1] - uy * size
        half = size * 0.42
        draw.polygon([(b[0], b[1]),
                      (bx + px * half, by + py * half),
                      (bx - px * half, by - py * half)],
                     fill=fill, outline=color)

    if kind in ("filled", "solid"):
        tri(16, color)
    elif kind == "hollow":
        tri(19, (255, 255, 255))
    elif kind == "open":
        size, half = 16 * zoom, 7.0 * zoom
        bx, by = b[0] - ux * size, b[1] - uy * size
        draw.line([(bx + px * half, by + py * half), (b[0], b[1]),
                   (bx - px * half, by - py * half)], fill=color, width=width)
    elif kind in ("diamond", "diamond_h"):
        d = 26 * zoom
        tx, ty = b[0] - ux * d, b[1] - uy * d
        mx, my = b[0] - ux * d / 2, b[1] - uy * d / 2
        w = d * 0.38
        draw.polygon([(b[0], b[1]), (mx + px * w, my + py * w), (tx, ty),
                      (mx - px * w, my - py * w)],
                     fill=color if kind == "diamond" else (255, 255, 255),
                     outline=color)
    elif kind == "circle":
        rad = 6 * zoom
        draw.ellipse([b[0] - rad, b[1] - rad, b[0] + rad, b[1] + rad], fill=color)
    elif kind == "bar":
        k = 8 * zoom
        draw.line([(b[0] + px * k, b[1] + py * k), (b[0] - px * k, b[1] - py * k)],
                  fill=color, width=width)


def draw_arrow(draw, points: Sequence[Point], kind: str = "filled", width: int = 3,
               color=(32, 38, 50), both: bool = False, zoom: float = 1.0):
    pts = [tuple(p) for p in points]
    if len(pts) < 2:
        return
    draw.line(pts, fill=color, width=width, joint="curve")
    if kind == "none":
        return
    draw_head(draw, pts[-2], pts[-1], kind, width, color, zoom)
    if both:
        draw_head(draw, pts[1], pts[0], kind, width, color, zoom)


def draw_dashed(draw, pts, width, color, dash=12, gap=9):
    for i in range(len(pts) - 1):
        (ax, ay), (bx, by) = pts[i], pts[i + 1]
        seg = math.hypot(bx - ax, by - ay)
        if seg < 1:
            continue
        ux, uy = (bx - ax) / seg, (by - ay) / seg
        s = 0.0
        while s < seg:
            e = min(seg, s + dash)
            draw.line([(ax + ux * s, ay + uy * s), (ax + ux * e, ay + uy * e)],
                      fill=color, width=width)
            s = e + gap


def draw_dotted(draw, pts, width, color, dot=3, gap=6):
    draw_dashed(draw, pts, width, color, dash=dot, gap=gap)


# 兼容旧接口
def _head(draw, a, b, kind, width, color):      # noqa: N802
    draw_head(draw, a, b, kind, width, color, 1.0)
