"""
AudioEnhancerMAX by Fd - Silence Removal Service
Detects and removes/mutes long silences in audio.
"""
import numpy as np
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)


def detect_silences(
    audio: np.ndarray,
    sr: int,
    threshold_db: float = -40,
    min_duration_ms: int = 1000,
) -> List[Tuple[int, int]]:
    """
    Detect silent segments in audio.
    Returns list of (start_sample, end_sample) tuples.
    """
    import librosa

    # Convert threshold from dB to amplitude
    threshold_amp = librosa.db_to_amplitude(threshold_db)

    # Calculate RMS energy in frames
    frame_length = int(sr * 0.025)  # 25ms frames
    hop_length = int(sr * 0.010)  # 10ms hop

    rms = librosa.feature.rms(
        y=audio, frame_length=frame_length, hop_length=hop_length
    )[0]

    # Find silent frames
    silent_frames = rms < threshold_amp

    # Convert to sample positions and merge adjacent silent frames
    silences = []
    in_silence = False
    start_frame = 0

    for i, is_silent in enumerate(silent_frames):
        if is_silent and not in_silence:
            start_frame = i
            in_silence = True
        elif not is_silent and in_silence:
            end_frame = i
            # Convert frames to samples
            start_sample = start_frame * hop_length
            end_sample = end_frame * hop_length

            # Check minimum duration
            duration_ms = (end_sample - start_sample) / sr * 1000
            if duration_ms >= min_duration_ms:
                silences.append((start_sample, end_sample))

            in_silence = False

    # Handle trailing silence
    if in_silence:
        end_sample = len(audio)
        start_sample = start_frame * hop_length
        duration_ms = (end_sample - start_sample) / sr * 1000
        if duration_ms >= min_duration_ms:
            silences.append((start_sample, end_sample))

    return silences


def remove_long_silences(
    audio: np.ndarray,
    sr: int,
    threshold_db: float = -40,
    min_duration_ms: int = 1000,
    keep_ms: int = 300,
) -> np.ndarray:
    """
    Remove long silences, keeping a short gap for natural flow.
    """
    silences = detect_silences(audio, sr, threshold_db, min_duration_ms)

    if not silences:
        return audio

    keep_samples = int(keep_ms / 1000 * sr)

    # Build output by keeping non-silent segments
    segments = []
    prev_end = 0

    for start, end in silences:
        # Keep audio before silence
        segments.append(audio[prev_end:start])

        # Add a short silence gap for natural flow
        gap = np.zeros(keep_samples)
        segments.append(gap)

        prev_end = end

    # Add remaining audio after last silence
    segments.append(audio[prev_end:])

    result = np.concatenate(segments)
    logger.info(
        f"Removed {len(silences)} silent segments. "
        f"Duration: {len(audio)/sr:.1f}s -> {len(result)/sr:.1f}s"
    )

    return result


def mute_segments(
    audio: np.ndarray,
    sr: int,
    segments: List[Tuple[int, int]],
) -> np.ndarray:
    """
    Mute (replace with silence) specified segments without changing duration.
    """
    result = audio.copy()

    for start, end in segments:
        start = max(0, start)
        end = min(len(audio), end)
        # Apply short fade to avoid clicks
        fade_samples = min(int(sr * 0.005), (end - start) // 4)

        if fade_samples > 0:
            # Fade out
            result[start:start + fade_samples] *= np.linspace(1, 0, fade_samples)
            # Silence middle
            result[start + fade_samples:end - fade_samples] = 0
            # Fade in
            result[end - fade_samples:end] *= np.linspace(0, 1, fade_samples)
        else:
            result[start:end] = 0

    logger.info(f"Muted {len(segments)} segments")
    return result
