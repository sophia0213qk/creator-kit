#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
webpage_to_word.py —— 批量抓取网页正文 / 图片 / 链接，整合成一份 Word 文档
===========================================================================

一条命令跑完：抓取 HTML → 按原文顺序解析 → 下载配图 → 渲染 .docx（配图内嵌、可离线看）

链接数量不限：传 1 个就是 1 篇，传 5 个就是 5 篇，按传入顺序合并成一份文档，
每篇一个一级标题章节。

依赖（只需装一次）：
    pip install requests beautifulsoup4 python-docx

用法：
    python webpage_to_word.py <url> [<url> ...] [选项]

示例：
    # 单篇
    python webpage_to_word.py "https://example.com/docs/install" --out ./out

    # 多篇合并（任意数量）
    python webpage_to_word.py "https://a.com/p1" "https://a.com/p2" "https://a.com/p3" \
        --title "XX 使用手册" --out "D:/doc" --page-break

    # 正文没抓对时，用 CSS 选择器指定容器
    python webpage_to_word.py "https://example.com/post" --selector "article.post-content"

    # 只做本地 Word，不下载图片（保留图片位置为空）
    python webpage_to_word.py "https://example.com/post" --no-images

常用选项：
    --out DIR         输出目录（默认当前工作目录）
    --name NAME       输出文件名（不含扩展名，默认取 --title）
    --title TITLE     文档主标题（默认取第一篇的标题）
    --selector CSS    正文容器 CSS 选择器（列表页/复杂站点建议显式指定）
    --work DIR        中间产物目录（HTML / 图片缓存 / JSON，默认系统临时目录）
    --img-width N     图片最大宽度，单位英寸（默认 5.6）
    --page-break      每篇之间插入分页符
    --toc             在开头插入目录页
    --no-links        不生成「附录：原文链接清单」
    --no-sources      不添加来源链接（封面来源清单 + 每章标题下的「原文链接」行）
    --no-images       不下载图片
    --keep-all-images 不跳过 logo / favicon 等疑似装饰图
    --dump-json       导出解析后的结构化 JSON，便于二次加工

适用平台：Windows / macOS / Linux（Python 3.8+）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

# ---------------------------------------------------------------------------
# 依赖检查（给人话提示，而不是一堆 traceback）
# ---------------------------------------------------------------------------
_MISSING = []
try:
    import requests
except ImportError:  # pragma: no cover
    _MISSING.append("requests")
try:
    from bs4 import BeautifulSoup, NavigableString, Tag
except ImportError:  # pragma: no cover
    _MISSING.append("beautifulsoup4")
try:
    from docx import Document
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Inches, Pt, RGBColor
except ImportError:  # pragma: no cover
    _MISSING.append("python-docx")

if _MISSING:
    sys.exit("缺少依赖：%s\n请先运行： pip install %s" % (", ".join(_MISSING), " ".join(_MISSING)))


# ===========================================================================
# ① 可调参数
# ===========================================================================

# 正文容器候选 class（按优先级）。抓不到正文时，用 --selector 显式指定。
CONTENT_HINTS = (
    "vp-doc", "markdown-body", "article-content", "post-content",
    "entry-content", "rich_media_content", "article-body", "content-body",
)

# 疑似装饰图，默认跳过
SKIP_IMG_KEYWORDS = ("favicon", "sprite")

# 图片友好命名覆盖表（可选）。键是图片原始文件名，值是不带扩展名的新名字。
# 留空即可 —— 默认会用「去掉构建哈希后的原文件名」命名，例如：
#   image-2.nX8V0i5W.png  ->  win-03-image-2.png
#   poster.png            ->  win-04-poster.png
# 想指定语义化名字时再加，例如：
#   IMAGE_NAME_MAP = {"image-2.nX8V0i5W.png": "install-01-agreement"}
IMAGE_NAME_MAP: dict = {}

# 从页面路径猜平台前缀（用于图片命名：win-01-xxx.png）。命中不了就用 URL slug。
PREFIX_HINTS = (
    ("windows", "win"), ("win", "win"),
    ("macos", "mac"), ("mac", "mac"),
    ("ios", "ios"), ("iphone", "ios"),
    ("android", "android"), ("harmony", "harmony"),
    ("linux", "linux"), ("web", "web"), ("mini", "mini"),
)

# ---- Word 排版参数 ----
FONT_EA = "微软雅黑"        # 中文字体
FONT_ASCII = "Segoe UI"     # 西文字体
BODY_SIZE = 10.5            # 正文磅值
COLOR_ACCENT = RGBColor(0x16, 0x68, 0xDC)
COLOR_GRAY = RGBColor(0x65, 0x6D, 0x76)
COLOR_DARK = RGBColor(0x1F, 0x23, 0x28)
COLOR_HEAD_BG = "F5F6F8"
COLOR_TIP_BG = "F4F8FF"
COLOR_TIP_BAR = "1668DC"
MAX_IMG_IN = 5.6            # 图片最大宽度（英寸）

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


# ===========================================================================
# ② 抓取
# ===========================================================================

SESSION = requests.Session()
SESSION.headers.update(HTTP_HEADERS)


def fetch(url: str, retries: int = 3, timeout: int = 40) -> str:
    """下载网页 HTML，自动处理编码。"""
    last = None
    for i in range(retries):
        try:
            r = SESSION.get(url, timeout=timeout)
            r.raise_for_status()
            if not r.encoding or r.encoding.lower() == "iso-8859-1":
                r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except Exception as e:  # noqa: BLE001
            last = e
            if i < retries - 1:
                time.sleep(1.5 * (i + 1))
    raise RuntimeError("抓取失败：%s（%s）" % (url, last))


