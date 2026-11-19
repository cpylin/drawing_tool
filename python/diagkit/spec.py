# -*- coding: utf-8 -*-
"""声明式规格（JSON / dict）→ 图。

规格是插件对外的主要接口：工具调用只传一份 JSON，不需要写 Python。
本模块负责**严格校验**并把规格分派到 :mod:`diagkit.presets`。校验错误会带
字段路径，方便模型或用户一次改对。

最小规格::

    {
      "kind": "flowchart",
      "title": "图1  发布流程",
      "items": [
        {"id": "a", "shape": "start",  "text": "开始"},
        {"id": "b", "shape": "process", "text": "填写商品信息"},
        {"id": "c", "shape": "decision", "text": "认证通过?"}
      ],
      "links": [
        {"from": "a", "to": "b"},
        {"from": "b", "to": "c", "label": "是"}
      ]
    }
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from . import presets
from .model import Diagram
from .render import Renderer
from .theme import PALETTES

SPEC_VERSION = 1

#: kind -> (构建函数, 必需字段, 可选字段)
KINDS: Dict[str, dict] = {
    "flowchart": dict(fn=presets.flowchart, required=("items", "links"),
                      optional=("title", "theme", "direction", "layout")),
    "dfd": dict(fn=presets.dfd, required=("entities", "processes", "stores", "flows"),
                optional=("title", "theme", "gap", "x0", "y0", "dy")),
    "structure": dict(fn=presets.structure, required=("tree",),
                      optional=("title", "theme", "dx", "dy")),
    "usecase": dict(fn=presets.usecase, required=("actors", "cases", "links"),
                    optional=("title", "theme", "boundary", "per_row")),
    "class": dict(fn=presets.class_diagram, required=("classes", "relations"),
                  optional=("title", "theme", "per_row")),
    "sequence": dict(fn=presets.sequence, required=("participants", "messages"),
                     optional=("title", "theme", "gap", "top", "step", "activate")),
    "activity": dict(fn=presets.activity, required=("lanes", "items", "links"),
                     optional=("title", "theme", "col_gap", "row_gap")),
    "state": dict(fn=presets.state_machine, required=("states", "transitions"),
                  optional=("title", "theme", "gap", "row_gap")),
    "erd": dict(fn=presets.erd, required=("entities", "relations"),
                optional=("title", "theme", "per_row")),
    "mindmap": dict(fn=presets.mindmap, required=("root", "branches"),
                    optional=("title", "theme", "cx", "cy", "branch_dx", "leaf_dx",
                              "leaf_gap", "branch_gap")),
    "architecture": dict(fn=presets.architecture, required=("layers",),
                         optional=("title", "theme", "box_gap", "band_h", "width")),
    "bizflow": dict(fn=presets.bizflow, required=("steps",),
                    optional=("title", "theme", "per_row", "dx", "dy")),
}


class SpecError(ValueError):
    """规格不合法。``path`` 指到具体字段。"""

    def __init__(self, message: str, path: str = ""):
        self.path = path
        super().__init__("%s: %s" % (path, message) if path else message)


def available_kinds() -> List[str]:
    return sorted(KINDS)


def _require(spec: dict, key: str, path: str) -> Any:
    if key not in spec:
        raise SpecError("缺少必需字段 %r" % key, path)
    return spec[key]


def _as_list(value: Any, path: str) -> list:
    if not isinstance(value, (list, tuple)):
        raise SpecError("应为数组，实际是 %s" % type(value).__name__, path)
    return list(value)


def _as_dict(value: Any, path: str) -> dict:
    if not isinstance(value, dict):
        raise SpecError("应为对象，实际是 %s" % type(value).__name__, path)
    return value


def _check_ids(items: List[dict], key: str, path: str) -> None:
    seen = set()
    for i, it in enumerate(items):
        if key not in it:
            raise SpecError("缺少字段 %r" % key, "%s[%d]" % (path, i))
        ident = str(it[key])
        if not ident:
            raise SpecError("id 不能为空", "%s[%d].%s" % (path, i, key))
        if ident in seen:
            raise SpecError("id 重复：%r" % ident, "%s[%d].%s" % (path, i, key))
        seen.add(ident)


def validate(spec: Any) -> dict:
    """校验并归一化规格；返回浅拷贝。"""
    spec = _as_dict(spec, "spec")
    kind = str(_require(spec, "kind", "spec")).lower()
    if kind not in KINDS:
        raise SpecError("未知图类型 %r，可选：%s" % (kind, ", ".join(available_kinds())),
                        "spec.kind")
    table = KINDS[kind]
    for field in table["required"]:
        _require(spec, field, "spec")

    theme = spec.get("theme", "light")
    if theme not in PALETTES:
        raise SpecError("未知主题 %r，可选：%s" % (theme, ", ".join(sorted(PALETTES))),
                        "spec.theme")

    allowed = set(table["required"]) | set(table["optional"]) | {"kind", "version"}
    unknown = sorted(set(spec) - allowed)
    if unknown:
        raise SpecError("不支持的字段 %s（%s 支持：%s）"
                        % (", ".join(unknown), kind, ", ".join(sorted(allowed))),
                        "spec")

    # 常见结构的 id 唯一性检查
    for field in ("items", "entities", "processes", "stores", "classes",
                  "participants", "states", "steps", "lanes"):
        if field in spec and isinstance(spec[field], list) and spec[field] \
                and isinstance(spec[field][0], dict) and "id" in spec[field][0]:
            _check_ids(spec[field], "id", "spec.%s" % field)
    if isinstance(spec.get("cases"), list) and spec["cases"] \
            and isinstance(spec["cases"][0], dict):
        _check_ids(spec["cases"], "id", "spec.cases")
    if isinstance(spec.get("actors"), list) and spec["actors"] \
            and isinstance(spec["actors"][0], dict):
        _check_ids(spec["actors"], "id", "spec.actors")
    return dict(spec)


def build(spec: Any) -> Diagram:
    """把规格构建成 :class:`Diagram`。"""
    spec = validate(spec)
    kind = str(spec["kind"]).lower()
    table = KINDS[kind]
    kwargs = {k: v for k, v in spec.items()
              if k in table["optional"] or k in table["required"]}
    kwargs.pop("kind", None)
    try:
        return table["fn"](**kwargs)
    except SpecError:
        raise
    except TypeError as exc:
        raise SpecError("参数不匹配：%s" % exc, "spec") from None


def render_spec(spec: Any, out: str, scale: float = 2.0) -> str:
    """构建并保存为 PNG，返回绝对路径。"""
    diagram = build(spec)
    out = os.path.abspath(out)
    parent = os.path.dirname(out)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    Renderer(diagram, scale=scale).save(out)
    return out


def load(path: str) -> dict:
    # utf-8-sig：Windows 记事本/PowerShell 保存的 JSON 常带 BOM，普通 utf-8 会解析失败
    with open(path, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def render_file(spec_path: str, out: str, scale: float = 2.0) -> str:
    return render_spec(load(spec_path), out, scale=scale)
