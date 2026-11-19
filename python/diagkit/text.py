# -*- coding: utf-8 -*-
"""文本排版与度量。

社区实践（Pillow ≥ 8）用 ``ImageFont.getbbox()`` / ``getlength()`` 做度量，并用
``anchor='mm'`` 精确居中；本模块把这些封装成 :class:`Label`，支持：

* 一行内多种字体混排（中文 / 加粗 / 等宽代码 / 西文衬线）
* 自动折行（中文按字、西文按词），避免长标签把方框撑破
* 依据真实字形高度给出块高，不再用固定行高估算
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Sequence, Tuple

KINDS = ("cn", "cnb", "code", "serif")

#: 各字体族的行距系数（相对字号）。等宽字体行高略小，视觉上才与中文等高。
LINE_FACTOR = {"cn": 1.42, "cnb": 1.42, "code": 1.42, "serif": 1.42}

Run = Tuple[str, str]          # (文字, 字体族)


def _runs_width(runs: Sequence[Run], measurer) -> float:
    return sum(measurer.textlength(t, font=measurer.font_of(k)) for t, k in runs)


def _runs_height(runs: Sequence[Run], measurer) -> float:
    if not runs:
        return 0.0
    return max(LINE_FACTOR[k] * measurer.size_of(k) for _, k in runs)


@dataclass
class Label:
    """一段可多行、可混排的文本。"""

    lines: List[List[Run]] = field(default_factory=list)
    wrap_width: float = 0.0     # >0 时按该宽度自动折行（设计像素）

    # ------------------------------------------------------------ 构造
    def add(self, text: str, kind: str = "cn") -> "Label":
        self.lines.append([(text, kind)])
        return self

    def line(self, *runs: Run) -> "Label":
        self.lines.append(list(runs))
        return self

    @property
    def empty(self) -> bool:
        return not any(t for row in self.lines for t, _ in row)

    def text(self) -> str:
        return "\n".join("".join(t for t, _ in row) for row in self.lines)

    def __len__(self) -> int:
        return len(self.lines)

    # ------------------------------------------------------------ 度量
    def measured_lines(self, measurer) -> List[List[Run]]:
        """返回折行后的行集合（不修改自身）。"""
        if not self.wrap_width:
            return [list(r) for r in self.lines]
        out: List[List[Run]] = []
        for row in self.lines:
            out.extend(_wrap_row(row, self.wrap_width, measurer))
        return out

    def size(self, measurer) -> Tuple[float, float]:
        rows = self.measured_lines(measurer)
        w = max((_runs_width(r, measurer) for r in rows), default=0.0)
        h = sum(_runs_height(r, measurer) for r in rows)
        return w, h


def _wrap_row(row: Sequence[Run], width: float, measurer) -> List[List[Run]]:
    """把一行按宽度折断。中文逐字可断，西文优先在空格处断。"""
    full = _runs_width(row, measurer)
    if full <= width:
        return [list(row)]

    # 逐字拆成 (字符, 字体族) 序列，保留原有族信息
    chars: List[Run] = []
    for text, kind in row:
        for ch in text:
            chars.append((ch, kind))

    lines: List[List[Run]] = []
    cur: List[Run] = []
    cur_w = 0.0
    for ch, kind in chars:
        cw = measurer.textlength(ch, font=measurer.font_of(kind))
        if cur and cur_w + cw > width:
            # 西文回退到最近空格，避免把单词劈开
            if ch != " " and kind != "cn":
                cut = _last_space(cur)
                if cut is not None:
                    lines.append(cur[:cut])
                    leftover = cur[cut + 1:]
                    cur = leftover
                    cur_w = _runs_width(cur, measurer)
                else:
                    lines.append(cur)
                    cur, cur_w = [], 0.0
            else:
                lines.append(cur)
                cur, cur_w = [], 0.0
        cur.append((ch, kind))
        cur_w += cw
    if cur:
        lines.append(cur)
    return [_merge(r) for r in lines]


def _last_space(row: Sequence[Run]):
    for i in range(len(row) - 1, -1, -1):
        if row[i][0] == " ":
            return i
    return None


def _merge(row: Sequence[Run]) -> List[Run]:
    """合并相邻同族字符，减少绘制调用。"""
    out: List[Run] = []
    for text, kind in row:
        if out and out[-1][1] == kind:
            out[-1] = (out[-1][0] + text, kind)
        else:
            out.append((text, kind))
    return out


# ---------------------------------------------------------------- 便捷构造
def cn(text: str) -> Label:
    return Label().add(text, "cn")


def cb(text: str) -> Label:
    return Label().add(text, "cnb")


def mono(text: str) -> Label:
    return Label().add(text, "code")


def serif(text: str) -> Label:
    return Label().add(text, "serif")


def mix(*runs: Run) -> Label:
    """单行混排：``mix(("定义 ", "cn"), ("p1, p2", "code"))``"""
    return Label([list(runs)])


def lines(*rows: Iterable[Run]) -> Label:
    return Label([list(r) for r in rows])


def from_plain(value) -> Label:
    """把 str / Label 统一成 Label；换行符拆成多行。"""
    if isinstance(value, Label):
        return value
    text = "" if value is None else str(value)
    lab = Label()
    parts = text.split("\n")
    for i, p in enumerate(parts):
        if i == 0:
            lab.lines.append([(p, "cn")])
        else:
            lab.lines.append([(p, "cn")])
    return lab
