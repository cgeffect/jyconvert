"""PyInstaller 入口：打包为 bin/yt-dlp 独立可执行文件。"""

from yt_dlp import main

raise SystemExit(main())
