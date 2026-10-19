#!/usr/bin/env python3
"""Nano Banana 文生图 / 图生图（多米 API），默认偏向手帐拼贴风。

需配置 DUOMI_API_KEY（.env / 环境变量 / --set-api-key）。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://duomiapi.com"
TXT2IMG_URL = f"{BASE}/api/gemini/nano-banana"
EDIT_URL = f"{BASE}/api/gemini/nano-banana-edit"
TASK_URL = f"{BASE}/api/gemini/nano-banana/{{task_id}}"

DEFAULT_MODEL = "gemini-3-pro-image-preview"
SKILL_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = SKILL_DIR / ".env"

COLLAGE_SUFFIX = (
    "手帐拼贴风 scrapbook collage，混合媒介 mixed media，"
    "撕边纸 scrap paper edges，和纸胶带 washi tape，拍立得相纸 polaroid frames，"
    "手写字体 handwritten notes，贴纸 stickers，纸张纹理 paper texture，"
    "剪贴簿布局 flat lay，温暖柔和色调，艺术感强，非写实摄影"
)

API_KEY_GUIDE = """
未找到 DUOMI_API_KEY。请按以下步骤获取，并写入本技能包的 .env：

1. 登录多米 API：
   https://duomiapi.com/
2. 充值（香蕉生图按量计费，需有余额才能调用）
3. 打开令牌页获取 API Key：
   https://duomiapi.com/console/token

拿到 Key 后：
  A) 编辑 {env_path}，写入：
     DUOMI_API_KEY=你的密钥
  B) 或运行：
     python scripts/generate.py --set-api-key 你的密钥
