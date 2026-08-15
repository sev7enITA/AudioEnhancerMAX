"""Local delivery checks based on measured audio facts.

The checks are workflow guidance, not third-party or regulatory certification.
Integrated loudness follows the BS.1770 algorithm exposed by pyloudnorm; true
peak is reported as a conservative 4x-oversampled estimate.
"""
from __future__ import annotations

import math
import json
from pathlib import Path
from typing import Any

import numpy as np
import pyloudnorm as pyln
from scipy.signal import resample_poly

from app.config import OUTPUT_DIR
from app.utils.audio_io import load_audio


DELIVERY_TARGETS: dict[str, dict[str, Any]] = {
    "podcast": {"label": "Podcast", "loudness_lufs": -16.0, "tolerance_lu": 1.0, "peak_ceiling_dbtp": -1.0},
    "video": {"label": "Online video", "loudness_lufs": -14.0, "tolerance_lu": 1.0, "peak_ceiling_dbtp": -1.0},
    "audiobook": {"label": "Audiobook", "loudness_lufs": -18.0, "tolerance_lu": 2.0, "peak_ceiling_dbtp": -3.0},
    "broadcast-r128": {"label": "Broadcast · EBU R128", "loudness_lufs": -23.0, "tolerance_lu": 0.5, "peak_ceiling_dbtp": -1.0},
    "source-master": {"label": "Source master", "loudness_lufs": None, "tolerance_lu": None, "peak_ceiling_dbtp": -1.0},
    "archive": {"label": "Lossless archive", "loudness_lufs": None, "tolerance_lu": None, "peak_ceiling_dbtp": -1.0},
}


def list_delivery_targets() -> list[dict[str, Any]]:
    return [{"id": key, **value} for key, value in DELIVERY_TARGETS.items()]


def compliance_path(file_id: str) -> Path:
    return OUTPUT_DIR / f"{file_id}_delivery_compliance.json"


def _dbfs(amplitude: float) -> float:
    return -math.inf if amplitude <= 0 else 20.0 * math.log10(amplitude)


def measure_audio(audio: np.ndarray, sample_rate: int) -> dict[str, Any]:
    samples = np.asarray(audio, dtype=np.float64)
    if samples.ndim not in (1, 2) or samples.size == 0:
        raise ValueError("Audio must contain mono or multi-channel samples")
    if sample_rate < 8000:
        raise ValueError("Sample rate must be at least 8000 Hz")

    channels = 1 if samples.ndim == 1 else int(samples.shape[1])
    meter = pyln.Meter(sample_rate)
    try:
        integrated = float(meter.integrated_loudness(samples))
    except (ValueError, OverflowError):
        integrated = -math.inf

    oversampled = resample_poly(samples, 4, 1, axis=0)
    peak = float(np.max(np.abs(oversampled)))
    sample_peak = float(np.max(np.abs(samples)))
    frames = int(samples.shape[0])
    return {
        "integrated_loudness_lufs": round(integrated, 2) if math.isfinite(integrated) else None,
        "estimated_true_peak_dbtp": round(_dbfs(peak), 2) if peak else None,
        "sample_peak_dbfs": round(_dbfs(sample_peak), 2) if sample_peak else None,
        "clipped_sample_count": int(np.count_nonzero(np.abs(samples) >= 1.0)),
        "sample_rate_hz": int(sample_rate),
        "channels": channels,
        "duration_seconds": round(frames / sample_rate, 3),
        "true_peak_method": "4x polyphase oversampling estimate",
    }


def evaluate_measurements(measurements: dict[str, Any], target_id: str) -> dict[str, Any]:
    if target_id not in DELIVERY_TARGETS:
        raise ValueError(f"Unknown delivery target: {target_id}")
    target = DELIVERY_TARGETS[target_id]
    rules: list[dict[str, Any]] = []

    measured_loudness = measurements.get("integrated_loudness_lufs")
    if target["loudness_lufs"] is not None:
        delta = None if measured_loudness is None else measured_loudness - target["loudness_lufs"]
        passed = delta is not None and abs(delta) <= target["tolerance_lu"]
        rules.append({
            "id": "integrated-loudness",
            "label": "Integrated loudness",
            "status": "pass" if passed else "fail",
            "measured": measured_loudness,
            "unit": "LUFS",
            "target": target["loudness_lufs"],
            "tolerance": target["tolerance_lu"],
            "detail": "Silence cannot satisfy a loudness target." if measured_loudness is None else f"Delta {delta:+.2f} LU.",
        })

    measured_peak = measurements.get("estimated_true_peak_dbtp")
    peak_passed = measured_peak is None or measured_peak <= target["peak_ceiling_dbtp"]
    rules.append({
        "id": "estimated-true-peak",
        "label": "Estimated true peak",
        "status": "pass" if peak_passed else "fail",
        "measured": measured_peak,
        "unit": "dBTP",
        "ceiling": target["peak_ceiling_dbtp"],
        "detail": measurements["true_peak_method"],
    })

    clipped = int(measurements.get("clipped_sample_count", 0))
    rules.append({
        "id": "sample-clipping",
        "label": "Digital clipping",
        "status": "pass" if clipped == 0 else "fail",
        "measured": clipped,
        "unit": "samples",
        "ceiling": 0,
        "detail": "Counts samples at or beyond full scale.",
    })
    rules.append({
        "id": "sample-rate",
        "label": "Sample rate",
        "status": "pass" if measurements["sample_rate_hz"] >= 44100 else "warn",
        "measured": measurements["sample_rate_hz"],
        "unit": "Hz",
        "floor": 44100,
        "detail": "44.1 kHz or higher is recommended for delivery masters.",
    })

    counts = {status: sum(rule["status"] == status for rule in rules) for status in ("pass", "warn", "fail")}
    overall = "fail" if counts["fail"] else ("warn" if counts["warn"] else "pass")
    return {
        "schema_version": 1,
        "target_id": target_id,
        "target_label": target["label"],
        "status": overall,
        "summary": counts,
        "measurements": measurements,
        "rules": rules,
        "reference": "ITU-R BS.1770-5; EBU R128 v5 for the broadcast-r128 preset",
        "disclaimer": "Local workflow guidance only; this result is not a regulatory or third-party certification.",
    }


def analyze_delivery(path: Path, target_id: str) -> dict[str, Any]:
    audio, sample_rate = load_audio(Path(path), mono=False)
    if audio.ndim == 2 and audio.shape[0] <= 8 and audio.shape[1] > audio.shape[0]:
        audio = audio.T
    result = evaluate_measurements(measure_audio(audio, sample_rate), target_id)
    result["artifact"] = Path(path).name
    return result


def save_delivery_result(file_id: str, result: dict[str, Any]) -> Path:
    destination = compliance_path(file_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(destination)
    return destination


def load_delivery_result(file_id: str) -> dict[str, Any] | None:
    try:
        return json.loads(compliance_path(file_id).read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
