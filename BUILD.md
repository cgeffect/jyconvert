# jyconvert 编译与开发说明

本文档介绍如何在本地开发、打包 Python 后端，以及构建 Mac / Windows 桌面 App。

功能与使用流程见 [README.md](README.md)。

---

## 跨平台说明

**Mac 打包产物不能在 Windows 上使用**，反之亦然。原因：

- PyInstaller 生成的 `jyconvert-py` / `yt-dlp` 是**平台相关**的可执行文件
- Electron 打包产物也不同：macOS 是 `.app` / `.dmg`，Windows 是 `.exe` / 安装包

| 平台 | 构建脚本 | 需在什么环境运行 |
|------|----------|------------------|
| macOS | `build-mac.sh` | macOS |
| Windows | `build-win.sh` | Windows（Git Bash 或 MSYS2） |

`npm run build:python` / `npm run dist` 会通过 `scripts/select-build.sh` 自动选择对应脚本。

---

## 目录结构

```
jyconvert/
├── build-mac.sh      一键打包 macOS App
├── build-win.sh      一键打包 Windows App
├── downloader/       视频下载模块（yt-dlp，与草稿转换独立）
├── electron/         主进程（调 Python）
├── renderer/         界面
├── python/           Python 后端源码
├── bin/              内嵌可执行程序（build 产物）
└── examples/         示例素材包（开发用）
```

> 草稿输出由 `--output-dir` 指定（如 zip 所在目录），不在仓库内。

---

## 开发与运行

```bash
cd jyconvert
npm install
npm run build:python   # 按当前系统自动打包 Python 后端
npm start              # Electron 优先用内嵌二进制
```

| 命令 | 说明 |
|------|------|
| `npm install` | 安装 Electron 依赖 |
| `npm run build:python` | PyInstaller 打包 Python 后端 |
| `npm run build:ytdlp` | PyInstaller 打包 yt-dlp（不依赖系统安装） |
| `npm run build:ffmpeg` | 复制内嵌 ffmpeg 到 `bin/` |
| `npm start` | 启动桌面应用（`prestart` 会自动确保 yt-dlp、ffmpeg 就绪） |
| `npm run dist:mac` | 完整打包 macOS App |
| `npm run dist:win` | 完整打包 Windows App |

---

## 打包 macOS App

```bash
cd jyconvert
chmod +x build-mac.sh
./build-mac.sh
```

一条命令完成：`npm install` → 打包 Python → 打包 yt-dlp → 内嵌 ffmpeg → 打 Mac App。

也可分步执行：

```bash
npm run build:python   # 仅打包 Python 后端
npm run build:ytdlp    # 仅打包 yt-dlp
npx electron-builder --mac
```

### macOS 产物

打包完成后在 **`jyconvert/dist/`**：

| 文件 | 说明 |
|------|------|
| `dist/mac-arm64/jyconvert.app` | **可直接双击运行的 App** |
| `dist/jyconvert-0.1.0-arm64.dmg` | 安装镜像（拖进 Applications） |
| `dist/jyconvert-0.1.0-arm64-mac.zip` | 压缩包分发 |

打开 App：

```bash
open dist/mac-arm64/jyconvert.app
```

内嵌 Python 在 `jyconvert.app/Contents/Resources/jyconvert-py`。

> 未签名 App 首次打开：右键 → 打开，或在「系统设置 → 隐私与安全性」中允许。

---

## GitHub 自动发版

推送 `v*` 标签后，GitHub Actions 会自动在 Mac / Windows 上打包，并把安装包上传到 [GitHub Releases](https://github.com/cgeffect/jyconvert/releases)。

### 发布新版本

```bash
# 1. 更新 package.json 中的 version（如 0.1.0 → 0.2.0）

# 2. 提交并打标签
git add package.json package-lock.json
git commit -m "chore: bump version to 0.2.0"
git tag v0.2.0
git push origin master
git push origin v0.2.0
```

推送标签后，在仓库 **Actions** 页查看 `Release` workflow。完成后，用户可在 Releases 页面下载：

| 平台 | 产物 |
|------|------|
| macOS (arm64) | `jyconvert-x.y.z-arm64.dmg`、`.zip` |
| Windows | `jyconvert Setup x.y.z.exe`、`.zip` |

### 手动发布（不用 CI）

本地打包后，也可手动上传到 GitHub Releases：

```bash
./build-mac.sh
gh release create v0.1.0 dist/jyconvert-0.1.0-arm64.dmg \
  --title "v0.1.0" \
  --notes "首个 Mac 可下载版本"
```

---

## 打包 Windows App

在 **Windows 机器**上，用 **Git Bash** 或 **MSYS2** 执行：

```bash
cd jyconvert
chmod +x build-win.sh
./build-win.sh
```

前置条件：

- 已安装 [Node.js](https://nodejs.org/)
- 已安装 Python 3（`python` 或 `python3` 可用）
- 使用 Git Bash / MSYS2 运行上述 bash 脚本

### Windows 产物

| 文件 | 说明 |
|------|------|
| `dist/win-unpacked/jyconvert.exe` | 解压版，可直接运行 |
| `dist/jyconvert Setup *.exe` | NSIS 安装包 |
| `dist/jyconvert-*-win.zip` | 压缩包分发 |

内嵌 Python 在 `resources/jyconvert-py.exe`。

导入剪映前，请在 App 第三步配置**剪映草稿目录**（Windows 上通常为 `%LOCALAPPDATA%\\JianyingPro\\User Data\\Projects\\com.lveditor.draft`，也可手动选择）。

---

## Python 内嵌原理

| 环境 | Electron 调用方式 |
|------|-------------------|
| 已打包内嵌二进制 | 直接执行 `bin/jyconvert-py`（Windows 为 `.exe`）、内嵌 `ffmpeg` |
| 开发未打包 | 回退 `python3 python/cli.py` |

CLI 子命令：

```bash
jyconvert-py convert --protocol ... --resource-root ... --name ... --output-dir ...
jyconvert-py import --draft-dir ... --jianying-name ... --jianying-drafts-root ...
```

---

## 开发 CLI（不经过 Electron）

```bash
python3 python/cli.py convert \
  --protocol examples/converted_protocol/converted_protocol.json \
  --resource-root examples/converted_protocol \
  --name my_draft \
  --output-dir ~/Downloads

python3 python/cli.py import \
  --draft-dir ~/Downloads/my_draft \
  --jianying-name my_draft
```

---

## 测试

```bash
npm run test:python
```

---

## 相关文档

- [README.md](README.md) — 功能介绍与使用说明
- [docs/jianying-draft.md](docs/jianying-draft.md) — 剪映 6.0+ 加密与 jyconvert 明文写入的关系
