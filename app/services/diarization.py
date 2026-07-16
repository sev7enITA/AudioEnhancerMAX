"""
AudioEnhancerMAX by Fd - Speaker Diarization Service
Identifies who speaks when in multi-speaker recordings.
Optimized for Apple Silicon M3 MAX via MPS backend.
"""
import numpy as np
from typing import List, Optional
from pathlib import Path
import tempfile
import logging
import soundfile as sf

logger = logging.getLogger(__name__)

_diarization_pipeline = None


def _temporary_wav_path() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        return Path(tmp.name)


def _init_diarization():
    """Initialize speaker diarization pipeline."""
    global _diarization_pipeline
    if _diarization_pipeline is not None:
        return

    try:
        from pyannote.audio import Pipeline
        import torch

        # Use MPS (Apple Silicon Metal) if available
        device = "mps" if torch.backends.mps.is_available() else "cpu"

        _diarization_pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=None  # Will use cached model or local
        )

        if device == "mps":
            _diarization_pipeline.to(torch.device(device))
            logger.info("Speaker diarization loaded on Apple Silicon (MPS)")
        else:
            logger.info("Speaker diarization loaded on CPU")

    except ImportError:
        logger.warning(
            "pyannote.audio not installed. Install with: "
            "pip install pyannote.audio"
        )
    except Exception as e:
        logger.warning(f"Diarization init failed: {e}. Using energy-based fallback.")


def diarize(
    audio: np.ndarray,
    sr: int,
    num_speakers: Optional[int] = None,
    min_speakers: int = 1,
    max_speakers: int = 10,
) -> List[dict]:
    """
    Perform speaker diarization.

    Returns list of segments:
    [{"speaker": "SPEAKER_01", "start": 0.5, "end": 3.2}, ...]
    """
    _init_diarization()

    if _diarization_pipeline is not None:
        return _diarize_pyannote(audio, sr, num_speakers, min_speakers, max_speakers)
    else:
        return _diarize_energy_fallback(audio, sr)


def _diarize_pyannote(
    audio: np.ndarray,
    sr: int,
    num_speakers: Optional[int],
    min_speakers: int,
    max_speakers: int,
) -> List[dict]:
    """Diarize using pyannote.audio."""
    temp_path = _temporary_wav_path()
    sf.write(str(temp_path), audio, sr)

    try:
        kwargs = {}
        if num_speakers:
            kwargs["num_speakers"] = num_speakers
        else:
            kwargs["min_speakers"] = min_speakers
            kwargs["max_speakers"] = max_speakers

        diarization = _diarization_pipeline(str(temp_path), **kwargs)

        segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append({
                "speaker": speaker,
                "start": round(turn.start, 3),
                "end": round(turn.end, 3),
                "duration": round(turn.end - turn.start, 3),
            })

        # Assign friendly names
        speaker_map = {}
        speaker_idx = 0
        for seg in segments:
            if seg["speaker"] not in speaker_map:
                speaker_idx += 1
                speaker_map[seg["speaker"]] = f"Speaker {speaker_idx}"
            seg["speaker_label"] = speaker_map[seg["speaker"]]

        logger.info(
            f"Diarization complete: {len(speaker_map)} speakers, "
            f"{len(segments)} segments"
        )
        return segments

    finally:
        temp_path.unlink(missing_ok=True)


def _diarize_energy_fallback(
    audio: np.ndarray,
    sr: int,
) -> List[dict]:
    """
    Simple energy-based speaker change detection fallback.
    Not as accurate as pyannote but works without extra dependencies.
    """
    import librosa

    frame_length = int(sr * 0.05)  # 50ms frames
    hop_length = int(sr * 0.025)  # 25ms hop

    # Extract features
    mfcc = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=13, hop_length=hop_length)
    rms = librosa.feature.rms(y=audio, frame_length=frame_length, hop_length=hop_length)[0]

    # Detect speaker changes via MFCC distance
    segments = []
    min_segment_frames = int(2.0 * sr / hop_length)  # Min 2 seconds per segment

    # Simple clustering based on MFCC features
    from scipy.spatial.distance import cosine

    current_speaker = 0
    seg_start = 0
    prev_features = mfcc[:, :min_segment_frames].mean(axis=1)

    for i in range(min_segment_frames, mfcc.shape[1], min_segment_frames):
        end_idx = min(i + min_segment_frames, mfcc.shape[1])
        current_features = mfcc[:, i:end_idx].mean(axis=1)

        dist = cosine(prev_features, current_features)

        if dist > 0.3:  # Speaker change threshold
            segments.append({
                "speaker": f"SPEAKER_{current_speaker:02d}",
                "speaker_label": f"Speaker {current_speaker + 1}",
                "start": round(seg_start * hop_length / sr, 3),
                "end": round(i * hop_length / sr, 3),
                "duration": round((i - seg_start) * hop_length / sr, 3),
            })
            seg_start = i
            current_speaker = (current_speaker + 1) % 2  # Toggle between 2 speakers

        prev_features = current_features

    # Final segment
    segments.append({
        "speaker": f"SPEAKER_{current_speaker:02d}",
        "speaker_label": f"Speaker {current_speaker + 1}",
        "start": round(seg_start * hop_length / sr, 3),
        "end": round(len(audio) / sr, 3),
        "duration": round((mfcc.shape[1] - seg_start) * hop_length / sr, 3),
    })

    return segments


def get_speaker_stats(segments: List[dict]) -> dict:
    """Calculate per-speaker statistics."""
    stats = {}
    for seg in segments:
        speaker = seg.get("speaker_label", seg["speaker"])
        if speaker not in stats:
            stats[speaker] = {"total_duration": 0, "segment_count": 0}
        stats[speaker]["total_duration"] += seg["duration"]
        stats[speaker]["segment_count"] += 1

    total = sum(s["total_duration"] for s in stats.values())
    for speaker, data in stats.items():
        data["percentage"] = round(data["total_duration"] / total * 100, 1) if total > 0 else 0
        data["total_duration"] = round(data["total_duration"], 1)

    return stats
