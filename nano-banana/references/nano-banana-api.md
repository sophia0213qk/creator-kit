# Nano Banana API 参考

Base：`https://duomiapi.com`  
Auth：请求头 `Authorization: <DUOMI_API_KEY>`（也可放 payload/url 的 key，本技能统一用 Header）

文档：
- 文生图：https://s.apifox.cn/b924931e-29c0-4127-b025-d68c90285060/api-346130262
- 图生图：https://s.apifox.cn/b924931e-29c0-4127-b025-d68c90285060/api-346293340
- 查任务：https://s.apifox.cn/b924931e-29c0-4127-b025-d68c90285060/api-346151382
- 产品页：https://duomiapi.com/doc/85 · https://duomiapi.com/doc/86

## 1. 文生图

`POST /api/gemini/nano-banana`

| 字段 | 必填 | 说明 |
|------|------|------|
| `model` | ✓ | 见模型表 |
| `prompt` | ✓ | 提示词 |
| `aspect_ratio` | | `auto` / `1:1` / `2:3` / `3:2` / `3:4` / `4:3` / `4:5` / `5:4` / `9:16` / `16:9` / `21:9` |
| `image_size` | | `1K` / `2K` / `4K`（**K 大写**；部分模型仅 1K） |
| `oversea` | | bool，示例为 `false` |

提交成功：

```json
{
  "code": 200,
  "msg": "success",
  "data": { "task_id": "e64e7980-27af-e5c2-c775-7860a215f33a" }
}
```

## 2. 图生图（图片编辑）

`POST /api/gemini/nano-banana-edit`

| 字段 | 必填 | 说明 |
|------|------|------|
| `model` | ✓ | 同文生图 |
| `prompt` | ✓ | 编辑指令 |
| `image_urls` | ✓ | 字符串数组，最多 10 张；**仅 URL，不支持 base64** |
| `aspect_ratio` | | 不传则自适应；**单参考图尽量不要传** |
| `image_size` | | `1K` / `2K` / `4K`（pro / nano 2 支持） |

## 3. 查询任务状态

`GET /api/gemini/nano-banana/{id}`

| state | 含义 |
|-------|------|
| `pending` | 队列中 |
| `running` | 生成中 |
| `succeeded` | 成功 → 读 `data.data.images[].url` |
| `error` | 失败 → 读 `data.msg` |

成功示例要点：

```json
{
  "code": 200,
  "data": {
    "task_id": "...",
    "state": "succeeded",
    "data": {
      "images": [
        { "url": "https://cdn3.dmiapi.com/....jpeg", "file_name": "output.jpeg" }
      ],
      "description": "..."
    },
    "msg": "",
    "action": "generate"
  }
}
```

建议轮询：间隔 2–3 秒，超时约 180 秒。

## 模型与分辨率

| 名称 | Model ID | 分辨率 | 约价/次 |
|------|----------|--------|---------|
| nano-banana | `gemini-2.5-flash-image` | 1K | 0.05 |
| nano-banana-pro | `gemini-3-pro-image-preview` | 1K/2K/4K | 0.15 |
| nano-banana-2 | `gemini-3.1-flash-image-preview` | 1K/2K/4K | 0.1 |
| nano-banana-2 lite | `gemini-3.1-flash-lite-image-preview` | 1K | 0.05 |
| nano-banana-2.1 | `gemini-nano-banana-2.1` | 1K/2K/4K | 0.08 |

限流（产品页）：文生图约 1 秒 10 次；图生图约 1 秒 100 次。

## 手帐拼贴宽高比建议

| 用途 | aspect_ratio |
|------|----------------|
| 手帐竖页 / 小红书感 | `3:4` |
| 方贴 / 贴纸 | `1:1` |
| 横版展开手帐 | `16:9` 或 `3:2` |
| 手机全屏竖图 | `9:16` |

## Curl 示例

文生图：

```bash
curl --location 'https://duomiapi.com/api/gemini/nano-banana' \
  --header "Authorization: $DUOMI_API_KEY" \
  --header 'Content-Type: application/json' \
  --data '{
    "model": "gemini-3-pro-image-preview",
    "prompt": "手帐拼贴风，撕边拍立得与和纸胶带，温暖纸张纹理",
    "aspect_ratio": "3:4",
    "image_size": "2K",
    "oversea": false
  }'
```

查任务：

```bash
curl --location "https://duomiapi.com/api/gemini/nano-banana/{task_id}" \
  --header "Authorization: $DUOMI_API_KEY"
```
