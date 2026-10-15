"""JIT-free signal-processing primitives used by packaged macOS builds.

The application previously delegated basic DSP operations to librosa.  That
dependency imports Numba/llvmlite and attempts to create executable memory at
runtime, which is incompatible with the hardened macOS distribution.  These
helpers intentionally use only NumPy and SciPy native wheels.
"""
from __future__ import annotations

from math import gcd

import numpy as np
from scipy import fftpack, signal


def db_to_amplitude(db: float) -> float:
    return float(10.0 ** (float(db) / 20.0))


def resample_audio(audio: np.ndarray, original_rate: int, target_rate: int) -> np.ndarray:
    """Resample along the sample axis with a polyphase anti-aliasing filter."""
    array = np.asarray(audio)
    if int(original_rate) == int(target_rate):
        return array.copy()
    common = gcd(int(original_rate), int(target_rate))
    result = signal.resample_poly(
        array,
        int(target_rate) // common,
        int(original_rate) // common,
        axis=-1,
        padtype="line",
    )
    return result.astype(array.dtype if np.issubdtype(array.dtype, np.floating) else np.float32, copy=False)


def stft(audio: np.ndarray, n_fft: int = 2048, hop_length: int | None = None) -> np.ndarray:
    """Return a centered complex STFT with frequency bins on axis zero."""
    samples = np.asarray(audio, dtype=np.float32)
    if samples.ndim != 1:
        raise ValueError("STFT expects mono audio")
    if len(samples) < int(n_fft):
        samples = np.pad(samples, (0, int(n_fft) - len(samples)))
    hop = int(hop_length or n_fft // 4)
    if hop <= 0 or hop > n_fft:
        raise ValueError("hop_length must be between 1 and n_fft")
    _, _, spectrum = signal.stft(
        samples,
        window="hann",
        nperseg=int(n_fft),
        noverlap=int(n_fft) - hop,
        nfft=int(n_fft),
        boundary="zeros",
        padded=True,
    )
    return spectrum


def istft(
    spectrum: np.ndarray,
    *,
    n_fft: int | None = None,
    hop_length: int | None = None,
    length: int | None = None,
) -> np.ndarray:
    """Invert :func:`stft` and trim or pad to an exact requested length."""
    bins = int(np.asarray(spectrum).shape[0])
    fft_size = int(n_fft or max(2, (bins - 1) * 2))
    hop = int(hop_length or fft_size // 4)
    _, samples = signal.istft(
        spectrum,
        window="hann",
        nperseg=fft_size,
        noverlap=fft_size - hop,
        nfft=fft_size,
        input_onesided=True,
        boundary=True,
    )
    samples = np.asarray(samples, dtype=np.float32)
    if length is not None:
        requested = max(0, int(length))
        if len(samples) < requested:
            samples = np.pad(samples, (0, requested - len(samples)))
        else:
            samples = samples[:requested]
    return samples


def _frames(audio: np.ndarray, frame_length: int, hop_length: int) -> np.ndarray:
    samples = np.asarray(audio, dtype=np.float32)
    if samples.ndim != 1:
        raise ValueError("Frame analysis expects mono audio")
    frame_length = max(2, int(frame_length))
    hop_length = max(1, int(hop_length))
    if not len(samples):
        return np.zeros((1, frame_length), dtype=np.float32)
    pad = frame_length // 2
    mode = "reflect" if len(samples) > 1 else "constant"
    padded = np.pad(samples, (pad, pad), mode=mode)
    if len(padded) < frame_length:
        padded = np.pad(padded, (0, frame_length - len(padded)))
    windows = np.lib.stride_tricks.sliding_window_view(padded, frame_length)[::hop_length]
    return np.asarray(windows)


def rms_frames(audio: np.ndarray, frame_length: int = 2048, hop_length: int = 512) -> np.ndarray:
    frames = _frames(audio, frame_length, hop_length)
    return np.sqrt(np.mean(np.square(frames, dtype=np.float64), axis=1)).astype(np.float32)


def zero_crossing_rate(
    audio: np.ndarray,
    frame_length: int = 2048,
    hop_length: int = 512,
) -> np.ndarray:
    frames = _frames(audio, frame_length, hop_length)
    signs = np.signbit(frames)
    return np.mean(signs[:, 1:] != signs[:, :-1], axis=1).astype(np.float32)


def spectral_features(
    audio: np.ndarray,
    sample_rate: int,
    *,
    n_fft: int = 2048,
    hop_length: int = 512,
) -> tuple[np.ndarray, np.ndarray]:
    """Return per-frame spectral centroid and bandwidth in hertz."""
    frames = _frames(audio, n_fft, hop_length)
    windowed = frames * signal.windows.hann(n_fft, sym=False)
    magnitude = np.abs(np.fft.rfft(windowed, n=n_fft, axis=1))
    frequencies = np.fft.rfftfreq(n_fft, d=1.0 / float(sample_rate))
    weights = np.sum(magnitude, axis=1) + np.finfo(np.float32).eps
    centroid = np.sum(magnitude * frequencies[None, :], axis=1) / weights
    variance = np.sum(
        magnitude * np.square(frequencies[None, :] - centroid[:, None]),
        axis=1,
    ) / weights
    return centroid.astype(np.float32), np.sqrt(np.maximum(variance, 0)).astype(np.float32)


def onset_strength(
    audio: np.ndarray,
    sample_rate: int,
    *,
    n_fft: int = 2048,
    hop_length: int = 512,
) -> np.ndarray:
    del sample_rate  # Kept in the signature for call-site clarity.
    magnitude = np.abs(stft(audio, n_fft=n_fft, hop_length=hop_length))
    if magnitude.shape[1] < 2:
        return np.zeros(1, dtype=np.float32)
    flux = np.maximum(np.diff(magnitude, axis=1), 0.0)
    return np.mean(flux, axis=0).astype(np.float32)


def estimate_tempo(onsets: np.ndarray, sample_rate: int, hop_length: int = 512) -> float:
    envelope = np.asarray(onsets, dtype=np.float32)
    if envelope.size < 3 or not np.any(envelope):
        return 0.0
    centered = envelope - np.mean(envelope)
    correlation = signal.correlate(centered, centered, mode="full", method="fft")
    correlation = correlation[len(centered) - 1 :]
    min_lag = max(1, int(round(60.0 * sample_rate / (200.0 * hop_length))))
    max_lag = min(len(correlation) - 1, int(round(60.0 * sample_rate / (40.0 * hop_length))))
    if max_lag <= min_lag:
        return 0.0
    lag = min_lag + int(np.argmax(correlation[min_lag : max_lag + 1]))
    return float(60.0 * sample_rate / (hop_length * lag))


def mfcc(
    audio: np.ndarray,
    sample_rate: int,
    *,
    n_mfcc: int = 13,
    hop_length: int = 512,
    n_fft: int = 2048,
    n_mels: int = 40,
) -> np.ndarray:
    """Compute compact MFCC features without librosa or runtime compilation."""
    magnitude = np.abs(stft(audio, n_fft=n_fft, hop_length=hop_length))
    power = np.square(magnitude, dtype=np.float64)
    frequencies = np.fft.rfftfreq(n_fft, d=1.0 / float(sample_rate))

    def hz_to_mel(value: np.ndarray | float) -> np.ndarray:
        return 2595.0 * np.log10(1.0 + np.asarray(value) / 700.0)

    def mel_to_hz(value: np.ndarray | float) -> np.ndarray:
        return 700.0 * (np.power(10.0, np.asarray(value) / 2595.0) - 1.0)

    mel_points = np.linspace(hz_to_mel(20.0), hz_to_mel(sample_rate / 2.0), n_mels + 2)
    hz_points = mel_to_hz(mel_points)
    filters = np.zeros((n_mels, len(frequencies)), dtype=np.float64)
    for index in range(n_mels):
        left, center, right = hz_points[index : index + 3]
        rising = (frequencies - left) / max(center - left, np.finfo(float).eps)
        falling = (right - frequencies) / max(right - center, np.finfo(float).eps)
        filters[index] = np.maximum(0.0, np.minimum(rising, falling))
    mel_power = np.maximum(filters @ power, np.finfo(float).eps)
    coefficients = fftpack.dct(np.log(mel_power), type=2, axis=0, norm="ortho")
    return coefficients[: int(n_mfcc)].astype(np.float32)
