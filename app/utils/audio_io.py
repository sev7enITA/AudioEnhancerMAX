"""
AudioEnhancerMAX by Fd - Audio I/O Utilities
Handles loading, converting, and saving audio in multiple formats.
"""
import os
import uuid
import subprocess
import tempfile
from pathlib import Path
from typing import Tuple, Optional

import numpy as np
import soundfile as sf
import librosa

# Ensure Homebrew binaries (ffmpeg, ffprobe) are on PATH for Apple Silicon
_homebrew_bin = "/opt/homebrew/bin"
if _homebrew_bin not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _homebrew_bin + ":" + os.environ.get("PATH", "")

from app.config import UPLOAD_DIR, OUTPUT_DIR, ALLOWED_EXTENSIONS, HIGH_QUALITY_SAMPLE_RATE


def generate_file_id() -> str:
    """Generate a unique file ID."""
    return str(uuid.uuid4())[:12]


def get_upload_path(file_id: str, ext: str = ".wav") -> Path:
    """Get the upload path for a file ID."""
    return UPLOAD_DIR / f"{file_id}{ext}"


def get_output_path(file_id: str, suffix: str = "_processed", ext: str = ".wav") -> Path:
    """Get the output path for a processed file."""
    return OUTPUT_DIR / f"{file_id}{suffix}{ext}"


def validate_extension(filename: str) -> bool:
    """Check if the file extension is allowed."""
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_EXTENSIONS


def extract_audio_from_video(video_path: Path, output_path: Path) -> Path:
    """Extract audio track from MP4/video files using FFmpeg."""
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn",  # no video
        "-acodec", "pcm_s16le",
        "-ar", str(HIGH_QUALITY_SAMPLE_RATE),
        "-ac", "1",  # mono
        str(output_path)
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path


def load_audio(file_path: Path, sr: Optional[int] = None, mono: bool = True) -> Tuple[np.ndarray, int]:
    """
    Load audio file to numpy array.
    Handles MP3, WAV, FLAC, OGG, MP4 (extracts audio).
    Returns (audio_data, sample_rate).
    """
    file_path = Path(file_path)
    ext = file_path.suffix.lower()

    # Handle video files - extract audio first
    if ext in {".mp4", ".m4a", ".avi", ".mkv", ".mov"}:
        wav_path = file_path.with_suffix(".wav")
        extract_audio_from_video(file_path, wav_path)
        file_path = wav_path

    # Load with librosa (handles mp3, wav, flac, ogg)
    y, sr_loaded = librosa.load(str(file_path), sr=sr, mono=mono)

    return y, sr_loaded


def save_audio(
    audio: np.ndarray,
    sr: int,
    output_path: Path,
    format: str = "wav",
    bitrate: str = "320k"
) -> Path:
    """
    Save audio array to file.
    Supports WAV, MP3, FLAC.
    """
    output_path = Path(output_path)

    if format == "wav":
        sf.write(str(output_path), audio, sr, subtype="PCM_24")

    elif format == "mp3":
        # Save as temp WAV first, then convert with FFmpeg
        temp_wav = output_path.with_suffix(".tmp.wav")
        sf.write(str(temp_wav), audio, sr, subtype="PCM_24")

        cmd = [
            "ffmpeg", "-y", "-i", str(temp_wav),
            "-codec:a", "libmp3lame",
            "-b:a", bitrate,
            str(output_path)
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        temp_wav.unlink(missing_ok=True)

    elif format == "flac":
        sf.write(str(output_path), audio, sr, subtype="PCM_24")

    return output_path


def get_audio_info(file_path: Path) -> dict:
    """Get audio file metadata."""
    file_path = Path(file_path)
    ext = file_path.suffix.lower()

    # For video files, probe with ffmpeg
    if ext in {".mp4", ".m4a", ".avi", ".mkv", ".mov"}:
        try:
            cmd = [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_streams", "-show_format", str(file_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            import json
            probe = json.loads(result.stdout)
            audio_stream = next(
                (s for s in probe.get("streams", []) if s.get("codec_type") == "audio"),
                {}
            )
            fmt = probe.get("format", {})
            return {
                "duration": float(fmt.get("duration", 0)),
                "sample_rate": int(audio_stream.get("sample_rate", 44100)),
                "channels": int(audio_stream.get("channels", 1)),
                "bitrate": int(fmt.get("bit_rate", 0)) // 1000,
                "format": ext.lstrip("."),
            }
        except Exception:
            pass

    # For audio files
    try:
        info = sf.info(str(file_path))
        return {
            "duration": info.duration,
            "sample_rate": info.samplerate,
            "channels": info.channels,
            "bitrate": None,
            "format": info.format,
        }
    except Exception:
        # Fallback with librosa
        y, sr = librosa.load(str(file_path), sr=None, mono=False)
        duration = librosa.get_duration(y=y, sr=sr)
        channels = 1 if y.ndim == 1 else y.shape[0]
        return {
            "duration": duration,
            "sample_rate": sr,
            "channels": channels,
            "bitrate": None,
            "format": ext.lstrip("."),
        }


def generate_waveform_data(audio: np.ndarray, num_points: int = 1000) -> list:
    """Generate downsampled waveform data for visualization."""
    if len(audio) == 0:
        return []

    # Downsample for visualization
    chunk_size = max(1, len(audio) // num_points)
    waveform = []

    for i in range(0, len(audio), chunk_size):
        chunk = audio[i:i + chunk_size]
        waveform.append(float(np.max(np.abs(chunk))))

    return waveform[:num_points]
