#!/usr/bin/env python3
"""
剪映草稿 → NGLEngine 协议（离线脚本，不接入 Electron）。

多时间线草稿:
  python3 python/jianying/from_jianying.py --draft-dir "..." --list-timelines
  python3 python/jianying/from_jianying.py --draft-dir "..." --timeline-name 时间线02 --tracks-only --output t2.json
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jianying.decrypt import is_encrypted_draft_file, load_draft_info_json
from jianying.timelines import list_timelines, resolve_draft_info_path
from protocol.from_jianying import ReverseContext, extract_tracks_info, write_protocol_bundle


def load_draft_info(args: argparse.Namespace, info_path: Path) -> dict:
    if args.draft_info:
        return json.loads(info_path.read_text(encoding="utf-8"))
    return load_draft_info_json(info_path, allow_decrypt=not args.no_decrypt)


def resolve_output_path(args: argparse.Namespace) -> Path:
    if args.output:
        return args.output.resolve()
    if args.output_dir:
        name = "tracks.json" if args.tracks_only else "converted_protocol.json"
        return (args.output_dir / name).resolve()
    raise ValueError("请指定 --output 或 --output-dir")


def print_timelines(draft_dir: Path) -> None:
    timelines = list_timelines(draft_dir)
    if not timelines:
        print("未找到 Timelines/ 结构，将使用根目录 draft_info.json")
        root = draft_dir / "draft_info.json"
        if root.exists():
            enc = is_encrypted_draft_file(root)
            print(f"  draft_info.json  encrypted={enc}")
        return

    print(f"草稿: {draft_dir.name}  共 {len(timelines)} 条时间线\n")
    for item in timelines:
        flags = []
        if item.get("is_main"):
            flags.append("主时间线")
        if item.get("is_active"):
            flags.append("当前激活")
        flag_text = f" ({', '.join(flags)})" if flags else ""
        enc = "加密" if item.get("encrypted") else "明文"
        print(f"  [{enc}] {item['name']}{flag_text}")
        print(f"         id: {item['id']}")
        print(f"         path: {item['draft_info']}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="剪映草稿 → NGLEngine 协议（离线）")
    parser.add_argument("--draft-dir", type=Path, required=True, help="剪映草稿目录")
    parser.add_argument("--output-dir", type=Path, help="完整转换输出目录")
    parser.add_argument("--output", type=Path, help="输出 JSON 文件路径")
    parser.add_argument("--tracks-only", action="store_true", help="只提取轨道信息")
    parser.add_argument("--list-timelines", action="store_true", help="列出草稿内所有时间线")
    parser.add_argument("--timeline-id", help="指定时间线 UUID")
    parser.add_argument("--timeline-name", help="指定时间线名称，如 时间线02")
    parser.add_argument("--font", type=Path, default=Path("examples/字制区喜脉体.ttf"))
    parser.add_argument("--protocol-id", default="converted_from_jianying")
    parser.add_argument("--draft-info", type=Path, help="明文 draft_info.json 路径")
    parser.add_argument("--no-decrypt", action="store_true", help="不尝试自动解密")
    args = parser.parse_args()

    draft_dir = args.draft_dir.resolve()
    if not draft_dir.is_dir():
        raise FileNotFoundError(f"草稿目录不存在: {draft_dir}")

    if args.list_timelines:
        print_timelines(draft_dir)
        return

    if not args.tracks_only and not args.output_dir:
        parser.error("完整转换需要 --output-dir；或改用 --tracks-only")

    if not args.tracks_only:
        font_path = args.font.resolve()
        if not font_path.exists():
            raise FileNotFoundError(f"字体文件不存在: {font_path}")

    info_path = resolve_draft_info_path(
        draft_dir,
        timeline_id=args.timeline_id,
        timeline_name=args.timeline_name,
        draft_info=args.draft_info,
    )
    if not info_path.exists():
        raise FileNotFoundError(f"找不到 draft_info: {info_path}")

    encrypted = is_encrypted_draft_file(info_path)
    if encrypted and not args.draft_info and args.no_decrypt:
        raise ValueError(
            f"draft_info.json 已加密: {info_path}\n"
            "请去掉 --no-decrypt，或使用 --draft-info 传入明文 JSON。"
        )

    mode = "轨道信息" if args.tracks_only else "完整协议"
    print("=" * 60)
    print(f"剪映草稿 → {mode}")
    print("=" * 60)
    print(f"[1/2] 读取草稿: {draft_dir}")
    if args.timeline_id or args.timeline_name:
        print(f"      时间线: {args.timeline_name or args.timeline_id}")
    print(f"      draft_info: {info_path}")
    if encrypted and not args.draft_info:
        print("      加密格式，尝试解密 ...")

    draft_info = load_draft_info(args, info_path)
    out_path = resolve_output_path(args)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.tracks_only:
        print(f"[2/2] 提取轨道 → {out_path}")
        tracks_info = extract_tracks_info(draft_info, draft_dir)
        timelines = list_timelines(draft_dir)
        if timelines:
            active = resolve_timeline_id_from_path(info_path, timelines)
            if active:
                tracks_info["timeline"] = active
        out_path.write_text(json.dumps(tracks_info, ensure_ascii=False, indent=2), encoding="utf-8")
        track_count = len(tracks_info["tracks"])
        seg_count = sum(len(t["segments"]) for t in tracks_info["tracks"])
        print("      完成")
        print(f"      轨道: {track_count}  片段: {seg_count}  时长: {tracks_info['duration_ms']}ms")
        return

    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        for child in output_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    output_dir.mkdir(parents=True, exist_ok=True)

    ctx = ReverseContext(
        draft_dir=draft_dir,
        output_dir=output_dir,
        font_source=args.font.resolve(),
        font_filename=args.font.resolve().name,
        protocol_id=args.protocol_id,
    )

    print(f"[2/3] 转换协议并导出资源 → {output_dir}")
    out_json = write_protocol_bundle(draft_info, ctx)

    print("[3/3] 完成")
    print(f"      协议: {out_json}")
    print(f"      资源: {ctx.assets_dir} ({len(list(ctx.assets_dir.glob('*')))} 个文件)")
    print(f"      字体: {ctx.fonts_dir / ctx.font_filename}")
    if ctx.warnings:
        print("      警告:")
        for warning in ctx.warnings:
            print(f"        - {warning}")


def resolve_timeline_id_from_path(info_path: Path, timelines: list[dict]) -> dict | None:
    for item in timelines:
        if Path(item["draft_info"]).resolve() == info_path.resolve():
            return {"id": item["id"], "name": item["name"]}
    return None


if __name__ == "__main__":
    main()
