"""将 NGLEngine 协议 JSON 转为 CapCut draft_info.json 结构。"""

from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from shutil import which
from typing import Any, Literal

from capcut.lib import new_uuid, now_us

from app_root import python_root
from protocol.path_resolver import resolve_protocol_path as resolve_media_path

JYCONVERT_ROOT = python_root()


MICROSECONDS = 1000  # 协议毫秒 → CapCut 微秒

# NGL 协议 size 为画布像素；CapCut/Jianying 为内部相对字号。
# 标定：1280 高画布上 NGL 35px ≈ CapCut 8.0（与 pyJianYingDraft 默认一致）
NGL_REF_FONT_PX = 35.0
CAPCUT_REF_FONT_SIZE = 8.0
NGL_REF_CANVAS_HEIGHT = 1280


@dataclass
class ConversionContext:
    protocol_path: Path
    resource_root: Path
    draft_dir: Path
    imported_dir: Path
    fonts_dir: Path

    id_map: dict[str, str] = field(default_factory=dict)
    path_map: dict[str, str] = field(default_factory=dict)
    copied_files: set[Path] = field(default_factory=set)

    speeds: list[dict[str, Any]] = field(default_factory=list)
    canvases: list[dict[str, Any]] = field(default_factory=list)
    placeholder_infos: list[dict[str, Any]] = field(default_factory=list)
    sound_channel_mappings: list[dict[str, Any]] = field(default_factory=list)
    material_colors: list[dict[str, Any]] = field(default_factory=list)
    vocal_separations: list[dict[str, Any]] = field(default_factory=list)

    videos: list[dict[str, Any]] = field(default_factory=list)
    audios: list[dict[str, Any]] = field(default_factory=list)
    texts: list[dict[str, Any]] = field(default_factory=list)
    tracks: list[dict[str, Any]] = field(default_factory=list)

    meta_videos: list[dict[str, Any]] = field(default_factory=list)
    meta_audios: list[dict[str, Any]] = field(default_factory=list)

    canvas_width: int = 720
    canvas_height: int = 1280
    draft_id: str = ""
    draft_target: Literal["capcut", "jianying"] = "capcut"

    warnings: list[str] = field(default_factory=list)


def ms_to_us(value: int | float) -> int:
    return int(round(float(value) * MICROSECONDS))


def timerange_to_us(tr: dict[str, Any]) -> dict[str, int]:
    return {
        "start": ms_to_us(tr.get("start", 0)),
        "duration": ms_to_us(tr.get("duration", 0)),
    }


def utf16_byte_offset(text: str, char_index: int) -> int:
    return len(text[:char_index].encode("utf-16-le"))


def rgb_to_hex(color: list[float], alpha: float = 1.0) -> str:
    r = max(0, min(255, int(round(color[0] * 255))))
    g = max(0, min(255, int(round(color[1] * 255))))
    b = max(0, min(255, int(round(color[2] * 255))))
    a = max(0, min(255, int(round(alpha * 255))))
    return f"#{r:02X}{g:02X}{b:02X}{a:02X}"


def ratio_from_canvas(width: int, height: int) -> str:
    if width == 720 and height == 1280:
        return "9:16"
    if width == 1080 and height == 1920:
        return "9:16"
    if width == 1920 and height == 1080:
        return "16:9"
    if width == height:
        return "1:1"
    return "original"


def resolve_protocol_path(raw: str, ctx: ConversionContext) -> Path | None:
    """协议 path 优先相对协议 JSON 所在目录解析。"""
    return resolve_media_path(
        raw,
        ctx.protocol_path.parent,
        extra_roots=[ctx.resource_root, ctx.resource_root.parent],
    )


def import_file(src: Path, ctx: ConversionContext, subdir: str = "imported") -> Path:
    dst_dir = ctx.imported_dir if subdir == "imported" else ctx.fonts_dir
    dst = dst_dir / src.name
    if dst not in ctx.copied_files:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        ctx.copied_files.add(dst)
    return dst


def map_id(old_id: str, ctx: ConversionContext) -> str:
    if old_id not in ctx.id_map:
        ctx.id_map[old_id] = new_uuid()
    return ctx.id_map[old_id]


def normalize_volume(raw: int | float | None) -> float:
    if raw is None:
        return 1.0
    value = float(raw)
    if value > 1.0:
        return max(0.0, min(1.0, value / 100.0))
    return max(0.0, min(1.0, value))


