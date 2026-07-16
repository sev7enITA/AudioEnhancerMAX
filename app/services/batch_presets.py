"""
AudioEnhancerMAX by Fd - Batch Processing & Presets Service
Process multiple files with same settings, save/load custom presets.
"""
import json
import logging
import re
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.config import PRESETS_DIR
from app.models.schemas import ProcessingOptions

logger = logging.getLogger(__name__)

# Presets storage
SAFE_PRESET_ID_RE = re.compile(r"^[a-z0-9_]{1,64}$")


# ══════════════════════════════════════════════════════════
# Processing Presets
# ══════════════════════════════════════════════════════════

def _slugify_preset_name(name: str) -> str:
    """Convert a user-facing preset name into a safe local filename stem."""
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    if not SAFE_PRESET_ID_RE.fullmatch(slug):
        raise ValueError("Preset name must contain at least one letter or number")
    return slug


def _preset_path(preset_id: str) -> Optional[Path]:
    if not SAFE_PRESET_ID_RE.fullmatch(preset_id or ""):
        return None
    return PRESETS_DIR / f"{preset_id}.json"

def save_preset(
    name: str,
    options: ProcessingOptions,
    description: str = "",
) -> dict:
    """Save a processing preset to disk."""
    preset_id = _slugify_preset_name(name)
    preset_path = PRESETS_DIR / f"{preset_id}.json"

    preset_data = {
        "id": preset_id,
        "name": name,
        "description": description,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "options": options.model_dump(),
    }

    with open(preset_path, "w") as f:
        json.dump(preset_data, f, indent=2, default=str)

    logger.info(f"Preset saved: {name} -> {preset_path}")
    return preset_data


def load_preset(preset_id: str) -> Optional[dict]:
    """Load a processing preset from disk."""
    preset_path = _preset_path(preset_id)

    if not preset_path or not preset_path.exists():
        return None

    with open(preset_path) as f:
        return json.load(f)


def list_presets() -> List[dict]:
    """List all saved presets."""
    presets = []
    for path in sorted(PRESETS_DIR.glob("*.json")):
        try:
            with open(path) as f:
                data = json.load(f)
                presets.append({
                    "id": data.get("id", path.stem),
                    "name": data.get("name", path.stem),
                    "description": data.get("description", ""),
                    "created_at": data.get("created_at", ""),
                })
        except Exception as e:
            logger.error(f"Failed to load preset {path}: {e}")

    return presets


def delete_preset(preset_id: str) -> bool:
    """Delete a saved preset."""
    preset_path = _preset_path(preset_id)
    if preset_path and preset_path.exists():
        preset_path.unlink()
        return True
    return False


def get_builtin_presets() -> List[dict]:
    """Return built-in preset templates."""
    return [
        {
            "id": "podcast_pro",
            "name": "Podcast Pro",
            "description": "Full cleanup for professional podcast production",
            "options": ProcessingOptions(
                remove_noise=True,
                noise_reduction_strength=0.7,
                remove_filler_words=True,
                remove_breaths=True,
                breath_reduction_strength=0.6,
                remove_long_silences=True,
                min_silence_duration_ms=1500,
                auto_eq=True,
                studio_sound=True,
                normalize=True,
                target_loudness_lufs=-16.0,
            ).model_dump(),
        },
        {
            "id": "quick_clean",
            "name": "Quick Clean",
            "description": "Fast noise removal and normalization",
            "options": ProcessingOptions(
                remove_noise=True,
                noise_reduction_strength=0.5,
                normalize=True,
            ).model_dump(),
        },
        {
            "id": "interview_mode",
            "name": "Interview Mode",
            "description": "Optimized for multi-speaker interviews",
            "options": ProcessingOptions(
                remove_noise=True,
                noise_reduction_strength=0.5,
                remove_breaths=True,
                breath_reduction_strength=0.5,
                auto_eq=True,
                normalize=True,
                target_loudness_lufs=-16.0,
            ).model_dump(),
        },
        {
            "id": "outdoor_rescue",
            "name": "Outdoor Rescue",
            "description": "Heavy-duty cleanup for outdoor recordings",
            "options": ProcessingOptions(
                remove_noise=True,
                noise_reduction_strength=0.9,
                wind_noise_remover=True,
                static_noise_remover=True,
                studio_sound=True,
                normalize=True,
            ).model_dump(),
        },
        {
            "id": "voice_memo_polish",
            "name": "Voice Memo Polish",
            "description": "Quick enhancement for voice memos",
            "options": ProcessingOptions(
                remove_noise=True,
                noise_reduction_strength=0.6,
                remove_long_silences=True,
                min_silence_duration_ms=2000,
                normalize=True,
            ).model_dump(),
        },
        {
            "id": "studio_master",
            "name": "Studio Master",
            "description": "Maximum quality processing chain",
            "options": ProcessingOptions(
                remove_noise=True,
                noise_reduction_strength=0.8,
                remove_mouth_sounds=True,
                remove_filler_words=True,
                remove_breaths=True,
                eliminate_hesitations=True,
                remove_long_silences=True,
                reverb_echo_remover=True,
                auto_eq=True,
                studio_sound=True,
                normalize=True,
                target_loudness_lufs=-16.0,
                frequency_restoration=True,
            ).model_dump(),
        },
    ]


# ══════════════════════════════════════════════════════════
# Batch Processing
# ══════════════════════════════════════════════════════════

class BatchJob:
    """Represents a batch processing job."""

    def __init__(self, job_id: str, file_ids: List[str], options: ProcessingOptions):
        self.job_id = job_id
        self.file_ids = file_ids
        self.options = options
        self.status = "pending"
        self.results: Dict[str, Any] = {}
        self.progress = 0.0
        self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "file_ids": self.file_ids,
            "total_files": len(self.file_ids),
            "processed_files": len(self.results),
            "status": self.status,
            "progress": self.progress,
            "results": self.results,
            "created_at": self.created_at,
        }


# In-memory batch job tracker
_batch_jobs: Dict[str, BatchJob] = {}


def create_batch_job(
    job_id: str,
    file_ids: List[str],
    options: ProcessingOptions,
) -> BatchJob:
    """Create a new batch processing job."""
    job = BatchJob(job_id, file_ids, options)
    _batch_jobs[job_id] = job
    return job


def get_batch_job(job_id: str) -> Optional[BatchJob]:
    """Get a batch job by ID."""
    return _batch_jobs.get(job_id)


def update_batch_progress(
    job_id: str,
    file_id: str,
    result: dict,
) -> None:
    """Update batch job progress after processing a file."""
    job = _batch_jobs.get(job_id)
    if job:
        job.results[file_id] = result
        job.progress = len(job.results) / len(job.file_ids)
        if len(job.results) == len(job.file_ids):
            job.status = "completed"
        else:
            job.status = "processing"


def list_batch_jobs() -> List[dict]:
    """List all batch jobs."""
    return [job.to_dict() for job in _batch_jobs.values()]
