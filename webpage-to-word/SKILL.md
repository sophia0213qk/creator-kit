---
name: webpage-to-word
version: 1.0.0
display_name: 网页转 Word 文档
display_name_zh: 网页转 Word 文档
display_name_en: Webpage to Word
description_zh: 抓取 1~N 个网页的正文、配图与链接，按原文顺序整理成一份本地 Word（.docx）文档并保存到本地目录。适用于「网页转 word」「把链接内容整理成文档」「爬取页面合并成一个文档」等场景。
description_en: Fetch one or more web pages, extract their body text, images and links, and compile them in original order into a well-formatted local Word (.docx) document saved to a local directory.
description: 抓取 1~N 个网页的正文、配图与链接，按原文顺序整理成一份本地 Word（.docx）文档并保存到本地目录。当用户给出一个或多个网页链接，希望「把链接内容整理成 Word / 文档 / 保存下来」「网页转 word」「爬取这些页面合并成一个文档」「把这几篇文档下载下来」时使用。支持单篇、多篇合并、任意数量链接。不涉及云端上传（飞书、ima、腾讯文档、云盘等）。
agent_created: true
---

# 网页 → Word 文档

## 用途

把任意数量的网页（1 篇、2 篇或更多）抓取下来，按原文顺序还原结构（标题 / 段落 / 有序无序列表 / 配图 / 超链接 / 提示框 / 表格 / 代码块），渲染成一份排版好的本地 `.docx`：图片全部内嵌、超链接可点、离线可看。

**边界**：只产出本地文件。不处理上传到飞书 / ima / 腾讯文档 / 云盘等云端动作——用户要上传时另走对应技能或连接器。

## 使用方法

### 1. 确认三件事

| 项目 | 处理方式 |
|---|---|
| 链接 | 用户给几个就抓几个，顺序即章节顺序，不必是 2 个 |
| 输出目录 | 用户指定就用指定的；没指定则放到当前工作目录，并在回复里说明落盘路径 |
| 文档标题 | 用户指定就用 `--title`；没指定则由脚本按第一篇标题自动生成 |

### 2. 安装依赖（只需一次）

```bash
<python> -m pip install requests beautifulsoup4 python-docx Pillow
```

在 WorkBuddy 环境中优先使用托管解释器；若已有 venv 装过这几个包，直接复用。

> **Pillow 建议装**：站点常把 WebP 图按 `.png` 命名返回，python-docx 不认 WebP 会直接抛 `UnrecognizedImageError` 中断整个文档。脚本已内置兜底——`build_assets` 用 Pillow 把这类图**无损转成 PNG**；没装 Pillow 时退化为跳过该图并在汇总里告警（不会崩）。

### 3. 运行脚本

脚本位于 `scripts/webpage_to_word.py`，**必须用绝对路径调用**：

```bash
<python> "<skill_dir>/scripts/webpage_to_word.py" <url1> [<url2> ...] --out "<输出目录>"
```

多篇合并的完整示例：

```bash
<python> "<skill_dir>/scripts/webpage_to_word.py" \
  "https://example.com/p1" \
  "https://example.com/p2" \
  "https://example.com/p3" \
  --title "XX 使用手册" --out "D:/文档" --page-break --toc
```

常用选项：

| 选项 | 作用 |
|---|---|
| `--out DIR` | 输出目录，默认当前目录 |
| `--name NAME` | 输出文件名（不含扩展名） |
| `--title TITLE` | 文档主标题 |
| `--selector CSS` | 正文容器选择器，自动识别正文失败时用 |
| `--page-break` | 每篇之间插分页符（多篇合并时更整齐） |
| `--toc` | 开头插目录 |
| `--img-width N` | 图片最大宽度（英寸，默认 5.6） |
| `--no-images` | 不下图片 |
| `--no-links` | 不生成附录链接清单 |
| `--no-sources` | 不添加来源链接（封面来源清单 + 每章标题下的「原文链接」行） |
| `--keep-all-images` | 不跳过 logo / favicon 等装饰图 |
| `--work DIR` | 中间产物（HTML / 图片缓存 / JSON）目录 |
| `--dump-json` | 导出解析后的结构化 JSON，便于二次加工 |

### 4. 校验并交付

脚本结束时会自校验并打印汇总，重点是这一行：

```
图片：解析到 30 张 ｜ 插入 30 张 ｜ docx 内图片资源 30 个
```

- **解析到 / 插入** 两个数应当相等。若「插入」小于「解析到」，脚本会额外列出漏掉的 URL，按「排查」处理，**不要直接交付**。
- **docx 内图片资源** 允许小于「插入」：python-docx 对字节完全相同的图片只存一份，同一张图被引用多次时这个数会偏小，属正常。
- 「解析到 0 张」也会告警：可能图片是 JS 动态渲染，或被装饰图黑名单误杀（试 `--keep-all-images`）。

确认无误后，用 `present_files` 把 `.docx` 交给用户，并在回复里写明**完整落盘路径**、篇数、配图数三个关键信息。

## 脚本内部流程

```
fetch（3 次重试 + 编码自愈）
  → parse_page（定位正文容器 → 遍历产出线性 blocks → 连续重复段落去重）
  → normalize（把 </ol> 之后紧跟的配图归位到对应列表项；剥掉顶层 h1）
  → download_all_images（按 URL 去重缓存，已存在则跳过）
  → build_assets（重命名为 <前缀>-<序号>-<语义名>.png，前缀取自 URL 关键词）
  → build_docx（封面 → 各篇一级标题章节 → 附录链接表）
  → zipfile 自校验
```

块类型：`heading / p / pinline / listitem / image / code / table / tip`。要扩展时，改 `blocks_from_children`（产出）和 `render_blocks`（消费）两处即可。

## 排查

详见 `references/troubleshooting.md`。常见三类问题速查：

| 现象 | 处理 |
|---|---|
| 正文抓成了整页导航或只有十几个字 | 用 `--selector` 显式指定正文容器。先用浏览器或 `curl` 看一眼目标容器 class，再传选择器 |
| 图片数为 0 或远少于预期 | 站点用懒加载或 `data-*` 属性。脚本已覆盖 `data-src / data-original / data-lazy-src / data-actualsrc / srcset`；仍抓不到就用 `--keep-all-images` 排除被关键字误杀，再确认是否为 JS 动态渲染 |
| 抓不到内容（返回空白 / 反爬） | 内容由 JS 渲染或需要登录。此时改为提示用户提供可访问的静态页面或已保存的 HTML，不要反复重试 |
| 构建 docx 时报 `UnrecognizedImageError`（错误信息可能为空） | 有图片真实格式是 WebP/AVIF 等 python-docx 不支持的格式（常见于 URL 以 `.png` 结尾但内容是 WebP）。先 `pip install Pillow`；脚本会自动转码，转不了的会在汇总里列为跳过项 |
| 汇总里「插入」小于「解析到」，但脚本没列漏图 | 极少数深层嵌套（如提示框内再套列表项）已修复；若再现，用 `walk_blocks` 输出每个 image 的**嵌套路径**定位，再对照 `_tip_block` / `render_lists_and_rest` 的分支 |
| 文档体积过大（上百 MB） | 大图按原始字节内嵌。若不是必须要原图，可先用 Pillow 等比压缩；单张超大动图（GIF）常是体积主因 |

## 资源

- `scripts/webpage_to_word.py` —— 完整流水线，单文件，无外部配置依赖
- `references/troubleshooting.md` —— 正文定位、懒加载、反爬、排版微调的排查手册
