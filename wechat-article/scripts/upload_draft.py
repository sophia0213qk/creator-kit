#!/usr/bin/env python3
"""把本地公众号成稿上传到微信草稿箱，并用草稿详情接口校验。

仅有 md + 图片时：先调用 md_to_html.py 生成 html，再上传。
封面：永久素材 add_material（type=image），得到 thumb_media_id
正文图：uploadimg 后，把 HTML 里本地图片 src 替换为微信返回的 url，再 draft/add
凭证：GET /cgi-bin/token（调用 IP 必须在公众号 IP 白名单内）

用法:
  python scripts/upload_draft.py "YYYYMMDD-HHmm-文章名/文章名.md"
  python scripts/upload_draft.py "YYYYMMDD-HHmm-文章名/文章名.html"
  python scripts/upload_draft.py "YYYYMMDD-HHmm-文章名"
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import subprocess
import sys
import uuid
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.weixin.qq.com"
SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
MD_TO_HTML = SCRIPTS_DIR / "md_to_html.py"
ENV_PATH = SKILL_DIR / ".env"

GUIDE = """
未配置公众号凭证。请在技能包 .env 写入：

  WECHAT_APPID=你的AppID
  WECHAT_APPSECRET=你的AppSecret

获取位置：
1. 打开微信开发者平台 https://developers.weixin.qq.com/console/product
2. 进入对应公众号 → 基础信息，复制 AppID
3. 开发密钥里查看或重置 AppSecret（平台不回显旧密钥，忘了就重置）
4. 同一页「IP 白名单」填上本机出口 IP，否则获取 token 会返回 40164

