# 配音稿示例

本文档提供不同场景的配音稿示例，所有示例均使用 **v1.1 格式**。

---

## 示例 1：视频旁白/解说（custom-voice 模式）

**原始文本**：
```
人工智能正在改变我们的生活。从智能手机的语音助手，到自动驾驶汽车，AI 技术无处不在。

但这也带来了一些担忧。人们开始思考：机器会取代人类的工作吗？

让我们一起来探讨这些问题。
```

**配音稿 JSON**：
```json
{
  "version": "1.1",
  "source": "AI科普视频解说",
  "language": "Chinese",
  "default_mode": "custom-voice",
  "silence_gap": 0.3,
  "character_switch_gap": 0.5,
  "total_segments": 4,
  
  "character_map": {
    "旁白": {
      "speaker": "Vivian",
      "default_instruct": "专业、清晰的科普解说"
    }
  },
  
  "segments": [
    {
      "id": 1,
      "character": "旁白",
      "text": "人工智能正在改变我们的生活。",
      "instruct": "开场白，语气庄重、引人入胜",
      "emotion": "serious"
    },
    {
      "id": 2,
      "character": "旁白",
      "text": "从智能手机的语音助手，到自动驾驶汽车，AI 技术无处不在。",
      "instruct": "列举说明，语气平稳、清晰",
      "emotion": "neutral"
    },
    {
      "id": 3,
      "character": "旁白",
      "text": "但这也带来了一些担忧。人们开始思考：机器会取代人类的工作吗？",
      "instruct": "转折后提问，语气略凝重，问句上扬",
      "emotion": "serious"
    },
    {
      "id": 4,
      "character": "旁白",
      "text": "让我们一起来探讨这些问题。",
      "instruct": "邀请式结尾，语气友好、期待",
      "emotion": "calm"
    }
  ]
}
```

**生成命令**：
```bash
uv run qwen3-tts-skills/scripts/batch_dubbing.py --input ai_video.dubbing.json --out-dir outputs
```

---

## 示例 2：多角色对话（custom-voice 模式）

**原始文本**：
```
【旁白】清晨的咖啡店里，两个老朋友久别重逢。

【小明】好久不见啊！你最近怎么样？

【小红】（惊喜地）小明！真的是你！我都快认不出来了！

【小明】（笑）是啊，我也变了不少。来，坐下聊聊！
```

**配音稿 JSON**：
```json
{
  "version": "1.1",
  "source": "咖啡店重逢对话",
  "language": "Chinese",
  "default_mode": "custom-voice",
  "silence_gap": 0.3,
  "character_switch_gap": 0.5,
  "total_segments": 4,
  
  "character_map": {
    "旁白": {
      "speaker": "Vivian",
      "default_instruct": "舒缓的叙述者"
    },
    "小明": {
      "speaker": "Ryan",
      "default_instruct": "年轻男生，热情友好"
    },
    "小红": {
      "speaker": "Vivian",
      "default_instruct": "年轻女生，活泼可爱"
    }
  },
  
  "segments": [
    {
      "id": 1,
      "character": "旁白",
      "text": "清晨的咖啡店里，两个老朋友久别重逢。",
      "instruct": "场景描述，平和舒缓",
      "emotion": "calm"
    },
    {
      "id": 2,
      "character": "小明",
      "text": "好久不见啊！你最近怎么样？",
      "instruct": "热情的问候，语气愉快上扬",
      "emotion": "happy"
    },
    {
      "id": 3,
      "character": "小红",
      "text": "小明！真的是你！我都快认不出来了！",
      "instruct": "惊喜激动，语速稍快，音调升高",
      "emotion": "surprised"
    },
    {
      "id": 4,
      "character": "小明",
      "text": "是啊，我也变了不少。来，坐下聊聊！",
      "instruct": "带笑意的回应，轻松友好",
      "emotion": "happy"
    }
  ]
}
```

---

## 示例 3：有声书片段（custom-voice 模式）

**原始文本**：
```
月光洒在湖面上，泛起点点银光。他站在岸边，久久凝视着远方。

"也许，就这样结束也好。"他轻声说道。

风吹过，带走了他的话语。夜，更深了。
```

