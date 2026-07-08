# jyconvert

**NGLEngine 素材包 → 剪映草稿**。Mac 桌面工具，内嵌 Python 后端，把 Chrome 项目预览页下载的素材包一键转成剪映 Pro 可打开的草稿。

---

## 能做什么

### 1. 素材包转剪映草稿

把 NGLEngine 协议（`converted_protocol.json` + 媒体资源）转换为剪映 10.x 可识别的草稿目录结构，包括：

- **视频 / 图片 / 音频** 轨道与片段
- **文字** 轨道（含富文本样式）
- **画布** 尺寸、时长、帧率
- **片段属性**：时间范围、音量、可见性、位置缩放等 clip 变换
- **草稿封面**（自动从时间轴或素材生成）
- **剪映 10.x 时间线**（`Timelines/` 目录）

转换后写入本地目录，不直接修改剪映安装路径，便于检查与复用。

### 2. 一键导入剪映 Pro

将本地草稿复制到你配置的剪映草稿目录，并在 `root_meta_info.json` 中注册，剪映草稿列表即可看到。

导入前需在界面中配置**剪映草稿目录**（通常为 `.../com.lveditor.draft`）。Windows 上剪映安装位置不固定，请手动选择；macOS 会自动填入常见默认路径。

### 3. 抖音视频下载（独立模块）

内置「视频下载」窗口，支持：

- 粘贴抖音分享口令或链接（可批量，每行一个）
- 应用内登录抖音（Cookie 持久化，无需每次登录）
- 下载视频到指定目录，并生成对照索引 CSV

该模块与草稿转换流程独立，用于获取素材或配合 NGLEngine 工作流。

---

## 桌面使用流程

打开 App 后，按三步流水线操作：

```
素材包 (.zip)  →  转换草稿  →  导入剪映
```

1. **素材包**：拖入或选择 Chrome 下载的 `.zip` 压缩包（内含协议 JSON 与资源文件）
2. **转换草稿**：填写草稿名称，生成剪映格式草稿（默认输出在 zip 所在目录）
3. **导入剪映**：写入剪映 Pro 草稿目录，完成后可打开文件夹查看

界面右上角「视频下载」可打开独立的抖音下载工具。

---

## 输入与输出

| 项目 | 说明 |
|------|------|
| 输入 | Chrome 项目预览页下载的素材包 `.zip` |
| 协议文件 | 解压后的 `converted_protocol.json`（NGLEngine 协议） |
| 资源目录 | 与协议同级的媒体文件（视频、图片、音频、字体等） |
| 本地草稿输出 | `--output-dir` 指定目录下的 `{草稿名称}/` |
| 剪映草稿位置 | 用户在导入前配置的 `com.lveditor.draft` 目录下的 `{名称}/` |

---

## 协议转换能力

当前转换器（`python/protocol/converter.py`）支持的主要映射：

| NGLEngine | 剪映草稿 |
|-----------|----------|
| `canvas_config` / `width` / `height` | `canvas_config` |
| `duration` / `fps` | 草稿时长与帧率 |
| `materials.videos` | 视频素材 |
| `materials.images` | 图片素材（作为 video 轨道素材） |
| `materials.audios` | 音频素材 |
| `materials.texts` | 文字素材（含样式） |
| `tracks`（video / image / audio / text） | 对应轨道与 `segments` |
| 片段 `clip`（位移、缩放等） | 剪映 `clip` 变换 |
| PAG 动态文字 | 降级为静态文字（并给出警告） |

不支持的素材或缺失引用会在转换日志中输出警告，不会中断整个流程。

---

## 重要提示：剪映加密

jyconvert 写入的是**明文 JSON 草稿**，剪映可以直接打开。

但剪映 6.0+ 在 App 内**再次保存（Cmd+S）**后会加密 `draft_info.json`，加密后外部工具难以再编辑。

**建议**：在剪映中预览、调整导出，尽量不要在剪映里二次保存该草稿。

详见 [docs/jianying-draft.md](docs/jianying-draft.md)。

---

## 系统要求

- **macOS** 或 **Windows**（桌面 App；各平台需单独打包，产物不通用）
- 已安装 **剪映 Pro**（导入前在 App 内配置剪映草稿目录）
- **无需单独安装 ffmpeg**（已内嵌在 App 中，用于从视频截取草稿封面）

---

## 项目结构（概览）

```
jyconvert/
├── electron/         主进程：调 Python、解压 zip、导入剪映、视频下载
├── renderer/         界面：主流水线 + 下载器
├── python/           协议转换与剪映草稿生成
│   ├── protocol/     NGLEngine → draft_info.json
│   └── jianying/     本地草稿组装与导入剪映
├── downloader/       yt-dlp 视频下载
└── examples/         示例素材包（开发调试）
```

---

## 相关文档

- [BUILD.md](BUILD.md) — 本地开发、打包 Python、构建 Mac / Windows App、GitHub 发版
- [docs/jianying-draft.md](docs/jianying-draft.md) — 剪映草稿加密原理
