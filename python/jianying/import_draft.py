#!/usr/bin/env python3
"""
步骤 2：将本地剪映草稿导入剪映 Pro 草稿目录。

此步骤必须在 Mac 本地运行（需要访问剪映 User Data 目录），
浏览器 / Chrome 无法直接写入该路径。

用法:
  cd jyconvert && python3 python/jianying/import_draft.py \
    --draft-dir ~/Downloads/my_draft \
    --jianying-name my_draft
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from capcut.lib import (
    load_json,
    new_uuid,
    now_us,
    regenerate_uuids,
    replace_path_prefix,
    save_json,
    summarize_draft,
    update_draft_root_paths,
    walk_replace_paths,
    UUID_PATTERN,
)
from jianying.lib import jianying_drafts_root


def _same_draft_folder(entry_path: str, draft_dir: Path) -> bool:
    if not entry_path:
        return False
    try:
        return Path(entry_path).resolve() == draft_dir
    except OSError:
        return False


def register_in_jianying_root_meta(
    draft_dir: Path,
    draft_id: str,
    draft_name: str,
    drafts_root: Path,
) -> None:
    """在剪映 root_meta_info.json 中注册新草稿。"""
    root_meta_path = drafts_root / "root_meta_info.json"
    if root_meta_path.exists():
        root_meta = load_json(root_meta_path)
    else:
        root_meta = {
            "all_draft_store": [],
            "draft_ids": 0,
            "root_path": str(drafts_root),
        }

    draft_dir = draft_dir.resolve()
    store = root_meta.get("all_draft_store", [])
    store = [
        d
        for d in store
        if d.get("draft_id") != draft_id
        and not _same_draft_folder(str(d.get("draft_fold_path", "")), draft_dir)
    ]

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
        "draft_root_path": str(drafts_root),
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
    root_meta["root_path"] = str(drafts_root)
    save_json(root_meta_path, root_meta)
    print("  已注册到 root_meta_info.json")


def rewrite_draft_paths(draft_dir: Path, src_dir: Path, drafts_root: Path) -> None:
    """将草稿 JSON 中的绝对路径从源目录重写为目标目录。"""
    src = str(src_dir.resolve())
    dst = str(draft_dir.resolve())
    path_mapping = {src: dst}
    for fp in draft_dir.rglob("*.json"):
        data = load_json(fp)
        replace_path_prefix(data, src, dst)
        walk_replace_paths(data, path_mapping)
        save_json(fp, data)
    update_draft_root_paths(draft_dir, drafts_root, path_mapping)


def detect_timeline_id(draft_dir: Path, info: dict, meta: dict) -> str:
    timelines_root = draft_dir / "Timelines"
    if timelines_root.is_dir():
        for child in timelines_root.iterdir():
            if child.is_dir() and UUID_PATTERN.match(child.name):
                return child.name
    return str(info.get("id") or meta.get("draft_id") or "")


def rekey_jianying_timelines(draft_dir: Path, old_id: str, new_id: str) -> None:
    if not old_id or not new_id or old_id == new_id:
        return

    timelines_root = draft_dir / "Timelines"
    old_dir = timelines_root / old_id
    new_dir = timelines_root / new_id
    if old_dir.exists():
        new_dir.parent.mkdir(parents=True, exist_ok=True)
        if new_dir.exists():
            shutil.rmtree(new_dir)
        old_dir.rename(new_dir)

    project_path = timelines_root / "project.json"
    if project_path.exists():
        project = load_json(project_path)
        project["main_timeline_id"] = new_id
        for timeline in project.get("timelines", []):
            if timeline.get("id") == old_id:
                timeline["id"] = new_id
        save_json(project_path, project)

    layout_path = draft_dir / "timeline_layout.json"
    if layout_path.exists():
        layout = load_json(layout_path)
        layout["activeTimeline"] = new_id
        for dock in layout.get("dockItems", []):
            timeline_ids = dock.get("timelineIds", [])
            dock["timelineIds"] = [new_id if item == old_id else item for item in timeline_ids]
        save_json(layout_path, layout)


def assign_new_jianying_draft_identity(
    draft_dir: Path,
    drafts_root: Path,
    draft_name: str,
) -> str:
    """导入时为剪映草稿生成全新 ID，避免多次导入共用同一 draft_id。"""
    info = load_json(draft_dir / "draft_info.json")
    meta = load_json(draft_dir / "draft_meta_info.json")
    old_timeline_id = detect_timeline_id(draft_dir, info, meta)

    regenerate_uuids(info, meta)
    new_id = new_uuid()

    rekey_jianying_timelines(draft_dir, old_timeline_id, new_id)

    info["id"] = new_id
    info["path"] = str(draft_dir)
    info["name"] = draft_name
    info["create_time"] = 0
    info["update_time"] = 0

    meta["draft_id"] = new_id
    meta["draft_name"] = draft_name
    meta["draft_fold_path"] = str(draft_dir)
    meta["draft_root_path"] = str(drafts_root)
    meta["draft_cover"] = "draft_cover.jpg"
    meta["tm_draft_create"] = now_us()
    meta["tm_draft_modified"] = now_us()

    save_json(draft_dir / "draft_info.json", info)
    save_json(draft_dir / "draft_meta_info.json", meta)

    timeline_info = draft_dir / "Timelines" / new_id / "draft_info.json"
    if timeline_info.parent.exists():
        save_json(timeline_info, info)

    cover = draft_dir / "draft_cover.jpg"
    if cover.exists():
        timeline_cover = draft_dir / "Timelines" / new_id / "draft_cover.jpg"
        if timeline_info.parent.exists():
            shutil.copy2(cover, timeline_cover)

    for name in (
        "draft_virtual_store.json",
        "attachment_editing.json",
        "key_value.json",
        "attachment_pc_common.json",
    ):
        fp = draft_dir / name
        if fp.exists():
            data = load_json(fp)
            save_json(fp, data)

    return new_id


def import_draft_to_jianying(
    src_draft: Path,
    jianying_name: str,
    drafts_root: str | Path | None = None,
) -> Path:
    """复制本地草稿到剪映目录并注册。"""
    drafts_root = jianying_drafts_root(drafts_root)
    src_draft = src_draft.resolve()
    if not src_draft.is_dir():
        raise FileNotFoundError(f"草稿目录不存在: {src_draft}")
    if not (src_draft / "draft_info.json").exists():
        raise FileNotFoundError(f"草稿不完整，缺少 draft_info.json: {src_draft}")

    dst = drafts_root / jianying_name
    if dst.exists():
        shutil.rmtree(dst)

    print(f"[1/3] 复制草稿: {src_draft} → {dst}")
    shutil.copytree(src_draft, dst)

    print("[2/3] 重写路径 ...")
    rewrite_draft_paths(dst, src_draft, drafts_root)

    print("[3/3] 生成独立草稿 ID 并注册到剪映 ...")
    draft_id = assign_new_jianying_draft_identity(dst, drafts_root, jianying_name)
    register_in_jianying_root_meta(dst, draft_id, jianying_name, drafts_root)
    return dst


def main() -> None:
    parser = argparse.ArgumentParser(description="本地剪映草稿 → 剪映 Pro（步骤 2/2）")
    parser.add_argument(
        "--draft-dir",
        type=Path,
        required=True,
        help="本地剪映草稿目录（步骤 1 convert.py 输出的目录，须含 draft_info.json）",
    )
    parser.add_argument(
        "--jianying-name",
        required=True,
        help="导入后在剪映中显示的草稿名称（同时作为剪映目录下的文件夹名）",
    )
    parser.add_argument(
        "--jianying-drafts-root",
        type=Path,
        help="剪映草稿根目录（com.lveditor.draft）；Windows 上通常需手动指定",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("本地剪映草稿 → 剪映 Pro（步骤 2/2）")
    print("=" * 60)

    src = args.draft_dir.expanduser().resolve()
    print(f"\n源草稿: {src}")

    dst = import_draft_to_jianying(src, args.jianying_name, args.jianying_drafts_root)
    summarize_draft(dst)

    print("\n✓ 导入完成")
    print(f"  剪映草稿: {dst}")
    print(f"  剪映草稿根目录: {jianying_drafts_root(args.jianying_drafts_root)}")
    print("  请重启剪映或刷新草稿列表查看")


if __name__ == "__main__":
    main()
