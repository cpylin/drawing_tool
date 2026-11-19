# -*- coding: utf-8 -*-
"""命令行入口：``python -m diagkit <子命令>``。"""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__, available_kinds, render_file, render_spec
from .spec import KINDS, SpecError, validate
from .theme import PALETTES


def _cmd_kinds(args) -> int:
    print("diagkit %s —— 支持的图类型" % __version__)
    print()
    width = max(len(k) for k in KINDS)
    for name in available_kinds():
        table = KINDS[name]
        print("  %-*s  必需：%s" % (width, name, ", ".join(table["required"])))
    print()
    print("主题：%s" % ", ".join(sorted(PALETTES)))
    return 0


def _cmd_validate(args) -> int:
    try:
        with open(args.spec, "r", encoding="utf-8-sig") as fh:
            spec = json.load(fh)
    except OSError as exc:
        print("无法读取规格文件：%s" % exc, file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print("JSON 解析失败（第 %d 行第 %d 列）：%s"
              % (exc.lineno, exc.colno, exc.msg), file=sys.stderr)
        return 2
    try:
        validate(spec)
    except SpecError as exc:
        print("规格不合法：%s" % exc, file=sys.stderr)
        return 1
    print("规格合法：kind=%s" % spec.get("kind"))
    return 0


def _cmd_render(args) -> int:
    out = args.out or os.path.splitext(os.path.basename(args.spec))[0] + ".png"
    try:
        path = render_file(args.spec, out, scale=args.scale)
    except SpecError as exc:
        print("规格不合法：%s" % exc, file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print("渲染失败：%s" % exc, file=sys.stderr)
        return 1
    print("已生成 %s" % path)
    return 0


def _cmd_gallery(args) -> int:
    from .gallery import SAMPLES
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)
    ok = 0
    for name, spec in SAMPLES.items():
        try:
            path = render_spec(spec, os.path.join(out_dir, name + ".png"), scale=args.scale)
            print("  %-16s -> %s" % (name, os.path.basename(path)))
            ok += 1
        except (SpecError, OSError, ValueError) as exc:
            print("  %-16s 失败：%s" % (name, exc), file=sys.stderr)
    print("共生成 %d/%d 张" % (ok, len(SAMPLES)))
    return 0 if ok == len(SAMPLES) else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="diagkit", description="代码即图的轻量绘图工具")
    p.add_argument("--version", action="version", version="diagkit %s" % __version__)
    sub = p.add_subparsers(dest="command", required=True)

    k = sub.add_parser("kinds", help="列出支持的图类型")
    k.set_defaults(fn=_cmd_kinds)

    v = sub.add_parser("validate", help="校验规格文件")
    v.add_argument("spec")
    v.set_defaults(fn=_cmd_validate)

    r = sub.add_parser("render", help="按规格渲染 PNG")
    r.add_argument("spec")
    r.add_argument("-o", "--out", default=None)
    r.add_argument("--scale", type=float, default=2.0,
                   help="超采样倍率，默认 2（越大越清晰，文件越大）")
    r.set_defaults(fn=_cmd_render)

    g = sub.add_parser("gallery", help="渲染内置样图")
    g.add_argument("-o", "--out", default="gallery")
    g.add_argument("--scale", type=float, default=2.0)
    g.set_defaults(fn=_cmd_gallery)
    return p


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
