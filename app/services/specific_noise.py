"""
AudioEnhancerMAX by Fd - Specific Noise Removal Service
Wind, buzzing, static, reverb/echo removal.
"""
import numpy as np
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def remove_wind_noise(
    audio: np.ndarray,
    sr: int,
    cutoff_hz: float = 200.0,
    strength: float = 0.8,
) -> np.ndarray:
    """
    Remove wind noise using aggressive high-pass filtering
    combined with spectral gating for low-frequency bursts.
    """
    try:
        import pedalboard as pb

        # Wind noise is primarily below 200-300Hz
        # Use a steep high-pass filter
        board = pb.Pedalboard([
            pb.HighpassFilter(cutoff_frequency_hz=cutoff_hz * strength),
        ])

        if audio.ndim == 1:
            audio_2d = audio.reshape(1, -1)
        else:
            audio_2d = audio

        filtered = board(audio_2d, sr).flatten() if audio.ndim == 1 else board(audio_2d, sr)

        # Blend based on strength
        result = audio * (1 - strength) + filtered * strength

        # Also apply gentle spectral gating for wind gusts
        # v2.0: Reduced prop_decrease (was strength*0.5, now strength*0.25)
        # to prevent metallic artifacts from double-processing
        try:
            import noisereduce as nr
            result = nr.reduce_noise(
                y=result, sr=sr,
                prop_decrease=strength * 0.25,
                freq_mask_smooth_hz=400,
                time_mask_smooth_ms=80,
            )
        except ImportError:
            pass

        return result

    except ImportError:
        # Fallback with scipy
        from scipy import signal
        sos = signal.butter(6, cutoff_hz * strength, btype='high', fs=sr, output='sos')
        return signal.sosfilt(sos, audio)


def remove_buzzing_noise(
    audio: np.ndarray,
    sr: int,
    base_freq_hz: float = 50.0,
    num_harmonics: int = 5,
    q_factor: float = 30.0,
) -> np.ndarray:
    """
    Remove electrical buzzing/hum (50Hz or 60Hz and harmonics).
    Uses notch filters at the fundamental and harmonic frequencies.
    """
    try:
        import pedalboard as pb

        filters = []
        for h in range(1, num_harmonics + 1):
            freq = base_freq_hz * h
            if freq < sr / 2:  # Below Nyquist
                filters.append(
                    pb.PeakFilter(
                        cutoff_frequency_hz=freq,
                        gain_db=-30.0,
                        q=q_factor,
                    )
                )

        board = pb.Pedalboard(filters)

        if audio.ndim == 1:
            audio_2d = audio.reshape(1, -1)
        else:
            audio_2d = audio

        processed = board(audio_2d, sr)
        return processed.flatten() if audio.ndim == 1 else processed

    except ImportError:
        # Fallback with scipy notch filters
        from scipy import signal
        result = audio.copy()

        for h in range(1, num_harmonics + 1):
            freq = base_freq_hz * h
            if freq < sr / 2:
                b, a = signal.iirnotch(freq, q_factor, sr)
                result = signal.filtfilt(b, a, result)

        return result


def remove_static_noise(
    audio: np.ndarray,
    sr: int,
    strength: float = 0.7,
) -> np.ndarray:
    """
    Remove static/white noise using spectral gating.
    Best for: microphone hiss, preamp noise, constant static.
    """
    try:
        import noisereduce as nr

        # v2.0: Cap prop_decrease at 0.85 (was strength * 1.3 -> could reach 1.0+)
        # Add time/freq smoothing to prevent metallic artifacts
        reduced = nr.reduce_noise(
            y=audio,
            sr=sr,
            stationary=True,
            prop_decrease=min(0.85, strength * 0.85),
            n_std_thresh_stationary=max(1.5, 2.0 - (strength * 0.3)),
            freq_mask_smooth_hz=600,
            time_mask_smooth_ms=80,
        )

        # v2.0: Wet/dry mix to preserve natural character
        wet = min(0.85, strength)
        result = reduced * wet + audio * (1.0 - wet)

        return result

    except ImportError:
        logger.warning("noisereduce not installed for static removal")
        return audio


def remove_reverb_echo(
    audio: np.ndarray,
    sr: int,
    strength: float = 0.7,
) -> np.ndarray:
    """
    Reduce reverb and echo using spectral processing.
    Method: spectral subtraction of the estimated reverb tail.
    """
    import librosa

    # STFT analysis
    n_fft = 2048
    hop_length = 512
    S = librosa.stft(audio, n_fft=n_fft, hop_length=hop_length)
    magnitude = np.abs(S)
    phase = np.angle(S)

    # Estimate reverb: the reverb tail causes energy to decay slowly
    # We look at the temporal decay of each frequency bin
    # and subtract the estimated reverb

    # Method: median filtering across time to estimate direct sound
    from scipy.ndimage import median_filter

    # Median filter in time dimension - removes transient reverb tails
    kernel_size = int(0.1 * sr / hop_length)  # ~100ms window
    kernel_size = max(3, kernel_size | 1)  # Ensure odd

    direct_estimate = median_filter(magnitude, size=(1, kernel_size))

    # Spectral subtraction
    # v2.0: Reduced over-subtraction factor (was strength*2.0, now strength*1.2)
    # Raised floor from 0.1 to 0.25 to preserve more harmonic detail
    alpha = strength * 1.2  # Over-subtraction factor
    reverb_estimate = magnitude - direct_estimate
    reverb_estimate = np.maximum(reverb_estimate, 0)

    # Subtract reverb estimate
    clean_magnitude = magnitude - alpha * reverb_estimate
    clean_magnitude = np.maximum(clean_magnitude, magnitude * 0.25)  # Floor to prevent artifacts

    # Reconstruct
    S_clean = clean_magnitude * np.exp(1j * phase)
    result = librosa.istft(S_clean, hop_length=hop_length, length=len(audio))

    # v2.0: Reduced blend factor (was strength*0.7, now strength*0.5)
    # to preserve more of the original signal's natural character
    result = audio * (1 - strength * 0.5) + result * (strength * 0.5)

    # Additionally try pedalboard if available
    try:
        import pedalboard as pb

        # De-ess and smooth remaining artifacts
        board = pb.Pedalboard([
            pb.NoiseGate(
                threshold_db=-30.0,
                ratio=2.0,
                attack_ms=5.0,
                release_ms=50.0,
            ),
        ])

        if result.ndim == 1:
            result_2d = result.reshape(1, -1)
        else:
            result_2d = result

        result = board(result_2d, sr)
        result = result.flatten() if audio.ndim == 1 else result

    except ImportError:
        pass

    return result
