"""
AudioEnhancerMAX by Fd - Main FastAPI Application
Full-featured audio processing dashboard backend.
Optimized for Apple Silicon M3 MAX.
"""
import os
import asyncio
import logging
import mimetypes
import re
import uuid
from pathlib import Path
from typing import Optional, List

import numpy as np
from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, Query, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import (
    APP_STORE_MODE, UPLOAD_DIR, OUTPUT_DIR, FRONTEND_DIR,
    ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB, ROADMAP_VOTES_FILE,
    bundled_whisper_model_available,
)
from app.models.schemas import (
    ProcessingOptions, ProcessingRequest,
    TranscriptionRequest, TranscriptFormat,
    TTSRequest, TTSRewriteRequest, FileInfo, ContentType, SmartProfile,
    VoiceProfileEnrollRequest, VoiceProfileUpdateRequest,
    SpeechEditorAnalyzeRequest, SpeechEditorUpdateRequest, SpeechEditorRenderRequest,
    SpeechEditorManualEditRequest, RevisionRequest, RuntimePrivacySettingsRequest,
    ProjectCapsuleRequest, BlindABReviewRequest,
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

APP_VERSION = "3.8.0"
APP_BUILD = os.getenv("AEMAX_BUILD_NUMBER", "3.8.0")
_PROCESSING_FILES: set[str] = set()
SAFE_FILE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
STREAMABLE_AUDIO_VERSIONS = {"original", "processed"}
DOWNLOAD_AUDIO_VERSIONS = {"original", "processed", "speech_edit", "watermarked", "tts"}
DOWNLOAD_AUDIO_FORMATS = {"wav", "mp3", "flac"}
AUDIO_MEDIA_TYPES = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".mp4": "audio/mp4",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".m4a": "audio/mp4",
}

