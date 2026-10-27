---
name: qwen3-tts
version: 1.0.0
display_name: Qwen3 语音合成
display_name_en: Qwen3 TTS Voice Generation
description: >-
  围绕 Qwen3-TTS 提供本地 TTS 工作流：单句语音生成（CustomVoice / VoiceDesign / VoiceClone）、
  长文稿批量配音（文章→配音稿 JSON→批量 TTS→合并）。当用户要生成语音、有声书配音、视频旁白、
  多角色对话朗读或语音克隆时使用。
description_zh: >-
  基于 Qwen3-TTS 的本地语音合成技能，支持内置音色、音色设计、参考音频克隆，以及长文稿批量配音合并。
description_en: >-
  Local Qwen3-TTS workflows for single-utterance synthesis (CustomVoice / VoiceDesign / VoiceClone)
  and long-form batch dubbing (script JSON → batch TTS → merge).
---

# Qwen3 语音合成

将文本转为高质量本地语音。脚本在本技能包 `scripts/` 下；在 WorkBuddy 中优先用托管解释器 / `uv`，工作目录为本技能包根目录，或用 `<skill_dir>` 绝对路径调用。

细则见 [dubbing-skills/SKILL.md](dubbing-skills/SKILL.md)、[dubbing-skills/references/dubbing_format.md](dubbing-skills/references/dubbing_format.md)、[references/python_api.md](references/python_api.md)。

## 两种用法

1. **单句 / 短文本**：直接跑 `scripts/run_qwen3_tts.py`（`custom-voice` / `voice-design` / `voice-clone`）。
2. **长文稿批量配音**：先按配音规范生成 JSON → 用户审核 → `scripts/batch_dubbing.py` 批量合成并合并。

## 模型选择

| 模式 | 模型 | 适用场景 | 命令 |
|------|------|----------|------|
| **CustomVoice** | `Qwen3-TTS-12Hz-1.7B-CustomVoice` | 内置音色 + 情感控制 | `custom-voice` |
| **VoiceDesign** | `Qwen3-TTS-12Hz-1.7B-VoiceDesign` | 用自然语言描述音色 | `voice-design` |
| **VoiceClone** | `Qwen3-TTS-12Hz-1.7B-Base` | 克隆参考音频 | `voice-clone` |
| **Tokenizer** | `Qwen3-TTS-Tokenizer-12Hz` | 音频编解码验证 | `tokenizer-roundtrip` |

**按已有音频克隆**必须用 **Base**（`voice-clone`），不要下 CustomVoice。

### CustomVoice 默认 Speaker

| 语言 | 默认 Speaker | 说明 |
|------|-------------|------|
| Chinese | Vivian | 女声，自然 |
| English | Ryan | 男声 |
| Japanese | Ono_Anna | 女声 |
| Korean | Sohee | 女声 |

## 快速开始

脚本带 PEP 723 依赖声明，推荐：

```bash
uv run "<skill_dir>/scripts/run_qwen3_tts.py" -h
```

当前目录已是本技能包根目录时，可写成 `uv run scripts/run_qwen3_tts.py ...`。

### 单句：CustomVoice（推荐入门）

```bash
uv run "<skill_dir>/scripts/run_qwen3_tts.py" custom-voice \
  --language Chinese \
  --text "你好，欢迎使用语音合成。" \
  --speaker Vivian \
  --instruct "轻松愉快的语气" \
  --out-dir outputs
```

- `--language`：Chinese / English / Japanese / Korean
- `--speaker`：可选；不填则按语言选默认
- `--instruct`：可选；情感/语气（如「开心地说」「低沉缓慢」）
- `--output`：可选；默认时间戳文件名
- `--model`：可选；本地目录或 Hub ID（离线时传本地路径）

### 单句：VoiceDesign

`--instruct` **必填**，用来描述音色：

```bash
uv run "<skill_dir>/scripts/run_qwen3_tts.py" voice-design \
  --language Chinese \
  --text "哥哥，你回来啦，人家等了你好久好久了，要抱抱！" \
  --instruct "体现撒娇稚嫩的萝莉女声，音调偏高且起伏明显。" \
  --out-dir outputs
```

### 单句：VoiceClone（参考音频克隆）

```bash
uv run "<skill_dir>/scripts/run_qwen3_tts.py" voice-clone \
  --language Chinese \
  --model "<skill_dir>/Qwen3-TTS-12Hz-1.7B-Base" \
  --ref-audio "path/to/reference.wav" \
  --ref-text "参考音频的文本内容" \
  --text "要合成的新文本" \
  --out-dir outputs
```

- `--ref-audio`：参考音频路径或 URL
- `--ref-text`：参考音频对应文本（必填）
- `--x-vector-only-mode`：可选；仅说话人特征（质量可能下降）
- VoiceClone **不支持** `--instruct`

### Tokenizer 往返

