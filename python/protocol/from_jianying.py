"""将剪映/CapCut draft_info.json 转为 NGLEngine 协议 JSON。"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from protocol.converter import (
    CAPCUT_REF_FONT_SIZE,
    MICROSECONDS,
    NGL_REF_CANVAS_HEIGHT,
    NGL_REF_FONT_PX,
)

PROTOCOL_TRACK_TYPES = {"video", "audio", "text", "image"}


@dataclass
class ReverseContext:
    draft_dir: Path
    output_dir: Path
    font_source: Path
    font_filename: str = "字制区喜脉体.ttf"
    protocol_id: str = "converted_from_jianying"

    assets_dir: Path = field(init=False)
    fonts_dir: Path = field(init=False)
    material_map: dict[str, str] = field(default_factory=dict)
    copied_files: set[Path] = field(default_factory=set)
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.assets_dir = self.output_dir / "assets"
        self.fonts_dir = self.output_dir / "fonts"
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self.fonts_dir.mkdir(parents=True, exist_ok=True)
        if self.font_source.exists():
            dst = self.fonts_dir / self.font_filename
            if dst not in self.copied_files:
                shutil.copy2(self.font_source, dst)
                self.copied_files.add(dst)


def us_to_ms(value: int | float) -> int:
    return int(round(float(value) / MICROSECONDS))


def timerange_to_ms(tr: dict[str, Any] | None) -> dict[str, int]:
    tr = tr or {}
    return {
        "start": us_to_ms(tr.get("start", 0)),
        "duration": us_to_ms(tr.get("duration", 0)),
    }


def capcut_font_size_to_ngl(capcut_size: float, canvas_height: int) -> float:
    height = canvas_height if canvas_height > 0 else NGL_REF_CANVAS_HEIGHT
    ngl_size = (
        float(capcut_size)
        * NGL_REF_FONT_PX
        * height
        / (CAPCUT_REF_FONT_SIZE * NGL_REF_CANVAS_HEIGHT)
    )
    return round(max(1.0, ngl_size), 3)


def capcut_stroke_width_to_ngl(width: float) -> float:
    return round(max(0.0, float(width) / 0.4), 4)


def denormalize_volume(raw: int | float | None) -> int:
    if raw is None:
        return 100
    value = float(raw)
    if value <= 1.0:
        return int(round(value * 100))
    return int(round(value))


def capcut_y_to_ngl_y(capcut_y: float) -> float:
    return -float(capcut_y)


def extract_solid(style_part: dict[str, Any] | None) -> tuple[list[float], float]:
    style_part = style_part or {}
    content = style_part.get("content") or {}
    solid = content.get("solid") or {}
    color = solid.get("color") or [1.0, 1.0, 1.0]
    alpha = float(solid.get("alpha", 1.0))
    return [float(c) for c in color], alpha


def capcut_style_to_ngl(style: dict[str, Any], canvas_height: int, font_path: str) -> dict[str, Any]:
    fill_color, fill_alpha = extract_solid(style.get("fill"))
    out: dict[str, Any] = {
        "range": style.get("range", [0, 0]),
        "size": capcut_font_size_to_ngl(float(style.get("size", 8.0)), canvas_height),
        "letter_spacing": float(style.get("letter_spacing", 0.0)),
        "line_height": float(style.get("line_height", 1.12)),
        "font": {"id": "", "path": font_path},
        "fill": {"alpha": fill_alpha, "color": fill_color},
    }
    strokes = style.get("strokes") or []
    if strokes:
        stroke = strokes[0]
        stroke_color, stroke_alpha = extract_solid(stroke)
        out["stroke"] = {
            "color": stroke_color,
            "alpha": stroke_alpha,
            "width": capcut_stroke_width_to_ngl(stroke.get("width", 0.08)),
        }
    return out


def capcut_text_content_to_ngl(content_str: str, canvas_height: int, font_path: str) -> str:
    data = json.loads(content_str)
    text = data.get("text", "")
    styles = [capcut_style_to_ngl(style, canvas_height, font_path) for style in data.get("styles", [])]
    if not styles and text:
        styles = [capcut_style_to_ngl({"range": [0, len(text)], "size": 8.0}, canvas_height, font_path)]
    return json.dumps({"styles": styles, "text": text}, ensure_ascii=False)


def capcut_clip_to_protocol(
    clip: dict[str, Any] | None,
    *,
    sticker: bool = False,
) -> dict[str, Any] | None:
    if not clip:
        return None
    transform = clip.get("transform") or {}
    scale = clip.get("scale") or {"x": 1.0, "y": 1.0}
    capcut_x = float(transform.get("x", 0.0))
    capcut_y = float(transform.get("y", 0.0))
    if sticker:
        # 贴纸/小图：CapCut y 正方向向下，与 NGLEngine 图像轨一致，不要翻转。
        ngl_x, ngl_y = capcut_x, capcut_y
    else:
        ngl_x, ngl_y = capcut_x, capcut_y_to_ngl_y(capcut_y)
    out: dict[str, Any] = {
        "alpha": clip.get("alpha", 1.0),
        "flip": clip.get("flip") or {"horizontal": False, "vertical": False},
        "transform": {
            "rotation": clip.get("rotation", 0.0),
            "scale": {"x": scale.get("x", 1.0), "y": scale.get("y", 1.0)},
            "translate": {"x": ngl_x, "y": ngl_y},
        },
    }
    if sticker:
        # 保持原始像素尺寸，避免 LetterBox 把小 GIF 放大到整屏。
        out["scaleMode"] = 0
    return out


DRAFT_PATH_PLACEHOLDER = re.compile(
    r"^##_draftpath_placeholder_[0-9A-Fa-f\-]+_##/(.*)$"
)


def resolve_sticker_file(path: Path) -> Path | None:
    """CapCut 贴纸素材 path 可能是目录，实际 GIF 在 final.gif。"""
    if path.is_file():
        return path
    if not path.is_dir():
        return None
    for name in ("final.gif", "final.webp", "final.png"):
        candidate = path / name
        if candidate.is_file():
            return candidate
    for candidate in sorted(path.glob("*.gif")):
        return candidate
    return None


def read_image_size(path: Path) -> tuple[int, int]:
    suffix = path.suffix.lower()
    if suffix == ".gif" and path.stat().st_size >= 10:
        with path.open("rb") as handle:
            header = handle.read(10)
        if header[:3] == b"GIF":
            return (
                int.from_bytes(header[6:8], "little"),
                int.from_bytes(header[8:10], "little"),
            )
    return 0, 0


def resolve_draft_media_path(raw: str, draft_dir: Path) -> Path | None:
    if not raw:
        return None
    p = Path(raw)
    if p.is_absolute() and p.exists():
        if p.is_dir():
            sticker = resolve_sticker_file(p)
            if sticker:
                return sticker.resolve()
        return p.resolve()

    placeholder = DRAFT_PATH_PLACEHOLDER.match(raw.strip())
    if placeholder:
        candidate = draft_dir / placeholder.group(1)
        if candidate.exists():
            return candidate.resolve()

    candidates = [
        draft_dir / raw,
        draft_dir / raw.lstrip("./"),
        draft_dir / "textReading" / Path(raw).name,
        draft_dir / "Resources" / "imported" / Path(raw).name,
        draft_dir / "Resources" / Path(raw).name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def export_asset(src: Path, ctx: ReverseContext, *, export_name: str | None = None) -> str:
    dst = ctx.assets_dir / (export_name or src.name)
    if dst not in ctx.copied_files:
        shutil.copy2(src, dst)
        ctx.copied_files.add(dst)
    return f"./assets/{dst.name}"


def infer_protocol_track_type(track: dict[str, Any], draft_info: dict[str, Any]) -> str:
    name = track.get("name") or ""
    match = re.match(r"track_(video|audio|text|image)_", name)
    if match:
        return match.group(1)

    capcut_type = track.get("type", "")
    if capcut_type == "text":
        return "text"
    if capcut_type == "audio":
        return "audio"
    if capcut_type == "sticker":
        return "image"

    mat_lookup = build_material_lookup(draft_info)
    for seg in track.get("segments", []):
        mat = mat_lookup.get(seg.get("material_id", ""))
        if not mat:
            continue
        mat_type = mat.get("type", "")
        if mat_type == "photo":
            return "image"
        if mat_type == "video":
            path_name = (mat.get("material_name") or mat.get("path") or "").lower()
            if path_name.endswith(".gif"):
                return "image"
            return "video"
    return "video" if capcut_type == "video" else capcut_type or "video"


def build_material_lookup(draft_info: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    materials = draft_info.get("materials") or {}
    for item in materials.get("videos") or []:
        lookup[item["id"]] = item
    for item in materials.get("audios") or []:
        lookup[item["id"]] = item
    for item in materials.get("texts") or []:
        lookup[item["id"]] = item
    for item in materials.get("stickers") or []:
        lookup[item["id"]] = item
    return lookup


def next_material_id(kind: str, counters: dict[str, int]) -> str:
    counters[kind] = counters.get(kind, -1) + 1
    return f"material_{kind}_{counters[kind]}"


def convert_video_material(item: dict[str, Any], ctx: ReverseContext, counters: dict[str, int]) -> dict[str, Any] | None:
    src = resolve_draft_media_path(item.get("path", ""), ctx.draft_dir)
    if not src:
        ctx.warnings.append(f"找不到视频素材: {item.get('path')}")
        return None
    rel = export_asset(src, ctx)
    old_id = item["id"]
    new_id = next_material_id("video", counters)
    ctx.material_map[old_id] = new_id
    return {
        "duration": us_to_ms(item.get("duration", 0)),
        "height": item.get("height", 0),
        "id": new_id,
        "name": item.get("material_name") or src.name,
        "path": rel,
        "type": "",
        "width": item.get("width", 0),
    }


def convert_image_material(item: dict[str, Any], ctx: ReverseContext, counters: dict[str, int]) -> dict[str, Any] | None:
    src = resolve_draft_media_path(item.get("path", ""), ctx.draft_dir)
    if not src:
        ctx.warnings.append(f"找不到图片素材: {item.get('path')}")
        return None
    rel = export_asset(src, ctx)
    old_id = item["id"]
    new_id = next_material_id("image", counters)
    ctx.material_map[old_id] = new_id
    is_gif = src.suffix.lower() == ".gif" or item.get("type") == "video"
    return {
        "duration": us_to_ms(item.get("duration", 0)),
        "height": item.get("height", 0),
        "id": new_id,
        "name": item.get("material_name") or src.name,
        "path": rel,
        "type": "gif" if is_gif else "image",
        "width": item.get("width", 0),
    }


def convert_sticker_material(item: dict[str, Any], ctx: ReverseContext, counters: dict[str, int]) -> dict[str, Any] | None:
    src = resolve_draft_media_path(item.get("path", ""), ctx.draft_dir)
    if not src:
        ctx.warnings.append(f"找不到贴纸素材: {item.get('path')}")
        return None
    sticker_id = str(item.get("sticker_id") or item.get("resource_id") or src.stem)
    export_name = f"{sticker_id}.gif" if src.suffix.lower() == ".gif" else src.name
    rel = export_asset(src, ctx, export_name=export_name)
    old_id = item["id"]
    new_id = next_material_id("image", counters)
    ctx.material_map[old_id] = new_id
    width, height = read_image_size(src)
    return {
        "duration": us_to_ms(item.get("duration", 0)),
        "height": height,
        "id": new_id,
        "name": item.get("name") or export_name,
        "path": rel,
        "type": "gif",
        "width": width,
    }


def convert_audio_material(item: dict[str, Any], ctx: ReverseContext, counters: dict[str, int]) -> dict[str, Any] | None:
    src = resolve_draft_media_path(item.get("path", ""), ctx.draft_dir)
    if not src:
        ctx.warnings.append(f"找不到音频素材: {item.get('path')}")
        return None
    rel = export_asset(src, ctx)
    old_id = item["id"]
    new_id = next_material_id("audio", counters)
    ctx.material_map[old_id] = new_id
    return {
        "id": new_id,
        "name": item.get("name") or item.get("material_name") or src.name,
        "path": rel,
        "type": "",
    }


def convert_text_material(item: dict[str, Any], ctx: ReverseContext, counters: dict[str, int], canvas_height: int) -> dict[str, Any] | None:
    content_str = item.get("content", "")
    if not content_str:
        ctx.warnings.append(f"跳过空文字素材: {item.get('id')}")
        return None
    old_id = item["id"]
    new_id = next_material_id("text", counters)
    ctx.material_map[old_id] = new_id
    font_path = f"./fonts/{ctx.font_filename}"
    out: dict[str, Any] = {
        "id": new_id,
        "alignment": item.get("alignment", 1),
        "content": capcut_text_content_to_ngl(content_str, canvas_height, font_path),
    }
    return out


def convert_segment(
    seg: dict[str, Any],
    *,
    track_type: str,
    capcut_track_type: str = "",
    seg_index: int,
    track_index: int,
    ctx: ReverseContext,
) -> dict[str, Any] | None:
    old_mid = seg.get("material_id", "")
    new_mid = ctx.material_map.get(old_mid)
    if not new_mid:
        ctx.warnings.append(f"跳过片段，找不到素材映射: {old_mid}")
        return None

    source_tr = timerange_to_ms(seg.get("source_timerange"))
    target_tr = timerange_to_ms(seg.get("target_timerange"))
    if track_type in {"text", "image"} and source_tr["duration"] == 0:
        source_tr = {"start": 0, "duration": target_tr["duration"]}

    prefix = {"video": "v", "audio": "a", "text": "text", "image": "image"}.get(track_type, "s")
    out: dict[str, Any] = {
        "id": f"segment_{prefix}_{track_index}_{seg_index}",
        "material_id": new_mid,
        "muted": bool(seg.get("muted", False)),
        "source_timerange": source_tr,
        "target_timerange": target_tr,
    }

    if track_type in {"video", "image", "text"}:
        out["visible"] = bool(seg.get("visible", True))
        clip = capcut_clip_to_protocol(
            seg.get("clip"),
            sticker=(capcut_track_type == "sticker"),
        )
        if clip:
            out["clip"] = clip

    if track_type in {"video", "audio"}:
        out["volume"] = denormalize_volume(seg.get("volume"))

    return out


def convert_draft_to_protocol(draft_info: dict[str, Any], ctx: ReverseContext) -> dict[str, Any]:
    canvas = draft_info.get("canvas_config") or {}
    width = int(canvas.get("width") or 720)
    height = int(canvas.get("height") or 1280)
    font_path = f"./fonts/{ctx.font_filename}"

    counters: dict[str, int] = {}
    materials_out: dict[str, list[dict[str, Any]]] = {
        "videos": [],
        "audios": [],
        "texts": [],
        "images": [],
    }

    mat_lookup = build_material_lookup(draft_info)
    referenced_ids: set[str] = set()
    for track in draft_info.get("tracks", []):
        for seg in track.get("segments", []):
            mid = seg.get("material_id")
            if mid:
                referenced_ids.add(mid)

    for item in draft_info.get("materials", {}).get("videos") or []:
        if item["id"] not in referenced_ids:
            continue
        mat_type = item.get("type", "video")
        path_name = (item.get("material_name") or item.get("path") or "").lower()
        if mat_type == "photo" or path_name.endswith((".png", ".jpg", ".jpeg", ".webp")):
            mat = convert_image_material(item, ctx, counters)
            if mat:
                materials_out["images"].append(mat)
        elif path_name.endswith(".gif"):
            mat = convert_image_material(item, ctx, counters)
            if mat:
                materials_out["images"].append(mat)
        else:
            mat = convert_video_material(item, ctx, counters)
            if mat:
                materials_out["videos"].append(mat)

    for item in draft_info.get("materials", {}).get("audios") or []:
        if item["id"] not in referenced_ids:
            continue
        mat = convert_audio_material(item, ctx, counters)
        if mat:
            materials_out["audios"].append(mat)

    for item in draft_info.get("materials", {}).get("texts") or []:
        if item["id"] not in referenced_ids:
            continue
        mat = convert_text_material(item, ctx, counters, height)
        if mat:
            materials_out["texts"].append(mat)

    for item in draft_info.get("materials", {}).get("stickers") or []:
        if item["id"] not in referenced_ids:
            continue
        mat = convert_sticker_material(item, ctx, counters)
        if mat:
            materials_out["images"].append(mat)

    tracks_out: list[dict[str, Any]] = []
    for track_index, track in enumerate(draft_info.get("tracks", [])):
        track_type = infer_protocol_track_type(track, draft_info)
        if track_type not in PROTOCOL_TRACK_TYPES:
            ctx.warnings.append(f"跳过未知轨道类型: {track.get('type')} ({track.get('name')})")
            continue

        segments: list[dict[str, Any]] = []
        for seg_index, seg in enumerate(track.get("segments", [])):
            converted = convert_segment(
                seg,
                track_type=track_type,
                capcut_track_type=track.get("type", ""),
                seg_index=seg_index,
                track_index=track_index,
                ctx=ctx,
            )
            if converted:
                segments.append(converted)

        if not segments:
            continue

        track_name = track.get("name") or ""
        if not track_name.startswith("track_"):
            track_name = f"track_{track_type}_{track_index}"

        tracks_out.append({
            "id": track_name,
            "type": track_type,
            "visible": True,
            "muted": False,
            "segments": segments,
        })

    return {
        "canvas_config": {"height": height, "width": width},
        "duration": us_to_ms(draft_info.get("duration", 0)),
        "fps": float(draft_info.get("fps", 30.0)),
        "id": ctx.protocol_id,
        "materials": materials_out,
        "tracks": tracks_out,
    }


def write_protocol_bundle(draft_info: dict[str, Any], ctx: ReverseContext) -> Path:
    protocol = convert_draft_to_protocol(draft_info, ctx)
    out_json = ctx.output_dir / "converted_protocol.json"
    out_json.write_text(json.dumps(protocol, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_json


def summarize_material(item: dict[str, Any], draft_dir: Path) -> dict[str, Any]:
    """提取素材摘要，不复制文件。"""
    path_raw = item.get("path") or ""
    resolved = resolve_draft_media_path(path_raw, draft_dir)
    out: dict[str, Any] = {
        "id": item.get("id", ""),
        "type": item.get("type", ""),
        "name": item.get("material_name") or item.get("name") or (resolved.name if resolved else Path(path_raw).name),
        "path": str(resolved) if resolved else path_raw,
    }
    if "duration" in item:
        out["duration_ms"] = us_to_ms(item.get("duration", 0))
    if item.get("width"):
        out["width"] = item.get("width")
    if item.get("height"):
        out["height"] = item.get("height")
    if item.get("type") == "text" or "content" in item:
        try:
            content = json.loads(item.get("content", "{}"))
            out["text"] = content.get("text", "")
        except json.JSONDecodeError:
            out["text"] = ""
    return out


def extract_tracks_info(draft_info: dict[str, Any], draft_dir: Path) -> dict[str, Any]:
    """只提取轨道与片段信息（毫秒时间轴），不导出媒体资源。"""
    canvas = draft_info.get("canvas_config") or {}
    width = int(canvas.get("width") or 720)
    height = int(canvas.get("height") or 1280)
    mat_lookup = build_material_lookup(draft_info)

    tracks_out: list[dict[str, Any]] = []
    for track_index, track in enumerate(draft_info.get("tracks", [])):
        track_type = infer_protocol_track_type(track, draft_info)
        segments_out: list[dict[str, Any]] = []

        for seg_index, seg in enumerate(track.get("segments", [])):
            mid = seg.get("material_id", "")
            mat = mat_lookup.get(mid)
            source_tr = timerange_to_ms(seg.get("source_timerange"))
            target_tr = timerange_to_ms(seg.get("target_timerange"))
            if track_type in {"text", "image"} and source_tr["duration"] == 0:
                source_tr = {"start": 0, "duration": target_tr["duration"]}

            seg_out: dict[str, Any] = {
                "id": seg.get("id") or f"segment_{track_index}_{seg_index}",
                "material_id": mid,
                "source_timerange": source_tr,
                "target_timerange": target_tr,
                "muted": bool(seg.get("muted", False)),
            }
            if mat:
                seg_out["material"] = summarize_material(mat, draft_dir)

            if track_type in {"video", "image", "text"}:
                seg_out["visible"] = bool(seg.get("visible", True))
                clip = capcut_clip_to_protocol(
                    seg.get("clip"),
                    sticker=(track.get("type") == "sticker"),
                )
                if clip:
                    seg_out["clip"] = clip

            if track_type in {"video", "audio"}:
                seg_out["volume"] = denormalize_volume(seg.get("volume"))

            segments_out.append(seg_out)

        if not segments_out:
            continue

        track_name = track.get("name") or f"track_{track_type}_{track_index}"
        tracks_out.append({
            "id": track_name,
            "type": track_type,
            "capcut_type": track.get("type", ""),
            "segments": segments_out,
        })

    return {
        "canvas_config": {"width": width, "height": height},
        "duration_ms": us_to_ms(draft_info.get("duration", 0)),
        "fps": float(draft_info.get("fps", 30.0)),
        "tracks": tracks_out,
    }
