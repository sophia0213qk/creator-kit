---
name: wechat-article-fetch
version: 1.0.0
display_name: 微信公众号文章批量落盘
display_name_en: WeChat Article Batch Fetch
description: >-
  用 curl 伪装浏览器抓取微信公众号文章，管道正则抽出 js_content，支持单篇/批量落盘为 md（默认）或 txt/html 等自定义格式。
  当用户给出 mp.weixin.qq.com 链接要下载、保存、批量导出公众号正文时使用。

description_zh: >-
  用 curl 抓取微信公众号文章并落盘：管道正则提取 js_content，
  默认保存为 Markdown，也可输出 txt/html；支持单篇与批量。

description_en: >-
  Fetch WeChat Official Account articles with curl, extract js_content via a
  pipe regex, and save locally as Markdown by default (or txt/html). Supports
  single and batch URLs.
---

# 微信公众号文章批量落盘

把一篇或多篇微信公众号文章**抓下来存成本地文件**。抓取只用 **curl**，正文用管道里的一行 Python 正则从 `js_content` 抠出——**不要**用 Python/`urllib`/`requests` 发 HTTP，**不要**用 `web_fetch`。

和「只读正文做摘要」不同：本技能默认**落盘**；用户要总结时，先落盘或先抽出正文再总结。

## 硬规则

1. 链接须含 `mp.weixin.qq.com/s`
2. 抓取命令必须是下面的 **curl 管道**（可改输出重定向与批量循环，不可改成 Python 联网）
3. 默认保存为 **`.md`**；用户指定格式再改扩展名/稍作包装
4. Windows 上 Python 命令用 `python`（或 `py`）；Linux/macOS 用 `python3`

## 核心命令（唯一抓取方式）

把 `"微信文章链接"` 换成真实 URL：

```bash
curl -s -L \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" \
  -H "Referer: https://mp.weixin.qq.com/" \
  "微信文章链接" | python3 -c "
import sys, re
html = sys.stdin.read()
m = re.search(r'id=\"js_content\"[^>]*>(.*?)</div>\s*<script', html, re.DOTALL)
if m:
    print(re.sub(r'<[^>]+>', '\n', m.group(1)).strip())
"
```

参数含义：`-s` 静默，`-L` 跟随跳转；UA / Referer 用来伪装浏览器。

## 单篇保存

用户指定输出目录则用指定目录，否则当前工作目录。文件名可用标题关键词或 `文章-1.md`；不确定标题时先抽出正文，再用首行或链接短码命名。

**存为 md（默认）**——正文前加标题行与原文链接：

```bash
URL="https://mp.weixin.qq.com/s/xxxx"
OUT_DIR="."
BODY=$(curl -s -L \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" \
  -H "Referer: https://mp.weixin.qq.com/" \
  "$URL" | python3 -c "
import sys, re
html = sys.stdin.read()
m = re.search(r'id=\"js_content\"[^>]*>(.*?)</div>\s*<script', html, re.DOTALL)
if m:
    print(re.sub(r'<[^>]+>', '\n', m.group(1)).strip())
")
# 将正文写入 md；标题可用用户给的，或暂用「微信文章」
printf '%s\n\n原文：%s\n\n%s\n' "# 微信文章" "$URL" "$BODY" > "$OUT_DIR/微信文章.md"
```

**只要纯文本 `.txt`**：同样管道，结果重定向到 `.txt`，不必加 Markdown 标题。

**要 `.html`**：curl 整页另存（仍用同一组 Header），例如  
`curl -s -L -H "User-Agent: ..." -H "Referer: https://mp.weixin.qq.com/" "$URL" -o article.html`  
（整页 HTML，不是只抽 js_content。）

## 批量

1. 收集全部 `mp.weixin.qq.com/s` 链接（参数、粘贴列表、或文本文件每行一个，`#` 注释可跳过）
2. **逐条**跑上面的 curl 管道，写入 `OUT_DIR/01-短名.md`、`02-短名.md`…
3. 篇与篇之间 `sleep 1`（或约 1～2 秒），不要并发狂扫
4. 单篇失败：记下 URL 与原因，继续下一篇；最后汇报成功/失败数与文件路径

Bash 示意：

```bash
OUT_DIR="./wechat-out"
mkdir -p "$OUT_DIR"
i=0
while read -r URL; do
  [[ -z "$URL" || "$URL" == \#* ]] && continue
  i=$((i+1))
  BODY=$(curl -s -L \
    -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" \
    -H "Referer: https://mp.weixin.qq.com/" \
    "$URL" | python3 -c "
import sys, re
html = sys.stdin.read()
m = re.search(r'id=\"js_content\"[^>]*>(.*?)</div>\s*<script', html, re.DOTALL)
if m:
    print(re.sub(r'<[^>]+>', '\n', m.group(1)).strip())
")
  printf '%s\n\n原文：%s\n\n%s\n' "# 文章 $i" "$URL" "$BODY" > "$OUT_DIR/$(printf '%02d' $i).md"
  sleep 1
done <<'URLS'
https://mp.weixin.qq.com/s/aaaa
https://mp.weixin.qq.com/s/bbbb
URLS
```

PowerShell 同样：**curl.exe** + 同一组 Header，管道给 `python -c "..."`（把 `python3` 换成 `python`），循环写文件并 `Start-Sleep -Seconds 1`。

## 交付

- 写清输出目录与每个成功文件的路径
- 失败常见原因：网络失败、页面无 `js_content`（结构变了或验证码）、非文章链接
- 抽出的是去标签纯文本；图片一般只剩空白换行，需要图时另说

## 不要做的事

- 不要用 `web_fetch` / Python 请求库抓微信链接
- 不要写成独立「爬虫框架」或本地 HTTP 客户端脚本替代 curl
- 不要用于非 `mp.weixin.qq.com` 链接（其它网页走别的技能）