def ngl_translate_y_to_capcut(ngl_y: float) -> float:
    """NGL y 轴：-1 顶部、1 底部；CapCut y 轴方向相反。"""
    return -float(ngl_y)


def convert_clip(clip: dict[str, Any] | None) -> dict[str, Any] | None:
    if not clip:
        return None
    transform = clip.get("transform") or {}
    translate = transform.get("translate") or {}
    scale = transform.get("scale") or {"x": 1.0, "y": 1.0}
    ngl_y = translate.get("y", transform.get("y", 0.0))
    return {
        "alpha": clip.get("alpha", 1.0),
        "flip": clip.get("flip") or {"horizontal": False, "vertical": False},
        "rotation": transform.get("rotation", 0.0),
        "scale": {"x": scale.get("x", 1.0), "y": scale.get("y", 1.0)},
        "transform": {
            "x": translate.get("x", transform.get("x", 0.0)),
            "y": ngl_translate_y_to_capcut(ngl_y),
        },
    }


def ngl_font_size_to_capcut(ngl_size: float, canvas_height: int) -> float:
    """将 NGL 像素字号转为 CapCut 内部字号。"""
    height = canvas_height if canvas_height > 0 else NGL_REF_CANVAS_HEIGHT
    capcut_size = (
        float(ngl_size)
        * CAPCUT_REF_FONT_SIZE
        * NGL_REF_CANVAS_HEIGHT
        / (NGL_REF_FONT_PX * height)
    )
    return round(max(0.1, capcut_size), 3)


def ngl_stroke_width_to_capcut(relative_width: float) -> float:
    """NGL 描边宽度为相对字号比例；CapCut content.strokes[].width 为小数。"""
    return round(max(0.0, relative_width) * 0.4, 4)


def capcut_style_from_ngl(
    style: dict[str, Any],
    text: str,
    ctx: ConversionContext,
    *,
    use_letter_color: bool = False,
) -> dict[str, Any]:
    char_start, char_end = style.get("range", [0, len(text)])
    char_len = len(text)
    start = max(0, min(int(char_start), char_len))
    end = max(0, min(int(char_end), char_len))
    if ctx.draft_target == "jianying":
        style_range = [start, end]
    else:
        style_range = [utf16_byte_offset(text, start), utf16_byte_offset(text, end)]

    ngl_size = float(style.get("size", 35.0))
    out: dict[str, Any] = {
        "range": style_range,
        "size": ngl_font_size_to_capcut(ngl_size, ctx.canvas_height),
        "bold": False,
        "italic": False,
    }
    if "letter_spacing" in style:
        out["letter_spacing"] = style["letter_spacing"]
    if "line_height" in style:
        out["line_height"] = style["line_height"]

    font = style.get("font") or {}
    font_path = font.get("path") or ""
    resolved_font = resolve_protocol_path(font_path, ctx) if font_path else None
    if resolved_font:
        dst = import_file(resolved_font, ctx, subdir="fonts")
        out["font"] = {"id": "", "path": str(dst)}
        ctx.path_map[font_path] = str(dst)
    elif font_path:
        out["font"] = {"id": "", "path": font_path}
    else:
        out["font"] = {"id": "", "path": ""}

    fill = style.get("fill") or {}
    fill_color = fill.get("color")
    if fill_color:
        out["fill"] = {
            "content": {
                "solid": {
                    "alpha": fill.get("alpha", 1.0),
                    "color": [float(c) for c in fill_color],
                },
            },
        }

    stroke = style.get("stroke")
    if stroke and stroke.get("color"):
        out["strokes"] = [{
            "width": ngl_stroke_width_to_capcut(stroke.get("width", 0.08)),
            "content": {
                "solid": {
                    "alpha": stroke.get("alpha", 1.0),
                    "color": [float(c) for c in stroke["color"]],
                },
            },
        }]

    if use_letter_color:
        out["useLetterColor"] = True

    return out


