"""
AudioEnhancerMAX by Fd - Audio Enhancement Service
Studio sound, AutoEQ, normalization, music preservation.
"""
import numpy as np
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def apply_studio_sound(
    audio: np.ndarray,
    sr: int,
) -> np.ndarray:
    """
    Apply studio-quality processing chain (v2.0 - Broadcast standard):
    1. High-pass rumble filter
    2. Gentle EQ for warmth + clarity
    3. De-esser to tame sibilance
    4. Gentle compression (preserves natural transients)
    5. Soft limiting
    """
    try:
        import pedalboard as pb

        # v2.0: Broadcast-quality chain - designed to sound natural,
        # not "processed". Key changes from v1:
        # - Slower attack (25ms) preserves consonant transients
        # - Lower ratio (2:1) = gentle compression, no pumping
        # - Less gain (+1.5dB) avoids over-driving the limiter
        # - De-esser tames sibilance without harshness
        # - Warmth boost at 150Hz for fuller voice
        board = pb.Pedalboard([
            # High-pass filter: remove rumble below 80Hz
            pb.HighpassFilter(cutoff_frequency_hz=80.0),

            # Warmth: gentle low-shelf boost for fuller voice body
            pb.LowShelfFilter(cutoff_frequency_hz=150.0, gain_db=1.0),

            # Presence: subtle clarity boost at 4kHz (v1 used 3kHz +2dB - too harsh)
            pb.HighShelfFilter(cutoff_frequency_hz=4000.0, gain_db=1.5),

            # De-esser: tame sibilance at 6kHz (prevents harsh S sounds)
            pb.PeakFilter(cutoff_frequency_hz=6000.0, gain_db=-3.0, q=2.0),

            # Compression: gentle broadcast-style (v1 was too aggressive)
            # - Attack 25ms: lets consonant transients through (v1: 10ms = destroyed them)
            # - Ratio 2:1: gentle dynamic control (v1: 3:1 = over-compressed)
            # - Threshold -18dB: higher = less compression overall
            pb.Compressor(
                threshold_db=-18.0,
                ratio=2.0,
                attack_ms=25.0,
                release_ms=150.0,
            ),

            # Gain stage: +1.5dB (v1: +3dB pushed too hard into limiter)
            pb.Gain(gain_db=1.5),

            # Limiter: gentle brick wall, slower release for transparent limiting
            pb.Limiter(threshold_db=-1.0, release_ms=200.0),
        ])

        # Pedalboard expects shape (channels, samples)
        if audio.ndim == 1:
            audio_2d = audio.reshape(1, -1)
        else:
            audio_2d = audio

        processed = board(audio_2d, sr)

        return processed.flatten() if audio.ndim == 1 else processed

    except ImportError:
        logger.warning("Pedalboard not installed. Applying basic processing.")
        return _basic_studio(audio, sr)


def _basic_studio(audio: np.ndarray, sr: int) -> np.ndarray:
    """Basic studio processing fallback without pedalboard."""
    from scipy import signal

    # High-pass filter
    sos = signal.butter(4, 80, btype='high', fs=sr, output='sos')
    audio = signal.sosfilt(sos, audio)

    # Simple compression
    threshold = 0.3
    ratio = 3.0
    above = np.abs(audio) > threshold
    audio[above] = np.sign(audio[above]) * (
        threshold + (np.abs(audio[above]) - threshold) / ratio
    )

    # Normalize to -1dB
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak * 0.89

    return audio


def apply_auto_eq(
    audio: np.ndarray,
    sr: int,
    target_profile: str = "broadcast"
) -> np.ndarray:
    """
    Apply intelligent auto-EQ based on spectral analysis.
    Adjusts frequency response to match a target profile.
    """
    try:
        import pedalboard as pb

        if target_profile == "broadcast":
            # v2.0 Broadcast/podcast EQ profile - warmer, less harsh
            # Key change: reduced 2.5kHz peak from +2.5dB to +1.5dB
            # Added warmth boost at 150Hz for fuller voice body
            board = pb.Pedalboard([
                pb.HighpassFilter(cutoff_frequency_hz=80.0),
                pb.LowShelfFilter(cutoff_frequency_hz=150.0, gain_db=1.0),
                pb.LowShelfFilter(cutoff_frequency_hz=250.0, gain_db=-1.5),
                pb.PeakFilter(cutoff_frequency_hz=2500.0, gain_db=1.5, q=1.0),
                pb.PeakFilter(cutoff_frequency_hz=5000.0, gain_db=1.0, q=0.7),
                pb.HighShelfFilter(cutoff_frequency_hz=8000.0, gain_db=0.5),
                pb.LowpassFilter(cutoff_frequency_hz=16000.0),
            ])
        elif target_profile == "warm":
            board = pb.Pedalboard([
                pb.HighpassFilter(cutoff_frequency_hz=60.0),
                pb.LowShelfFilter(cutoff_frequency_hz=250.0, gain_db=2.0),
                pb.PeakFilter(cutoff_frequency_hz=1000.0, gain_db=-1.0, q=0.5),
                pb.HighShelfFilter(cutoff_frequency_hz=6000.0, gain_db=-1.0),
            ])
        elif target_profile == "bright":
            board = pb.Pedalboard([
                pb.HighpassFilter(cutoff_frequency_hz=100.0),
                pb.PeakFilter(cutoff_frequency_hz=3000.0, gain_db=3.0, q=1.0),
                pb.PeakFilter(cutoff_frequency_hz=8000.0, gain_db=2.0, q=0.7),
                pb.HighShelfFilter(cutoff_frequency_hz=10000.0, gain_db=2.0),
            ])
        else:
            return audio

        if audio.ndim == 1:
            audio_2d = audio.reshape(1, -1)
        else:
            audio_2d = audio

        processed = board(audio_2d, sr)
        return processed.flatten() if audio.ndim == 1 else processed

    except ImportError:
        logger.warning("Pedalboard not installed for AutoEQ")
        return audio


