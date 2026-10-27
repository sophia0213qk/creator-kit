#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
配音稿预处理脚本：将长文本切分为适合 TTS 的片段

用法：
    uv run prepare_dubbing.py --input article.txt --output article.dubbing.json

功能：
    1. 按段落和句号智能切分
    2. 检测语言
    3. 识别角色标记 【xxx】
    4. 生成基础配音稿 JSON（不含情感分析）

注意：
    - 情感/语气分析建议在 AI 对话中完成（更准确）
    - 本脚本生成的 JSON 可作为初稿，由 AI 或人工补充 instruct
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path


def detect_language(text: str) -> str:
    """简单检测主要语言"""
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    total_chars = len(re.findall(r'\w', text))
    
    if total_chars == 0:
        return "Chinese"
    
    chinese_ratio = chinese_chars / total_chars
    
    if chinese_ratio > 0.3:
        return "Chinese"
    else:
        return "English"


def get_default_speaker(language: str) -> str:
    """根据语言返回默认 speaker"""
    speaker_map = {
        "Chinese": "Vivian",
        "English": "Ryan",
        "Japanese": "Ono_Anna",
        "Korean": "Sohee",
    }
    return speaker_map.get(language, "Vivian")


def split_by_sentences(text: str, max_chars: int = 300) -> list[str]:
    """
    按句号切分文本
    
    处理中英文标点，保持引号内完整
    """
    # 句子结束标点
    sentence_endings = r'[。！？.!?]'
    
    # 先简单按句号切分
    # 注意：这是基础实现，不处理引号内的特殊情况
    parts = re.split(f'({sentence_endings})', text)
    
    sentences = []
    current = ""
    
    for i, part in enumerate(parts):
        if re.match(sentence_endings, part):
            # 这是标点，附加到当前句子
            current += part
            if current.strip():
                sentences.append(current.strip())
            current = ""
        else:
            current += part
    
    # 处理最后剩余的内容
    if current.strip():
        sentences.append(current.strip())
    
    # 如果某句太长，按逗号二次切分
    result = []
    for sentence in sentences:
        if len(sentence) > max_chars:
            # 按逗号切分
            comma_parts = re.split(r'([，,])', sentence)
            current_chunk = ""
            for j, cp in enumerate(comma_parts):
                if re.match(r'[，,]', cp):
                    current_chunk += cp
                else:
                    if len(current_chunk) + len(cp) > max_chars and current_chunk.strip():
                        result.append(current_chunk.strip())
                        current_chunk = cp
                    else:
                        current_chunk += cp
            if current_chunk.strip():
                result.append(current_chunk.strip())
        else:
            result.append(sentence)
    
    return [s for s in result if s.strip()]


def parse_character_marks(text: str) -> tuple[str | None, str]:
    """
    解析角色标记
    
    输入: "【旁白】这是一个阳光明媚的早晨。"
    输出: ("旁白", "这是一个阳光明媚的早晨。")
    
    输入: "这是普通文本"
    输出: (None, "这是普通文本")
    """
    pattern = r'^【([^】]+)】(.*)$'
    match = re.match(pattern, text.strip())
    
    if match:
        character = match.group(1).strip()
        content = match.group(2).strip()
        return character, content
    
    return None, text.strip()


def parse_emotion_marks(text: str) -> tuple[str | None, str]:
    """
    解析情绪/动作标记
    
    输入: "（惊讶地）小明！真的是你！"
    输出: ("惊讶地", "小明！真的是你！")
    """
    pattern = r'^[（(]([^）)]+)[）)](.*)$'
    match = re.match(pattern, text.strip())
    
    if match:
        emotion_hint = match.group(1).strip()
        content = match.group(2).strip()
        return emotion_hint, content
    
    return None, text.strip()


