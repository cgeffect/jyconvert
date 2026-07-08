"""剪映草稿路径。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

DRAFTS_REL = Path("User Data/Projects/com.lveditor.draft")


def default_jianying_drafts_roots() -> list[Path]:
    """各平台常见剪映草稿目录候选（含自定义安装时的默认位置）。"""
    home = Path.home()
    candidates: list[Path] = []

    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "").strip()
        if local:
            candidates.append(
                Path(local) / "JianyingPro" / "User Data" / "Projects" / "com.lveditor.draft"
            )
        candidates.append(
            home / "AppData" / "Local" / "JianyingPro" / "User Data" / "Projects" / "com.lveditor.draft"
        )
    else:
        candidates.append(home / "Movies" / "JianyingPro" / DRAFTS_REL)
        candidates.append(
            home
            / "Library"
            / "Containers"
            / "com.lemon.lvpro"
            / "Data"
            / "Movies"
            / "JianyingPro"
            / DRAFTS_REL
        )

    return candidates


def normalize_jianying_drafts_root(raw: str | Path) -> Path:
    """将用户输入规范为 com.lveditor.draft 目录。"""
    path = Path(str(raw).strip()).expanduser()
    if not path.is_absolute():
        path = path.resolve()

    if path.name == "com.lveditor.draft":
        return path

    nested = path / "User Data" / "Projects" / "com.lveditor.draft"
    if nested.is_dir():
        return nested.resolve()

    if path.name == "JianyingPro":
        candidate = path / DRAFTS_REL
        if candidate.is_dir():
            return candidate.resolve()

    return path


def resolve_jianying_drafts_root(override: str | Path | None = None) -> Path:
    """解析剪映草稿根目录；优先用户配置，其次环境变量，最后自动探测。"""
    if override:
        root = normalize_jianying_drafts_root(override)
        if not root.is_dir():
            raise FileNotFoundError(f"剪映草稿目录不存在: {root}")
        return root

    env = os.environ.get("JYCONVERT_JIANYING_DRAFTS_ROOT", "").strip()
    if env:
        root = normalize_jianying_drafts_root(env)
        if root.is_dir():
            return root

    for candidate in default_jianying_drafts_roots():
        if candidate.is_dir():
            return candidate.resolve()

    raise FileNotFoundError(
        "未找到剪映草稿目录。请在导入前配置剪映草稿路径（通常为 "
        ".../JianyingPro/User Data/Projects/com.lveditor.draft）。"
    )


def jianying_drafts_root(override: str | Path | None = None) -> Path:
    return resolve_jianying_drafts_root(override)


# 兼容旧代码引用（仅用于文档/日志；实际导入请传 drafts_root）
JIANYING_ROOT = Path.home() / "Movies" / "JianyingPro"
JIANYING_PATH_ALIASES = default_jianying_drafts_roots()
