---
name: dubbing-skills
description: 将长文稿/文章转换为配音稿 JSON，支持智能切分、情感分析、多角色识别。当用户需要将文章转语音、制作有声书、处理多角色对话配音时，按本规范生成配音稿。
---

# 配音稿生成技能

将长文稿转换为结构化配音稿 JSON，用于批量 TTS 生成。

---

## 🎯 使用场景

- 文章 / 博客 → 有声版本
- 剧本 / 小说 → 有声书
- 视频脚本 → 配音
- 多角色对话 → 分角色朗读

---

## 📋 工作流程

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ 用户给文稿  │ →  │ AI生成JSON  │ →  │ 用户审核    │ →  │ 批量生成    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

---

## Step 1: AI 分析文本生成配音稿

当用户说 *"把这篇文章转成语音"* + 贴上文章，按以下流程分析：

### 1.1 检测语言

根据文本内容判断：Chinese / English / Japanese / Korean

### 1.2 识别文本类型

| 类型 | 特征 | 处理方式 |
|------|------|----------|
| 多角色对话 | 有 `【角色名】` 标记 | 解析角色名 |
| 无标记对话 | 有 `"引号"` 对话 | 标记为 character_1, 2... |
| 纯旁白 | 无对话标记 | 使用默认角色 `旁白` |

### 1.3 智能切分

**规则**：
1. 按段落分割（`\n\n`）
2. 按句号切分（`。！？.!?`）
3. 超过 300 字在逗号处二次切分
4. **不在引号内切分**

**保持完整的情况**：
- `"今天天气真好。我们出去吧。"` → 引号内不切
- `我想……可能不行` → 省略号不切
- `3.14` `2.5%` → 数字不切

### 1.4 情感分析

为每段生成 `instruct`（10-20 字）：

| 文本特征 | emotion | instruct 示例 |
|----------|---------|---------------|
| 陈述事实 | neutral | 平静陈述 |
| 感叹号多 | happy/excited | 开心兴奋，语速稍快 |
| 问句 | neutral | 疑问上扬 |
| 省略号 | sad/calm | 低沉缓慢，略带叹息 |
| 描写场景 | calm | 舒缓平和，营造氛围 |
| 冲突对话 | angry | 语气激动，重音明显 |

### 1.5 确定模式和 Speaker

| 角色需求 | 推荐模式 | 配置 |
|----------|----------|------|
| 普通角色 | custom-voice | `speaker: Vivian/Ryan` |
| 特定音色（萝莉、大叔等）| voice-design | `voice_instruct: 音色描述` |
| 真人声音 | voice-clone | `ref_audio + ref_text` |

**内置 Speaker**：
- Chinese → `Vivian`（女）
- English → `Ryan`（男）
- Japanese → `Ono_Anna`（女）
- Korean → `Sohee`（女）

---

## Step 2: 输出 JSON

### 标准模板

```json
{
  "version": "1.1",
  "source": "文章标题或来源",
  "language": "Chinese",
  "default_mode": "custom-voice",
  "silence_gap": 0.3,
  "character_switch_gap": 0.5,
  "total_segments": 5,
  
  "character_map": {
    "旁白": {
      "speaker": "Vivian",
      "default_instruct": "平静的叙述"
    },
    "角色A": {
      "speaker": "Ryan",
      "default_instruct": "年轻活泼"
    }
  },
  
  "segments": [
    {
      "id": 1,
      "character": "旁白",
      "text": "第一段内容。",
      "instruct": "情感/语气描述",
      "emotion": "neutral"
    }
  ]
}
```

### 输出时提示用户

> 这是生成的配音稿 JSON。请检查：
> 1. 切分是否合理
> 2. 角色分配是否正确
> 3. 情感 instruct 是否合适
> 4. 需要调整的 mode（custom-voice / voice-design / voice-clone）
>
> 修改后保存为 `.dubbing.json` 文件，然后告诉我"帮我生成语音"。

---

## Step 3: 批量生成语音

用户确认后，执行：

```bash
uv run qwen3-tts-skills/scripts/batch_dubbing.py \
  --input article.dubbing.json \
  --out-dir outputs
```

---

## 📖 三种模式配置

### custom-voice（默认）

```json
"character_map": {
  "旁白": {
    "mode": "custom-voice",
    "speaker": "Vivian",
    "default_instruct": "平静叙述"
  }
}
```

### voice-design

```json
"character_map": {
  "萝莉": {
    "mode": "voice-design",
    "voice_instruct": "稚嫩可爱的萝莉女声，音调偏高",
    "default_instruct": "撒娇语气"
  }
}
```

### voice-clone

```json
"character_map": {
  "主播": {
    "mode": "voice-clone",
    "ref_audio": "voices/host.wav",
    "ref_text": "参考音频的文本内容"
  }
}
```

**⚠️ voice-clone 不支持 instruct 情感控制**

---

## 📝 instruct 写法参考

| 情感 | 示例 |
|------|------|
| 开心 | 开心愉快，语调上扬 |
| 悲伤 | 低沉缓慢，略带叹息 |
| 愤怒 | 语气激动，语速加快 |
| 惊讶 | 惊讶上扬，略微拖长 |
| 平静 | 平和舒缓，语速适中 |
| 紧张 | 语速略快，有些紧张 |
| 神秘 | 压低声音，营造悬疑 |
| 温柔 | 轻声细语，温柔亲切 |
| 严肃 | 庄重正式，一字一顿 |
| 撒娇 | 撒娇拖音，语调起伏 |

---

## 🔗 相关文档

- **格式规范**：`references/dubbing_format.md`
- **完整示例**：`references/examples.md`
- **主技能**：`../SKILL.md`

---

## 💡 快速示例

**用户输入**：
```
【旁白】清晨的咖啡店里，阳光透过玻璃窗洒落。
【小明】早上好！今天天气真不错！
【小红】是啊，我们一起去公园吧！
```

**AI 输出**：
```json
{
  "version": "1.1",
  "language": "Chinese",
  "default_mode": "custom-voice",
  "silence_gap": 0.3,
  "character_switch_gap": 0.5,
  "total_segments": 3,
  "character_map": {
    "旁白": {"speaker": "Vivian", "default_instruct": "平静叙述"},
    "小明": {"speaker": "Ryan", "default_instruct": "年轻活泼男声"},
    "小红": {"speaker": "Vivian", "default_instruct": "温柔甜美女声"}
  },
  "segments": [
    {"id": 1, "character": "旁白", "text": "清晨的咖啡店里，阳光透过玻璃窗洒落。", "instruct": "场景描述，舒缓平和", "emotion": "calm"},
    {"id": 2, "character": "小明", "text": "早上好！今天天气真不错！", "instruct": "开心问候，语气上扬", "emotion": "happy"},
    {"id": 3, "character": "小红", "text": "是啊，我们一起去公园吧！", "instruct": "兴奋期待，活泼语气", "emotion": "excited"}
  ]
}
```