```bash
uv run "<skill_dir>/scripts/run_qwen3_tts.py" tokenizer-roundtrip \
  --audio "path/to/audio.wav" \
  --out-dir outputs
```

## 长文稿批量配音

```
用户文稿 → AI 生成配音稿 JSON → 用户审核 → 批量 TTS → FFmpeg 合并 → 完整语音.wav
```

### Step 1：生成配音稿

用户说「把下面这篇文章转成语音」并贴上正文时，按 [dubbing-skills/SKILL.md](dubbing-skills/SKILL.md)：

1. 智能切分（每段约 200–300 字）
2. 识别角色（`【旁白】`、`【小明】` 等）
3. 分析情感，生成 `instruct`（克隆模式可省略）
4. 输出配音稿 JSON

### Step 2：用户审核

检查切分、角色、`instruct`、TTS 模式；保存为 `article.dubbing.json`。

### Step 3：批量生成

```bash
uv run "<skill_dir>/scripts/batch_dubbing.py" \
  --input article.dubbing.json \
  --out-dir outputs
```

| 参数 | 说明 | 默认 |
|------|------|------|
| `--input` | 配音稿 JSON | 必填 |
| `--out-dir` | 输出目录 | outputs |
| `--silence-gap` | 段落间静音（秒） | 0.3 |
| `--character-switch-gap` | 角色切换静音（秒） | 0.5 |
| `--clean-segments` | 合并后删除中间片段 | 保留 |

输出示例：

```
outputs/
├── segments/
│   ├── seg_001_旁白.wav
│   └── ...
├── article.dubbing.json
└── article_final.wav
```

批量配音可用的模式：`custom-voice`（默认）、`voice-design`、`voice-clone`。

## 环境配置

### 固定虚拟环境（可选）

```bash
uv venv --python 3.12
.\.venv\Scripts\activate
uv pip install -U qwen-tts
```

WorkBuddy 环境优先用托管解释器；已有装过依赖的 venv 可直接复用。

### FlashAttention 2（可选，降显存）

```bash
uv pip install -U flash-attn --no-build-isolation
# 内存 < 96GB 时：
MAX_JOBS=4 uv pip install -U flash-attn --no-build-isolation
```

需硬件兼容，且模型以 `float16` / `bfloat16` 加载。

### FFmpeg（批量合并必需）

```powershell
choco install ffmpeg -y
ffmpeg -version
```

## 模型离线下载

权重体积大（1.7B 约 3.5–4 GB/个），**不要提交到 git**。中国大陆优先 ModelScope；按需下载，克隆场景只下 Base：

```bash
uv pip install -U modelscope
modelscope download --model Qwen/Qwen3-TTS-12Hz-1.7B-Base --local_dir ./Qwen3-TTS-12Hz-1.7B-Base
# 需要内置音色时再下：
# modelscope download --model Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice --local_dir ./Qwen3-TTS-12Hz-1.7B-CustomVoice
# modelscope download --model Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign --local_dir ./Qwen3-TTS-12Hz-1.7B-VoiceDesign
# modelscope download --model Qwen/Qwen3-TTS-Tokenizer-12Hz --local_dir ./Qwen3-TTS-Tokenizer-12Hz
```

Hugging Face：

```bash
uv pip install -U "huggingface_hub[cli]"
huggingface-cli download Qwen/Qwen3-TTS-12Hz-1.7B-Base --local-dir ./Qwen3-TTS-12Hz-1.7B-Base
```

本地已下载时，调用脚本加 `--model ./Qwen3-TTS-12Hz-1.7B-Base`（或对应目录）。

## 本地 Web UI（可选）

```bash
qwen-tts-demo --help
qwen-tts-demo Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice --ip 0.0.0.0 --port 8000
```

麦克风权限需要 HTTPS 时：

```bash
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=localhost"
qwen-tts-demo Qwen/Qwen3-TTS-12Hz-1.7B-Base \
  --ip 0.0.0.0 --port 8000 \
  --ssl-certfile cert.pem \
  --ssl-keyfile key.pem \
  --no-ssl-verify
```

## 性能参数

```bash
uv run "<skill_dir>/scripts/run_qwen3_tts.py" custom-voice \
  --device-map cuda:0 \
  --dtype bfloat16 \
  --attn flash_attention_2 \
  --language Chinese \
  --text "测试文本" \
  --out-dir outputs
```

| 参数 | 说明 |
|------|------|
| `--device-map` | GPU（如 `cuda:0`）或 CPU |
| `--dtype` | auto / bfloat16 / float16 / float32 |
| `--attn` | auto / flash_attention_2 |

## 常见问题

### Windows 路径

绝对路径用双引号：

```bash
uv run "C:/path/to/voice-generate-skill/scripts/run_qwen3_tts.py" -h
```

### SoX 警告

`SoX could not be found!` 不影响功能；可消除警告：

```powershell
choco install sox.portable -y
```

### 模型下载慢

优先 ModelScope，或提前下到本地目录后用 `--model` 指向本地路径。
