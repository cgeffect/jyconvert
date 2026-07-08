#!/usr/bin/env bash
# macOS：用 PyInstaller 将 yt-dlp 打包为 jyconvert/bin/yt-dlp（不依赖系统安装）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DL="$ROOT/downloader"
VENV="$DL/.venv-ytdlp"
OUT="$ROOT/bin/yt-dlp"

if [ ! -d "$VENV" ]; then
  echo "==> 创建 yt-dlp 构建 venv"
  python3 -m venv "$VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"

echo "==> 安装 yt-dlp + PyInstaller"
pip install -r "$DL/requirements.txt" pyinstaller --quiet

echo "==> PyInstaller 打包 yt-dlp"
cd "$DL"
pyinstaller ytdlp.spec --noconfirm --clean

mkdir -p "$ROOT/bin"
rm -rf "$ROOT/bin/yt-dlp.app" "$OUT"
cp -R dist/yt-dlp "$ROOT/bin/yt-dlp.app"
ln -sf "yt-dlp.app/yt-dlp" "$OUT"
chmod +x "$OUT" "$ROOT/bin/yt-dlp.app/yt-dlp"

echo "==> 验证"
"$OUT" --version
echo "    → $OUT"