def convert_text_content(content_str: str, ctx: ConversionContext) -> tuple[str, dict[str, Any], bool]:
    data = json.loads(content_str)
    text = data.get("text", "")
    ngl_styles = data.get("styles", [])
    first_fill = (ngl_styles[0].get("fill") or {}).get("color") if ngl_styles else None

    styles = []
    for style in ngl_styles:
        fill_color = (style.get("fill") or {}).get("color")
        use_letter_color = fill_color is not None and first_fill is not None and fill_color != first_fill
        styles.append(capcut_style_from_ngl(style, text, ctx, use_letter_color=use_letter_color))

    capcut_content = {"text": text, "styles": styles, "layer_weight": 1, "effect": []}
    first = ngl_styles[0] if ngl_styles else {}
    fill = first.get("fill") or {}
    stroke = first.get("stroke") or {}
    fill_color = fill.get("color", [1.0, 1.0, 1.0])
    stroke_color = stroke.get("color", [0.0, 0.0, 0.0])
    meta = {
        "font_size": ngl_font_size_to_capcut(float(first.get("size", 35.0)), ctx.canvas_height),
        "text_color": rgb_to_hex(fill_color, fill.get("alpha", 1.0)),
        "border_color": rgb_to_hex(stroke_color, stroke.get("alpha", 1.0)),
        "border_width": ngl_stroke_width_to_capcut(stroke.get("width", 0.08)),
    }
    return json.dumps(capcut_content, ensure_ascii=False), meta, len(styles) > 1


def strip_pag_fields(text_mat: dict[str, Any]) -> None:
    text_mat.pop("renderer", None)
    text_mat.pop("pagConfig", None)
    text_mat.pop("pagFile", None)


def make_companions(ctx: ConversionContext) -> dict[str, str]:
    speed_id = new_uuid()
    canvas_id = new_uuid()
    placeholder_id = new_uuid()
    sound_id = new_uuid()
    color_id = new_uuid()
    vocal_id = new_uuid()

    ctx.speeds.append({
        "curve_speed": None,
        "id": speed_id,
        "mode": 0,
        "speed": 1.0,
        "type": "speed",
    })
    ctx.canvases.append({
        "album_image": "",
        "blur": 0.0,
        "color": "",
        "id": canvas_id,
        "image": "",
        "image_id": "",
        "image_name": "",
        "source_platform": 0,
        "team_id": "",
        "type": "canvas_color",
    })
    ctx.placeholder_infos.append({
        "error_path": "",
        "error_text": "",
        "id": placeholder_id,
        "meta_type": "none",
        "res_path": "",
        "res_text": "",
        "type": "placeholder_info",
    })
    ctx.sound_channel_mappings.append({
        "audio_channel_mapping": 0,
        "id": sound_id,
        "is_config_open": False,
        "type": "none",
    })
    ctx.material_colors.append({
        "gradient_angle": 90.0,
        "gradient_colors": [],
        "gradient_percents": [],
        "height": 0.0,
        "id": color_id,
        "is_color_clip": False,
        "is_gradient": False,
        "solid_color": "",
        "width": 0.0,
    })
    ctx.vocal_separations.append({
        "choice": 0,
        "enter_from": "",
        "final_algorithm": "",
        "id": vocal_id,
        "production_path": "",
        "removed_sounds": [],
        "time_range": None,
        "type": "vocal_separation",
    })
    return {
        "speed": speed_id,
        "canvas": canvas_id,
        "placeholder": placeholder_id,
        "sound": sound_id,
        "color": color_id,
        "vocal": vocal_id,
    }


def base_segment_fields(
    material_id: str,
    source_tr: dict[str, Any],
    target_tr: dict[str, Any],
    *,
    clip: dict[str, Any] | None,
    volume: float = 1.0,
    visible: bool = True,
    extra_refs: list[str] | None = None,
    render_index: int = 0,
    track_render_index: int = 0,
) -> dict[str, Any]:
    return {
        "id": new_uuid(),
        "material_id": material_id,
        "source_timerange": timerange_to_us(source_tr),
        "target_timerange": timerange_to_us(target_tr),
        "clip": clip,
        "visible": visible,
        "volume": volume,
        "speed": 1.0,
        "reverse": False,
        "cartoon": False,
        "caption_info": None,
        "common_keyframes": [],
        "desc": "",
        "enable_adjust": clip is not None,
        "enable_adjust_mask": False,
        "enable_color_adjust_pro": False,
        "enable_color_correct_adjust": False,
        "enable_color_curves": True,
        "enable_color_match_adjust": False,
        "enable_color_wheels": True,
        "enable_hsl": False,
        "enable_hsl_curves": True,
        "enable_lut": clip is not None,
        "enable_mask_shadow": False,
        "enable_mask_stroke": False,
        "enable_smart_color_adjust": False,
        "enable_video_mask": clip is not None,
        "extra_material_refs": extra_refs or [],
        "group_id": "",
        "hdr_settings": None,
        "intensifies_audio": False,
        "is_loop": False,
        "is_placeholder": False,
        "is_tone_modify": False,
        "keyframe_refs": [],
        "last_nonzero_volume": volume,
        "lyric_keyframes": None,
        "raw_segment_id": "",
        "render_index": render_index,
        "render_timerange": {"duration": 0, "start": 0},
        "responsive_layout": {
            "enable": False,
            "horizontal_pos_layout": 0,
            "size_layout": 0,
            "target_follow": "",
            "vertical_pos_layout": 0,
        },
        "source": "segmentsourcenormal",
        "state": 0,
        "template_id": "",
        "template_scene": "default",
        "track_attribute": 0,
        "track_render_index": track_render_index,
        "uniform_scale": {"on": True, "value": 1.0} if clip is not None else None,
    }


