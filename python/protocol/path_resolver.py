"""协议内媒体路径解析：相对协议 JSON 所在目录。"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


def resolve_protocol_path(
    raw: str,
    protocol_dir: Path,
    *,
    must_exist: bool = True,
    extra_roots: Iterable[Path] = (),
) -> Path | None:
    """
    将协议中的 path 解析为本地文件路径。

    约定：``./assets/foo.mp4``、``./abc/foo.mp4`` 均相对 **协议 JSON 文件所在目录**。
    ``extra_roots`` 仅作兼容回退（例如历史素材包把资源放在上级目录）。
    """
    if not raw:
        return None

    p = Path(raw)
    if p.is_absolute():
        if not must_exist or p.exists():
            return p.resolve()
        return None

    protocol_dir = protocol_dir.resolve()
    rel = raw.lstrip("./")
    candidates = [
        protocol_dir / raw,
        protocol_dir / rel,
    ]
    for root in extra_roots:
        root = root.resolve()
        candidates.extend((root / raw, root / rel))

    seen: set[Path] = set()
    for candidate in candidates:
        key = candidate.resolve()
        if key in seen:
            continue
        seen.add(key)
        if candidate.exists():
            return key

    if not must_exist and candidates:
        return candidates[0].resolve()
    return None
