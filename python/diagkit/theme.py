# -*- coding: utf-8 -*-
"""主题与字体解析。

设计要点
--------
* 主题只描述"可用什么"，不描述"画在哪"：颜色、字体族、线宽、圆角半径。
* 字体族带候选链，跨平台回退；解析结果按 (文件, 字号) 缓存，避免重复打开 ttc。
* 所有尺寸都是"设计像素"（1x），渲染器负责超采样放大，因此在主题里不需要关心 dpi。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Tuple

from PIL import ImageFont

# ---------------------------------------------------------------- 字体候选链
CJK_SANS = (
    r"C:\Windows\Fonts\msyh.ttc",            # 微软雅黑
    r"C:\Windows\Fonts\simhei.ttf",          # 黑体
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/PingFang.ttc",
)
CJK_SANS_BOLD = (
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/System/Library/Fonts/PingFang.ttc",
)
MONO = (
    r"C:\Windows\Fonts\consolab.ttf",
    r"C:\Windows\Fonts\consola.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/System/Library/Fonts/Menlo.ttc",
)
SERIF = (
    r"C:\Windows\Fonts\times.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/System/Library/Fonts/Times.ttc",
)


def first_existing(paths: Tuple[str, ...]) -> str:
    """返回候选链中第一个存在的字体文件。"""
    for p in paths:
        if os.path.exists(p):
            return p
    raise FileNotFoundError(
        "找不到可用字体，请在 theme.Theme.fonts 中显式指定字体文件路径；已尝试：%s"
        % (paths,)
    )


@dataclass(frozen=True)
class Palette:
    """一套配色。浅色用于填充，深色用于描边，文字色单独给出。"""

    ink: Tuple[int, int, int] = (32, 38, 50)
    line: Tuple[int, int, int] = (62, 74, 94)
    muted: Tuple[int, int, int] = (108, 118, 134)
    accent: Tuple[int, int, int] = (28, 76, 176)
    danger: Tuple[int, int, int] = (196, 44, 36)
    success: Tuple[int, int, int] = (22, 118, 74)
    canvas: Tuple[int, int, int] = (255, 255, 255)

    fill_term: Tuple[int, int, int] = (230, 240, 254)
    fill_process: Tuple[int, int, int] = (255, 255, 255)
    fill_decision: Tuple[int, int, int] = (255, 247, 222)
    fill_entity: Tuple[int, int, int] = (243, 246, 250)
    fill_store: Tuple[int, int, int] = (238, 246, 240)
    fill_actor: Tuple[int, int, int] = (247, 250, 223)
    fill_class_header: Tuple[int, int, int] = (226, 236, 250)
    fill_state: Tuple[int, int, int] = (247, 249, 254)
    fill_note: Tuple[int, int, int] = (255, 252, 230)
    fill_lane: Tuple[int, int, int] = (238, 243, 250)
    fill_activation: Tuple[int, int, int] = (226, 236, 250)

    outline_term: Tuple[int, int, int] = (70, 118, 198)
    outline_decision: Tuple[int, int, int] = (196, 140, 34)
    outline_entity: Tuple[int, int, int] = (86, 100, 124)
    outline_store: Tuple[int, int, int] = (60, 122, 92)
    outline_actor: Tuple[int, int, int] = (120, 140, 60)
    outline_class: Tuple[int, int, int] = (56, 74, 110)
    outline_state: Tuple[int, int, int] = (80, 104, 150)
    outline_note: Tuple[int, int, int] = (180, 160, 90)

    grid: Tuple[int, int, int] = (206, 213, 224)
    band: Tuple[int, int, int] = (26, 52, 110)
    title: Tuple[int, int, int] = (16, 40, 96)


LIGHT = Palette()

DARK = Palette(
    ink=(232, 236, 244),
    line=(150, 168, 200),
    muted=(148, 160, 182),
    accent=(120, 170, 255),
    danger=(255, 128, 120),
    success=(120, 214, 160),
    canvas=(22, 26, 34),
    fill_term=(38, 50, 72),
    fill_process=(30, 36, 48),
    fill_decision=(60, 52, 30),
    fill_entity=(36, 42, 56),
    fill_store=(30, 48, 40),
    fill_actor=(48, 50, 32),
    fill_class_header=(40, 52, 78),
    fill_state=(36, 44, 60),
    fill_note=(58, 52, 34),
    fill_lane=(32, 38, 50),
    fill_activation=(42, 54, 78),
    outline_term=(110, 150, 220),
    outline_decision=(214, 170, 80),
    outline_entity=(140, 156, 184),
    outline_store=(110, 180, 140),
    outline_actor=(160, 180, 96),
    outline_class=(140, 160, 200),
    outline_state=(130, 156, 200),
    outline_note=(180, 164, 110),
    grid=(70, 80, 96),
    band=(150, 180, 230),
    title=(190, 210, 245),
)

PRINT = Palette(
    ink=(0, 0, 0),
    line=(50, 50, 50),
    muted=(90, 90, 90),
    accent=(30, 60, 130),
    danger=(150, 30, 25),
    success=(20, 90, 60),
    canvas=(255, 255, 255),
    fill_term=(255, 255, 255),
    fill_process=(255, 255, 255),
    fill_decision=(255, 255, 255),
    fill_entity=(255, 255, 255),
    fill_store=(255, 255, 255),
    fill_actor=(255, 255, 255),
    fill_class_header=(240, 240, 240),
    fill_state=(255, 255, 255),
    fill_note=(250, 250, 250),
    fill_lane=(248, 248, 248),
    fill_activation=(235, 235, 235),
    outline_term=(30, 30, 30),
    outline_decision=(60, 60, 60),
    outline_entity=(30, 30, 30),
    outline_store=(30, 30, 30),
    outline_actor=(60, 60, 60),
    outline_class=(20, 20, 20),
    outline_state=(40, 40, 40),
    outline_note=(120, 120, 120),
    grid=(150, 150, 150),
    band=(0, 0, 0),
    title=(0, 0, 0),
)

PALETTES: Dict[str, Palette] = {"light": LIGHT, "dark": DARK, "print": PRINT}


@dataclass
class Fonts:
    """字体族与基准字号。字号以设计像素给出，渲染器按 scale 放大。"""

    sans: Tuple[str, ...] = CJK_SANS
    sans_bold: Tuple[str, ...] = CJK_SANS_BOLD
    mono: Tuple[str, ...] = MONO
    serif: Tuple[str, ...] = SERIF

    size_base: int = 23      # 普通文字
    size_bold: int = 23      # 加粗文字
    size_code: int = 20      # 等宽代码
    size_serif: int = 22     # 西文衬线
    size_note: int = 19      # 注释
    size_title: int = 32     # 图题
    size_legend: int = 20    # 图例

    def resolve(self) -> Dict[str, str]:
        return {
            "cn": first_existing(self.sans),
            "cnb": first_existing(self.sans_bold),
            "code": first_existing(self.mono),
            "serif": first_existing(self.serif),
        }


@dataclass
class Theme:
    """绘图主题：配色 + 字体 + 线条几何。"""

    name: str = "light"
    palette: Palette = field(default_factory=lambda: LIGHT)
    fonts: Fonts = field(default_factory=Fonts)
    line_width: int = 2
    edge_width: int = 3
    radius: int = 22
    margin: int = 40
    grid: int = 10

    @staticmethod
    def get(name: str = "light") -> "Theme":
        key = (name or "light").lower()
        if key not in PALETTES:
            raise ValueError("未知主题 %r，可选：%s" % (name, ", ".join(sorted(PALETTES))))
        return Theme(name=key, palette=PALETTES[key])

    # ---------------------------------------------------------- 字体缓存
    def font(self, kind: str, size: int, cache: dict = None) -> ImageFont.FreeTypeFont:
        """按 (族, 字号) 取字体对象；同一次渲染共享缓存。"""
        paths = self.fonts.resolve()
        path = paths.get(kind, paths["cn"])
        key = (path, size)
        if cache is not None and key in cache:
            return cache[key]
        try:
            f = ImageFont.truetype(path, size)
        except OSError:
            f = ImageFont.load_default()
        if cache is not None:
            cache[key] = f
        return f
