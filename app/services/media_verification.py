"""Local, bounded measurements on a snapshot of the received media."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import BinaryIO

import numpy as np

from app.release import APP_BUILD, APP_VERSION
from app.services.content_credentials import CredentialsError, CredentialsUnavailable, MEDIA_TYPES, inspect_stream

SCHEMA = "audioenhancermax.media-verification.v1"
SAMPLE_RATE = 48_000
PREVIEW_SECONDS = 30
DECODE_FRAME_LIMIT = 16_384
DEMUXERS = {
    ".wav": "wav", ".mp3": "mp3", ".flac": "flac",
    ".m4a": "mov", ".mp4": "mov", ".mov": "mov",
}
CODE_PATTERN = re.compile(r"[a-zA-Z0-9_.-]{1,100}")


def _matches_format(stream: BinaryIO, suffix: str) -> bool:
    header = stream.read(12)
    stream.seek(0)
    if suffix == ".wav":
        return header[:4] in {b"RIFF", b"RIFX", b"RF64"} and header[8:12] == b"WAVE"
    if suffix == ".flac":
        return header.startswith(b"fLaC")
    if suffix == ".mp3":
        return header.startswith(b"ID3") or (len(header) >= 2 and header[0] == 255 and header[1] & 224 == 224)
    return header[4:8] in {b"ftyp", b"moov", b"mdat", b"wide", b"free", b"skip", b"pnot", b"uuid"}


def _deny_external_media(*_args):
    raise OSError("External media references are disabled")


def _sample_audio(stream: BinaryIO, suffix: str) -> tuple[np.ndarray, dict]:
    import av

    stream.seek(0)
    with av.open(
        stream,
        format=DEMUXERS[suffix],
        options={"probesize": "1048576", "analyzeduration": "3000000", "enable_drefs": "0"},
        io_open=_deny_external_media,
    ) as media:
        track = next(iter(media.streams.audio), None)
        if track is None:
            return np.empty(0, dtype=np.float32), {"status": "no_audio_track"}
        codec = track.codec_context
        metadata = {
            "source_codec": codec.name,
            "source_sample_rate_hz": codec.sample_rate or None,
            "source_channels": codec.channels or None,
        }
        # Decode a fixed prefix of the first audio track and no video frames.
        converter = av.AudioResampler(format="fltp", layout="mono", rate=SAMPLE_RATE)
        buffer = np.empty(SAMPLE_RATE * PREVIEW_SECONDS, dtype=np.float32)
        used = 0
        frame_count = 0
        for frame in media.decode(track):
            frame_count += 1
            if frame_count > DECODE_FRAME_LIMIT or frame.samples > SAMPLE_RATE * 2 or len(frame.layout.channels) > 8:
                return np.empty(0, dtype=np.float32), {"status": "decode_limit", **metadata}
            for converted in converter.resample(frame):
                samples = converted.to_ndarray()[0]
                count = min(len(samples), len(buffer) - used)
                buffer[used:used + count] = samples[:count]
                used += count
            if used == len(buffer):
                break
        if used and used < len(buffer):
            for converted in converter.resample(None):
                samples = converted.to_ndarray()[0]
                count = min(len(samples), len(buffer) - used)
                buffer[used:used + count] = samples[:count]
                used += count
        return buffer[:used], metadata


def _measure(samples: np.ndarray) -> dict:
    if not len(samples) or not np.isfinite(samples).all():
        return {"status": "unreadable_audio"}
    magnitude = np.abs(samples)
    peak = float(magnitude.max())
    rms = float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))
    if peak > 32:
        return {"status": "unreadable_audio"}
    envelope = [round(float(section.max()), 4) for section in np.array_split(magnitude, min(64, len(samples)))]
    return {
        "status": "measured",
        "method": "first_audio_track_mono_prefix_v1",
        "sample_rate_hz": SAMPLE_RATE,
        "analyzed_seconds": round(len(samples) / SAMPLE_RATE, 5),
        "preview_limit_seconds": PREVIEW_SECONDS,
        "peak_dbfs": round(20 * np.log10(peak), 2) if peak else None,
        "rms_dbfs": round(20 * np.log10(rms), 2) if rms else None,
        "near_full_scale_percent": round(100 * float(np.mean(magnitude >= 0.999)), 5),
        "waveform_peak": envelope,
    }


def _credential_projection(stream: BinaryIO, suffix: str) -> dict:
    try:
        result = inspect_stream(stream, suffix)
    except CredentialsUnavailable:
        return {"status": "validator_unavailable"}
    except CredentialsError:
        return {"status": "unreadable"}
    for key in ("actions", "failure_codes"):
        values = result.get(key, [])
        result[key] = [value for value in values[:32] if isinstance(value, str) and CODE_PATTERN.fullmatch(value)]
    signer = result.get("signer")
    if isinstance(signer, str):
        result["signer"] = "".join(char for char in signer[:160] if char.isprintable())
    return result


def verify_media(stream: BinaryIO, suffix: str, sha256: str, size_bytes: int, audioseal: bool = False) -> dict:
    """Analyze one private snapshot. Fingerprint is supplied by its streaming writer."""
    import av

    format_matches = _matches_format(stream, suffix)
    credentials = _credential_projection(stream, suffix) if format_matches else {"status": "format_mismatch"}
    try:
        if not format_matches:
            raise ValueError("Unexpected media header")
        samples, metadata = _sample_audio(stream, suffix)
        audio = metadata if "status" in metadata else {**metadata, **_measure(samples)}
    except (av.FFmpegError, OSError, ValueError, OverflowError):
        audio = {"status": "unreadable_audio"}
    report = {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "application": {"version": APP_VERSION, "build": APP_BUILD, "platform": "macos"},
        "asset": {
            "sha256": sha256, "size_bytes": size_bytes,
            "media_type": MEDIA_TYPES[suffix] if format_matches else None,
        },
        "credentials": credentials,
        "audio": audio,
    }
    if audioseal:
        from app.services.audioseal_detector import evaluate

        report["watermark"] = evaluate(samples, SAMPLE_RATE) if audio["status"] == "measured" else {
            "status": "audio_unavailable",
        }
    return report
