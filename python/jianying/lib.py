"""剪映草稿路径。"""

from __future__ import annotations

from pathlib import Path

JIANYING_ROOT = Path("/Users/xy/Movies/JianyingPro")

DRAFTS_REL = Path("User Data/Projects/com.lveditor.draft")

JIANYING_PATH_ALIASES = [
    JIANYING_ROOT,
    Path("/Users/xy/Library/Containers/com.lemon.lvpro/Data/Movies/JianyingPro"),
]


def jianying_drafts_root() -> Path:
    return JIANYING_ROOT / DRAFTS_REL