def process_text(
    text: str,
    language: str | None = None,
    max_chars: int = 300,
    default_speaker: str | None = None,
    default_pause_ms: int = 500,
) -> dict:
    """
    处理文本，生成配音稿 JSON
    """
    # 检测语言
    if not language or language.lower() == "auto":
        language = detect_language(text)
    
    # 确定默认 speaker
    if not default_speaker:
        default_speaker = get_default_speaker(language)
    
    # 按段落分割
    paragraphs = re.split(r'\n\s*\n', text.strip())
    
    segments = []
    character_map = {}
    segment_id = 0
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        # 按行处理（支持每行一个角色的格式）
        lines = para.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 解析角色标记
            character, content = parse_character_marks(line)
            
            if not content:
                continue
            
            # 解析情绪标记
            emotion_hint, content = parse_emotion_marks(content)
            
            # 切分成句子
            sentences = split_by_sentences(content, max_chars)
            
            for sentence in sentences:
                if not sentence.strip():
                    continue
                
                segment_id += 1
                
                # 确定角色
                char_name = character or "旁白"
                
                # 确定 speaker
                if char_name not in character_map:
                    character_map[char_name] = {
                        "speaker": default_speaker,
                        "default_instruct": None,
                    }
                
                speaker = character_map[char_name]["speaker"]
                
                segment = {
                    "id": segment_id,
                    "character": char_name,
                    "text": sentence,
                    "char_count": len(sentence),
                    "speaker": speaker,
                    "language": language,
                    "instruct": emotion_hint,  # 如果有情绪标记，用作初始 instruct
                    "emotion": None,  # 待 AI 分析
                    "pause_after_ms": default_pause_ms,
                }
                
                segments.append(segment)
    
    # 构建完整 JSON
    result = {
        "version": "1.0",
        "source": None,
        "language": language,
        "created_at": datetime.now().isoformat(),
        "total_segments": len(segments),
        "total_characters": sum(s["char_count"] for s in segments),
        "estimated_duration_sec": None,  # 可后续计算
        "character_map": character_map,
        "segments": segments,
    }
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description="配音稿预处理：将长文本切分为 TTS 片段"
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="输入文件路径 (txt/md)",
    )
    parser.add_argument(
        "--output", "-o",
        help="输出 JSON 文件路径（默认：输入文件名.dubbing.json）",
    )
    parser.add_argument(
        "--language", "-l",
        default="auto",
        help="语言：Chinese/English/auto（默认：auto）",
    )
    parser.add_argument(
        "--max-chars", "-m",
        type=int,
        default=300,
        help="每段最大字符数（默认：300）",
    )
    parser.add_argument(
        "--speaker", "-s",
        help="默认 speaker（默认根据语言自动选择）",
    )
    parser.add_argument(
        "--pause", "-p",
        type=int,
        default=500,
        help="段落间默认停顿毫秒数（默认：500）",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="格式化输出 JSON（默认：紧凑格式）",
    )
    
    args = parser.parse_args()
    
    # 读取输入文件
    input_path = Path(args.input).expanduser()
    if not input_path.exists():
        print(f"错误：输入文件不存在: {input_path}")
        return 1
    
    text = input_path.read_text(encoding="utf-8")
    
    # 处理文本
    result = process_text(
        text=text,
        language=args.language if args.language.lower() != "auto" else None,
        max_chars=args.max_chars,
        default_speaker=args.speaker,
        default_pause_ms=args.pause,
    )
    
    # 设置来源
    result["source"] = input_path.name
    
    # 确定输出路径
    if args.output:
        output_path = Path(args.output).expanduser()
    else:
        output_path = input_path.with_suffix(".dubbing.json")
    
    # 写入输出
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    indent = 2 if args.pretty else None
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=indent),
        encoding="utf-8",
    )
    
    print(f"配音稿已生成: {output_path}")
    print(f"   - 语言: {result['language']}")
    print(f"   - 片段数: {result['total_segments']}")
    print(f"   - 总字符: {result['total_characters']}")
    print(f"   - 角色: {', '.join(result['character_map'].keys())}")
    print()
    print("提示：")
    print("   - 生成的 JSON 不含情感分析，建议用 AI 补充 instruct 字段")
    print("   - 可以手动编辑 character_map 来分配不同的 speaker")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
