"""Python 包根目录（开发 / PyInstaller 打包统一入口）。"""

from __future__ import annotations

import sys
from pathlib import Path


def python_root() -> Path:
    """含 templates/ 等资源；PyInstaller 打包后为 sys._MEIPASS。"""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent
