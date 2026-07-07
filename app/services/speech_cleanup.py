"""
AudioEnhancerMAX by Fd — Speech Cleanup Service
Handles filler words, breaths, mouth sounds, hesitations, stuttering.
"""
import numpy as np
from typing import List, Tuple, Optional
import logging
import re

logger = logging.getLogger(__name__)

# Lazy-loaded Whisper model
_whisper_model = None


def _init_whisper():
    """Lazily initialize faster-whisper model."""
    global _whisper_model
    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel
            _whisper_model = WhisperModel(
                "large-v3",
                device="auto",
                compute_type="auto"
            )
            logger.info("Whisper model loaded for speech cleanup")
        except ImportError:
            logger.warning("faster-whisper not installed. Trying regular whisper.")
            try:
                import whisper
                _whisper_model = whisper.load_model("base")
                logger.info("OpenAI Whisper model loaded (fallback)")
            except ImportError:
                logger.error("No whisper implementation available")
        except Exception as e:
            logger.error(f"Whisper init failed: {e}")


def _get_word_timestamps(
    audio: np.ndarray,
    sr: int,
    language: Optional[str] = None
) -> List[dict]:
    """Get word-level timestamps from audio using Whisper."""
    _init_whisper()

    if _whisper_model is None:
        return []

    try:
        # Save temp file for Whisper
        import tempfile
        import soundfile as sf
        from pathlib import Path

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            temp_path = Path(tmp.name)
        sf.write(str(temp_path), audio, sr)

        words = []

        # Try faster-whisper first
        try:
            from faster_whisper import WhisperModel
            if isinstance(_whisper_model, WhisperModel):
                segments, info = _whisper_model.transcribe(
                    str(temp_path),
                    language=language,
                    word_timestamps=True,
                    vad_filter=True,
                )

                for segment in segments:
                    if segment.words:
                        for word in segment.words:
                            words.append({
                                "word": word.word.strip().lower(),
                                "start": word.start,
                                "end": word.end,
                                "probability": word.probability,
                            })
        except (ImportError, AttributeError):
            # Fallback to OpenAI whisper
            result = _whisper_model.transcribe(
                str(temp_path),
                language=language,
                word_timestamps=True,
            )
            for segment in result.get("segments", []):
                for word_info in segment.get("words", []):
                    words.append({
                        "word": word_info["word"].strip().lower(),
                        "start": word_info["start"],
                        "end": word_info["end"],
                        "probability": word_info.get("probability", 0),
                    })

        return words

    except Exception as e:
        logger.error(f"Word timestamp extraction failed: {e}")
        return []
    finally:
        if "temp_path" in locals():
            temp_path.unlink(missing_ok=True)


# ── Filler Word Removal ──────────────────────────────────

DEFAULT_FILLER_WORDS = {
    # English
    "uh", "uhm", "um", "uhh", "umm", "hmm", "hm", "mm",
    "er", "err", "ah", "ahh", "like", "you know",
    # Italian
    "ehm", "eh", "beh", "mah", "boh",
}


def remove_filler_words(
    audio: np.ndarray,
    sr: int,
    custom_fillers: Optional[List[str]] = None,
    language: Optional[str] = None,
    crossfade_ms: int = 30,
) -> np.ndarray:
    """
    Remove filler words (uhm, uh, eh, etc.) by detecting them with Whisper
    and cutting them out with smooth crossfades.
    """
    fillers = DEFAULT_FILLER_WORDS.copy()
    if custom_fillers:
        fillers.update(w.lower() for w in custom_fillers)

    words = _get_word_timestamps(audio, sr, language)

    if not words:
        logger.warning("No word timestamps available for filler detection")
        return audio

    # Find filler word segments
    segments_to_remove = []
    for w in words:
        if w["word"] in fillers:
            start_sample = int(w["start"] * sr)
            end_sample = int(w["end"] * sr)
            segments_to_remove.append((start_sample, end_sample))
            logger.debug(f"Filler detected: '{w['word']}' at {w['start']:.2f}s")

    if not segments_to_remove:
        return audio

    return _remove_segments(audio, sr, segments_to_remove, crossfade_ms)


# ── Breath Removal ──────────────────────────────────

