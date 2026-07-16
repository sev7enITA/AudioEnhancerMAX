"""First-launch system readiness checks for desktop distributions."""

from __future__ import annotations

import importlib.util
import json
import os
import platform
import shutil
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import (
    DATA_DIR,
    OUTPUT_DIR,
    PREFLIGHT_STATE_FILE,
    PRESETS_DIR,
    RESOURCE_DIR,
    UPLOAD_DIR,
)


MIN_MACOS_MAJOR = 13
MIN_MEMORY_GB = 8
RECOMMENDED_MEMORY_GB = 16
MIN_FREE_DISK_GB = 2
RECOMMENDED_FREE_DISK_GB = 5
CORE_MODULES = (
    "fastapi",
    "faster_whisper",
    "librosa",
    "noisereduce",
    "numpy",
    "pedalboard",
    "scipy",
    "soundfile",
    "torch",
    "uvicorn",
)
OPTIONAL_ENGINES = {
    "TTS": "Coqui XTTS",
    "demucs": "Demucs",
    "df": "DeepFilterNet",
    "kokoro": "Kokoro",
    "pyannote": "Pyannote diarization",
}


def _check(
    check_id: str,
    label: str,
    status: str,
    required: bool,
    detail: str,
    resolution: str = "",
) -> dict[str, Any]:
    return {
        "id": check_id,
        "label": label,
        "status": status,
        "required": required,
        "detail": detail,
        "resolution": resolution,
    }


def _macos_check() -> dict[str, Any]:
    system = platform.system()
    version = platform.mac_ver()[0]
    if system != "Darwin":
        return _check(
            "operating_system",
            "macOS version",
            "blocked",
            True,
            f"Detected {system or 'unknown operating system'}.",
            "Install the macOS build on a supported Mac.",
        )

    try:
        major = int(version.split(".", 1)[0])
    except (TypeError, ValueError):
        major = 0
    if major < MIN_MACOS_MAJOR:
        return _check(
            "operating_system",
            "macOS version",
            "blocked",
            True,
            f"macOS {version or 'unknown'} detected; macOS {MIN_MACOS_MAJOR} or later is required.",
            "Update macOS before using this build.",
        )
    return _check(
        "operating_system",
        "macOS version",
        "pass",
        True,
        f"macOS {version} is supported.",
    )


def _architecture_check() -> dict[str, Any]:
    architecture = platform.machine().lower()
    if architecture not in {"arm64", "aarch64"}:
        return _check(
            "architecture",
            "Apple Silicon",
            "blocked",
            True,
            f"Detected {architecture or 'unknown architecture'}; this package is built for Apple Silicon.",
            "Use the source distribution on this computer or install the matching package.",
        )
    return _check(
        "architecture",
        "Apple Silicon",
        "pass",
        True,
        f"Native {architecture} execution is available.",
    )


def _memory_check() -> dict[str, Any]:
    try:
        import psutil

        memory_gb = psutil.virtual_memory().total / (1024 ** 3)
    except Exception:
        return _check(
            "memory",
            "System memory",
            "warning",
            False,
            "Memory capacity could not be measured.",
            "Audio processing remains available; large AI models may require more memory.",
        )

    if memory_gb < MIN_MEMORY_GB:
        return _check(
            "memory",
            "System memory",
            "blocked",
            True,
            f"{memory_gb:.1f} GB detected; at least {MIN_MEMORY_GB} GB is required.",
            "Use a Mac with more memory or process the project from source with smaller models.",
        )
    if memory_gb < RECOMMENDED_MEMORY_GB:
        return _check(
            "memory",
            "System memory",
            "warning",
            False,
            f"{memory_gb:.1f} GB detected; {RECOMMENDED_MEMORY_GB} GB is recommended for large AI models.",
            "Core DSP remains available. Select smaller transcription models for long recordings.",
        )
    return _check(
        "memory",
        "System memory",
        "pass",
        True,
        f"{memory_gb:.1f} GB is available.",
    )


