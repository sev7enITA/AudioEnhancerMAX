"""Runtime capability inventory for truthful feature disclosure.

The registry intentionally relies on packaged modules and bundled assets instead
of configuration claims.  It is safe to call during startup because it does not
load any model weights.
"""
from __future__ import annotations

import importlib.util
from importlib import metadata
from typing import Any

from app.config import APP_STORE_MODE, bundled_whisper_model_available


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _package_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def _engine(
    engine_id: str,
    label: str,
    *,
    available: bool,
    mode: str,
    version: str | None = None,
    fallback: str | None = None,
    detail: str = "",
) -> dict[str, Any]:
    return {
        "id": engine_id,
        "label": label,
        "available": bool(available),
        "mode": mode,
        "version": version,
        "fallback": fallback,
        "detail": detail,
    }


def get_capability_registry() -> dict[str, Any]:
    """Return the engines that can actually run in this distribution."""
    faster_whisper = _module_available("faster_whisper")
    deepfilter = _module_available("df")
    noisereduce = _module_available("noisereduce")
    pyannote = _module_available("pyannote.audio")
    demucs = _module_available("demucs") and not APP_STORE_MODE
    audiosr = _module_available("audiosr")
    kokoro = _module_available("kokoro") and not APP_STORE_MODE
    edge_tts = _module_available("edge_tts")
    try:
        from app.services.voice_profiles import clone_adapter_capabilities

        voice_clone = clone_adapter_capabilities()
    except Exception:
        voice_clone = {"available": False, "detail": "Voice clone adapter unavailable"}

    engines = {
        "transcription": _engine(
            "faster-whisper-medium",
            "Faster-Whisper Medium",
            available=faster_whisper and (bundled_whisper_model_available() or not APP_STORE_MODE),
            mode="packaged" if bundled_whisper_model_available() else "runtime-managed",
            version=_package_version("faster-whisper"),
            detail="Local speech recognition; Store builds require the bundled model.",
        ),
        "noise_reduction": _engine(
            "deepfilternet" if deepfilter else "spectral-gating",
            "DeepFilterNet" if deepfilter else "Spectral gating",
            available=deepfilter or noisereduce,
            mode="neural" if deepfilter else "dsp-fallback",
            version=_package_version("deepfilternet") if deepfilter else _package_version("noisereduce"),
            fallback="spectral-gating" if deepfilter and noisereduce else None,
            detail=(
                "Neural enhancement with spectral fallback."
                if deepfilter
                else "Deterministic noisereduce fallback; no neural denoiser is packaged."
            ),
        ),
        "diarization": _engine(
            "pyannote-3.1" if pyannote else "mfcc-change-detection",
            "Pyannote 3.1" if pyannote else "MFCC change detection",
            available=True,
            mode="neural" if pyannote else "heuristic-fallback",
            version=_package_version("pyannote.audio") if pyannote else None,
            detail=(
                "Neural speaker diarization is available."
                if pyannote
                else "Approximate two-speaker segmentation; not production-grade diarization."
            ),
        ),
        "source_separation": _engine(
            "demucs",
            "Demucs",
            available=demucs,
            mode="neural" if demucs else "unavailable",
            version=_package_version("demucs") if demucs else None,
            detail="Not exposed in the Mac App Store build." if APP_STORE_MODE else "Optional local model.",
        ),
        "super_resolution": _engine(
            "audiosr" if audiosr else "harmonic-extension",
            "AudioSR" if audiosr else "Harmonic extension",
            available=True,
            mode="neural" if audiosr else "dsp-fallback",
            detail=(
                "Neural audio super-resolution is available."
                if audiosr
                else "Deterministic bandwidth extension; it does not reconstruct original information."
            ),
        ),
        "local_tts": _engine(
            "kokoro",
            "Kokoro",
            available=kokoro,
            mode="neural-local" if kokoro else "unavailable",
            version=_package_version("kokoro") if kokoro else None,
            detail="Disabled in the Mac App Store distribution." if APP_STORE_MODE else "Optional local synthesis.",
        ),
        "cloud_tts": _engine(
            "edge-tts",
            "Microsoft Edge Neural TTS",
            available=edge_tts,
            mode="external-network",
            version=_package_version("edge-tts") if edge_tts else None,
            detail="Text leaves this Mac only after the user starts synthesis.",
        ),
        "voice_clone": _engine(
            voice_clone.get("backend") or "makemyvoice-adapter",
            "MakeMyVoice Personal Voices",
            available=bool(voice_clone.get("available")) and not APP_STORE_MODE,
            mode=voice_clone.get("execution", "unavailable"),
            version=voice_clone.get("version"),
            detail=(
                "Not exposed in the Mac App Store build."
                if APP_STORE_MODE else voice_clone.get("detail", "")
            ),
        ),
        "smart_analysis": _engine(
            "audio-intelligence-v1",
            "Audio Intelligence v1",
            available=True,
            mode="deterministic-local",
            version="1",
            detail="Audio measurements and deterministic policy; no external model decides DSP settings.",
        ),
    }

    from app.services.runtime_settings import load_runtime_settings
    runtime_privacy = load_runtime_settings()
    engines["cloud_tts"]["allowed"] = runtime_privacy["external_services_allowed"]
    return {
        "schema_version": 1,
        "distribution": "app-store" if APP_STORE_MODE else "direct",
        "media_backend": "PyAV (embedded FFmpeg libraries)",
        "engines": engines,
        # Backward-compatible feature flags used by the existing interface.
        "transcription_model": engines["transcription"]["label"],
        "transcription_bundled": bundled_whisper_model_available(),
        "kokoro_local_tts": engines["local_tts"]["available"],
        "personal_voice_profiles": engines["voice_clone"]["available"],
        "demucs_music_separation": engines["source_separation"]["available"],
        "neural_denoise": engines["noise_reduction"]["mode"] == "neural",
        "neural_diarization": engines["diarization"]["mode"] == "neural",
        "neural_super_resolution": engines["super_resolution"]["mode"] == "neural",
        "non_destructive_speech_editor": True,
        "runtime_privacy": runtime_privacy,
    }


def engine_for_step(step: str) -> dict[str, Any]:
    """Resolve a processing step to the engine disclosed in job reports."""
    registry = get_capability_registry()["engines"]
    mappings = {
        "remove_noise": "noise_reduction",
        "keep_music": "source_separation",
        "frequency_restoration": "super_resolution",
    }
    if step in mappings:
        return dict(registry[mappings[step]])

    if step == "speech_edl_render":
        return _engine(
            "precision-speech-editor-v1",
            "Precision Speech Editor EDL",
            available=True,
            mode="reviewed-local",
            version="1",
            detail="Only user-approved cut and mute decisions are rendered; the source is preserved.",
        )

    heuristic_steps = {
        "remove_mouth_sounds",
        "remove_filler_words",
        "eliminate_hesitations",
        "remove_stuttering",
        "remove_breaths",
    }
    if step in heuristic_steps:
        return _engine(
            "speech-cleanup-heuristics",
            "Speech cleanup heuristics",
            available=True,
            mode="heuristic-local",
            detail="Rule-based detection; review the result with A/B comparison.",
        )

    return _engine(
        "native-dsp",
        "Local DSP",
        available=True,
        mode="deterministic-local",
        detail="Deterministic local signal processing.",
    )
