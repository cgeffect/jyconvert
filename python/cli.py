#!/usr/bin/env python3
"""
jyconvert Python CLI（Electron 内嵌调用入口）。

用法:
  python3 cli.py convert --protocol ... --resource-root ... --name ... --output-dir ...
  python3 cli.py import --draft-dir ... --jianying-name ...
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from capcut.lib import summarize_draft
from jianying.convert_lib import convert_protocol_to_local_draft
from jianying.import_draft import import_draft_to_jianying


def cmd_convert(args: argparse.Namespace) -> None:
    if not args.protocol.exists():
        raise FileNotFoundError(f"协议文件不存在: {args.protocol}")
    if not args.resource_root.exists():
        raise FileNotFoundError(f"资源根目录不存在: {args.resource_root}")

    output_root = args.output_dir.resolve()
    print("=" * 60)
    print("NGLEngine 协议 → 本地剪映草稿")
    print("=" * 60)

    draft_dir = convert_protocol_to_local_draft(
        protocol_path=args.protocol,
        resource_root=args.resource_root,
        draft_name=args.name,
        output_root=output_root,
    )
    summarize_draft(draft_dir)
    print("\n✓ 转换完成")
    print(f"  本地草稿: {draft_dir}")


def cmd_import(args: argparse.Namespace) -> None:
    draft_dir = args.draft_dir.expanduser().resolve()
    if not draft_dir.is_dir():
        raise FileNotFoundError(f"草稿目录不存在: {draft_dir}")
    if not (draft_dir / "draft_info.json").exists():
        raise FileNotFoundError(f"草稿不完整，缺少 draft_info.json: {draft_dir}")

    print("=" * 60)
    print("本地剪映草稿 → 剪映 Pro")
    print("=" * 60)
    dst = import_draft_to_jianying(
        draft_dir,
        args.jianying_name,
        args.jianying_drafts_root,
    )
    summarize_draft(dst)
    print("\n✓ 导入完成")
    print(f"  剪映草稿: {dst}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="jyconvert-py")
    sub = parser.add_subparsers(dest="command", required=True)

    p_convert = sub.add_parser("convert", help="协议 → 本地剪映草稿")
    p_convert.add_argument("--protocol", type=Path, required=True)
    p_convert.add_argument("--resource-root", type=Path, required=True)
    p_convert.add_argument("--name", required=True)
    p_convert.add_argument("--output-dir", type=Path, required=True)
    p_convert.set_defaults(func=cmd_convert)

    p_import = sub.add_parser("import", help="本地草稿 → 剪映 Pro")
    p_import.add_argument("--draft-dir", type=Path, required=True)
    p_import.add_argument("--jianying-name", required=True)
    p_import.add_argument("--jianying-drafts-root", type=Path, help="剪映草稿根目录（com.lveditor.draft）")
    p_import.set_defaults(func=cmd_import)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