def normalize_volume(
    audio: np.ndarray,
    sr: int,
    target_lufs: float = -16.0,
) -> np.ndarray:
    """
    Normalize audio volume using EBU R128 loudness standard.
    target_lufs: -16 LUFS is standard for podcasts.
    """
    try:
        import pyloudnorm as pyln

        meter = pyln.Meter(sr)
        current_loudness = meter.integrated_loudness(audio)

        if np.isinf(current_loudness) or np.isnan(current_loudness):
            logger.warning("Cannot measure loudness (silent audio?)")
            return audio

        # Normalize to target
        normalized = pyln.normalize.loudness(audio, current_loudness, target_lufs)

        # Prevent clipping
        peak = np.max(np.abs(normalized))
        if peak > 1.0:
            normalized = normalized / peak * 0.99

        logger.info(f"Normalized: {current_loudness:.1f} LUFS -> {target_lufs:.1f} LUFS")
        return normalized

    except ImportError:
        logger.warning("pyloudnorm not installed. Using peak normalization.")
        return _peak_normalize(audio, target_db=-1.0)


def _peak_normalize(audio: np.ndarray, target_db: float = -1.0) -> np.ndarray:
    """Simple peak normalization fallback."""
    target_amp = 10 ** (target_db / 20)
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak * target_amp
    return audio


def keep_music(
    audio: np.ndarray,
    sr: int,
    process_vocals_fn=None,
) -> np.ndarray:
    """
    Separate vocals from music using Demucs,
    process vocals only, then remix with original music.
    """
    try:
        import torch
        import torchaudio
        from demucs.pretrained import get_model
        from demucs.apply import apply_model

        model = get_model("htdemucs")
        model.eval()

        # Enable Metal GPU acceleration on Apple Silicon
        device = torch.device("mps") if torch.backends.mps.is_available() else torch.device("cpu")
        model.to(device)
        logger.info(f"Demucs on device: {device}")

        # Demucs expects (batch, channels, samples) at model.samplerate
        if audio.ndim == 1:
            audio_tensor = torch.from_numpy(audio).unsqueeze(0).unsqueeze(0).float()
            audio_tensor = audio_tensor.repeat(1, 2, 1)  # mono to stereo
        else:
            audio_tensor = torch.from_numpy(audio).unsqueeze(0).float()

        # Resample if needed
        if sr != model.samplerate:
            audio_tensor = torchaudio.functional.resample(
                audio_tensor.squeeze(0), sr, model.samplerate
            ).unsqueeze(0)

        # Move audio to GPU
        audio_tensor = audio_tensor.to(device)

        # Separate sources (GPU-accelerated)
        with torch.no_grad():
            sources = apply_model(model, audio_tensor, device=device)

        # Move results back to CPU for numpy conversion
        sources = sources.cpu()

        # sources shape: (batch, num_sources, channels, samples)
        # htdemucs sources: drums, bass, other, vocals
        vocals = sources[0, 3].mean(0).numpy()  # mono vocals
        other = sources[0, :3].sum(1).mean(0).numpy()  # everything else

        # Process vocals if a function is provided
        if process_vocals_fn:
            vocals = process_vocals_fn(vocals, model.samplerate)

        # Remix
        result = vocals + other

        # Resample back if needed
        if sr != model.samplerate:
            import librosa
            result = librosa.resample(result, orig_sr=model.samplerate, target_sr=sr)

        return result

    except ImportError:
        logger.error("Demucs not installed. Cannot separate vocals from music.")
        return audio
    except Exception as e:
        logger.error(f"Music separation failed: {e}")
        return audio
