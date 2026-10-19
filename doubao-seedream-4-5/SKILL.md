---
name: doubao-seedream-4-5
version: 1.0.0
display_name: 公众号抖音小红书文生图
display_name_en: Doubao Seedream 4.5 Image Generation
description: >-
  调用火山方舟 Doubao Seedream 4.5 文生图 / 图生图 / 组图 API（Model ID: doubao-seedream-4-5-251128）。
  当用户提到豆包生图、Seedream 4.5、文生图、图生图、多图融合、组图生成，或要生成/编辑图片时使用。
description_zh: >-
  基于火山方舟 Doubao Seedream 4.5 的文生图技能，支持文生图、图生图、多图融合与组图生成，
  并内置公众号、小红书、抖音等图文平台常用尺寸。
description_en: >-
  Text-to-image skill powered by Volcengine Ark Doubao Seedream 4.5. Supports
  text-to-image, image-to-image, multi-image fusion, and sequential image sets,
  with preset sizes for WeChat Official Accounts, Xiaohongshu, and Douyin.
---

# Doubao Seedream 4.5 图片生成

固定使用 **Seedream 4.5**，Model ID 不可替换为其他版本：

```
doubao-seedream-4-5-251128
```

官方文档：https://docs.volcengine.com/docs/ark/seedream-4-0-5-0?lang=zh

## 前置条件：API Key（.env）

密钥保存在技能包根目录 `.env`（已 gitignore），格式：

```
ARK_API_KEY=你的密钥
```

**读取优先级：** `--api-key` > 系统环境变量 > `.env`

### 用户尚未提供 Key 时

Agent **必须**按下列步骤引导用户获取，拿到后写入 `.env`，**不要编造图片**：

1. 打开火山引擎官网登录：https://console.volcengine.com/auth/login （手机号登录）
2. 完成实名认证：https://console.volcengine.com/user/authentication/detail/
3. 进入开通管理，开通 **Doubao-Seedream-4.5**（豆包生图可白嫖约 200 张）：  
   https://console.volcengine.com/ark/region:ark+cn-beijing/openManagement?COMPUTER_VISION=%7B%7D&LLM=%7B%7D&advancedActiveKey=model&tab=ComputerVision
4. 创建 API Key：  
   https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey?apikey=%7B%7D  
   点击「创建」，创建后复制 Key

用户给出 Key 后，立即写入并确认：

```bash
python scripts/generate.py --set-api-key 用户提供的密钥
```

或直接编辑 `.env` / 复制 `.env.example` 为 `.env` 后填写。

### 其他依赖

流式模式需要：`pip install requests`（非流式仅标准库即可）。

## 能力边界（4.5）

| 能力 | 支持 |
|------|------|
| 文生图 / 文生组图 | ✓ |
| 单图 / 多图生图 / 生组图 | ✓ |
| 流式输出 | ✓ |
| 联网搜索 | ✗ |
| 交互编辑 / 图层拆分 | ✗ |
| 输出格式 | 仅 jpeg（勿传 `output_format`） |
| 分辨率 | `2K` / `4K`（或宽高像素） |
| 提示词优化 | 仅 standard（勿设 `fast`） |

## 默认参数

调用时自动填充，除非用户明确指定：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `model` | `doubao-seedream-4-5-251128` | 固定 |
| `size` | `2K` | 可选 `4K` 或 `宽x高` |
| `response_format` | `url` | 或 `b64_json` |
| `watermark` | `false` | 用户要水印时改 `true` |
| `sequential_image_generation` | 省略 / `disabled` | 组图时用 `auto` |

## 工作流

按用户意图选场景，再调用 API 或脚本：

```
任务进度:
- [ ] 0. 确认 .env 中有 ARK_API_KEY；没有则按「前置条件」引导并 --set-api-key 写入
- [ ] 1. 确认场景（文生图 / 图生图 / 多图融合 / 组图）
- [ ] 2. 整理 prompt（≤300 汉字；主体+行为+环境+风格）
- [ ] 3. 准备参考图 URL 或 base64（如有）
- [ ] 4. 调用生成
- [ ] 5. 返回结果 URL，提醒 24 小时内保存
```

### 场景 A：文生图（单图）

```bash
python scripts/generate.py --prompt "你的提示词" --size 2K
```

### 场景 B：图生图 / 多图融合

```bash
# 单图编辑
python scripts/generate.py --prompt "将服装改为红色" --image "https://example.com/a.png"

# 多图融合（提示词中用 图1/图2 指代）
python scripts/generate.py --prompt "将图1的服装换为图2的服装" \
  --image "https://example.com/a.png" --image "https://example.com/b.png"
```

### 场景 C：组图

设置 `sequential_image_generation=auto`，并用 `max_images` 限制张数：

```bash
python scripts/generate.py --prompt "生成4张电影分镜：..." --sequential --max-images 4
```

### 场景 D：流式（组图可边生成边看）

```bash
python scripts/generate.py --prompt "..." --sequential --max-images 4 --stream
```

## Curl 模板（文生图）

```bash
curl https://ark.cn-beijing.volces.com/api/v3/images/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ARK_API_KEY" \
  -d '{
    "model": "doubao-seedream-4-5-251128",
    "prompt": "充满活力的特写编辑肖像，模特眼神犀利，头戴雕塑感帽子，色彩拼接丰富",
    "size": "2K",
    "response_format": "url",
    "watermark": false
  }'
```

## Prompt 要点

- 结构：`主体 + 行为 + 环境`，再补 `风格 / 色彩 / 光影 / 构图`
- 建议不超过 **300 汉字** 或 **600 英文单词**
- 指定宽高比时：在 prompt 里写「宽高比 16:9」并设 `size` 为 `2K`/`4K`；或直接 `size: "2848x1600"`
- 多参考图：用「图1」「图2」指代输入顺序
- **图文平台尺寸**（详见 [references/seedream-api.md](references/seedream-api.md)「图文平台常用尺寸」）：
  - 公众号封面 → `3136x1344`（21:9）
  - 公众号文章内配图 → `2848x1600`（16:9）
  - 小红书封面/配图 → `1728x2304`（3:4）

## 输入图限制

- 格式：jpeg / png / webp / bmp / tiff / gif / heic / heif
- 单张 ≤ 30 MB；宽高比 \[1/16, 16\]；总像素 ≤ 6000×6000
- 最多 **14** 张参考图
- 传入：公网 URL，或 `data:image/png;base64,...`（格式名小写）

## 结果处理

1. `response_format=url` 时，图片 URL **仅保留 24 小时**，告知用户及时下载
2. 组图遍历 `data[]` 输出全部 URL
3. 失败时展示 API 错误信息，勿伪造成功

## 详细参数

完整字段与 4.5 分辨率对照见 [references/seedream-api.md](references/seedream-api.md)。
