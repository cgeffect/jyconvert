"""NGLEngine 协议 → 剪映草稿格式（本地输出，不写入剪映目录）。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from capcut.lib import JYCONVERT_ROOT, new_uuid, now_us, save_json
from protocol.converter import (
    ConversionContext,
    build_draft_meta_info,
    convert_protocol_to_draft_info,
    write_draft_cover,
)

SCAFFOLD_DIR = JYCONVERT_ROOT / "templates" / "jianying_scaffold"

SCAFFOLD_FILES = (
    "draft_settings",
    "draft_agency_config.json",
    "draft_biz_config.json",
    "performance_opt_info.json",
    "draft_virtual_store.json",
    "attachment_editing.json",
    "key_value.json",
    "attachment_pc_common.json",
)

SCAFFOLD_SUBDIRS = (
    "common_attachment",
    "adjust_mask",
    "matting",
    "qr_upload",
    "smart_crop",
)


def copy_draft_scaffold(src_draft: Path, dst_draft: Path) -> None:
    """复制剪映辅助文件；timeline_layout / Timelines 由转换流程生成。"""
    for name in SCAFFOLD_FILES:
        src = src_draft / name
        if src.exists():
            dst = dst_draft / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)

    for sub in SCAFFOLD_SUBDIRS:
        src = src_draft / sub
        if src.exists() and src.is_dir():
            shutil.copytree(src, dst_draft / sub, dirs_exist_ok=True)


def resolve_scaffold_source() -> Path:
    """优先使用仓库内置 scaffold，可在任意环境运行（不依赖剪映目录）。"""
    if (SCAFFOLD_DIR / "draft_settings").exists():
        return SCAFFOLD_DIR

    from jianying.lib import jianying_drafts_root

    drafts_root = jianying_drafts_root()
    if not drafts_root.exists():
        raise FileNotFoundError(
            f"缺少内置 scaffold（{SCAFFOLD_DIR}），且剪映草稿目录不存在: {drafts_root}"
        )

    candidates: list[tuple[int, float, Path]] = []
    for p in drafts_root.iterdir():
        if not p.is_dir() or p.name.startswith("."):
            continue
        if not (p / "draft_settings").exists():
            continue
        score = 2 if (p / "Timelines").is_dir() else 1
        candidates.append((score, p.stat().st_mtime, p))

    candidates.sort(key=lambda item: (-item[0], -item[1]))
    if candidates:
        return candidates[0][2]

    raise FileNotFoundError(
        f"缺少内置 scaffold（{SCAFFOLD_DIR}），请先在剪映中保留至少一个现有草稿。"
    )


def write_jianying_timelines(draft_dir: Path, draft_info: dict[str, Any], timeline_id: str) -> None:
    """剪映 10.x 从 Timelines/{id}/draft_info.json 读取轨道。"""
    now = now_us()
    project_id = new_uuid()
    timeline_root = draft_dir / "Timelines"
    timeline_dir = timeline_root / timeline_id
    timeline_dir.mkdir(parents=True, exist_ok=True)

    project = {
        "config": {
            "color_space": -1,
            "mixed_track_mode_on": False,
            "render_index_track_mode_on": True,
            "use_float_render": False,
        },
        "create_time": now,
        "id": project_id,
        "main_timeline_id": timeline_id,
        "timelines": [{
            "create_time": now,
            "id": timeline_id,
            "is_marked_delete": False,
            "name": "时间线01",
            "update_time": now,
        }],
        "update_time": now,
        "version": 0,
    }
    save_json(timeline_root / "project.json", project)
    save_json(timeline_dir / "draft_info.json", draft_info)
    save_json(timeline_dir / "attachment_pc_common.json", {})

    layout = {
        "activeTimeline": timeline_id,
        "dockItems": [{
            "dockIndex": 0,
            "ratio": 1,
            "timelineIds": [timeline_id],
            "timelineNames": ["时间线01"],
        }],
        "layoutOrientation": 1,
    }
    save_json(draft_dir / "timeline_layout.json", layout)


def sync_timeline_cover(draft_dir: Path, timeline_id: str) -> None:
    cover = draft_dir / "draft_cover.jpg"
    if cover.exists():
        shutil.copy2(cover, draft_dir / "Timelines" / timeline_id / "draft_cover.jpg")


def convert_protocol_to_local_draft(
    protocol_path: Path,
    resource_root: Path,
    draft_name: str,
    output_root: Path,
) -> Path:
    """将 NGL 协议转为剪映草稿格式，写入本地目录（不触碰剪映安装目录）。"""
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    drafts_root = output_root.resolve()
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
        draft_target="jianying",
    )
    ctx.imported_dir.mkdir(parents=True, exist_ok=True)
    ctx.fonts_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/5] 读取协议: {protocol_path}")
    print(f"      资源根目录: {resource_root}")
    print("[2/5] 转换 draft_info.json ...")
    draft_info = convert_protocol_to_draft_info(protocol, ctx)
    draft_id = ctx.draft_id or draft_info["id"]
    draft_info["id"] = draft_id

    print(f"[3/5] 写入本地草稿: {draft_dir}")
    save_json(draft_dir / "draft_info.json", draft_info)
    write_jianying_timelines(draft_dir, draft_info, draft_id)
    draft_meta = build_draft_meta_info(draft_info, ctx, draft_id, drafts_root)
    save_json(draft_dir / "draft_meta_info.json", draft_meta)

    print("[4/5] 复制 scaffold 辅助文件 ...")
    copy_draft_scaffold(resolve_scaffold_source(), draft_dir)

    print("[5/5] 生成封面与复制媒体 ...")
    if write_draft_cover(protocol, ctx):
        print(f"      封面: {draft_dir / 'draft_cover.jpg'}")
        sync_timeline_cover(draft_dir, draft_id)
    print(f"      已复制 {len(ctx.copied_files)} 个媒体/字体文件")
    if ctx.warnings:
        print("      警告:")
        for warning in ctx.warnings:
            print(f"        - {warning}")

    return draft_dir