def norm_url(src: str, page_url: str = "") -> str:
    """把相对 / 协议相对 / 带空格的地址补全成绝对 URL。"""
    if not src:
        return ""
    src = src.strip().replace("\u200b", "")
    if src.startswith("//"):
        return "https:" + src
    if src.startswith(("http://", "https://", "data:")):
        return src
    if not page_url:
        return src
    return urljoin(page_url, src)


# 懒加载站点常见的图片真实地址属性
IMG_ATTRS = (
    "src", "data-src", "data-original", "data-lazy-src",
    "data-actualsrc", "data-echo", "data-url", "data-original-src",
)


def pick_img_src(tag) -> str:
    """尽量拿到图片的真实地址（兼容懒加载 / srcset）。"""
    for a in IMG_ATTRS:
        v = (tag.get(a) or "").strip()
        if v and not v.startswith("data:image/gif"):  # 1px 占位图
            return v
    for a in ("srcset", "data-srcset"):
        ss = (tag.get(a) or "").strip()
        if ss:
            parts = [p.strip().split()[0] for p in ss.split(",") if p.strip()]
            if parts:
                return parts[-1]  # 通常最后一个是最大尺寸
    return ""


# ===========================================================================
# ③ 解析：HTML → 线性 blocks
#   heading{level,text} | p{text} | pinline{parts:[str|{text,href}]}
#   listitem{ordered,index,blocks} | image{src,alt} | code{text}
#   table{rows} | tip{title,blocks}
# ===========================================================================

INLINE_TAGS = {
    "strong", "b", "em", "i", "span", "mark", "u", "code", "a", "br",
    "small", "sub", "sup", "del", "s", "kbd", "abbr", "time", "label",
}
BLOCK_TAGS = {
    "div", "p", "ul", "ol", "li", "table", "thead", "tbody", "tr", "td", "th",
    "h1", "h2", "h3", "h4", "h5", "h6", "pre", "details", "summary",
    "section", "article", "blockquote", "figure", "hr", "img",
}
TIP_WORDS = ("TIP", "提示", "WARNING", "注意", "CAUTION", "警告", "INFO", "信息", "NOTE", "说明")
TIP_CLASS = ("custom-block", "tip", "warning", "note", "callout", "alert", "admonition")


def pick_content(soup: BeautifulSoup, selector: str = ""):
    """定位正文容器：显式选择器 → 常见 class → 最紧凑的含标题容器 → body。"""
    if selector:
        try:
            node = soup.select_one(selector)
            if node is not None:
                return node
            print("    ⚠ 选择器 %r 没匹配到元素，自动识别正文" % selector)
        except Exception as e:  # noqa: BLE001
            print("    ⚠ 选择器 %r 无效（%s），自动识别正文" % (selector, e))

    # 常见正文 class —— 命中多个时取最内层（后代最少）的那个
    hits = []
    for div in soup.find_all("div"):
        cls = " ".join(div.get("class") or [])
        if any(h in cls for h in CONTENT_HINTS):
            hits.append(div)
    if hits:
        return min(hits, key=lambda d: len(d.find_all(True)))

    # 没有 class 线索：在 article/main/div 里找「有 h1 或 h2 且正文够长」的最紧凑容器
    cands = []
    for tag in soup.find_all(["article", "main", "div"]):
        if not (tag.find("h1") or tag.find("h2")):
            continue
        text_len = len(tag.get_text(" ", strip=True))
        if text_len < 400:
            continue
        cands.append((len(tag.find_all(True)), text_len, tag))
    if cands:
        return min(cands)[2]

    return soup.body or soup


def inline_parts(node):
    """把一个块级节点里的行内内容压成 parts 列表，保留链接。"""
    parts = []
    for sub in node.children:
        if isinstance(sub, NavigableString):
            t = str(sub)
            if t.strip():
                parts.append(t)
            continue
        if not isinstance(sub, Tag):
            continue
        if sub.name == "a":
            h = norm_url(sub.get("href") or "")
            t = sub.get_text(" ", strip=True)
            if not t or h.startswith("javascript:"):
                continue
            parts.append(t if (not h or h.startswith("#")) else {"text": t, "href": h})
            continue
        if sub.name == "br":
            parts.append("\n")
            continue
        if sub.name == "code":
            parts.append("`%s`" % sub.get_text(" ", strip=True))
            continue
        parts.extend(inline_parts(sub))

    merged = []
    for p in parts:
        if isinstance(p, str) and merged and isinstance(merged[-1], str):
            merged[-1] += p
        else:
            merged.append(p)
    return merged


def clean_parts(parts):
    out = []
    for p in parts:
        if isinstance(p, str):
            s = " ".join(p.replace("\u200b", "").split())
            if s:
                out.append(s)
        else:
            t = " ".join(p["text"].split())
            if t:
                out.append({"text": t, "href": p["href"]})
    return out


def has_block_child(node) -> bool:
    for c in node.descendants:
        if isinstance(c, Tag) and c.name.lower() in BLOCK_TAGS:
            return True
    return False


def _mk_p(parts):
    if not parts:
        return None
    if len(parts) == 1 and isinstance(parts[0], str):
        return {"type": "p", "text": parts[0]}
    return {"type": "pinline", "parts": parts}


def _img_block(tag, page_url, keep_all):
    src = norm_url(pick_img_src(tag), page_url)
    if not src:
        return None
    if not keep_all and any(k in src.lower() for k in SKIP_IMG_KEYWORDS):
        return None
    return {"type": "image", "src": src, "alt": (tag.get("alt") or "").strip()}


