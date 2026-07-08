#!/usr/bin/env bash
# Windows：用 PyInstaller 将 yt-dlp 打包为 jyconvert/bin/yt-dlp.exe（不依赖系统安装）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DL="$ROOT/downloader"
VENV="$DL/.venv-ytdlp"
OUT_DIR="$ROOT/bin/yt-dlp.app"
OUT="$ROOT/bin/yt-dlp.exe"

if [ ! -d "$VENV" ]; then
  echo "==> 创建 yt-dlp 构建 venv"
  python -m venv "$VENV" 2>/dev/null || python3 -m venv "$VENV"
fi

# shellcheck disable=SC1091
source "$VENV/Scripts/activate"

echo "==> 安装 yt-dlp + PyInstaller"
pip install -r "$DL/requirements.txt" pyinstaller --quiet

echo "==> PyInstaller 打包 yt-dlp"
cd "$DL"
pyinstaller ytdlp.spec --noconfirm --clean

mkdir -p "$ROOT/bin"
rm -rf "$OUT_DIR" "$OUT"
cp -R dist/yt-dlp "$OUT_DIR"
cp -f "$OUT_DIR/yt-dlp.exe" "$OUT"

echo "==> 验证"
"$OUT" --version
echo "    → $OUT"
