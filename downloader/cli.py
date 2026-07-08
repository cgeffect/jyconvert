#!/usr/bin/env python3
"""本地测试 CLI：从分享文案或 URL 下载视频。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.download import DownloadOptions, download_video, probe_url, resolve_input_url
from lib.chrome_cookies import inspect_chrome_cookies
from lib.extract import extract_urls


def cmd_extract(args: argparse.Namespace) -> int:
    urls = extract_urls(args.text)
    if not urls:
        print("未找到链接", file=sys.stderr)
        return 1
    for url in urls:
        print(url)
    return 0


def _add_cookie_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--cookies-browser",
        default="chrome",
        help="从浏览器读取 Cookie（默认 chrome，传 none 禁用）",
    )
    parser.add_argument(
        "--cookies-file",
        default=None,
        help="Netscape 格式 cookies.txt（优先于 --cookies-browser）",
    )


def _resolve_cookie_args(args: argparse.Namespace) -> tuple[str | None, Path | None]:
    browser = None if args.cookies_browser == "none" else args.cookies_browser
    cookies_file = Path(args.cookies_file).expanduser() if args.cookies_file else None
    return browser, cookies_file


def cmd_probe(args: argparse.Namespace) -> int:
    browser, cookies_file = _resolve_cookie_args(args)
    try:
        url = resolve_input_url(args.input)
        info = probe_url(url, cookies_from_browser=browser, cookies_file=cookies_file)
    except Exception as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1

    print(f"URL:   {url}")
    print(f"标题:  {info.get('title', '—')}")
    print(f"时长:  {info.get('duration', '—')}s")
    print(f"ID:    {info.get('id', '—')}")
    return 0


def cmd_download(args: argparse.Namespace) -> int:
    output_dir = Path(args.output).expanduser().resolve()
    browser, cookies_file = _resolve_cookie_args(args)

    def on_progress(line: str) -> None:
        if args.verbose or line.startswith("[") or "%" in line:
            print(line, flush=True)

    result = download_video(
        args.input,
        DownloadOptions(
            output_dir=output_dir,
            cookies_from_browser=browser,
            cookies_file=cookies_file,
        ),
        on_progress=on_progress,
    )

    if not result.ok:
        print(f"\n下载失败: {result.error}", file=sys.stderr)
        if result.log:
            print(result.log, file=sys.stderr)
        return 1

    print("\n下载成功")
    print(f"  链接: {result.url}")
    if result.filepath:
        print(f"  文件: {result.filepath}")
    return 0


def cmd_check_cookies(_args: argparse.Namespace) -> int:
    import json

    status = inspect_chrome_cookies()
    payload = {
        "db_path": str(status.db_path) if status.db_path else None,
        "total": status.total,
        "douyin": status.douyin,
        "ok": status.douyin > 0,
        "message": (
            "已检测到 douyin Cookie，可尝试下载"
            if status.douyin
            else "未检测到 douyin Cookie。请在 Chrome 打开 https://www.douyin.com 登录并刷新，或使用应用内登录。"
        ),
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="jyconvert 视频下载（本地测试）")
    sub = parser.add_subparsers(dest="command", required=True)

    p_extract = sub.add_parser("extract", help="从分享文案提取 URL")
    p_extract.add_argument("text", help="分享文案")
    p_extract.set_defaults(func=cmd_extract)

    p_probe = sub.add_parser("probe", help="探测视频信息（不下载）")
    p_probe.add_argument("input", help="URL 或分享文案")
    _add_cookie_args(p_probe)
    p_probe.set_defaults(func=cmd_probe)

    p_dl = sub.add_parser("download", help="下载视频")
    p_dl.add_argument("input", help="URL 或分享文案")
    p_dl.add_argument(
        "-o",
        "--output",
        default=str(ROOT / "output"),
        help="保存目录（默认 downloader/output）",
    )
    _add_cookie_args(p_dl)
    p_dl.add_argument("-v", "--verbose", action="store_true", help="输出完整日志")
    p_dl.set_defaults(func=cmd_download)

    p_check = sub.add_parser("check-cookies", help="检测 Chrome 是否有 douyin Cookie")
    p_check.set_defaults(func=cmd_check_cookies)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
