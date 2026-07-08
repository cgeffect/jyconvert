# jyconvert

NGLEngine 素材包 → 剪映草稿。Electron 桌面工具 + **内嵌 Python 后端**。

## 目录结构

```
jyconvert/
├── build.sh          一键打包 App
├── downloader/       视频下载模块（yt-dlp，与草稿转换独立）
├── electron/         主进程（调 Python）
├── renderer/         界面
├── python/           Python 后端源码
├── bin/              内嵌可执行程序（build 产物：jyconvert-py、yt-dlp）
└── examples/         示例素材包（开发用）
```

> 草稿输出由 `--output-dir` 指定（如 zip 所在目录），不在仓库内。

---

## 开发与运行

```bash
cd jyconvert
npm install
npm run build:python   # 打包 Python → bin/jyconvert-py
npm start              # Electron 优先用内嵌二进制
```

| 命令 | 说明 |
|------|------|
| `npm install` | 安装 Electron 依赖 |
| `npm run build:python` | PyInstaller 打包 Python 后端到 `bin/jyconvert-py` |
| `npm run build:ytdlp` | PyInstaller 打包 yt-dlp 到 `bin/yt-dlp`（不依赖系统安装） |
| `npm start` | 启动桌面应用（自动确保内嵌二进制就绪） |

---

## 打包 App

```bash
cd jyconvert
chmod +x build.sh
./build.sh
```

一条命令完成：npm install → 打包 Python → 打包 yt-dlp → 打 Mac App。

### 产物在哪

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

## Python 内嵌原理

| 环境 | Electron 调用方式 |
|------|-------------------|
| 已打包 `bin/jyconvert-py` | 直接执行内嵌二进制 |
| 开发未打包 | 回退 `python3 python/cli.py` |

CLI 子命令：

```bash
jyconvert-py convert --protocol ... --resource-root ... --name ... --output-dir ...
jyconvert-py import --draft-dir ... --jianying-name ...
```

---

## 桌面流程

1. 选择 Chrome 下载的素材包 zip
2. 内嵌 Python 转换 → 剪映草稿（输出在 zip 所在目录）
3. 内嵌 Python 导入 → 剪映 Pro

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

## 剪映草稿格式说明

见 [docs/jianying-draft.md](docs/jianying-draft.md)：剪映 6.0+ 加密与 jyconvert 明文写入的关系。