def blocks_from_children(node, ordered=False, depth=0, page_url="", keep_all=False):
    """遍历子元素，产出线性 blocks。"""
    out = []

    # 纯行内节点（如 <li> 里只有文字和 <strong>）：整体当一段，避免碎片化
    if not has_block_child(node):
        b = _mk_p(clean_parts(inline_parts(node)))
        return [b] if b else []

    inline_buf = []

    def flush_inline():
        if not inline_buf:
            return
        parts = clean_parts(inline_buf[:])
        inline_buf.clear()
        b = _mk_p(parts)
        if b:
            out.append(b)

    for child in node.children:
        if isinstance(child, NavigableString):
            t = " ".join(str(child).split())
            if t:
                inline_buf.append(t)
            continue
        if not isinstance(child, Tag):
            continue
        name = child.name.lower()

        if name in ("script", "style", "nav", "aside", "button", "svg", "noscript",
                    "iframe", "form", "select", "textarea"):
            continue

        if name in INLINE_TAGS:
            inline_buf.extend(inline_parts(child))
            continue

        flush_inline()

        # --- 标题 ---
        if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            txt = child.get_text(" ", strip=True).replace("\u200b", "").strip()
            if txt:
                out.append({"type": "heading", "level": int(name[1]), "text": txt})
            continue

        # --- 图片 ---
        if name == "img":
            ib = _img_block(child, page_url, keep_all)
            if ib:
                out.append(ib)
            continue

        # --- 列表 ---
        if name in ("ul", "ol"):
            try:
                start = int(child.get("start") or 1)
            except (TypeError, ValueError):
                start = 1
            for i, li in enumerate(child.find_all("li", recursive=False), 1):
                out.append({
                    "type": "listitem",
                    "ordered": name == "ol",
                    "index": (start + i - 1) if name == "ol" else None,
                    "blocks": blocks_from_children(li, name == "ol", depth + 1,
                                                   page_url, keep_all),
                    "depth": depth,
                })
            continue

        # --- 表格 ---
        if name == "table":
            rows = []
            for tr in child.find_all("tr"):
                rows.append([td.get_text(" ", strip=True).replace("\u200b", "")
                             for td in tr.find_all(["td", "th"])])
            if rows:
                out.append({"type": "table", "rows": rows})
            continue

        # --- 代码块 ---
        if name == "pre":
            out.append({"type": "code", "text": child.get_text("\n", strip=True)})
            continue

        # --- 折叠块 ---
        if name == "details":
            summ = child.find("summary")
            title = summ.get_text(" ", strip=True) if summ else ""
            body = blocks_from_children(child, depth=depth, page_url=page_url,
                                        keep_all=keep_all)
            if summ:
                body = [b for b in body if not (b["type"] == "p" and b["text"] == title)]
            out.append({"type": "tip", "title": title, "blocks": body})
            continue

        # --- 提示框 ---
        if name == "div":
            cls = " ".join(child.get("class") or []).lower()
            if any(k in cls for k in TIP_CLASS):
                body = blocks_from_children(child, depth=depth, page_url=page_url,
                                            keep_all=keep_all)
                title = ""
                if body and body[0]["type"] == "p" and body[0]["text"].upper() in TIP_WORDS:
                    title = body.pop(0)["text"]
                if body:
                    out.append({"type": "tip", "title": title, "blocks": body})
                continue
            out.extend(blocks_from_children(child, depth=depth, page_url=page_url,
                                            keep_all=keep_all))
            continue

        # --- 段落（可能夹带图片） ---
        if name in ("p", "summary", "figure", "figcaption", "blockquote"):
            b = _mk_p(clean_parts(inline_parts(child)))
            if b:
                out.append(b)
            for i in child.find_all("img"):
                ib = _img_block(i, page_url, keep_all)
                if ib:
                    out.append(ib)
            continue

        # --- 其它块级元素：递归展开 ---
        out.extend(blocks_from_children(child, depth=depth, page_url=page_url,
                                        keep_all=keep_all))

    flush_inline()
    return out


def parse_page(html: str, url: str, selector: str = "", keep_all: bool = False) -> dict:
    """HTML → {title, source, blocks}（已去重）。"""
    soup = BeautifulSoup(html, "html.parser")

    for bad in soup.find_all(["script", "style", "nav", "header", "footer", "aside",
                              "noscript", "template"]):
        bad.decompose()

    og = soup.find("meta", attrs={"property": "og:title"})
    page_title = (og.get("content") or "").strip() if og else ""
    if not page_title and soup.title:
        page_title = soup.title.get_text(strip=True)
    page_title = re.sub(r"\s*[|｜\-–—]\s*[^|｜\-–—]{0,30}$", "", page_title).strip() or page_title

    content = pick_content(soup, selector)
    blocks = blocks_from_children(content, page_url=url, keep_all=keep_all)

    # 去重：连续相同的段落
    dedup = []
    for b in blocks:
        if (dedup and b.get("type") == "p" and dedup[-1].get("type") == "p"
                and dedup[-1].get("text") == b.get("text")):
            continue
        dedup.append(b)

    h1 = next((b["text"] for b in dedup if b["type"] == "heading" and b["level"] == 1), "")
    return {"title": h1 or page_title, "page_title": page_title,
            "source": url, "blocks": dedup}


def walk_blocks(bs):
    for b in bs:
        yield b
        if b["type"] in ("listitem", "tip"):
            yield from walk_blocks(b["blocks"])


def collect_images(doc) -> list:
    return [b["src"] for b in walk_blocks(doc["blocks"]) if b["type"] == "image"]


def collect_links(doc) -> list:
    out = []
    for b in walk_blocks(doc["blocks"]):
        if b["type"] == "pinline":
            for p in b["parts"]:
                if isinstance(p, dict):
                    out.append((p["text"], p["href"]))
        elif b["type"] == "p":
            for u in re.findall(r"https?://[^\s，。）()\"'<>]+", b["text"]):
                out.append((u, u))
    return out


