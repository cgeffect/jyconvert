"""CapCut 草稿导入/导出共享工具库。"""

from __future__ import annotations

import copy
import json
import re
import shutil
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

from app_root import python_root

CAPCUT_ROOT = Path("/Users/xy/Movies/CapCut")
JYCONVERT_ROOT = python_root()

DRAFTS_REL = Path("User Data/Projects/com.lveditor.draft")
MANIFEST_NAME = "manifest.json"

CAPCUT_PATH_ALIASES = [
    CAPCUT_ROOT,
    Path("/Users/xy/Library/Containers/com.lemon.lvoverseas/Data/Movies/CapCut"),
]

PATH_KEYS = {
    "path",
    "file_Path",
    "draft_fold_path",
    "draft_root_path",
    "draft_json_file",
    "draft_cover",
    "intensifies_path",
    "intensifies_audio_path",
    "reverse_path",
    "reverse_intensifies_path",
    "media_path",
    "algorithm_artifact_path",
    "aigc_current_artifact_path",
    "static_cover_image_path",
    "live_photo_cover_path",
    "cartoon_path",
    "mask_video_path",
}

MATERIAL_CATEGORIES = (
    "videos", "audios", "images", "stickers", "video_effects",
    "effects", "transitions", "filters", "canvases", "texts",
    "handwrites", "flowers", "green_screens",
)

DRAFT_JSON_FILES = (
    "draft_info.json",
    "draft_meta_info.json",
    "draft_virtual_store.json",
    "attachment_editing.json",
    "key_value.json",
)

DRAFT_EXTRA_FILES = (
    "draft_cover.jpg",
    "draft_settings",
    "draft_agency_config.json",
    "draft_biz_config.json",
    "timeline_layout.json",
    "performance_opt_info.json",
)

DRAFT_SUBDIRS = (
    "common_attachment", "Resources", "adjust_mask",
    "matting", "qr_upload", "smart_crop",
)

UUID_PATTERN = re.compile(
    r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$"
)


def new_uuid() -> str:
    return str(uuid.uuid4()).upper()


def capcut_drafts_root() -> Path:
    return CAPCUT_ROOT / DRAFTS_REL


def jyconvert_drafts_root() -> Path:
    return JYCONVERT_ROOT / DRAFTS_REL


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def normalize_capcut_path(raw: str) -> Path | None:
    if not raw or not isinstance(raw, str):
        return None
    p = Path(raw)
    if p.is_absolute() and p.exists():
        return p.resolve()
    for root in CAPCUT_PATH_ALIASES:
        marker = "User Data/"
        if marker in raw:
            suffix = raw.split(marker, 1)[1]
            candidate = root / "User Data" / suffix
            if candidate.exists():
                return candidate.resolve()
        if raw.startswith(str(root)):
            candidate = Path(raw)
            if candidate.exists():
                return candidate.resolve()
    return p if p.exists() else None


def is_under_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def is_under_capcut(path: Path) -> bool:
    return any(is_under_root(path, root) for root in CAPCUT_PATH_ALIASES)


def is_under_jyconvert(path: Path) -> bool:
    return is_under_root(path, JYCONVERT_ROOT)


def relative_to_root(path: Path, root: Path) -> Path:
    return path.resolve().relative_to(root.resolve())


def capcut_relative(path: Path) -> Path:
    for root in CAPCUT_PATH_ALIASES:
        if is_under_root(path, root):
            return relative_to_root(path, root)
    raise ValueError(f"路径不在 CapCut 目录下: {path}")


def jyconvert_relative(path: Path) -> Path:
    return relative_to_root(path, JYCONVERT_ROOT)


def jyconvert_target(rel: Path) -> Path:
    return JYCONVERT_ROOT / rel


def capcut_target(rel: Path) -> Path:
    return CAPCUT_ROOT / rel


def walk_collect_uuids(obj: Any, found: set[str]) -> None:
    if isinstance(obj, str) and UUID_PATTERN.match(obj):
        found.add(obj)
    elif isinstance(obj, dict):
        for value in obj.values():
            walk_collect_uuids(value, found)
    elif isinstance(obj, list):
        for item in obj:
            walk_collect_uuids(item, found)


def walk_replace_uuids(obj: Any, mapping: dict[str, str]) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, str) and value in mapping:
                obj[key] = mapping[value]
            else:
                walk_replace_uuids(value, mapping)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, str) and item in mapping:
                obj[i] = mapping[item]
            else:
                walk_replace_uuids(item, mapping)