""".strip()

MODEL_ALIASES = {
    "nano-banana": "gemini-2.5-flash-image",
    "nano-banana-pro": "gemini-3-pro-image-preview",
    "pro": "gemini-3-pro-image-preview",
    "nano-banana-2": "gemini-3.1-flash-image-preview",
    "nano-banana-2-lite": "gemini-3.1-flash-lite-image-preview",
    "lite": "gemini-3.1-flash-lite-image-preview",
    "nano-banana-2.1": "gemini-nano-banana-2.1",
    "2.1": "gemini-nano-banana-2.1",
}


def load_dotenv(path: Path = ENV_PATH) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def save_api_key(api_key: str, path: Path = ENV_PATH) -> None:
    api_key = api_key.strip()
    lines: list[str] = []
    found = False
    if path.is_file():
        for raw in path.read_text(encoding="utf-8").splitlines():
            if raw.strip().startswith("DUOMI_API_KEY="):
                lines.append(f"DUOMI_API_KEY={api_key}")
                found = True
            else:
                lines.append(raw)
    if not found:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(f"DUOMI_API_KEY={api_key}")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    os.environ["DUOMI_API_KEY"] = api_key


def resolve_api_key(cli_key: str | None = None) -> str | None:
    load_dotenv()
    if cli_key and cli_key.strip():
        return cli_key.strip()
    return os.getenv("DUOMI_API_KEY", "").strip() or None


def resolve_model(name: str) -> str:
    key = name.strip()
    return MODEL_ALIASES.get(key, MODEL_ALIASES.get(key.lower(), key))


def http_json(
    method: str,
    url: str,
    api_key: str,
    body: dict | None = None,
    timeout: int = 120,
) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {
        "Authorization": api_key,
        "Accept": "application/json",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {e.code}: {err}") from e


def enrich_prompt(prompt: str, collage: bool) -> str:
    if not collage:
        return prompt
    if "拼贴" in prompt or "scrapbook" in prompt.lower() or "collage" in prompt.lower():
        return prompt
    return f"{prompt.rstrip('，,。. ')}，{COLLAGE_SUFFIX}"


def submit_txt2img(api_key: str, args: argparse.Namespace) -> str:
    body: dict = {
        "model": resolve_model(args.model),
        "prompt": enrich_prompt(args.prompt, not args.no_collage),
        "oversea": args.oversea,
    }
    if args.aspect_ratio:
        body["aspect_ratio"] = args.aspect_ratio
    if args.image_size:
        body["image_size"] = args.image_size
    result = http_json("POST", TXT2IMG_URL, api_key, body)
    if result.get("code") != 200:
        raise SystemExit(json.dumps(result, ensure_ascii=False, indent=2))
    task_id = (result.get("data") or {}).get("task_id")
    if not task_id:
        raise SystemExit(json.dumps(result, ensure_ascii=False, indent=2))
    return task_id


def submit_edit(api_key: str, args: argparse.Namespace) -> str:
    if not args.image_url:
        raise SystemExit("图生图需要至少一个 --image-url")
    body: dict = {
        "model": resolve_model(args.model),
        "prompt": enrich_prompt(args.prompt, not args.no_collage),
        "image_urls": args.image_url,
    }
    # 单参考图默认不传 aspect_ratio（文档建议自适应）
    if args.aspect_ratio:
        body["aspect_ratio"] = args.aspect_ratio
    if args.image_size:
        body["image_size"] = args.image_size
    result = http_json("POST", EDIT_URL, api_key, body)
    if result.get("code") != 200:
        raise SystemExit(json.dumps(result, ensure_ascii=False, indent=2))
    task_id = (result.get("data") or {}).get("task_id")
    if not task_id:
        raise SystemExit(json.dumps(result, ensure_ascii=False, indent=2))
    return task_id


def poll_task(
    api_key: str,
    task_id: str,
    interval: float = 2.5,
    timeout: float = 180.0,
) -> dict:
    url = TASK_URL.format(task_id=task_id)
    deadline = time.time() + timeout
    last: dict = {}
    while time.time() < deadline:
        last = http_json("GET", url, api_key, None, timeout=60)
        data = last.get("data") or {}
        state = data.get("state") or ""
        print(f"task={task_id} state={state}", file=sys.stderr)
        if state == "succeeded":
            return last
        if state == "error":
            msg = data.get("msg") or last.get("msg") or "unknown error"
            raise SystemExit(f"任务失败: {msg}\n{json.dumps(last, ensure_ascii=False, indent=2)}")
        time.sleep(interval)
    raise SystemExit(
        f"轮询超时（{timeout}s）。可稍后: python scripts/generate.py --task-id {task_id}"
    )


def print_images(result: dict) -> None:
    data = result.get("data") or {}
    inner = data.get("data") or {}
    images = inner.get("images") or []
    if not images:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    for i, item in enumerate(images, 1):
        print(f"[{i}] {item.get('file_name', '')} {item.get('url', '')}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Nano Banana 文生图/图生图")
    parser.add_argument("--prompt", help="提示词 / 编辑指令")
    parser.add_argument(
        "--edit",
        action="store_true",
        help="图生图模式（nano-banana-edit）",
    )
    parser.add_argument(
        "--image-url",
        action="append",
        default=[],
        help="参考图 URL，可重复；仅支持链接",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="模型 ID 或别名 pro / nano-banana-2 / 2.1 等",
    )
    parser.add_argument(
        "--aspect-ratio",
        default="3:4",
        help="宽高比；图生图单图默认不传，除非 --force-aspect",
    )
    parser.add_argument(
        "--force-aspect",
        action="store_true",
        help="图生图单参考图时仍传 aspect_ratio",
    )
    parser.add_argument("--image-size", default="2K", help="1K / 2K / 4K")
    parser.add_argument(
        "--oversea",
        action="store_true",
        help="文生图 oversea=true",
    )
    parser.add_argument(
        "--no-collage",
        action="store_true",
        help="不自动追加手帐拼贴风格词",
    )
    parser.add_argument("--task-id", help="仅查询已有任务")
    parser.add_argument("--no-wait", action="store_true", help="只提交不轮询")
    parser.add_argument("--poll-interval", type=float, default=2.5)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--api-key", help="本次使用的 Key")
    parser.add_argument("--set-api-key", metavar="KEY", help="写入 .env 后退出或继续生图")
    args = parser.parse_args()

    if args.set_api_key:
        save_api_key(args.set_api_key)
        print(f"已写入 {ENV_PATH}", file=sys.stderr)
        if not args.prompt and not args.task_id:
            return

    api_key = resolve_api_key(args.api_key or args.set_api_key)
    if not api_key:
        print(API_KEY_GUIDE.format(env_path=ENV_PATH), file=sys.stderr)
        sys.exit(1)

    if args.task_id:
        result = poll_task(api_key, args.task_id, args.poll_interval, args.timeout)
        print_images(result)
        return

    if not args.prompt:
        parser.error("需要 --prompt，或使用 --task-id / --set-api-key")

    # 文生图默认 3:4；若用户传空字符串则不带该字段
    if args.aspect_ratio == "":
        args.aspect_ratio = None

    if args.edit:
        # 单图且未 force：提交时去掉默认 3:4
        if len(args.image_url) == 1 and not args.force_aspect:
            args.aspect_ratio = None
        task_id = submit_edit(api_key, args)
    else:
        task_id = submit_txt2img(api_key, args)

    print(f"task_id={task_id}", file=sys.stderr)
    if args.no_wait:
        print(task_id)
        return

    result = poll_task(api_key, task_id, args.poll_interval, args.timeout)
    print_images(result)


if __name__ == "__main__":
    main()