def normalize(bs) -> list:
    """整理块序列：
       1) 紧跟列表项后的图片归入该列表项（原文常把步骤配图放在 </ol> 之后）；
       2) 去掉顶层 h1（章节标题由生成器统一提供）。
    """
    res = []
    i = 0
    while i < len(bs):
        b = bs[i]
        if b["type"] == "heading" and b["level"] == 1:
            i += 1
            continue
        if b["type"] == "listitem":
            nb = dict(b)
            nb["blocks"] = normalize(list(b["blocks"]))
            i += 1
            while i < len(bs) and bs[i]["type"] == "image":
                nb["blocks"].append(bs[i])
                i += 1
            res.append(nb)
            continue
        if b["type"] == "tip":
            nb = dict(b)
            nb["blocks"] = normalize(list(b["blocks"]))
            res.append(nb)
            i += 1
            continue
        res.append(b)
        i += 1
    return res


# ===========================================================================
# ④ 图片：下载 + 友好重命名
# ===========================================================================

def safe_name(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fa5._-]+", "_", s).strip("_")


def strip_hash(fn: str) -> str:
    """image-2.nX8V0i5W.png -> image-2.png（去掉构建哈希）"""
    return re.sub(r"\.[0-9A-Za-z_-]{6,}\.(png|jpg|jpeg|webp|gif|bmp)$", r".\1", fn)


def ext_from(url: str, ctype: str = "") -> str:
    tail = unquote(urlparse(url).path.rsplit("/", 1)[-1])
    m = re.search(r"\.(png|jpg|jpeg|webp|gif|bmp|svg)$", tail, re.I)
    if m:
        return "." + m.group(1).lower().replace("jpeg", "jpg")
    m = re.search(r"image/(png|jpeg|jpg|webp|gif|bmp|svg)", ctype or "", re.I)
    if m:
        return "." + m.group(1).lower().replace("jpeg", "jpg")
    return ".png"


def cache_file_name(url: str) -> str:
    tail = unquote(urlparse(url).path.rsplit("/", 1)[-1])
    if tail and re.search(r"\.(png|jpg|jpeg|webp|gif|bmp|svg)$", tail, re.I):
        return safe_name(tail)
    return hashlib.md5(url.encode("utf-8")).hexdigest()[:12] + ext_from(url)


def download_image(url: str, dest: Path, retries: int = 3) -> int:
    for i in range(retries):
        try:
            r = SESSION.get(url, timeout=60)
            r.raise_for_status()
            dest.write_bytes(r.content)
            return len(r.content)
        except Exception:  # noqa: BLE001
            if i == retries - 1:
                return 0
            time.sleep(1.2 * (i + 1))
    return 0


def download_all_images(docs, img_dir: Path, verbose=True) -> dict:
    """下载所有图片到 img_dir，返回 {原始URL: 缓存文件名}。"""
    img_dir.mkdir(parents=True, exist_ok=True)
    srcs = []
    for d in docs:
        for s in collect_images(d):
            if s and s not in srcs:
                srcs.append(s)

    mapping, ok, fail = {}, 0, []
    for s in srcs:
        fn = cache_file_name(s)
        dest = img_dir / fn
        if dest.exists() and dest.stat().st_size > 0:
            mapping[s] = fn
            ok += 1
            continue
        n = download_image(s, dest)
        if n:
            mapping[s] = fn
            ok += 1
            if verbose:
                print("    ✓ %-46s %8d B" % (fn[:46], n))
        else:
            fail.append(s)
            if verbose:
                print("    ✗ 下载失败 %s" % s)
    if verbose:
        print("  图片：成功 %d / %d%s"
              % (ok, len(srcs), ("，失败 %d" % len(fail)) if fail else ""))
    return mapping


def ensure_embeddable(path: Path):
    """确保 python-docx 能识别该图片；遇到 WebP 等不支持的格式就地转成 PNG。

    返回可用的文件路径；无法转换时返回 None（调用方应跳过该图）。
    """
    try:
        from docx.image.image import Image as DxImage
        DxImage.from_file(str(path))
        return path
    except Exception:  # noqa: BLE001 —— 不支持的格式（如 webp）会走到这里
        pass
    try:
        from PIL import Image as PILImage
    except ImportError:
        print("    ⚠ 图片格式无法识别且未安装 Pillow，已跳过：%s" % path.name)
        return None
    try:
        im = PILImage.open(str(path))
        if getattr(im, "is_animated", False):
            im.seek(0)
        im = im.convert("RGBA") if im.mode in ("RGBA", "LA", "P") else im.convert("RGB")
        out = path.with_suffix(".png")
        im.save(str(out), "PNG")
        if out != path and path.exists():
            path.unlink()
        print("    ↻ 已转码为 PNG：%s" % out.name)
        return out
    except Exception as e:  # noqa: BLE001
        print("    ⚠ 转码失败（%s），已跳过：%s" % (e, path.name))
        return None


def build_assets(keyed_docs, img_cache: dict, img_dir: Path, assets_dir: Path) -> dict:
    """把图片重命名成 `<前缀>-<序号>-<语义名>.png`，返回 {URL: "assets/xxx.png"}。"""
    if assets_dir.exists():
        shutil.rmtree(assets_dir)
    assets_dir.mkdir(parents=True, exist_ok=True)

    out, counters = {}, {}
    for key, doc in keyed_docs:
        for src in collect_images(doc):
            if src in out:
                continue
            fn = img_cache.get(src)
            if not fn:
                continue
            base = IMAGE_NAME_MAP.get(fn) or strip_hash(fn)
            base = safe_name(base.rsplit(".", 1)[0]) or "image"
            counters[key] = counters.get(key, 0) + 1
            new_name = "%s-%02d-%s%s" % (key, counters[key], base, Path(fn).suffix or ".png")
            srcf, dstf = img_dir / fn, assets_dir / new_name
            if not srcf.exists():
                continue
            shutil.copy2(srcf, dstf)
            dstf = ensure_embeddable(dstf)
            if dstf is None:
                continue
            out[src] = "assets/" + dstf.name
    return out


