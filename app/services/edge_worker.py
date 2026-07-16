#!/usr/bin/env python3
"""
AudioEnhancerMAX by Fd - Edge Worker (Runs on Android via Termux)
Lightweight FastAPI server that processes audio chunks for the main orchestrator.
Only DSP filters - no heavy ML models.

Usage:
  python3 edge_worker.py [--port 8877] [--name "My Phone"]
"""
import asyncio
import io
import json
import logging
import os
import platform
import socket
import struct
import subprocess
import sys
import threading
import time
from typing import Optional

import numpy as np
import uvicorn
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import Response

logging.basicConfig(level=logging.INFO, format="%(asctime)s [WORKER] %(message)s")
logger = logging.getLogger("edge_worker")

# ══════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════

WORKER_PORT = int(os.environ.get("WORKER_PORT", "8877"))
WORKER_NAME = os.environ.get("WORKER_NAME", f"Worker-{platform.node()}")
DISCOVERY_PORT = 9999
DISCOVERY_MAGIC = b"AEMAX_DISCOVER"
DISCOVERY_INTERVAL = 5  # seconds

app = FastAPI(title=f"AudioEnhancerMAX Edge Worker - {WORKER_NAME}")


# ══════════════════════════════════════════════════════════
# Device Detection
# ══════════════════════════════════════════════════════════

