"""Persistent personal voices with a versioned MakeMyVoice runtime adapter.

AudioEnhancerMAX owns the stable profile contract (name, samples and TTS
defaults).  MakeMyVoice owns the cloning implementation.  The two are joined
through a subprocess boundary so that changing MakeMyVoice's backend does not
invalidate saved AudioEnhancerMAX profiles or force both applications into the
same Python dependency environment.
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from app.config import MAKEMYVOICE_ROOT, SOURCE_BASE_DIR, VOICE_PROFILES_DIR
from app.utils.audio_io import load_audio

logger = logging.getLogger(__name__)

REGISTRY_FILE = VOICE_PROFILES_DIR / "profiles.json"
PROFILE_ID_RE = re.compile(r"^[a-z0-9_\-]{1,64}$")
DEFAULT_SETTINGS = {
    "language": "it",
    "style": "neutral",
    "speed": 1.0,
    "pitch": 1.0,
    "warmth": 0.5,
}
_registry_lock = threading.RLock()
_capability_cache: tuple[float, dict[str, Any]] | None = None


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9_\-]+", "_", value.strip().lower()).strip("_")
    return slug[:40] or "voice"


def _require_profile_id(profile_id: str) -> str:
    if not PROFILE_ID_RE.fullmatch(profile_id or ""):
        raise ValueError("invalid voice profile id")
    return profile_id


def _load_registry() -> dict[str, Any]:
    try:
        data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("profiles"), dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"schema_version": 1, "profiles": {}}


def _save_registry(data: dict[str, Any]) -> None:
    VOICE_PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    temporary = REGISTRY_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(REGISTRY_FILE)


def _makemyvoice_python(root: Path | None = None) -> Path:
    return (root or MAKEMYVOICE_ROOT) / ".venv" / "bin" / "python"


def _worker_environment(root: Path) -> dict[str, str]:
    env = os.environ.copy()
    paths = [str(SOURCE_BASE_DIR), str(root)]
    if env.get("PYTHONPATH"):
        paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(paths)
    return env


def clone_adapter_capabilities(force: bool = False) -> dict[str, Any]:
    """Inspect MakeMyVoice without loading model weights."""
    global _capability_cache
    now = time.monotonic()
    if not force and _capability_cache and now - _capability_cache[0] < 15:
        return dict(_capability_cache[1])

    root = MAKEMYVOICE_ROOT
    python = _makemyvoice_python(root)
    unavailable = {
        "available": False,
        "adapter": "makemyvoice-subprocess-v1",
        "backend": "",
        "model": "",
        "version": None,
        "execution": "unavailable",
        "detail": "MakeMyVoice runtime not found",
    }
    if not python.is_file() or not (root / "makemyvoice").is_dir():
        _capability_cache = (now, unavailable)
        return dict(unavailable)

    command = [
        str(python), "-m", "app.services.voice_clone_worker",
        "--capabilities", "--mmv-root", str(root),
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            env=_worker_environment(root),
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "capability probe failed")
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        capability = json.loads(lines[-1])
        capability["available"] = bool(capability.get("available"))
        _capability_cache = (now, capability)
        return dict(capability)
    except Exception as exc:
        failed = dict(unavailable)
        failed["detail"] = f"MakeMyVoice probe failed: {type(exc).__name__}"
        _capability_cache = (now, failed)
        return failed


def _mmv_profile_stats(
    root: Path,
    source_profile_id: str,
    finetune_target_seconds: float = 15 * 60,
) -> dict[str, Any]:
    index = root / "data" / "voicebank" / source_profile_id / "index.json"
    try:
        raw = json.loads(index.read_text(encoding="utf-8"))
        entries = [entry for entry in raw.get("entries", []) if isinstance(entry, dict)]
    except (OSError, json.JSONDecodeError):
        entries = []
    seconds = sum(float(entry.get("duration", 0) or 0) for entry in entries)
    return {
        "samples": len(entries),
        "seconds": round(seconds, 1),
        "finetune_ready": seconds >= finetune_target_seconds,
        "finetune_progress": min(1.0, seconds / finetune_target_seconds),
    }


def _sync_makemyvoice_profiles(registry: dict[str, Any]) -> bool:
    """Link named MakeMyVoice banks while preserving AEMAX-specific defaults."""
    root = MAKEMYVOICE_ROOT
    source_registry = root / "data" / "voicebank" / "profiles.json"
    try:
        source = json.loads(source_registry.read_text(encoding="utf-8"))
        names = source.get("names", {})
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(names, dict):
        return False

    changed = False
    for source_id, display_name in names.items():
        source_id = str(source_id)
        if not PROFILE_ID_RE.fullmatch(source_id):
            continue
        safe_source_id = _slug(source_id)
        profile_id = f"mmv_{safe_source_id}"[:64]
        existing = registry["profiles"].get(profile_id)
        if existing is None:
            registry["profiles"][profile_id] = {
                "id": profile_id,
                "name": str(display_name),
                "source": "makemyvoice",
                "source_profile_id": source_id,
                "created_at": _now(),
                "updated_at": _now(),
                "consent_confirmed": True,
                "settings": dict(DEFAULT_SETTINGS),
            }
            changed = True
        elif existing.get("source_profile_id") != source_id:
            existing["source_profile_id"] = source_id
            existing["updated_at"] = _now()
            changed = True
    return changed


def _public_profile(profile: dict[str, Any], capability: dict[str, Any]) -> dict[str, Any]:
    finetune_target_seconds = max(
        1.0, float(capability.get("finetune_minimum_seconds", 15 * 60) or 15 * 60)
    )
    if profile.get("source") == "makemyvoice":
        stats = _mmv_profile_stats(
            MAKEMYVOICE_ROOT,
            profile.get("source_profile_id", ""),
            finetune_target_seconds,
        )
    else:
        samples = profile.get("samples", [])
        seconds = sum(float(sample.get("duration", 0) or 0) for sample in samples)
        stats = {
            "samples": len(samples),
            "seconds": round(seconds, 1),
            "finetune_ready": seconds >= finetune_target_seconds,
            "finetune_progress": min(1.0, seconds / finetune_target_seconds),
        }
    return {
        "id": profile["id"],
        "name": profile["name"],
        "source": profile.get("source", "audioenhancer"),
        "settings": {**DEFAULT_SETTINGS, **profile.get("settings", {})},
        "samples": stats["samples"],
        "seconds": stats["seconds"],
        "zero_shot_ready": stats["seconds"] >= 2 and capability.get("available", False),
        "finetune_ready": stats["finetune_ready"],
        "finetune_progress": stats["finetune_progress"],
        "finetune_target_seconds": finetune_target_seconds,
        "finetune_workflow": (
            "makemyvoice-managed"
            if profile.get("source") == "makemyvoice"
            else "reference-only"
        ),
        "engine": capability.get("backend") or "MakeMyVoice",
        "engine_version": capability.get("version"),
        "execution": capability.get("execution", "local"),
        "adapter": capability.get("adapter", "makemyvoice-subprocess-v1"),
        "available": bool(capability.get("available")) and stats["samples"] > 0,
        "detail": capability.get("detail", ""),
    }


def list_voice_profiles() -> dict[str, Any]:
    with _registry_lock:
        registry = _load_registry()
        if _sync_makemyvoice_profiles(registry):
            _save_registry(registry)
        profiles = list(registry["profiles"].values())
    capability = clone_adapter_capabilities()
    return {
        "profiles": [_public_profile(profile, capability) for profile in profiles],
        "adapter": capability,
    }


def get_voice_profile(profile_id: str, *, internal: bool = False) -> dict[str, Any]:
    profile_id = _require_profile_id(profile_id)
    with _registry_lock:
        registry = _load_registry()
        if _sync_makemyvoice_profiles(registry):
            _save_registry(registry)
        profile = registry["profiles"].get(profile_id)
        if profile is None:
            raise ValueError("voice profile not found")
        profile = json.loads(json.dumps(profile))
    if internal:
        return profile
    return _public_profile(profile, clone_adapter_capabilities())


def update_voice_profile(profile_id: str, name: str | None, settings: dict[str, Any]) -> dict[str, Any]:
    profile_id = _require_profile_id(profile_id)
    with _registry_lock:
        registry = _load_registry()
        profile = registry["profiles"].get(profile_id)
        if profile is None:
            raise ValueError("voice profile not found")
        if name:
            profile["name"] = name.strip()
        profile["settings"] = {**DEFAULT_SETTINGS, **settings}
        profile["updated_at"] = _now()
        _save_registry(registry)
    return get_voice_profile(profile_id)


def _sample_quality(audio: np.ndarray) -> float:
    audio = np.asarray(audio, dtype=np.float32)
    if not len(audio):
        return 0.0
    magnitude = np.abs(audio)
    rms = float(np.sqrt(np.mean(np.square(audio))) + 1e-9)
    active_ratio = float(np.mean(magnitude > max(0.004, rms * 0.25)))
    clipping = float(np.mean(magnitude >= 0.995))
    level_score = 1.0 - min(1.0, abs(20 * math.log10(rms) + 22) / 35)
    return round(max(0.0, min(1.0, 0.55 * active_ratio + 0.45 * level_score - 4 * clipping)), 3)


def _write_local_samples(
    profile: dict[str, Any],
    source_path: Path,
    transcript: str,
    language: str,
) -> list[dict[str, Any]]:
    audio, sr = load_audio(source_path, sr=24000, mono=True)
    duration = len(audio) / sr
    segments: list[dict[str, Any]] = []

    if transcript.strip() and duration <= 15:
        segments = [{"start": 0.0, "end": duration, "text": transcript.strip()}]
    else:
        from app.services.transcription import transcribe

        result = transcribe(audio, sr, language=language or None)
        for segment in result.get("segments", []):
            text = str(segment.get("text", "")).strip()
            start = max(0.0, float(segment.get("start", 0) or 0))
            end = min(duration, float(segment.get("end", duration) or duration))
            if text and 2.0 <= end - start <= 15.0:
                segments.append({"start": start, "end": end, "text": text})

    if not segments:
        if transcript.strip() and duration <= 30:
            segments = [{"start": 0.0, "end": duration, "text": transcript.strip()}]
        else:
            raise RuntimeError("No 2-15 second speech segment with a usable transcript was found")

    profile_dir = VOICE_PROFILES_DIR / profile["id"] / "samples"
    profile_dir.mkdir(parents=True, exist_ok=True)
    added: list[dict[str, Any]] = []
    for segment in segments:
        start_sample = int(segment["start"] * sr)
        end_sample = int(segment["end"] * sr)
        clip = np.asarray(audio[start_sample:end_sample], dtype=np.float32)
        if len(clip) < 2 * sr:
            continue
        sample_id = uuid.uuid4().hex[:12]
        filename = f"sample_{sample_id}.wav"
        sf.write(profile_dir / filename, clip, sr, subtype="PCM_16")
        added.append({
            "id": sample_id,
            "file": filename,
            "text": segment["text"],
            "duration": round(len(clip) / sr, 3),
            "quality": _sample_quality(clip),
            "added_at": _now(),
        })
    if not added:
        raise RuntimeError("The recording did not contain a long enough voice segment")
    return added


def _enroll_makemyvoice(profile: dict[str, Any], source_path: Path) -> None:
    root = MAKEMYVOICE_ROOT
    python = _makemyvoice_python(root)
    command = [
        str(python), "-m", "makemyvoice", "enroll", str(source_path),
        "--profile", profile["source_profile_id"],
    ]
    completed = subprocess.run(
        command,
        cwd=root,
        env=_worker_environment(root),
        capture_output=True,
        text=True,
        timeout=1800,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"MakeMyVoice enrollment failed: {detail[-600:]}")


def enroll_voice_profile(
    *,
    source_path: Path,
    name: str,
    profile_id: str | None,
    transcript: str,
    consent_confirmed: bool,
    settings: dict[str, Any],
) -> dict[str, Any]:
    if not consent_confirmed:
        raise ValueError("voice-owner consent must be confirmed")
    if not source_path.is_file():
        raise ValueError("voice sample not found")

    with _registry_lock:
        registry = _load_registry()
        _sync_makemyvoice_profiles(registry)
        if profile_id:
            profile_id = _require_profile_id(profile_id)
            profile = registry["profiles"].get(profile_id)
            if profile is None:
                raise ValueError("voice profile not found")
        else:
            base = _slug(name)
            profile_id = f"voice_{base}_{uuid.uuid4().hex[:6]}"[:64]
            profile = {
                "id": profile_id,
                "name": name.strip(),
                "source": "audioenhancer",
                "created_at": _now(),
                "updated_at": _now(),
                "consent_confirmed": True,
                "settings": {**DEFAULT_SETTINGS, **settings},
                "samples": [],
            }
            registry["profiles"][profile_id] = profile
            _save_registry(registry)

    try:
        if profile.get("source") == "makemyvoice":
            _enroll_makemyvoice(profile, source_path)
            added_count = 0
        else:
            added = _write_local_samples(
                profile, source_path, transcript, str(settings.get("language", "it"))
            )
            added_count = len(added)
            with _registry_lock:
                registry = _load_registry()
                stored = registry["profiles"][profile_id]
                stored.setdefault("samples", []).extend(added)
                stored["settings"] = {**DEFAULT_SETTINGS, **settings}
                stored["updated_at"] = _now()
                _save_registry(registry)
    except Exception:
        if profile.get("source") != "makemyvoice" and not profile.get("samples"):
            with _registry_lock:
                registry = _load_registry()
                registry["profiles"].pop(profile_id, None)
                _save_registry(registry)
            shutil.rmtree(VOICE_PROFILES_DIR / profile_id, ignore_errors=True)
        raise

    result = get_voice_profile(profile_id)
    result["added_samples"] = added_count
    return result


def _reference_entries(profile: dict[str, Any]) -> tuple[Path, list[dict[str, Any]]]:
    if profile.get("source") == "makemyvoice":
        root = MAKEMYVOICE_ROOT / "data" / "voicebank" / profile["source_profile_id"]
        try:
            raw = json.loads((root / "index.json").read_text(encoding="utf-8"))
            entries = [entry for entry in raw.get("entries", []) if isinstance(entry, dict)]
        except (OSError, json.JSONDecodeError):
            entries = []
        eligible = [entry for entry in entries if float(entry.get("rp_distance", 1)) <= 0.25]
        if sum(float(entry.get("duration", 0) or 0) for entry in eligible) < 6:
            eligible = entries
        eligible.sort(key=lambda entry: -(
            float(entry.get("pesq", 0) or 0) - 3.2 * float(entry.get("rp_distance", 1) or 1)
        ))
        return root, eligible

    root = VOICE_PROFILES_DIR / profile["id"] / "samples"
    entries = list(profile.get("samples", []))
    entries.sort(key=lambda entry: -float(entry.get("quality", 0) or 0))
    return root, entries


def build_profile_reference(profile_id: str, target_seconds: float = 8.0) -> tuple[np.ndarray, int, str, dict[str, Any]]:
    profile = get_voice_profile(profile_id, internal=True)
    root, entries = _reference_entries(profile)
    chosen: list[tuple[np.ndarray, str]] = []
    total = 0.0
    for entry in entries:
        path = root / str(entry.get("file", ""))
        text = str(entry.get("text", "")).strip()
        if not path.is_file() or not text:
            continue
        audio, sr = load_audio(path, sr=24000, mono=True)
        if len(audio) < sr:
            continue
        chosen.append((np.asarray(audio, dtype=np.float32), text))
        total += len(audio) / sr
        if total >= target_seconds:
            break
    if not chosen:
        raise RuntimeError("The selected voice profile has no usable reference audio")

    fade = int(0.02 * 24000)
    parts: list[np.ndarray] = []
    for index, (clip, _) in enumerate(chosen):
        clip = clip.copy()
        if index and len(clip) > fade and len(parts[-1]) > fade:
            ramp = np.linspace(0, 1, fade, dtype=np.float32)
            parts[-1][-fade:] *= 1 - ramp
            clip[:fade] *= ramp
        parts.append(clip)
    reference = np.concatenate(parts)
    reference_text = ". ".join(text for _, text in chosen)
    return reference, 24000, reference_text, profile


def synthesize_voice_profile(text: str, profile_id: str, speed: float = 1.0) -> tuple[np.ndarray, int, dict[str, Any]]:
    capability = clone_adapter_capabilities(force=True)
    if not capability.get("available"):
        raise RuntimeError(capability.get("detail") or "MakeMyVoice runtime is unavailable")
    reference, sr, reference_text, profile = build_profile_reference(profile_id)
    root = MAKEMYVOICE_ROOT
    python = _makemyvoice_python(root)

    with tempfile.TemporaryDirectory(prefix="aemax-voice-", dir=VOICE_PROFILES_DIR) as temporary:
        temp = Path(temporary)
        reference_path = temp / "reference.wav"
        request_path = temp / "request.json"
        output_path = temp / "output.wav"
        result_path = temp / "result.json"
        sf.write(reference_path, reference, sr, subtype="PCM_16")
        request_path.write_text(json.dumps({
            "text": text,
            "reference_audio": str(reference_path),
            "reference_text": reference_text,
            "output_audio": str(output_path),
            "result": str(result_path),
            "speed": speed,
            "source_profile_id": profile.get("source_profile_id"),
        }, ensure_ascii=False), encoding="utf-8")
        command = [
            str(python), "-m", "app.services.voice_clone_worker",
            "--request", str(request_path), "--mmv-root", str(root),
        ]
        completed = subprocess.run(
            command,
            cwd=root,
            env=_worker_environment(root),
            capture_output=True,
            text=True,
            timeout=1800,
            check=False,
        )
        if completed.returncode != 0 or not output_path.is_file():
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(f"Voice cloning failed: {detail[-800:]}")
        audio, output_sr = sf.read(output_path, dtype="float32")
        metadata = {}
        try:
            metadata = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass

    return np.asarray(audio, dtype=np.float32), int(output_sr), {
        "engine": metadata.get("backend", capability.get("backend", "makemyvoice")),
        "engine_version": metadata.get("version", capability.get("version")),
        "execution": metadata.get("execution", capability.get("execution", "local-metal")),
        "model": metadata.get("model", capability.get("model")),
        "personal_model": bool(metadata.get("personal_model", False)),
        "adapter": "makemyvoice-subprocess-v1",
        "voice_profile_id": profile_id,
        "voice_profile_name": profile["name"],
    }
