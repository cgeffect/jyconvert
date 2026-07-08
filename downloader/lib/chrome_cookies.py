"""Chrome Cookie 检测与导出（绕过 yt-dlp 误选扩展 Cookie 库的问题）。"""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path

DOUYIN_HOST_SQL = (
    "host_key LIKE '%douyin%' OR host_key LIKE '%iesdouyin%' OR host_key LIKE '%amemv%'"
)


@dataclass(frozen=True)
class ChromeCookieStatus:
    total: int
    douyin: int
    db_path: Path | None


def _chrome_roots() -> list[Path]:
    if os.name != "posix":
        return []
    home = Path.home()
    return [
        home / "Library/Application Support/Google/Chrome",
        home / "Library/Application Support/Google/Chrome Beta",
        home / "Library/Application Support/Chromium",
    ]


def _main_cookie_db(chrome_root: Path) -> Path | None:
    db = chrome_root / "Default" / "Cookies"
    return db if db.is_file() else None


def inspect_chrome_cookies() -> ChromeCookieStatus:
    """只读统计 Chrome 主 Cookie 库（不解密值）。"""
    for root in _chrome_roots():
        db_path = _main_cookie_db(root)
        if not db_path:
            continue
        try:
            con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            total = con.execute("SELECT COUNT(*) FROM cookies").fetchone()[0]
            douyin = con.execute(
                f"SELECT COUNT(*) FROM cookies WHERE {DOUYIN_HOST_SQL}",
            ).fetchone()[0]
            con.close()
            return ChromeCookieStatus(total=total, douyin=douyin, db_path=db_path)
        except sqlite3.Error:
            continue
    return ChromeCookieStatus(total=0, douyin=0, db_path=None)


def chrome_douyin_cookie_hint() -> str | None:
    status = inspect_chrome_cookies()
    if status.douyin:
        return None
    if status.db_path:
        return (
            f"Chrome 主 Cookie 库（{status.db_path}）中未发现 douyin.com 登录 Cookie（共 {status.total} 条）。"
            "网页上看起来已登录，有时 Cookie 尚未写入或被拦截。"
            "请在 Chrome 打开 https://www.douyin.com ，刷新页面并确认右上角头像，"
            "然后点「检测登录」或导出 cookies.txt。"
        )
    return (
        "未找到 Chrome 主 Cookie 库。"
        "请在 Chrome 打开 https://www.douyin.com 登录后重试，或导出 cookies.txt。"
    )


@dataclass
class IsolatedChromeCookies:
    """将 Chrome 主 Cookie 库复制到独立临时目录，供 yt-dlp 读取。"""

    tmp_dir: Path
    browser_spec: str

    def cleanup(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)


def create_isolated_chrome_cookies() -> IsolatedChromeCookies | None:
    """
    yt-dlp 会在 Chrome 配置目录下递归查找名为 Cookies 的文件并取最新修改时间，
    可能误选 Storage/ext/glic/... 扩展目录。此处只复制 Default/Cookies + Local State。
    """
    for root in _chrome_roots():
        cookies_db = _main_cookie_db(root)
        local_state = root / "Local State"
        if not cookies_db or not local_state.is_file():
            continue

        tmp_dir = Path(tempfile.mkdtemp(prefix="jyconvert-chrome-cookies-"))
        try:
            profile_dir = tmp_dir / "Default"
            profile_dir.mkdir(parents=True)
            shutil.copy2(cookies_db, profile_dir / "Cookies")
            shutil.copy2(local_state, tmp_dir / "Local State")
            return IsolatedChromeCookies(
                tmp_dir=tmp_dir,
                browser_spec=f"chrome:{profile_dir}",
            )
        except OSError:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            continue
    return None
