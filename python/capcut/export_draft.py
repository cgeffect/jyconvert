#!/usr/bin/env python3
"""
脚本 1：从 CapCut 导出草稿到 jyconvert 目录。

用法:
  cd jyconvert && python3 capcut/export_draft.py                  # 导出今日最新草稿
  cd jyconvert && python3 capcut/export_draft.py --name 0706      # 导出指定名称草稿
  cd jyconvert && python3 capcut/export_draft.py --date 2026-07-06
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from capcut.lib import (
    DRAFTS_REL,
    capcut_drafts_root,
    capcut_relative,
    capcut_target,
    collect_material_paths,
    copy_draft_assets,
    copy_file,
    copy_tree,
    find_draft_by_name,
    find_today_draft,
    is_under_capcut,
    is_under_root,
    jyconvert_drafts_root,
    jyconvert_target,
    load_json,
    save_json,
    save_manifest,
    summarize_draft,
    update_draft_root_paths,
    CAPCUT_ROOT,
    JYCONVERT_ROOT,
)


def copy_resources_to_jyconvert(
    resolved: dict[str, Path],
    draft_dir: Path,
) -> dict[str, str]:
    """复制素材到 jyconvert，保持 CapCut 目录层级，返回路径映射。"""
    mapping: dict[str, str] = {}

    for raw, src in resolved.items():
        src = src.resolve()

        try:
            src.relative_to(draft_dir.resolve())
            mapping[raw] = str(src)
            continue
        except ValueError:
            pass

        if is_under_capcut(src):
            rel = capcut_relative(src)
            sub = rel.relative_to("User Data") if rel.parts[0] == "User Data" else rel
            if sub.parts and sub.parts[0] == "Projects":
                continue
            dst = jyconvert_target(rel)
            if src.is_dir():
                copy_tree(src, dst)
            else:
                copy_file(src, dst)
            mapping[raw] = str(dst)
            print(f"  [cache] {rel}")
        elif is_under_root(src, JYCONVERT_ROOT):
            mapping[raw] = str(src)
        else:
            imported = draft_dir / "Resources" / "imported" / src.name
            if src.is_dir():
                copy_tree(src, imported)
            else:
                copy_file(src, imported)
            mapping[raw] = str(imported)
            print(f"  [media] {src.name} -> {imported.relative_to(JYCONVERT_ROOT)}")

    return mapping


def export_draft(src_draft: Path, export_name: str | None = None) -> Path:
    name = export_name or src_draft.name
    dst = jyconvert_drafts_root() / name

    print(f"\n[1/4] 复制草稿: {src_draft.name} -> {dst.relative_to(JYCONVERT_ROOT)}")
    copy_tree(src_draft, dst)

    print("[2/4] 收集并复制资源...")
    _, resolved = collect_material_paths(src_draft)
    print(f"  共 {len(resolved)} 个资源")
    path_mapping = copy_resources_to_jyconvert(resolved, dst)

    print("[3/4] 更新草稿内路径引用...")
    update_draft_root_paths(dst, jyconvert_drafts_root(), path_mapping)

    src_meta = load_json(src_draft / "draft_meta_info.json")
    manifest = {
        "exported_at": datetime.now().isoformat(),
        "source": {
            "capcut_root": str(CAPCUT_ROOT),
            "draft_name": src_draft.name,
            "draft_path": str(src_draft),
            "draft_id": src_meta.get("draft_id"),
        },
        "export": {
            "draft_name": name,
            "draft_path": str(dst),
            "drafts_root": str(jyconvert_drafts_root()),
            "workspace_root": str(JYCONVERT_ROOT),
        },
        "path_mapping": path_mapping,
    }
    manifest_path = save_manifest(manifest)
    print(f"[4/4] 写入清单: {manifest_path.relative_to(JYCONVERT_ROOT)}")

    return dst


def main() -> None:
    parser = argparse.ArgumentParser(description="从 CapCut 导出草稿到 jyconvert")
    parser.add_argument("--name", help="指定 CapCut 草稿名称")
    parser.add_argument("--date", help="指定日期 YYYY-MM-DD，导出该日最新草稿")
    parser.add_argument("--output-name", help="jyconvert 中的导出目录名（默认同源草稿名）")
    args = parser.parse_args()

    print("=" * 60)
    print("CapCut → jyconvert  导出")
    print("=" * 60)

    if args.name:
        src = find_draft_by_name(args.name, capcut_drafts_root())
    elif args.date:
        src = find_today_draft(date.fromisoformat(args.date))
    else:
        src = find_today_draft()

    print(f"\n源草稿: {src}")
    dst = export_draft(src, args.output_name)
    summarize_draft(dst)

    print("\n✓ 导出完成")
    print(f"  草稿目录: {dst.relative_to(JYCONVERT_ROOT)}")
    print(f"  下一步:   python3 capcut/import_draft.py")


if __name__ == "__main__":
    main()
