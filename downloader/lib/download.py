"""yt-dlp 下载封装。"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from .chrome_cookies import (
    chrome_douyin_cookie_hint,
    create_isolated_chrome_cookies,
    inspect_chrome_cookies,
    IsolatedChromeCookies,
)
from .extract import extract_urls, pick_best_url

ProgressCallback = Callable[[str], None]


@dataclass
class DownloadOptions:
    output_dir: Path
    cookies_from_browser: str | None = "chrome"
    cookies_file: Path | None = None
    format: str = "bestvideo*+bestaudio/best"
    merge_format: str = "mp4"
    write_info_json: bool = False


@dataclass
class DownloadResult:
    ok: bool
    url: str
    title: str | None = None
    filepath: Path | None = None
    error: str | None = None
    log: str = field(default_factory=str)


def resolve_ytdlp() -> list[str]:
    """
    返回 yt-dlp 启动命令前缀。

    优先使用内嵌二进制（jyconvert/bin/yt-dlp 或 YTDLP_PATH），
    不依赖系统 PATH 中的 yt-dlp。本地开发可设 ALLOW_SYSTEM_YTDLP=1 回退。
    """
    for candidate in _bundled_ytdlp_candidates():
        if candidate.is_file():
            return [str(candidate)]

    module_root = Path(__file__).resolve().parents[1]
    venv_bin = module_root / ".venv" / "bin" / "yt-dlp"
    if venv_bin.is_file():
        return [str(venv_bin)]

    if os.environ.get("ALLOW_SYSTEM_YTDLP") == "1":
        which = shutil.which("yt-dlp")
        if which:
            return [which]

    jyconvert_bin = module_root.parent / "bin" / "yt-dlp"
    raise FileNotFoundError(
        "找不到内嵌 yt-dlp。请运行: bash scripts/fetch-ytdlp.sh\n"
        f"期望路径: {jyconvert_bin}"
    )


def _bundled_ytdlp_candidates() -> list[Path]:
    module_root = Path(__file__).resolve().parents[1]
    jyconvert_root = module_root.parent
    bin_name = "yt-dlp.exe" if os.name == "nt" else "yt-dlp"
    candidates: list[Path] = []

    env_path = os.environ.get("YTDLP_PATH", "").strip()
    if env_path:
        candidates.append(Path(env_path))

    candidates.append(jyconvert_root / "bin" / "yt-dlp.app" / bin_name)
    candidates.append(jyconvert_root / "bin" / bin_name)
    return candidates


def _spawn_env() -> dict[str, str]:
    extra = ["/opt/homebrew/bin", "/usr/local/bin"]
    path_parts = [p for p in extra if os.path.isdir(p)]
    path_parts.append(os.environ.get("PATH", ""))
    return {**os.environ, "PATH": ":".join(path_parts)}


def resolve_input_url(text_or_url: str) -> str:
    """纯 URL 直接返回；分享文案则提取第一条链接。"""
    stripped = text_or_url.strip()
    if not stripped:
        raise ValueError("请输入链接或分享文案")

    if stripped.startswith("http://") or stripped.startswith("https://"):
        urls = extract_urls(stripped)
        return urls[0] if urls else stripped

    url = pick_best_url(stripped)
    if not url:
        raise ValueError("未在文案中找到可识别的视频链接")
    return url


def _friendly_error(raw: str, log: str = "") -> str:
    lower = raw.lower()
    log_lower = log.lower()
    if "storage/ext/glic" in log_lower and "extracted" in log_lower:
        hint = chrome_douyin_cookie_hint()
        if hint:
            return (
                "yt-dlp 读取到了 Chrome 扩展的 Cookie，但未找到抖音登录 Cookie。\n"
                f"{hint}\n"
                f"\n原始错误: {raw}"
            )
    if "fresh cookies" in lower or ("cookies" in lower and "douyin" in lower):
        hint = chrome_douyin_cookie_hint()
        extra = f"\n{hint}" if hint else ""
        return (
            "抖音 Cookie 无效或未包含登录态。\n"
            "常见原因：yt-dlp 误读了 Chrome 扩展 Cookie（已在本工具中修复），"
            "或 Chrome 里实际上还没有 douyin.com 的登录 Cookie。\n"
            "请尝试：\n"
            "1. 在 Chrome 打开 https://www.douyin.com ，刷新并确认右上角头像\n"
            "2. 点下载窗口「检测登录」，确认能读到 douyin Cookie\n"
            "3. 仍失败则用扩展导出 cookies.txt 并选择该文件"
            f"{extra}\n"
            f"\n原始错误: {raw}"
        )
    if "failed to parse json" in lower and "douyin" in lower:
        return (
            "抖音接口返回异常，通常是 Cookie 失效或被风控拦截。"
            "请换 Safari、导出 cookies.txt，或稍后重试。\n"
            f"\n原始错误: {raw}"
        )
    return raw


def _cookie_attempts(
    cookies_from_browser: str | None,
    cookies_file: Path | None,
) -> list[tuple[str | None, Path | None]]:
    """按优先级生成 Cookie 来源尝试列表。"""
    if cookies_file and cookies_file.is_file():
        return [(None, cookies_file)]

    if not cookies_from_browser or cookies_from_browser == "none":
        return [(None, None)]

    browser = cookies_from_browser.strip().lower()
    if browser == "chrome":
        return [
            ("__isolated_chrome__", None),
            ("edge", None),
        ]
    if browser == "safari":
        return [
            ("safari", None),
            ("__isolated_chrome__", None),
        ]
    if browser == "edge":
        return [
            ("edge", None),
            ("__isolated_chrome__", None),
        ]
    return [(cookies_from_browser, None)]


def _apply_cookie_args(
    cmd: list[str],
    *,
    cookies_from_browser: str | None,
    cookies_file: Path | None,
) -> None:
    if cookies_file and cookies_file.is_file():
        cmd[1:1] = ["--cookies", str(cookies_file)]
    elif cookies_from_browser:
        cmd[1:1] = ["--cookies-from-browser", cookies_from_browser]


def probe_url(
    url: str,
    *,
    cookies_from_browser: str | None = "chrome",
    cookies_file: Path | None = None,
) -> dict:
    """获取视频元信息（不下载）。"""
    cmd = [
        *resolve_ytdlp(),
        "--dump-single-json",
        "--no-playlist",
        "--no-warnings",
        url,
    ]
    _apply_cookie_args(
        cmd,
        cookies_from_browser=cookies_from_browser,
        cookies_file=cookies_file,
    )

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=_spawn_env(),
        check=False,
    )
    if proc.returncode != 0:
        err = proc.stderr.strip() or proc.stdout.strip() or f"退出码 {proc.returncode}"
        raise RuntimeError(_friendly_error(err))

    return json.loads(proc.stdout)


def _run_ytdlp(cmd: list[str], on_progress: ProgressCallback | None) -> tuple[int, str]:
    log_lines: list[str] = []

    def emit(line: str) -> None:
        log_lines.append(line)
        if on_progress:
            on_progress(line)

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=_spawn_env(),
    )

    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            emit(line)

    return proc.wait(), "\n".join(log_lines)


def _is_retryable_douyin_cookie_error(log: str) -> bool:
    lower = log.lower()
    return "douyin" in lower and (
        "fresh cookies" in lower or "failed to parse json" in lower
    )


def _is_browser_cookie_access_error(log: str) -> bool:
    lower = log.lower()
    return "operation not permitted" in lower or "could not copy chrome cookie" in lower


def download_video(
    text_or_url: str,
    options: DownloadOptions,
    on_progress: ProgressCallback | None = None,
) -> DownloadResult:
    """
    下载单个视频。

    text_or_url: 纯 URL 或整段分享文案
    """
    log_lines: list[str] = []

    def emit(line: str) -> None:
        log_lines.append(line)
        if on_progress:
            on_progress(line)

    try:
        url = resolve_input_url(text_or_url)
    except ValueError as exc:
        return DownloadResult(ok=False, url="", error=str(exc), log="\n".join(log_lines))

    output_dir = options.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not options.cookies_file and options.cookies_from_browser not in (None, "none"):
        hint = chrome_douyin_cookie_hint()
        if hint:
            emit(f"提示: {hint}")

    outtmpl = str(output_dir / "%(title).80B [%(id)s].%(ext)s")
    attempts = _cookie_attempts(options.cookies_from_browser, options.cookies_file)

    full_log = ""
    last_raw_err = ""
    last_douyin_err = ""

    for index, (browser, cookies_file) in enumerate(attempts):
        isolated: IsolatedChromeCookies | None = None
        browser_spec = browser
        if browser == "__isolated_chrome__":
            isolated = create_isolated_chrome_cookies()
            if not isolated:
                emit("跳过: 找不到 Chrome 主 Cookie 库")
                continue
            browser_spec = isolated.browser_spec
            status = inspect_chrome_cookies()
            emit(
                f"使用 Chrome 主 Cookie 库（共 {status.total} 条，douyin 相关 {status.douyin} 条）"
            )

        cmd = [
            *resolve_ytdlp(),
            "--no-playlist",
            "--merge-output-format",
            options.merge_format,
            "-f",
            options.format,
            "-o",
            outtmpl,
            "--newline",
            "--progress",
            url,
        ]

        _apply_cookie_args(
            cmd,
            cookies_from_browser=browser_spec,
            cookies_file=cookies_file,
        )

        if options.write_info_json:
            cmd.insert(-1, "--write-info-json")

        if index > 0:
            label = cookies_file or browser_spec or browser or "无 Cookie"
            emit(f"--- 尝试备用 Cookie 来源: {label} ---")
        emit(f"执行: {' '.join(cmd[:8])} ... {url}")

        try:
            code, attempt_log = _run_ytdlp(cmd, emit)
        finally:
            if isolated:
                isolated.cleanup()
        full_log = f"{full_log}\n{attempt_log}".strip() if full_log else attempt_log

        if code == 0:
            filepath = _find_latest_media(output_dir)
            title = filepath.stem if filepath else None
            return DownloadResult(
                ok=True,
                url=url,
                title=title,
                filepath=filepath,
                log=full_log,
            )

        last_raw_err = attempt_log.splitlines()[-1] if attempt_log else f"退出码 {code}"
        if _is_retryable_douyin_cookie_error(attempt_log):
            last_douyin_err = last_raw_err
            if index + 1 < len(attempts):
                continue
        if len(attempts) == 1:
            break
        if _is_browser_cookie_access_error(attempt_log):
            continue
        if not _is_retryable_douyin_cookie_error(attempt_log):
            break

    report_err = last_douyin_err or last_raw_err
    return DownloadResult(
        ok=False,
        url=url,
        error=_friendly_error(report_err, full_log),
        log=full_log,
    )


def _find_latest_media(output_dir: Path) -> Path | None:
    candidates: Iterable[Path] = (
        p
        for p in output_dir.iterdir()
        if p.is_file() and p.suffix.lower() in {".mp4", ".mkv", ".webm", ".m4a", ".mp3"}
    )
    files = list(candidates)
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)
