#!/usr/bin/env bash
# 一键打包 Mac App：Python 内嵌 + Electron .app / .dmg
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

PYTHON_DIR="$ROOT/python"
VENV_DIR="$PYTHON_DIR/.venv"
OUT_BIN="$ROOT/bin/jyconvert-py"

build_ytdlp() {
  bash "$ROOT/scripts/fetch-ytdlp-mac.sh"
}

build_ffmpeg() {
  node "$ROOT/scripts/fetch-ffmpeg.js"
}

build_python() {
  if [ ! -d "$VENV_DIR" ]; then
    echo "==> [1/4] 创建 Python venv"
    python3 -m venv "$VENV_DIR"
  fi

  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"

  echo "==> [2/4] 打包 Python 后端"
  pip install pyinstaller --quiet
  cd "$PYTHON_DIR"
  pyinstaller jyconvert.spec --noconfirm --clean

  mkdir -p "$ROOT/bin"
  cp -f dist/jyconvert-py "$OUT_BIN"
  chmod +x "$OUT_BIN"
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

echo "==> [4/5] 打包 Electron App (macOS)"
npx electron-builder --mac --publish never

echo ""
echo "==> [5/5] 完成"
echo "  App:  $ROOT/dist/mac-arm64/jyconvert.app"
echo "  DMG:  $ROOT/dist/jyconvert-"*"-arm64.dmg"
echo ""
echo "打开: open dist/mac-arm64/jyconvert.app"
