"""从分享文案中提取可下载的视频链接。"""

from __future__ import annotations

import re
from typing import Iterable

# 抖音短链（手机/网页分享文案里最常见）
DOUYIN_SHORT_RE = re.compile(
    r"https?://v\.douyin\.com/[A-Za-z0-9_\-]+/?",
    re.IGNORECASE,
)

# 抖音完整页
DOUYIN_VIDEO_RE = re.compile(
    r"https?://(?:www\.)?douyin\.com/video/\d+",
    re.IGNORECASE,
)

# 抖音分享页（旧域名）
IESDOUYIN_RE = re.compile(
    r"https?://(?:www\.)?iesdouyin\.com/share/video/\d+",
    re.IGNORECASE,
)

# 通用：任意 http(s) 链接（兜底，优先级最低）
GENERIC_URL_RE = re.compile(r"https?://[^\s<>\[\]()\"']+", re.IGNORECASE)

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("douyin_short", DOUYIN_SHORT_RE),
    ("douyin_video", DOUYIN_VIDEO_RE),
    ("iesdouyin", IESDOUYIN_RE),
)


def _normalize_url(url: str) -> str:
    cleaned = url.rstrip(".,;:!?)】》\"'")
    return cleaned


def extract_urls(text: str) -> list[str]:
    """
    从整段分享文案中提取 URL，按优先级去重返回。

    支持手机分享、网页分享等夹杂大量无关字符的文本。
    """
    if not text or not text.strip():
        return []

    found: list[str] = []
    seen: set[str] = set()

    for _kind, pattern in _PATTERNS:
        for match in pattern.finditer(text):
            url = _normalize_url(match.group(0))
            if url not in seen:
                seen.add(url)
                found.append(url)

    if found:
        return found

    for match in GENERIC_URL_RE.finditer(text):
        url = _normalize_url(match.group(0))
        if url not in seen:
            seen.add(url)
            found.append(url)

    return found


def pick_best_url(text: str) -> str | None:
    """返回文案中最优先的一条链接。"""
    urls = extract_urls(text)
    return urls[0] if urls else None


def is_likely_share_text(text: str) -> bool:
    """判断输入更像分享文案而非纯 URL。"""
    stripped = text.strip()
    if not stripped:
        return False
    if stripped.startswith("http://") or stripped.startswith("https://"):
        return False
    return bool(extract_urls(stripped))
