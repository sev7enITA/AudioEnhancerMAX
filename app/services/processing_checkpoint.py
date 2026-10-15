"""Compatible, lossless checkpoints for the deterministic local DSP pipeline."""
from __future__ import annotations

import hashlib
import json
import uuid
import zipfile
from importlib import metadata
from pathlib import Path

import numpy as np

from app.services.artifact_store import atomic_json, sha256_file


def processing_identity(source: Path, requested: dict, effective: dict, steps: list[str],
                        version: str, build: str, engines: list[dict]) -> str:
    packages = {}
    for name in ("numpy", "scipy", "soundfile", "av", "pedalboard", "pyloudnorm", "noisereduce"):
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = None
    payload = {"schema": 1, "source_sha256": sha256_file(source), "requested": requested,
               "effective": effective, "steps": steps, "app_version": version,
               "app_build": build, "engines": engines, "packages": packages}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load_checkpoint(directory: Path, identity: str, steps: list[str]):
    """Corrupt, legacy, incompatible or non-prefix checkpoints restart cleanly."""
    try:
        record = json.loads((directory / "meta.json").read_text())
        completed = record["completed_steps"]
        if record.get("identity") != identity or not completed or completed != steps[:len(completed)]:
            return None
        name = record["audio_file"]
        if Path(name).name != name or not name.endswith(".npz"):
            return None
        path = directory / name
        if sha256_file(path) != record["audio_sha256"]:
            return None
        with np.load(path, allow_pickle=False) as stored:
            audio = stored["audio"]
            sr = int(stored["sample_rate"])
        if audio.ndim not in (1, 2) or not audio.size or not np.isfinite(audio).all() or sr < 8000:
            return None
        return audio, sr, set(completed)
    except (OSError, ValueError, KeyError, TypeError, EOFError, zipfile.BadZipFile):
        return None


def save_checkpoint(directory: Path, identity: str, audio, sample_rate: int,
                    completed_steps: list[str]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    name = f"audio-{uuid.uuid4().hex}.npz"
    path = directory / name
    # np.savez retains the pipeline dtype and samples without PCM quantization.
    np.savez(path, audio=audio, sample_rate=sample_rate)
    atomic_json(directory / "meta.json", {"schema_version": 1, "identity": identity,
                "completed_steps": completed_steps, "audio_file": name,
                "audio_sha256": sha256_file(path)})
    # Only the last successfully committed snapshot is needed.
    for previous in directory.glob("audio-*.npz"):
        if previous != path:
            previous.unlink(missing_ok=True)
