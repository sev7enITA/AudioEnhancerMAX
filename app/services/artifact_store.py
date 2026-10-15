"""Revision-bound audio exports. Published audio files are never overwritten."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import threading
import uuid
from pathlib import Path

from app.config import OUTPUT_DIR

_LOCK = threading.RLock()
FORMATS = {"wav", "mp3", "flac"}
VERSIONS = {"processed", "speech_edit", "watermarked", "tts"}


class StaleRevision(ValueError):
    """The requested revision is no longer the current result."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _manifest_path(file_id: str, version: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", file_id) or version not in VERSIONS:
        raise ValueError("Invalid artifact identity")
    return OUTPUT_DIR / f"{file_id}_{version}_artifact.json"


def _entry(path: Path) -> dict:
    return {"name": path.name, "sha256": sha256_file(path), "size_bytes": path.stat().st_size}


def _checked_path(entry: dict) -> Path:
    name = entry["name"]
    if Path(name).name != name:
        raise ValueError("Invalid artifact path")
    path = OUTPUT_DIR / name
    if sha256_file(path) != entry["sha256"]:
        raise ValueError("Audio artifact changed on disk; process it again")
    return path


def publish_audio(file_id: str, audio, sample_rate: int, fmt: str, version: str = "processed") -> dict:
    """Encode privately, then atomically point to a new immutable revision."""
    from app.utils.audio_io import save_audio
    if fmt not in FORMATS:
        raise ValueError("Unsupported audio format")
    manifest_path = _manifest_path(file_id, version)
    revision = uuid.uuid4().hex
    output = OUTPUT_DIR / f"{file_id}_{version}_{revision}.{fmt}"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    save_audio(audio, sample_rate, output, format=fmt)
    manifest = {"schema_version": 1, "file_id": file_id, "version": version,
                "revision": revision, "master_format": fmt, "exports": {fmt: _entry(output)}}
    with _LOCK:
        atomic_json(manifest_path, manifest)
    return manifest


def current_artifact(file_id: str, version: str = "processed") -> dict:
    """Adopt a pre-revision result once; new runs always have explicit masters."""
    path = _manifest_path(file_id, version)
    with _LOCK:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        legacy = [OUTPUT_DIR / f"{file_id}_{version}.{fmt}" for fmt in FORMATS]
        legacy = [item for item in legacy if item.is_file()]
        if not legacy:
            raise FileNotFoundError("No completed output for this operation")
        source = max(legacy, key=lambda item: item.stat().st_mtime_ns)
        revision = uuid.uuid4().hex
        fmt = source.suffix[1:]
        destination = OUTPUT_DIR / f"{file_id}_{version}_{revision}.{fmt}"
        shutil.copyfile(source, destination)
        manifest = {"schema_version": 1, "file_id": file_id, "version": version,
                    "revision": revision, "master_format": fmt,
                    "legacy_adoption": "Most recently modified pre-revision output",
                    "exports": {fmt: _entry(destination)}}
        atomic_json(path, manifest)
        return manifest


def resolve_export(file_id: str, fmt: str | None = None, version: str = "processed",
                   revision: str | None = None) -> tuple[Path, dict]:
    """Resolve or encode this revision's export, never a prior cached conversion."""
    from app.utils.audio_io import load_audio, save_audio
    with _LOCK:
        manifest = current_artifact(file_id, version)
        if revision is not None and revision != manifest["revision"]:
            raise StaleRevision("The result changed; reload the current output before downloading")
        fmt = fmt or manifest["master_format"]
        if fmt not in FORMATS:
            raise ValueError("Unsupported audio format")
        if fmt not in manifest["exports"]:
            source = _checked_path(manifest["exports"][manifest["master_format"]])
            audio, sr = load_audio(source, mono=False)
            if audio.ndim == 2 and audio.shape[0] <= 8:
                audio = audio.T
            output = OUTPUT_DIR / f"{file_id}_{version}_{manifest['revision']}.{fmt}"
            temporary = output.with_name(f".{output.stem}.{uuid.uuid4().hex}.{fmt}")
            try:
                save_audio(audio, sr, temporary, format=fmt)
                temporary.replace(output)
            finally:
                temporary.unlink(missing_ok=True)
            manifest["exports"][fmt] = _entry(output)
            atomic_json(_manifest_path(file_id, version), manifest)
        return _checked_path(manifest["exports"][fmt]), manifest
