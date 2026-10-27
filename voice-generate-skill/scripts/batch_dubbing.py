#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "soundfile",
# ]
# ///
"""
批量配音生成脚本：读取配音稿 JSON，遍历 segments 调用 TTS，最后用 FFmpeg 合并

用法：
    uv run batch_dubbing.py --input article.dubbing.json --out-dir outputs

功能：
    1. 读取配音稿 JSON
    2. 遍历 segments，根据 mode 调用对应的 TTS 命令
    3. 在段落间插入静音（默认 0.3s，角色切换 0.5s）
    4. 用 FFmpeg 合并为最终音频文件
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Any


@dataclass
class DubbingConfig:
    """配音配置"""
    language: str = "Chinese"
    default_mode: str = "custom-voice"
    silence_gap: float = 0.3
    character_switch_gap: float = 0.5
    sample_rate: int = 24000  # Qwen3-TTS 默认采样率


def generate_silence_wav(output_path: Path, duration_sec: float, sample_rate: int = 24000) -> bool:
    """使用 FFmpeg 生成静音 WAV 文件"""
    try:
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"anullsrc=r={sample_rate}:cl=mono",
            "-t", str(duration_sec),
            "-c:a", "pcm_s16le",
            str(output_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        print("错误：未找到 FFmpeg，请安装 FFmpeg 并添加到 PATH")
        return False


def get_tts_script_path() -> Path:
    """获取 TTS 脚本路径"""
    # 相对于当前脚本的位置
    script_dir = Path(__file__).parent
    tts_script = script_dir / "run_qwen3_tts.py"
    if tts_script.exists():
        return tts_script
    
    # 备用：尝试从 skill 根目录找
    skill_root = script_dir.parent
    tts_script = skill_root / "scripts" / "run_qwen3_tts.py"
    if tts_script.exists():
        return tts_script
    
    raise FileNotFoundError("无法找到 run_qwen3_tts.py 脚本")


def run_tts_custom_voice(
    tts_script: Path,
    text: str,
    language: str,
    speaker: str,
    instruct: str | None,
    output_file: Path,
) -> bool:
    """调用 custom-voice 模式 TTS"""
    cmd = [
        "uv", "run", str(tts_script), "custom-voice",
        "--language", language,
        "--speaker", speaker,
        "--text", text,
        "--output", str(output_file),
    ]
    if instruct:
        cmd.extend(["--instruct", instruct])
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"TTS 错误: {result.stderr[:200] if result.stderr else 'unknown error'}")
    return result.returncode == 0


def run_tts_voice_design(
    tts_script: Path,
    text: str,
    language: str,
    voice_instruct: str,
    segment_instruct: str | None,
    output_file: Path,
) -> bool:
    """调用 voice-design 模式 TTS"""
    # 合并音色描述和情感指令
    full_instruct = voice_instruct
    if segment_instruct:
        full_instruct = f"{voice_instruct}，{segment_instruct}"
    
    cmd = [
        "uv", "run", str(tts_script), "voice-design",
        "--language", language,
        "--text", text,
        "--instruct", full_instruct,
        "--output", str(output_file),
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"TTS 错误: {result.stderr[:200] if result.stderr else 'unknown error'}")
    return result.returncode == 0


def run_tts_voice_clone(
    tts_script: Path,
    text: str,
    language: str,
    ref_audio: str,
    ref_text: str,
    output_file: Path,
) -> bool:
    """调用 voice-clone 模式 TTS（注意：不支持 instruct）"""
    cmd = [
        "uv", "run", str(tts_script), "voice-clone",
        "--language", language,
        "--ref-audio", ref_audio,
        "--ref-text", ref_text,
        "--text", text,
        "--output", str(output_file),
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"TTS 错误: {result.stderr[:200] if result.stderr else 'unknown error'}")
    return result.returncode == 0


def sanitize_filename(name: str) -> str:
    """清理文件名中的非法字符"""
    # 替换非法字符为下划线
    illegal_chars = r'<>:"/\|?*'
    for char in illegal_chars:
        name = name.replace(char, '_')
    return name


def concat_audio_files(file_list_path: Path, output_path: Path) -> bool:
    """使用 FFmpeg concat 合并音频文件"""
    try:
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(file_list_path),
            "-c", "copy",
            str(output_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        print("错误：未找到 FFmpeg")
        return False


def process_dubbing(
    dubbing_json: dict,
    out_dir: Path,
    silence_gap: float | None = None,
    character_switch_gap: float | None = None,
    keep_segments: bool = True,
) -> Path | None:
    """处理配音稿，生成最终音频"""
    
    # 解析配置
    config = DubbingConfig()
    config.language = dubbing_json.get("language", "Chinese")
    config.default_mode = dubbing_json.get("default_mode", "custom-voice")
    config.silence_gap = silence_gap if silence_gap is not None else dubbing_json.get("silence_gap", 0.3)
    config.character_switch_gap = character_switch_gap if character_switch_gap is not None else dubbing_json.get("character_switch_gap", 0.5)
    
    character_map = dubbing_json.get("character_map", {})
    segments = dubbing_json.get("segments", [])
    
    if not segments:
        print("错误：配音稿中没有 segments")
        return None
    
    # 创建输出目录
    segments_dir = out_dir / "segments"
    segments_dir.mkdir(parents=True, exist_ok=True)
    
    # 获取 TTS 脚本路径
    try:
        tts_script = get_tts_script_path()
    except FileNotFoundError as e:
        print(f"错误：{e}")
        return None
    
    # 生成静音文件
    print(f"生成静音文件...")
    silence_normal = out_dir / f"silence_{config.silence_gap}s.wav"
    silence_switch = out_dir / f"silence_{config.character_switch_gap}s.wav"
    
    if not generate_silence_wav(silence_normal, config.silence_gap, config.sample_rate):
        return None
    if config.silence_gap != config.character_switch_gap:
        if not generate_silence_wav(silence_switch, config.character_switch_gap, config.sample_rate):
            return None
    else:
        silence_switch = silence_normal
    
    # 生成每个 segment 的音频
    generated_files: list[Path] = []
    prev_character: str | None = None
    failed_count = 0
    
    print(f"\n开始生成 {len(segments)} 个片段...\n")
    
    for i, segment in enumerate(segments):
        seg_id = segment.get("id", i + 1)
        character = segment.get("character", "旁白")
        text = segment.get("text", "")
        instruct = segment.get("instruct")
        seg_language = segment.get("language", config.language)
        
        if not text.strip():
            print(f"跳过空片段 #{seg_id}")
            continue
        
        # 确定模式和参数
        char_config = character_map.get(character, {})
        mode = char_config.get("mode", config.default_mode)
        speaker = segment.get("speaker") or char_config.get("speaker", "Vivian")
        
        # 生成文件名
        safe_char = sanitize_filename(character)
        seg_filename = f"seg_{seg_id:03d}_{safe_char}.wav"
        seg_path = segments_dir / seg_filename
        
        print(f"  [{seg_id}/{len(segments)}] {character}: {text[:30]}{'...' if len(text) > 30 else ''}")
        
        # 根据模式调用 TTS
        success = False
        if mode == "custom-voice":
            success = run_tts_custom_voice(
                tts_script=tts_script,
                text=text,
                language=seg_language,
                speaker=speaker,
                instruct=instruct,
                output_file=seg_path,
            )
        elif mode == "voice-design":
            voice_instruct = char_config.get("voice_instruct", "自然的声音")
            success = run_tts_voice_design(
                tts_script=tts_script,
                text=text,
                language=seg_language,
                voice_instruct=voice_instruct,
                segment_instruct=instruct,
                output_file=seg_path,
            )
        elif mode == "voice-clone":
            ref_audio = char_config.get("ref_audio", "")
            ref_text = char_config.get("ref_text", "")
            if not ref_audio:
                print(f"voice-clone 模式缺少 ref_audio，跳过")
                failed_count += 1
                continue
            success = run_tts_voice_clone(
                tts_script=tts_script,
                text=text,
                language=seg_language,
                ref_audio=ref_audio,
                ref_text=ref_text,
                output_file=seg_path,
            )
        else:
            print(f"未知模式: {mode}，使用 custom-voice")
            success = run_tts_custom_voice(
                tts_script=tts_script,
                text=text,
                language=seg_language,
                speaker=speaker,
                instruct=instruct,
                output_file=seg_path,
            )
        
        if not success or not seg_path.exists():
            print(f"生成失败")
            failed_count += 1
            continue
        
        generated_files.append(seg_path)
        
        # 判断是否需要添加静音
        if i < len(segments) - 1:  # 不是最后一个
            # 判断角色是否切换
            if prev_character is not None and prev_character != character:
                generated_files.append(silence_switch)
            else:
                generated_files.append(silence_normal)
        
        prev_character = character
    
    print(f"\n片段生成完成：成功 {len(segments) - failed_count}/{len(segments)}")
    
    if not generated_files:
        print("没有成功生成任何片段")
        return None
    
    # 生成 file_list.txt
    file_list_path = out_dir / "file_list.txt"
    with open(file_list_path, "w", encoding="utf-8") as f:
        for audio_file in generated_files:
            # FFmpeg concat 格式
            f.write(f"file '{audio_file.absolute()}'\n")
    
    # 合并音频
    source_name = dubbing_json.get("source", "output")
    if isinstance(source_name, str) and "." in source_name:
        source_name = source_name.rsplit(".", 1)[0]
    final_output = out_dir / f"{source_name}_final.wav"
    
    print(f"\n合并音频文件...")
    if concat_audio_files(file_list_path, final_output):
        print(f"最终音频已生成: {final_output}")
    else:
        print("音频合并失败")
        return None
    
    # 清理中间文件（如果不保留）
    if not keep_segments:
        print("清理中间文件...")
        shutil.rmtree(segments_dir)
        silence_normal.unlink(missing_ok=True)
        if silence_switch != silence_normal:
            silence_switch.unlink(missing_ok=True)
        file_list_path.unlink(missing_ok=True)
    
    return final_output


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="batch_dubbing.py",
        description="批量配音生成：读取配音稿 JSON → TTS → FFmpeg 合并",
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="输入配音稿 JSON 文件路径",
    )
    parser.add_argument(
        "--out-dir", "-o",
        default="outputs",
        help="输出目录（默认：outputs）",
    )
    parser.add_argument(
        "--silence-gap",
        type=float,
        default=None,
        help="普通段落间静音秒数（默认：使用 JSON 配置或 0.3）",
    )
    parser.add_argument(
        "--character-switch-gap",
        type=float,
        default=None,
        help="角色切换时静音秒数（默认：使用 JSON 配置或 0.5）",
    )
    parser.add_argument(
        "--keep-segments",
        action="store_true",
        default=True,
        help="保留中间生成的片段文件（默认：保留）",
    )
    parser.add_argument(
        "--clean-segments",
        action="store_true",
        help="合并后删除中间片段文件",
    )
    
    args = parser.parse_args()
    
    # 读取配音稿 JSON
    input_path = Path(args.input).expanduser()
    if not input_path.exists():
        print(f"输入文件不存在: {input_path}")
        return 1
    
    try:
        dubbing_json = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"JSON 解析失败: {e}")
        return 1
    
    # 确定输出目录
    out_dir = Path(args.out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # 复制原始配音稿到输出目录
    shutil.copy2(input_path, out_dir / input_path.name)
    
    # 处理配音
    keep_segments = not args.clean_segments
    result = process_dubbing(
        dubbing_json=dubbing_json,
        out_dir=out_dir,
        silence_gap=args.silence_gap,
        character_switch_gap=args.character_switch_gap,
        keep_segments=keep_segments,
    )
    
    if result:
        print(f"\n完成!最终文件: {result}")
        return 0
    else:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
