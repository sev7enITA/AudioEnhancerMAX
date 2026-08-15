"""Create durable, machine-readable evidence for each processing job."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from app.config import OUTPUT_DIR
from app.services.audio_intelligence import analyze_audio_quality
from app.services.capability_registry import engine_for_step


def report_path(file_id: str) -> Path:
    return OUTPUT_DIR / f"{file_id}_processing_report.json"


def quality_summary(audio: np.ndarray, sr: int) -> dict[str, Any]:
    diagnosis = analyze_audio_quality(audio, sr)
    return {
        "quality_score": diagnosis["quality_score"],
        "quality_grade": diagnosis["quality_grade"],
        "metrics": diagnosis["metrics"],
        "issues": diagnosis["issues"],
    }


def create_processing_report(
    *,
    file_id: str,
    app_version: str,
    input_summary: dict[str, Any],
    output_audio: np.ndarray,
    output_sample_rate: int,
    options: dict[str, Any],
    active_steps: list[str],
    distributed_steps: list[str] | None = None,
    speech_edl: dict[str, Any] | None = None,
    elapsed_seconds: float | None = None,
    app_build: str | None = None,
    source_path: Path | None = None,
    output_path: Path | None = None,
    compliance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build and persist a local report. Failures should be handled by the caller."""
    distributed = set(distributed_steps or [])
    engines = []
    warnings: list[str] = []
    for step in active_steps:
        if step in distributed:
            engine = {
                "id": "trusted-lan-edge-dsp",
                "label": "Trusted LAN edge DSP",
                "available": True,
                "mode": "trusted-lan",
                "version": None,
                "fallback": None,
                "detail": "Audio chunks were sent to a user-configured worker on the trusted local network.",
            }
        else:
            engine = engine_for_step(step)
        engines.append({"step": step, **engine})
        if "fallback" in engine["mode"] or "heuristic" in engine["mode"]:
            warnings.append(f"{step} used {engine['label']} ({engine['mode']}).")

    from app.services.runtime_settings import load_runtime_settings
    runtime_privacy = load_runtime_settings()
    report = {
        "schema_version": 2,
        "product": "AudioEnhancerMAX",
        "app_version": app_version,
        "app_build": app_build,
        "file_id": file_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "privacy": {
            "audio_transmitted": bool(distributed),
            "analysis_engine": "audio-intelligence-v1",
            "processing_location": "local-and-trusted-lan" if distributed else "local",
            "distributed_steps": sorted(distributed),
            "external_services_allowed": runtime_privacy["external_services_allowed"],
            "ollama_editorial_allowed": runtime_privacy["ollama_editorial_allowed"],
            "trusted_lan_processing_allowed": runtime_privacy["trusted_lan_processing_allowed"],
            "external_service_used_by_this_job": False,
        },
        "input": input_summary,
        "output": quality_summary(output_audio, output_sample_rate),
        "pipeline": engines,
        "options": options,
        "elapsed_seconds": round(elapsed_seconds, 3) if elapsed_seconds is not None else None,
        "warnings": warnings,
        "interpretation": (
            "Quality scores are comparative signal-derived indicators. "
            "They are not a guarantee of perceptual quality or intelligibility."
        ),
    }
    if source_path is not None and output_path is not None:
        from app.services.project_bundle import sha256_file
        report["provenance"] = {
            "hash_algorithm": "SHA-256",
            "source": {"name": Path(source_path).name, "sha256": sha256_file(Path(source_path))},
            "processed_output": {"name": Path(output_path).name, "sha256": sha256_file(Path(output_path))},
        }
    if compliance is not None:
        report["delivery_compliance"] = compliance
    if speech_edl is not None:
        approved = [
            item for item in speech_edl.get("candidates", [])
            if item.get("decision") == "apply"
        ]
        report["speech_edits"] = {
            "edl_schema_version": speech_edl.get("schema_version"),
            "edl_revision": speech_edl.get("revision"),
            "source_preserved": True,
            "manual_review_required": True,
            "candidate_count": len(speech_edl.get("candidates", [])),
            "approved_count": len(approved),
            "approved_by_type": {
                edit_type: sum(item.get("type") == edit_type for item in approved)
                for edit_type in sorted({item.get("type", "unknown") for item in approved})
            },
            "actions": {
                action: sum(item.get("action") == action for item in approved)
                for action in sorted({item.get("action", "unknown") for item in approved})
            },
        }
    destination = report_path(file_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(destination)
    return report


def load_processing_report(file_id: str) -> dict[str, Any] | None:
    try:
        return json.loads(report_path(file_id).read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
