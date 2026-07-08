# jyconvert 编译说明

本文档面向开发者：如何从源码本地运行、打包 Mac / Windows 安装包，以及通过 GitHub Actions 发版。

功能介绍与用户使用说明见 [README.md](README.md)。

---

## 环境要求

| 依赖 | 版本建议 |
|------|----------|
| Node.js | 20+ |
| Python | 3.12+ |
| npm | 随 Node 安装 |
| macOS 打包 | 必须在 macOS 上执行 |
| Windows 打包 | 必须在 Windows 上执行（Git Bash 或 MSYS2） |

---

## 目录结构

```
jyconvert/
├── build-mac.sh          一键打包 macOS
├── build-win.sh          一键打包 Windows
├── electron/             Electron 主进程
├── renderer/             界面
├── python/               协议转换、剪映导入
├── downloader/           抖音下载（yt-dlp）
├── scripts/              构建辅助脚本
└── bin/                  打包产物（gitignore，本地生成）
```

---

## 本地开发

```bash
cd jyconvert
npm install
npm start
```

`npm start` 会自动构建内嵌的 yt-dlp、ffmpeg（首次稍慢），然后启动 Electron。

| 命令 | 说明 |
|------|------|
| `npm start` | 开发模式启动 |
| `npm run build:python` | 打包 Python 后端 → `bin/jyconvert-py` |
| `npm run build:ytdlp` | 打包 yt-dlp |
| `npm run build:ffmpeg` | 复制内嵌 ffmpeg → `bin/ffmpeg` |
| `npm run test:python` | 运行 Python 单元测试 |

---

## 打包 macOS App

```bash
chmod +x build-mac.sh
./build-mac.sh
```

产物位于 `dist/`：

| 文件 | 说明 |
|------|------|
| `dist/mac-arm64/jyconvert.app` | 可直接运行 |
| `dist/jyconvert-x.y.z-arm64.dmg` | 分发用安装镜像 |
| `dist/jyconvert-x.y.z-arm64-mac.zip` | 压缩包 |

分步打包：

```bash
npm run build:python
npm run build:ytdlp
npm run build:ffmpeg
npx electron-builder --mac --publish never
```

---

## 打包 Windows App

在 Windows 上（Git Bash）：

```bash
chmod +x build-win.sh
./build-win.sh
```

产物位于 `dist/`：

| 文件 | 说明 |
|------|------|
| `dist/win-unpacked/jyconvert.exe` | 解压版 |
| `dist/jyconvert-x.y.z-win-x64.exe` | NSIS 安装包 |
| `dist/jyconvert-x.y.z-win-x64.zip` | 压缩包 |

---

## 跨平台说明

Mac 与 Windows 的安装包**不能互换**。PyInstaller 二进制和 Electron 产物都是平台相关的，需在对应系统上分别打包。

`npm run build:python` 等命令会通过 `scripts/select-build.sh` 自动选择 `build-mac.sh` 或 `build-win.sh`。

---

## GitHub Actions 自动发版

推送 `v*` 标签后，`.github/workflows/release.yml` 会在 Mac / Windows 上并行构建，并上传到 [GitHub Releases](https://github.com/cgeffect/jyconvert/releases)。

```bash
# 1. 更新 package.json 中的 version
# 2. 提交并打标签
git add package.json package-lock.json
git commit -m "chore: bump version to 0.2.0"
git tag v0.2.0
git push origin master
git push origin v0.2.0
```

构建使用 `--publish never`，由 workflow 的 `softprops/action-gh-release` 上传产物，不依赖 `GH_TOKEN` 在 electron-builder 阶段发布。

手动发版：

```bash
./build-mac.sh
gh release create v0.1.0 dist/jyconvert-0.1.0-arm64.dmg \
  --title "v0.1.0" \
  --notes "说明文字"
```

---

## CLI（不经过 Electron）

```bash
python3 python/cli.py convert \
  --protocol examples/converted_protocol/converted_protocol.json \
  --resource-root examples/converted_protocol \
  --name my_draft \
  --output-dir ~/Downloads

python3 python/cli.py import \
  --draft-dir ~/Downloads/my_draft \
  --jianying-name my_draft \
  --jianying-drafts-root "~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft"
```

打包后的内嵌二进制：

```bash
bin/jyconvert-py convert --protocol ... --resource-root ... --name ... --output-dir ...
bin/jyconvert-py import --draft-dir ... --jianying-name ... --jianying-drafts-root ...
```

---

## 内嵌依赖原理

| 组件 | 构建方式 | 运行时路径 |
|------|----------|------------|
| Python 后端 | PyInstaller `python/jyconvert.spec` | `Resources/jyconvert-py` |
| yt-dlp | PyInstaller `downloader/ytdlp.spec` | `Resources/yt-dlp.app/` |
| ffmpeg | `@ffmpeg-installer/ffmpeg` | `Resources/ffmpeg` |

Electron 通过 `electron/lib/runner.js` 调用内嵌 Python；开发模式下回退到 `python3 python/cli.py`。

---

## 相关文档

- [README.md](README.md) — 功能与使用说明
- [docs/jianying-draft.md](docs/jianying-draft.md) — 剪映 6.0+ 草稿加密说明