# Python's default MIME initialization reads system files such as
# /etc/apache2/mime.types, which are intentionally inaccessible inside the
# Mac App Store sandbox. Clear the platform file list and initialize from
# Python's built-in table before StaticFiles or FileResponse can trigger that
# lookup. (On Python 3.11, ``init(files=[])`` still prepends ``knownfiles``.)
mimetypes.knownfiles.clear()
mimetypes.init()
for extension, media_type in {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    **AUDIO_MEDIA_TYPES,
}.items():
    mimetypes.add_type(media_type, extension)


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
    title="AudioEnhancerMAX by Fabrizio Degni",
    description="Professional podcast audio processing suite - Apple Silicon Metal GPU + Edge Cluster computing",
    version=APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials="*" not in CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def prevent_stale_frontend(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path in {"/", "/landing", "/roadmap", "/roadmap.html"} or path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Serve frontend
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
app.mount("/img", StaticFiles(directory=str(FRONTEND_DIR / "img")), name="public-images")
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
# Lifecycle - Start/Stop services
# ══════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup_services():
    """Start background services on app startup."""
    # Configure Apple Silicon acceleration (MPS/Metal/Accelerate)
    from app.services.apple_acceleration import configure_apple_acceleration
    configure_apple_acceleration()

    from app.services.system_monitor import system_monitor
    from app.services.cluster_manager import cluster_manager
    from app.services.runtime_settings import external_service_allowed
    from app.services.timing_engine import timing_engine
    system_monitor.start()
    if (
        external_service_allowed("trusted-lan")
        and os.getenv("AEMAX_EDGE_CLUSTER_AUTOSTART", "0") == "1"
    ):
        cluster_manager.start()
        logger.info(" System monitor + Cluster manager started")
    else:
        logger.info(" System monitor started; edge discovery awaits explicit user action")
    logger.info(f" Timing engine ready (history: {len(timing_engine._history.get('filter_timings', {}))} filters tracked)")

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
# Routes - System Monitor
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


@app.get("/api/system/preflight")
async def get_system_preflight():
    """Return first-launch readiness checks without changing the system."""
    from app.services.preflight import run_preflight

    return run_preflight(APP_VERSION)


@app.get("/api/system/capabilities")
async def get_system_capabilities():
    """Expose the reviewed feature set so the browser UI never advertises unavailable engines."""
    from app.services.cluster_manager import cluster_manager
    from app.services.capability_registry import get_capability_registry
    from app.services.runtime_settings import load_runtime_settings

    capabilities = get_capability_registry()
    capabilities.update({
        "edge_cluster_available": True,
        "edge_cluster_enabled": cluster_manager.enabled,
        "runtime_privacy": load_runtime_settings(),
    })
    return capabilities


@app.get("/api/settings/privacy")
async def get_runtime_privacy_settings():
    from app.services.runtime_settings import load_runtime_settings
    return load_runtime_settings()


@app.patch("/api/settings/privacy")
async def update_runtime_privacy_settings(request: RuntimePrivacySettingsRequest):
    from app.services.runtime_settings import save_runtime_settings
    settings = save_runtime_settings(request.model_dump())
    if not settings["trusted_lan_processing_allowed"]:
        from app.services.cluster_manager import cluster_manager
        cluster_manager.stop()
    return settings


@app.get("/api/output-profiles")
async def get_output_profiles():
    from app.services.output_profiles import list_output_profiles
    return {"profiles": list_output_profiles()}


@app.post("/api/system/preflight/configure")
async def configure_system_preflight():
    """Configure private runtime storage and acknowledge the current build."""
    from app.services.preflight import configure_runtime

    report = configure_runtime(APP_VERSION)
    if not report["can_continue"]:
        return JSONResponse(status_code=409, content=report)
    return report


# ══════════════════════════════════════════════════════════
# Routes - Cluster Management
# ══════════════════════════════════════════════════════════

@app.get("/api/cluster/status")
async def get_cluster_status():
    """Get connected workers and cluster status."""
    from app.services.cluster_manager import cluster_manager
    return await cluster_manager.get_status()


@app.post("/api/cluster/enable")
async def enable_cluster_discovery():
    """Start LAN discovery only after an explicit user action."""
    from app.services.cluster_manager import cluster_manager
    from app.services.runtime_settings import external_service_allowed

    if not external_service_allowed("trusted-lan"):
        raise HTTPException(403, "Trusted-LAN processing is disabled in Settings")

    cluster_manager.start()
    return await cluster_manager.get_status()


class WorkerAddRequest(BaseModel):
    ip: str
    port: int = 8877


@app.post("/api/cluster/add")
async def add_cluster_worker(req: WorkerAddRequest):
    """Manually add a worker by IP address."""
    from app.services.cluster_manager import cluster_manager
    from app.services.runtime_settings import external_service_allowed
    if not external_service_allowed("trusted-lan"):
        raise HTTPException(403, "Trusted-LAN processing is disabled in Settings")
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
# Routes - Frontend
# ══════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    return FileResponse(str(FRONTEND_DIR / "index.html"), media_type="text/html")


@app.get("/landing", response_class=HTMLResponse)
async def serve_landing():
    """Bilingual landing page presenting AudioEnhancerMAX."""
    return FileResponse(str(FRONTEND_DIR / "landing.html"), media_type="text/html")


@app.get("/roadmap", response_class=HTMLResponse)
async def serve_roadmap():
    """Public roadmap page for upcoming AudioEnhancerMAX releases."""
    return FileResponse(str(FRONTEND_DIR / "roadmap.html"), media_type="text/html")


@app.get("/roadmap.html", response_class=HTMLResponse)
async def serve_roadmap_html():
    """Static-compatible roadmap route."""
    return FileResponse(str(FRONTEND_DIR / "roadmap.html"), media_type="text/html")


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
# Routes - Estimation (Adaptive Timing Engine)
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
# Routes - Upload
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
async def get_audio(file_id: str, version: str = "original", revision: str | None = None):
    file_id = _require_file_id(file_id)
    version = _require_choice(version, STREAMABLE_AUDIO_VERSIONS, "version")
    if version == "processed":
        path, artifact = await _resolve_export(file_id, revision=revision)
        return FileResponse(path, media_type=AUDIO_MEDIA_TYPES[path.suffix],
                            headers={"Cache-Control": "no-store", "X-Audio-Revision": artifact["revision"]})
    path = _find_source(file_id)
    if path is None:
        raise HTTPException(404, "Original audio not found")
    return FileResponse(path, media_type=AUDIO_MEDIA_TYPES.get(path.suffix, "application/octet-stream"),
                        headers={"Cache-Control": "no-store"})


# ══════════════════════════════════════════════════════════
# Routes - Processing
# ══════════════════════════════════════════════════════════

@app.post("/api/process")
async def process_audio(request: ProcessingRequest):
    import time as _time
    from app.services.timing_engine import timing_engine

    file_id = _require_file_id(request.file_id)
    options = request.options.model_copy(deep=True)
    requested_options = options.model_dump(mode="json")
    processing_started = _time.monotonic()

    if options.output_profile:
        from app.services.output_profiles import resolve_output_profile
        try:
            resolved_profile = resolve_output_profile(
                options.output_profile, options.output_profile_overrides
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        for field, value in resolved_profile["resolved"].items():
            if field == "output_format":
                options.output_format = type(options.output_format)(value)
            else:
                setattr(options, field, value)

    if APP_STORE_MODE and options.keep_music:
        raise HTTPException(400, "Music separation is not included in the Mac App Store build")

    source_path = _find_source(file_id)
    if not source_path:
        raise HTTPException(404, "Source file not found")

    if file_id in _PROCESSING_FILES:
        raise HTTPException(409, "This file is already being processed")
    _PROCESSING_FILES.add(file_id)
    try:
        audio_duration_sec = 60.0
        try:
            info = get_audio_info(source_path)
            audio_duration_sec = info.get("duration", 60.0)
        except Exception:
            pass

        # Diagnose and tune the original, even when a later checkpoint is reusable.
        audio, sr = load_audio(source_path)
        checkpoint_dir = OUTPUT_DIR / f"{file_id}_checkpoints"
        completed_steps_set = set()
        from app.services.processing_report import quality_summary
        report_input_summary = await asyncio.to_thread(quality_summary, audio, sr)

        await progress_tracker.send_progress(file_id, "loading", 0.05, "Audio loaded")

        total_steps = _count_steps(options)
        if total_steps == 0 and not options.output_profile:
            raise HTTPException(400, "No processing options selected")
        total_steps = max(1, total_steps)

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
            f" Estimate for {file_id}: ~{estimates['total_seconds']}s "
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
                    f" Dynamic tuning: {len(dynamic_params)} filters optimized for this audio"
                )
        except Exception as e:
            logger.warning(f"Dynamic tuning skipped: {e}")

        # Compatibility includes original bytes, requested/effective parameters,
        # ordered steps, application build and the available DSP runtime versions.
        from app.services.processing_checkpoint import processing_identity, load_checkpoint, save_checkpoint
        from app.services.capability_registry import engine_for_step
        from app.services.runtime_settings import external_service_allowed
        engines = [engine_for_step(step) for step in active_steps]
        checkpoint_enabled = (
            not external_service_allowed("trusted-lan")
            and not any(step in {"remove_filler_words", "eliminate_hesitations", "remove_stuttering", "keep_music"} for step in active_steps)
            and all(engine["mode"] in {"deterministic-local", "dsp-fallback", "heuristic-local"} for engine in engines)
        )
        identity = await asyncio.to_thread(
            processing_identity, source_path, requested_options, options.model_dump(mode="json"),
            active_steps, APP_VERSION, APP_BUILD, engines,
        )
        checkpoint = await asyncio.to_thread(load_checkpoint, checkpoint_dir, identity, active_steps) if checkpoint_enabled else None
        if checkpoint is not None:
            audio, sr, completed_steps_set = checkpoint
            await progress_tracker.send_progress(file_id, "resume", 0.08,
                f"Resuming {len(completed_steps_set)} verified DSP steps")
        resumed_steps = [step for step in active_steps if step in completed_steps_set]
        opts_dict = options.model_dump()

        # ── Distributed Edge Processing ──
        distributed_filters = set()
        try:
            from app.services.cluster_manager import cluster_manager
            from app.services.runtime_settings import external_service_allowed
            if external_service_allowed("trusted-lan") and cluster_manager.can_distribute(opts_dict):
                n_workers = len(cluster_manager.online_workers)
                await progress_tracker.send_progress(
                    file_id, "cluster", 0.08,
                    f" Distributing DSP to {n_workers} edge worker(s)..."
                )
                supported_filters = cluster_manager.distributable_filters(opts_dict)
                offload_opts = {key: True for key in supported_filters}
                if offload_opts:
                    audio = await cluster_manager.process_distributed(
                        audio, sr, offload_opts,
                        progress_callback=lambda name, pct, msg: progress_tracker.send_progress(file_id, name, pct, msg)
                    )
                    distributed_filters = set(offload_opts.keys())
                    logger.info(f" Distributed processing done for: {distributed_filters}")
                    await progress_tracker.send_progress(
                        file_id, "cluster_done", 0.35,
                        f" Edge processing complete - {len(distributed_filters)} filters distributed"
                    )
        except Exception as e:
            logger.warning(f"Distributed processing skipped: {e}")

        # ── Helper: run a step with timing + checkpoint ──
        current_step_idx = [0]

        async def run_step(step_name, msg, process_fn):
            """Execute a step with timing, progress, and checkpoint."""
            nonlocal audio, sr
            # Skip if already done (checkpoint resume) or distributed
            if step_name in completed_steps_set:
                current_step_idx[0] += 1
                logger.info(f" Skipping '{step_name}' (checkpoint)")
                return
            if step_name in distributed_filters:
                return

            step_est = estimates.get("per_step", {}).get(step_name, {}).get("estimated_seconds", 5.0)
            timing_engine.start_step(job_id, step_name)

            await progress_tracker.send_progress(
                file_id, step_name, current_step_idx[0] / total_steps,
                f" {msg}...",
                step_estimate_seconds=step_est,
                steps_completed=current_step_idx[0],
                steps_total=total_steps,
                eta_confidence=estimates.get("confidence"),
            )

            # Execute the actual processing - in thread to keep server responsive
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
            completed_steps_set.add(step_name)
            if checkpoint_enabled:
                completed_list = [step for step in active_steps if step in completed_steps_set]
                await asyncio.to_thread(save_checkpoint, checkpoint_dir, identity, audio, sr, completed_list)

            # Get live ETA from timing engine
            live = timing_engine.get_live_eta(job_id)
            remaining = live["remaining_seconds"] if live else None

            await progress_tracker.send_progress(
                file_id, step_name, current_step_idx[0] / total_steps,
                f"Completed: {msg} ({elapsed:.1f}s)",
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
        from app.services.artifact_store import publish_audio, atomic_json
        artifact = await asyncio.to_thread(publish_audio, file_id, audio, sr, fmt)
        output_path = OUTPUT_DIR / artifact["exports"][fmt]["name"]

        waveform = generate_waveform_data(audio, num_points=500)
        result_url = f"/outputs/{output_path.name}"
        report_url = None
        report_summary = None
        compliance_result = None
        compliance_target = {
            "youtube": "video",
            "audiobook": "audiobook",
            "archive": "archive",
            "source-master": "source-master",
        }.get(options.output_profile or "", "podcast")
        try:
            from app.services.delivery_compliance import analyze_delivery, save_delivery_result
            compliance_result = await asyncio.to_thread(analyze_delivery, output_path, compliance_target)
            compliance_result["revision"] = artifact["revision"]
            await asyncio.to_thread(save_delivery_result, file_id, compliance_result)
        except Exception as compliance_error:
            logger.warning("Delivery compliance could not be measured: %s", compliance_error)
        try:
            from app.services.processing_report import create_processing_report

            processing_report = await asyncio.to_thread(
                create_processing_report,
                file_id=file_id,
                app_version=APP_VERSION,
                input_summary=report_input_summary,
                output_audio=audio,
                output_sample_rate=sr,
                options=options.model_dump(mode="json"),
                active_steps=active_steps,
                distributed_steps=sorted(distributed_filters),
                elapsed_seconds=_time.monotonic() - processing_started,
                app_build=APP_BUILD,
                source_path=source_path,
                output_path=output_path,
                compliance=compliance_result,
            )
            processing_report["artifact_revision"] = artifact["revision"]
            processing_report["checkpoint"] = {"identity": identity, "enabled": checkpoint_enabled, "resumed_steps": resumed_steps}
            atomic_json(output_path.with_suffix(".report.json"), processing_report)
            report_url = f"/api/reports/{file_id}?revision={artifact['revision']}"
            report_summary = {
                "input_quality_score": processing_report["input"]["quality_score"],
                "output_quality_score": processing_report["output"]["quality_score"],
                "engine_count": len(processing_report["pipeline"]),
                "warnings": len(processing_report["warnings"]),
                "compliance_status": compliance_result["status"] if compliance_result else None,
            }
        except Exception as report_error:
            logger.warning("Processing report could not be generated: %s", report_error)

        # Clean up checkpoints on success
        import shutil
        if checkpoint_dir.exists():
            shutil.rmtree(checkpoint_dir, ignore_errors=True)
            logger.info(f" Checkpoints cleaned for {file_id}")

        await progress_tracker.send_complete(file_id, result_url)

        return {
            "file_id": file_id,
            "status": "completed",
            "output_url": result_url,
            "revision": artifact["revision"],
            "artifact_sha256": artifact["exports"][fmt]["sha256"],
            "checkpoint": {"enabled": checkpoint_enabled, "resumed_steps": resumed_steps},
            "duration_seconds": len(audio) / sr,
            "sample_rate": sr,
            "waveform_data": waveform,
            "format": fmt,
            "report_url": report_url,
            "report_summary": report_summary,
            "compliance_url": f"/api/compliance/{file_id}" if compliance_result else None,
            "compliance_summary": compliance_result,
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
    finally:
        _PROCESSING_FILES.discard(file_id)


# ══════════════════════════════════════════════════════════
# Routes - Smart Mode (local Ollama/Gemma)
# ══════════════════════════════════════════════════════════

@app.post("/api/smart-mode/{file_id}")
async def smart_mode_analyze(
    file_id: str,
    profile: SmartProfile = Query(default=SmartProfile.BALANCED),
):
    file_id = _require_file_id(file_id)
    source_path = _find_source(file_id)
    if not source_path:
        raise HTTPException(404, "File not found")

    try:
        audio, sr = load_audio(source_path)
        from app.services.smart_mode import analyze_and_suggest
        return await asyncio.to_thread(analyze_and_suggest, audio, sr, profile.value)
    except Exception as e:
        raise HTTPException(500, f"Smart mode failed: {str(e)}")


@app.get("/api/reports/{file_id}")
async def get_processing_report(file_id: str, version: str = "processed", revision: str | None = None):
    """Return evidence for the requested current result, not another operation."""
    import json
    file_id = _require_file_id(file_id)
    version = _require_choice(version, {"processed", "speech_edit"}, "version")
    output, artifact = await _resolve_export(file_id, version=version, revision=revision)
    path = output.with_suffix(".report.json")
    if path.is_file():
        return json.loads(path.read_text())
    from app.services.processing_report import load_processing_report
    report = load_processing_report(file_id)
    if report and report.get("provenance", {}).get("processed_output", {}).get("sha256") == artifact["exports"][artifact["master_format"]]["sha256"]:
        return report
    raise HTTPException(404, "Report for this output revision is unavailable")


@app.get("/api/compliance-targets")
async def get_compliance_targets():
    """Expose the fixed, inspectable delivery check presets."""
    from app.services.delivery_compliance import list_delivery_targets
    return {"targets": list_delivery_targets()}


@app.get("/api/compliance/{file_id}")
async def get_delivery_compliance(file_id: str, target_id: str = Query(default="podcast"),
                                  format: str | None = None, version: str = "processed",
                                  revision: str | None = None):
    """Measure the exact encoded export identified by revision and format."""
    file_id = _require_file_id(file_id)
    version = _require_choice(version, {"processed", "speech_edit"}, "version")
    if format is not None:
        format = _require_choice(format, DOWNLOAD_AUDIO_FORMATS, "format")
    from app.services.delivery_compliance import analyze_delivery, save_delivery_result, DELIVERY_TARGETS
    if target_id not in DELIVERY_TARGETS:
        raise HTTPException(400, "Unknown delivery target")
    output_path, artifact = await _resolve_export(file_id, format, version, revision)
    result = await asyncio.to_thread(analyze_delivery, output_path, target_id)
    result["revision"] = artifact["revision"]
    result["version"] = version
    await asyncio.to_thread(save_delivery_result, file_id, result)
    return result


@app.post("/api/reviews/{file_id}/blind-ab")
async def save_blind_ab_review(file_id: str, request: BlindABReviewRequest):
    """Persist a user-revealed blind A/B decision as local review evidence."""
    file_id = _require_file_id(file_id)
    source = _find_source(file_id)
    if source is None:
        raise HTTPException(404, "Original and processed artifacts are required")
    output, artifact = await _resolve_export(file_id, version=request.output_version, revision=request.revision)
    from app.services.artifact_store import sha256_file, atomic_json
    import json
    from datetime import datetime, timezone
    destination = output.with_suffix(".review.json")
    record = {
        "schema_version": 1,
        "file_id": file_id,
        "output_version": request.output_version,
        "revision": artifact["revision"],
        "output_sha256": artifact["exports"][artifact["master_format"]]["sha256"],
        "source_sha256": sha256_file(source),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "blind_slot": request.blind_slot,
        "selected_version": request.selected_version,
        "target_id": request.target_id,
        "source_preserved": True,
        "reviewer_assertion": "User-selected listening preference; not an objective quality score.",
    }
    atomic_json(destination, record)
    return record


@app.post("/api/projects/{file_id}/export")
async def export_project(file_id: str, request: ProjectCapsuleRequest):
    """Return a portable ZIP with evidence and optional original audio."""
    file_id = _require_file_id(file_id)
    source_path = _find_source(file_id)
    if source_path is None:
        raise HTTPException(404, "Original and processed artifacts are required")
    output_path, artifact = await _resolve_export(
        file_id, request.format.value if request.format else None, request.output_version, request.revision
    )
    master_path = OUTPUT_DIR / artifact["exports"][artifact["master_format"]]["name"]

    from app.services.delivery_compliance import analyze_delivery
    from app.services.artifact_store import atomic_json
    from app.services.project_bundle import export_project_capsule
    from app.services.speech_editor import speech_edl_path
    try:
        compliance = await asyncio.to_thread(analyze_delivery, output_path, request.target_id)
        compliance["revision"] = artifact["revision"]
        compliance["version"] = request.output_version
        compliance_file = output_path.with_suffix(f".{request.target_id}.compliance.json")
        atomic_json(compliance_file, compliance)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    candidates = {
        "processing-report": master_path.with_suffix(".report.json"),
        "delivery-compliance": compliance_file,
        "speech-edl": speech_edl_path(file_id),
        "transcript": OUTPUT_DIR / f"{file_id}_transcript.json",
        "blind-ab-review": master_path.with_suffix(".review.json"),
    }
    optional = {role: path for role, path in candidates.items() if path.is_file()}
    execution_boundary = "local"
    if candidates["processing-report"].is_file():
        try:
            import json
            stored_report = json.loads(candidates["processing-report"].read_text(encoding="utf-8"))
            execution_boundary = stored_report.get("privacy", {}).get("processing_location", "local")
        except (OSError, ValueError):
            pass
    capsule, _ = await asyncio.to_thread(
        export_project_capsule,
        file_id=file_id,
        app_version=APP_VERSION,
        app_build=APP_BUILD,
        source_path=source_path,
        output_path=output_path,
        optional_artifacts=optional,
        include_source=request.include_source,
        execution_boundary=execution_boundary,
    )
    return FileResponse(capsule, media_type="application/zip", filename=capsule.name)


@app.post("/api/smart-mode/{file_id}/suggestions")
async def get_editing_suggestions(file_id: str):
    """Get AI-assisted editing suggestions from the configured local Ollama/Gemma model."""
    file_id = _require_file_id(file_id)
    source_path = _find_source(file_id)
    if not source_path:
        raise HTTPException(404, "File not found")
    from app.services.runtime_settings import external_service_allowed
    if not external_service_allowed("ollama"):
        raise HTTPException(403, "Local Ollama editorial assistance is disabled in Settings")

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
# Routes - Transcription (STT)
# ══════════════════════════════════════════════════════════

@app.post("/api/transcribe")
async def transcribe_audio(request: TranscriptionRequest):
    """Non-blocking transcription - runs in thread to keep server responsive."""
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
    """Synchronous transcription worker - runs in a separate thread."""
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
    logger.info(f" Transcription took {elapsed:.1f}s for {audio_duration:.1f}s audio")

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
# Routes - Streaming Transcription (SSE)
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
            # Poll queue without blocking - allow other async tasks
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
                logger.info(f" Streaming transcription took {elapsed:.1f}s for {audio_duration:.1f}s audio")
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
# Routes - Precision Speech Editor (non-destructive EDL)
# ══════════════════════════════════════════════════════════

@app.post("/api/speech-editor/analyze")
async def analyze_speech_edits(request: SpeechEditorAnalyzeRequest):
    """Create a reviewable edit decision list without modifying source audio."""
    file_id = _require_file_id(request.file_id)
    source_path = _find_source(file_id)
    if not source_path:
        raise HTTPException(404, "File not found")

    def analyze_sync():
        audio, sr = load_audio(source_path)
        from app.services.transcription import transcribe
        from app.services.speech_editor import build_speech_edl

        transcription = transcribe(audio, sr, language=request.language)
        return build_speech_edl(
            file_id=file_id,
            audio=audio,
            sr=sr,
            transcription=transcription,
            custom_fillers=request.custom_filler_words,
        )

    try:
        return await asyncio.to_thread(analyze_sync)
    except Exception as exc:
        logger.error("Speech editor analysis failed: %s", exc, exc_info=True)
        raise HTTPException(500, f"Speech editor analysis failed: {exc}") from exc


@app.get("/api/speech-editor/{file_id}")
async def get_speech_edits(file_id: str):
    file_id = _require_file_id(file_id)
    from app.services.speech_editor import load_speech_edl

    edl = load_speech_edl(file_id)
    if edl is None:
        raise HTTPException(404, "Speech edit list not found")
    return edl


@app.patch("/api/speech-editor/{file_id}")
async def update_speech_edits(file_id: str, request: SpeechEditorUpdateRequest):
    file_id = _require_file_id(file_id)
    from app.services.speech_editor import load_speech_edl, update_speech_edl

    edl = load_speech_edl(file_id)
    if edl is None:
        raise HTTPException(404, "Speech edit list not found")
    try:
        return await asyncio.to_thread(
            update_speech_edl,
            edl,
            [item.model_dump() for item in request.decisions],
            request.revision,
        )
    except KeyError as exc:
        raise HTTPException(400, str(exc)) from exc
    except ValueError as exc:
        status_code = 409 if "changed" in str(exc) else 400
        raise HTTPException(status_code, str(exc)) from exc


@app.post("/api/speech-editor/{file_id}/manual-edit")
async def add_manual_speech_edit_endpoint(file_id: str, request: SpeechEditorManualEditRequest):
    file_id = _require_file_id(file_id)
    from app.services.speech_editor import add_manual_speech_edit, load_speech_edl

    edl = load_speech_edl(file_id)
    if edl is None:
        raise HTTPException(404, "Speech edit list not found")
    try:
        return await asyncio.to_thread(
            add_manual_speech_edit, edl, request.model_dump(), request.revision
        )
    except ValueError as exc:
        status_code = 409 if "changed" in str(exc) else 400
        raise HTTPException(status_code, str(exc)) from exc


@app.post("/api/speech-editor/{file_id}/undo")
async def undo_speech_edit(file_id: str, request: RevisionRequest):
    return await _navigate_speech_edit_history(file_id, request.revision, "undo")


@app.post("/api/speech-editor/{file_id}/redo")
async def redo_speech_edit(file_id: str, request: RevisionRequest):
    return await _navigate_speech_edit_history(file_id, request.revision, "redo")


async def _navigate_speech_edit_history(file_id: str, revision: int, direction: str):
    file_id = _require_file_id(file_id)
    from app.services.speech_editor import load_speech_edl, navigate_speech_edl_history

    edl = load_speech_edl(file_id)
    if edl is None:
        raise HTTPException(404, "Speech edit list not found")
    try:
        return await asyncio.to_thread(
            navigate_speech_edl_history, edl, revision, direction
        )
    except ValueError as exc:
        status_code = 409 if "changed" in str(exc) else 400
        raise HTTPException(status_code, str(exc)) from exc


@app.get("/api/speech-editor/{file_id}/export")
async def export_speech_edits(file_id: str, format: str = Query(default="json")):
    import csv
    import io

    file_id = _require_file_id(file_id)
    format = _require_choice(format, {"json", "csv"}, "export format")
    from app.services.speech_editor import load_speech_edl

    edl = load_speech_edl(file_id)
    if edl is None:
        raise HTTPException(404, "Speech edit list not found")
    filename = f"AudioEnhancerMAX-{file_id}-speech-edl.{format}"
    if format == "json":
        import json
        content = json.dumps(edl, indent=2, ensure_ascii=False).encode("utf-8")
        media_type = "application/json"
    else:
        output = io.StringIO()
        fields = [
            "id", "type", "label", "start", "end", "duration", "confidence",
            "detector", "action", "decision", "text", "evidence",
        ]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for candidate in edl.get("candidates", []):
            row = dict(candidate)
            for field in {"id", "type", "label", "detector", "action", "decision", "text", "evidence"}:
                value = str(row.get(field, ""))
                if value.startswith(("=", "+", "-", "@")):
                    value = "'" + value
                row[field] = value
            writer.writerow(row)
        content = output.getvalue().encode("utf-8-sig")
        media_type = "text/csv"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )


@app.get("/api/speech-editor/{file_id}/preview/{candidate_id}")
async def preview_speech_edit(
    file_id: str,
    candidate_id: str,
    mode: str = Query(default="original"),
):
    """Stream an original or proposed edit preview with local context."""
    import io
    import soundfile as sf

    file_id = _require_file_id(file_id)
    mode = _require_choice(mode, {"original", "applied"}, "mode")
    if re.fullmatch(r"edit-[0-9]{4}", candidate_id) is None:
        raise HTTPException(400, "Invalid speech edit candidate")
    source_path = _find_source(file_id)
    if not source_path:
        raise HTTPException(404, "File not found")

    from app.services.speech_editor import load_speech_edl, render_candidate_preview

    edl = load_speech_edl(file_id)
    if edl is None:
        raise HTTPException(404, "Speech edit list not found")
    candidate = next((item for item in edl["candidates"] if item["id"] == candidate_id), None)
    if candidate is None:
        raise HTTPException(404, "Speech edit candidate not found")

    audio, sr = await asyncio.to_thread(load_audio, source_path)
    preview = await asyncio.to_thread(
        render_candidate_preview,
        audio,
        sr,
        candidate,
        apply=mode == "applied",
    )
    buffer = io.BytesIO()
    sf.write(buffer, preview, sr, format="WAV", subtype="PCM_16")
    return Response(
        content=buffer.getvalue(),
        media_type="audio/wav",
        headers={"Cache-Control": "no-store"},
    )


@app.post("/api/speech-editor/{file_id}/render")
async def render_speech_edits(file_id: str, request: SpeechEditorRenderRequest):
    """Render approved EDL decisions to a new file while retaining the source."""
    import time as _time

    file_id = _require_file_id(file_id)
    source_path = _find_source(file_id)
    if not source_path:
        raise HTTPException(404, "File not found")

    from app.services.speech_editor import load_speech_edl, render_speech_edl

    edl = load_speech_edl(file_id)
    if edl is None:
        raise HTTPException(404, "Speech edit list not found")
    if int(edl.get("revision", 0)) != request.revision:
        raise HTTPException(409, "Speech edit list changed; reload before rendering")
    if not edl.get("summary", {}).get("selected_candidates"):
        raise HTTPException(400, "No speech edits are approved")

    def render_sync():
        started = _time.monotonic()
        audio, sr = load_audio(source_path)
        from app.services.processing_report import create_processing_report, quality_summary

        input_summary = quality_summary(audio, sr)
        rendered = render_speech_edl(audio, sr, edl)
        output_format = request.output_format.value
        from app.services.artifact_store import publish_audio, atomic_json
        artifact = publish_audio(file_id, rendered, sr, output_format, "speech_edit")
        output_path = OUTPUT_DIR / artifact["exports"][output_format]["name"]
        report = create_processing_report(
            file_id=file_id,
            app_version=APP_VERSION,
            input_summary=input_summary,
            output_audio=rendered,
            output_sample_rate=sr,
            options={
                "operation": "speech_edl_render",
                "edl_revision": edl["revision"],
                "approved_candidate_ids": [
                    item["id"] for item in edl["candidates"]
                    if item["decision"] == "apply"
                ],
                "output_format": output_format,
            },
            active_steps=["speech_edl_render"],
            speech_edl=edl,
            elapsed_seconds=_time.monotonic() - started,
            app_build=APP_BUILD, source_path=source_path, output_path=output_path,
        )
        report["artifact_revision"] = artifact["revision"]
        atomic_json(output_path.with_suffix(".report.json"), report)
        return rendered, sr, output_format, report, artifact, output_path

    try:
        rendered, sr, output_format, report, artifact, output_path = await asyncio.to_thread(render_sync)
    except Exception as exc:
        logger.error("Speech edit rendering failed: %s", exc, exc_info=True)
        raise HTTPException(500, f"Speech edit rendering failed: {exc}") from exc

    return {
        "file_id": file_id,
        "status": "completed",
        "output_url": f"/outputs/{output_path.name}",
        "revision": artifact["revision"],
        "duration_seconds": round(len(rendered) / sr, 3),
        "sample_rate": sr,
        "format": output_format,
        "applied_edits": edl["summary"]["selected_candidates"],
        "source_preserved": True,
        "edl_revision": edl["revision"],
        "report_url": f"/api/reports/{file_id}?version=speech_edit&revision={artifact['revision']}",
        "report_summary": {
            "input_quality_score": report["input"]["quality_score"],
            "output_quality_score": report["output"]["quality_score"],
            "approved_edits": report["speech_edits"]["approved_count"],
        },
    }


# ══════════════════════════════════════════════════════════
# Routes - Text-to-Speech (TTS)
# ══════════════════════════════════════════════════════════

@app.get("/api/voice-profiles")
async def voice_profiles():
    """Named local voice profiles plus the current adapter capability."""
    from app.services.voice_profiles import list_voice_profiles

    return await asyncio.to_thread(list_voice_profiles)


@app.post("/api/voice-profiles/enroll")
async def enroll_voice_profile_endpoint(request: VoiceProfileEnrollRequest):
    """Create a personal voice, or improve one with another recording."""
    from app.services.voice_profiles import enroll_voice_profile

    file_id = _require_file_id(request.file_id)
    source = _find_source(file_id)
    if source is None:
        raise HTTPException(404, "Voice sample not found")
    try:
        return await asyncio.to_thread(
            enroll_voice_profile,
            source_path=source,
            name=request.name,
            profile_id=request.profile_id,
            transcript=request.transcript,
            consent_confirmed=request.consent_confirmed,
            settings=request.settings.model_dump(),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.patch("/api/voice-profiles/{profile_id}")
async def update_voice_profile_endpoint(profile_id: str, request: VoiceProfileUpdateRequest):
    from app.services.voice_profiles import update_voice_profile

    try:
        return await asyncio.to_thread(
            update_voice_profile,
            profile_id,
            request.name,
            request.settings.model_dump(),
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc

@app.get("/api/tts/voices")
async def get_voices():
    from app.services.tts import get_available_voices
    from app.services.runtime_settings import external_service_allowed
    voices = get_available_voices()
    if not external_service_allowed("external"):
        voices = [voice for voice in voices if voice.get("engine") != "edge"]
    return {"voices": voices}


@app.post("/api/tts/synthesize")
async def synthesize(request: TTSRequest):
    try:
        from app.services.tts import synthesize_speech
        from app.services.runtime_settings import external_service_allowed

        if request.expressive and not external_service_allowed("ollama"):
            raise HTTPException(403, "Local Ollama editorial assistance is disabled in Settings")
        if request.engine == "voice-clone" and not request.voice_profile_id:
            raise HTTPException(400, "Select a saved personal voice profile")
        if request.clone_voice_file_id and not request.voice_profile_id:
            raise HTTPException(
                400,
                "One-shot voice samples are no longer accepted. Save the sample as a named personal voice first.",
            )
        if not external_service_allowed("external") and not request.voice_profile_id:
            if request.engine == "edge" or (request.voice_id or "").startswith(("it_", "en_", "es_", "fr_", "de_")):
                raise HTTPException(403, "Optional external TTS services are disabled in Settings")
            if request.engine == "auto":
                request.engine = "kokoro"

        # Run TTS in thread - model loading + inference + Gemma rewrite can take 30+ seconds
        audio, sr, metadata = await asyncio.to_thread(
            synthesize_speech,
            text=request.text, language=request.language,
            voice_id=request.voice_id, speed=request.speed,
            pitch=request.pitch, warmth=request.warmth,
            style=request.style, voice_profile_id=request.voice_profile_id,
            expressive=request.expressive, engine=request.engine,
        )

        # Check if we got actual audio
        if len(audio) < 100:
            raise HTTPException(503, "TTS model not available - check server logs")

        file_id = generate_file_id()
        output_path = get_output_path(file_id, "_tts", ".wav")
        save_audio(audio, sr, output_path)

        return {
            "file_id": file_id,
            "audio_url": f"/outputs/{file_id}_tts.wav",
            "duration": round(len(audio) / sr, 2),
            "engine": metadata.get("engine", "edge"),
            "engine_version": metadata.get("engine_version"),
            "execution": metadata.get("execution", "external" if metadata.get("engine") == "edge" else "local"),
            "model": metadata.get("model"),
            "personal_model": bool(metadata.get("personal_model", False)),
            "voice_profile_id": metadata.get("voice_profile_id"),
            "voice_profile_name": metadata.get("voice_profile_name"),
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
        from app.services.runtime_settings import external_service_allowed
        if not external_service_allowed("ollama"):
            raise HTTPException(403, "Local Ollama editorial assistance is disabled in Settings")
        from app.services.tts import rewrite_expressive
        rewritten = await asyncio.to_thread(
            rewrite_expressive, request.text, request.language, request.style
        )
        return {
            "original": request.text,
            "rewritten": rewritten,
            "changed": rewritten != request.text,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Rewrite failed: {str(e)}")


# ══════════════════════════════════════════════════════════
# Routes - Speaker Diarization
# ══════════════════════════════════════════════════════════

@app.post("/api/diarize")
async def diarize_audio(request: DiarizationRequest):
    """Non-blocking diarization - runs in thread to keep server responsive."""
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
    """Synchronous diarization worker - runs in a separate thread."""
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
# Routes - Audio Watermarking
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
        from app.services.artifact_store import publish_audio
        artifact = await asyncio.to_thread(publish_audio, file_id, watermarked, sr, "wav", "watermarked")
        output_path = OUTPUT_DIR / artifact["exports"]["wav"]["name"]

        return {
            "file_id": file_id,
            "watermarked_url": f"/outputs/{output_path.name}",
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
# Routes - Presets
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
# Routes - Batch Processing
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
# Routes - Download
# ══════════════════════════════════════════════════════════

async def _resolve_export(file_id: str, format: str | None = None,
                          version: str = "processed", revision: str | None = None):
    from app.services.artifact_store import resolve_export, StaleRevision
    try:
        return await asyncio.to_thread(resolve_export, file_id, format, version, revision)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except StaleRevision as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/api/download/{file_id}")
async def download_file(file_id: str, format: str = "wav", version: str = "processed",
                        revision: str | None = None):
    file_id = _require_file_id(file_id)
    format = _require_choice(format, DOWNLOAD_AUDIO_FORMATS, "format")
    version = _require_choice(version, DOWNLOAD_AUDIO_VERSIONS, "version")
    if version == "original":
        path = _find_source(file_id)
        if path is None:
            raise HTTPException(404, "Original audio not found")
        # Original downloads preserve the original artifact; the suffix is explicit.
        return FileResponse(path, media_type=AUDIO_MEDIA_TYPES.get(path.suffix),
                            filename=f"AudioEnhancerMAX_{file_id}_original{path.suffix}",
                            headers={"Cache-Control": "no-store"})
    path, artifact = await _resolve_export(file_id, format, version, revision)
    return FileResponse(path, media_type=AUDIO_MEDIA_TYPES[path.suffix],
                        filename=f"AudioEnhancerMAX_{file_id}.{format}",
                        headers={"Cache-Control": "no-store", "X-Audio-Revision": artifact["revision"],
                                 "X-Audio-SHA256": artifact["exports"][format]["sha256"]})


# ══════════════════════════════════════════════════════════
# WebSocket - Progress
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
    try:
        import torch
        mps_available = bool(torch.backends.mps.is_available())
    except (ImportError, OSError):
        mps_available = False
    gpu_info = "Apple Silicon MPS" if mps_available else "CPU"

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
                "soc_cpu_percent": metrics.get("soc_cpu_percent", 0),
                "app_cpu_percent": metrics.get("app_cpu_percent", 0),
                "app_cpu_core_percent": metrics.get("app_cpu_core_percent", 0),
                "app_ram_mb": metrics.get("app_ram_mb", 0),
                "metric_scope": metrics.get("metric_scope", "system"),
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
        "app": "AudioEnhancerMAX by Fabrizio Degni",
        "version": APP_VERSION,
        "build": APP_BUILD,
        "compute": gpu_info,
        "mps_available": mps_available,
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
            "name": "Mac - Master",
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


def _find_processed_output(file_id: str) -> Optional[Path]:
    """Resolve the explicit current processing master."""
    if not _is_safe_file_id(file_id):
        return None
    from app.services.artifact_store import resolve_export
    try:
        return resolve_export(file_id)[0]
    except (OSError, ValueError):
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


# ══════════════════════════════════════════════════════════
# Routes - Community Roadmap Voting API
# ══════════════════════════════════════════════════════════

@app.get("/api/roadmap/votes")
async def get_roadmap_votes():
    import json
    votes_file = ROADMAP_VOTES_FILE
    if votes_file.exists():
        try:
            with open(votes_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read votes file: {e}")
    return {}

@app.post("/api/roadmap/vote")
async def vote_feature(request: dict):
    import json
    feature_id = request.get("feature_id")
    if not feature_id:
        raise HTTPException(400, "Missing feature_id")

    votes_file = ROADMAP_VOTES_FILE
    votes = {}
    if votes_file.exists():
        try:
            with open(votes_file, "r") as f:
                votes = json.load(f)
        except Exception:
            pass

    votes[feature_id] = votes.get(feature_id, 0) + 1
    try:
        with open(votes_file, "w") as f:
            json.dump(votes, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save votes: {e}")
        raise HTTPException(500, f"Failed to save vote: {e}")

    return {"feature_id": feature_id, "votes": votes[feature_id]}
