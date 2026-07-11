"""剪映/CapCut 加密 draft_info.json 检测与可选解密。"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

CAPCUT_LIB = Path("/Applications/CapCut.app/Contents/Frameworks/libvideoeditor.dylib")
CAPCUT_FRAMEWORKS = CAPCUT_LIB.parent

DECRYPT_HELPER_SRC = Path(__file__).resolve().parent / "draft_decrypt_helper.cpp"
DECRYPT_HELPER_BIN = Path(__file__).resolve().parent / "draft_decrypt_helper"


def is_encrypted_draft_text(text: str) -> bool:
    stripped = text.lstrip()
    if not stripped:
        return False
    if stripped.startswith("{"):
        try:
            json.loads(text)
            return False
        except json.JSONDecodeError:
            return True
    return True


def is_encrypted_draft_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    return is_encrypted_draft_text(text)


def _ensure_decrypt_helper() -> Path | None:
    if DECRYPT_HELPER_BIN.exists() and DECRYPT_HELPER_BIN.stat().st_mtime >= DECRYPT_HELPER_SRC.stat().st_mtime:
        return DECRYPT_HELPER_BIN
    if not CAPCUT_LIB.exists() or not DECRYPT_HELPER_SRC.exists():
        return None

    cmd = [
        "c++",
        "-std=c++17",
        "-O2",
        "-o",
        str(DECRYPT_HELPER_BIN),
        str(DECRYPT_HELPER_SRC),
        f"-L{CAPCUT_FRAMEWORKS}",
        "-lvideoeditor",
        f"-Wl,-rpath,{CAPCUT_FRAMEWORKS}",
        "-Wl,-undefined,dynamic_lookup",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    DECRYPT_HELPER_BIN.chmod(0o755)
    return DECRYPT_HELPER_BIN


def try_decrypt_draft_file(src: Path) -> str | None:
    """尝试解密 draft_info.json，成功返回明文 JSON 字符串。"""
    helper = _ensure_decrypt_helper()
    if helper is None:
        return None

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        out_path = Path(tmp.name)

    try:
        proc = subprocess.run(
            [str(helper), str(src), str(out_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0 or not out_path.exists():
            return None
        text = out_path.read_text(encoding="utf-8")
        if is_encrypted_draft_text(text):
            return None
        return text
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        out_path.unlink(missing_ok=True)


def load_draft_info_json(path: Path, *, allow_decrypt: bool = True) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    if not is_encrypted_draft_text(text):
        return json.loads(text)

    if not allow_decrypt:
        raise ValueError(f"draft_info.json 已加密，无法读取: {path}")

    decrypted = try_decrypt_draft_file(path)
    if decrypted is not None:
        return json.loads(decrypted)

    raise ValueError(
        f"draft_info.json 已加密，当前环境无法自动解密: {path}\n"
        "剪映 6.0+ 在 App 内保存后会加密草稿。可选方案：\n"
        "  1. 使用未在剪映里二次保存的明文草稿（jyconvert 生成的草稿）\n"
        "  2. 在 Windows 上用 jy-draftc 解密后，用 --draft-info 传入明文 JSON\n"
        "  3. 安装 CapCut 并确保 draft_decrypt_helper 可编译运行（macOS 实验性）"
    )
