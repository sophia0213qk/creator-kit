#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "qwen-tts",
#   "soundfile",
#   "torch",
# ]
# ///
from __future__ import annotations

import argparse
import os
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


def _parse_dtype(dtype: str):
    import torch

    dtype_normalized = dtype.strip().lower()
    if dtype_normalized in {"auto", ""}:
        return None
    if dtype_normalized in {"bf16", "bfloat16"}:
        return torch.bfloat16
    if dtype_normalized in {"fp16", "float16", "half"}:
        return torch.float16
    if dtype_normalized in {"fp32", "float32"}:
        return torch.float32
    raise ValueError(f"Unsupported dtype: {dtype!r} (choose: auto/bfloat16/float16/float32)")


def _default_device_map() -> str:
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda:0"
    except Exception:
        pass
    return "cpu"


def _write_first_wav(output_path: str, wavs, sample_rate: int) -> None:
    import soundfile as sf

    if not wavs:
        raise RuntimeError("Model returned no audio (empty wavs).")
    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    sf.write(output_path, wavs[0], sample_rate)


def _resolve_output_path(output: str, out_dir: str, filename_prefix: str) -> str:
    """
    Resolve output path.
    - If --output is provided and includes a directory, use it as-is.
    - If --output is provided as a filename, join with --out-dir.
    - If --output is omitted/empty, auto-generate a timestamped filename under --out-dir.
    """
    out_dir_path = Path(out_dir).expanduser()

    output_stripped = (output or "").strip()
    if output_stripped:
        output_path = Path(output_stripped).expanduser()
        if output_path.parent != Path("."):
            return str(output_path)
        return str(out_dir_path / output_path)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    auto_name = f"{filename_prefix}_{timestamp}.wav"
    return str(out_dir_path / auto_name)


@dataclass(frozen=True)
class CommonLoadArgs:
    model_id_or_path: str
    device_map: str
    dtype: str
    attn_implementation: str


def _load_model(args: CommonLoadArgs):
    from qwen_tts import Qwen3TTSModel

    load_kwargs: dict[str, Any] = {
        "device_map": args.device_map,
    }
    parsed_dtype = _parse_dtype(args.dtype)
    if parsed_dtype is not None:
        load_kwargs["dtype"] = parsed_dtype
    if args.attn_implementation and args.attn_implementation.strip().lower() != "auto":
        load_kwargs["attn_implementation"] = args.attn_implementation

    return Qwen3TTSModel.from_pretrained(args.model_id_or_path, **load_kwargs)


def _load_tokenizer(model_id_or_path: str, device_map: str):
    from qwen_tts import Qwen3TTSTokenizer

    return Qwen3TTSTokenizer.from_pretrained(model_id_or_path, device_map=device_map)


def _cmd_custom_voice(ns: argparse.Namespace) -> int:
    model = _load_model(
        CommonLoadArgs(
            model_id_or_path=ns.model,
            device_map=ns.device_map,
            dtype=ns.dtype,
            attn_implementation=ns.attn,
        )
    )

    speaker = (ns.speaker or "").strip()
    if not speaker:
        language_normalized = (ns.language or "").strip().lower()
        if language_normalized in {"chinese", "zh", "zh-cn", "zh-hans"}:
            speaker = "Vivian"
        elif language_normalized in {"english", "en"}:
            speaker = "Ryan"
        elif language_normalized in {"japanese", "ja"}:
            speaker = "Ono_Anna"
        elif language_normalized in {"korean", "ko"}:
            speaker = "Sohee"
        else:
            raise ValueError("custom-voice requires --speaker, unless --language is one of: Chinese/English/Japanese/Korean.")

    generate_kwargs: dict[str, Any] = {
        "text": ns.text,
        "language": ns.language,
        "speaker": speaker,
    }
    if ns.instruct is not None:
        generate_kwargs["instruct"] = ns.instruct

    wavs, sample_rate = model.generate_custom_voice(**generate_kwargs)
    output_path = _resolve_output_path(
        output=ns.output,
        out_dir=ns.out_dir,
        filename_prefix="qwen3tts_custom_voice",
    )
    _write_first_wav(output_path, wavs, sample_rate)
    return 0


def _cmd_voice_design(ns: argparse.Namespace) -> int:
    model = _load_model(
        CommonLoadArgs(
            model_id_or_path=ns.model,
            device_map=ns.device_map,
            dtype=ns.dtype,
            attn_implementation=ns.attn,
        )
    )
    wavs, sample_rate = model.generate_voice_design(
        text=ns.text,
        language=ns.language,
        instruct=ns.instruct,
    )
    output_path = _resolve_output_path(
        output=ns.output,
        out_dir=ns.out_dir,
        filename_prefix="qwen3tts_voice_design",
    )
    _write_first_wav(output_path, wavs, sample_rate)
    return 0


def _cmd_voice_clone(ns: argparse.Namespace) -> int:
    model = _load_model(
        CommonLoadArgs(
            model_id_or_path=ns.model,
            device_map=ns.device_map,
            dtype=ns.dtype,
            attn_implementation=ns.attn,
        )
    )

    if ns.x_vector_only_mode and not ns.ref_text:
        # 文档说明：x_vector_only_mode=True 时 ref_text 可省略，但质量可能降低
        pass
    else:
        if not ns.ref_text:
            raise ValueError("voice-clone requires --ref-text (or pass --x-vector-only-mode with reduced quality).")

    wavs, sample_rate = model.generate_voice_clone(
        text=ns.text,
        language=ns.language,
        ref_audio=ns.ref_audio,
        ref_text=ns.ref_text,
        x_vector_only_mode=ns.x_vector_only_mode,
    )
    output_path = _resolve_output_path(
        output=ns.output,
        out_dir=ns.out_dir,
        filename_prefix="qwen3tts_voice_clone",
    )
    _write_first_wav(output_path, wavs, sample_rate)
    return 0