def _detect_device() -> dict:
    """Detect device model and capabilities."""
    info = {
        "name": WORKER_NAME,
        "device_model": "Unknown",
        "cpu_cores": os.cpu_count() or 4,
        "ram_gb": 0,
        "soc": "Unknown",
        "platform": platform.system(),
        "arch": platform.machine(),
    }

    # Try Android-specific detection
    try:
        result = subprocess.run(
            ["getprop", "ro.product.model"],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0 and result.stdout.strip():
            info["device_model"] = result.stdout.strip()
    except FileNotFoundError:
        pass

    # Try SoC detection
    try:
        result = subprocess.run(
            ["getprop", "ro.soc.model"],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0 and result.stdout.strip():
            info["soc"] = result.stdout.strip()
    except FileNotFoundError:
        pass

    # RAM detection
    try:
        import psutil
        info["ram_gb"] = round(psutil.virtual_memory().total / 1024**3, 1)
    except ImportError:
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if "MemTotal" in line:
                        kb = int(line.split()[1])
                        info["ram_gb"] = round(kb / 1024**2, 1)
                        break
        except Exception:
            pass

    return info


DEVICE_INFO = _detect_device()

# Available DSP filters on this worker
AVAILABLE_FILTERS = [
    "remove_noise", "wind_noise_remover", "buzzing_noise_remover",
    "static_noise_remover", "reverb_echo_remover", "remove_mouth_sounds",
    "remove_breaths", "remove_long_silences", "auto_eq", "studio_sound",
    "normalize", "frequency_restoration",
]


# ══════════════════════════════════════════════════════════
# DSP Processing Functions (Lightweight)
# ══════════════════════════════════════════════════════════

def _apply_noise_reduction(audio: np.ndarray, sr: int, strength: float = 0.7) -> np.ndarray:
    """Noise reduction using noisereduce (spectral gating)."""
    try:
        import noisereduce as nr
        prop_decrease = min(0.85, strength * 0.85)
        reduced = nr.reduce_noise(
            y=audio, sr=sr,
            prop_decrease=prop_decrease,
            stationary=True,
            n_std_thresh_stationary=max(1.5, 2.0 - (strength * 0.5)),
            time_mask_smooth_ms=100,
            freq_mask_smooth_hz=500,
        )
        wet = min(0.85, strength)
        return reduced * wet + audio * (1.0 - wet)
    except ImportError:
        logger.warning("noisereduce not available")
        return audio


def _apply_studio_sound(audio: np.ndarray, sr: int) -> np.ndarray:
    """Studio processing chain using pedalboard."""
    try:
        import pedalboard as pb
        board = pb.Pedalboard([
            pb.HighpassFilter(cutoff_frequency_hz=80.0),
            pb.LowShelfFilter(cutoff_frequency_hz=150.0, gain_db=1.0),
            pb.HighShelfFilter(cutoff_frequency_hz=4000.0, gain_db=1.5),
            pb.PeakFilter(cutoff_frequency_hz=6000.0, gain_db=-3.0, q=2.0),
            pb.Compressor(threshold_db=-18.0, ratio=2.0, attack_ms=25.0, release_ms=150.0),
            pb.Gain(gain_db=1.5),
            pb.Limiter(threshold_db=-1.0, release_ms=200.0),
        ])
        audio_2d = audio.reshape(1, -1) if audio.ndim == 1 else audio
        processed = board(audio_2d, sr)
        return processed.flatten() if audio.ndim == 1 else processed
    except ImportError:
        logger.warning("pedalboard not available")
        return audio


def _apply_auto_eq(audio: np.ndarray, sr: int) -> np.ndarray:
    """Auto EQ for broadcast voice."""
    try:
        import pedalboard as pb
        board = pb.Pedalboard([
            pb.HighpassFilter(cutoff_frequency_hz=80.0),
            pb.LowShelfFilter(cutoff_frequency_hz=150.0, gain_db=1.0),
            pb.LowShelfFilter(cutoff_frequency_hz=250.0, gain_db=-1.5),
            pb.PeakFilter(cutoff_frequency_hz=2500.0, gain_db=1.5, q=1.0),
            pb.PeakFilter(cutoff_frequency_hz=5000.0, gain_db=1.0, q=0.7),
            pb.HighShelfFilter(cutoff_frequency_hz=8000.0, gain_db=0.5),
            pb.LowpassFilter(cutoff_frequency_hz=16000.0),
        ])
        audio_2d = audio.reshape(1, -1) if audio.ndim == 1 else audio
        processed = board(audio_2d, sr)
        return processed.flatten() if audio.ndim == 1 else processed
    except ImportError:
        return audio


def _apply_normalize(audio: np.ndarray, sr: int, target_lufs: float = -16.0) -> np.ndarray:
    """Simple peak normalization."""
    peak = np.max(np.abs(audio))
    if peak > 0:
        target_peak = 10 ** (target_lufs / 20)
        audio = audio * (target_peak / peak)
    return np.clip(audio, -1.0, 1.0)


def process_chunk(audio: np.ndarray, sr: int, filters: dict) -> np.ndarray:
    """Apply requested DSP filters to an audio chunk."""
    if filters.get("remove_noise"):
        audio = _apply_noise_reduction(audio, sr)
    if filters.get("studio_sound"):
        audio = _apply_studio_sound(audio, sr)
    if filters.get("auto_eq"):
        audio = _apply_auto_eq(audio, sr)
    if filters.get("normalize"):
        audio = _apply_normalize(audio, sr)
    return audio


# ══════════════════════════════════════════════════════════
# API Endpoints
# ══════════════════════════════════════════════════════════

@app.get("/worker/health")
async def health():
    """Health check + capabilities report."""
    try:
        import psutil
        cpu_pct = psutil.cpu_percent(interval=0.1)
        ram_pct = psutil.virtual_memory().percent
    except ImportError:
        cpu_pct = 0
        ram_pct = 0

    return {
        **DEVICE_INFO,
        "status": "online",
        "port": WORKER_PORT,
        "filters": AVAILABLE_FILTERS,
        "benchmark": 0,
        "cpu_percent": cpu_pct,
        "ram_percent": ram_pct,
        "timestamp": time.time(),
    }


@app.get("/worker/status")
async def status():
    """Current load and availability."""
    try:
        import psutil
        return {
            "status": "online",
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "ram_percent": psutil.virtual_memory().percent,
            "load_avg": os.getloadavg() if hasattr(os, "getloadavg") else [0, 0, 0],
        }
    except ImportError:
        return {"status": "online", "cpu_percent": 0, "ram_percent": 0}


@app.post("/worker/process")
async def process_audio(
    audio: UploadFile = File(...),
    filters: str = Form("{}"),
    sr: str = Form("44100"),
):
    """Process an audio chunk with specified DSP filters."""
    import soundfile as sf

    start_time = time.time()

    # Read audio
    audio_bytes = await audio.read()
    buf = io.BytesIO(audio_bytes)
    audio_data, sample_rate = sf.read(buf, dtype="float32")

    # Parse filters
    filter_dict = json.loads(filters)

    logger.info(
        f"Processing chunk: {len(audio_data)/int(sr):.1f}s, "
        f"filters: {[k for k,v in filter_dict.items() if v]}"
    )

    # Process
    result = process_chunk(audio_data, sample_rate, filter_dict)

    elapsed = time.time() - start_time
    logger.info(f" Chunk processed in {elapsed:.2f}s")

    # Return as WAV bytes
    out_buf = io.BytesIO()
    sf.write(out_buf, result, sample_rate, format="WAV", subtype="FLOAT")
    out_bytes = out_buf.getvalue()

    return Response(content=out_bytes, media_type="audio/wav")


# ══════════════════════════════════════════════════════════
# Discovery Broadcast
# ══════════════════════════════════════════════════════════

def _broadcast_presence():
    """Periodically broadcast presence on the LAN."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    payload = json.dumps({
        "port": WORKER_PORT,
        "name": DEVICE_INFO["name"],
        "device_model": DEVICE_INFO["device_model"],
        "cpu_cores": DEVICE_INFO["cpu_cores"],
        "ram_gb": DEVICE_INFO["ram_gb"],
        "filters": AVAILABLE_FILTERS,
        "benchmark": 0,
    }).encode()

    message = DISCOVERY_MAGIC + payload

    while True:
        try:
            sock.sendto(message, ("<broadcast>", DISCOVERY_PORT))
            logger.debug("Discovery broadcast sent")
        except Exception as e:
            logger.debug(f"Broadcast failed: {e}")
        time.sleep(DISCOVERY_INTERVAL)


# ══════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AudioEnhancerMAX Edge Worker")
    parser.add_argument("--port", type=int, default=WORKER_PORT)
    parser.add_argument("--name", type=str, default=WORKER_NAME)
    args = parser.parse_args()

    WORKER_PORT = args.port
    WORKER_NAME = args.name
    DEVICE_INFO["name"] = WORKER_NAME

    # Start discovery broadcast in background
    broadcast_thread = threading.Thread(target=_broadcast_presence, daemon=True)
    broadcast_thread.start()

    logger.info(f" Edge Worker starting: {WORKER_NAME}")
    logger.info(f"   Device: {DEVICE_INFO['device_model']}")
    logger.info(f"   SoC: {DEVICE_INFO['soc']}")
    logger.info(f"   Cores: {DEVICE_INFO['cpu_cores']}, RAM: {DEVICE_INFO['ram_gb']}GB")
    logger.info(f"   Port: {WORKER_PORT}")
    logger.info(f"   Filters: {len(AVAILABLE_FILTERS)} DSP filters available")

    uvicorn.run(app, host="0.0.0.0", port=WORKER_PORT, log_level="info")