# ===========================================================================
# ⑤ 渲染 Word
# ===========================================================================

def set_run(run, size=BODY_SIZE, bold=False, color=None, italic=False, ea=FONT_EA):
    run.font.name = FONT_ASCII
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    if color is not None:
        run.font.color.rgb = color
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.get_or_add_rFonts()
    rFonts.set(qn("w:ascii"), FONT_ASCII)
    rFonts.set(qn("w:hAnsi"), FONT_ASCII)
    rFonts.set(qn("w:eastAsia"), ea)


def shade_para(p, fill):
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    pPr.append(shd)


def para_border(p, edge="left", color=COLOR_TIP_BAR, size=18, space=4):
    pPr = p._p.get_or_add_pPr()
    pBdr = pPr.find(qn("w:pBdr"))
    if pBdr is None:
        pBdr = OxmlElement("w:pBdr")
        pPr.append(pBdr)
    el = OxmlElement("w:%s" % edge)
    el.set(qn("w:val"), "single")
    el.set(qn("w:sz"), str(size))
    el.set(qn("w:space"), str(space))
    el.set(qn("w:color"), color)
    pBdr.append(el)


def add_hyperlink(paragraph, url, text, size=BODY_SIZE, color="1668DC", underline=True):
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    r_id = paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True)
    hl = OxmlElement("w:hyperlink")
    hl.set(qn("r:id"), r_id)
    r = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")
    rf = OxmlElement("w:rFonts")
    rf.set(qn("w:ascii"), FONT_ASCII)
    rf.set(qn("w:hAnsi"), FONT_ASCII)
    rf.set(qn("w:eastAsia"), FONT_EA)
    rPr.append(rf)
    c = OxmlElement("w:color")
    c.set(qn("w:val"), color)
    rPr.append(c)
    if underline:
        u = OxmlElement("w:u")
        u.set(qn("w:val"), "single")
        rPr.append(u)
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), str(int(size * 2)))
    rPr.append(sz)
    r.append(rPr)
    t = OxmlElement("w:t")
    t.text = text
    t.set(qn("xml:space"), "preserve")
    r.append(t)
    hl.append(r)
    paragraph._p.append(hl)


def cell_shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


class DocBuilder:
    def __init__(self, doc: Document, imgmap: dict, work: Path, img_max_in: float = MAX_IMG_IN):
        self.doc = doc
        self.imgmap = imgmap
        self.work = work
        self.img_max_in = img_max_in
        self.images_drawn = 0     # 成功插入的图片数
        self.images_skipped = []  # 没能插入的图片 URL（自检用）

    def para(self, space_after=6, space_before=0, align=None, indent=None, line=1.4):
        p = self.doc.add_paragraph()
        pf = p.paragraph_format
        pf.space_after = Pt(space_after)
        pf.space_before = Pt(space_before)
        pf.line_spacing = line
        if align is not None:
            pf.alignment = align
        if indent is not None:
            pf.left_indent = Inches(indent)
        return p

    def text_para(self, text, **kw):
        p = self.para(**kw)
        set_run(p.add_run(text))
        return p

    def heading(self, text, level=1):
        sizes = {1: 17, 2: 14, 3: 12}
        p = self.para(space_after=8, space_before=16 if level == 1 else 12, line=1.2)
        if level == 1:
            para_border(p, edge="bottom", color="D8DCE0", size=8, space=6)
        set_run(p.add_run(text), size=sizes.get(level, 11), bold=True,
                color=COLOR_ACCENT if level == 1 else COLOR_DARK)
        return p

    def source_line(self, url):
        p = self.para(space_after=10)
        set_run(p.add_run("原文链接："), size=9, color=COLOR_GRAY)
        add_hyperlink(p, url, url, size=9)
        return p

    def page_break(self):
        from docx.enum.text import WD_BREAK
        self.doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    def image(self, src, alt=""):
        rel = self.imgmap.get(src)
        if not rel:
            # imgmap 为空 = 用户传了 --no-images，属预期；非空却查不到 = 真的漏了
            if self.imgmap:
                self.images_skipped.append(src)
            return
        path = self.work / rel
        if not path.exists():
            self.images_skipped.append(src)
            return
        # 兜底：万一图片格式 python-docx 仍不认（如漏网的 webp），转成 PNG 再用
        try:
            from docx.image.image import Image as DxImage
            DxImage.from_file(str(path))
        except Exception:  # noqa: BLE001
            fixed = ensure_embeddable(path)
            if fixed is None:
                self.images_skipped.append(src)
                return
            path = fixed
        p = self.para(space_after=2, space_before=6, align=WD_ALIGN_PARAGRAPH.CENTER)
        width_in = self.img_max_in
        try:
            from docx.image.image import Image as DxImage
            img = DxImage.from_file(str(path))
            nat = img.px_width / (img.horiz_dpi or 96)
            width_in = min(self.img_max_in, max(2.0, nat))
        except Exception:  # noqa: BLE001
            pass
        p.add_run().add_picture(str(path), width=Inches(width_in))
        self.images_drawn += 1
        if alt and alt.lower() not in ("图片", "image", "screenshot", "截图", "img"):
            cap = self.para(space_after=10, align=WD_ALIGN_PARAGRAPH.CENTER)
            set_run(cap.add_run(alt), size=8.5, color=COLOR_GRAY)

    # --- 提示块 ---
    def _tip_block(self, x):
        out = []
        if x["type"] == "p":
            p = self.para(space_after=2, indent=0.12)
            set_run(p.add_run(x["text"]))
            out.append(p)
        elif x["type"] == "pinline":
            p = self.para(space_after=2, indent=0.12)
            for part in x["parts"]:
                if isinstance(part, str):
                    set_run(p.add_run(part))
                else:
                    add_hyperlink(p, part["href"], part["text"], size=10)
            out.append(p)
        elif x["type"] == "image":
            self.image(x["src"], x.get("alt") or "")
        elif x["type"] == "listitem":
            p = self.para(space_after=2, indent=0.34)
            p.paragraph_format.first_line_indent = Inches(-0.18)
            set_run(p.add_run("• "), bold=True, color=COLOR_ACCENT)
            for s in x["blocks"]:
                if s["type"] == "p":
                    set_run(p.add_run(s["text"]))
                elif s["type"] == "pinline":
                    for part in s["parts"]:
                        if isinstance(part, str):
                            set_run(p.add_run(part))
                        else:
                            add_hyperlink(p, part["href"], part["text"], size=10)
                elif s["type"] == "image":
                    self.image(s["src"], s.get("alt") or "")
                else:
                    # 嵌套的 listitem / tip / table / code：递归处理，避免静默丢弃
                    out.extend(self._tip_block(s))
            out.append(p)
        elif x["type"] == "tip":
            out.extend(self._tip_seq(x.get("title") or "", x["blocks"]))
        else:
            # table / code / heading 等：走通用渲染，避免 _tip_seq 自递归
            render_blocks([x], self, {"last_p": None})
        return out

    def _tip_seq(self, title, blocks):
        paras = []
        head = self.para(space_after=2, space_before=8, indent=0.12)
        set_run(head.add_run("💡 %s" % (title or "提示")), size=9.5, bold=True,
                color=COLOR_ACCENT)
        paras.append(head)
        for x in blocks:
            paras.extend(self._tip_block(x))
        for p in paras:
            para_border(p, "left", color=COLOR_TIP_BAR, size=20, space=6)
            shade_para(p, COLOR_TIP_BG)
        return paras

    def tip(self, title, blocks, ctx=None):
        self._tip_seq(title or "", blocks)

    def step(self, num, text_runs):
        p = self.para(space_after=6, indent=0.28)
        p.paragraph_format.first_line_indent = Inches(-0.28)
        set_run(p.add_run("%s " % num), bold=True, color=COLOR_ACCENT)
        for kind, val in text_runs:
            if kind == "text":
                set_run(p.add_run(val))
            else:
                add_hyperlink(p, val["href"], val["text"])
        return p