def _cmd_tokenizer_roundtrip(ns: argparse.Namespace) -> int:
    tokenizer = _load_tokenizer(ns.model, ns.device_map)
    encoded = tokenizer.encode(ns.audio)
    wavs, sample_rate = tokenizer.decode(encoded)
    output_path = _resolve_output_path(
        output=ns.output,
        out_dir=ns.out_dir,
        filename_prefix="qwen3tts_tokenizer_roundtrip",
    )
    _write_first_wav(output_path, wavs, sample_rate)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_qwen3_tts.py",
        description="Qwen3-TTS local inference script (run via `uv run`).",
    )

    parser.add_argument(
        "--device-map",
        default=_default_device_map(),
        help="e.g. cuda:0 / cpu. Default: cuda:0 if CUDA available, else cpu.",
    )
    parser.add_argument(
        "--dtype",
        default="auto",
        help="auto / bfloat16 / float16 / float32 (FlashAttention2 usually needs bf16/fp16).",
    )
    parser.add_argument(
        "--attn",
        default="auto",
        help='auto / flash_attention_2 (if installed & supported) / other Transformers attention implementations.',
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    p_custom = subparsers.add_parser(
        "custom-voice",
        help="Run CustomVoice TTS.",
    )
    p_custom.add_argument(
        "--model",
        default="Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        help="Hugging Face model ID or local path.",
    )
    p_custom.add_argument("--text", required=True, help="Text to synthesize.")
    p_custom.add_argument(
        "--language",
        default="Auto",
        help="Language: Chinese/English/... or Auto.",
    )
    p_custom.add_argument(
        "--speaker",
        default="",
        help="Speaker name, e.g. Vivian / Ryan. If omitted, defaults by language: Chinese->Vivian, English->Ryan, Japanese->Ono_Anna, Korean->Sohee.",
    )
    p_custom.add_argument("--instruct", default=None, help="Optional: instruction (emotion/prosody/speed).")
    p_custom.add_argument(
        "--out-dir",
        default=".",
        help="Output directory (used when --output is omitted or is a filename).",
    )
    p_custom.add_argument(
        "--output",
        default="",
        help="Output wav path. If omitted, a timestamped filename will be generated under --out-dir.",
    )
    p_custom.set_defaults(func=_cmd_custom_voice)

    p_design = subparsers.add_parser(
        "voice-design",
        help="Run VoiceDesign TTS (voice described by an instruction).",
    )
    p_design.add_argument(
        "--model",
        default="Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
        help="Hugging Face model ID or local path.",
    )
    p_design.add_argument("--text", required=True, help="Text to synthesize.")
    p_design.add_argument(
        "--language",
        default="Auto",
        help="Language: Chinese/English/... or Auto.",
    )
    p_design.add_argument("--instruct", required=True, help="Natural-language voice/style description.")
    p_design.add_argument(
        "--out-dir",
        default=".",
        help="Output directory (used when --output is omitted or is a filename).",
    )
    p_design.add_argument(
        "--output",
        default="",
        help="Output wav path. If omitted, a timestamped filename will be generated under --out-dir.",
    )
    p_design.set_defaults(func=_cmd_voice_design)

    p_clone = subparsers.add_parser(
        "voice-clone",
        help="Run voice cloning using the Base model (reference audio + transcript).",
    )
    p_clone.add_argument(
        "--model",
        default="Qwen/Qwen3-TTS-12Hz-1.7B-Base",
        help="Hugging Face model ID or local path.",
    )
    p_clone.add_argument("--text", required=True, help="Text to synthesize.")
    p_clone.add_argument(
        "--language",
        default="Auto",
        help="Language: Chinese/English/... or Auto.",
    )
    p_clone.add_argument(
        "--ref-audio",
        required=True,
        help="Reference audio: local path or URL.",
    )
    p_clone.add_argument(
        "--ref-text",
        default="",
        help="Transcript for the reference audio (required unless --x-vector-only-mode).",
    )
    p_clone.add_argument(
        "--x-vector-only-mode",
        action="store_true",
        help="Use speaker embedding only (ref_text optional, quality may degrade).",
    )
    p_clone.add_argument(
        "--out-dir",
        default=".",
        help="Output directory (used when --output is omitted or is a filename).",
    )
    p_clone.add_argument(
        "--output",
        default="",
        help="Output wav path. If omitted, a timestamped filename will be generated under --out-dir.",
    )
    p_clone.set_defaults(func=_cmd_voice_clone)

    p_tok = subparsers.add_parser(
        "tokenizer-roundtrip",
        help="Tokenizer encode+decode roundtrip (validation / transport / preprocessing).",
    )
    p_tok.add_argument(
        "--model",
        default="Qwen/Qwen3-TTS-Tokenizer-12Hz",
        help="Hugging Face model ID or local path.",
    )
    p_tok.add_argument("--audio", required=True, help="Input audio: local path or URL.")
    p_tok.add_argument(
        "--out-dir",
        default=".",
        help="Output directory (used when --output is omitted or is a filename).",
    )
    p_tok.add_argument(
        "--output",
        default="",
        help="Output wav path. If omitted, a timestamped filename will be generated under --out-dir.",
    )
    p_tok.set_defaults(func=_cmd_tokenizer_roundtrip)

    return parser


def main() -> int:
    parser = build_parser()
    ns = parser.parse_args()
    func = getattr(ns, "func", None)
    assert func is not None
    return int(func(ns))


if __name__ == "__main__":
    raise SystemExit(main())