def detect_breaths(
    audio: np.ndarray,
    sr: int,
    sensitivity: float = 0.8
) -> List[Tuple[int, int]]:
    """
    Detect breath sounds using spectral analysis.
    Breaths are characterized by:
    - Low energy bursts (lower than speech)
    - Frequency content in 100-2000 Hz range
    - Short duration (typically 200-800ms)
    """
    import librosa

    frame_length = int(sr * 0.025)
    hop_length = int(sr * 0.010)

    # Compute spectral features
    rms = librosa.feature.rms(y=audio, frame_length=frame_length, hop_length=hop_length)[0]
    spectral_centroid = librosa.feature.spectral_centroid(
        y=audio, sr=sr, n_fft=frame_length, hop_length=hop_length
    )[0]
    zcr = librosa.feature.zero_crossing_rate(
        y=audio, frame_length=frame_length, hop_length=hop_length
    )[0]

    # Breath characteristics:
    # - Medium-low RMS (not silent, not loud speech)
    # - Low spectral centroid (100-2000Hz)
    # - Higher zero-crossing rate than silence
    rms_mean = np.mean(rms[rms > 0]) if np.any(rms > 0) else 1e-6
    rms_threshold_low = rms_mean * (0.05 * (2 - sensitivity))
    rms_threshold_high = rms_mean * (0.4 + 0.2 * (1 - sensitivity))

    breath_frames = (
        (rms > rms_threshold_low) &
        (rms < rms_threshold_high) &
        (spectral_centroid < 2000) &
        (spectral_centroid > 100) &
        (zcr > 0.02)
    )

    # Convert frames to segments
    breaths = []
    in_breath = False
    start_frame = 0

    for i, is_breath in enumerate(breath_frames):
        if is_breath and not in_breath:
            start_frame = i
            in_breath = True
        elif not is_breath and in_breath:
            # Check duration (200-800ms typical for breaths)
            duration_ms = (i - start_frame) * hop_length / sr * 1000
            if 150 <= duration_ms <= 1200:
                start_sample = start_frame * hop_length
                end_sample = i * hop_length
                breaths.append((start_sample, end_sample))
            in_breath = False

    return breaths


def remove_breaths(
    audio: np.ndarray,
    sr: int,
    strength: float = 0.8,
    crossfade_ms: int = 15,
) -> np.ndarray:
    """
    Remove or attenuate breath sounds.
    strength=1.0: fully remove, strength=0.5: reduce by 50%
    """
    breaths = detect_breaths(audio, sr, sensitivity=strength)

    if not breaths:
        return audio

    result = audio.copy()
    fade_samples = int(crossfade_ms / 1000 * sr)

    for start, end in breaths:
        start = max(0, start)
        end = min(len(result), end)

        # v2.0: Never fully mute breaths — cap attenuation at 80%
        # and use longer fades (30ms) for smoother transitions.
        # Full muting sounds unnatural (creates "holes" in audio).
        effective_strength = min(strength, 0.8)
        fade_len = max(fade_samples, int(0.030 * sr))  # v2.0: minimum 30ms fades

        if end - start > fade_len * 2:
            # Attenuate with smooth fades (never fully zero)
            result[start:start + fade_len] *= np.linspace(1, 1 - effective_strength, fade_len)
            result[start + fade_len:end - fade_len] *= (1 - effective_strength)
            result[end - fade_len:end] *= np.linspace(1 - effective_strength, 1, fade_len)
        else:
            # Short breath: gentle attenuation
            result[start:end] *= (1 - effective_strength * 0.5)

    logger.info(f"Processed {len(breaths)} breath segments (strength={strength}, effective={effective_strength:.2f})")
    return result


# ── Mouth Sound / Click Removal ──────────────────────────────────

def remove_mouth_sounds(
    audio: np.ndarray,
    sr: int,
    sensitivity: float = 0.5,
) -> np.ndarray:
    """
    Remove mouth clicks and lip smacking sounds.
    Uses spectral analysis to detect short, high-frequency transients.
    """
    import librosa

    frame_length = int(sr * 0.005)  # 5ms frames for click detection
    hop_length = int(sr * 0.002)  # 2ms hop

    # Compute spectral flux (change in spectrum between frames)
    S = np.abs(librosa.stft(audio, n_fft=frame_length, hop_length=hop_length))
    spectral_flux = np.sum(np.diff(S, axis=1) ** 2, axis=0)

    # v2.0: Raised base threshold from 3 to 4 to reduce false positives.
    # Too many false positives = "patchy" audio with interpolation artifacts.
    flux_threshold = np.mean(spectral_flux) + np.std(spectral_flux) * (4 - sensitivity * 2)

    click_frames = spectral_flux > flux_threshold

    result = audio.copy()
    repair_samples = int(sr * 0.003)  # 3ms repair window

    for i, is_click in enumerate(click_frames):
        if is_click:
            center = i * hop_length
            start = max(0, center - repair_samples)
            end = min(len(result), center + repair_samples)

            # v2.0: Use local average interpolation (smoother than linear)
            # Linear interpolation between endpoints can create audible discontinuities
            if start > repair_samples and end < len(result) - repair_samples:
                # Use surrounding audio average for smoother repair
                before_avg = np.mean(result[max(0, start - repair_samples):start])
                after_avg = np.mean(result[end:min(len(result), end + repair_samples)])
                result[start:end] = np.linspace(before_avg, after_avg, end - start)
            elif start > 0 and end < len(result):
                result[start:end] = np.linspace(result[start], result[end - 1], end - start)

    return result