def _disk_check() -> dict[str, Any]:
    try:
        free_gb = shutil.disk_usage(DATA_DIR).free / (1024 ** 3)
    except OSError as exc:
        return _check(
            "disk_space",
            "Free disk space",
            "blocked",
            True,
            f"Disk capacity could not be measured: {exc}",
            "Verify access to the application data container.",
        )

    if free_gb < MIN_FREE_DISK_GB:
        return _check(
            "disk_space",
            "Free disk space",
            "blocked",
            True,
            f"{free_gb:.1f} GB is free; at least {MIN_FREE_DISK_GB} GB is required.",
            "Free disk space before importing audio.",
        )
    if free_gb < RECOMMENDED_FREE_DISK_GB:
        return _check(
            "disk_space",
            "Free disk space",
            "warning",
            False,
            f"{free_gb:.1f} GB is free; {RECOMMENDED_FREE_DISK_GB} GB is recommended.",
            "Short jobs can run, but large media files may need more space.",
        )
    return _check(
        "disk_space",
        "Free disk space",
        "pass",
        True,
        f"{free_gb:.1f} GB is free in the application data volume.",
    )


def _data_directory_check() -> dict[str, Any]:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=DATA_DIR, prefix="preflight-", delete=True):
            pass
    except OSError as exc:
        return _check(
            "data_directory",
            "Application data",
            "blocked",
            True,
            f"The application data directory is not writable: {exc}",
            "Verify the app sandbox and storage permissions.",
        )
    return _check(
        "data_directory",
        "Application data",
        "pass",
        True,
        "Private uploads, outputs and settings storage is writable.",
    )


def _core_runtime_check() -> dict[str, Any]:
    missing = [name for name in CORE_MODULES if importlib.util.find_spec(name) is None]
    if missing:
        return _check(
            "core_runtime",
            "Bundled processing engine",
            "blocked",
            True,
            "Missing packaged modules: " + ", ".join(missing),
            "Reinstall AudioEnhancerMAX. The package is incomplete and will not download code at runtime.",
        )
    return _check(
        "core_runtime",
        "Bundled processing engine",
        "pass",
        True,
        "Core DSP and application modules are present.",
    )


def _optional_engines_check() -> dict[str, Any]:
    missing = [label for module, label in OPTIONAL_ENGINES.items() if importlib.util.find_spec(module) is None]
    if missing:
        return _check(
            "optional_engines",
            "Optional packaged engines",
            "warning",
            False,
            "Unavailable optional engines: " + ", ".join(missing) + ".",
            "Existing fallback paths remain available. A Store package must bundle or hide each advertised optional engine.",
        )
    return _check(
        "optional_engines",
        "Optional packaged engines",
        "pass",
        False,
        "All declared optional processing engines are present.",
    )


def _media_tools_check() -> dict[str, Any]:
    bundled_ffmpeg = RESOURCE_DIR / "bin" / "ffmpeg"
    bundled_ffprobe = RESOURCE_DIR / "bin" / "ffprobe"
    if bundled_ffmpeg.is_file() and bundled_ffprobe.is_file():
        return _check(
            "media_tools",
            "Bundled media codecs",
            "pass",
            True,
            "FFmpeg and FFprobe are included in the application bundle.",
        )

    system_ffmpeg = shutil.which("ffmpeg")
    system_ffprobe = shutil.which("ffprobe")
    app_store_mode = os.getenv("AEMAX_APP_STORE") == "1"
    if app_store_mode:
        return _check(
            "media_tools",
            "Bundled media codecs",
            "blocked",
            True,
            "The App Store package does not contain FFmpeg and FFprobe.",
            "Install a complete AudioEnhancerMAX build. External package managers are not used.",
        )
    if system_ffmpeg and system_ffprobe:
        return _check(
            "media_tools",
            "Media codecs",
            "pass",
            True,
            "FFmpeg and FFprobe are available on this development system.",
        )
    return _check(
        "media_tools",
        "Media codecs",
        "warning",
        False,
        "FFmpeg or FFprobe is unavailable. WAV processing remains available, but compressed media support is limited.",
        "Use a self-contained distribution that includes the licensed media tools.",
    )


