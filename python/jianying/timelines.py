"""剪映多时间线草稿辅助函数。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from capcut.lib import load_json
from jianying.decrypt import is_encrypted_draft_file


def list_timelines(draft_dir: Path) -> list[dict[str, Any]]:
    """从明文 project.json / timeline_layout.json 列出时间线。"""
    draft_dir = draft_dir.resolve()
    timelines_root = draft_dir / "Timelines"
    name_map: dict[str, str] = {}
    active_id = ""

    layout_path = draft_dir / "timeline_layout.json"
    if layout_path.exists():
        layout = load_json(layout_path)
        active_id = layout.get("activeTimeline", "")
        for dock in layout.get("dockItems", []):
            ids = dock.get("timelineIds", [])
            names = dock.get("timelineNames", [])
            for index, timeline_id in enumerate(ids):
                label = names[index] if index < len(names) else timeline_id
                name_map[timeline_id] = label

    project_path = timelines_root / "project.json"
    project_timelines: list[dict[str, Any]] = []
    main_id = ""
    if project_path.exists():
        project = load_json(project_path)
        main_id = project.get("main_timeline_id", "")
        project_timelines = project.get("timelines", [])

    if project_timelines:
        items = project_timelines
    elif timelines_root.is_dir():
        items = [{"id": child.name} for child in timelines_root.iterdir() if child.is_dir()]
    else:
        return []

    result: list[dict[str, Any]] = []
    for item in items:
        timeline_id = item.get("id", "")
        if not timeline_id:
            continue
        info_path = timelines_root / timeline_id / "draft_info.json"
        encrypted = info_path.exists() and is_encrypted_draft_file(info_path)
        result.append({
            "id": timeline_id,
            "name": item.get("name") or name_map.get(timeline_id, timeline_id),
            "is_main": timeline_id == main_id,
            "is_active": timeline_id == active_id,
            "draft_info": str(info_path),
            "encrypted": encrypted,
        })
    return result


def resolve_timeline_id(
    draft_dir: Path,
    *,
    timeline_id: str | None = None,
    timeline_name: str | None = None,
) -> str | None:
    timelines = list_timelines(draft_dir)
    if not timelines:
        return None

    if timeline_id:
        for item in timelines:
            if item["id"].upper() == timeline_id.upper():
                return item["id"]
        raise ValueError(f"找不到时间线 id: {timeline_id}")

    if timeline_name:
        for item in timelines:
            if item["name"] == timeline_name:
                return item["id"]
        raise ValueError(f"找不到时间线名称: {timeline_name}")

    for item in timelines:
        if item.get("is_active"):
            return item["id"]
    for item in timelines:
        if item.get("is_main"):
            return item["id"]
    return timelines[0]["id"]


def resolve_draft_info_path(
    draft_dir: Path,
    *,
    timeline_id: str | None = None,
    timeline_name: str | None = None,
    draft_info: Path | None = None,
) -> Path:
    if draft_info:
        return draft_info.resolve()

    draft_dir = draft_dir.resolve()
    timelines = list_timelines(draft_dir)
    if timelines:
        resolved_id = resolve_timeline_id(
            draft_dir,
            timeline_id=timeline_id,
            timeline_name=timeline_name,
        )
        if resolved_id:
            return draft_dir / "Timelines" / resolved_id / "draft_info.json"

    return draft_dir / "draft_info.json"
