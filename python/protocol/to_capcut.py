#!/usr/bin/env python3
"""
将 NGLEngine 协议 JSON 转为 CapCut 可打开的草稿。

用法:
  cd jyconvert && python3 python/protocol/to_capcut.py \
    --protocol examples/converted_protocol/converted_protocol.json \
    --resource-root examples/converted_protocol \
    --name my_draft \
    --output capcut

说明:
  - 协议时间单位为毫秒，CapCut 草稿为微秒（自动 ×1000）
  - 协议中 renderer=pag 的文字会去掉 PAG 动画，仅保留静态文字
  - 媒体文件复制到草稿 Resources/imported/，字体复制到 Resources/fonts/
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from capcut.lib import (
    CAPCUT_ROOT,
    JYCONVERT_ROOT,
    capcut_drafts_root,
    new_uuid,
    save_json,
    summarize_draft,
)
from capcut.import_draft import register_in_capcut_root_meta
from protocol.converter import (
    ConversionContext,
    build_draft_meta_info,
    convert_protocol_to_draft_info,
    write_draft_cover,
)

def copy_draft_scaffold(src_draft: Path, dst_draft: Path) -> None:
    names = [
        "draft_settings",
        "draft_agency_config.json",
        "draft_biz_config.json",
        "timeline_layout.json",
        "performance_opt_info.json",
        "draft_virtual_store.json",
        "attachment_editing.json",
        "key_value.json",
    ]
    for name in names:
        src = src_draft / name
        if src.exists():
            dst = dst_draft / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)

    for sub in ("common_attachment", "adjust_mask", "matting", "qr_upload", "smart_crop"):
        src = src_draft / sub
        if src.exists() and src.is_dir():
            shutil.copytree(src, dst_draft / sub, dirs_exist_ok=True)


def resolve_scaffold_source() -> Path:
    candidates = [
        Path("/Users/xy/Movies/CapCut/User Data/Projects/com.lveditor.draft/0706"),
        JYCONVERT_ROOT / "User Data/Projects/com.lveditor.draft/0706_from_jy",
    ]
    for candidate in candidates:
        if (candidate / "draft_info.json").exists():
            return candidate
    raise FileNotFoundError("找不到 CapCut 草稿模板，请至少保留一个现有草稿用于复制 scaffold 文件。")


def convert_protocol(
    protocol_path: Path,
    resource_root: Path | None,
    draft_name: str,
    output: str,
    register: bool,
) -> Path:
    protocol_path = protocol_path.resolve()
    resource_root = (resource_root or protocol_path.parent).resolve()
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if output == "capcut":
        drafts_root = capcut_drafts_root()
    else:
        drafts_root = JYCONVERT_ROOT / "User Data/Projects/com.lveditor.draft"

    draft_dir = drafts_root / draft_name
    if draft_dir.exists():
        shutil.rmtree(draft_dir)
    draft_dir.mkdir(parents=True, exist_ok=True)

    ctx = ConversionContext(
        protocol_path=protocol_path.resolve(),
        resource_root=resource_root.resolve(),
        draft_dir=draft_dir.resolve(),
        imported_dir=draft_dir / "Resources" / "imported",
        fonts_dir=draft_dir / "Resources" / "fonts",
    )
    ctx.imported_dir.mkdir(parents=True, exist_ok=True)
    ctx.fonts_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/5] 读取协议: {protocol_path}")
    print(f"      资源根目录: {resource_root}")
    print(f"[2/5] 转换 draft_info.json ...")
    draft_info = convert_protocol_to_draft_info(protocol, ctx)
    draft_id = ctx.draft_id or draft_info["id"]

    print(f"[3/5] 写入草稿目录: {draft_dir}")
    save_json(draft_dir / "draft_info.json", draft_info)
    draft_meta = build_draft_meta_info(draft_info, ctx, draft_id, drafts_root)
    save_json(draft_dir / "draft_meta_info.json", draft_meta)

    scaffold = resolve_scaffold_source()
    copy_draft_scaffold(scaffold, draft_dir)

    print("[4/5] 生成草稿封面与复制媒体 ...")
    if write_draft_cover(protocol, ctx):
        print(f"      封面: {draft_dir / 'draft_cover.jpg'}")
    print(f"      已复制 {len(ctx.copied_files)} 个媒体/字体文件")
    if ctx.warnings:
        print("      警告:")
        for warning in ctx.warnings:
            print(f"        - {warning}")

    if register and output == "capcut":
        print("[5/5] 注册到 CapCut root_meta_info.json ...")
        register_in_capcut_root_meta(draft_dir, draft_id, draft_name)
    else:
        print("[5/5] 跳过 CapCut 注册")

    return draft_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="NGLEngine 协议 → CapCut 草稿")
    parser.add_argument(
        "--protocol",
        type=Path,
        required=True,
        help="协议 JSON 路径",
    )
    parser.add_argument(
        "--resource-root",
        type=Path,
        default=None,
        help="可选；默认使用协议 JSON 所在目录（协议内 ./assets/、./abc/ 等相对它解析）",
    )
    parser.add_argument(
        "--name",
        required=True,
        help="草稿名称",
    )
    parser.add_argument(
        "--output",
        choices=("capcut", "jyconvert"),
        required=True,
        help="输出位置：capcut=写入 CapCut 草稿目录；jyconvert=仅写入 jyconvert 本地",
    )
    parser.add_argument(
        "--no-register",
        action="store_true",
        help="写入 CapCut 目录但不修改 root_meta_info.json",
    )
    args = parser.parse_args()

    if not args.protocol.exists():
        raise FileNotFoundError(f"协议文件不存在: {args.protocol}")
    resource_root = (args.resource_root or args.protocol.parent).resolve()
    if not resource_root.exists():
        raise FileNotFoundError(f"资源根目录不存在: {resource_root}")

    print("=" * 60)
    print("NGLEngine 协议 → CapCut 草稿")
    print("=" * 60)

    draft_dir = convert_protocol(
        protocol_path=args.protocol,
        resource_root=resource_root,
        draft_name=args.name,
        output=args.output,
        register=(args.output == "capcut" and not args.no_register),
    )

    summarize_draft(draft_dir)
    print("\n✓ 转换完成")
    if args.output == "capcut":
        print(f"  CapCut 草稿: {draft_dir}")
        print(f"  CapCut 根目录: {CAPCUT_ROOT}")
        print("  请重启 CapCut 或刷新草稿列表查看")
    else:
        print(f"  输出草稿: {draft_dir}")


if __name__ == "__main__":
    main()