def _mps_check() -> dict[str, Any]:
    try:
        import torch

        available = bool(torch.backends.mps.is_available())
    except Exception:
        available = False
    if available:
        return _check(
            "metal_acceleration",
            "Metal acceleration",
            "pass",
            False,
            "PyTorch MPS acceleration is available.",
        )
    return _check(
        "metal_acceleration",
        "Metal acceleration",
        "warning",
        False,
        "MPS acceleration is unavailable; compatible processing falls back to CPU.",
        "No installation is required. Performance depends on the current hardware and model.",
    )


def _ollama_check() -> dict[str, Any]:
    try:
        request = urllib.request.Request("http://127.0.0.1:11434/api/tags")
        with urllib.request.urlopen(request, timeout=0.75) as response:
            payload = json.loads(response.read().decode("utf-8"))
        models = [item.get("name", "") for item in payload.get("models", [])]
        gemma_models = [name for name in models if "gemma" in name.lower()]
        if gemma_models:
            return _check(
                "local_ai",
                "Optional local AI",
                "pass",
                False,
                f"Local model available: {gemma_models[0]}.",
            )
        return _check(
            "local_ai",
            "Optional local AI",
            "warning",
            False,
            "Ollama is running, but no compatible Gemma model was found.",
            "Smart Mode uses deterministic local heuristics when no model is available.",
        )
    except (OSError, ValueError, urllib.error.URLError):
        return _check(
            "local_ai",
            "Optional local AI",
            "warning",
            False,
            "No local Ollama service was detected.",
            "Core audio processing remains available; Smart Mode uses deterministic local heuristics.",
        )


def _load_state() -> dict[str, Any]:
    try:
        return json.loads(PREFLIGHT_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def run_preflight(app_version: str) -> dict[str, Any]:
    checks = [
        _macos_check(),
        _architecture_check(),
        _memory_check(),
        _disk_check(),
        _data_directory_check(),
        _core_runtime_check(),
        _optional_engines_check(),
        _media_tools_check(),
        _mps_check(),
        _ollama_check(),
    ]
    required_failures = [item for item in checks if item["required"] and item["status"] == "blocked"]
    warnings = [item for item in checks if item["status"] == "warning"]
    status = "blocked" if required_failures else "degraded" if warnings else "ready"
    state = _load_state()
    acknowledged = state.get("version") == app_version
    return {
        "app_version": app_version,
        "status": status,
        "can_continue": not required_failures,
        "show_on_launch": bool(required_failures) or not acknowledged,
        "acknowledged": acknowledged,
        "checks": checks,
        "summary": {
            "passed": sum(item["status"] == "pass" for item in checks),
            "warnings": len(warnings),
            "blocked": len(required_failures),
        },
        "policy": {
            "distribution": "self-contained",
            "external_installation": False,
            "diagnostics_transmitted": False,
        },
    }


def configure_runtime(app_version: str) -> dict[str, Any]:
    for path in (DATA_DIR, UPLOAD_DIR, OUTPUT_DIR, PRESETS_DIR):
        path.mkdir(parents=True, exist_ok=True)

    report = run_preflight(app_version)
    if not report["can_continue"]:
        return report

    state = {
        "version": app_version,
        "configured_at": datetime.now(timezone.utc).isoformat(),
        "status": report["status"],
        "check_statuses": {item["id"]: item["status"] for item in report["checks"]},
    }
    temporary = PREFLIGHT_STATE_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
    temporary.replace(PREFLIGHT_STATE_FILE)
    return run_preflight(app_version)