**配音稿 JSON**：
```json
{
  "version": "1.1",
  "source": "有声书 - 第三章",
  "language": "Chinese",
  "default_mode": "custom-voice",
  "silence_gap": 0.4,
  "character_switch_gap": 0.6,
  "total_segments": 5,
  
  "character_map": {
    "旁白": {
      "speaker": "Vivian",
      "default_instruct": "沉稳、富有感染力的文学朗读"
    },
    "主角": {
      "speaker": "Ryan",
      "default_instruct": "深沉、略带忧郁的男声"
    }
  },
  
  "segments": [
    {
      "id": 1,
      "character": "旁白",
      "text": "月光洒在湖面上，泛起点点银光。",
      "instruct": "优美的景色描写，语速缓慢，营造氛围",
      "emotion": "calm"
    },
    {
      "id": 2,
      "character": "旁白",
      "text": "他站在岸边，久久凝视着远方。",
      "instruct": "描述人物状态，略带忧伤的氛围",
      "emotion": "sad"
    },
    {
      "id": 3,
      "character": "主角",
      "text": "也许，就这样结束也好。",
      "instruct": "轻声自语，带有无奈和释然",
      "emotion": "sad"
    },
    {
      "id": 4,
      "character": "旁白",
      "text": "风吹过，带走了他的话语。",
      "instruct": "环境描写，轻柔空灵",
      "emotion": "calm"
    },
    {
      "id": 5,
      "character": "旁白",
      "text": "夜，更深了。",
      "instruct": "结尾点题，意味深长，语速极慢",
      "emotion": "neutral"
    }
  ]
}
```

---

## 示例 4：voice-design 模式（自定义音色）

**场景**：需要一个萝莉音色的角色

**配音稿 JSON**：
```json
{
  "version": "1.1",
  "source": "萝莉角色配音",
  "language": "Chinese",
  "default_mode": "voice-design",
  "silence_gap": 0.3,
  "character_switch_gap": 0.5,
  "total_segments": 2,
  
  "character_map": {
    "萝莉": {
      "mode": "voice-design",
      "voice_instruct": "稚嫩可爱的萝莉女声，音调偏高且起伏明显，营造出黏人、撒娇的听觉效果",
      "default_instruct": "撒娇语气"
    }
  },
  
  "segments": [
    {
      "id": 1,
      "character": "萝莉",
      "text": "哥哥，你回来啦！人家等了你好久好久了！",
      "instruct": "撒娇、开心，语调上扬"
    },
    {
      "id": 2,
      "character": "萝莉",
      "text": "今天可以陪我玩游戏吗？求求你啦~",
      "instruct": "可怜巴巴地请求，拖长尾音"
    }
  ]
}
```

**说明**：
- `mode: "voice-design"` 表示使用 VoiceDesign 模式
- `voice_instruct` 描述音色特征（必填）
- `instruct` 描述情感/语气（可选，会与 voice_instruct 合并）

---

## 示例 5：voice-clone 模式（语音克隆）

**场景**：使用真人录制的参考音频来配音

**配音稿 JSON**：
```json
{
  "version": "1.1",
  "source": "真人配音项目",
  "language": "Chinese",
  "default_mode": "voice-clone",
  "silence_gap": 0.3,
  "character_switch_gap": 0.5,
  "total_segments": 2,
  
  "character_map": {
    "主播小明": {
      "mode": "voice-clone",
      "ref_audio": "voices/xiaoming_sample.wav",
      "ref_text": "大家好，我是小明，今年二十五岁，是一名程序员。"
    }
  },
  
  "segments": [
    {
      "id": 1,
      "character": "主播小明",
      "text": "欢迎来到今天的节目！"
    },
    {
      "id": 2,
      "character": "主播小明",
      "text": "我们今天要聊一个很有趣的话题。"
    }
  ]
}
```

