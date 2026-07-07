"""
AudioEnhancerMAX by Fd — Main FastAPI Application
Full-featured audio processing dashboard backend.
Optimized for Apple Silicon M3 MAX.
"""
import os
import asyncio
import logging
import re
import uuid
from pathlib import Path
from typing import Optional, List

import numpy as np
from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, Query, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import (
    UPLOAD_DIR, OUTPUT_DIR, FRONTEND_DIR,
    ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB
)
from app.models.schemas import (
    ProcessingOptions, ProcessingRequest,
    TranscriptionRequest, TranscriptFormat,
    TTSRequest, TTSRewriteRequest, FileInfo, ContentType
)
from app.utils.audio_io import (
    generate_file_id, get_upload_path, get_output_path,
    validate_extension, load_audio, save_audio, get_audio_info,
    generate_waveform_data
)
from app.utils.progress import progress_tracker

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

APP_VERSION = "3.5.1"
SAFE_FILE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
STREAMABLE_AUDIO_VERSIONS = {"original", "processed"}
DOWNLOAD_AUDIO_VERSIONS = {"original", "processed", "watermarked", "tts"}
DOWNLOAD_AUDIO_FORMATS = {"wav", "mp3", "flac"}


def _cors_origins_from_env() -> list[str]:
    """Resolve browser origins allowed to call the local API."""
    raw = os.getenv(
        "AEMAX_CORS_ORIGINS",
        "http://127.0.0.1:8000,http://localhost:8000",
    )
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def _is_safe_file_id(file_id: str) -> bool:
    return bool(SAFE_FILE_ID_RE.fullmatch(file_id or ""))


def _require_file_id(file_id: str) -> str:
    if not _is_safe_file_id(file_id):
        raise HTTPException(400, "Invalid file id")
    return file_id


def _require_choice(value: str, allowed: set[str], label: str) -> str:
    if value not in allowed:
        raise HTTPException(400, f"Invalid {label}. Allowed: {', '.join(sorted(allowed))}")
    return value

# ══════════════════════════════════════════════════════════
# FastAPI App
# ══════════════════════════════════════════════════════════

CORS_ORIGINS = _cors_origins_from_env()