def render_table(rows, b: DocBuilder):
    if not rows:
        return
    ncol = max(len(r) for r in rows)
    table = b.doc.add_table(rows=1, cols=ncol)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for c, txt in zip(table.rows[0].cells, rows[0] + [""] * (ncol - len(rows[0]))):
        cell_shade(c, COLOR_HEAD_BG)
        set_run(c.paragraphs[0].add_run(txt), size=9.5, bold=True)
    for row in rows[1:]:
        cells = table.add_row().cells
        for c, txt in zip(cells, row + [""] * (ncol - len(row))):
            set_run(c.paragraphs[0].add_run(txt), size=9)
    b.doc.add_paragraph()


def render_blocks(bs, b: DocBuilder, ctx, in_tip=False):
    for x in bs:
        t = x["type"]
        if t == "heading":
            b.heading(x["text"], min(x["level"], 3))
        elif t == "p":
            if in_tip:
                p = ctx.get("last_p") or b.para(indent=0.12)
                set_run(p.add_run(x["text"]))
                ctx["last_p"] = p
            else:
                b.text_para(x["text"])
        elif t == "pinline":
            if in_tip:
                p = ctx.get("last_p") or b.para(indent=0.12)
                ctx["last_p"] = p
            else:
                p = b.para()
            for part in x["parts"]:
                if isinstance(part, str):
                    set_run(p.add_run(part))
                else:
                    add_hyperlink(p, part["href"], part["text"])
        elif t == "image":
            b.image(x["src"], x.get("alt") or "")
        elif t == "code":
            p = b.para(space_after=8)
            shade_para(p, COLOR_HEAD_BG)
            set_run(p.add_run(x["text"]), size=9)
        elif t == "tip":
            b.tip(x.get("title") or "", x["blocks"], ctx)
        elif t == "table":
            render_table(x["rows"], b)
        elif t == "listitem":
            # 嵌套列表（<li> 里再套 <ul>/<ol>）——必须在这里续上，
            # 否则嵌套项会被静默丢弃，连带里面的配图一起丢。
            render_lists_and_rest([x], b, ctx, in_tip=in_tip)


def render_lists_and_rest(bs, b: DocBuilder, ctx, in_tip=False):
    """listitem 序列 → 编号步骤 / 项目符号；其余块正常渲染。"""
    i = 0
    while i < len(bs):
        x = bs[i]
        if x["type"] == "listitem":
            j = i
            while (j < len(bs) and bs[j]["type"] == "listitem"
                   and bs[j]["ordered"] == x["ordered"]):
                item = bs[j]
                if item["ordered"]:
                    runs, rest = [], []
                    for s in item["blocks"]:
                        if s["type"] == "p" and not runs:
                            runs.append(("text", s["text"]))
                        elif s["type"] == "pinline" and not runs:
                            runs.extend(("text", p) if isinstance(p, str) else ("link", p)
                                        for p in s["parts"])
                        else:
                            rest.append(s)
                    b.step("%d." % (item["index"] or (j - i + 1)), runs)
                    render_blocks(rest, b, {"last_p": None}, in_tip=in_tip)
                else:
                    p = b.para(space_after=4, indent=0.28)
                    p.paragraph_format.first_line_indent = Inches(-0.18)
                    set_run(p.add_run("• "), bold=True, color=COLOR_ACCENT)
                    for s in item["blocks"]:
                        if s["type"] == "p":
                            set_run(p.add_run(s["text"]))
                        elif s["type"] == "pinline":
                            for part in s["parts"]:
                                if isinstance(part, str):
                                    set_run(p.add_run(part))
                                else:
                                    add_hyperlink(p, part["href"], part["text"])
                        elif s["type"] == "image":
                            b.image(s["src"], s.get("alt") or "")
                        elif s["type"] == "tip":
                            b.tip(s.get("title") or "", s["blocks"], {"last_p": None})
                        else:
                            render_blocks([s], b, {"last_p": None}, in_tip=in_tip)
                j += 1
            i = j
            continue
        render_blocks([x], b, ctx, in_tip=in_tip)
        i += 1


