"""Run one Qwen3 VoiceDesign request inside the desktop app's network sandbox."""
import argparse
import json
from pathlib import Path

import mlx.core as mx
from mlx_audio.tts.utils import load_model
import numpy as np
import soundfile as sf


def _write_audio(results, output, rate, max_tokens):
    chunks = []
    tokens = 0
    for result in results:
        tokens += int(result.token_count or 0)
        rate = int(result.sample_rate)
        samples = np.asarray(result.audio, dtype=np.float32).reshape(-1)
        if samples.size:
            chunks.append(samples)

    if not chunks or tokens >= max_tokens:
        raise RuntimeError("Voice generation was incomplete")
    audio = np.concatenate(chunks)
    if not np.isfinite(audio).all() or not np.any(audio):
        raise RuntimeError("The generated audio is invalid")
    sf.write(output, audio, rate, subtype="FLOAT")


def _read_reference_passages(model, request, reference_dir):
    reference_text = (reference_dir / "reference.txt").read_text(encoding="utf-8").strip()
    for index, passage in enumerate(json.loads(request.read_text(encoding="utf-8"))):
        mx.random.seed(665063 + index)
        max_tokens = 4096
        results = model.generate(
            text=passage, ref_audio=str(reference_dir / "reference.wav"), ref_text=reference_text,
            lang_code="Italian", temperature=0.68, top_p=0.92, top_k=35, max_tokens=max_tokens,
            repetition_penalty=1.05, verbose=False, stream=False,
        )
        _write_audio(results, request.parent / f"{index}.wav", int(model.sample_rate), max_tokens)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--model", type=Path)
    parser.add_argument("--language", choices=("English", "Italian"))
    parser.add_argument("--text-file", type=Path)
    parser.add_argument("--instruct-file", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--reference-request", type=Path)
    parser.add_argument("--reference-dir", type=Path)
    args = parser.parse_args()

    if not mx.metal.is_available():
        raise RuntimeError("Metal is unavailable")
    mx.set_default_device(mx.gpu)
    if args.check:
        mx.eval(mx.array([1.0]) + 1.0)
        return

    model = load_model(str(args.model), strict=True)
    if args.reference_request:
        _read_reference_passages(model, args.reference_request, args.reference_dir)
        return

    max_tokens = 4096
    results = model.generate_voice_design(
        text=args.text_file.read_text(encoding="utf-8"),
        instruct=args.instruct_file.read_text(encoding="utf-8"),
        language=args.language,
        max_tokens=max_tokens,
        temperature=0.7,
        verbose=False,
        stream=False,
    )
    _write_audio(results, args.output, int(model.sample_rate), max_tokens)


if __name__ == "__main__":
    main()
