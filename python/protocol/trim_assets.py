#!/usr/bin/env python3
"""
按协议 source_timerange 用 ffmpeg 裁剪素材，并生成更新后的协议 JSON。

协议里每个片段的 source_timerange { start, duration }（毫秒）表示
从源文件截取 [start, start+duration) 区间。裁剪后：
  - 素材 path 指向新文件
  - source_timerange 重置为 { start: 0, duration: 原 duration }
  - 视频素材 duration 更新为片段时长

用法:
  python3 python/protocol/trim_assets.py \\
    --protocol examples/converted_from_capcut_0709/converted_protocol.json

  # 快速模式（流复制，可能卡在关键帧，不够帧精确）
  python3 python/protocol/trim_assets.py --protocol ... --mode copy

  # 只打印计划，不执行
  python3 python/protocol/trim_assets.py --protocol ... --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from protocol.converter import resolve_ffmpeg


def pick_ffmpeg() -> str:
    """优先环境变量 / 系统 PATH；打包版在部分环境会被 SIGKILL。"""
    env = os.environ.get("JYCONVERT_FFMPEG", "").strip()
    if env and Path(env).is_file():
        return env
    system = shutil.which("ffmpeg")
    if system:
        return system
    resolved = resolve_ffmpeg()
    if resolved:
        return resolved
    raise FileNotFoundError("找不到 ffmpeg，请安装或运行 scripts/fetch-ffmpeg.js")

MEDIA_TRACK_TYPES = {"video", "audio", "image"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
AUDIO_EXTS = {".mp3", ".wav", ".aac", ".m4a", ".flac", ".ogg"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


@dataclass
class TrimJob:
    material_id: str
    segment_id: str
    track_type: str
    src_path: Path
    start_ms: int
    duration_ms: int

    @property
    def out_name(self) -> str:
        stem = self.src_path.stem
        ext = self.src_path.suffix.lower() or ".mp4"
        safe_stem = re.sub(r"[^\w.\-]+", "_", stem)[:80]
        return f"{safe_stem}_{self.start_ms}-{self.duration_ms}{ext}"


def ms_to_sec(ms: int | float) -> float:
    return max(0.0, float(ms) / 1000.0)


from protocol.path_resolver import resolve_protocol_path(protocol: dict[str, Any]) -> dict[str, tuple[str, dict[str, Any]]]:
    lookup: dict[str, tuple[str, dict[str, Any]]] = {}
    for category in ("videos", "audios", "images"):
        for item in protocol.get("materials", {}).get(category, []):
            lookup[item["id"]] = (category, item)
    return lookup


def collect_trim_jobs(
    protocol: dict[str, Any],
    resource_root: Path,
    *,
    must_exist: bool = True,
) -> list[TrimJob]:
    lookup = build_material_lookup(protocol)
    jobs: list[TrimJob] = []
    seen: set[tuple[str, int, int]] = set()

    for track in protocol.get("tracks", []):
        track_type = track.get("type", "")
        if track_type not in MEDIA_TRACK_TYPES:
            continue
        for seg in track.get("segments", []):
            mid = seg.get("material_id", "")
            if not mid or mid not in lookup:
                continue
            category, mat = lookup[mid]
            src = resolve_protocol_path(mat.get("path", ""), resource_root, must_exist=must_exist)
            if not src:
                continue

            source_tr = seg.get("source_timerange") or seg.get("target_timerange") or {}
            start_ms = int(source_tr.get("start", 0))
            duration_ms = int(source_tr.get("duration", 0))
            if duration_ms <= 0:
                continue

            key = (mid, start_ms, duration_ms)
            if key in seen:
                continue
            seen.add(key)

            ext = src.suffix.lower()
            if category == "images" or ext in IMAGE_EXTS:
                continue

            jobs.append(TrimJob(
                material_id=mid,
                segment_id=seg.get("id", mid),
                track_type=track_type,
                src_path=src,
                start_ms=start_ms,
                duration_ms=duration_ms,
            ))
    return jobs


def probe_duration_ms(ffmpeg: str, path: Path) -> int | None:
    ffprobe = Path(ffmpeg).with_name("ffprobe")
    if not ffprobe.is_file():
        ffprobe_path = shutil.which("ffprobe")
        if not ffprobe_path:
            return None
        ffprobe = Path(ffprobe_path)
    proc = subprocess.run(
        [
            str(ffprobe),
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    try:
        return int(round(float(proc.stdout.strip()) * 1000))
    except ValueError:
        return None


def should_copy_whole_file(job: TrimJob, ffmpeg: str) -> bool:
    if job.start_ms != 0:
        return False
    file_ms = probe_duration_ms(ffmpeg, job.src_path)
    if file_ms is None:
        return False
    return abs(file_ms - job.duration_ms) <= 50


def copy_whole_file(src: Path, dst: Path, *, dry_run: bool) -> None:
    print(f"  $ cp {src} -> {dst}")
    if not dry_run:
        shutil.copy2(src, dst)


def run_ffmpeg(cmd: list[str], *, dry_run: bool) -> None:
    print("  $", " ".join(cmd))
    if dry_run:
        return
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"ffmpeg failed: {proc.returncode}")


def trim_media(
    ffmpeg: str,
    job: TrimJob,
    dst: Path,
    *,
    mode: str,
    dry_run: bool,
) -> None:
    start = ms_to_sec(job.start_ms)
    duration = ms_to_sec(job.duration_ms)
    ext = job.src_path.suffix.lower()

    if ext in AUDIO_EXTS:
        cmd = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(job.src_path),
            "-ss", f"{start:.3f}",
            "-t", f"{duration:.3f}",
            "-vn",
        ]
        if ext == ".mp3":
            cmd += ["-c:a", "libmp3lame", "-q:a", "2", str(dst)]
        else:
            cmd += ["-c", "copy", str(dst)]
        run_ffmpeg(cmd, dry_run=dry_run)
        return

    # video
    if mode == "copy":
        cmd = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{start:.3f}",
            "-i", str(job.src_path),
            "-t", f"{duration:.3f}",
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            str(dst),
        ]
    else:
        # -ss 放在 -i 之后：解码级精确裁剪（会重编码）
        cmd = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(job.src_path),
            "-ss", f"{start:.3f}",
            "-t", f"{duration:.3f}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(dst),
        ]
    run_ffmpeg(cmd, dry_run=dry_run)


def apply_trim_to_protocol(
    protocol: dict[str, Any],
    *,
    material_out_paths: dict[str, str],
    material_durations: dict[str, int],
) -> dict[str, Any]:
    updated = json.loads(json.dumps(protocol))
    lookup = build_material_lookup(updated)

    for mid, rel_path in material_out_paths.items():
        if mid not in lookup:
            continue
        category, mat = lookup[mid]
        mat["path"] = rel_path
        if category == "videos" and mid in material_durations:
            mat["duration"] = material_durations[mid]

    for track in updated.get("tracks", []):
        if track.get("type") not in MEDIA_TRACK_TYPES:
            continue
        for seg in track.get("segments", []):
            mid = seg.get("material_id", "")
            if mid not in material_out_paths:
                continue
            dur = material_durations.get(mid)
            if dur is None:
                source_tr = seg.get("source_timerange") or {}
                dur = int(source_tr.get("duration", 0))
            seg["source_timerange"] = {"start": 0, "duration": dur}

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


def trim_protocol_assets(
    protocol_path: Path,
    output_dir: Path | None,
    *,
    mode: str = "accurate",
    dry_run: bool = False,
) -> Path:
    protocol_path = protocol_path.resolve()
    resource_root = protocol_path.parent
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))

    if output_dir is None:
        output_dir = resource_root.parent / f"{resource_root.name}_trimmed"
    output_dir = output_dir.resolve()
    assets_dir = output_dir / "assets"
    fonts_src = resource_root / "fonts"

    ffmpeg = pick_ffmpeg()
    if not ffmpeg and not dry_run:
        raise FileNotFoundError("找不到 ffmpeg，请安装或运行 scripts/fetch-ffmpeg.js")

    jobs = collect_trim_jobs(protocol, resource_root)
    if not jobs:
        raise ValueError("协议中没有可裁剪的音视频片段（检查 tracks + source_timerange）")

    if not dry_run:
        if output_dir.exists():
            shutil.rmtree(output_dir)
        assets_dir.mkdir(parents=True, exist_ok=True)
        if fonts_src.is_dir():
            shutil.copytree(fonts_src, output_dir / "fonts")

    material_out_paths: dict[str, str] = {}
    material_durations: dict[str, int] = {}

    print(f"共 {len(jobs)} 个裁剪任务（mode={mode}）\n")
    for index, job in enumerate(jobs, 1):
        rel = f"./assets/{job.out_name}"
        dst = assets_dir / job.out_name
        print(
            f"[{index}/{len(jobs)}] {job.material_id}  "
            f"{job.src_path.name}  {job.start_ms}ms +{job.duration_ms}ms"
        )
        if not dry_run and should_copy_whole_file(job, ffmpeg or "ffmpeg"):
            copy_whole_file(job.src_path, dst, dry_run=dry_run)
        else:
            trim_media(ffmpeg or "ffmpeg", job, dst, mode=mode, dry_run=dry_run)
        material_out_paths[job.material_id] = rel
        material_durations[job.material_id] = job.duration_ms

    # 图片等未裁剪素材：原样复制
    lookup = build_material_lookup(protocol)
    referenced_images: set[str] = set()
    for track in protocol.get("tracks", []):
        if track.get("type") != "image":
            continue
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
        print(f"[copy] {src.name}")
        if not dry_run:
            shutil.copy2(src, dst)
        material_out_paths[mid] = rel

    updated = apply_trim_to_protocol(
        protocol,
        material_out_paths=material_out_paths,
        material_durations=material_durations,
    )
    out_protocol = output_dir / "converted_protocol.json"
    if not dry_run:
        out_protocol.write_text(
            json.dumps(updated, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return out_protocol


def main() -> None:
    parser = argparse.ArgumentParser(description="按协议 source_timerange 裁剪素材")
    parser.add_argument("--protocol", type=Path, required=True, help="converted_protocol.json")
    parser.add_argument("--output-dir", type=Path, help="输出目录（默认 <协议目录>_trimmed）")
    parser.add_argument(
        "--mode",
        choices=("accurate", "copy"),
        default="accurate",
        help="accurate=重编码帧精确；copy=流复制更快但可能不精确",
    )
    parser.add_argument("--dry-run", action="store_true", help="只打印 ffmpeg 命令")
    args = parser.parse_args()

    if not args.protocol.exists():
        raise FileNotFoundError(f"协议不存在: {args.protocol}")

    out = trim_protocol_assets(
        args.protocol,
        args.output_dir,
        mode=args.mode,
        dry_run=args.dry_run,
    )
    if not args.dry_run:
        print(f"\n✓ 完成: {out}")


if __name__ == "__main__":
    main()