app = FastAPI(
    title="AudioEnhancerMAX by Fd",
    description="Professional podcast audio processing suite — Apple Silicon Metal GPU + Edge Cluster computing",
    version=APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials="*" not in CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")


# ── Schemas for new endpoints ──

class PresetSaveRequest(BaseModel):
    name: str
    description: str = ""
    options: ProcessingOptions

class BatchRequest(BaseModel):
    file_ids: List[str]
    options: ProcessingOptions
    preset_id: Optional[str] = None

class DiarizationRequest(BaseModel):
    file_id: str
    num_speakers: Optional[int] = None
    min_speakers: int = 1
    max_speakers: int = 10


# ══════════════════════════════════════════════════════════
# Lifecycle — Start/Stop services
# ══════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup_services():
    """Start background services on app startup."""
    # Configure Apple Silicon acceleration (MPS/Metal/Accelerate)
    from app.services.apple_acceleration import configure_apple_acceleration
    configure_apple_acceleration()

    from app.services.system_monitor import system_monitor
    from app.services.cluster_manager import cluster_manager
    from app.services.timing_engine import timing_engine
    system_monitor.start()
    cluster_manager.start()
    logger.info("🚀 System monitor + Cluster manager started")
    logger.info(f"⏱️ Timing engine ready (history: {len(timing_engine._history.get('filter_timings', {}))} filters tracked)")

    # Run DSP benchmark in background (doesn't block startup)
    import threading
    def _run_benchmark():
        from app.services.benchmark import run_dsp_benchmark
        run_dsp_benchmark()
    threading.Thread(target=_run_benchmark, daemon=True).start()


@app.on_event("shutdown")
async def shutdown_services():
    """Stop background services on app shutdown."""
    from app.services.system_monitor import system_monitor
    from app.services.cluster_manager import cluster_manager
    system_monitor.stop()
    cluster_manager.stop()


# ══════════════════════════════════════════════════════════
# Routes — System Monitor
# ══════════════════════════════════════════════════════════

@app.get("/api/system/stats")
async def get_system_stats():
    """Real-time CPU/GPU/ANE/RAM metrics."""
    from app.services.system_monitor import system_monitor
    return system_monitor.get_stats()


@app.get("/api/system/history")
async def get_system_history():
    """Last 60 seconds of metrics history for sparkline charts."""
    from app.services.system_monitor import system_monitor
    return system_monitor.get_history()


# ══════════════════════════════════════════════════════════
# Routes — Cluster Management
# ══════════════════════════════════════════════════════════

@app.get("/api/cluster/status")
async def get_cluster_status():
    """Get connected workers and cluster status."""
    from app.services.cluster_manager import cluster_manager
    return await cluster_manager.get_status()


class WorkerAddRequest(BaseModel):
    ip: str
    port: int = 8877


@app.post("/api/cluster/add")
async def add_cluster_worker(req: WorkerAddRequest):
    """Manually add a worker by IP address."""
    from app.services.cluster_manager import cluster_manager
    return await cluster_manager.add_worker(req.ip, req.port)


@app.post("/api/cluster/remove")
async def remove_cluster_worker(req: WorkerAddRequest):
    """Remove a worker from the cluster."""
    from app.services.cluster_manager import cluster_manager
    return await cluster_manager.remove_worker(req.ip, req.port)


@app.post("/api/cluster/health-check")
async def cluster_health_check():
    """Ping all workers and update their status."""
    from app.services.cluster_manager import cluster_manager
    await cluster_manager.health_check_all()
    return await cluster_manager.get_status()


# ══════════════════════════════════════════════════════════
# Routes — Frontend
# ══════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/landing", response_class=HTMLResponse)
async def serve_landing():
    """Bilingual landing page presenting AudioEnhancerMAX."""
    return FileResponse(str(FRONTEND_DIR / "landing.html"))


# ══════════════════════════════════════════════════════════
# Per-Filter Benchmarks (seconds per 60s of audio on M3 MAX)
# ══════════════════════════════════════════════════════════

FILTER_BENCHMARKS = {
    "remove_noise":          {"seconds_per_60s": 8.0,  "group": "deepfilter"},
    "wind_noise_remover":    {"seconds_per_60s": 2.5,  "group": "dsp"},
    "buzzing_noise_remover": {"seconds_per_60s": 0.5,  "group": "dsp"},
    "static_noise_remover":  {"seconds_per_60s": 2.5,  "group": "dsp"},
    "reverb_echo_remover":   {"seconds_per_60s": 4.0,  "group": "dsp"},
    "remove_filler_words":   {"seconds_per_60s": 35.0, "group": "whisper"},
    "eliminate_hesitations":  {"seconds_per_60s": 35.0, "group": "whisper"},
    "remove_stuttering":     {"seconds_per_60s": 35.0, "group": "whisper"},
    "remove_mouth_sounds":   {"seconds_per_60s": 2.0,  "group": "dsp"},
    "remove_breaths":        {"seconds_per_60s": 3.0,  "group": "dsp"},
    "remove_long_silences":  {"seconds_per_60s": 1.0,  "group": "dsp"},
    "auto_eq":               {"seconds_per_60s": 0.3,  "group": "dsp"},
    "studio_sound":          {"seconds_per_60s": 0.5,  "group": "dsp"},
    "normalize":             {"seconds_per_60s": 0.3,  "group": "dsp"},
    "keep_music":            {"seconds_per_60s": 25.0, "group": "demucs"},
    "frequency_restoration": {"seconds_per_60s": 5.0,  "group": "dsp"},
}

# One-time model load costs per group (seconds)
GROUP_LOAD_COSTS = {
    "deepfilter": 5,
    "whisper": 12,
    "demucs": 8,
    "dsp": 0,
}


# ══════════════════════════════════════════════════════════
# Routes — Estimation (Adaptive Timing Engine)
# ══════════════════════════════════════════════════════════

@app.post("/api/estimate")
async def estimate_processing_time(request: ProcessingRequest):
    """Adaptive estimate using real historical data + benchmark fallback."""
    from app.services.timing_engine import timing_engine
    opts = request.options
    file_id = _require_file_id(request.file_id)

    # Try to get actual duration
    duration = 60.0
    source = _find_source(file_id)
    if source:
        try:
            info = get_audio_info(source)
            duration = info.get("duration", 60.0)
        except Exception:
            pass

    # Collect active filter keys
    opts_dict = opts.model_dump()
    active_steps = [k for k in FILTER_BENCHMARKS if opts_dict.get(k)]

    estimate = timing_engine.get_adaptive_estimate(active_steps, duration)

    return {
        "estimated_seconds": estimate["total_seconds"],
        "audio_duration": estimate["audio_duration"],
        "active_filters": len(active_steps),
        "confidence": estimate["confidence"],
        "source": estimate["source"],
        "breakdown_text": estimate["breakdown_text"],
        "per_step": estimate["per_step"],
    }


class OperationEstimateRequest(BaseModel):
    operation: str
    audio_duration: float = 60.0


@app.post("/api/estimate/operation")
async def estimate_operation_time(request: OperationEstimateRequest):
    """Adaptive estimate for non-filter operations (transcribe, diarize, tts)."""
    from app.services.timing_engine import timing_engine
    return timing_engine.estimate_operation(request.operation, request.audio_duration)


@app.get("/api/estimate/history")
async def get_estimate_history():
    """Return stored timing history summary."""
    from app.services.timing_engine import timing_engine
    return timing_engine.get_history_summary()


# ══════════════════════════════════════════════════════════
# Routes — Upload
# ══════════════════════════════════════════════════════════

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    if not validate_extension(file.filename):
        raise HTTPException(400, f"Unsupported format. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    file_id = generate_file_id()
    ext = Path(file.filename).suffix.lower()
    upload_path = get_upload_path(file_id, ext)

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(400, f"File too large. Max: {MAX_FILE_SIZE_MB}MB")

    with open(upload_path, "wb") as f:
        f.write(content)

    try:
        info = get_audio_info(upload_path)
        audio, sr = load_audio(upload_path)
        wav_path = get_upload_path(file_id, ".wav")
        if ext != ".wav":
            save_audio(audio, sr, wav_path)

        waveform = generate_waveform_data(audio, num_points=500)

        return {
            "file_id": file_id,
            "filename": file.filename,
            "size_bytes": len(content),
            "duration_seconds": info["duration"],
            "sample_rate": info["sample_rate"],
            "channels": info["channels"],
            "format": ext.lstrip("."),
            "bitrate": info.get("bitrate"),
            "waveform_data": waveform,
            "audio_url": f"/api/audio/{file_id}",
        }
    except Exception as e:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(500, f"Failed to process upload: {str(e)}")


@app.get("/api/audio/{file_id}")
async def get_audio(file_id: str, version: str = "original"):
    file_id = _require_file_id(file_id)
    version = _require_choice(version, STREAMABLE_AUDIO_VERSIONS, "version")

    if version == "processed":
        for ext in [".wav", ".mp3", ".flac"]:
            path = get_output_path(file_id, "_processed", ext)
            if path.exists():
                return FileResponse(str(path), media_type=f"audio/{ext.lstrip('.')}")

    for ext in [".wav", ".mp3", ".mp4", ".flac", ".ogg", ".m4a"]:
        path = get_upload_path(file_id, ext)
        if path.exists():
            return FileResponse(str(path), media_type=f"audio/{ext.lstrip('.')}")

    raise HTTPException(404, "Audio file not found")


# ══════════════════════════════════════════════════════════
# Routes — Processing
# ══════════════════════════════════════════════════════════

@app.post("/api/process")
async def process_audio(request: ProcessingRequest):
    import time as _time
    from app.services.timing_engine import timing_engine

    file_id = _require_file_id(request.file_id)
    options = request.options

    source_path = _find_source(file_id)
    if not source_path:
        raise HTTPException(404, "Source file not found")

    try:
        audio_duration_sec = 60.0
        try:
            info = get_audio_info(source_path)
            audio_duration_sec = info.get("duration", 60.0)
        except Exception:
            pass

        # ── Checkpoint/Resume: check for partial work ──
        checkpoint_dir = OUTPUT_DIR / f"{file_id}_checkpoints"
        checkpoint_meta_path = checkpoint_dir / "meta.json"
        completed_steps_set = set()
        resume_step = None

        if checkpoint_dir.exists() and checkpoint_meta_path.exists():
            import json as _json
            try:
                with open(checkpoint_meta_path) as f:
                    ckpt = _json.load(f)
                completed_steps_set = set(ckpt.get("completed_steps", []))
                resume_step = ckpt.get("last_step")
                # Load audio from last checkpoint
                last_audio_path = checkpoint_dir / f"{resume_step}.wav"
                if last_audio_path.exists() and completed_steps_set:
                    audio, sr = load_audio(last_audio_path)
                    logger.info(f"♻️ Resuming job {file_id}: {len(completed_steps_set)} steps already done, loading from checkpoint '{resume_step}'")
                    await progress_tracker.send_progress(
                        file_id, "resume", 0.05,
                        f"♻️ Ripresa dal checkpoint: {len(completed_steps_set)} step già completati"
                    )
                else:
                    audio, sr = load_audio(source_path)
            except Exception as e:
                logger.warning(f"Checkpoint load failed, starting fresh: {e}")
                audio, sr = load_audio(source_path)
        else:
            audio, sr = load_audio(source_path)

        await progress_tracker.send_progress(file_id, "loading", 0.05, "Audio loaded")

        total_steps = _count_steps(options)
        if total_steps == 0:
            raise HTTPException(400, "No processing options selected")

        # ── Build ordered list of active steps ──
        opts_dict = options.model_dump()
        STEP_ORDER = [
            "remove_noise", "wind_noise_remover", "buzzing_noise_remover",
            "static_noise_remover", "reverb_echo_remover", "remove_mouth_sounds",
            "remove_filler_words", "eliminate_hesitations", "remove_stuttering",
            "remove_breaths", "remove_long_silences", "keep_music",
            "auto_eq", "studio_sound", "frequency_restoration", "normalize",
        ]
        active_steps = [s for s in STEP_ORDER if opts_dict.get(s)]

        # ── Timing Engine: start job + get adaptive estimate ──
        job_id = file_id
        estimates = timing_engine.start_job(job_id, audio_duration_sec, active_steps)
        await progress_tracker.send_estimate(file_id, estimates)
        logger.info(
            f"⏱️ Estimate for {file_id}: ~{estimates['total_seconds']}s "
            f"({estimates['confidence']} confidence, {estimates['source']})"
        )

        # ── Dynamic Parameter Tuning ──
        try:
            from app.services.smart_mode import get_dynamic_parameters
            dynamic_params = await asyncio.to_thread(get_dynamic_parameters, audio, sr, opts_dict)
            if dynamic_params:
                logger.info(f"v2.0 Dynamic tuning active: {len(dynamic_params)} filters adjusted")
                if "remove_noise" in dynamic_params and hasattr(options, 'noise_reduction_strength'):
                    options.noise_reduction_strength = dynamic_params["remove_noise"]["strength"]
                if "remove_breaths" in dynamic_params and hasattr(options, 'breath_reduction_strength'):
                    options.breath_reduction_strength = dynamic_params["remove_breaths"]["strength"]
                if "remove_mouth_sounds" in dynamic_params and hasattr(options, 'mouth_sound_sensitivity'):
                    options.mouth_sound_sensitivity = dynamic_params["remove_mouth_sounds"]["strength"]
                await progress_tracker.send_progress(
                    file_id, "tuning", 0.08,
                    f"🧠 Dynamic tuning: {len(dynamic_params)} filters optimized for this audio"
                )
        except Exception as e:
            logger.warning(f"Dynamic tuning skipped: {e}")

        # ── Distributed Edge Processing ──
        distributed_filters = set()
        try:
            from app.services.cluster_manager import cluster_manager
            if cluster_manager.can_distribute(opts_dict):
                n_workers = len(cluster_manager.online_workers)
                await progress_tracker.send_progress(
                    file_id, "cluster", 0.08,
                    f"🌐 Distributing DSP to {n_workers} edge worker(s)..."
                )
                from app.services.cluster_manager import OFFLOADABLE_FILTERS
                offload_opts = {k: True for k in OFFLOADABLE_FILTERS if opts_dict.get(k)}
                if offload_opts:
                    audio = await cluster_manager.process_distributed(
                        audio, sr, offload_opts,
                        progress_callback=lambda name, pct, msg: progress_tracker.send_progress(file_id, name, pct, msg)
                    )
                    distributed_filters = set(offload_opts.keys())
                    logger.info(f"🌐 Distributed processing done for: {distributed_filters}")
                    await progress_tracker.send_progress(
                        file_id, "cluster_done", 0.35,
                        f"🌐 Edge processing complete — {len(distributed_filters)} filters distributed"
                    )
        except Exception as e:
            logger.warning(f"Distributed processing skipped: {e}")

        # ── Helper: run a step with timing + checkpoint ──
        current_step_idx = [0]

        def _save_checkpoint(step_name, audio_data, sample_rate, completed_list):
            """Save intermediate audio and metadata to checkpoint dir."""
            import json as _json
            checkpoint_dir.mkdir(parents=True, exist_ok=True)
            save_audio(audio_data, sample_rate, checkpoint_dir / f"{step_name}.wav")
            with open(checkpoint_meta_path, "w") as f:
                _json.dump({
                    "file_id": file_id,
                    "completed_steps": completed_list,
                    "last_step": step_name,
                    "audio_duration": audio_duration_sec,
                    "sample_rate": sample_rate,
                }, f)

        async def run_step(step_name, msg, process_fn):
            """Execute a step with timing, progress, and checkpoint."""
            nonlocal audio, sr
            # Skip if already done (checkpoint resume) or distributed
            if step_name in completed_steps_set:
                current_step_idx[0] += 1
                logger.info(f"⏩ Skipping '{step_name}' (checkpoint)")
                return
            if step_name in distributed_filters:
                return

            step_est = estimates.get("per_step", {}).get(step_name, {}).get("estimated_seconds", 5.0)
            timing_engine.start_step(job_id, step_name)

            await progress_tracker.send_progress(
                file_id, step_name, current_step_idx[0] / total_steps,
                f"⏳ {msg}...",
                step_estimate_seconds=step_est,
                steps_completed=current_step_idx[0],
                steps_total=total_steps,
                eta_confidence=estimates.get("confidence"),
            )

            # Execute the actual processing — in thread to keep server responsive
            result = await asyncio.to_thread(process_fn, audio, sr)
            if isinstance(result, tuple):
                audio, sr = result
            else:
                audio = result

            elapsed = timing_engine.end_step(job_id, step_name)
            current_step_idx[0] += 1

            # Mark model group as loaded for future estimates
            from app.services.timing_engine import STATIC_BENCHMARKS
            bench = STATIC_BENCHMARKS.get(step_name, {})
            if bench.get("model_load", 0) > 0:
                timing_engine.mark_group_loaded(bench["group"])

            # Checkpoint: save intermediate audio
            completed_list = [s for s in STEP_ORDER if s in completed_steps_set or s == step_name]
            completed_steps_set.add(step_name)
            _save_checkpoint(step_name, audio, sr, list(completed_steps_set))

            # Get live ETA from timing engine
            live = timing_engine.get_live_eta(job_id)
            remaining = live["remaining_seconds"] if live else None

            await progress_tracker.send_progress(
                file_id, step_name, current_step_idx[0] / total_steps,
                f"✓ {msg} ({elapsed:.1f}s)",
                estimated_remaining_seconds=remaining,
                steps_completed=current_step_idx[0],
                steps_total=total_steps,
                eta_confidence=estimates.get("confidence"),
            )

        # ── Processing Chain (order matters!) ──

        if options.remove_noise:
            from app.services.noise_removal import remove_noise as _remove_noise
            await run_step("remove_noise", "Noise removal complete",
                           lambda a, s: _remove_noise(a, s, options.noise_reduction_strength))

        if options.wind_noise_remover:
            from app.services.specific_noise import remove_wind_noise
            await run_step("wind_noise_remover", "Wind noise removed",
                           lambda a, s: remove_wind_noise(a, s))

        if options.buzzing_noise_remover:
            from app.services.specific_noise import remove_buzzing_noise
            await run_step("buzzing_noise_remover", "Buzzing removed",
                           lambda a, s: remove_buzzing_noise(a, s, options.buzz_frequency_hz))

        if options.static_noise_remover:
            from app.services.specific_noise import remove_static_noise
            await run_step("static_noise_remover", "Static noise removed",
                           lambda a, s: remove_static_noise(a, s))

        if options.reverb_echo_remover:
            from app.services.specific_noise import remove_reverb_echo
            await run_step("reverb_echo_remover", "Reverb/echo removed",
                           lambda a, s: remove_reverb_echo(a, s))

        if options.remove_mouth_sounds:
            from app.services.speech_cleanup import remove_mouth_sounds
            await run_step("remove_mouth_sounds", "Mouth sounds removed",
                           lambda a, s: remove_mouth_sounds(a, s, options.mouth_sound_sensitivity))

        if options.remove_filler_words:
            from app.services.speech_cleanup import remove_filler_words
            await run_step("remove_filler_words", "Filler words removed",
                           lambda a, s: remove_filler_words(a, s, options.custom_filler_words))

        if options.eliminate_hesitations:
            from app.services.speech_cleanup import eliminate_hesitations
            await run_step("eliminate_hesitations", "Hesitations eliminated",
                           lambda a, s: eliminate_hesitations(a, s))

        if options.remove_stuttering:
            from app.services.speech_cleanup import remove_stuttering
            await run_step("remove_stuttering", "Stuttering removed",
                           lambda a, s: remove_stuttering(a, s))

        if options.remove_breaths:
            from app.services.speech_cleanup import remove_breaths
            await run_step("remove_breaths", "Breaths removed",
                           lambda a, s: remove_breaths(a, s, options.breath_reduction_strength))

        if options.remove_long_silences:
            from app.services.silence_removal import remove_long_silences as _rm_silence, mute_segments, detect_silences
            if options.mute_segments:
                await run_step("remove_long_silences", "Silences muted",
                               lambda a, s: mute_segments(a, s, detect_silences(a, s, options.silence_threshold_db, options.min_silence_duration_ms)))
            else:
                await run_step("remove_long_silences", "Silences removed",
                               lambda a, s: _rm_silence(a, s, options.silence_threshold_db, options.min_silence_duration_ms))

        if options.keep_music:
            from app.services.enhancement import keep_music
            await run_step("keep_music", "Music preserved",
                           lambda a, s: keep_music(a, s))

        if options.auto_eq:
            from app.services.enhancement import apply_auto_eq
            await run_step("auto_eq", "AutoEQ applied",
                           lambda a, s: apply_auto_eq(a, s))

        if options.studio_sound:
            from app.services.enhancement import apply_studio_sound
            await run_step("studio_sound", "Studio sound applied",
                           lambda a, s: apply_studio_sound(a, s))

        if options.frequency_restoration:
            from app.services.super_resolution import restore_frequencies
            await run_step("frequency_restoration", "Frequency restoration complete",
                           lambda a, s: restore_frequencies(a, s, options.target_sample_rate))

        if options.normalize:
            from app.services.enhancement import normalize_volume
            await run_step("normalize", "Volume normalized",
                           lambda a, s: normalize_volume(a, s, options.target_loudness_lufs))

        # ── Finalize: save output ──
        timing_engine.end_job(job_id)

        fmt = options.output_format.value
        output_path = get_output_path(file_id, "_processed", f".{fmt}")
        save_audio(audio, sr, output_path, format=fmt)

        waveform = generate_waveform_data(audio, num_points=500)
        result_url = f"/outputs/{file_id}_processed.{fmt}"

        # Clean up checkpoints on success
        import shutil
        if checkpoint_dir.exists():
            shutil.rmtree(checkpoint_dir, ignore_errors=True)
            logger.info(f"🧹 Checkpoints cleaned for {file_id}")

        await progress_tracker.send_complete(file_id, result_url)

        return {
            "file_id": file_id,
            "status": "completed",
            "output_url": result_url,
            "duration_seconds": len(audio) / sr,
            "sample_rate": sr,
            "waveform_data": waveform,
            "format": fmt,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)
        try:
            timing_engine.end_job(file_id)
        except Exception:
            pass
        await progress_tracker.send_error(file_id, str(e))
        raise HTTPException(500, f"Processing failed: {str(e)}")


# ══════════════════════════════════════════════════════════
# Routes — Smart Mode (local Ollama/Gemma)
# ══════════════════════════════════════════════════════════

@app.post("/api/smart-mode/{file_id}")
async def smart_mode_analyze(file_id: str):
    file_id = _require_file_id(file_id)
    source_path = _find_source(file_id)
    if not source_path:
        raise HTTPException(404, "File not found")

    try:
        audio, sr = load_audio(source_path)
        from app.services.smart_mode import analyze_and_suggest
        return analyze_and_suggest(audio, sr)
    except Exception as e:
        raise HTTPException(500, f"Smart mode failed: {str(e)}")


@app.post("/api/smart-mode/{file_id}/suggestions")
async def get_editing_suggestions(file_id: str):
    """Get AI-assisted editing suggestions from the configured local Ollama/Gemma model."""
    file_id = _require_file_id(file_id)
    source_path = _find_source(file_id)
    if not source_path:
        raise HTTPException(404, "File not found")

    try:
        audio, sr = load_audio(source_path)
        from app.services.smart_mode import get_editing_suggestions
        from app.services.transcription import transcribe

        # Quick transcribe for context
        result = transcribe(audio[:sr*60], sr)  # First 60 seconds
        suggestions = get_editing_suggestions(audio, sr, result.get("text", ""))
        return {"suggestions": suggestions}
    except Exception as e:
        raise HTTPException(500, f"Suggestions failed: {str(e)}")


# ══════════════════════════════════════════════════════════
# Routes — Transcription (STT)
# ══════════════════════════════════════════════════════════

@app.post("/api/transcribe")
async def transcribe_audio(request: TranscriptionRequest):
    """Non-blocking transcription — runs in thread to keep server responsive."""
    file_id = _require_file_id(request.file_id)
    source_path = _find_source(file_id)
    if not source_path:
        raise HTTPException(404, "File not found")

    try:
        result = await asyncio.to_thread(
            _transcribe_sync, source_path, request.language, request.output_format
        )
        return result
    except Exception as e:
        raise HTTPException(500, f"Transcription failed: {str(e)}")


def _transcribe_sync(source_path, language, output_format):
    """Synchronous transcription worker — runs in a separate thread."""
    import time as _time
    from app.services.timing_engine import timing_engine

    audio, sr = load_audio(source_path)
    audio_duration = len(audio) / sr
    from app.services.transcription import transcribe, format_as_srt, format_as_vtt, format_as_json

    t0 = _time.monotonic()
    result = transcribe(audio, sr, language=language)
    elapsed = _time.monotonic() - t0

    # Record timing for future estimates
    timing_engine.record_operation("transcribe", audio_duration, elapsed)
    timing_engine.mark_group_loaded("whisper")
    logger.info(f"⏱️ Transcription took {elapsed:.1f}s for {audio_duration:.1f}s audio")

    formatters = {
        TranscriptFormat.SRT: lambda: format_as_srt(result["segments"]),
        TranscriptFormat.VTT: lambda: format_as_vtt(result["segments"]),
        TranscriptFormat.JSON: lambda: format_as_json(result["segments"], result["text"], result["language"]),
        TranscriptFormat.TXT: lambda: result["text"],
    }
    formatted = formatters.get(output_format, lambda: result["text"])()

    return {
        "text": result["text"],
        "language": result["language"],
        "duration": result["duration"],
        "segments": result["segments"],
        "formatted": formatted,
        "format": output_format.value,
        "processing_time": round(elapsed, 2),
    }


# ══════════════════════════════════════════════════════════
# Routes — Streaming Transcription (SSE)
# ══════════════════════════════════════════════════════════

@app.post("/api/transcribe/stream")
async def transcribe_audio_stream(request: TranscriptionRequest):
    """
    Streaming transcription via Server-Sent Events.
    Sends segments in real-time as Whisper processes them.
    Saves incrementally to disk for crash resilience.
    """
    file_id = _require_file_id(request.file_id)
    source_path = _find_source(file_id)
    if not source_path:
        raise HTTPException(404, "File not found")

    from starlette.responses import StreamingResponse

    async def event_stream():
        import time as _time
        import json
        from app.services.timing_engine import timing_engine
        from app.services.transcription import transcribe_streaming

        audio, sr = load_audio(source_path)
        audio_duration = len(audio) / sr

        # Incremental output file
        output_path = OUTPUT_DIR / f"{file_id}_transcript.json"

        t0 = _time.monotonic()

        # Run the generator in a thread to not block the event loop
        import queue
        result_queue = queue.Queue()

        def _run_streaming():
            try:
                for event in transcribe_streaming(
                    audio, sr,
                    language=request.language,
                    output_path=output_path,
                ):
                    result_queue.put(event)
            except Exception as e:
                result_queue.put({"type": "error", "message": str(e)})
            finally:
                result_queue.put(None)  # Sentinel

        import threading
        worker = threading.Thread(target=_run_streaming, daemon=True)
        worker.start()

        while True:
            # Poll queue without blocking — allow other async tasks
            try:
                event = await asyncio.to_thread(result_queue.get, timeout=0.5)
            except Exception:
                continue

            if event is None:
                break

            # Send SSE event
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            if event.get("type") == "done":
                elapsed = _time.monotonic() - t0
                timing_engine.record_operation("transcribe", audio_duration, elapsed)
                timing_engine.mark_group_loaded("whisper")
                logger.info(f"⏱️ Streaming transcription took {elapsed:.1f}s for {audio_duration:.1f}s audio")
                break
            elif event.get("type") == "error":
                break

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/transcribe/resume/{file_id}")
async def check_transcript_resume(file_id: str):
    """Check if a partial transcript exists from a previous interrupted session."""
    import json
    file_id = _require_file_id(file_id)
    output_path = OUTPUT_DIR / f"{file_id}_transcript.json"
    if output_path.exists():
        try:
            with open(output_path) as f:
                data = json.load(f)
            return {
                "has_partial": True,
                "complete": data.get("complete", False),
                "segments_count": data.get("segments_count", 0),
                "text": data.get("text", ""),
                "language": data.get("language", ""),
            }
        except Exception:
            pass
    return {"has_partial": False}


# ══════════════════════════════════════════════════════════
# Routes — Text-to-Speech (TTS)
# ══════════════════════════════════════════════════════════

@app.get("/api/tts/voices")
async def get_voices():
    from app.services.tts import get_available_voices
    return {"voices": get_available_voices()}


@app.post("/api/tts/synthesize")
async def synthesize(request: TTSRequest):
    try:
        from app.services.tts import synthesize_speech

        clone_path = None
        if request.clone_voice_file_id:
            clone_file_id = _require_file_id(request.clone_voice_file_id)
            clone_path = str(_find_source(clone_file_id) or "")

        # Run TTS in thread — model loading + inference + Gemma rewrite can take 30+ seconds
        audio, sr, metadata = await asyncio.to_thread(
            synthesize_speech,
            text=request.text, language=request.language,
            voice_id=request.voice_id, speed=request.speed,
            pitch=request.pitch, warmth=request.warmth,
            style=request.style, clone_voice_path=clone_path if clone_path else None,
            expressive=request.expressive, engine=request.engine,
        )

        # Check if we got actual audio
        if len(audio) < 100:
            raise HTTPException(503, "TTS model not available — check server logs")

        file_id = generate_file_id()
        output_path = get_output_path(file_id, "_tts", ".wav")
        save_audio(audio, sr, output_path)

        return {
            "file_id": file_id,
            "audio_url": f"/outputs/{file_id}_tts.wav",
            "duration": round(len(audio) / sr, 2),
            "engine": metadata.get("engine", "edge"),
            "expressive": metadata.get("expressive", False),
            "rewritten_text": metadata.get("rewritten_text"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"TTS failed: {str(e)}")


@app.post("/api/tts/rewrite")
async def rewrite_text(request: TTSRewriteRequest):
    """Preview Gemma's expressive rewrite of the input text."""
    try:
        from app.services.tts import rewrite_expressive
        rewritten = await asyncio.to_thread(
            rewrite_expressive, request.text, request.language, request.style
        )
        return {
            "original": request.text,
            "rewritten": rewritten,
            "changed": rewritten != request.text,
        }
    except Exception as e:
        raise HTTPException(500, f"Rewrite failed: {str(e)}")


# ══════════════════════════════════════════════════════════
# Routes — Speaker Diarization
# ══════════════════════════════════════════════════════════

@app.post("/api/diarize")
async def diarize_audio(request: DiarizationRequest):
    """Non-blocking diarization — runs in thread to keep server responsive."""
    file_id = _require_file_id(request.file_id)
    source_path = _find_source(file_id)
    if not source_path:
        raise HTTPException(404, "File not found")

    try:
        result = await asyncio.to_thread(
            _diarize_sync, source_path, file_id,
            request.num_speakers, request.min_speakers, request.max_speakers
        )
        return result
    except Exception as e:
        raise HTTPException(500, f"Diarization failed: {str(e)}")


def _diarize_sync(source_path, file_id, num_speakers, min_speakers, max_speakers):
    """Synchronous diarization worker — runs in a separate thread."""
    audio, sr = load_audio(source_path)
    from app.services.diarization import diarize, get_speaker_stats

    segments = diarize(
        audio, sr,
        num_speakers=num_speakers,
        min_speakers=min_speakers,
        max_speakers=max_speakers,
    )
    stats = get_speaker_stats(segments)

    return {
        "file_id": file_id,
        "segments": segments,
        "speaker_stats": stats,
        "total_speakers": len(stats),
    }


# ══════════════════════════════════════════════════════════
# Routes — Audio Watermarking
# ══════════════════════════════════════════════════════════

@app.post("/api/watermark/{file_id}")
async def add_watermark(file_id: str, identifier: str = ""):
    file_id = _require_file_id(file_id)
    source_path = _find_source(file_id, check_outputs=True)
    if not source_path:
        raise HTTPException(404, "File not found")

    try:
        audio, sr = load_audio(source_path)
        from app.services.watermarking import embed_watermark

        watermarked = embed_watermark(audio, sr, identifier or file_id)
        output_path = get_output_path(file_id, "_watermarked", ".wav")
        save_audio(watermarked, sr, output_path)

        return {
            "file_id": file_id,
            "watermarked_url": f"/outputs/{file_id}_watermarked.wav",
            "status": "watermark_embedded",
        }
    except Exception as e:
        raise HTTPException(500, f"Watermarking failed: {str(e)}")


@app.post("/api/watermark/detect/{file_id}")
async def detect_watermark(file_id: str):
    file_id = _require_file_id(file_id)
    source_path = _find_source(file_id, check_outputs=True)
    if not source_path:
        raise HTTPException(404, "File not found")

    try:
        audio, sr = load_audio(source_path)
        from app.services.watermarking import detect_watermark as _detect
        result = _detect(audio, sr)
        return {"file_id": file_id, "watermark": result}
    except Exception as e:
        raise HTTPException(500, f"Detection failed: {str(e)}")


# ══════════════════════════════════════════════════════════
# Routes — Presets
# ══════════════════════════════════════════════════════════

@app.get("/api/presets")
async def list_all_presets():
    from app.services.batch_presets import list_presets, get_builtin_presets
    return {
        "builtin": get_builtin_presets(),
        "custom": list_presets(),
    }


@app.post("/api/presets")
async def save_preset(request: PresetSaveRequest):
    from app.services.batch_presets import save_preset
    try:
        return save_preset(request.name, request.options, request.description)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/presets/{preset_id}")
async def get_preset(preset_id: str):
    from app.services.batch_presets import load_preset, get_builtin_presets
    # Check builtin first
    for bp in get_builtin_presets():
        if bp["id"] == preset_id:
            return bp
    result = load_preset(preset_id)
    if not result:
        raise HTTPException(404, "Preset not found")
    return result


@app.delete("/api/presets/{preset_id}")
async def remove_preset(preset_id: str):
    from app.services.batch_presets import delete_preset
    if delete_preset(preset_id):
        return {"status": "deleted"}
    raise HTTPException(404, "Preset not found")


# ══════════════════════════════════════════════════════════
# Routes — Batch Processing
# ══════════════════════════════════════════════════════════

@app.post("/api/batch")
async def start_batch(request: BatchRequest):
    from app.services.batch_presets import create_batch_job, load_preset, get_builtin_presets

    job_id = str(uuid.uuid4())[:12]
    file_ids = [_require_file_id(file_id) for file_id in request.file_ids]
    if not file_ids:
        raise HTTPException(400, "Batch requires at least one file")

    # If preset_id is provided, load its options
    options = request.options
    if request.preset_id:
        for bp in get_builtin_presets():
            if bp["id"] == request.preset_id:
                options = ProcessingOptions(**bp["options"])
                break
        else:
            preset = load_preset(request.preset_id)
            if preset:
                options = ProcessingOptions(**preset["options"])

    job = create_batch_job(job_id, file_ids, options)

    # Process files sequentially in background
    asyncio.create_task(_process_batch(job_id, file_ids, options))

    return {"job_id": job_id, "status": "started", "total_files": len(file_ids)}


@app.get("/api/batch/{job_id}")
async def get_batch_status(job_id: str):
    from app.services.batch_presets import get_batch_job
    job_id = _require_file_id(job_id)
    job = get_batch_job(job_id)
    if not job:
        raise HTTPException(404, "Batch job not found")
    return job.to_dict()


async def _process_batch(job_id: str, file_ids: List[str], options: ProcessingOptions):
    """Process batch files sequentially."""
    from app.services.batch_presets import update_batch_progress

    for file_id in file_ids:
        try:
            req = ProcessingRequest(file_id=file_id, options=options)
            result = await process_audio(req)
            update_batch_progress(job_id, file_id, {"status": "completed", "output_url": result["output_url"]})
        except Exception as e:
            update_batch_progress(job_id, file_id, {"status": "error", "error": str(e)})


# ══════════════════════════════════════════════════════════
# Routes — Download
# ══════════════════════════════════════════════════════════

@app.get("/api/download/{file_id}")
async def download_file(file_id: str, format: str = "wav", version: str = "processed"):
    file_id = _require_file_id(file_id)
    format = _require_choice(format, DOWNLOAD_AUDIO_FORMATS, "format")
    version = _require_choice(version, DOWNLOAD_AUDIO_VERSIONS, "version")
    suffix = f"_{version}" if version != "original" else ""

    path = get_output_path(file_id, suffix, f".{format}")
    if path.exists():
        return FileResponse(str(path), media_type=f"audio/{format}", filename=f"AudioEnhancerMAX_{file_id}.{format}")

    for ext in [".wav", ".mp3", ".flac"]:
        source = get_output_path(file_id, suffix, ext)
        if source.exists():
            if format != ext.lstrip("."):
                audio, sr = load_audio(source)
                converted = get_output_path(file_id, suffix, f".{format}")
                save_audio(audio, sr, converted, format=format)
                return FileResponse(str(converted), filename=f"AudioEnhancerMAX_{file_id}.{format}")
            return FileResponse(str(source), filename=f"AudioEnhancerMAX_{file_id}{ext}")

    for ext in [".wav", ".mp3", ".mp4", ".flac"]:
        source = get_upload_path(file_id, ext)
        if source.exists():
            return FileResponse(str(source), filename=f"AudioEnhancerMAX_{file_id}{ext}")

    raise HTTPException(404, "File not found")


# ══════════════════════════════════════════════════════════
# WebSocket — Progress
# ══════════════════════════════════════════════════════════

@app.websocket("/ws/progress/{file_id}")
async def websocket_progress(websocket: WebSocket, file_id: str):
    if not _is_safe_file_id(file_id):
        await websocket.close(code=1008)
        return

    await progress_tracker.connect(file_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        await progress_tracker.disconnect(file_id)


# ══════════════════════════════════════════════════════════
# Health & System
# ══════════════════════════════════════════════════════════

@app.get("/api/health")
async def health():
    import torch
    gpu_info = "Apple Silicon M3 MAX (MPS)" if torch.backends.mps.is_available() else "CPU"

    # Check local Ollama / Gemma-family model
    gemma_status = "unknown"
    gemma_model = None
    try:
        from app.services.smart_mode import _check_ollama_available
        import app.services.smart_mode as smart_mod
        if _check_ollama_available():
            gemma_status = "available"
            gemma_model = smart_mod.OLLAMA_MODEL
        else:
            gemma_status = "not_running"
    except Exception:
        gemma_status = "error"

    # System utilization (real-time from macmon)
    system_data = {}
    try:
        from app.services.system_monitor import system_monitor
        metrics = system_monitor.get_stats()
        if metrics:
            system_data = {
                "chip": metrics.get("chip", "Apple M3 Max"),
                "cpu_percent": metrics.get("cpu_percent", 0),
                "cpu_per_core": metrics.get("cpu_per_core", []),
                "cpu_freq_ghz": metrics.get("cpu_freq_ghz", 0),
                "gpu_percent": metrics.get("gpu_percent", 0),
                "gpu_freq_ghz": metrics.get("gpu_freq_ghz", 0),
                "ram_percent": metrics.get("ram_percent", 0),
                "ram_used_gb": metrics.get("ram_used_gb", 0),
                "ram_total_gb": metrics.get("ram_total_gb", 0),
                "swap_used_gb": metrics.get("swap_used_gb", 0),
                "ane_percent": metrics.get("ane_percent", 0),
                "power_watts": metrics.get("power_watts", 0),
                "thermal_pressure": metrics.get("thermal_pressure", "nominal"),
                "cpu_temp_c": metrics.get("cpu_temp_c", 0),
                "gpu_temp_c": metrics.get("gpu_temp_c", 0),
                "timestamp": metrics.get("timestamp", 0),
            }
            # Include benchmark score if available
            try:
                from app.services.benchmark import get_benchmark_result
                bench = get_benchmark_result()
                if bench:
                    system_data["benchmark_score"] = bench.get("score", 0)
            except Exception:
                pass
    except Exception:
        pass

    return {
        "status": "healthy",
        "app": "AudioEnhancerMAX by Fd",
        "version": APP_VERSION,
        "compute": gpu_info,
        "mps_available": torch.backends.mps.is_available(),
        "gemma4_status": gemma_status,
        "gemma_model": gemma_model,
        "ollama_status": gemma_status,
        "ollama_model": gemma_model,
        "system": system_data,
    }


@app.get("/api/acceleration")
async def acceleration_info():
    """Show active hardware acceleration configuration."""
    from app.services.apple_acceleration import get_acceleration_info
    return get_acceleration_info()


@app.get("/api/benchmark")
async def benchmark_results():
    """Get benchmark results for all devices in the cluster."""
    from app.services.benchmark import get_benchmark_result
    from app.services.cluster_manager import cluster_manager

    mac_bench = get_benchmark_result()
    
    # Gather worker benchmarks from cluster status
    workers = []
    try:
        status = await cluster_manager.get_status()
        for w in status.get("workers", []):
            workers.append({
                "name": w.get("device_model", w.get("name", "Unknown")),
                "ip": w.get("ip", ""),
                "status": w.get("status", "offline"),
                "benchmark_score": w.get("benchmark_score", 0),
                "tasks_completed": w.get("tasks_completed", 0),
                "avg_speed": w.get("avg_speed", None),
            })
    except Exception:
        pass

    return {
        "master": {
            "name": "Mac — Master",
            "chip": mac_bench.get("tests", {}).get("fft", {}).get("description", "") if mac_bench else "",
            "score": mac_bench.get("score", 0) if mac_bench else 0,
            "tests": mac_bench.get("tests", {}) if mac_bench else {},
        },
        "workers": workers,
    }


# ══════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════

def _find_source(file_id: str, check_outputs: bool = False) -> Optional[Path]:
    """Find audio file by ID across uploads and outputs."""
    if not _is_safe_file_id(file_id):
        return None

    for ext in [".wav", ".mp3", ".mp4", ".flac", ".ogg", ".m4a"]:
        path = get_upload_path(file_id, ext)
        if path.exists():
            return path

    if check_outputs:
        for suffix in ["_processed", "_watermarked", "_tts"]:
            for ext in [".wav", ".mp3", ".flac"]:
                path = get_output_path(file_id, suffix, ext)
                if path.exists():
                    return path
    return None


def _count_steps(options: ProcessingOptions) -> int:
    """Count active processing steps."""
    return sum([
        options.remove_noise, options.remove_long_silences,
        options.remove_mouth_sounds, options.eliminate_hesitations,
        options.remove_stuttering, options.remove_filler_words,
        options.remove_breaths, options.studio_sound,
        options.auto_eq, options.normalize,
        options.keep_music, options.wind_noise_remover,
        options.buzzing_noise_remover, options.static_noise_remover,
        options.reverb_echo_remover, options.frequency_restoration,
    ])
