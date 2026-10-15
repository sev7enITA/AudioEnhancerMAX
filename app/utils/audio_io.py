"""
AudioEnhancerMAX by Fd - Audio I/O Utilities
Handles loading, converting, and saving audio in multiple formats.
"""
import uuid
from fractions import Fraction
from pathlib import Path
from typing import Tuple, Optional

import numpy as np
import soundfile as sf

from app.config import UPLOAD_DIR, OUTPUT_DIR, ALLOWED_EXTENSIONS, HIGH_QUALITY_SAMPLE_RATE
from app.utils.signal_processing import resample_audio


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
    """Extract an audio track with the bundled PyAV/FFmpeg libraries."""
    audio, sample_rate = _load_with_pyav(
        Path(video_path),
        sr=HIGH_QUALITY_SAMPLE_RATE,
        mono=True,
    )
    sf.write(str(output_path), audio, sample_rate, subtype="PCM_24")
    return output_path


def _load_with_pyav(
    file_path: Path,
    sr: Optional[int] = None,
    mono: bool = True,
) -> Tuple[np.ndarray, int]:
    """Decode media using PyAV without invoking an external executable."""
    import av

    with av.open(str(file_path), mode="r") as container:
        stream = next((item for item in container.streams if item.type == "audio"), None)
        if stream is None:
            raise ValueError(f"No audio stream found in {file_path.name}")

        source_rate = int(stream.codec_context.sample_rate or HIGH_QUALITY_SAMPLE_RATE)
        target_rate = int(sr or source_rate)
        source_layout = stream.codec_context.layout
        source_channels = len(source_layout.channels) if source_layout else 1
        target_layout = "mono" if mono else ("stereo" if source_channels > 1 else "mono")
        resampler = av.AudioResampler(format="fltp", layout=target_layout, rate=target_rate)
        chunks: list[np.ndarray] = []

        def append_frames(frames) -> None:
            if frames is None:
                return
            if not isinstance(frames, list):
                frames = [frames]
            for resampled in frames:
                array = resampled.to_ndarray().astype(np.float32, copy=False)
                if array.ndim == 1:
                    array = array.reshape(1, -1)
                chunks.append(array)

        for frame in container.decode(stream):
            append_frames(resampler.resample(frame))
        append_frames(resampler.resample(None))

    if not chunks:
        raise ValueError(f"No decodable audio samples found in {file_path.name}")

    planar = np.concatenate(chunks, axis=1)
    if mono:
        return planar[0], target_rate
    return planar, target_rate


def _as_planar_float32(audio: np.ndarray) -> np.ndarray:
    """Normalize mono/interleaved/planar arrays for PyAV encoders."""
    array = np.asarray(audio, dtype=np.float32)
    if array.ndim == 1:
        return array.reshape(1, -1)
    if array.ndim != 2:
        raise ValueError("Audio must be a mono or stereo array")
    if array.shape[0] <= 8 and array.shape[0] < array.shape[1]:
        return array
    return array.T


def _save_mp3_with_pyav(audio: np.ndarray, sr: int, output_path: Path, bitrate: str) -> None:
    """Encode MP3 with the FFmpeg libraries bundled in the PyAV wheel."""
    import av

    planar = np.ascontiguousarray(_as_planar_float32(audio))
    channels = planar.shape[0]
    if channels not in {1, 2}:
        planar = planar[:2]
        channels = planar.shape[0]
    layout = "mono" if channels == 1 else "stereo"
    bitrate_kbps = int(str(bitrate).lower().removesuffix("k"))

    with av.open(str(output_path), mode="w", format="mp3") as container:
        stream = container.add_stream("libmp3lame", rate=int(sr))
        stream.bit_rate = bitrate_kbps * 1000
        stream.layout = layout
        frame_size = 1152
        for offset in range(0, planar.shape[1], frame_size):
            chunk = np.ascontiguousarray(planar[:, offset:offset + frame_size])
            frame = av.AudioFrame.from_ndarray(chunk, format="fltp", layout=layout)
            frame.sample_rate = int(sr)
            frame.pts = offset
            frame.time_base = Fraction(1, int(sr))
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode(None):
            container.mux(packet)


def load_audio(file_path: Path, sr: Optional[int] = None, mono: bool = True) -> Tuple[np.ndarray, int]:
    """
    Load audio file to numpy array.
    Handles MP3, WAV, FLAC, OGG, MP4 (extracts audio).
    Returns (audio_data, sample_rate).
    """
    file_path = Path(file_path)
    ext = file_path.suffix.lower()

    try:
        return _load_with_pyav(file_path, sr=sr, mono=mono)
    except Exception:
        # libsndfile remains a self-contained fallback for WAV/FLAC/OGG.
        if ext in {".wav", ".flac", ".ogg"}:
            y, sr_loaded = sf.read(str(file_path), dtype="float32", always_2d=True)
            y = y.T
            if mono:
                y = np.mean(y, axis=0)
            if sr is not None and int(sr) != int(sr_loaded):
                y = resample_audio(y, int(sr_loaded), int(sr))
                sr_loaded = int(sr)
            return np.asarray(y, dtype=np.float32), int(sr_loaded)
        raise


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
        _save_mp3_with_pyav(audio, sr, output_path, bitrate)

    elif format == "flac":
        sf.write(str(output_path), audio, sr, subtype="PCM_24")

    return output_path


def get_audio_info(file_path: Path) -> dict:
    """Get audio file metadata."""
    file_path = Path(file_path)
    ext = file_path.suffix.lower()

    try:
        import av

        with av.open(str(file_path), mode="r") as container:
            stream = next((item for item in container.streams if item.type == "audio"), None)
            if stream is not None:
                if stream.duration is not None and stream.time_base is not None:
                    duration = float(stream.duration * stream.time_base)
                elif container.duration is not None:
                    duration = float(container.duration / av.time_base)
                else:
                    duration = 0.0
                layout = stream.codec_context.layout
                channels = len(layout.channels) if layout else 1
                bitrate = stream.bit_rate or container.bit_rate or 0
                return {
                    "duration": duration,
                    "sample_rate": int(stream.codec_context.sample_rate or 44100),
                    "channels": channels,
                    "bitrate": int(bitrate) // 1000 if bitrate else None,
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
    except Exception as exc:
        raise ValueError(f"Unable to read audio metadata from {file_path.name}") from exc


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