def new_document():
    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Cm(21.0)
    sec.page_height = Cm(29.7)
    sec.top_margin = Cm(2.4)
    sec.bottom_margin = Cm(2.4)
    sec.left_margin = Cm(2.6)
    sec.right_margin = Cm(2.6)
    style = doc.styles["Normal"]
    style.font.name = FONT_ASCII
    style.font.size = Pt(BODY_SIZE)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), FONT_EA)
    return doc


def build_docx(sections, imgmap, work: Path, out_path: Path, title: str,
               subtitle: str = "", appendix=None, img_max_in: float = MAX_IMG_IN,
               page_break: bool = False, toc: bool = False,
               show_sources: bool = True):
    """sections: [(章节标题, 原文URL, blocks)]

    show_sources=False 时不添加来源链接：封面来源清单 + 每章标题下的「原文链接」行。

    返回 (输出路径, 成功插入的图片数, 未能插入的图片URL列表)
    """
    doc = new_document()
    b = DocBuilder(doc, imgmap, work, img_max_in)

    # 封面
    p = b.para(space_after=6, space_before=30, line=1.2)
    set_run(p.add_run(title), size=24, bold=True, color=COLOR_DARK)
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER

    sub = b.para(space_after=18, align=WD_ALIGN_PARAGRAPH.CENTER)
    set_run(sub.add_run(subtitle or "共 %d 篇原文" % len(sections)), size=9.5, color=COLOR_GRAY)
    para_border(sub, edge="bottom", color="D8DCE0", size=8, space=10)

    if show_sources:
        intro = b.para(space_after=6)
        set_run(intro.add_run("本文档由以下 %d 个原始页面整理而成，完整保留原文的正文结构、配图与链接："
                              % len(sections)))
        for _, src, _ in sections:
            pl = b.para(space_after=2, indent=0.2)
            pl.paragraph_format.first_line_indent = Inches(-0.18)
            set_run(pl.add_run("· "), color=COLOR_GRAY, size=9)
            add_hyperlink(pl, src, src, size=9)

    # 目录
    if toc and len(sections) > 1:
        b.para(space_after=4, space_before=16)
        b.heading("目录", 2)
        for idx, (label, _, _) in enumerate(sections, 1):
            pl = b.para(space_after=2, indent=0.3)
            set_run(pl.add_run("%d.  %s" % (idx, label)), size=10)

    # 正文
    for n, (label, src, blocks) in enumerate(sections):
        if page_break and n:
            b.page_break()
        b.heading(label, 1)
        if show_sources:
            b.source_line(src)
        render_lists_and_rest(blocks, b, {"last_p": None})

    # 附录
    if appendix and appendix.get("rows"):
        if page_break:
            b.page_break()
        b.heading(appendix.get("title") or "附录", 1)
        b.text_para(appendix.get("note") or "")
        rows = [("来源页面", "链接文字", "链接地址")] + list(appendix["rows"])
        table = doc.add_table(rows=1, cols=3)
        table.style = "Table Grid"
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        widths = (Cm(3.2), Cm(3.6), Cm(8.6))
        for c, txt in zip(table.rows[0].cells, rows[0]):
            cell_shade(c, COLOR_HEAD_BG)
            set_run(c.paragraphs[0].add_run(txt), size=9.5, bold=True)
        for label, text, href in rows[1:]:
            cells = table.add_row().cells
            set_run(cells[0].paragraphs[0].add_run(label), size=9)
            set_run(cells[1].paragraphs[0].add_run(text), size=9)
            add_hyperlink(cells[2].paragraphs[0], href, href, size=8)
        for row in table.rows:
            for c, w in zip(row.cells, widths):
                c.width = w

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    return out_path, b.images_drawn, b.images_skipped


# ===========================================================================
# ⑥ 主流程
# ===========================================================================

def url_prefix(url: str, index: int) -> str:
    """给图片命名用的前缀：优先平台关键词，其次 URL slug，最后 p<序号>。"""
    tail = url.rstrip("/").rsplit("/", 1)[-1].lower()
    for kw, pref in PREFIX_HINTS:
        if kw in tail:
            return pref
    slug = safe_name(re.sub(r"\.(html?|php|aspx?)$", "", tail))[:12]
    return slug or ("p%d" % index)


def make_appendix(labeled_docs):
    seen, rows = set(), []
    for label, doc in labeled_docs:
        for text, href in collect_links(doc):
            if (text, href) in seen:
                continue
            seen.add((text, href))
            rows.append((label, text, href))
    return rows


