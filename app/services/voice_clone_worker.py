"""Isolated MakeMyVoice adapter executed by its own Python environment."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf


def _chunks(text: str, limit: int = 320) -> list[str]:
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    chunks: list[str] = []
    current = ""
    for sentence in sentences or [text.strip()]:
        if current and len(current) + len(sentence) + 1 > limit:
            chunks.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current)
    return chunks


def _load_runtime(root: Path):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from makemyvoice.config import load_config
    from makemyvoice.version import __version__

    return load_config(), __version__


def _execution_for_backend(backend: str) -> str:
    if "mlx" in backend:
        return "local-metal"
    if backend == "s2s":
        return "local-hybrid"
    return "local"


def capabilities(root: Path) -> dict:
    try:
        cfg, version = _load_runtime(root)
        return {
            "available": True,
            "adapter": "makemyvoice-subprocess-v1",
            "backend": cfg.tts.backend,
            "model": cfg.tts.model,
            "steps": cfg.tts.steps,
            "version": version,
            "execution": _execution_for_backend(cfg.tts.backend),
            "finetune_minimum_seconds": cfg.finetune.minimum_seconds,
            "detail": "MakeMyVoice runtime ready",
        }
    except Exception as exc:
        return {
            "available": False,
            "adapter": "makemyvoice-subprocess-v1",
            "backend": "",
            "model": "",
            "version": None,
            "execution": "unavailable",
            "detail": f"{type(exc).__name__}: {exc}",
        }


def synthesize(request_path: Path, root: Path) -> None:
    request = json.loads(request_path.read_text(encoding="utf-8"))
    cfg, version = _load_runtime(root)
    from makemyvoice.audio import io as mmv_io
    from makemyvoice.tts.base import build

    model = cfg.tts.model
    personal_model = False
    source_profile_id = str(request.get("source_profile_id") or "").strip()
    if cfg.tts.backend == "f5_mlx" and source_profile_id:
        try:
            from makemyvoice.finetune import status as finetune_status

            fine_tune = finetune_status(cfg, source_profile_id)
            model_dir = Path(fine_tune.get("paths", {}).get("model", ""))
            if fine_tune.get("active") and model_dir.is_dir():
                model = str(model_dir)
                personal_model = True
        except Exception:
            # A stale or changing fine-tune API must never break the known
            # zero-shot path. The active model is an optional improvement.
            personal_model = False

    reference, reference_sr = sf.read(request["reference_audio"], dtype="float32")
    if reference.ndim > 1:
        reference = reference.mean(axis=1)
    cloner = build(
        cfg.tts.backend,
        model,
        steps=cfg.tts.steps,
        command=cfg.tts.external_commands.get(cfg.tts.backend),
        reference_sample_rate=int(reference_sr),
        timeout_seconds=cfg.tts.external_timeout_seconds,
    )
    if int(reference_sr) != int(cloner.sample_rate):
        reference = mmv_io.resample(reference, int(reference_sr), int(cloner.sample_rate))

    parts: list[np.ndarray] = []
    for index, chunk in enumerate(_chunks(str(request["text"]))):
        speed = float(request.get("speed", 1.0))
        # MakeMyVoice normally receives an exact replacement-slot duration.
        # Free-form TTS has no slot, so derive a conservative spoken duration
        # instead of leaving F5's total-sequence length unconstrained (which
        # can yield only a fraction of a second after the reference prefix).
        word_count = max(1, len(re.findall(r"\b[\w'’-]+\b", chunk)))
        target_seconds = max(0.9, word_count / (2.55 * max(0.5, speed)))
        generated = cloner.synthesize(
            chunk,
            np.asarray(reference, dtype=np.float32),
            str(request["reference_text"]),
            target_seconds=target_seconds,
            seed=1729 + index,
            speed=speed,
        )
        generated = np.asarray(generated, dtype=np.float32).reshape(-1)
        if len(generated):
            parts.append(generated)
            parts.append(np.zeros(int(cloner.sample_rate * 0.16), dtype=np.float32))
    if not parts:
        raise RuntimeError("MakeMyVoice returned no audio")
    audio = np.concatenate(parts[:-1])
    sf.write(request["output_audio"], audio, cloner.sample_rate, subtype="PCM_16")
    Path(request["result"]).write_text(json.dumps({
        "backend": cloner.name,
        "version": version,
        "execution": _execution_for_backend(cfg.tts.backend),
        "sample_rate": cloner.sample_rate,
        "model": model,
        "personal_model": personal_model,
    }), encoding="utf-8")
    cloner.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mmv-root", required=True, type=Path)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--capabilities", action="store_true")
    args = parser.parse_args()
    if args.capabilities:
        print(json.dumps(capabilities(args.mmv_root)))
        return
    if args.request is None:
        parser.error("--request is required")
    synthesize(args.request, args.mmv_root)


if __name__ == "__main__":
    main()