def walk_replace_paths(obj: Any, mapping: dict[str, str]) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in PATH_KEYS and isinstance(value, str) and value in mapping:
                obj[key] = mapping[value]
            else:
                walk_replace_paths(value, mapping)
    elif isinstance(obj, list):
        for item in obj:
            walk_replace_paths(item, mapping)


def replace_path_prefix(obj: Any, old_prefix: str, new_prefix: str) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in PATH_KEYS and isinstance(value, str) and old_prefix in value:
                obj[key] = value.replace(old_prefix, new_prefix)
            else:
                replace_path_prefix(value, old_prefix, new_prefix)
    elif isinstance(obj, list):
        for item in obj:
            replace_path_prefix(item, old_prefix, new_prefix)


def draft_folder_dates(draft_dir: Path) -> set[date]:
    dates: set[date] = set()
    meta = draft_dir / "draft_meta_info.json"
    if meta.exists():
        try:
            data = load_json(meta)
            for key in ("tm_draft_create", "tm_draft_modified"):
                ts = data.get(key)
                if isinstance(ts, (int, float)) and ts > 0:
                    dates.add(datetime.fromtimestamp(ts / 1_000_000).date())
        except (json.JSONDecodeError, OSError, OverflowError, ValueError):
            pass
    for name in ("draft_info.json", "draft_meta_info.json"):
        fp = draft_dir / name
        if fp.exists():
            try:
                dates.add(datetime.fromtimestamp(fp.stat().st_mtime).date())
            except OSError:
                pass
    try:
        dates.add(datetime.fromtimestamp(draft_dir.stat().st_mtime).date())
    except OSError:
        pass
    return dates


def find_today_draft(target_day: date | None = None) -> Path:
    target_day = target_day or date.today()
    drafts_root = capcut_drafts_root()
    if not drafts_root.exists():
        raise FileNotFoundError(f"CapCut 草稿目录不存在: {drafts_root}")

    candidates: list[tuple[datetime, Path]] = []
    for child in drafts_root.iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        if not (child / "draft_info.json").exists():
            continue
        if target_day in draft_folder_dates(child):
            mtime = datetime.fromtimestamp((child / "draft_info.json").stat().st_mtime)
            candidates.append((mtime, child))

    if not candidates:
        available = []
        for child in sorted(drafts_root.iterdir()):
            if child.is_dir() and (child / "draft_info.json").exists():
                available.append(f"  - {child.name} (dates={sorted(draft_folder_dates(child))})")
        hint = "\n".join(available) if available else "  (无草稿)"
        raise FileNotFoundError(f"未找到 {target_day} 创建或修改的草稿。\n现有草稿:\n{hint}")

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def find_draft_by_name(name: str, root: Path) -> Path:
    draft = root / name
    if not (draft / "draft_info.json").exists():
        raise FileNotFoundError(f"草稿不存在: {draft}")
    return draft


def collect_material_paths(draft_dir: Path) -> tuple[set[str], dict[str, Path]]:
    raw_paths: set[str] = set()
    info_path = draft_dir / "draft_info.json"
    meta_path = draft_dir / "draft_meta_info.json"

    if info_path.exists():
        info = load_json(info_path)
        for category in MATERIAL_CATEGORIES:
            for item in info.get("materials", {}).get(category, []):
                if isinstance(item, dict):
                    p = item.get("path")
                    if isinstance(p, str) and p.strip():
                        raw_paths.add(p.strip())

    if meta_path.exists():
        meta = load_json(meta_path)
        for group in meta.get("draft_materials", []):
            for item in group.get("value", []):
                if isinstance(item, dict):
                    p = item.get("file_Path") or item.get("path")
                    if isinstance(p, str) and p.strip():
                        raw_paths.add(p.strip())

    resolved: dict[str, Path] = {}
    for raw in raw_paths:
        p = normalize_capcut_path(raw)
        if not p or not p.exists():
            candidate = Path(raw)
            p = candidate.resolve() if candidate.exists() else None
        if p and p.exists():
            resolved[raw] = p

    return raw_paths, resolved


def regenerate_uuids(*objs: Any) -> None:
    old_uuids: set[str] = set()
    for obj in objs:
        walk_collect_uuids(obj, old_uuids)
    mapping = {u: new_uuid() for u in old_uuids}
    for obj in objs:
        walk_replace_uuids(obj, mapping)


