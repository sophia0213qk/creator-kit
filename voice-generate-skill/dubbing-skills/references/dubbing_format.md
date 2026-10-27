# 配音稿 JSON 格式规范（v1.1）

本文档定义了配音稿的标准 JSON 格式，确保与 TTS 批量生成脚本兼容。

## 完整结构

```json
{
  "version": "1.1",
  "source": "原始文件名或来源",
  "language": "Chinese",
  "created_at": "2026-01-25T15:00:00",
  "total_segments": 10,
  "total_characters": 2500,
  "estimated_duration_sec": 180,
  
  "default_mode": "custom-voice",
  "silence_gap": 0.3,
  "character_switch_gap": 0.5,
  
  "character_map": {
    "旁白": {
      "mode": "custom-voice",
      "speaker": "Vivian",
      "default_instruct": "平静舒缓的叙述"
    },
    "小明": {
      "mode": "voice-clone",
      "ref_audio": "voices/xiaoming_ref.wav",
      "ref_text": "大家好，我是小明。",
      "default_instruct": "年轻活泼的男声"
    },
    "萝莉": {
      "mode": "voice-design",
      "voice_instruct": "稚嫩可爱的萝莉女声，音调偏高",
      "default_instruct": "撒娇语气"
    }
  },
  
  "segments": [
    {
      "id": 1,
      "character": "旁白",
      "text": "这是要朗读的文本内容。",
      "char_count": 12,
      "speaker": "Vivian",
      "language": "Chinese",
      "instruct": "平静、陈述性的语气",
      "emotion": "neutral",
      "pause_after_ms": 500
    }
  ]
}
```

## 字段说明

### 顶级字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `version` | string | 是 | 格式版本，当前为 "1.1" |
| `source` | string | 否 | 原始文件名或来源描述 |
| `language` | string | 是 | 主要语言：Chinese / English / Japanese / Korean |
| `created_at` | string | 否 | 创建时间（ISO 8601 格式）|
| `total_segments` | int | 是 | segment 总数 |
| `total_characters` | int | 否 | 总字符数 |
| `estimated_duration_sec` | int | 否 | 预估总时长（秒）|
| `default_mode` | string | 否 | 默认 TTS 模式（见下方说明）|
| `silence_gap` | float | 否 | 普通段落间静音秒数（默认 0.3）|
| `character_switch_gap` | float | 否 | 角色切换时静音秒数（默认 0.5）|
| `character_map` | object | 否 | 角色 → 配置映射表 |
| `segments` | array | 是 | segment 数组 |

### TTS 模式（mode）

| 模式 | 说明 | 必需字段 |
|------|------|----------|
| `custom-voice` | 使用内置音色 + 可选情感指令 | `speaker` |
| `voice-design` | 用自然语言描述音色 | `voice_instruct` |
| `voice-clone` | 克隆参考音频的声音 | `ref_audio`, `ref_text` |

**注意**：`voice-clone` 模式不支持 `instruct` 情感控制，情感靠文本内容自然表达。

### character_map 字段

定义每个角色的配置：

```json
"character_map": {
  "角色名": {
    "mode": "custom-voice",
    "speaker": "Vivian",
    "default_instruct": "角色的默认语气描述",
    
    // voice-design 模式专用
    "voice_instruct": "音色描述（如：低沉成熟的男声）",
    
    // voice-clone 模式专用
    "ref_audio": "参考音频路径或 URL",
    "ref_text": "参考音频对应的文本"
  }
}
```

#### character_map 字段详解

| 字段 | 模式 | 说明 |
|------|------|------|
| `mode` | 全部 | TTS 模式（覆盖 default_mode）|
| `speaker` | custom-voice | 内置 speaker 名称 |
| `default_instruct` | custom-voice, voice-design | 默认情感/语气指令 |
| `voice_instruct` | voice-design | 音色描述（必填）|
| `ref_audio` | voice-clone | 参考音频路径或 URL（必填）|
| `ref_text` | voice-clone | 参考音频的文本内容（必填）|

### segment 字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | int | 是 | 序号（从 1 开始）|
| `character` | string | 否 | 角色名（如 "旁白"、"小明"）|
| `text` | string | 是 | 要朗读的文本 |
| `char_count` | int | 否 | 文本字符数 |
| `speaker` | string | 否 | 覆盖角色的 speaker（custom-voice 模式）|
| `language` | string | 否 | 该段的语言（覆盖顶级 language）|
| `instruct` | string | 否 | 情感/语气指令（voice-clone 模式下忽略）|
| `emotion` | string | 否 | 情感标签（用于分类）|
| `pause_after_ms` | int | 否 | 该段后的静音时长（毫秒，已弃用，使用 silence_gap）|

### emotion 可选值