def add_meta_video(ctx: ConversionContext, mat_id: str, path: Path, item: dict[str, Any], metetype: str) -> None:
    ctx.meta_videos.append({
        "ai_group_type": "",
        "create_time": int(now_us() / 1_000_000),
        "duration": ms_to_us(item.get("duration", 0)),
        "enter_from": 0,
        "extra_info": path.name,
        "file_Path": str(path),
        "height": item.get("height", 0),
        "id": mat_id,
        "import_time": int(now_us() / 1_000_000),
        "import_time_ms": now_us(),
        "item_source": 1,
        "md5": "",
        "metetype": metetype,
        "roughcut_time_range": {"duration": ms_to_us(item.get("duration", 0)), "start": 0},
        "sub_time_range": {"duration": -1, "start": -1},
        "type": 0,
        "width": item.get("width", 0),
    })


def add_meta_audio(ctx: ConversionContext, mat_id: str, path: Path, duration_ms: int) -> None:
    ctx.meta_audios.append({
        "create_time": int(now_us() / 1_000_000),
        "duration": ms_to_us(duration_ms),
        "extra_info": path.name,
        "file_Path": str(path),
        "id": mat_id,
        "import_time": int(now_us() / 1_000_000),
        "import_time_ms": now_us(),
        "item_source": 1,
        "md5": "",
        "metetype": "music",
        "type": 1,
    })


def convert_video_material(item: dict[str, Any], ctx: ConversionContext) -> dict[str, Any] | None:
    src = resolve_protocol_path(item.get("path", ""), ctx)
    if not src:
        ctx.warnings.append(f"找不到视频素材: {item.get('path')}")
        return None
    dst = import_file(src, ctx)
    mat_id = map_id(item["id"], ctx)
    ctx.path_map[item.get("path", "")] = str(dst)
    add_meta_video(ctx, mat_id, dst, item, "video")
    return {
        "id": mat_id,
        "type": "video",
        "path": str(dst),
        "duration": ms_to_us(item.get("duration", 0)),
        "width": item.get("width", 0),
        "height": item.get("height", 0),
        "material_name": item.get("name") or src.name,
        "category_name": "local",
        "check_flag": 62978047,
        "has_audio": True,
        "source": 0,
        "source_platform": 0,
        "local_material_id": new_uuid().lower(),
    }


def convert_image_material(item: dict[str, Any], ctx: ConversionContext) -> dict[str, Any] | None:
    src = resolve_protocol_path(item.get("path", ""), ctx)
    if not src:
        ctx.warnings.append(f"找不到图片素材: {item.get('path')}")
        return None
    dst = import_file(src, ctx)
    mat_id = map_id(item["id"], ctx)
    ctx.path_map[item.get("path", "")] = str(dst)
    is_gif = (item.get("type") == "gif") or src.suffix.lower() == ".gif"
    metetype = "video" if is_gif else "photo"
    capcut_type = "video" if is_gif else "photo"
    add_meta_video(ctx, mat_id, dst, item, metetype)
    return {
        "id": mat_id,
        "type": capcut_type,
        "path": str(dst),
        "duration": ms_to_us(item.get("duration", 0)),
        "width": item.get("width", 0),
        "height": item.get("height", 0),
        "material_name": item.get("name") or src.name,
        "category_name": "local",
        "check_flag": 62978047,
        "has_audio": False,
        "source": 0,
        "source_platform": 0,
        "local_material_id": new_uuid().lower(),
    }