def update_draft_root_paths(
    draft_dir: Path,
    drafts_root: Path,
    path_mapping: dict[str, str] | None = None,
) -> None:
    for name in DRAFT_JSON_FILES:
        fp = draft_dir / name
        if not fp.exists():
            continue
        data = load_json(fp)
        if path_mapping:
            walk_replace_paths(data, path_mapping)
        if name == "draft_meta_info.json":
            data["draft_fold_path"] = str(draft_dir)
            data["draft_root_path"] = str(drafts_root)
            cover = data.get("draft_cover", "")
            if isinstance(cover, str) and cover and not cover.startswith("/"):
                data["draft_cover"] = str(draft_dir / cover)
        if name == "draft_info.json":
            data["path"] = str(draft_dir)
        save_json(fp, data)


def copy_draft_assets(src: Path, dst: Path) -> None:
    for name in DRAFT_EXTRA_FILES:
        s = src / name
        if s.exists():
            copy_file(s, dst / name)
    for sub in DRAFT_SUBDIRS:
        s = src / sub
        if s.exists() and s.is_dir():
            copy_tree(s, dst / sub)


def summarize_draft(draft_dir: Path) -> None:
    info = load_json(draft_dir / "draft_info.json")
    print(f"\n── 草稿摘要: {draft_dir.name} ──")
    for track in info.get("tracks", []):
        print(f"  轨道 [{track.get('type', '?')}]: {len(track.get('segments', []))} 个片段")
    mats = info.get("materials", {})
    print(f"  视频: {len(mats.get('videos', []))}  贴图: {len(mats.get('stickers', []))}  特效: {len(mats.get('video_effects', []))}")


def save_manifest(data: dict[str, Any]) -> Path:
    path = JYCONVERT_ROOT / MANIFEST_NAME
    save_json(path, data)
    return path


def load_manifest() -> dict[str, Any]:
    path = JYCONVERT_ROOT / MANIFEST_NAME
    if not path.exists():
        raise FileNotFoundError(
            f"未找到 {MANIFEST_NAME}，请先运行 capcut/export_draft.py 导出草稿。"
        )
    return load_json(path)


def now_us() -> int:
    return int(datetime.now().timestamp() * 1_000_000)


def clone_draft_with_new_identity(
    src_dir: Path,
    dst_dir: Path,
    drafts_root: Path,
    draft_name: str,
    path_mapping: dict[str, str],
    src_prefix_replace: tuple[str, str] | None = None,
) -> str:
    """复制草稿目录并赋予全新 ID，返回新 draft_id。"""
    dst_dir.mkdir(parents=True, exist_ok=True)
    copy_draft_assets(src_dir, dst_dir)

    info = load_json(src_dir / "draft_info.json")
    meta = load_json(src_dir / "draft_meta_info.json")
    info = copy.deepcopy(info)
    meta = copy.deepcopy(meta)

    regenerate_uuids(info, meta)
    walk_replace_paths(info, path_mapping)
    walk_replace_paths(meta, path_mapping)

    draft_id = new_uuid()
    info["id"] = new_uuid()
    info["path"] = str(dst_dir)
    info["name"] = draft_name
    info["create_time"] = 0
    info["update_time"] = 0

    meta["draft_id"] = draft_id
    meta["draft_name"] = draft_name
    meta["draft_fold_path"] = str(dst_dir)
    meta["draft_root_path"] = str(drafts_root)
    meta["draft_cover"] = "draft_cover.jpg"
    meta["tm_draft_create"] = now_us()
    meta["tm_draft_modified"] = now_us()

    if src_prefix_replace:
        old, new = src_prefix_replace
        replace_path_prefix(info, old, new)
        replace_path_prefix(meta, old, new)

    save_json(dst_dir / "draft_info.json", info)
    save_json(dst_dir / "draft_meta_info.json", meta)

    for name in ("draft_virtual_store.json", "attachment_editing.json", "key_value.json"):
        fp = dst_dir / name
        if fp.exists():
            data = load_json(fp)
            if path_mapping:
                walk_replace_paths(data, path_mapping)
            if src_prefix_replace:
                replace_path_prefix(data, src_prefix_replace[0], src_prefix_replace[1])
            save_json(fp, data)

    return draft_id
