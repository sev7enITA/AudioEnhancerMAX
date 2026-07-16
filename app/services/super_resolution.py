"""
AudioEnhancerMAX by Fd - Audio Super-Resolution Service
Restores lost frequencies from compression, upsamples bitrate.
"""
import numpy as np
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def restore_frequencies(
    audio: np.ndarray,
    sr: int,
    target_sr: int = 48000,
) -> tuple:
    """
    Audio super-resolution: restore frequencies lost to compression.
    Uses AudioSR if available, falls back to high-quality resampling + spectral enhancement.

    Returns (enhanced_audio, new_sample_rate)
    """
    # Try AudioSR first (AI-based)
    result = _try_audiosr(audio, sr, target_sr)
    if result is not None:
        return result

    # Fallback: high-quality resampling + spectral enhancement
    logger.info("Using spectral enhancement fallback for super-resolution")
    return _spectral_enhance(audio, sr, target_sr)


def _try_audiosr(
    audio: np.ndarray,
    sr: int,
    target_sr: int,
) -> Optional[tuple]:
    """Try using AudioSR for AI-based super-resolution."""
    try:
        # AudioSR requires specific installation
        import audiosr

        # AudioSR expects audio as a specific format
        enhanced = audiosr.super_resolution(
            audio,
            sr,
            target_sr=target_sr,
        )

        logger.info(f"AudioSR: {sr}Hz -> {target_sr}Hz super-resolution applied")
        return enhanced, target_sr

    except ImportError:
        logger.info("AudioSR not installed. Using fallback.")
        return None
    except Exception as e:
        logger.warning(f"AudioSR failed: {e}")
        return None


def _spectral_enhance(
    audio: np.ndarray,
    sr: int,
    target_sr: int,
) -> tuple:
    """
    Fallback super-resolution using high-quality resampling
    + spectral enhancement to synthesize high frequencies.
    """
    import librosa

    # Step 1: High-quality resample
    if sr < target_sr:
        audio_hr = librosa.resample(audio, orig_sr=sr, target_sr=target_sr, res_type='soxr_hq')
    else:
        audio_hr = audio
        target_sr = sr

    # Step 2: Spectral enhancement - add harmonics
    # Analyze existing spectrum to generate plausible high-frequency content
    n_fft = 4096
    S = librosa.stft(audio_hr, n_fft=n_fft)
    magnitude = np.abs(S)
    phase = np.angle(S)

    # Nyquist bin for original sample rate
    original_nyquist_bin = int(n_fft * (sr / 2) / target_sr)

    # Generate harmonic extensions above original Nyquist
    for i in range(original_nyquist_bin, magnitude.shape[0]):
        # Mirror lower frequencies with decreasing amplitude
        source_bin = i % original_nyquist_bin
        if source_bin < magnitude.shape[0]:
            # v2.0: Faster harmonic rolloff (was /4, now /6)
            # Less aggressive = less harsh artificial harmonics
            harmonic_order = i // original_nyquist_bin
            attenuation = 1.0 / (harmonic_order * 6 + 1)
            magnitude[i] = magnitude[source_bin] * attenuation

    # Reconstruct with enhanced spectrum
    S_enhanced = magnitude * np.exp(1j * phase)
    audio_enhanced = librosa.istft(S_enhanced, length=len(audio_hr))

    # v2.0: Reduced blending (was 0.3, now 0.15)
    # Subtler enhancement preserves natural character
    alpha = 0.15
    result = audio_hr * (1 - alpha) + audio_enhanced * alpha

    # Normalize
    peak = np.max(np.abs(result))
    if peak > 1.0:
        result = result / peak * 0.99

    logger.info(f"Spectral enhancement: {sr}Hz -> {target_sr}Hz")
    return result, target_sr


def boost_bitrate(
    audio: np.ndarray,
    sr: int,
    target_bit_depth: int = 24,
) -> np.ndarray:
    """
    Improve audio quality by processing at higher bit depth.
    Applies dithering for bit-depth conversion.
    """
    # Ensure float64 for processing
    audio = audio.astype(np.float64)

    # Apply subtle noise shaping dither
    if target_bit_depth >= 24:
        dither_level = 1.0 / (2 ** 23)  # 24-bit dither
    else:
        dither_level = 1.0 / (2 ** 15)  # 16-bit dither

    # Triangular probability dither (TPDF)
    dither = np.random.triangular(-dither_level, 0, dither_level, size=audio.shape)
    audio = audio + dither

    # Clip
    audio = np.clip(audio, -1.0, 1.0)

    return audio.astype(np.float32)