def convert_audio_material(item: dict[str, Any], ctx: ConversionContext, duration_ms: int) -> dict[str, Any] | None:
    src = resolve_protocol_path(item.get("path", ""), ctx)
    if not src:
        ctx.warnings.append(f"找不到音频素材: {item.get('path')}")
        return None
    dst = import_file(src, ctx)
    mat_id = map_id(item["id"], ctx)
    ctx.path_map[item.get("path", "")] = str(dst)
    add_meta_audio(ctx, mat_id, dst, duration_ms)
    return {
        "id": mat_id,
        "type": "extract_music",
        "path": str(dst),
        "duration": ms_to_us(duration_ms),
        "name": item.get("name") or src.name,
        "category_name": "local",
        "check_flag": 1,
        "source": 0,
        "source_platform": 0,
        "local_material_id": new_uuid().lower(),
    }


def convert_text_material(item: dict[str, Any], ctx: ConversionContext) -> dict[str, Any] | None:
    content_str = item.get("content", "")
    if not content_str:
        ctx.warnings.append(f"跳过空文字素材: {item.get('id')}")
        return None

    capcut_content, style_meta, has_rich_styles = convert_text_content(content_str, ctx)
    mat_id = map_id(item["id"], ctx)

    mat: dict[str, Any] = {
        "id": mat_id,
        "type": "text",
        "content": capcut_content,
        "alignment": item.get("alignment", 1),
        "font_name": "",
        "font_size": style_meta["font_size"],
        "font_path": "",
        "text_color": style_meta["text_color"],
        "border_color": style_meta["border_color"],
        "border_width": style_meta["border_width"],
        "global_alpha": 1.0,
        "check_flag": 7,
        "has_shadow": False,
        "shadow_color": "#000000FF",
        "shadow_distance": 8.0,
        "background_color": "#00000000",
        "background_alpha": 0.0,
        "combo_info": {"text_templates": []},
        "typesetting": 0,
        "line_feed": 1,
        "line_max_width": 0.82,
        "letter_spacing": 0.0,
        "line_spacing": 0.2,
        "border_mode": 0,
        "border_alpha": 1.0,
        "text_alpha": 1.0,
    }
    if has_rich_styles and ctx.draft_target == "jianying":
        mat["is_rich_text"] = True
        mat["use_effect_default_color"] = False
    else:
        mat["is_rich_text"] = False
        mat["use_effect_default_color"] = True
    return mat


def load_template_draft_info(template_path: Path) -> dict[str, Any]:
    with template_path.open("r", encoding="utf-8") as f:
        template = json.load(f)
    template["tracks"] = []
    for key in list(template.get("materials", {}).keys()):
        template["materials"][key] = []
    return template


def resolve_draft_info_template() -> Path:
    template_path = JYCONVERT_ROOT / "templates" / "draft_info.template.json"
    if template_path.exists():
        return template_path
    raise FileNotFoundError(
        f"缺少内置 draft_info 模板: {template_path}\n"
        "请确认 templates/draft_info.template.json 已随 jyconvert 一起打包。"
    )


