#!/usr/bin/env python3
"""Doubao Seedream 4.5 image generation helper.

API Key 优先读技能包目录下的 .env（ARK_API_KEY），其次读系统环境变量。
流式模式可选：pip install requests
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
MODEL_ID = "doubao-seedream-4-5-251128"
SKILL_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = SKILL_DIR / ".env"

API_KEY_GUIDE = """
未找到 ARK_API_KEY。请按以下步骤获取，并写入本技能包的 .env 文件：

1. 打开火山引擎官网登录：
   https://console.volcengine.com/auth/login
   使用手机号登录。

2. 完成实名认证：
   https://console.volcengine.com/user/authentication/detail/

3. 进入开通管理，开通 Doubao-Seedream-4.5（豆包生图模型可白嫖约 200 张）：
   https://console.volcengine.com/ark/region:ark+cn-beijing/openManagement?COMPUTER_VISION=%7B%7D&LLM=%7B%7D&advancedActiveKey=model&tab=ComputerVision

4. 创建 API Key：
   https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey?apikey=%7B%7D
   点击「创建」按钮，创建后即可拿到 API Key。

拿到 Key 后任选一种方式写入：
  A) 编辑文件 {env_path}，写入一行：
     ARK_API_KEY=你的密钥
  B) 运行：
     python scripts/generate.py --set-api-key 你的密钥
""".strip()


def load_dotenv(path: Path = ENV_PATH) -> dict[str, str]:
    """从 .env 加载 KEY=VALUE，不覆盖已有环境变量。"""
    loaded: dict[str, str] = {}
    if not path.is_file():
        return loaded
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if not key:
            continue
        loaded[key] = value
        if key not in os.environ:
            os.environ[key] = value
    return loaded


def save_api_key(api_key: str, path: Path = ENV_PATH) -> None:
    """把 ARK_API_KEY 写入 .env（已有则更新，保留其他行）。"""
    api_key = api_key.strip()
    lines: list[str] = []
    found = False
    if path.is_file():
        for raw in path.read_text(encoding="utf-8").splitlines():
            if raw.strip().startswith("ARK_API_KEY="):
                lines.append(f"ARK_API_KEY={api_key}")
                found = True
            else:
                lines.append(raw)
    if not found:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(f"ARK_API_KEY={api_key}")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    os.environ["ARK_API_KEY"] = api_key


def resolve_api_key(cli_key: str | None = None) -> str | None:
    """优先级：--api-key > 环境变量 > .env。"""
    load_dotenv()
    if cli_key and cli_key.strip():
        return cli_key.strip()
    key = os.getenv("ARK_API_KEY", "").strip()
    return key or None


def print_api_key_guide() -> None:
    print(API_KEY_GUIDE.format(env_path=ENV_PATH), file=sys.stderr)


def build_body(args: argparse.Namespace) -> dict:
    body: dict = {
        "model": MODEL_ID,
        "prompt": args.prompt,
        "size": args.size,
        "response_format": args.response_format,
        "watermark": args.watermark,
    }
    if args.image:
        body["image"] = args.image[0] if len(args.image) == 1 else args.image
    if args.sequential:
        body["sequential_image_generation"] = "auto"
        body["sequential_image_generation_options"] = {
            "max_images": args.max_images
        }
    if args.stream:
        body["stream"] = True
    return body


def request_json(body: dict, api_key: str) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode("utf-8"))


def request_stream(body: dict, api_key: str) -> None:
    try:
        import requests
    except ImportError:
        print(
            "流式模式需要 requests：pip install requests",
            file=sys.stderr,
        )
        sys.exit(1)

    with requests.post(
        API_URL,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        json=body,
        stream=True,
        timeout=300,
    ) as resp:
        if resp.status_code >= 400:
            print(resp.text, file=sys.stderr)
            sys.exit(1)
        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                event = json.loads(payload)
            except json.JSONDecodeError:
                print(line)
                continue
            etype = event.get("type", "")
            if etype == "image_generation.partial_succeeded":
                print(
                    f"OK size={event.get('size')} url={event.get('url')}"
                )
            elif etype == "image_generation.partial_failed":
                print(f"FAIL {event.get('error')}", file=sys.stderr)
            elif etype == "image_generation.completed":
                print(f"DONE usage={event.get('usage')}")
            else:
                print(json.dumps(event, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate images with Doubao Seedream 4.5"
    )
    parser.add_argument("--prompt", help="文本提示词")
    parser.add_argument(
        "--image",
        action="append",
        default=[],
        help="参考图 URL 或 data URL，可重复传入多张",
    )
    parser.add_argument("--size", default="2K", help="2K / 4K / 宽x高")
    parser.add_argument(
        "--response-format",
        default="url",
        choices=["url", "b64_json"],
    )
    parser.add_argument(
        "--watermark",
        action="store_true",
        help="添加「AI生成」水印",
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="开启组图 (sequential_image_generation=auto)",
    )
    parser.add_argument(
        "--max-images",
        type=int,
        default=4,
        help="组图最大张数（需配合 --sequential）",
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="流式输出",
    )
    parser.add_argument(
        "--api-key",
        help="本次使用的 API Key（不会自动写入 .env，除非同时用 --set-api-key）",
    )
    parser.add_argument(
        "--set-api-key",
        metavar="KEY",
        help="将 API Key 写入技能包 .env 后退出（或与 --prompt 一起用于生图）",
    )
    args = parser.parse_args()

    if args.set_api_key:
        save_api_key(args.set_api_key)
        print(f"已写入 {ENV_PATH}", file=sys.stderr)
        if not args.prompt:
            return

    api_key = resolve_api_key(args.api_key or args.set_api_key)
    if not api_key:
        print_api_key_guide()
        sys.exit(1)

    if not args.prompt:
        parser.error("生图时需要 --prompt；仅保存 Key 请用 --set-api-key")

    body = build_body(args)

    if args.stream:
        request_stream(body, api_key)
        return

    try:
        result = request_json(body, api_key)
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        print(f"HTTP {e.code}: {err}", file=sys.stderr)
        sys.exit(1)

    data = result.get("data") or []
    if not data:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(1)

    for i, item in enumerate(data, 1):
        url = item.get("url") or ""
        size = item.get("size") or ""
        b64 = item.get("b64_json")
        if url:
            print(f"[{i}] size={size} url={url}")
        elif b64:
            print(f"[{i}] size={size} b64_len={len(b64)}")
        else:
            print(f"[{i}] {json.dumps(item, ensure_ascii=False)}")

    print(
        "提示：url 结果仅保留约 24 小时，请及时下载保存。",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
