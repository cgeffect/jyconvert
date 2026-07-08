# downloader

独立于剪映草稿转换的视频下载模块，基于 [yt-dlp](https://github.com/yt-dlp/yt-dlp)。

## 功能

- 从抖音手机/网页分享文案中自动提取 `v.douyin.com` 短链
- 调用 yt-dlp 下载视频（默认从 Chrome 读取 Cookie，提高抖音成功率）
- 提供 CLI 供本地测试，后续由 Electron 子窗口调用

## 内嵌 yt-dlp

Electron 不依赖系统安装的 yt-dlp。构建时会将 yt-dlp 打成独立二进制：

```bash
# 单独打包 yt-dlp → jyconvert/bin/yt-dlp
bash scripts/fetch-ytdlp.sh
# 或
npm run build:ytdlp
```

`npm start` / `./build.sh` 会自动确保 `bin/yt-dlp` 存在，并随 Electron `extraResources` 打入 `.app`。

## 本地测试

```bash
cd jyconvert/downloader

# 先确保内嵌二进制（在 jyconvert 根目录执行）
cd .. && npm run build:ytdlp && cd downloader

# 单元测试：URL 提取
python3 tests/test_extract.py

# 从分享文案提取链接
python3 cli.py extract '9.28 复制打开抖音... https://v.douyin.com/wi_0Wcyj-l4/ ...'

# 探测 / 下载（使用 bin/yt-dlp，非系统 PATH）
python3 cli.py probe 'https://v.douyin.com/wi_0Wcyj-l4/'
python3 cli.py download '整段分享文案或 URL' -o output/
```

开发时 `resolve_ytdlp()` 查找顺序：

1. 环境变量 `YTDLP_PATH`（Electron 注入）
2. `jyconvert/bin/yt-dlp`（内嵌二进制）
3. `downloader/.venv/bin/yt-dlp`（仅本地 pip 开发）

不会使用系统 PATH 中的 yt-dlp（除非设 `ALLOW_SYSTEM_YTDLP=1`）。

### 抖音 Cookie

抖音常需要登录态。默认 `--cookies-browser chrome` 从 Chrome 读取 Cookie。

- 请先在 Chrome 登录 douyin.com
- macOS 可能弹出钥匙串授权
- 禁用 Cookie：`--cookies-browser none`

## 目录

```
downloader/
├── cli.py              本地测试入口
├── requirements.txt
├── lib/
│   ├── extract.py      分享文案 → URL
│   └── download.py     yt-dlp 下载封装
└── tests/
    └── test_extract.py
```

## Electron 接入（待做）

主窗口增加「视频下载」按钮 → 打开子窗口 → IPC 调用本模块。