def convert_protocol_to_draft_info(protocol: dict[str, Any], ctx: ConversionContext) -> dict[str, Any]:
    draft = load_template_draft_info(resolve_draft_info_template())

    canvas = protocol.get("canvas_config") or {}
    width = int(canvas.get("width") or protocol.get("width") or 720)
    height = int(canvas.get("height") or protocol.get("height") or 1280)
    ctx.canvas_width = width
    ctx.canvas_height = height

    ctx.draft_id = new_uuid()
    draft["id"] = ctx.draft_id
    draft["name"] = ctx.draft_dir.name
    draft["path"] = str(ctx.draft_dir)
    draft["duration"] = ms_to_us(protocol.get("duration", 0))
    draft["fps"] = float(protocol.get("fps", 30.0))
    draft["canvas_config"] = {
        "background": None,
        "height": height,
        "width": width,
        "ratio": ratio_from_canvas(width, height),
    }

    materials = protocol.get("materials", {})
    material_lookup: dict[str, dict[str, Any]] = {}

    audio_durations: dict[str, int] = {}
    for track in protocol.get("tracks", []):
        if track.get("type") != "audio":
            continue
        for seg in track.get("segments", []):
            mid = seg.get("material_id")
            if not mid:
                continue
            dur = seg.get("source_timerange", {}).get("duration", 0)
            audio_durations[mid] = max(audio_durations.get(mid, 0), dur)

    for item in materials.get("videos", []):
        mat = convert_video_material(item, ctx)
        if mat:
            ctx.videos.append(mat)
            material_lookup[item["id"]] = mat

    for item in materials.get("images", []):
        mat = convert_image_material(item, ctx)
        if mat:
            ctx.videos.append(mat)
            material_lookup[item["id"]] = mat

    for item in materials.get("audios", []):
        mat = convert_audio_material(item, ctx, audio_durations.get(item["id"], 0))
        if mat:
            ctx.audios.append(mat)
            material_lookup[item["id"]] = mat

    for item in materials.get("texts", []):
        cleaned = copy.deepcopy(item)
        if item.get("renderer") == "pag":
            try:
                preview = json.loads(item.get("content", "{}")).get("text", "")[:24]
            except json.JSONDecodeError:
                preview = item.get("id", "")
            ctx.warnings.append(f"PAG 文字已降级为静态文字: {item.get('id')} ({preview})")
        strip_pag_fields(cleaned)
        mat = convert_text_material(cleaned, ctx)
        if mat:
            ctx.texts.append(mat)
            material_lookup[item["id"]] = mat

    track_render_index = 0
    for track in protocol.get("tracks", []):
        track_type = track.get("type")
        capcut_type = track_type
        if track_type == "image":
            capcut_type = "video"

        segments: list[dict[str, Any]] = []
        for index, seg in enumerate(track.get("segments", [])):
            mid = seg.get("material_id")
            mat = material_lookup.get(mid)
            if not mat:
                ctx.warnings.append(f"跳过片段，找不到素材 {mid}")
                continue

            source_tr = seg.get("source_timerange") or seg.get("target_timerange") or {"start": 0, "duration": 0}
            target_tr = seg.get("target_timerange") or source_tr
            volume = normalize_volume(seg.get("volume"))
            visible = seg.get("visible", True)
            clip = convert_clip(seg.get("clip"))

            if capcut_type == "audio":
                segment = base_segment_fields(
                    mat["id"],
                    source_tr,
                    target_tr,
                    clip=None,
                    volume=volume,
                    visible=visible,
                    track_render_index=track_render_index,
                    render_index=index,
                )
            elif capcut_type == "text":
                if source_tr.get("duration", 0) == 0:
                    source_tr = target_tr
                segment = base_segment_fields(
                    mat["id"],
                    source_tr,
                    target_tr,
                    clip=clip,
                    volume=1.0,
                    visible=visible,
                    track_render_index=track_render_index,
                    render_index=index,
                )
            else:
                companions = make_companions(ctx)
                extra_refs = [
                    companions["speed"],
                    companions["placeholder"],
                    companions["canvas"],
                    companions["sound"],
                    companions["color"],
                    companions["vocal"],
                ]
                if source_tr.get("duration", 0) == 0:
                    source_tr = {"start": 0, "duration": target_tr.get("duration", 0)}
                segment = base_segment_fields(
                    mat["id"],
                    source_tr,
                    target_tr,
                    clip=clip or convert_clip({}),
                    volume=volume,
                    visible=visible,
                    extra_refs=extra_refs,
                    track_render_index=track_render_index,
                    render_index=index,
                )
                if capcut_type == "video" and clip is None:
                    segment["clip"]["alpha"] = 1.0

            segments.append(segment)

        if not segments:
            continue

        ctx.tracks.append({
            "attribute": 0,
            "flag": 0,
            "id": new_uuid(),
            "is_default_name": True,
            "name": track.get("id", ""),
            "segments": segments,
            "type": capcut_type,
        })
        track_render_index += 1

    draft["tracks"] = ctx.tracks
    draft["materials"]["videos"] = ctx.videos
    draft["materials"]["audios"] = ctx.audios
    draft["materials"]["texts"] = ctx.texts
    draft["materials"]["speeds"] = ctx.speeds
    draft["materials"]["canvases"] = ctx.canvases
    draft["materials"]["placeholder_infos"] = ctx.placeholder_infos
    draft["materials"]["sound_channel_mappings"] = ctx.sound_channel_mappings
    draft["materials"]["material_colors"] = ctx.material_colors
    draft["materials"]["vocal_separations"] = ctx.vocal_separations
    if ctx.draft_target == "jianying":
        apply_jianying_platform(draft)
    return draft


