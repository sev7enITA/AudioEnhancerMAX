"""Deterministic, local audio diagnosis and processing recommendations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


EPSILON = 1e-10
PROFILE_NAMES = ("conservative", "balanced", "maximum")


@dataclass(frozen=True)
class AnalysisThresholds:
    clipping_ratio: float = 0.0001
    low_level_dbfs: float = -28.0
    noisy_snr_db: float = 16.0
    severe_noise_snr_db: float = 9.0
    excessive_silence_ratio: float = 0.35
    dc_offset: float = 0.015
    hum_ratio: float = 0.10


def _db(value: float) -> float:
    return float(20.0 * np.log10(max(float(value), EPSILON)))


def _representative_audio(audio: np.ndarray, sr: int, seconds_per_section: int = 20) -> np.ndarray:
    """Use start, middle and end for long files without resampling their spectrum."""
    samples = np.asarray(audio, dtype=np.float32).reshape(-1)
    samples = np.nan_to_num(samples, nan=0.0, posinf=1.0, neginf=-1.0)
    section = max(1, int(sr * seconds_per_section))
    if len(samples) <= section * 3:
        return samples
    middle = max(0, (len(samples) - section) // 2)
    return np.concatenate((samples[:section], samples[middle:middle + section], samples[-section:]))


def _frame_rms(audio: np.ndarray, sr: int) -> np.ndarray:
    frame = max(256, int(sr * 0.05))
    hop = max(128, int(sr * 0.025))
    if len(audio) < frame:
        padded = np.pad(audio, (0, frame - len(audio)))
        return np.array([np.sqrt(np.mean(padded * padded) + EPSILON)], dtype=np.float64)
    starts = np.arange(0, len(audio) - frame + 1, hop)
    return np.array(
        [np.sqrt(np.mean(audio[start:start + frame] ** 2) + EPSILON) for start in starts],
        dtype=np.float64,
    )


def _spectrum_metrics(audio: np.ndarray, sr: int) -> dict[str, float]:
    if not len(audio):
        return {
            "spectral_centroid_hz": 0.0,
            "spectral_rolloff_95_hz": 0.0,
            "spectral_flatness": 0.0,
            "high_frequency_ratio": 0.0,
            "low_frequency_ratio": 0.0,
            "hum_50_ratio": 0.0,
            "hum_60_ratio": 0.0,
        }

    from scipy.signal import welch

    nperseg = min(8192, len(audio))
    frequencies, power = welch(audio, fs=sr, nperseg=nperseg, noverlap=nperseg // 2)
    power = np.maximum(power.astype(np.float64), 0.0)
    total = float(np.sum(power)) + EPSILON
    centroid = float(np.sum(frequencies * power) / total)
    normalized_power = np.maximum(power / total, EPSILON)
    spectral_flatness = float(np.exp(np.mean(np.log(normalized_power))) / np.mean(normalized_power))
    cumulative = np.cumsum(power)
    rolloff_index = min(int(np.searchsorted(cumulative, cumulative[-1] * 0.95)), len(frequencies) - 1)

    def band_ratio(low: float, high: float) -> float:
        mask = (frequencies >= low) & (frequencies <= min(high, sr / 2))
        return float(np.sum(power[mask]) / total)

    def harmonic_hum_ratio(fundamental: float) -> float:
        numerator = 0.0
        for harmonic in range(1, 5):
            center = fundamental * harmonic
            mask = np.abs(frequencies - center) <= 2.0
            numerator += float(np.sum(power[mask]))
        reference = float(np.sum(power[(frequencies >= 20) & (frequencies <= 1000)])) + EPSILON
        return numerator / reference

    high_start = min(10000.0, sr * 0.35)
    return {
        "spectral_centroid_hz": round(centroid, 1),
        "spectral_rolloff_95_hz": round(float(frequencies[rolloff_index]), 1),
        "spectral_flatness": round(spectral_flatness, 6),
        "high_frequency_ratio": round(band_ratio(high_start, sr / 2), 6),
        "low_frequency_ratio": round(band_ratio(20, 100), 6),
        "hum_50_ratio": round(harmonic_hum_ratio(50), 6),
        "hum_60_ratio": round(harmonic_hum_ratio(60), 6),
    }


def _issue(
    issue_id: str,
    label: str,
    severity: str,
    confidence: float,
    evidence: str,
    recommendation: str,
) -> dict[str, Any]:
    return {
        "id": issue_id,
        "label": label,
        "severity": severity,
        "confidence": round(float(np.clip(confidence, 0.0, 1.0)), 2),
        "evidence": evidence,
        "recommendation": recommendation,
    }


def analyze_audio_quality(audio: np.ndarray, sr: int) -> dict[str, Any]:
    """Measure common quality risks without sending audio or loading an AI model."""
    if sr <= 0:
        raise ValueError("Sample rate must be positive")
    original = np.asarray(audio, dtype=np.float32).reshape(-1)
    if not len(original):
        raise ValueError("Audio is empty")

    representative = _representative_audio(original, sr)
    frame_rms = _frame_rms(representative, sr)
    frame_db = 20.0 * np.log10(np.maximum(frame_rms, EPSILON))
    active = frame_rms[frame_db > -55.0]
    if not len(active):
        active = frame_rms

    rms = float(np.sqrt(np.mean(representative ** 2) + EPSILON))
    peak = float(np.max(np.abs(representative)))
    noise_floor = float(np.percentile(frame_rms, 20))
    speech_level = float(np.percentile(active, 80))
    spectrum = _spectrum_metrics(representative, sr)
    energy_contrast = speech_level / max(noise_floor, EPSILON)
    if energy_contrast < 1.33:
        # Continuous audio has no quiet frames from which to estimate a noise
        # floor. Spectral flatness separates broadband noise from tonal audio.
        snr = 8.0 if spectrum["spectral_flatness"] > 0.18 else 28.0
    else:
        snr = float(np.clip(_db(energy_contrast), 0.0, 60.0))
    dynamic_range = max(0.0, _db(np.percentile(active, 95) / max(np.percentile(active, 10), EPSILON)))
    clipping_ratio = float(np.mean(np.abs(representative) >= 0.999))
    silence_ratio = float(np.mean(frame_db < -45.0))
    dc_offset = float(abs(np.mean(representative)))
    zero_crossing_rate = float(np.mean(np.abs(np.diff(np.signbit(representative))))) if len(representative) > 1 else 0.0

    metrics: dict[str, Any] = {
        "duration_seconds": round(len(original) / sr, 3),
        "analyzed_seconds": round(len(representative) / sr, 3),
        "sample_rate": sr,
        "rms_dbfs": round(_db(rms), 2),
        "peak_dbfs": round(_db(peak), 2),
        "crest_factor_db": round(_db(peak / max(rms, EPSILON)), 2),
        "dynamic_range_db": round(dynamic_range, 2),
        "estimated_snr_db": round(snr, 2),
        "noise_floor_dbfs": round(_db(noise_floor), 2),
        "silence_ratio": round(silence_ratio, 4),
        "clipping_ratio": round(clipping_ratio, 6),
        "dc_offset": round(dc_offset, 6),
        "zero_crossing_rate": round(zero_crossing_rate, 5),
        **spectrum,
    }

    thresholds = AnalysisThresholds()
    issues: list[dict[str, Any]] = []
    if clipping_ratio >= thresholds.clipping_ratio:
        severe = clipping_ratio >= 0.005
        issues.append(_issue(
            "clipping", "Clipping detected", "high" if severe else "medium",
            min(0.99, 0.65 + clipping_ratio * 30),
            f"{clipping_ratio * 100:.3f}% of analyzed samples are at full scale.",
            "Use conservative processing; clipped peaks cannot be fully reconstructed.",
        ))
    if metrics["rms_dbfs"] < thresholds.low_level_dbfs:
        issues.append(_issue(
            "low_level", "Low recording level", "medium", 0.86,
            f"Average level is {metrics['rms_dbfs']:.1f} dBFS.",
            "Normalize after cleanup to avoid amplifying noise before denoising.",
        ))
    if snr < thresholds.noisy_snr_db:
        severe = snr < thresholds.severe_noise_snr_db
        issues.append(_issue(
            "background_noise", "Background noise", "high" if severe else "medium",
            min(0.96, max(0.58, (thresholds.noisy_snr_db - snr) / 16 + 0.55)),
            f"Estimated signal-to-noise ratio is {snr:.1f} dB.",
            "Apply noise reduction before EQ and loudness normalization.",
        ))
    if silence_ratio > thresholds.excessive_silence_ratio:
        issues.append(_issue(
            "excessive_silence", "Long or frequent silence", "low", 0.72,
            f"{silence_ratio * 100:.1f}% of analysis frames are below -45 dBFS.",
            "Review silence removal manually when conversational timing matters.",
        ))
    if dc_offset > thresholds.dc_offset:
        issues.append(_issue(
            "dc_offset", "DC offset", "medium", 0.9,
            f"Mean waveform offset is {dc_offset:.4f}.",
            "Apply a high-pass/DC-removal stage before dynamics processing.",
        ))

    hum_frequency = 50 if spectrum["hum_50_ratio"] >= spectrum["hum_60_ratio"] else 60
    hum_ratio = max(spectrum["hum_50_ratio"], spectrum["hum_60_ratio"])
    if hum_ratio >= thresholds.hum_ratio:
        issues.append(_issue(
            "mains_hum", f"Possible {hum_frequency} Hz hum", "medium", min(0.94, 0.55 + hum_ratio),
            f"Mains harmonics represent approximately {hum_ratio * 100:.1f}% of low-band energy.",
            f"Apply targeted {hum_frequency} Hz buzz removal and verify with A/B listening.",
        ))

    nyquist = sr / 2
    if sr >= 32000 and spectrum["spectral_rolloff_95_hz"] < min(7000, nyquist * 0.45):
        issues.append(_issue(
            "limited_bandwidth", "Limited high-frequency bandwidth", "low", 0.66,
            f"95% spectral roll-off is {spectrum['spectral_rolloff_95_hz']:.0f} Hz.",
            "Prefer gentle EQ; synthetic frequency restoration should remain optional.",
        ))

    penalty = {"high": 18, "medium": 10, "low": 5}
    score = max(0, 100 - sum(penalty[item["severity"]] for item in issues))
    grade = "excellent" if score >= 90 else "good" if score >= 75 else "needs_attention" if score >= 55 else "poor"
    return {
        "schema_version": 1,
        "engine": "audio-intelligence-v1",
        "local_only": True,
        "quality_score": score,
        "quality_grade": grade,
        "metrics": metrics,
        "issues": issues,
        "limitations": [
            "SNR, hum and bandwidth values are signal-derived estimates, not calibrated laboratory measurements.",
            "Always confirm destructive speech edits with A/B listening.",
        ],
    }


def build_processing_profiles(
    diagnosis: dict[str, Any],
    content_type: str,
    capabilities: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Build three explainable option sets from the same measured evidence."""
    issue_ids = {item["id"] for item in diagnosis["issues"]}
    metrics = diagnosis["metrics"]
    is_music = content_type == "music"
    neural_denoise = bool(capabilities.get("neural_denoise"))
    demucs_available = bool(capabilities.get("demucs_music_separation"))

    profiles: dict[str, dict[str, Any]] = {}
    definitions = {
        "conservative": (0.35, "Minimal intervention; preserves timing and natural room tone."),
        "balanced": (0.55, "Recommended cleanup with controlled enhancement."),
        "maximum": (0.78, "Strong restoration; review speech edits and artifacts with A/B playback."),
    }

    for name, (strength, description) in definitions.items():
        options: dict[str, Any] = {
            "remove_noise": "background_noise" in issue_ids and not is_music,
            "noise_reduction_strength": strength if neural_denoise else min(strength, 0.65),
            "remove_long_silences": False,
            "silence_threshold_db": -45 if name == "conservative" else -42 if name == "balanced" else -40,
            "min_silence_duration_ms": 1500 if name == "conservative" else 1100 if name == "balanced" else 800,
            "mute_segments": False,
            "remove_mouth_sounds": False,
            "mouth_sound_sensitivity": 0.4 if name != "maximum" else 0.6,
            "eliminate_hesitations": False,
            "remove_stuttering": False,
            "remove_filler_words": False,
            "custom_filler_words": None,
            "remove_breaths": False,
            "breath_reduction_strength": 0.35 if name == "conservative" else 0.5 if name == "balanced" else 0.65,
            "studio_sound": name != "conservative" and not is_music,
            "auto_eq": name != "conservative" or "limited_bandwidth" in issue_ids,
            "normalize": metrics["rms_dbfs"] < -18 or metrics["peak_dbfs"] > -1,
            "target_loudness_lufs": -16.0,
            "keep_music": is_music and demucs_available,
            "wind_noise_remover": False,
            "buzzing_noise_remover": "mains_hum" in issue_ids,
            "buzz_frequency_hz": 50.0 if metrics["hum_50_ratio"] >= metrics["hum_60_ratio"] else 60.0,
            "static_noise_remover": name == "maximum" and "background_noise" in issue_ids and not is_music,
            "reverb_echo_remover": False,
            "frequency_restoration": name == "maximum" and "limited_bandwidth" in issue_ids,
            "target_sample_rate": 48000,
            "smart_mode": True,
            "content_type": content_type,
            "output_format": "wav",
        }
        active_steps = [
            key for key, value in options.items()
            if value is True and key not in {"smart_mode"}
        ]
        reasons = [item["recommendation"] for item in diagnosis["issues"]]
        if not active_steps:
            reasons.append("No corrective processing is required by the selected profile.")
        profiles[name] = {
            "name": name,
            "description": description,
            "options": options,
            "active_steps": active_steps,
            "reasons": reasons,
            "review_required": name == "maximum" and options["frequency_restoration"],
        }
    return profiles
