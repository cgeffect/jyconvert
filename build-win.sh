#!/usr/bin/env bash
# 一键打包 Windows App：Python 内嵌 + Electron 安装包
# 需在 Windows（Git Bash / MSYS2）上运行；Mac 产物无法在 Windows 使用。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

PYTHON_DIR="$ROOT/python"
VENV_DIR="$PYTHON_DIR/.venv"
OUT_BIN="$ROOT/bin/jyconvert-py.exe"

build_ytdlp() {
  bash "$ROOT/scripts/fetch-ytdlp-win.sh"
}

build_ffmpeg() {
  node "$ROOT/scripts/fetch-ffmpeg.js"
}

build_python() {
  if [ ! -d "$VENV_DIR" ]; then
    echo "==> [1/4] 创建 Python venv"
    python -m venv "$VENV_DIR" 2>/dev/null || python3 -m venv "$VENV_DIR"
  fi

  # shellcheck disable=SC1091
  source "$VENV_DIR/Scripts/activate"

  echo "==> [2/4] 打包 Python 后端"
  pip install pyinstaller --quiet
  cd "$PYTHON_DIR"
  pyinstaller jyconvert.spec --noconfirm --clean

  mkdir -p "$ROOT/bin"
  cp -f dist/jyconvert-py.exe "$OUT_BIN"
  cd "$ROOT"
  echo "      → $OUT_BIN"
}

if [[ "${1:-}" == "--python-only" ]]; then
  build_python
  exit 0
fi

if [[ "${1:-}" == "--ytdlp-only" ]]; then
  build_ytdlp
  exit 0
fi

if [[ "${1:-}" == "--ffmpeg-only" ]]; then
  build_ffmpeg
  exit 0
fi

echo "==> [1/5] npm install"
npm install

build_python
build_ytdlp
build_ffmpeg

echo "==> [4/5] 打包 Electron App (Windows)"
npx electron-builder --win --publish never

echo ""
echo "==> [5/5] 完成"
echo "  程序: $ROOT/dist/win-unpacked/jyconvert.exe"
echo "  安装包: $ROOT/dist/jyconvert-"*"-win-x64.exe"