def apply_jianying_platform(draft: dict[str, Any]) -> None:
    """剪映草稿需标记 app_source=lv，否则富文本等字段可能不生效。"""
    platform = copy.deepcopy(draft.get("platform") or {})
    platform.update({
        "app_id": 3704,
        "app_source": "lv",
        "os": platform.get("os") or "mac",
    })
    draft["platform"] = platform
    draft["last_modified_platform"] = copy.deepcopy(platform)


def build_draft_meta_info(draft_info: dict[str, Any], ctx: ConversionContext, draft_id: str, drafts_root: Path) -> dict[str, Any]:
    total_size = 0
    for path in ctx.copied_files:
        try:
            total_size += path.stat().st_size
        except OSError:
            pass

    return {
        "cloud_draft_cover": False,
        "cloud_draft_sync": False,
        "cloud_package_completed_time": "",
        "draft_cloud_capcut_purchase_info": "",
        "draft_cloud_last_action_download": False,
        "draft_cloud_package_type": "",
        "draft_cloud_purchase_info": "",
        "draft_cloud_template_id": "",
        "draft_cloud_tutorial_info": "",
        "draft_cloud_videocut_purchase_info": "",
        "draft_cover": str(ctx.draft_dir / "draft_cover.jpg"),
        "draft_deeplink_url": "",
        "draft_enterprise_info": {
            "draft_enterprise_extra": "",
            "draft_enterprise_id": "",
            "draft_enterprise_name": "",
            "enterprise_material": [],
        },
        "draft_fold_path": str(ctx.draft_dir),
        "draft_id": draft_id,
        "draft_is_ae_produce": False,
        "draft_is_ai_packaging_used": False,
        "draft_is_ai_shorts": False,
        "draft_is_ai_translate": False,
        "draft_is_article_video_draft": False,
        "draft_is_cloud_temp_draft": False,
        "draft_is_from_deeplink": "false",
        "draft_is_invisible": False,
        "draft_is_pippit_draft": False,
        "draft_is_web_article_video": False,
        "draft_materials": [
            {"type": 0, "value": ctx.meta_videos},
            {"type": 1, "value": ctx.meta_audios},
            {"type": 2, "value": []},
            {"type": 3, "value": []},
            {"type": 6, "value": []},
            {"type": 7, "value": []},
            {"type": 8, "value": []},
        ],
        "draft_materials_copied_info": [],
        "draft_name": ctx.draft_dir.name,
        "draft_need_rename_folder": False,
        "draft_new_version": "",
        "draft_removable_storage_device": "",
        "draft_root_path": str(drafts_root),
        "draft_segment_extra_info": [],
        "draft_timeline_materials_size_": total_size,
        "draft_type": "",
        "draft_web_article_video_enter_from": "",
        "tm_draft_create": now_us(),
        "tm_draft_modified": now_us(),
        "tm_draft_removed": 0,
        "tm_duration": draft_info.get("duration", 0),
    }


def find_timeline_cover_source(protocol: dict[str, Any], ctx: ConversionContext) -> tuple[Path, float] | None:
    """取第一条视频轨上最早片段的源素材第一帧做封面。"""
    for track in protocol.get("tracks", []):
        if track.get("type") != "video":
            continue
        segments = [s for s in track.get("segments", []) if s.get("visible", True)]
        if not segments:
            continue
        best_seg = min(
            segments,
            key=lambda s: s.get("target_timerange", {}).get("start", 0),
        )

        capcut_mat_id = ctx.id_map.get(best_seg.get("material_id", ""))
        if not capcut_mat_id:
            return None

        for item in ctx.videos:
            if item.get("id") != capcut_mat_id:
                continue
            path = item.get("path")
            if not path:
                return None
            video_path = Path(path)
            if not video_path.exists():
                return None
            if item.get("type") != "video":
                return None
            return video_path, 0.0
        return None

    return None


