# 排查手册

## 1. 正文定位不准

`pick_content()` 的判定顺序：

1. 命令行 `--selector`（最高优先级）
2. 常见正文 class：`vp-doc` / `markdown-body` / `article-content` / `post-content` / `entry-content` / `rich_media_content` / `article-body` / `content-body`，命中多个时取**后代最少**的那个
3. 在 `article / main / div` 中找「含 h1 或 h2 且纯文本 > 400 字」的最紧凑容器
4. 兜底 `soup.body`

**表现**：抓出来内容极少（只剩标题）、或混进大量导航/推荐位。

**处理**：

```bash
# 先看页面结构，找正文容器的 class 或 id
curl -sL "<url>" | grep -oE '<(div|article|main)[^>]*class="[^"]*"' | head -30

# 用选择器重跑
<python> scripts/webpage_to_word.py "<url>" --selector "article.post-content" --out "<dir>"
```

若站点用的是 CSS Module / 哈希类名（如 `class="content_a1b2c"`），用属性子串选择器：
`--selector '[class*="content_"]'`。

## 2. 图片缺失

脚本按以下顺序取图片真实地址（`IMG_ATTRS`）：

```
src → data-src → data-original → data-lazy-src → data-actualsrc → data-echo → data-url → data-original-src
```

都取不到时回退 `srcset` / `data-srcset` 的最后一项（通常是最大尺寸）。
`data:image/gif` 开头的 1px 占位图会被跳过。

**排查步骤**：

1. 看脚本输出的「配图 N 张」。0 张 → 说明图片是 JS 动态插入的（`<img>` 在原始 HTML 里不存在）。
2. 有图但明显偏少 → 先加 `--keep-all-images`，排除被 `SKIP_IMG_KEYWORDS`（`favicon` / `sprite`）误杀。
3. 仍有缺失 → 用 `--dump-json` 导出结构，检查 `image` 块的位置和 URL 是否正常。
4. 图片 URL 正常但下载失败 → 大概率是**防盗链**（服务器检查 `Referer`）。在 `download_image()` 里加：

   ```python
   r = SESSION.get(url, timeout=60, headers={"Referer": page_url})
   ```

   或在 `HTTP_HEADERS` 里全局加 `Referer`。

## 3. 抓不到内容（空白 / 反爬）

- **JS 渲染**（SPA、Next.js 客户端渲染）：原始 HTML 里没有正文。需要浏览器渲染才能拿到内容，此时不要反复重试脚本。
- **反爬拦截**：返回 403/503 或验证页。可换 `User-Agent`、降低频率；不要用脚本去猜验证码或绕过风控。
- **需要登录**：脚本不带 Cookie。让用户手动保存页面 HTML 后落盘，再改走「解析本地 HTML」的路径（`parse_page()` 只依赖 HTML 字符串，可离线调用）。

## 4. 排版微调

改脚本顶部的常量即可，全部集中在「① 可调参数」区：

| 常量 | 作用 |
|---|---|
| `FONT_EA` / `FONT_ASCII` | 中/西文字体 |
| `BODY_SIZE` | 正文字号（磅） |
| `COLOR_ACCENT` 等 | 主题色 |
| `MAX_IMG_IN` | 图片最大宽度（英寸），或用 `--img-width` |
| `IMAGE_NAME_MAP` | 给图片指定语义化文件名，键是原始文件名、值是不带扩展名的新名字 |
| `CONTENT_HINTS` | 追加站点自己的正文容器 class |
| `PREFIX_HINTS` | 图片文件名前缀，如某站点目录叫 `tutorial/` 想用 `tut-` 前缀就在这里加 |
| `TIP_CLASS` | 提示框容器的 class 关键词 |

## 5. 已知陷阱

- **嵌套列表被静默丢弃**（已修复，勿回退）：`<li>` 里再套 `<ul>`/`<ol>` 时，内层列表项会以 `listitem` 类型出现在外层列表项的 `blocks` 里。`render_blocks()` 必须显式处理 `listitem`（转交 `render_lists_and_rest()`），否则内层文字**连同里面的配图一起消失**。实测一个 FAQ 页面因此丢了 4 张图、92 个段落。修改渲染逻辑后务必比对「解析到 / 插入」图片数是否相等。
- **跨节列表编号累加**：解析时必须按每个 `<ol>` 重置计数，`<ol start="n">` 要读 `start` 属性，否则第二段列表会接着第一段继续编号。
- **列表里的配图**：很多文档站把步骤配图放在 `</ol>` 之后，必须靠 `normalize()` 把它们归位到前面的列表项，否则图片会全部堆在列表末尾。
- **行内标签碎片化**：`<strong>` / `<a>` / `<code>` 要并入段落缓冲，随最近的块级边界一起输出，否则同一句话会被拆成多个段落。
- **Word 列表自动续号**：步骤用「加粗编号 + 悬挂缩进」的普通段落实现，而非 Word 原生列表，避免打开后编号从上一段接着续。
- **docx 内图片资源数可能小于插入数**：python-docx 按字节哈希去重，同一张图被引用多次时只存一份，这不是丢图。
- **Windows 路径**：`--out` 传含空格或中文的路径时务必加引号；`rm -rf` 配合 `$TEMP` 可能被 safe-delete 策略拦截，用完整正斜杠路径。