| 值 | 描述 |
|------|------|
| `neutral` | 平静、中性 |
| `happy` | 开心、愉快 |
| `sad` | 悲伤、低落 |
| `angry` | 愤怒、激动 |
| `surprised` | 惊讶、意外 |
| `scared` | 恐惧、担忧 |
| `calm` | 平和、舒缓 |
| `excited` | 兴奋、激动（正面）|
| `tender` | 温柔、亲切 |
| `serious` | 严肃、庄重 |

### 静音间隔说明

| 场景 | 默认值 | 配置字段 |
|------|--------|----------|
| 同一角色连续段落 | 0.3 秒 | `silence_gap` |
| 角色切换 | 0.5 秒 | `character_switch_gap` |

## 三种模式示例

### custom-voice 模式（最常用）

使用内置音色，可选情感指令：

```json
{
  "version": "1.1",
  "language": "Chinese",
  "default_mode": "custom-voice",
  "silence_gap": 0.3,
  "character_switch_gap": 0.5,
  "total_segments": 2,
  "character_map": {
    "旁白": {
      "speaker": "Vivian",
      "default_instruct": "平静舒缓"
    }
  },
  "segments": [
    {
      "id": 1,
      "character": "旁白",
      "text": "今天是个好日子。",
      "instruct": "轻松愉快的语气"
    },
    {
      "id": 2,
      "character": "旁白",
      "text": "阳光明媚，万里无云。",
      "instruct": "舒缓平和"
    }
  ]
}
```

### voice-design 模式

用自然语言描述想要的音色：

```json
{
  "version": "1.1",
  "language": "Chinese",
  "default_mode": "voice-design",
  "total_segments": 1,
  "character_map": {
    "萝莉": {
      "mode": "voice-design",
      "voice_instruct": "稚嫩可爱的萝莉女声，音调偏高且起伏明显"
    }
  },
  "segments": [
    {
      "id": 1,
      "character": "萝莉",
      "text": "哥哥，你回来啦！",
      "instruct": "撒娇、开心"
    }
  ]
}
```

### voice-clone 模式

克隆参考音频的声音：

```json
{
  "version": "1.1",
  "language": "Chinese",
  "default_mode": "voice-clone",
  "total_segments": 1,
  "character_map": {
    "小明": {
      "mode": "voice-clone",
      "ref_audio": "voices/xiaoming_sample.wav",
      "ref_text": "大家好，我是小明，今年二十岁。"
    }
  },
  "segments": [
    {
      "id": 1,
      "character": "小明",
      "text": "今天我给大家讲一个故事。"
    }
  ]
}
```

**⚠️ 注意**：voice-clone 模式不支持 `instruct` 情感控制。如果需要情感表达，请在文本中体现。

### 混合模式示例

同一配音稿中使用多种模式：

```json
{
  "version": "1.1",
  "language": "Chinese",
  "default_mode": "custom-voice",
  "silence_gap": 0.3,
  "character_switch_gap": 0.5,
  "total_segments": 3,
  "character_map": {
    "旁白": {
      "mode": "custom-voice",
      "speaker": "Vivian",
      "default_instruct": "平静叙述"
    },
    "小明": {
      "mode": "voice-clone",
      "ref_audio": "voices/xiaoming.wav",
      "ref_text": "大家好，我是小明。"
    },
    "萝莉": {
      "mode": "voice-design",
      "voice_instruct": "稚嫩可爱的萝莉女声"
    }
  },
  "segments": [
    {
      "id": 1,
      "character": "旁白",
      "text": "这是一个阳光明媚的早晨。",
      "instruct": "平静开场"
    },
    {
      "id": 2,
      "character": "小明",
      "text": "早上好！今天天气真不错！"
    },
    {
      "id": 3,
      "character": "萝莉",
      "text": "哥哥早安！",
      "instruct": "开心、撒娇"
    }
  ]
}
```

## 验证规则

1. `segments` 数组不能为空
2. 每个 segment 必须有 `id` 和 `text`
3. `id` 应该连续且从 1 开始
4. `text` 不能为空字符串
5. `custom-voice` 模式需要 `speaker`（可从 character_map 继承）
6. `voice-design` 模式需要 `voice_instruct`（在 character_map 中定义）
7. `voice-clone` 模式需要 `ref_audio` 和 `ref_text`（在 character_map 中定义）
8. `silence_gap` 和 `character_switch_gap` 应该是 0-5 之间的浮点数

## 生成命令

配音稿编辑完成后，使用以下命令生成最终音频：

```bash
uv run qwen3-tts-skills/scripts/batch_dubbing.py \
  --input article.dubbing.json \
  --out-dir outputs
```

可选参数：
- `--silence-gap 0.3`：覆盖普通静音间隔
- `--character-switch-gap 0.5`：覆盖角色切换静音间隔
- `--clean-segments`：合并后删除中间片段文件
