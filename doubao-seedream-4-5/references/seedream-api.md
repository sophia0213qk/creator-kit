# Seedream 4.5 API 参考

Endpoint: `POST https://ark.cn-beijing.volces.com/api/v3/images/generations`  
Auth: `Authorization: Bearer $ARK_API_KEY`  
Model: `doubao-seedream-4-5-251128`

## 请求字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `model` | string | ✓ | 固定 `doubao-seedream-4-5-251128` |
| `prompt` | string | ✓ | 文本描述 |
| `image` | string \| string[] | | 参考图 URL 或 base64；多图用数组 |
| `size` | string | | `2K` / `4K`，或 `宽x高`（如 `2048x2048`） |
| `response_format` | string | | `url`（默认）或 `b64_json` |
| `watermark` | bool | | `true` 右下角「AI生成」水印 |
| `sequential_image_generation` | string | | `auto` 开启组图；`disabled` 关闭 |
| `sequential_image_generation_options.max_images` | int | | 组图最大张数 |
| `stream` | bool | | `true` 流式返回 |

**不要传（4.5 不支持或无效）：**

- `output_format`（固定 jpeg）
- `tools` / `web_search`（无联网搜索）
- `optimize_prompt_options.mode: "fast"`（仅 standard）

## size：分辨率档位（推荐）

在 prompt 中描述宽高比，`size` 用档位，由模型映射像素：

| 宽高比 | 2K | 4K |
|--------|-----|-----|
| 1:1 | 2048×2048 | 4096×4096 |
| 4:3 | 2304×1728 | 4704×3520 |
| 3:4 | 1728×2304 | 3520×4704 |
| 16:9 | 2848×1600 | 5504×3040 |
| 9:16 | 1600×2848 | 3040×5504 |
| 3:2 | 2496×1664 | 4992×3328 |
| 2:3 | 1664×2496 | 3328×4992 |
| 21:9 | 3136×1344 | 6240×2656 |

## 图文平台常用尺寸（Seedream 4.5 / 2K 映射）

生图时推荐：`size` 用档位 `"2K"`，并在 prompt 中写明宽高比；或直接传下表「建议 size」像素值。需要更高清可改用 `4K` 同比例。

### 微信公众号

| 用途 | 宽高比 | 建议 size（2K） | 说明 |
|------|--------|-----------------|------|
| **封面（推荐）** | **21:9** | **`3136x1344`** | 公众号头条/次条封面横幅，信息流展示友好 |
| **文章内配图** | **16:9** | **`2848x1600`** | 正文插图，横版阅读舒适 |
| 文章内配图（方图） | 1:1 | `2048x2048` | 单品、对比、表情包类插图 |
| 文章内配图（竖图） | 3:4 | `1728x2304` | 长文中的竖向插画、海报感配图 |

调用示例：

```json
{ "size": "3136x1344", "prompt": "公众号封面，宽高比21:9，..." }
```

或：

```json
{ "size": "2K", "prompt": "公众号文章内配图，宽高比16:9，..." }
```

### 小红书

| 用途 | 宽高比 | 建议 size（2K） | 说明 |
|------|--------|-----------------|------|
| **笔记封面 / 配图（推荐）** | **3:4** | **`1728x2304`** | 信息流占屏最大；封面与内页尽量统一比例 |
| 笔记方图 | 1:1 | `2048x2048` | 产品正面、对比图 |
| 笔记横图 | 4:3 | `2304x1728` | 风景/全景；封面不优先（信息流偏小） |
| 视频向竖屏封面 | 9:16 | `1600x2848` | 偏视频封面/全屏竖图 |

说明：平台上传常用 1080×1440（3:4），用 Seedream 出 `1728x2304` 后再压缩即可，清晰度更稳。

### 其他常见图文场景

| 平台 / 场景 | 宽高比 | 建议 size（2K） | 说明 |
|-------------|--------|-----------------|------|
| 抖音 / 视频号 竖屏封面 | 9:16 | `1600x2848` | 竖屏信息流 |
| 抖音 / 视频号 横屏封面 | 16:9 | `2848x1600` | 横屏内容封面 |
| 朋友圈 / 通用方图 | 1:1 | `2048x2048` | 晒图、头像感主图 |
| 海报 / 印刷感竖版 | 2:3 | `1664x2496` | 偏海报、长图海报 |
| 横版 Banner | 21:9 | `3136x1344` | 与公众号封面同规格 |

**Agent 选尺寸规则：** 用户说「公众号封面」→ `3136x1344`（21:9）；「公众号配图/插图」→ `2848x1600`（16:9）；「小红书」→ 默认 `1728x2304`（3:4），除非用户指定方图/横图。

## size：直接指定像素

- 总像素范围：`[2560×1440, 4096×4096]`（约 3686400 ~ 16777216）
- 宽高比：`[1/16, 16]`
- 示例：`"size": "2048x2048"`

档位与像素值不可混用。

## 响应（非流式）

```json
{
  "data": [
    { "url": "https://...", "size": "2048x2048" }
  ],
  "usage": { ... }
}
```

组图时 `data` 含多张。URL 24 小时后失效。

## 流式事件类型

| type | 含义 |
|------|------|
| `image_generation.partial_succeeded` | 单张成功（含 url / size） |
| `image_generation.partial_failed` | 单张失败 |
| `image_generation.completed` | 全部完成（含 usage） |
| `image_generation.partial_image` | 部分图像数据（b64） |

## Python（arkruntime）

```python
import os
from arkruntime import Ark

client = Ark(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.getenv("ARK_API_KEY"),
)

resp = client.images.generate(
    model="doubao-seedream-4-5-251128",
    prompt="一座安静的湖边小屋，清晨薄雾，电影感光影",
    size="2K",
    response_format="url",
    watermark=False,
)
print(resp.data[0].url)
```

## Python（OpenAI 兼容）

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.getenv("ARK_API_KEY"),
)

resp = client.images.generate(
    model="doubao-seedream-4-5-251128",
    prompt="一座安静的湖边小屋，清晨薄雾，电影感光影",
    size="2K",
    response_format="url",
    extra_body={"watermark": False},
)
print(resp.data[0].url)
```

## 限流

账号下同模型版本 IPM（张/分钟）上限：**500**。超限会报错。
