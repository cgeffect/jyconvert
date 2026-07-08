#!/usr/bin/env python3
"""
脚本 2：将 jyconvert 中导出的草稿写回 CapCut（创建全新独立草稿）。

用法:
  cd jyconvert && python3 capcut/import_draft.py                        # 从 manifest 导入
  cd jyconvert && python3 capcut/import_draft.py --name 0706            # 指定 jyconvert 草稿名
  cd jyconvert && python3 capcut/import_draft.py --capcut-name my_edit  # 指定 CapCut 中新草稿名称
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from capcut.lib import (
    clone_draft_with_new_identity,
    collect_material_paths,
    copy_file,
    copy_tree,
    find_draft_by_name,
    is_under_root,
    jyconvert_drafts_root,
    jyconvert_relative,
    jyconvert_target,
    load_json,
    load_manifest,
    capcut_drafts_root,
    capcut_target,
    save_json,
    summarize_draft,
    CAPCUT_ROOT,
    JYCONVERT_ROOT,
)


def copy_cache_to_capcut(src_draft: Path) -> dict[str, str]:
    """将 jyconvert Cache 资源复制到 CapCut，返回 jy→capcut 路径映射。"""
    mapping: dict[str, str] = {}
    _, resolved = collect_material_paths(src_draft)

    for raw, src in resolved.items():
        src = src.resolve()
        if not is_under_root(src, JYCONVERT_ROOT):
            continue
        rel = jyconvert_relative(src)
        if not rel.parts or rel.parts[0] != "User Data":
            continue
        sub = rel.relative_to("User Data")
        if not sub.parts or sub.parts[0] != "Cache":
            continue

        dst = capcut_target(rel)
        if dst.exists():
            mapping[str(src)] = str(dst)
            mapping[raw] = str(dst)
            print(f"  [cache skip] {rel} (已存在)")
            continue

        if src.is_dir():
            copy_tree(src, dst)
        else:
            copy_file(src, dst)
        capcut_path = str(dst)
        mapping[str(src)] = capcut_path
        mapping[raw] = capcut_path
        print(f"  [cache] {rel}")

    return mapping


def build_path_mapping(src_draft: Path, dst_draft: Path, cache_mapping: dict[str, str]) -> dict[str, str]:
    """构建 jyconvert 路径 → CapCut 路径的完整映射。"""
    mapping: dict[str, str] = dict(cache_mapping)
    _, resolved = collect_material_paths(src_draft)

    for raw, src in resolved.items():
        src = src.resolve()
        if raw in mapping:
            continue

        if is_under_root(src, JYCONVERT_ROOT):
            rel = jyconvert_relative(src)
            if "Resources/imported" in str(rel):
                dst = dst_draft / "Resources" / "imported" / src.name
                dst.parent.mkdir(parents=True, exist_ok=True)
                if not dst.exists():
                    if src.is_dir():
                        copy_tree(src, dst)
                    else:
                        copy_file(src, dst)
                mapping[raw] = str(dst)
                mapping[str(src)] = str(dst)
            continue

        if src.exists():
            dst = dst_draft / "Resources" / "imported" / src.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists():
                copy_file(src, dst)
            mapping[raw] = str(dst)
            mapping[str(src)] = str(dst)

    # jyconvert 根 → capcut 根（兜底）
    mapping[str(JYCONVERT_ROOT)] = str(CAPCUT_ROOT)
    mapping[str(jyconvert_drafts_root())] = str(capcut_drafts_root())
    mapping[str(src_draft)] = str(dst_draft)

    return mapping


def register_in_capcut_root_meta(draft_dir: Path, draft_id: str, draft_name: str) -> None:
    """在 CapCut root_meta_info.json 中注册新草稿。"""
    root_meta_path = capcut_drafts_root() / "root_meta_info.json"
    if root_meta_path.exists():
        root_meta = load_json(root_meta_path)
    else:
        root_meta = {"all_draft_store": [], "draft_ids": 0, "root_path": str(capcut_drafts_root())}

    store = root_meta.get("all_draft_store", [])
    store = [d for d in store if d.get("draft_id") != draft_id]

    src_meta = load_json(draft_dir / "draft_meta_info.json")
    entry = {
        "cloud_draft_cover": False,
        "cloud_draft_sync": False,
        "draft_cloud_last_action_download": False,
        "draft_cloud_purchase_info": "",
        "draft_cloud_template_id": "",
        "draft_cloud_tutorial_info": "",
        "draft_cloud_videocut_purchase_info": "",
        "draft_cover": str(draft_dir / "draft_cover.jpg"),
        "draft_fold_path": str(draft_dir),
        "draft_id": draft_id,
        "draft_is_ai_shorts": False,
        "draft_is_cloud_temp_draft": False,
        "draft_is_invisible": False,
        "draft_is_pippit_draft": False,
        "draft_is_web_article_video": False,
        "draft_json_file": str(draft_dir / "draft_info.json"),
        "draft_name": draft_name,
        "draft_new_version": "",
        "draft_root_path": str(capcut_drafts_root()),
        "draft_timeline_materials_size": src_meta.get("draft_timeline_materials_size_", 0),
        "draft_type": "",
        "draft_web_article_video_enter_from": "",
        "streaming_edit_draft_ready": True,
        "tm_draft_cloud_completed": "",
        "tm_draft_cloud_entry_id": -1,
        "tm_draft_cloud_modified": 0,
        "tm_draft_cloud_parent_entry_id": -1,
        "tm_draft_cloud_space_id": -1,
        "tm_draft_cloud_user_id": -1,
        "tm_draft_create": src_meta.get("tm_draft_create"),
        "tm_draft_modified": src_meta.get("tm_draft_modified"),
        "tm_draft_removed": 0,
        "tm_duration": src_meta.get("tm_duration", 0),
    }
    store.insert(0, entry)
    root_meta["all_draft_store"] = store
    root_meta["draft_ids"] = len(store)
    root_meta["root_path"] = str(capcut_drafts_root())
    save_json(root_meta_path, root_meta)
    print(f"  已注册到 root_meta_info.json")


def import_draft(src_draft: Path, capcut_name: str | None = None) -> Path:
    suffix = datetime.now().strftime("%m%d_%H%M%S")
    base = capcut_name or f"{src_draft.name}_imported_{suffix}"
    dst = capcut_drafts_root() / base

    print(f"\n[1/5] 目标草稿: {dst}")
    print("[2/5] 复制 Cache 资源到 CapCut...")
    cache_mapping = copy_cache_to_capcut(src_draft)

    print("[3/5] 构建路径映射...")
    path_mapping = build_path_mapping(src_draft, dst, cache_mapping)

    print("[4/5] 创建新草稿（全新 ID）...")
    draft_id = clone_draft_with_new_identity(
        src_dir=src_draft,
        dst_dir=dst,
        drafts_root=capcut_drafts_root(),
        draft_name=base,
        path_mapping=path_mapping,
        src_prefix_replace=(str(src_draft), str(dst)),
    )
    print(f"  draft_id = {draft_id}")

    print("[5/5] 注册到 CapCut...")
    register_in_capcut_root_meta(dst, draft_id, base)

    return dst


def resolve_source_draft(name: str | None) -> Path:
    if name:
        return find_draft_by_name(name, jyconvert_drafts_root())
    manifest = load_manifest()
    export = manifest["export"]
    return Path(export["draft_path"])


def main() -> None:
    parser = argparse.ArgumentParser(description="将 jyconvert 草稿写回 CapCut")
    parser.add_argument("--name", help="jyconvert 中的草稿目录名（默认读 manifest）")
    parser.add_argument("--capcut-name", help="CapCut 中新草稿名称")
    args = parser.parse_args()

    print("=" * 60)
    print("jyconvert → CapCut  导入")
    print("=" * 60)

    src = resolve_source_draft(args.name)
    print(f"\n源草稿: {src}")

    if not (src / "draft_info.json").exists():
        raise FileNotFoundError(f"草稿不完整，缺少 draft_info.json: {src}")

    dst = import_draft(src, args.capcut_name)
    summarize_draft(dst)

    print("\n✓ 导入完成")
    print(f"  CapCut 新草稿: {dst}")
    print("  请重启 CapCut 或刷新草稿列表查看")


if __name__ == "__main__":
    main()
