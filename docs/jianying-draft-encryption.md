# 剪映草稿加密与 jyconvert 写入原理

## 剪映草稿是加密的吗？

**分两种情况：**

| 来源 | `draft_info.json` 格式 | 剪映能否打开 |
|------|------------------------|--------------|
| 在剪映里创建/保存的草稿 | **加密**（6.0+ 起） | 可以 |
| 外部工具写入的明文草稿 | **明文 JSON** | 可以（首次导入） |

剪映 Pro **6.0 及以上**会对自己在 App 内保存的草稿核心 JSON 做加密（macOS 上是 `draft_info.json`，Windows 上是 `draft_content.json`）。你在 Finder 里打开原生草稿，文件开头是一串乱码，而不是 `{`。

但这不等于「外部永远不能写入草稿」。

## jyconvert 是怎么写入的？

jyconvert **不破解、不解密**剪映的加密格式，而是 **从零生成一份新的明文草稿**，再复制进剪映目录。

流程简述：

```
Chrome 素材 zip
    ↓ 解压
协议 JSON + assets/
    ↓ Python 转换（protocol/converter.py）
明文 draft_info.json + Timelines/ + Resources/imported/
    ↓ 复制到剪映目录（jianying/import_draft.py）
~/Movies/JianyingPro/.../com.lveditor.draft/<草稿名>/
    ↓
剪映读取明文草稿 → 正常显示轨道与素材
```

### 我们写入了哪些文件？

- `draft_info.json` — 轨道、素材、时间线（**明文 JSON**）
- `Timelines/<id>/draft_info.json` — 剪映 10.x 从此处读轨道
- `draft_meta_info.json` — 草稿元信息
- `Resources/imported/` — 视频、音频、图片、字体
- `draft_cover.jpg` — 封面（剪映 10.x 无封面时可能显示空时间线）
- `templates/jianying_scaffold/` 下的辅助 JSON

模板骨架来自 `python/templates/draft_info.template.json`，不依赖读取你电脑上已有的加密草稿。

### 导入时做了什么？

`import_draft.py` 会：

1. 把本地草稿目录 **整份复制** 到剪映草稿根目录
2. **重写 JSON 内所有绝对路径**（从 Desktop 临时目录改到剪映目录）
3. 在 `root_meta_info.json` 里 **注册** 新草稿

## 和「加密」的关系

可以这样理解：

- **加密**：剪映保护自己产出的草稿，防止第三方随意读取/篡改已保存项目。
- **明文写入**：外部工具（扣子插件、jyconvert 等）按剪映能识别的 JSON 结构 **新建** 草稿；剪映作为「导入方」可以读明文。
- **再次保存**：若在剪映 6.0+ 里打开后 **再次保存**，剪映可能把该草稿 **重新加密**；之后就要用剪映打开，不宜再用脚本改 JSON。

社区共识（参见 [pyJianYingDraft](https://github.com/GuanYixuan/pyJianYingDraft)、[capcut-cli 版本说明](https://github.com/renezander030/capcut-cli/blob/master/docs/version-support.md)）：

- 剪映 **5.9** 及以前：草稿全程明文，工具链最省心。
- 剪映 **6.0+**：读取原生加密草稿很难；**生成**明文草稿给剪映打开仍然可行。
- **CapCut 国际版**：草稿长期保持明文（另一套工具链）。

## jyconvert 实际验证过的环境

- macOS 剪映 Pro（用户环境）：明文导入草稿可正常显示轨道与素材
- 关键条件：素材路径正确、`draft_cover.jpg` 存在、打开的是 **本次导入的草稿名**（不是剪映里旧的同名日期草稿）

## 常见问题

**Q：为什么日志里转换成功，剪映里却是空的？**

常见原因（与加密无关）：

1. 素材 zip 解压目录与草稿输出目录 **同名被覆盖**（已修复：使用 `{zip名}_draft`）
2. 导入后 JSON 路径未改到剪映目录（已修复：`replace_path_prefix`）
3. 缺少 `draft_cover.jpg`（App 内 ffmpeg PATH 问题，已修复）
4. 在剪映里打开了 **错误的草稿**（例如旧的 `7月7日` 而非 `converted_protocol_draft`）

**Q：jyconvert 能编辑剪映里已有的加密草稿吗？**

不能。只能 **协议 zip → 新草稿**；不能打开并修改剪映内已加密保存的旧项目。

---

*文档随 jyconvert 实现更新；若剪映大版本变更 JSON 结构或加密策略，需重新验证。*
