# Qwen3-TTS Python API 参考

用于将 Qwen3-TTS 集成到你自己的 Python 项目中。

> **建议**：先用 `uv run qwen3-tts-skills/scripts/run_qwen3_tts.py ...` 验证环境和模型可用，再进行代码集成。

---

## 通用加载配置

```python
import torch
from qwen_tts import Qwen3TTSModel

model = Qwen3TTSModel.from_pretrained(
    "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",  # 模型路径或 ID
    device_map="cuda:0",                       # 设备
    dtype=torch.bfloat16,                      # 数据类型
    attn_implementation="flash_attention_2",   # 注意力实现（可选）
)
```

**参数说明**：
| 参数 | 说明 |
|------|------|
| `device_map` | `cuda:0` / `cuda:1` / `cpu` |
| `dtype` | `torch.bfloat16` / `torch.float16` / `torch.float32` |
| `attn_implementation` | `flash_attention_2`（需安装且硬件兼容）|

---

## CustomVoice（自定义音色）

使用内置 Speaker，可选情感控制。

### 单句生成

```python
import torch
import soundfile as sf
from qwen_tts import Qwen3TTSModel

model = Qwen3TTSModel.from_pretrained(
    "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
    device_map="cuda:0",
    dtype=torch.bfloat16,
)

wavs, sr = model.generate_custom_voice(
    text="其实我真的有发现，我是一个特别善于观察别人情绪的人。",
    language="Chinese",
    speaker="Vivian",
    instruct="用轻松愉快的语气说",  # 可选
)
sf.write("output.wav", wavs[0], sr)
```

### 批量生成

```python
wavs, sr = model.generate_custom_voice(
    text=[
        "其实我真的有发现，我是一个特别善于观察别人情绪的人。",
        "She said she would be here by noon.",
    ],
    language=["Chinese", "English"],
    speaker=["Vivian", "Ryan"],
    instruct=["轻松愉快", "Very happy."],
)
sf.write("output_1.wav", wavs[0], sr)
sf.write("output_2.wav", wavs[1], sr)
```

### 内置 Speaker 列表

| 语言 | Speaker |
|------|---------|
| Chinese | Vivian |
| English | Ryan |
| Japanese | Ono_Anna |
| Korean | Sohee |

---

## VoiceDesign（语音设计）

用自然语言描述想要的音色。

```python
import torch
import soundfile as sf
from qwen_tts import Qwen3TTSModel

model = Qwen3TTSModel.from_pretrained(
    "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
    device_map="cuda:0",
    dtype=torch.bfloat16,
)

wavs, sr = model.generate_voice_design(
    text="哥哥，你回来啦，人家等了你好久好久了，要抱抱！",
    language="Chinese",
    instruct="体现撒娇稚嫩的萝莉女声，音调偏高且起伏明显，营造出黏人、撒娇的听觉效果。",
)
sf.write("output_voice_design.wav", wavs[0], sr)
```

**注意**：`instruct` 参数是**必填**的，用于描述音色特征。

---

## VoiceClone（语音克隆）

克隆参考音频的声音。

### 基本用法

```python
import torch
import soundfile as sf
from qwen_tts import Qwen3TTSModel

model = Qwen3TTSModel.from_pretrained(
    "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
    device_map="cuda:0",
    dtype=torch.bfloat16,
)

ref_audio = "path/to/reference.wav"  # 或 URL
ref_text = "参考音频对应的文本内容"

wavs, sr = model.generate_voice_clone(
    text="要合成的新文本",
    language="Chinese",
    ref_audio=ref_audio,
    ref_text=ref_text,
)
sf.write("output_voice_clone.wav", wavs[0], sr)
```

### 复用 Prompt（避免重复特征提取）

批量生成时，先提取特征再复用：

```python
# 1. 提取声音特征（只需一次）
prompt_items = model.create_voice_clone_prompt(
    ref_audio=ref_audio,
    ref_text=ref_text,
    x_vector_only_mode=False,
)

# 2. 批量生成
wavs, sr = model.generate_voice_clone(
    text=["第一句话。", "第二句话。", "第三句话。"],
    language=["Chinese", "Chinese", "Chinese"],
    voice_clone_prompt=prompt_items,  # 复用
)
for i, w in enumerate(wavs):
    sf.write(f"output_{i}.wav", w, sr)
```

---

## 高级用法：VoiceDesign + VoiceClone

先用 VoiceDesign "设计"一个音色，然后当作参考音频进行克隆。

```python
import torch
import soundfile as sf
from qwen_tts import Qwen3TTSModel

# 1. 用 VoiceDesign 生成参考音频
design_model = Qwen3TTSModel.from_pretrained(
    "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
    device_map="cuda:0",
    dtype=torch.bfloat16,
)

ref_text = "大家好，我是虚拟主播小星星。"
ref_instruct = "活泼开朗的虚拟主播女声，声音清脆悦耳"

ref_wavs, sr = design_model.generate_voice_design(
    text=ref_text,
    language="Chinese",
    instruct=ref_instruct,
)
sf.write("designed_voice.wav", ref_wavs[0], sr)

# 2. 用 VoiceClone 复用这个音色
clone_model = Qwen3TTSModel.from_pretrained(
    "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
    device_map="cuda:0",
    dtype=torch.bfloat16,
)

voice_clone_prompt = clone_model.create_voice_clone_prompt(
    ref_audio=(ref_wavs[0], sr),  # 直接传入音频数据
    ref_text=ref_text,
)

# 3. 批量生成
sentences = [
    "欢迎来到今天的直播！",
    "我们今天要聊一个超级有趣的话题。",
    "大家准备好了吗？",
]

wavs, sr = clone_model.generate_voice_clone(
    text=sentences,
    language=["Chinese"] * len(sentences),
    voice_clone_prompt=voice_clone_prompt,
)
for i, w in enumerate(wavs):
    sf.write(f"clone_{i}.wav", w, sr)
```

---

## Tokenizer（音频编解码）

用于音频的编码和解码处理。

```python
import soundfile as sf
from qwen_tts import Qwen3TTSTokenizer

tokenizer = Qwen3TTSTokenizer.from_pretrained(
    "Qwen/Qwen3-TTS-Tokenizer-12Hz",
    device_map="cuda:0",
)

# 编码
encoded = tokenizer.encode("path/to/audio.wav")  # 或 URL

# 解码
wavs, sr = tokenizer.decode(encoded)
sf.write("decoded_output.wav", wavs[0], sr)
```

---

## 常见问题

### 1. FlashAttention 2 报错

确保：
- 已安装：`pip install flash-attn --no-build-isolation`
- 使用 `dtype=torch.bfloat16` 或 `torch.float16`
- 硬件支持（Ampere 及更新架构）

不支持时移除 `attn_implementation` 参数即可。

### 2. 显存不足

- 使用小模型：`Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice`
- 降低 batch size
- 使用 `torch.float16` 代替 `torch.float32`

### 3. 生成的音频有杂音

- 检查 `ref_audio` 质量（语音克隆）
- 调整 `instruct` 描述
- 尝试不同的 speaker
