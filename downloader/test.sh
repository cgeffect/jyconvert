#!/usr/bin/env bash
# 本地快速测试 downloader 模块
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [ ! -x "$ROOT/../bin/yt-dlp" ]; then
  echo "==> 构建内嵌 yt-dlp"
  bash "$ROOT/../scripts/fetch-ytdlp.sh"
fi

export YTDLP_PATH="$ROOT/../bin/yt-dlp"

if [ ! -d ".venv" ]; then
  echo "==> 创建 venv（仅用于运行 cli.py）"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> URL 提取测试"
python3 tests/test_extract.py -v

echo ""
echo "==> 分享文案提取"
python3 cli.py extract '9.28 复制打开抖音... https://v.douyin.com/wi_0Wcyj-l4/ ipq:/ :4pm'
python3 cli.py extract '6.43 ytr:/ ... https://v.douyin.com/yQbK5iC3VwM/ 复制此链接'

echo ""
echo "==> 抖音 probe（需 Chrome 已登录 douyin.com）"
set +e
python3 cli.py probe 'https://v.douyin.com/wi_0Wcyj-l4/'
PROBE_CODE=$?
set -e
if [ "$PROBE_CODE" -ne 0 ]; then
  echo "（probe 失败通常是因为 Cookie 未就绪，请在 Chrome 登录 douyin.com 后重试）"
fi

echo ""
echo "完成。下载示例:"
echo "  python3 cli.py download '分享文案或 URL' -o output/"
