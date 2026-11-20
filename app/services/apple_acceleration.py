"""Host chip detection and optional local acceleration for AudioEnhancerMAX."""
import logging
import os
import platform
import subprocess
import sys

logger = logging.getLogger(__name__)


def detect_host_chip() -> str | None:
    """Read the macOS chip model independently of optional model engines."""
    if sys.platform != "darwin":
        return platform.processor() or None
    try:
        result = subprocess.run(
            ["/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True, text=True, timeout=2, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def is_mps_available() -> bool:
    """Return whether this runtime can use the optional PyTorch Metal backend."""
    try:
        import torch
        return bool(torch.backends.mps.is_available())
    except (ImportError, OSError, AttributeError, RuntimeError):
        return False


def configure_apple_acceleration():
    """Apply Apple Silicon runtime defaults without requiring model engines."""
    if sys.platform != "darwin" or platform.machine() not in {"arm64", "aarch64"}:
        return

    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("OMP_NUM_THREADS", str(os.cpu_count() or 1))
    os.environ.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.7")
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    os.environ.setdefault("CT2_USE_EXPERIMENTAL_PACKED_GEMM", "1")
    logger.info("Apple Silicon runtime defaults configured")


def get_optimal_device():
    """Return the best available PyTorch device."""
    if is_mps_available():
        import torch
        return torch.device("mps")
    return "cpu"


def get_acceleration_info() -> dict:
    """Report available engines and any acceleration confirmed by their runtime."""
    mps_available = is_mps_available()
    info = {
        "platform": platform.machine(),
        "chip": detect_host_chip(),
        "accelerations": [],
        "mps_available": mps_available,
    }

    try:
        import numpy
        info["accelerations"].append(f"NumPy {numpy.__version__} (signal processing)")
    except (ImportError, OSError):
        pass

    if mps_available:
        info["accelerations"].append("PyTorch MPS (Metal GPU available)")

    try:
        import ctranslate2
        info["accelerations"].append(f"CTranslate2 {ctranslate2.__version__} (local CPU inference)")
    except (ImportError, OSError, RuntimeError):
        pass

    return info