def iter_ffmpeg_candidates() -> list[str]:
    """按优先级列出 ffmpeg 路径，仅返回实测可执行的版本。"""
    seen: set[str] = set()
    ordered: list[str] = []

    def add(raw: str | None) -> None:
        if not raw:
            return
        path = str(Path(raw).resolve())
        if path in seen or not Path(path).is_file():
            return
        seen.add(path)
        ordered.append(path)

    add(os.environ.get("JYCONVERT_FFMPEG", "").strip())

    project_root = JYCONVERT_ROOT.parent
    for name in ("ffmpeg", "ffmpeg.exe"):
        add(str(project_root / "bin" / name))

    add(which("ffmpeg"))
    add("/opt/homebrew/bin/ffmpeg")
    add("/usr/local/bin/ffmpeg")

    working: list[str] = []
    for candidate in ordered:
        try:
            subprocess.run(
                [candidate, "-version"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=8,
            )
            working.append(candidate)
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            continue
    return working


def resolve_ffmpeg() -> str | None:
    """返回首个可用的 ffmpeg。"""
    candidates = iter_ffmpeg_candidates()
    return candidates[0] if candidates else None


def _run_ffmpeg_cover(ffmpeg: str, source: Path, output: Path, time_sec: float) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    time_label = f"{max(0.0, time_sec):.3f}"
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        time_label,
        "-i",
        str(source),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        "-f",
        "image2",
        str(output),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def _write_image_cover(source: Path, output: Path) -> None:
    """将任意图片转为 JPEG 封面。"""
    if source.suffix.lower() in {".jpg", ".jpeg"}:
        try:
            with open(source, "rb") as fh:
                if fh.read(3) == b"\xff\xd8\xff":
                    shutil.copy2(source, output)
                    return
        except OSError:
            pass

    last_exc: Exception | None = None
    for ffmpeg in iter_ffmpeg_candidates():
        try:
            _run_ffmpeg_cover(ffmpeg, source, output, 0.0)
            return
        except (OSError, subprocess.CalledProcessError) as exc:
            last_exc = exc
    if last_exc:
        raise last_exc
    raise FileNotFoundError("ffmpeg")


def find_fallback_cover(ctx: ConversionContext) -> Path | None:
    """ffmpeg 截帧失败时，尝试用已导入图片或内置占位图。"""
    for pattern in ("*.jpg", "*.jpeg", "*.png", "*.gif"):
        for img in sorted(ctx.imported_dir.glob(pattern)):
            return img
    placeholder = JYCONVERT_ROOT / "templates" / "draft_cover.placeholder.jpg"
    if placeholder.is_file():
        return placeholder
    return None


def generate_draft_cover(source: Path, output: Path, time_sec: float = 0.0) -> None:
    """用 ffmpeg 从视频源素材截取一帧写入 draft_cover.jpg。"""
    last_exc: Exception | None = None
    for ffmpeg in iter_ffmpeg_candidates():
        try:
            _run_ffmpeg_cover(ffmpeg, source, output, time_sec)
            return
        except (OSError, subprocess.CalledProcessError) as exc:
            last_exc = exc
    if last_exc:
        raise last_exc
    raise FileNotFoundError("ffmpeg")


def write_draft_cover(protocol: dict[str, Any], ctx: ConversionContext) -> bool:
    cover_path = ctx.draft_dir / "draft_cover.jpg"
    source = find_timeline_cover_source(protocol, ctx)
    if not source:
        fallback = find_fallback_cover(ctx)
        if fallback:
            try:
                _write_image_cover(fallback, cover_path)
                return True
            except OSError as exc:
                ctx.warnings.append(f"生成备用封面失败: {fallback.name} ({exc})")
        ctx.warnings.append("未找到视频素材，无法生成草稿封面")
        return False

    video_path, time_sec = source
    try:
        generate_draft_cover(video_path, cover_path, time_sec)
        return True
    except (OSError, subprocess.CalledProcessError) as exc:
        fallback = find_fallback_cover(ctx)
        if fallback:
            try:
                _write_image_cover(fallback, cover_path)
                ctx.warnings.append(
                    f"ffmpeg 生成封面失败，已使用备用封面: {video_path.name} ({exc})",
                )
                return True
            except OSError as img_exc:
                ctx.warnings.append(
                    f"生成草稿封面失败: {video_path.name} ({exc}); 备用封面也失败 ({img_exc})",
                )
                return False
        ctx.warnings.append(f"生成草稿封面失败: {video_path.name} ({exc})")
        return False