文件：{env_path}
""".strip()


def load_dotenv(path: Path = ENV_PATH) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def http_json(method: str, url: str, body: dict | None = None, timeout: int = 60) -> dict:
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {e.code}: {err}") from e


def multipart_file(url: str, file_path: Path, field: str = "media") -> dict:
    boundary = "----WebKitFormBoundary" + uuid.uuid4().hex
    mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    file_bytes = file_path.read_bytes()
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{file_path.name}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode("utf-8")
    tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(
        url,
        data=head + file_bytes + tail,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"上传失败 HTTP {e.code}: {err}") from e


def explain_token_error(payload: dict) -> None:
    code = payload.get("errcode")
    msg = payload.get("errmsg", "")
    if code == 40164:
        raise SystemExit(
            "获取 access_token 失败：调用 IP 不在白名单（40164）。\n"
            "请到 https://developers.weixin.qq.com/console/product\n"
            "进入该公众号 → 基础信息 → 开发密钥 → IP 白名单，加入当前出口 IP 后再试。\n"
            f"微信返回：{msg}"
        )
    if code == 40243:
        raise SystemExit("AppSecret 已冻结（40243）。请到开发者平台解冻后再试。")
    if code in (40013, 40125, 41004):
        raise SystemExit(f"AppID 或 AppSecret 不正确（{code}）：{msg}")
    raise SystemExit(f"获取 access_token 失败：{json.dumps(payload, ensure_ascii=False)}")


def get_access_token(appid: str, secret: str) -> str:
    query = urllib.parse.urlencode(
        {"grant_type": "client_credential", "appid": appid, "secret": secret}
    )
    payload = http_json("GET", f"{API}/cgi-bin/token?{query}")
    if payload.get("errcode"):
        explain_token_error(payload)
    token = payload.get("access_token")
    if not token:
        explain_token_error(payload)
    return token


def raise_if_error(payload: dict, action: str) -> None:
    code = payload.get("errcode")
    if code not in (None, 0):
        raise SystemExit(f"{action}失败 {code}: {payload.get('errmsg', payload)}")


def upload_cover(token: str, image: Path) -> str:
    url = f"{API}/cgi-bin/material/add_material?access_token={urllib.parse.quote(token)}&type=image"
    payload = multipart_file(url, image)
    raise_if_error(payload, "上传封面")
    media_id = payload.get("media_id")
    if not media_id:
        raise SystemExit(f"上传封面未返回 media_id：{payload}")
    print(f"封面永久素材 media_id={media_id}", file=sys.stderr)
    return media_id


def upload_content_image(token: str, image: Path) -> str:
    if image.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        raise SystemExit(f"正文图只支持 jpg/png：{image.name}")
    if image.stat().st_size > 1024 * 1024:
        raise SystemExit(f"正文图必须小于 1MB：{image}（{image.stat().st_size} bytes）")
    url = f"{API}/cgi-bin/media/uploadimg?access_token={urllib.parse.quote(token)}"
    payload = multipart_file(url, image)
    raise_if_error(payload, f"上传正文图 {image.name}")
    wx_url = payload.get("url")
    if not wx_url:
        raise SystemExit(f"上传正文图未返回 url：{payload}")
    print(f"正文图 {image.name} → {wx_url}", file=sys.stderr)
    return wx_url


def extract_article_html(raw: str) -> str:
    match = re.search(
        r'<div id="article"[^>]*>([\s\S]*?)</div>\s*(?:<script|</body>)',
        raw,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    body = re.search(r"<body[^>]*>([\s\S]*)</body>", raw, flags=re.IGNORECASE)
    return (body.group(1) if body else raw).strip()


def extract_title(html_text: str, fallback: str) -> str:
    match = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", html_text, flags=re.IGNORECASE)
    if not match:
        return fallback[:32]
    text = re.sub(r"<[^>]+>", "", match.group(1))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 32:
        raise SystemExit(f"标题超过微信上限 32 字（当前 {len(text)}）：{text}")
    return text or fallback[:32]


def strip_body_title(html_text: str) -> str:
    """草稿 title 字段已单独提交，去掉正文里的首个 H1，避免双标题。"""
    return re.sub(
        r"<h1[^>]*>[\s\S]*?</h1>\s*",
        "",
        html_text,
        count=1,
        flags=re.IGNORECASE,
    ).strip()


def extract_digest(html_text: str, override: str | None) -> str:
    if override:
        return override[:120]
    texts: list[str] = []
    for para in re.findall(r"<p[^>]*>([\s\S]*?)</p>", html_text, flags=re.IGNORECASE):
        plain = re.sub(r"<[^>]+>", "", para)
        plain = re.sub(r"\s+", " ", plain).strip()
        if plain:
            texts.append(plain)
        if sum(len(t) for t in texts) >= 80:
            break
    digest = "".join(texts)
    return digest[:120]


def resolve_src(src: str, html_dir: Path) -> Path | None:
    src = src.strip().strip("'\"")
    if src.startswith(("http://", "https://", "data:")):
        return None
    path = (html_dir / src).resolve()
    if not path.is_file():
        raise SystemExit(f"找不到图片：{src}（相对于 {html_dir}）")
    return path


def replace_images(html_text: str, html_dir: Path, token: str) -> tuple[str, Path | None]:
    """正文图走 uploadimg；封面只收集路径，正文里去掉，避免重复展示且避开 1MB 限制。"""
    cover: Path | None = None
    cache: dict[str, str] = {}

    def repl(match: re.Match[str]) -> str:
        nonlocal cover
        tag = match.group(0)
        src_match = re.search(r'src="([^"]+)"', tag)
        if not src_match:
            return tag
        local = resolve_src(src_match.group(1), html_dir)
        if local is None:
            return tag
        if local.stem.lower() == "cover":
            if cover is None:
                cover = local
            return ""  # 封面用 thumb_media_id，不放正文
        key = str(local)
        if key not in cache:
            cache[key] = upload_content_image(token, local)
        return tag.replace(src_match.group(1), cache[key], 1)

    new_html = re.sub(r"<img\b[^>]*>", repl, html_text, flags=re.IGNORECASE)
    new_html = re.sub(r"<p[^>]*>\s*</p>", "", new_html, flags=re.IGNORECASE)
    if cover is None:
        for name in ("cover.jpg", "cover.jpeg", "cover.png"):
            candidate = html_dir / "images" / name
            if candidate.is_file():
                cover = candidate
                break
    return new_html, cover


def add_draft(token: str, article: dict) -> str:
    payload = http_json(
        "POST",
        f"{API}/cgi-bin/draft/add?access_token={urllib.parse.quote(token)}",
        {"articles": [article]},
    )
    raise_if_error(payload, "新增草稿")
    media_id = payload.get("media_id")
    if not media_id:
        raise SystemExit(f"新增草稿未返回 media_id：{payload}")
    return media_id


def verify_draft(token: str, media_id: str, title: str) -> None:
    payload = http_json(
        "POST",
        f"{API}/cgi-bin/draft/get?access_token={urllib.parse.quote(token)}",
        {"media_id": media_id},
    )
    raise_if_error(payload, "获取草稿详情")
    items = payload.get("news_item") or []
    if not items:
        raise SystemExit(f"草稿详情为空，可能未写入成功：{payload}")
    got = (items[0].get("title") or "").strip()
    if got != title:
        raise SystemExit(f"草稿校验失败：期望标题「{title}」，实际「{got}」")
    print(f"草稿校验成功 title={got} media_id={media_id}")


def run_md_to_html(md_path: Path) -> Path:
    """只有 md 时先转 html，再上传。"""
    if not MD_TO_HTML.is_file():
        raise SystemExit(f"找不到转换脚本：{MD_TO_HTML}")
    if not md_path.is_file():
        raise SystemExit(f"找不到 md：{md_path}")
    out = md_path.with_suffix(".html")
    print(f"仅有 md，先转 html：{md_path.name} → {out.name}", file=sys.stderr)
    proc = subprocess.run(
        [sys.executable, str(MD_TO_HTML), str(md_path), "-o", str(out)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise SystemExit(f"md_to_html 失败：{err or proc.returncode}")
    if not out.is_file():
        raise SystemExit(f"md_to_html 未生成：{out}")
    return out


def locate_md(dir_path: Path) -> Path | None:
    mds = sorted(p for p in dir_path.glob("*.md") if p.is_file())
    return mds[0] if mds else None


def locate_html(target: Path) -> Path:
    """接受目录 / .md / .html；缺 html 时自动 md_to_html。"""
    target = target.resolve()
    if target.is_dir():
        htmls = sorted(
            p
            for p in target.glob("*.html")
            if p.is_file() and not p.name.endswith(".wx.html")
        )
        if htmls:
            return htmls[0]
        md = locate_md(target)
        if md:
            return run_md_to_html(md)
        raise SystemExit(f"目录里没有 html 也没有 md：{target}")

    if not target.is_file():
        raise SystemExit(f"找不到文件：{target}")

    if target.suffix.lower() == ".md":
        sibling = target.with_suffix(".html")
        if sibling.is_file():
            return sibling
        return run_md_to_html(target)

    return target


def write_wx_html(html_path: Path, content: str) -> Path:
    """把替换过微信图床链接的正文落盘，便于核对上传内容。"""
    out = html_path.with_name(html_path.stem + ".wx.html")
    out.write_text(
        "<!DOCTYPE html>\n<html lang=\"zh-CN\"><head>"
        "<meta charset=\"utf-8\"/><title>wechat-draft</title></head><body>\n"
        f"{content}\n</body></html>\n",
        encoding="utf-8",
    )
    print(f"已写入替换后的正文：{out}", file=sys.stderr)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="上传公众号文章到草稿箱并校验")
    parser.add_argument(
        "target",
        type=Path,
        help="成稿目录、.md 或 .html（仅有 md 时会先转 html）",
    )
    parser.add_argument("--digest", default="", help="摘要，默认取正文开头，不超过 120 字")
    args = parser.parse_args()

    load_dotenv()
    appid = os.getenv("WECHAT_APPID", "").strip()
    secret = os.getenv("WECHAT_APPSECRET", "").strip()
    if not appid or not secret:
        print(GUIDE.format(env_path=ENV_PATH), file=sys.stderr)
        sys.exit(1)

    html_path = locate_html(args.target)
    raw = html_path.read_text(encoding="utf-8")
    article_html = extract_article_html(raw)
    title = extract_title(article_html, html_path.stem)
    # 微信草稿顶部已有标题字段，正文不再保留 H1
    article_html = strip_body_title(article_html)
    token = get_access_token(appid, secret)
    # 上传正文图后，把本地 images/... 替换为微信返回的 url，再写入草稿
    content, cover = replace_images(article_html, html_path.parent, token)
    write_wx_html(html_path, content)
    if cover is None:
        raise SystemExit("缺少封面图 images/cover.jpg（或 HTML 中文件名 stem 为 cover 的图片）")
    thumb_media_id = upload_cover(token, cover)
    digest = extract_digest(content, args.digest or None)
    # 不传 author：公众号顶部已显示账号名，再写 author 会出现双作者

    media_id = add_draft(
        token,
        {
            "article_type": "news",
            "title": title,
            "author": "",
            "digest": digest,
            "content": content,
            "thumb_media_id": thumb_media_id,
            "need_open_comment": 0,
            "only_fans_can_comment": 0,
        },
    )
    print(f"已写入草稿箱 media_id={media_id}", file=sys.stderr)
    verify_draft(token, media_id, title)


if __name__ == "__main__":
    main()
