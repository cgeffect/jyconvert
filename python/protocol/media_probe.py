"""ffprobe / ffmpeg 路径与媒体探测。"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from protocol.converter import resolve_ffmpeg


def pick_ffmpeg() -> str:
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


def pick_ffprobe() -> str:
    ffmpeg = pick_ffmpeg()
    candidate = Path(ffmpeg).with_name("ffprobe")
    if candidate.is_file():
        return str(candidate)
    found = shutil.which("ffprobe")
    if found:
        return found
    raise FileNotFoundError("找不到 ffprobe")


def probe_duration_ms(path: Path) -> int | None:
    proc = subprocess.run(
        [
            pick_ffprobe(),
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


def list_keyframe_times_sec(path: Path) -> list[float]:
    """返回视频关键帧时间戳（秒），含 0。"""
    proc = subprocess.run(
        [
            pick_ffprobe(),
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "packet=pts_time,flags",
            "-of", "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "ffprobe keyframes failed")

    times: list[float] = []
    for line in proc.stdout.splitlines():
        parts = [part.strip() for part in line.split(",") if part.strip()]
        if len(parts) < 2:
            continue
        try:
            pts = float(parts[0])
        except ValueError:
            continue
        if "K" not in parts[1]:
            continue
        times.append(pts)

    if not times:
        proc = subprocess.run(
            [
                pick_ffprobe(),
                "-v", "error",
                "-select_streams", "v:0",
                "-skip_frame", "nokey",
                "-show_entries", "frame=pkt_dts_time",
                "-of", "csv=p=0",
                str(path),
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                line = line.strip().rstrip(",")
                if not line:
                    continue
                try:
                    times.append(float(line))
                except ValueError:
                    continue

    if not times or times[0] > 0.001:
        times.insert(0, 0.0)
    return sorted(set(times))


def align_to_keyframes(
    start_ms: int,
    end_ms: int,
    keyframes_sec: list[float],
    file_duration_ms: int,
) -> tuple[int, int]:
    """
    将 [start_ms, end_ms) 扩展为关键帧对齐区间 [trim_start_ms, trim_end_ms]。
    trim_start = start 之前（含）最近的关键帧；trim_end = end 之后（含）最近的关键帧。
    """
    start_sec = start_ms / 1000.0
    end_sec = end_ms / 1000.0
    file_end_sec = file_duration_ms / 1000.0

    prev_kf = [t for t in keyframes_sec if t <= start_sec + 1e-6]
    trim_start_sec = max(prev_kf) if prev_kf else 0.0

    next_kf = [t for t in keyframes_sec if t >= end_sec - 1e-6]
    trim_end_sec = min(next_kf) if next_kf else file_end_sec
    if trim_end_sec < trim_start_sec:
        trim_end_sec = file_end_sec

    trim_start_ms = int(round(trim_start_sec * 1000))
    trim_end_ms = int(round(trim_end_sec * 1000))
    if trim_end_ms <= trim_start_ms:
        trim_end_ms = min(file_duration_ms, trim_start_ms + max(1, end_ms - start_ms))
    return trim_start_ms, trim_end_ms
