# 剪映草稿加密与 jyconvert 写入原理

## 一句话

**剪映 6.0+ 会加密「自己在 App 里保存过的草稿」；jyconvert 写入的是「外部生成的明文 JSON」，剪映可以打开，但不要在剪映里再保存回去。**

---

## 剪映里两种草稿

| 来源 | `draft_info.json` 形态 | 剪映能否打开 |
|------|-------------------------|--------------|
| 在剪映里创建 / 编辑 / 保存 | **加密**（乱码，非 JSON） | 可以 |
| 外部工具生成（jyconvert、扣子插件等） | **明文 JSON** | 可以 |

你在 Finder 里对比就能看到：

- `7月7日/draft_info.json` → 加密，开头像 `gbDCLnhHb3eF...`
- `converted_protocol_draft/draft_info.json` → 明文，开头是 `{ "canvas_config": ...`

---

## 「加密」到底加密了什么？

- **macOS 剪映**：主要加密 `draft_info.json`（时间轴、轨道、素材引用）以及 `draft_meta_info.json` 等。
- **Windows 剪映**：对应文件多为 `draft_content.json`（概念相同）。

加密发生在 **剪映客户端保存时**，没有对外公开的「导入明文」开关。  
一旦在剪映 6.0+ 里打开外部草稿并 **再次保存（Cmd+S）**，文件会被重新加密，之后命令行/脚本就很难再改。

因此社区共识是：**生成 → 交给剪映播放/导出，不要在剪映里二次编辑再存。**

---

## jyconvert 是怎么写进去的？

jyconvert **不破解、不解密** 剪映格式，而是 **按剪映能识别的目录结构，直接写出一份新的明文草稿**：

```
本地草稿目录/
├── draft_info.json          ← 明文：轨道、片段、素材路径
├── draft_meta_info.json
├── draft_cover.jpg          ← 封面（剪映 10.x 强烈依赖）
├── Timelines/{id}/draft_info.json
├── Resources/imported/      ← 复制的视频、音频、图片
├── Resources/fonts/
└── …（scaffold 辅助文件）
```

流程：

1. **转换**：NGLEngine 协议 JSON → 生成上述目录（`python/jianying/convert_lib.py`）
2. **导入**：复制到剪映草稿根目录，并注册到 `root_meta_info.json`（`python/jianying/import_draft.py`）

剪映启动时扫描 `~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft/`，发现新文件夹 + `root_meta_info` 里有登记，就会出现在草稿列表里。

---

## 为什么有时打开是空的？

常见原因（与「加密」无关）：

| 问题 | 原因 |
|------|------|
| 没有视频/音频，只有文字 | 素材路径错误，或 zip 解压目录被转换步骤删掉 |
| 剪映里显示空时间线 | 缺少 `draft_cover.jpg`，或 `Timelines/` 与 `draft_info.json` 不一致 |
| 打开了错误的草稿 | 列表里是 `7月7日`，实际导入的是 `converted_protocol_draft` |
| 导入后媒体丢失 | 导入时 JSON 里的绝对路径未改到剪映目录（已在 `rewrite_draft_paths` 修复） |

---

## 和 CapCut 的关系

- **CapCut 国际版**：草稿长期为 **明文 JSON**，第三方工具生态更成熟。
- **剪映国内版**：6.0+ **读** 自己的草稿要解密；**写** 明文草稿仍被支持（与扣子等插件相同路线）。
- jyconvert 的 `protocol/converter.py` 同时服务 CapCut / 剪映，剪映会额外设置 `platform.app_source = "lv"` 并生成 `Timelines/` 结构。

---

## 使用建议

1. 用 jyconvert **生成并导入** 后，在剪映里 **预览、导出**，尽量避免在剪映里大改再保存。
2. 若必须在剪映里长期编辑，应把该草稿当作「终点」，不要指望再导回 NGLEngine 协议。
3. 开发调试时，用 **明文草稿**（`converted_protocol_draft`）对比 **加密草稿**（`7月7日`），不要混为同一个文件。

---

## 参考

- [pyJianYingDraft](https://github.com/GuanYixuan/pyJianYingDraft)：说明 6+ 加密，5.9 及以下为明文。
- [JianYing 6.0+ encryption gist](https://gist.github.com/renezander030/521e6c6e8590a2a6e917009d9313bc55)：检测与工作区说明（降级 5.9 或走 CapCut）。
