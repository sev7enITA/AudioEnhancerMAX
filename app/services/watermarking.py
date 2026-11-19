"""
AudioEnhancerMAX by Fd - Audio Watermarking Service
Embeds and detects invisible watermarks in processed audio files.
"""
import numpy as np
from typing import Optional
import logging
import hashlib
import struct
import re

logger = logging.getLogger(__name__)

# Watermark configuration
WATERMARK_PREFIX = "AEMAX-Fd"
WATERMARK_FREQ_BAND = (18000, 19500)  # Near-ultrasonic, inaudible for most
WATERMARK_BIT_DURATION = 0.02  # 20ms per bit
REVISION_MARK_PREFIX = b"AEMAX4|"
REVISION_MARK_ID = re.compile(rb"[A-Za-z0-9_-]{1,32}")
PCM24_SCALE = 1 << 23


def _revision_mark_payload(identifier: bytes) -> bytes:
    checksum = hashlib.sha256(identifier).hexdigest()[:8].encode("ascii")
    return REVISION_MARK_PREFIX + identifier + b"|" + checksum + b"\0"


def embed_revision_watermark(audio: np.ndarray, identifier: str) -> np.ndarray:
    """Embed a marker in 24-bit PCM without changing duration or sample rate."""
    key = identifier.encode("ascii")
    if not REVISION_MARK_ID.fullmatch(key):
        raise ValueError("Enter 1–32 letters, digits, hyphens or underscores for the watermark.")
    bits = np.unpackbits(np.frombuffer(_revision_mark_payload(key), dtype=np.uint8))
    if len(audio) < len(bits):
        raise ValueError("The edited audio is too short to embed this watermark.")
    result = np.asarray(audio, dtype=np.float32).copy()
    head = np.rint(result[:len(bits)] * PCM24_SCALE)
    samples = np.clip(head, -PCM24_SCALE, PCM24_SCALE - 1).astype(np.int32)
    result[:len(bits)] = ((samples & ~1) | bits).astype(np.float32) / PCM24_SCALE
    return result


def _detect_revision_watermark(audio: np.ndarray) -> Optional[dict]:
    max_bytes = len(REVISION_MARK_PREFIX) + 32 + 1 + 8 + 1
    head = np.rint(audio[:max_bytes * 8] * PCM24_SCALE).astype(np.int32)
    payload = np.packbits((head & 1).astype(np.uint8)).tobytes()
    if not payload.startswith(REVISION_MARK_PREFIX) or b"\0" not in payload:
        return None
    payload = payload.split(b"\0", 1)[0] + b"\0"
    identifier = payload[len(REVISION_MARK_PREFIX):].split(b"|", 1)[0]
    if not REVISION_MARK_ID.fullmatch(identifier) or payload != _revision_mark_payload(identifier):
        return None
    return {"detected": True, "payload": identifier.decode("ascii"), "method": "pcm24-revision"}


def embed_watermark(
    audio: np.ndarray,
    sr: int,
    identifier: str = "",
    strength: float = 0.005,
) -> np.ndarray:
    """
    Embed an invisible watermark in audio using spread-spectrum technique.
    The watermark is embedded in near-ultrasonic frequencies (18-19.5kHz),
    making it inaudible but detectable.
    """
    if sr < 40000:
        # Sample rate too low for ultrasonic watermarking
        # Fall back to sub-audible method
        return _embed_subaudible(audio, sr, identifier, strength)

    # Create watermark data
    watermark_data = _create_watermark_payload(identifier)
    bits = _string_to_bits(watermark_data)

    # Embed each bit as a short burst in the ultrasonic band
    samples_per_bit = int(WATERMARK_BIT_DURATION * sr)
    result = audio.copy()

    for i, bit in enumerate(bits):
        start = i * samples_per_bit
        if start + samples_per_bit > len(result):
            break

        if bit:
            # Embed a carrier signal at watermark frequency
            t = np.arange(samples_per_bit) / sr
            freq = WATERMARK_FREQ_BAND[0] + (i % 10) * 100
            carrier = strength * np.sin(2 * np.pi * freq * t)
            result[start:start + samples_per_bit] += carrier

    logger.info(f"Watermark embedded: {len(bits)} bits, strength={strength}")
    return result


