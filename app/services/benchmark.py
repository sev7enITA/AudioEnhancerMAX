"""
AudioEnhancerMAX by Fd - DSP Benchmark Module
Standardized benchmark to compare device performance across the cluster.

Runs a set of representative DSP operations on a synthetic audio signal
and measures throughput. The same benchmark runs on both Mac and Android
workers, enabling fair cross-device comparison.
"""
import time
import logging
import numpy as np
from typing import Optional

logger = logging.getLogger(__name__)

# Benchmark result cache
_benchmark_result: Optional[dict] = None


def run_dsp_benchmark(duration_seconds: float = 5.0, sample_rate: int = 44100) -> dict:
    """
    Run a standardized DSP benchmark suite.
    Tests: FFT, noise reduction, filtering, resampling.
    Returns a score dict with ops/sec and overall score.
    """
    global _benchmark_result

    logger.info(" Running DSP benchmark...")
    results = {}

    # Generate test signal (pink noise + sine tones)
    n_samples = int(duration_seconds * sample_rate)
    t = np.linspace(0, duration_seconds, n_samples, dtype=np.float32)
    test_signal = (
        0.3 * np.sin(2 * np.pi * 440 * t) +
        0.2 * np.sin(2 * np.pi * 1000 * t) +
        0.1 * np.random.randn(n_samples).astype(np.float32)
    )

    # 1. FFT Benchmark (most common DSP operation)
    fft_times = []
    for _ in range(20):
        start = time.perf_counter()
        spectrum = np.fft.rfft(test_signal)
        _ = np.fft.irfft(spectrum)
        fft_times.append(time.perf_counter() - start)
    
    avg_fft = np.median(fft_times)
    results["fft"] = {
        "ops_per_sec": round(1.0 / avg_fft, 1),
        "avg_ms": round(avg_fft * 1000, 2),
        "description": f"FFT/IFFT on {n_samples} samples"
    }

    # 2. FIR Filter Benchmark (used in EQ, studio sound)
    try:
        from scipy.signal import firwin, lfilter
        coeffs = firwin(256, [100, 8000], pass_zero=False, fs=sample_rate)
        filter_times = []
        for _ in range(20):
            start = time.perf_counter()
            _ = lfilter(coeffs, 1.0, test_signal)
            filter_times.append(time.perf_counter() - start)
        
        avg_filter = np.median(filter_times)
        results["fir_filter"] = {
            "ops_per_sec": round(1.0 / avg_filter, 1),
            "avg_ms": round(avg_filter * 1000, 2),
            "description": "256-tap FIR bandpass filter"
        }
    except ImportError:
        results["fir_filter"] = {"ops_per_sec": 0, "avg_ms": 0, "description": "scipy not available"}

    # 3. Spectral Gating (noise reduction core)
    stft_times = []
    for _ in range(10):
        start = time.perf_counter()
        # STFT
        n_fft = 2048
        hop = 512
        frames = (len(test_signal) - n_fft) // hop
        for i in range(frames):
            chunk = test_signal[i * hop:i * hop + n_fft]
            spec = np.fft.rfft(chunk * np.hanning(n_fft))
            mag = np.abs(spec)
            # Spectral gate
            threshold = np.mean(mag) * 0.5
            mask = (mag > threshold).astype(np.float32)
            _ = np.fft.irfft(spec * mask)
        stft_times.append(time.perf_counter() - start)
    
    avg_stft = np.median(stft_times)
    results["spectral_gate"] = {
        "ops_per_sec": round(1.0 / avg_stft, 1),
        "avg_ms": round(avg_stft * 1000, 2),
        "description": f"STFT spectral gating ({frames} frames)"
    }

    # 4. Resampling Benchmark
    try:
        from scipy.signal import resample
        resample_times = []
        for _ in range(5):
            start = time.perf_counter()
            _ = resample(test_signal, int(n_samples * 48000 / sample_rate))
            resample_times.append(time.perf_counter() - start)
        
        avg_resample = np.median(resample_times)
        results["resample"] = {
            "ops_per_sec": round(1.0 / avg_resample, 1),
            "avg_ms": round(avg_resample * 1000, 2),
            "description": f"Resample {sample_rate}->48000 Hz"
        }
    except ImportError:
        results["resample"] = {"ops_per_sec": 0, "avg_ms": 0, "description": "scipy not available"}

    # Calculate overall score (weighted geometric mean)
    weights = {"fft": 3, "fir_filter": 2, "spectral_gate": 3, "resample": 1}
    total_weight = 0
    log_sum = 0
    for key, weight in weights.items():
        ops = results.get(key, {}).get("ops_per_sec", 0)
        if ops > 0:
            log_sum += weight * np.log(ops)
            total_weight += weight

    overall_score = round(np.exp(log_sum / total_weight), 1) if total_weight > 0 else 0

    _benchmark_result = {
        "score": overall_score,
        "tests": results,
        "signal_duration_sec": duration_seconds,
        "sample_rate": sample_rate,
        "timestamp": time.time(),
    }

    logger.info(f" Benchmark complete - Score: {overall_score} ops/s")
    return _benchmark_result


def get_benchmark_result() -> Optional[dict]:
    """Get cached benchmark result, or run if not available."""
    global _benchmark_result
    if _benchmark_result is None:
        run_dsp_benchmark()
    return _benchmark_result