**说明**：
- `mode: "voice-clone"` 表示使用 VoiceClone 模式
- `ref_audio` 填写参考音频的路径或 URL（必填）
- `ref_text` 填写参考音频的文本内容（必填）
- **⚠️ voice-clone 模式不支持 `instruct` 情感控制**

---

## 示例 6：混合模式（多种模式组合）

**场景**：同一配音稿中使用多种模式

**配音稿 JSON**：
```json
{
  "version": "1.1",
  "source": "混合模式演示",
  "language": "Chinese",
  "default_mode": "custom-voice",
  "silence_gap": 0.3,
  "character_switch_gap": 0.5,
  "total_segments": 4,
  
  "character_map": {
    "旁白": {
      "mode": "custom-voice",
      "speaker": "Vivian",
      "default_instruct": "专业解说"
    },
    "萝莉": {
      "mode": "voice-design",
      "voice_instruct": "稚嫩可爱的萝莉女声，音调偏高",
      "default_instruct": "活泼可爱"
    },
    "真人主播": {
      "mode": "voice-clone",
      "ref_audio": "voices/host.wav",
      "ref_text": "大家好，欢迎收看我的节目。"
    }
  },
  
  "segments": [
    {
      "id": 1,
      "character": "旁白",
      "text": "今天我们来听一个故事。",
      "instruct": "平静开场"
    },
    {
      "id": 2,
      "character": "萝莉",
      "text": "这个故事可有趣了！",
      "instruct": "兴奋期待"
    },
    {
      "id": 3,
      "character": "真人主播",
      "text": "让我来给大家讲一讲。"
    },
    {
      "id": 4,
      "character": "旁白",
      "text": "故事开始了...",
      "instruct": "神秘悬疑的氛围"
    }
  ]
}
```

---

## 示例 7：英文内容

**原始文本**：
```
Welcome to today's tutorial! We're going to learn something amazing.

First, let me show you the basics. Don't worry, it's easier than you think!
```

**配音稿 JSON**：
```json
{
  "version": "1.1",
  "source": "English Tutorial",
  "language": "English",
  "default_mode": "custom-voice",
  "silence_gap": 0.3,
  "character_switch_gap": 0.5,
  "total_segments": 3,
  
  "character_map": {
    "narrator": {
      "speaker": "Ryan",
      "default_instruct": "Friendly and engaging tutorial host"
    }
  },
  
  "segments": [
    {
      "id": 1,
      "character": "narrator",
      "text": "Welcome to today's tutorial!",
      "instruct": "Warm welcome, enthusiastic and inviting",
      "emotion": "happy"
    },
    {
      "id": 2,
      "character": "narrator",
      "text": "We're going to learn something amazing.",
      "instruct": "Building anticipation, excited tone",
      "emotion": "excited"
    },
    {
      "id": 3,
      "character": "narrator",
      "text": "First, let me show you the basics. Don't worry, it's easier than you think!",
      "instruct": "Reassuring and encouraging, friendly pace",
      "emotion": "calm"
    }
  ]
}
```

---

## 最小化示例

只包含必需字段的最简配音稿：

```json
{
  "version": "1.1",
  "language": "Chinese",
  "total_segments": 2,
  "character_map": {
    "旁白": {"speaker": "Vivian"}
  },
  "segments": [
    {"id": 1, "character": "旁白", "text": "今天是个好日子。"},
    {"id": 2, "character": "旁白", "text": "阳光明媚，万里无云。"}
  ]
}
```

---

## 常用 instruct 写法参考

| 情感/语气 | instruct 示例 |
|-----------|---------------|
| 开心 | "开心愉快，语调上扬" |
| 悲伤 | "低沉缓慢，略带叹息" |
| 愤怒 | "语气激动，语速加快，重音明显" |
| 惊讶 | "惊讶上扬，略微拖长" |
| 平静 | "平和舒缓，语速适中" |
| 紧张 | "语速略快，有些紧张颤抖" |
| 神秘 | "压低声音，营造悬疑氛围" |
| 温柔 | "轻声细语，温柔亲切" |
| 严肃 | "庄重正式，一字一顿" |
| 撒娇 | "撒娇拖音，语调起伏明显" |