def _embed_subaudible(
    audio: np.ndarray,
    sr: int,
    identifier: str,
    strength: float,
) -> np.ndarray:
    """
    Fallback: embed watermark using LSB (Least Significant Bit) modification
    in the time-domain signal. Works at any sample rate.
    """
    watermark_data = _create_watermark_payload(identifier)
    bits = _string_to_bits(watermark_data)

    result = audio.copy()

    # Scale to 16-bit integer range for LSB manipulation
    scale = 32767
    int_audio = (result * scale).astype(np.int32)

    # Embed bits in LSB
    for i, bit in enumerate(bits):
        if i >= len(int_audio):
            break
        # Clear LSB, then set it to our watermark bit
        int_audio[i] = (int_audio[i] & ~1) | bit

    # Convert back to float
    result = int_audio.astype(np.float32) / scale

    logger.info(f"Subaudible watermark embedded: {len(bits)} bits")
    return result


def detect_watermark(
    audio: np.ndarray,
    sr: int,
) -> Optional[dict]:
    """
    Detect and extract watermark from audio.
    Returns watermark info if found, None otherwise.
    """
    revision_mark = _detect_revision_watermark(audio)
    if revision_mark:
        return revision_mark
    if sr >= 40000:
        result = _detect_ultrasonic(audio, sr)
        if result:
            return result

    return _detect_lsb(audio, sr)


def _detect_ultrasonic(audio: np.ndarray, sr: int) -> Optional[dict]:
    """Detect ultrasonic watermark."""
    from app.utils.signal_processing import stft

    # Analyze energy in watermark frequency band
    S = np.abs(stft(audio, n_fft=4096))
    freqs = np.fft.rfftfreq(4096, d=1.0 / float(sr))

    band_mask = (freqs >= WATERMARK_FREQ_BAND[0]) & (freqs <= WATERMARK_FREQ_BAND[1])
    band_energy = np.mean(S[band_mask, :], axis=0)

    # Check if there's a pattern in the band energy
    threshold = np.mean(band_energy) * 1.5
    has_watermark = np.sum(band_energy > threshold) > 10

    if has_watermark:
        # Try to decode
        samples_per_bit = int(WATERMARK_BIT_DURATION * sr)
        bits = []
        for i in range(0, len(audio) - samples_per_bit, samples_per_bit):
            chunk = audio[i:i + samples_per_bit]
            S_chunk = np.abs(np.fft.rfft(chunk))
            freq_resolution = sr / len(chunk)
            band_start = int(WATERMARK_FREQ_BAND[0] / freq_resolution)
            band_end = int(WATERMARK_FREQ_BAND[1] / freq_resolution)
            band_e = np.mean(S_chunk[band_start:band_end]) if band_end > band_start else 0
            bits.append(1 if band_e > threshold else 0)

        payload = _bits_to_string(bits)
        if payload and payload.startswith(WATERMARK_PREFIX):
            return {"detected": True, "payload": payload, "method": "ultrasonic"}

    return None


def _detect_lsb(audio: np.ndarray, sr: int) -> Optional[dict]:
    """Detect LSB watermark."""
    scale = 32767
    int_audio = (audio * scale).astype(np.int32)

    # Extract LSBs
    bits = [int(int_audio[i] & 1) for i in range(min(len(int_audio), 1000))]

    payload = _bits_to_string(bits)
    if payload and WATERMARK_PREFIX in payload[:20]:
        return {"detected": True, "payload": payload, "method": "lsb"}

    return None


def _create_watermark_payload(identifier: str = "") -> str:
    """Create watermark payload string."""
    import time
    timestamp = int(time.time())
    checksum = hashlib.md5(f"{WATERMARK_PREFIX}-{identifier}-{timestamp}".encode()).hexdigest()[:8]
    return f"{WATERMARK_PREFIX}|{identifier}|{timestamp}|{checksum}"


def _string_to_bits(s: str) -> list:
    """Convert string to list of bits."""
    bits = []
    for char in s.encode("utf-8"):
        for i in range(8):
            bits.append((char >> (7 - i)) & 1)
    return bits


def _bits_to_string(bits: list) -> str:
    """Convert list of bits back to string."""
    chars = []
    for i in range(0, len(bits) - 7, 8):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | bits[i + j]
        if 32 <= byte < 127:
            chars.append(chr(byte))
        elif byte == 0:
            break
    return "".join(chars)
