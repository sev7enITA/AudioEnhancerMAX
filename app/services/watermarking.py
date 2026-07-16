"""
AudioEnhancerMAX by Fd - Audio Watermarking Service
Embeds and detects invisible watermarks in processed audio files.
"""
import numpy as np
from typing import Optional
import logging
import hashlib
import struct

logger = logging.getLogger(__name__)

# Watermark configuration
WATERMARK_PREFIX = "AEMAX-Fd"
WATERMARK_FREQ_BAND = (18000, 19500)  # Near-ultrasonic, inaudible for most
WATERMARK_BIT_DURATION = 0.02  # 20ms per bit


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
    if sr >= 40000:
        result = _detect_ultrasonic(audio, sr)
        if result:
            return result

    return _detect_lsb(audio, sr)


def _detect_ultrasonic(audio: np.ndarray, sr: int) -> Optional[dict]:
    """Detect ultrasonic watermark."""
    import librosa

    # Analyze energy in watermark frequency band
    S = np.abs(librosa.stft(audio, n_fft=4096))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=4096)

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
