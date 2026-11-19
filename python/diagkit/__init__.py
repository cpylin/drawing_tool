# -*- coding: utf-8 -*-
"""diagkit —— 代码即图的轻量绘图工具包。

设计目标
--------
1. **依赖极简**：只用 Pillow，安装成本低，离线可用。
2. **声明式输入**：一份 JSON 规格即可出图，便于交给 AI 生成、便于版本管理。
3. **可复现**：同样输入 + 同样主题 = 像素级相同的输出，适合放进报告与仓库。
4. **可扩展**：新增图元只需登记一个画笔，新增图类型只需登记一个构建器。

快速开始
--------
>>> from diagkit import render_spec
>>> render_spec({"kind": "flowchart",
...              "items": [{"id": "a", "shape": "start", "text": "开始"},
...                        {"id": "b", "shape": "process", "text": "处理"}],
...              "links": [{"from": "a", "to": "b"}]},
...             "out.png")

命令行
------
>>> python -m diagkit render spec.json -o out.png --scale 2
>>> python -m diagkit kinds
>>> python -m diagkit gallery -o ./gallery
"""
from __future__ import annotations

__version__ = "0.1.0"

from .model import Diagram, Edge, Node, label_of
from .render import Renderer, render
from .spec import KINDS, SpecError, available_kinds, build, render_file, render_spec, validate
from .text import Label, cb, cn, lines, mix, mono, serif
from .theme import PALETTES, Theme

__all__ = [
    "__version__",
    # 模型
    "Diagram", "Node", "Edge", "label_of",
    # 文本
    "Label", "cn", "cb", "mono", "serif", "mix", "lines",
    # 渲染
    "Renderer", "render",
    # 规格
    "build", "validate", "render_spec", "render_file", "available_kinds", "KINDS",
    "SpecError",
    # 主题
    "Theme", "PALETTES",
]