def main(argv=None):
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass

    ap = argparse.ArgumentParser(
        description="抓取 1~N 个网页的正文/图片/链接，整合成一份 Word 文档",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("urls", nargs="+", help="要抓取的页面链接（1 个或多个）")
    ap.add_argument("--out", default=".", help="输出目录（默认当前目录）")
    ap.add_argument("--name", default="", help="输出文件名（不含扩展名）")
    ap.add_argument("--title", default="", help="文档主标题（默认取第一篇的标题）")
    ap.add_argument("--selector", default="", help="正文容器 CSS 选择器")
    ap.add_argument("--work", default="", help="中间产物目录（默认系统临时目录）")
    ap.add_argument("--img-width", type=float, default=MAX_IMG_IN, help="图片最大宽度（英寸）")
    ap.add_argument("--page-break", action="store_true", help="每篇之间插入分页符")
    ap.add_argument("--toc", action="store_true", help="在开头插入目录")
    ap.add_argument("--no-links", action="store_true", help="不生成链接清单附录")
    ap.add_argument("--no-sources", action="store_true",
                    help="不添加来源链接（封面来源清单 + 每章标题下的「原文链接」行）")
    ap.add_argument("--no-images", action="store_true", help="不下载图片")
    ap.add_argument("--keep-all-images", action="store_true", help="不跳过 logo/favicon 等装饰图")
    ap.add_argument("--dump-json", action="store_true", help="导出解析后的结构化 JSON")
    args = ap.parse_args(argv)

    outs = [u.strip() for u in args.urls if u.strip()]
    if not outs:
        sys.exit("请至少提供一个链接。用法：python webpage_to_word.py <url> [<url> ...]")

    out_dir = Path(args.out).expanduser()
    work = Path(args.work).expanduser() if args.work else (
        Path(tempfile.gettempdir()) / "webpage_to_word")
    work.mkdir(parents=True, exist_ok=True)
    pages_dir, img_dir = work / "pages", work / "images"
    pages_dir.mkdir(exist_ok=True)

    print("=" * 68)
    print("网页 → Word")
    print("=" * 68)
    print("输出目录：%s" % out_dir.resolve())
    print("中间产物：%s" % work)
    print("待抓取 %d 个页面" % len(outs))

    # --- 1. 抓取 + 解析 ---
    docs, prefixes = [], []
    for i, url in enumerate(outs, 1):
        print("\n[%d/%d] %s" % (i, len(outs), url))
        html = fetch(url)
        (pages_dir / ("page-%d.html" % i)).write_text(html, encoding="utf-8")
        doc = parse_page(html, url, args.selector, args.keep_all_images)
        doc["blocks"] = normalize(doc["blocks"])
        print("  标题：%s" % (doc["title"] or "(未识别)"))
        print("  结构：%d 个内容块 ｜ 配图 %d 张 ｜ 链接 %d 条"
              % (len(doc["blocks"]), len(collect_images(doc)), len(collect_links(doc))))
        docs.append(doc)
        prefixes.append(url_prefix(url, i))

    # --- 2. 下载图片 ---
    if args.no_images:
        imgmap = {}
        print("\n已跳过图片下载（--no-images）")
    else:
        print("\n下载配图 …")
        img_cache = download_all_images(docs, img_dir)
        imgmap = build_assets(list(zip(prefixes, docs)), img_cache, img_dir, work / "assets")
        print("  已整理到：%s（%d 张）" % (work / "assets", len(imgmap)))

    # --- 3. 组装 ---
    sections = [(d["title"] or ("第 %d 篇" % i), u, d["blocks"])
                for i, (u, d) in enumerate(zip(outs, docs), 1)]

    title = args.title.strip()
    if not title:
        title = sections[0][0] if len(sections) == 1 else "%s 等 %d 篇" % (sections[0][0], len(sections))

    rows = [] if args.no_links else make_appendix(
        [(label, doc) for (label, _, _), doc in zip(sections, docs)])
    appendix = None
    if rows:
        appendix = {"title": "附录：原文链接清单",
                    "note": "下表汇总原文正文中出现的外部链接（去重后共 %d 条）。" % len(rows),
                    "rows": rows}

    safe_title = safe_name(title) or "网页文档"
    doc_name = args.name.strip() or safe_title
    out_path = out_dir / (doc_name if doc_name.lower().endswith(".docx") else doc_name + ".docx")

    out_path, drawn, skipped = build_docx(
        sections, imgmap, work, out_path, title=title,
        subtitle="共 %d 篇原文" % len(sections),
        appendix=appendix, img_max_in=args.img_width,
        page_break=args.page_break, toc=args.toc,
        show_sources=not args.no_sources)

    if args.dump_json:
        for pref, doc in zip(prefixes, docs):
            (work / ("%s.json" % pref)).write_text(
                json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        print("\n  结构化 JSON：%s" % work)

    # --- 5. 自校验 ---
    import zipfile
    with zipfile.ZipFile(out_path) as z:
        media = [n for n in z.namelist() if n.startswith("word/media/")]
        xml = z.read("word/document.xml").decode("utf-8")

    expected = sum(len(collect_images(d)) for d in docs)
    print("\n" + "=" * 68)
    print("✅ 完成：%s" % out_path.resolve())
    print("   %.2f MB ｜ 段落 %d ｜ 表格 %d ｜ 超链接 %d"
          % (out_path.stat().st_size / 1048576,
             xml.count("<w:p ") + xml.count("<w:p>"),
             xml.count("<w:tbl>"), len(re.findall(r"<w:hyperlink r:id", xml))))
    if args.no_images:
        print("   图片：已按 --no-images 跳过（解析到 %d 张）" % expected)
    else:
        print("   图片：解析到 %d 张 ｜ 插入 %d 张 ｜ docx 内图片资源 %d 个"
              % (expected, drawn, len(media)))
        if skipped:
            print("   ⚠ 有 %d 张图片未能插入（前 5 条）：" % len(skipped))
            for s in skipped[:5]:
                print("      - %s" % s)
        elif expected == 0:
            print("   ⚠ 一个配图都没解析到 —— 可能是 JS 动态渲染，"
                  "或图片在疑似装饰图黑名单里（试试 --keep-all-images）")
    print("=" * 68)
    return str(out_path.resolve())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\n已中断。")
    except Exception as exc:  # noqa: BLE001
        sys.exit("\n❌ 执行出错：%s" % exc)