# ── Hesitation & Stuttering Removal ──────────────────────────────────

def eliminate_hesitations(
    audio: np.ndarray,
    sr: int,
    language: Optional[str] = None,
    crossfade_ms: int = 30,
) -> np.ndarray:
    """
    Remove hesitations (unnatural pauses within sentences).
    Detects gaps between words that are longer than normal but shorter
    than sentence breaks.
    """
    words = _get_word_timestamps(audio, sr, language)

    if len(words) < 2:
        return audio

    segments_to_shorten = []

    for i in range(len(words) - 1):
        gap_start = words[i]["end"]
        gap_end = words[i + 1]["start"]
        gap_duration = gap_end - gap_start

        # Hesitation: gap between 0.5s and 2.0s
        if 0.5 < gap_duration < 2.0:
            # Keep a natural 0.15s gap
            keep = 0.15
            remove_start = int((gap_start + keep) * sr)
            remove_end = int(gap_end * sr)
            if remove_end > remove_start:
                segments_to_shorten.append((remove_start, remove_end))

    if not segments_to_shorten:
        return audio

    return _remove_segments(audio, sr, segments_to_shorten, crossfade_ms)


def remove_stuttering(
    audio: np.ndarray,
    sr: int,
    language: Optional[str] = None,
    crossfade_ms: int = 30,
) -> np.ndarray:
    """
    Remove stuttering (repeated words or syllable repetitions).
    """
    words = _get_word_timestamps(audio, sr, language)

    if len(words) < 2:
        return audio

    segments_to_remove = []
    i = 0

    while i < len(words) - 1:
        # Check for word repetition
        current = words[i]["word"].strip(".,!?;:")
        next_word = words[i + 1]["word"].strip(".,!?;:")

        if current == next_word and len(current) > 1:
            # Remove the first occurrence (keep the last, cleaner one)
            start_sample = int(words[i]["start"] * sr)
            end_sample = int(words[i]["end"] * sr)
            segments_to_remove.append((start_sample, end_sample))
            logger.debug(f"Stutter detected: '{current}' repeated at {words[i]['start']:.2f}s")
            i += 2
        else:
            i += 1

    if not segments_to_remove:
        return audio

    return _remove_segments(audio, sr, segments_to_remove, crossfade_ms)


# ── Utilities ──────────────────────────────────

def _remove_segments(
    audio: np.ndarray,
    sr: int,
    segments: List[Tuple[int, int]],
    crossfade_ms: int = 30,
) -> np.ndarray:
    """Remove audio segments with smooth crossfades."""
    if not segments:
        return audio

    # Sort segments by start position
    segments = sorted(segments, key=lambda x: x[0])

    # Merge overlapping segments
    merged = [segments[0]]
    for start, end in segments[1:]:
        if start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    crossfade_samples = int(crossfade_ms / 1000 * sr)

    # Build output
    result_parts = []
    prev_end = 0

    for start, end in merged:
        start = max(0, start)
        end = min(len(audio), end)

        # Keep audio before this cut
        segment = audio[prev_end:start].copy()

        # Apply fade out at end
        if len(segment) > crossfade_samples:
            segment[-crossfade_samples:] *= np.linspace(1, 0.3, crossfade_samples)

        result_parts.append(segment)
        prev_end = end

    # Add remaining audio
    remaining = audio[prev_end:].copy()
    if len(remaining) > crossfade_samples:
        remaining[:crossfade_samples] *= np.linspace(0.3, 1, crossfade_samples)
    result_parts.append(remaining)

    result = np.concatenate(result_parts)
    removed_duration = sum((e - s) for s, e in merged) / sr
    logger.info(f"Removed {len(merged)} segments ({removed_duration:.1f}s)")

    return result
