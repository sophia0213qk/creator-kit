---
name: duomi-banana-collage
version: 1.0.0
display_name: 多米香蕉手帐拼贴
display_name_en: Nano Banana Scrapbook Collage Image Gen
description: >-
  调用多米 API Nano Banana 文生图 / 图生图（手帐拼贴、手绘、艺术感强画面首选）。
  当用户提到 nano-banana、香蕉生图、手帐、拼贴风、手绘插画、贴纸拼贴，或要做艺术感强的文生图/图生图时使用。
description_zh: >-
  基于多米 API Nano Banana 的文生图与图生图技能，专精手帐拼贴、手绘与艺术感强画面；
  支持异步任务提交与轮询取图。
description_en: >-
  Nano Banana text-to-image and image-to-image via Duomi API, optimized for
  scrapbook collage, hand-drawn, and strongly artistic visuals; async submit + poll.
---

# Nano Banana 手帐拼贴生图

本技能走 [多米 API](https://duomiapi.com/doc/85) Nano Banana 系列，**擅长手帐拼贴 / 手绘 / 艺术感强画面**。  
对接文档：[文生图](https://s.apifox.cn/b924931e-29c0-4127-b025-d68c90285060/api-346130262) · [图生图](https://s.apifox.cn/b924931e-29c0-4127-b025-d68c90285060/api-346293340) · [查任务](https://s.apifox.cn/b924931e-29c0-4127-b025-d68c90285060/api-346151382)

## 何时用本技能（而非 Seedream）

| 场景 | 用 Nano Banana |
|------|----------------|
| 手帐 / 拼贴 / 贴纸 / washi tape | ✓ 首选 |
| 手绘感、纸张纹理、撕边、胶带 | ✓ |
| 艺术插画、混合媒介、剪贴簿 | ✓ |
| 写实摄影、公众号封面偏真实感 | 改用 Seedream 4.5 |

## 前置条件：API Key（.env）

技能包根目录 `.env`：

```
DUOMI_API_KEY=你的密钥
```

**读取优先级：** `--api-key` > 环境变量 `DUOMI_API_KEY` > `.env`

### 用户尚未提供 Key 时

`.env` 里没有 `DUOMI_API_KEY`（或值为空）时，Agent **必须**按下列步骤提醒用户，拿到后再写入 `.env`，**不要编造图片**：

1. 登录多米 API：https://duomiapi.com/
2. 充值（香蕉生图按量计费，需有余额才能调用）
3. 打开令牌页获取 API Key：https://duomiapi.com/console/token
4. 把密钥交给 Agent，或自行写入 `.env`

```bash
python scripts/generate.py --set-api-key 用户提供的密钥
```

## 默认模型与参数

手帐拼贴默认用质量更好的 **nano-banana-pro**：

| 项 | 默认值 |
|----|--------|
| `model` | `gemini-3-pro-image-preview` |
| `aspect_ratio` | `3:4`（手帐竖版）；用户指定则覆盖 |
| `image_size` | `2K`（pro / nano-2 / 2.1 支持；基础款仅 1K） |
| `oversea` | `false`（仅文生图） |

可选模型：

| 名称 | Model ID | 分辨率 | 约价 |
|------|----------|--------|------|
| nano-banana | `gemini-2.5-flash-image` | 1K | 0.05 |
| nano-banana-pro（默认） | `gemini-3-pro-image-preview` | 1K/2K/4K | 0.15 |
| nano-banana-2 | `gemini-3.1-flash-image-preview` | 1K/2K/4K | 0.1 |
| nano-banana-2 lite | `gemini-3.1-flash-lite-image-preview` | 1K | 0.05 |
| nano-banana-2.1 | `gemini-nano-banana-2.1` | 1K/2K/4K | 0.08 |

## 工作流（异步）

```
任务进度:
- [ ] 0. 确认 DUOMI_API_KEY
- [ ] 1. 判断文生图 or 图生图；补齐手帐拼贴风格词
- [ ] 2. POST 提交，拿到 task_id
- [ ] 3. GET 轮询 /api/gemini/nano-banana/{task_id} 直到 succeeded / error
- [ ] 4. 输出 images[].url，勿伪造
```

### 场景 A：文生图

```bash
python scripts/generate.py --prompt "手帐拼贴风：春日出行，撕边拍立得+和纸胶带+手写标题"
```

### 场景 B：图生图 / 多参考编辑

参考图 **仅支持 URL**（最多 10 张，不支持 base64）。单参考图尽量 **不传** `aspect_ratio`（自适应）。

```bash
python scripts/generate.py --edit \
  --prompt "把画面改成手帐拼贴：增加撕边、胶带、手写注记，保留主体" \
  --image-url "https://example.com/a.jpg"
```

### 场景 C：只查任务

```bash
python scripts/generate.py --task-id "xxx-xxx"
```

## 手帐拼贴 Prompt 模板（默认追加）

用户未明确拒绝风格时，Agent 在 prompt **末尾**追加或融合下列要素（中英文均可）：

```
手帐拼贴风 scrapbook collage，混合媒介 mixed media，
撕边纸 scrap paper edges，和纸胶带 washi tape，拍立得相纸 polaroid frames，
手写字体 handwritten notes，贴纸 stickers，纸张纹理 paper texture，
剪贴簿布局 flat lay，温暖柔和色调，艺术感强，非写实摄影
```

**少用：** 超写实、商业棚拍、纯 3D 渲染（会冲淡拼贴感）。

示例完整 prompt：

> 一页旅行手帐展开页，中央是富士山拍立得，周围散落车票残片、干花、手绘小人路线箭头，右上角手写「Day 3 · 晴」，和纸胶带斜贴，撕边与阴影自然，scrapbook collage, warm paper texture

## 接口速查

| 能力 | 方法 | URL |
|------|------|-----|
| 文生图 | POST | `https://duomiapi.com/api/gemini/nano-banana` |
| 图生图 | POST | `https://duomiapi.com/api/gemini/nano-banana-edit` |
| 查状态 | GET | `https://duomiapi.com/api/gemini/nano-banana/{task_id}` |

Header：`Authorization: <DUOMI_API_KEY>`，`Content-Type: application/json`

任务 `state`：`pending` → `running` → `succeeded` / `error`。成功时读 `data.data.images[].url`。

## 详细参数

见 [references/nano-banana-api.md](references/nano-banana-api.md)。
