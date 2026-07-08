#!/usr/bin/env bash
# 按当前系统选择 build-mac.sh 或 build-win.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)
    SCRIPT="$ROOT/build-win.sh"
    ;;
  *)
    SCRIPT="$ROOT/build-mac.sh"
    ;;
esac

exec bash "$SCRIPT" "$@"
