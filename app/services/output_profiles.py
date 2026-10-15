"""Fixed, explainable delivery profiles with auditable overrides."""
from __future__ import annotations

from typing import Any


OUTPUT_PROFILES: dict[str, dict[str, Any]] = {
    "podcast": {
        "id": "podcast",
        "label": "Podcast",
        "description": "Lossless master normalized to -16 LUFS.",
        "values": {"output_format": "wav", "normalize": True, "target_loudness_lufs": -16.0},
    },
    "youtube": {
        "id": "youtube",
        "label": "YouTube / video",
        "description": "WAV delivery normalized to -14 LUFS.",
        "values": {"output_format": "wav", "normalize": True, "target_loudness_lufs": -14.0},
    },
    "audiobook": {
        "id": "audiobook",
        "label": "Audiobook",
        "description": "Lossless spoken-word master normalized to -18 LUFS.",
        "values": {"output_format": "wav", "normalize": True, "target_loudness_lufs": -18.0},
    },
    "archive": {
        "id": "archive",
        "label": "Lossless archive",
        "description": "FLAC export with source loudness preserved.",
        "values": {"output_format": "flac", "normalize": False},
    },
    "source-master": {
        "id": "source-master",
        "label": "Source-quality master",
        "description": "WAV export with source loudness preserved.",
        "values": {"output_format": "wav", "normalize": False},
    },
}

OVERRIDABLE_FIELDS = {"output_format", "normalize", "target_loudness_lufs"}


def list_output_profiles() -> list[dict[str, Any]]:
    return [dict(profile) for profile in OUTPUT_PROFILES.values()]


def resolve_output_profile(profile_id: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    if profile_id not in OUTPUT_PROFILES:
        raise ValueError(f"Unknown output profile: {profile_id}")
    supplied = overrides or {}
    unknown = set(supplied) - OVERRIDABLE_FIELDS
    if unknown:
        raise ValueError(f"Unsupported output profile override(s): {', '.join(sorted(unknown))}")
    if "normalize" in supplied and not isinstance(supplied["normalize"], bool):
        raise ValueError("Output profile normalize override must be a boolean")
    resolved = dict(OUTPUT_PROFILES[profile_id]["values"])
    resolved.update(supplied)
    if resolved.get("output_format") not in {"wav", "mp3", "flac"}:
        raise ValueError("Output profile format must be wav, mp3, or flac")
    loudness = float(resolved.get("target_loudness_lufs", -16.0))
    if not -30.0 <= loudness <= -5.0:
        raise ValueError("Output profile loudness must be between -30 and -5 LUFS")
    resolved["target_loudness_lufs"] = loudness
    resolved["normalize"] = bool(resolved.get("normalize", False))
    return {
        "profile_id": profile_id,
        "profile_label": OUTPUT_PROFILES[profile_id]["label"],
        "resolved": resolved,
        "overrides": {key: supplied[key] for key in sorted(supplied)},
    }
