"""
AudioEnhancerMAX by Fd - Apple Silicon Acceleration Module
Centralized Metal/MPS/ANE/Accelerate optimizations for M3 MAX.

GPU acceleration strategy:
- PyTorch MPS (Metal): Demucs, pyannote diarization
- Apple Accelerate (vDSP): numpy FFT, scipy signal processing
- ARM NEON (via ctranslate2): faster-whisper inference
- CoreML/ANE: future - model compilation for Neural Engine

Note: CTranslate2 (faster-whisper) does NOT support MPS.
Its ARM NEON backend is already optimized for Apple Silicon.
"""
import logging
import os
import platform
import sys

logger = logging.getLogger(__name__)


def configure_apple_acceleration():
    """
    Configure environment for optimal Apple Silicon performance.
    Call this once at application startup.
    """
    if platform.machine() != "arm64":
        logger.info("Not Apple Silicon - skipping Metal acceleration config")
        return

    optimizations = []

    # 1. Enable Apple Accelerate for numpy/scipy (BLAS/LAPACK/vDSP)
    # macOS ships numpy linked against Accelerate by default,
    # but we ensure OPENBLAS threading doesn't interfere
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("OMP_NUM_THREADS", str(os.cpu_count()))
    optimizations.append("Apple Accelerate (BLAS/vDSP)")

    # 2. PyTorch MPS backend
    try:
        import torch
        if torch.backends.mps.is_available():
            # Set default device for new tensors (opt-in per operation)
            os.environ.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.7")
            # Enable MPS fallback for unsupported ops (prevents crashes)
            os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
            optimizations.append(f"PyTorch MPS (Metal) - {torch.backends.mps.is_built()}")
        else:
            optimizations.append("PyTorch MPS - not available")
    except ImportError:
        pass

    # 3. CTranslate2 (faster-whisper) - ARM NEON is auto-detected
    # No config needed, but we can set inter/intra threads
    os.environ.setdefault("CT2_USE_EXPERIMENTAL_PACKED_GEMM", "1")
    optimizations.append("CTranslate2 ARM NEON")

    # 4. LibTorch memory optimization
    os.environ.setdefault("PYTORCH_MPS_ALLOCATOR_POLICY", "garbage_collection")
    optimizations.append("MPS GC allocator")

    # 5. Multiprocessing for signal processing
    # Use fork on macOS for numpy/scipy parallelism
    try:
        import multiprocessing
        if multiprocessing.get_start_method(allow_none=True) is None:
            multiprocessing.set_start_method("fork", force=False)
    except (RuntimeError, ValueError):
        pass

    logger.info(
        f" Apple Silicon acceleration configured: "
        f"{', '.join(optimizations)}"
    )


def get_optimal_device():
    """Return the best available PyTorch device."""
    try:
        import torch
        if torch.backends.mps.is_available():
            return torch.device("mps")
    except ImportError:
        pass
    return "cpu"


def get_acceleration_info() -> dict:
    """Return info about what acceleration is active."""
    info = {
        "platform": platform.machine(),
        "chip": _detect_chip(),
        "accelerations": [],
    }

    # Check numpy backend
    try:
        import numpy as np
        config = np.__config__
        blas_info = str(config.show()) if hasattr(config, 'show') else ""
        if "accelerate" in str(getattr(np, '__config__', '')).lower():
            info["accelerations"].append("Apple Accelerate (BLAS)")
        else:
            info["accelerations"].append("numpy (generic BLAS)")
    except Exception:
        pass

    # Check PyTorch MPS
    try:
        import torch
        if torch.backends.mps.is_available():
            info["accelerations"].append("PyTorch MPS (Metal GPU)")
            info["mps_available"] = True
        else:
            info["mps_available"] = False
    except ImportError:
        info["mps_available"] = False

    # Check CTranslate2
    try:
        import ctranslate2
        info["accelerations"].append(f"CTranslate2 {ctranslate2.__version__} (ARM NEON)")
    except ImportError:
        pass

    return info


def _detect_chip() -> str:
    """Detect Apple Silicon chip name."""
    try:
        import subprocess
        result = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip()
    except Exception:
        return platform.processor() or "Unknown"
