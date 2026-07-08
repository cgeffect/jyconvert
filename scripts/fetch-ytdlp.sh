#!/usr/bin/env bash
# 兼容旧命令：默认走 macOS 脚本
exec bash "$(dirname "$0")/fetch-ytdlp-mac.sh" "$@"
