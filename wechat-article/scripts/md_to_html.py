#!/usr/bin/env python3
"""将公众号成稿 Markdown 转为适合预览/粘贴的 HTML。

用法:
  python scripts/md_to_html.py path/to/文章名.md
  python scripts/md_to_html.py path/to/文章名.md -o path/to/文章名.html
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path


CSS = """
body {
  margin: 0;
  background: #f3f3f3;
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB",
    "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif;
}
.toolbar {
  position: sticky;
  top: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.92);
  border-bottom: 1px solid #e8e8e8;
  backdrop-filter: blur(8px);
}
.copy-btn {
  appearance: none;
  border: none;
  cursor: pointer;
  padding: 10px 18px;
  border-radius: 999px;
  background: #07c160;
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  line-height: 1;
  box-shadow: 0 2px 8px rgba(7, 193, 96, 0.35);
}
.copy-btn:hover { background: #06ad56; }
.copy-btn:active { transform: scale(0.98); }
.copy-btn.copied { background: #576b95; box-shadow: none; }
.copy-hint {
  font-size: 13px;
  color: #888;
}
"""

FONT = (
    "font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',"
    "'Hiragino Sans GB','Microsoft YaHei',sans-serif;"
)
P_STYLE = (
    f"{FONT}font-size:15px;color:#2b2b2b;line-height:1.8;margin:14px 0;"
    "letter-spacing:.3px;text-align:justify;"
)
H1_STYLE = (
    f"{FONT}font-size:22px;font-weight:700;color:#1a1a1a;line-height:1.5;"
    "margin:26px 0 18px;text-align:center;letter-spacing:.5px;"
)
H2_STYLE = (
    f"{FONT}font-size:17px;font-weight:700;color:#1f5c46;line-height:1.5;"
    "margin:30px 0 14px;padding-left:10px;border-left:4px solid #b8892b;"
)
H3_STYLE = (
    f"{FONT}font-size:16px;font-weight:700;color:#1f5c46;line-height:1.5;"
    "margin:24px 0 12px;padding-left:10px;border-left:4px solid #b8892b;"
)
IMG_STYLE = "width:100%;display:block;margin:20px auto;border-radius:6px;"
QUOTE_STYLE = (
    f"{FONT}font-size:16px;font-weight:700;color:#1f5c46;line-height:1.75;"
    "margin:22px 0;padding:12px 14px;background:#f4f7f5;"
    "border-left:4px solid #b8892b;border-radius:2px;text-align:left;"
)
STRONG_STYLE = "color:#1f5c46;font-weight:700;"
LIST_STYLE = (
    f"{FONT}font-size:15px;color:#2b2b2b;line-height:1.8;"
    "margin:8px 0 8px 4px;text-align:justify;"
)
CARD_STYLE = (
    "max-width:677px;margin:0 auto;background:#ffffff;padding:20px 18px 32px;"
    "border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,.06);"
)
BODY_STYLE = (
    "margin:0;padding:24px 12px;background:#f2f2f2;"
    "font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',"
    "'Hiragino Sans GB','Microsoft YaHei',sans-serif;"
)

COPY_SCRIPT = """
<script>
(function () {
  var btn = document.getElementById("copy-btn");
  var article = document.getElementById("article");
  if (!btn || !article) return;

  function setCopied() {
    var old = btn.textContent;
    btn.textContent = "已复制";
    btn.classList.add("copied");
    setTimeout(function () {
      btn.textContent = old;
      btn.classList.remove("copied");
    }, 1800);
  }

  function fallbackCopy() {
    var range = document.createRange();
    range.selectNodeContents(article);
    var sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    var ok = false;
    try {
      ok = document.execCommand("copy");
    } catch (e) {}
    sel.removeAllRanges();
    return ok;
  }

  btn.addEventListener("click", async function () {
    var htmlContent = article.innerHTML;
    var textContent = article.innerText || article.textContent || "";

    try {
      if (navigator.clipboard && window.ClipboardItem) {
        var item = new ClipboardItem({
          "text/html": new Blob([htmlContent], { type: "text/html" }),
          "text/plain": new Blob([textContent], { type: "text/plain" }),
        });
        await navigator.clipboard.write([item]);
        setCopied();
        return;
      }
    } catch (e) {}

    if (fallbackCopy()) {
      setCopied();
      return;
    }

    alert("复制失败，请手动选中正文后复制。若用本地文件打开，可改用本地服务器或允许剪贴板权限后再试。");
  });
})();
</script>
"""


def strip_image_slots(text: str) -> str:
    """去掉未替换的 image-slot 注释，避免进 HTML。"""
    return re.sub(
        r"<!--\s*image-slot[\s\S]*?-->",
        "",
        text,
        flags=re.IGNORECASE,
    )


def inline_format(raw: str) -> str:
    """转义后还原加粗、链接。整段只有加粗时由调用方走金句样式。"""
    parts: list[str] = []
    pattern = re.compile(r"\*\*(.+?)\*\*|\[([^\]]+)\]\(([^)]+)\)|`([^`]+)`")
    pos = 0
    for match in pattern.finditer(raw):
        parts.append(html.escape(raw[pos : match.start()]))
        if match.group(1) is not None:
            parts.append(
                f"<strong style='{STRONG_STYLE}'>{html.escape(match.group(1))}</strong>"
            )
        elif match.group(2) is not None:
            parts.append(
                f"<a href=\"{html.escape(match.group(3), quote=True)}\" "
                f"style=\"color:#576b95;text-decoration:none;\">"
                f"{html.escape(match.group(2))}</a>"
            )
        else:
            parts.append(html.escape(match.group(4)))
        pos = match.end()
    parts.append(html.escape(raw[pos:]))
    return "".join(parts)


def quote_block(text: str) -> str:
    inner = re.sub(r"^\*\*(.*)\*\*$", r"\1", text.strip())
    return (
        f"<p style=\"{QUOTE_STYLE}\">"
        f"<strong style='{STRONG_STYLE}'>{html.escape(inner)}</strong></p>"
    )


def is_pure_bold(text: str) -> bool:
    return bool(re.fullmatch(r"\*\*.+\*\*", text.strip()))


def convert_wechat(md_text: str) -> str:
    """输出带行内样式的 HTML，方便粘贴进公众号编辑器。"""
    lines = md_text.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    i = 0

    def flush_list(items: list[str], ordered: bool) -> None:
        if not items:
            return
        bits = []
        for n, item in enumerate(items, 1):
            prefix = f"{n}. " if ordered else "• "
            bits.append(prefix + inline_format(item))
        out.append(f"<p style=\"{LIST_STYLE}\">{'<br/>'.join(bits)}</p>")

    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            continue

        if stripped.startswith("- ") or stripped.startswith("* "):
            items: list[str] = []
            while i < len(lines) and (
                lines[i].strip().startswith("- ") or lines[i].strip().startswith("* ")
            ):
                items.append(lines[i].strip()[2:].strip())
                i += 1
            flush_list(items, ordered=False)
            continue

        if re.match(r"^\d+\.\s+", stripped):
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i].strip()):
                items.append(re.sub(r"^\d+\.\s+", "", lines[i].strip()))
                i += 1
            flush_list(items, ordered=True)
            continue

        img = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", stripped)
        if img:
            alt, src = img.group(1), img.group(2)
            out.append(
                f'<img src="{html.escape(src, quote=True)}" '
                f'alt="{html.escape(alt, quote=True)}" style="{IMG_STYLE}"/>'
            )
            i += 1
            continue

        if stripped.startswith("### "):
            out.append(f"<h3 style=\"{H3_STYLE}\">{inline_format(stripped[4:])}</h3>")
        elif stripped.startswith("## "):
            out.append(f"<h2 style=\"{H2_STYLE}\">{inline_format(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            out.append(f"<h1 style=\"{H1_STYLE}\">{inline_format(stripped[2:])}</h1>")
        elif stripped.startswith("> ") or is_pure_bold(stripped):
            text = stripped[2:].strip() if stripped.startswith("> ") else stripped
            out.append(quote_block(text))
        elif stripped == "---":
            out.append(
                '<p style="border:none;border-top:1px solid #eee;margin:24px 0;"></p>'
            )
        else:
            out.append(f"<p style=\"{P_STYLE}\">{inline_format(stripped)}</p>")
        i += 1

    return "\n".join(out)


def to_html_document(title: str, body: str) -> str:
    safe_title = html.escape(title or "文章")
    return (
        "<!DOCTYPE html>\n"
        '<html lang="zh-CN">\n'
        "<head>\n"
        '<meta charset="utf-8" />\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1" />\n'
        f"<title>{safe_title}</title>\n"
        f"<style>{CSS}</style>\n"
        "</head>\n"
        f'<body style="{BODY_STYLE}">\n'
        '<div class="toolbar">\n'
        '<span class="copy-hint">复制后可粘贴到公众号编辑器</span>\n'
        '<button type="button" class="copy-btn" id="copy-btn">一键复制</button>\n'
        "</div>\n"
        f'<div id="article" style="{CARD_STYLE}">\n{body}\n</div>\n'
        f"{COPY_SCRIPT}\n"
        "</body>\n"
        "</html>\n"
    )


def extract_title(md_text: str, fallback: str) -> str:
    for line in md_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def main() -> None:
    parser = argparse.ArgumentParser(description="Markdown → HTML（公众号成稿）")
    parser.add_argument("input", type=Path, help="输入 .md 路径")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="输出 .html 路径（默认与 md 同名同目录）",
    )
    args = parser.parse_args()

    md_path = args.input
    if not md_path.is_file():
        print(f"找不到文件: {md_path}", file=sys.stderr)
        sys.exit(1)

    raw = md_path.read_text(encoding="utf-8")
    text = strip_image_slots(raw).strip() + "\n"
    title = extract_title(text, md_path.stem)

    body = convert_wechat(text)

    out_path = args.output or md_path.with_suffix(".html")
    out_path.write_text(to_html_document(title, body), encoding="utf-8")
    print(out_path)


if __name__ == "__main__":
    main()
