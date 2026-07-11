#!/usr/bin/env python3
"""
两阶段素材处理：重编码视频 → 关键帧对齐流复制裁剪。

阶段 1：将所有视频素材重编码为 MP4、720×1280、25fps、固定 GOP（便于关键帧对齐），适度降低码率。
阶段 2：从母版精确裁剪各片段（source.start=0，避免 NGLEngine 衔接处 seek 黑屏）。

裁剪后协议更新：
  - 素材 path 指向裁剪文件
  - 素材 duration = 片段时长
  - 片段 source_timerange = { start: 0, duration: 原 duration }
  - 视频轨 target_timerange 首尾相接（消除 CapCut 转换带来的 1ms 缝隙/重叠）

用法:
  python3 python/protocol/prepare_assets.py \\
    --protocol examples/converted_from_capcut_0709/converted_protocol.json \\
    --output-dir examples/converted_from_capcut_0709_prepared

  python3 python/protocol/prepare_assets.py --protocol ... --dry-run
  python3 python/protocol/prepare_assets.py --protocol ... --skip-reencode  # 仅阶段 2
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from protocol.media_probe import (
    pick_ffmpeg,
)
from protocol.trim_assets import (
    TrimJob,
    build_material_lookup,
    collect_trim_jobs,
    copy_whole_file,
    resolve_protocol_path,
    run_ffmpeg,
    should_copy_whole_file,
    trim_media,
)

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


@dataclass
class KeyframeTrimResult:
    material_id: str
    rel_path: str
    trim_start_ms: int
    trim_end_ms: int
    protocol_start_ms: int
    protocol_duration_ms: int


def safe_stem(path: Path) -> str:
    return re.sub(r"[^\w.\-]+", "_", path.stem)[:80]


def master_name(src: Path, *, width: int, height: int) -> str:
    key = f"{src.resolve()}:{width}x{height}"
    digest = hashlib.md5(key.encode()).hexdigest()[:8]
    return f"{safe_stem(src)}_{digest}.mp4"


def scale_filter(width: int, height: int) -> str:
    """等比放大后居中裁剪到目标分辨率（适配竖屏 9:16）。"""
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1"
    )


def reencode_video(
    ffmpeg: str,
    src: Path,
    dst: Path,
    *,
    width: int,
    height: int,
    fps: int,
    crf: int,
    gop: int,
    audio_bitrate: str,
    dry_run: bool,
) -> None:
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-map", "0:v:0?",
        "-map", "0:a:0?",
        "-vf", scale_filter(width, height),
        "-r", str(fps),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", str(crf),
        "-g", str(gop),
        "-keyint_min", str(gop),
        "-sc_threshold", "0",
        "-bf", "0",
        "-fps_mode", "cfr",
        "-c:a", "aac",
        "-b:a", audio_bitrate,
        "-movflags", "+faststart",
        str(dst),
    ]
    run_ffmpeg(cmd, dry_run=dry_run)


def accurate_trim_from_master(
    ffmpeg: str,
    src: Path,
    dst: Path,
    start_ms: int,
    duration_ms: int,
    *,
    crf: int,
    dry_run: bool,
) -> None:
    """从 720p 母版精确裁剪，输出 source.start=0 的片段文件。"""
    start_sec = start_ms / 1000.0
    duration_sec = max(0.001, duration_ms / 1000.0)
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{start_sec:.3f}",
        "-i", str(src),
        "-t", f"{duration_sec:.3f}",
        "-map", "0:v:0",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", str(crf),
        "-bf", "0",
        "-fps_mode", "cfr",
        "-an",
        "-movflags", "+faststart",
        str(dst),
    ]
    run_ffmpeg(cmd, dry_run=dry_run)


def align_video_target_timeranges(protocol: dict[str, Any]) -> dict[str, Any]:
    """让视频轨 target 首尾相接，修复 1ms 缝隙/重叠导致的衔接黑屏。"""
    updated = json.loads(json.dumps(protocol))
    for track in updated.get("tracks", []):
        if track.get("type") != "video":
            continue
        segments = sorted(
            track.get("segments", []),
            key=lambda s: (s.get("target_timerange") or {}).get("start", 0),
        )
        for index in range(1, len(segments)):
            prev_tr = segments[index - 1].setdefault("target_timerange", {})
            cur_tr = segments[index].setdefault("target_timerange", {})
            cur_tr["start"] = int(prev_tr.get("start", 0)) + int(prev_tr.get("duration", 0))
        track["segments"] = segments
    return updated


def collect_unique_video_sources(
    protocol: dict[str, Any],
    resource_root: Path,
) -> dict[str, Path]:
    """rel_path -> absolute source path（去重）。"""
    unique: dict[str, Path] = {}
    for item in protocol.get("materials", {}).get("videos", []):
        rel = item.get("path", "")
        src = resolve_protocol_path(rel, resource_root)
        if not src:
            continue
        if src.suffix.lower() not in VIDEO_EXTS and src.suffix.lower() not in {".mp4", ".mov"}:
            continue
        unique[rel] = src
    return unique


def phase1_reencode_masters(
    protocol: dict[str, Any],
    resource_root: Path,
    masters_dir: Path,
    *,
    width: int,
    height: int,
    fps: int,
    crf: int,
    gop: int,
    audio_bitrate: str,
    dry_run: bool,
) -> tuple[dict[str, str], dict[str, Path]]:
    """
    返回 (old_rel -> new_master_rel, old_rel -> master_abs_path)。
    """
    ffmpeg = pick_ffmpeg()
    sources = collect_unique_video_sources(protocol, resource_root)
    rel_to_master_rel: dict[str, str] = {}
    rel_to_master_abs: dict[str, Path] = {}

    print(f"阶段 1：重编码 {len(sources)} 个视频源 → {width}x{height} / {fps}fps MP4\n")
    for index, (old_rel, src) in enumerate(sorted(sources.items()), 1):
        out_name = master_name(src, width=width, height=height)
        master_rel = f"./assets/_masters/{out_name}"
        master_abs = masters_dir / out_name
        rel_to_master_rel[old_rel] = master_rel
        rel_to_master_abs[old_rel] = master_abs

        if not dry_run and master_abs.exists():
            print(f"[{index}/{len(sources)}] 跳过（已存在） {out_name}")
            continue

        print(f"[{index}/{len(sources)}] {src.name} → {out_name}")
        if not dry_run:
            masters_dir.mkdir(parents=True, exist_ok=True)
        reencode_video(
            ffmpeg, src, master_abs,
            width=width, height=height,
            fps=fps, crf=crf, gop=gop, audio_bitrate=audio_bitrate,
            dry_run=dry_run,
        )

    return rel_to_master_rel, rel_to_master_abs


def apply_master_paths(protocol: dict[str, Any], rel_to_master: dict[str, str]) -> dict[str, Any]:
    updated = json.loads(json.dumps(protocol))
    for item in updated.get("materials", {}).get("videos", []):
        old = item.get("path", "")
        if old in rel_to_master:
            item["path"] = rel_to_master[old]
            item["name"] = Path(rel_to_master[old]).name
    return updated


def apply_keyframe_trim_to_protocol(
    protocol: dict[str, Any],
    results: list[KeyframeTrimResult],
    *,
    width: int | None = None,
    height: int | None = None,
) -> dict[str, Any]:
    updated = json.loads(json.dumps(protocol))
    by_material = {r.material_id: r for r in results}

    lookup = build_material_lookup(updated)
    for mid, result in by_material.items():
        if mid not in lookup:
            continue
        category, mat = lookup[mid]
        mat["path"] = result.rel_path
        if category == "videos":
            mat["duration"] = result.protocol_duration_ms
            if width and height:
                mat["width"] = width
                mat["height"] = height

    for track in updated.get("tracks", []):
        if track.get("type") not in {"video", "audio", "image"}:
            continue
        for seg in track.get("segments", []):
            mid = seg.get("material_id", "")
            result = by_material.get(mid)
            if not result:
                continue
            offset = 0
            seg["source_timerange"] = {
                "start": offset,
                "duration": result.protocol_duration_ms,
            }

    referenced: set[str] = set()
    for track in updated.get("tracks", []):
        for seg in track.get("segments", []):
            mid = seg.get("material_id")
            if mid:
                referenced.add(mid)

    for category in ("videos", "audios", "images"):
        items = updated.get("materials", {}).get(category, [])
        updated["materials"][category] = [item for item in items if item.get("id") in referenced]

    return updated


def phase2_trim_videos(
    protocol: dict[str, Any],
    resource_root: Path,
    assets_dir: Path,
    *,
    crf: int,
    dry_run: bool,
) -> list[KeyframeTrimResult]:
    ffmpeg = pick_ffmpeg()
    lookup = build_material_lookup(protocol)
    jobs = [
        j for j in collect_trim_jobs(protocol, resource_root, must_exist=not dry_run)
        if j.track_type == "video"
    ]
    results: list[KeyframeTrimResult] = []

    print(f"\n阶段 2：精确裁剪 {len(jobs)} 个视频片段（720p 母版 → source.start=0）\n")
    for index, job in enumerate(jobs, 1):
        if job.material_id not in lookup:
            continue
        _, mat = lookup[job.material_id]
        master = resolve_protocol_path(
            mat.get("path", ""), resource_root, must_exist=not dry_run,
        )
        if not master or (not dry_run and not master.exists()):
            raise FileNotFoundError(f"找不到重编码母版: {job.material_id} ({mat.get('path')})")

        end_ms = job.start_ms + job.duration_ms
        out_name = f"{safe_stem(master)}_{job.start_ms}-{job.duration_ms}.mp4"
        rel = f"./assets/{out_name}"
        dst = assets_dir / out_name

        print(
            f"[{index}/{len(jobs)}] {job.material_id}  "
            f"协议 {job.start_ms}-{end_ms}ms"
        )
        if not dry_run:
            assets_dir.mkdir(parents=True, exist_ok=True)
            accurate_trim_from_master(
                ffmpeg, master, dst, job.start_ms, job.duration_ms,
                crf=crf, dry_run=dry_run,
            )

        results.append(KeyframeTrimResult(
            material_id=job.material_id,
            rel_path=rel,
            trim_start_ms=job.start_ms,
            trim_end_ms=end_ms,
            protocol_start_ms=job.start_ms,
            protocol_duration_ms=job.duration_ms,
        ))

    return results


def phase2_trim_audio_and_copy_rest(
    protocol: dict[str, Any],
    resource_root: Path,
    assets_dir: Path,
    *,
    skip_material_ids: set[str],
    dry_run: bool,
) -> tuple[dict[str, str], dict[str, int]]:
    ffmpeg = pick_ffmpeg()
    material_out_paths: dict[str, str] = {}
    material_durations: dict[str, int] = {}

    jobs = collect_trim_jobs(protocol, resource_root)
    audio_jobs = [j for j in jobs if j.track_type == "audio" and j.material_id not in skip_material_ids]

    if audio_jobs:
        print(f"\n音频裁剪 {len(audio_jobs)} 个\n")
    for index, job in enumerate(audio_jobs, 1):
        rel = f"./assets/{job.out_name}"
        dst = assets_dir / job.out_name
        print(f"[audio {index}] {job.material_id}  {job.start_ms}ms +{job.duration_ms}ms")
        if not dry_run:
            assets_dir.mkdir(parents=True, exist_ok=True)
            if should_copy_whole_file(job, ffmpeg):
                copy_whole_file(job.src_path, dst, dry_run=dry_run)
            else:
                trim_media(ffmpeg, job, dst, mode="accurate", dry_run=dry_run)
        material_out_paths[job.material_id] = rel
        material_durations[job.material_id] = job.duration_ms

    lookup = build_material_lookup(protocol)
    referenced_images: set[str] = set()
    for track in protocol.get("tracks", []):
        if track.get("type") == "image":
            for seg in track.get("segments", []):
                referenced_images.add(seg.get("material_id", ""))

    for mid in referenced_images:
        if mid in material_out_paths or mid not in lookup:
            continue
        _, mat = lookup[mid]
        src = resolve_protocol_path(mat.get("path", ""), resource_root)
        if not src or not src.exists():
            continue
        rel = f"./assets/{src.name}"
        dst = assets_dir / src.name
        print(f"[copy image] {src.name}")
        if not dry_run:
            shutil.copy2(src, dst)
        material_out_paths[mid] = rel

    return material_out_paths, material_durations


def prepare_protocol_assets(
    protocol_path: Path,
    output_dir: Path | None,
    *,
    width: int = 720,
    height: int = 1280,
    fps: int = 25,
    crf: int = 26,
    gop: int = 25,
    audio_bitrate: str = "128k",
    skip_reencode: bool = False,
    drop_masters: bool = False,
    dry_run: bool = False,
) -> Path:
    protocol_path = protocol_path.resolve()
    resource_root = protocol_path.parent
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))

    if output_dir is None:
        output_dir = resource_root.parent / f"{resource_root.name}_prepared"
    output_dir = output_dir.resolve()
    assets_dir = output_dir / "assets"
    masters_dir = assets_dir / "_masters"
    fonts_src = resource_root / "fonts"

    if not dry_run:
        if output_dir.exists():
            shutil.rmtree(output_dir)
        assets_dir.mkdir(parents=True, exist_ok=True)
        if fonts_src.is_dir():
            shutil.copytree(fonts_src, output_dir / "fonts")

    working = protocol
    phase2_root = output_dir if not dry_run else resource_root

    if skip_reencode:
        print("跳过阶段 1（使用协议内现有视频路径作为母版）\n")
        phase2_root = resource_root
    else:
        rel_to_master, _ = phase1_reencode_masters(
            protocol, resource_root, masters_dir,
            width=width, height=height,
            fps=fps, crf=crf, gop=gop, audio_bitrate=audio_bitrate,
            dry_run=dry_run,
        )
        working = apply_master_paths(protocol, rel_to_master)

    video_results = phase2_trim_videos(
        working, phase2_root, assets_dir, crf=crf, dry_run=dry_run,
    )
    video_ids = {r.material_id for r in video_results}

    audio_paths, audio_durations = phase2_trim_audio_and_copy_rest(
        protocol, resource_root, assets_dir,
        skip_material_ids=video_ids,
        dry_run=dry_run,
    )

    expected_audio = sum(
        1 for track in protocol.get("tracks", [])
        if track.get("type") == "audio"
    )
    if expected_audio and not audio_paths and not dry_run:
        print(
            f"\n⚠ 警告：协议有 {expected_audio} 条音频轨，但未处理任何音频。"
            f"请确认协议内素材路径相对 {resource_root} 可访问（如 ./assets/、./abc/）。\n",
            file=sys.stderr,
        )

    updated = apply_keyframe_trim_to_protocol(
        working, video_results, width=width, height=height,
    )
    updated = align_video_target_timeranges(updated)

    if audio_paths:
        lookup = build_material_lookup(updated)
        for mid, rel in audio_paths.items():
            if mid not in lookup:
                continue
            _, mat = lookup[mid]
            mat["path"] = rel
        for track in updated.get("tracks", []):
            if track.get("type") != "audio":
                continue
            for seg in track.get("segments", []):
                mid = seg.get("material_id", "")
                if mid in audio_durations:
                    seg["source_timerange"] = {
                        "start": 0,
                        "duration": audio_durations[mid],
                    }

    out_protocol = output_dir / "converted_protocol.json"
    if not dry_run:
        out_protocol.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
        if drop_masters and masters_dir.is_dir():
            shutil.rmtree(masters_dir)
    return out_protocol


def main() -> None:
    parser = argparse.ArgumentParser(description="重编码 + 关键帧对齐裁剪")
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--width", type=int, default=720, help="重编码输出宽度")
    parser.add_argument("--height", type=int, default=1280, help="重编码输出高度")
    parser.add_argument("--fps", type=int, default=25)
    parser.add_argument("--crf", type=int, default=26, help="x264 CRF，720p 默认 26（18~28）")
    parser.add_argument("--gop", type=int, default=25, help="关键帧间隔（帧数），25=每秒一个关键帧")
    parser.add_argument("--audio-bitrate", default="128k")
    parser.add_argument("--skip-reencode", action="store_true", help="跳过阶段 1")
    parser.add_argument("--drop-masters", action="store_true", help="阶段 2 完成后删除 _masters")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.protocol.exists():
        raise FileNotFoundError(f"协议不存在: {args.protocol}")

    out = prepare_protocol_assets(
        args.protocol,
        args.output_dir,
        width=args.width,
        height=args.height,
        fps=args.fps,
        crf=args.crf,
        gop=args.gop,
        audio_bitrate=args.audio_bitrate,
        skip_reencode=args.skip_reencode,
        drop_masters=args.drop_masters,
        dry_run=args.dry_run,
    )
    if not args.dry_run:
        print(f"\n✓ 完成: {out}")


if __name__ == "__main__":
    main()
