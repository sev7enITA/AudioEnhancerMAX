"""
AudioEnhancerMAX by Fd — Smart Mode Service via local Ollama/Gemma.
Uses a locally available Gemma-family model for assistive content classification
and editing suggestions, with deterministic heuristics as fallback.
"""
import numpy as np
import json
import logging
import tempfile
import base64
import subprocess
from typing import Optional
from pathlib import Path

import soundfile as sf

from app.config import SMART_PRESETS
from app.models.schemas import ContentType, ProcessingOptions

logger = logging.getLogger(__name__)

OLLAMA_MODEL = None  # Auto-detected
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_PREFERRED_MODELS = ["gemma4:e2b", "gemma4:e4b", "gemma4:latest", "gemma3:4b"]


def _query_gemma(prompt: str, audio_path: Optional[str] = None) -> Optional[str]:
    """
    Query the selected local Gemma-family model via Ollama Chat API.
    Uses /api/chat for chat-tuned models.
    """
    import urllib.request
    import urllib.error

    # Ensure model is detected
    if OLLAMA_MODEL is None:
        if not _check_ollama_available():
            return None

    url = f"{OLLAMA_BASE_URL}/api/chat"

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are an expert audio engineer. Always respond with valid JSON only, no markdown or extra text."
            },
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "stream": False,
        "format": "json",
        "keep_alive": "10m",
        "options": {
            "temperature": 0.3,
            "num_predict": 800,
        }
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            content = result.get("message", {}).get("content", "")
            logger.info(f"Ollama/Gemma response ({OLLAMA_MODEL}, {len(content)} chars): {content[:100]}...")
            return content
    except urllib.error.URLError as e:
        logger.warning(f"Ollama not reachable: {e}. Falling back to heuristics.")
        return None
    except Exception as e:
        logger.warning(f"Ollama/Gemma query failed: {e}. Falling back to heuristics.")
        return None


def _check_ollama_available() -> bool:
    """Check if Ollama is running and a Gemma model is available."""
    global OLLAMA_MODEL
    try:
        import urllib.request
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = [m.get("name", "") for m in data.get("models", [])]

            # Try preferred models in order
            for preferred in OLLAMA_PREFERRED_MODELS:
                for available in models:
                    if preferred in available or available.startswith(preferred.split(":")[0]):
                        OLLAMA_MODEL = available
                        return True

            # Check any gemma variant
            for m in models:
                if "gemma" in m.lower():
                    OLLAMA_MODEL = m
                    return True

            return False
    except Exception:
        return False


def detect_content_type(
    audio: np.ndarray,
    sr: int,
) -> dict:
    """
    Detect content type using local Ollama/Gemma first, with spectral heuristics fallback.
    """
    # Try local Gemma first
    gemma_result = _detect_with_gemma(audio, sr)
    if gemma_result:
        return gemma_result

    # Fallback to spectral heuristics
    logger.info("Using spectral heuristics fallback for content detection")
    return _detect_with_heuristics(audio, sr)


def _detect_with_gemma(audio: np.ndarray, sr: int) -> Optional[dict]:
    """Use local Ollama/Gemma for content classification via spectral feature analysis."""
    if not _check_ollama_available():
        return None

    import librosa

    # Extract audio features for local model analysis
    duration = len(audio) / sr
    preview = audio[:int(min(30, duration) * sr)]

    spectral_centroid = float(np.mean(librosa.feature.spectral_centroid(y=preview, sr=sr)))
    spectral_bandwidth = float(np.mean(librosa.feature.spectral_bandwidth(y=preview, sr=sr)))
    rms = librosa.feature.rms(y=preview)[0]
    rms_mean = float(np.mean(rms))
    rms_dynamic_range = float(np.std(rms) / (rms_mean + 1e-10))

    onset_env = librosa.onset.onset_strength(y=preview, sr=sr)
    tempo = float(librosa.feature.tempo(onset_envelope=onset_env, sr=sr)[0])

    zcr = float(np.mean(librosa.feature.zero_crossing_rate(preview)))
    silence_threshold = librosa.db_to_amplitude(-40)
    silence_ratio = float(np.sum(rms < silence_threshold) / len(rms))

    # Build descriptive prompt with extracted features
    prompt = f"""You are an expert audio engineer. Analyze these audio features and classify the content.

AUDIO FEATURES:
- Duration: {duration:.1f} seconds
- Sample rate: {sr} Hz
- Spectral centroid: {spectral_centroid:.0f} Hz (higher = brighter sound)
- Spectral bandwidth: {spectral_bandwidth:.0f} Hz (higher = wider frequency range)
- RMS energy (mean): {rms_mean:.4f} (volume level)
- Dynamic range: {rms_dynamic_range:.2f} (higher = more variation in volume, typical of speech)
- Tempo: {tempo:.0f} BPM (higher values suggest music)
- Zero crossing rate: {zcr:.4f} (higher = noisier/percussive)
- Silence ratio: {silence_ratio:.1%} (how much of the audio is silent)

Classify into ONE of these categories:
- podcast: Long-form speech, one or multiple speakers
- voice_memo: Short personal recording, casual speech
- interview: Two speakers in Q&A format (usually high silence ratio due to turn-taking)
- music: Musical content with instruments/vocals (high tempo, wide bandwidth)
- outdoor_recording: Outdoor environmental sounds (high zero crossing, irregular dynamics)

Respond ONLY with a valid JSON object:
{{"type": "<category>", "confidence": <0.0-1.0>, "description": "<brief description>", "speakers": <estimated number>, "noise_level": "<low|medium|high>", "suggestions": ["<suggestion1>", "<suggestion2>"]}}"""

    response = _query_gemma(prompt)  # Text-only query

    if not response:
        return None

    try:
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            json_str = response[json_start:json_end]
            logger.info(f"Parsing JSON: {json_str[:150]}...")
            data = json.loads(json_str)

            content_type = data.get("type", "podcast")
            type_map = {
                "podcast": ContentType.PODCAST,
                "voice_memo": ContentType.VOICE_MEMO,
                "interview": ContentType.INTERVIEW,
                "music": ContentType.MUSIC,
                "outdoor_recording": ContentType.OUTDOOR,
                "outdoor": ContentType.OUTDOOR,
            }

            detected = type_map.get(content_type, ContentType.PODCAST)

            result = {
                "type": detected,
                "confidence": float(data.get("confidence", 0.8)),
                "description": data.get("description", f"Detected as {content_type}"),
                "speakers": data.get("speakers", 1),
                "noise_level": data.get("noise_level", "medium"),
                "ai_suggestions": data.get("suggestions", []),
                "engine": OLLAMA_MODEL or "ollama-gemma",
            }
            logger.info(f"Ollama/Gemma classification via {result['engine']}: {content_type} ({result['confidence']:.0%})")
            return result
        else:
            logger.warning(f"No JSON found in Gemma response: {response[:100]}")
    except Exception as e:
        logger.warning(f"Failed to parse Gemma response: {e}, raw: {response[:100]}")

    return None


def _detect_with_heuristics(audio: np.ndarray, sr: int) -> dict:
    """Fallback spectral analysis for content classification."""
    import librosa

    duration = len(audio) / sr

    spectral_centroid = np.mean(librosa.feature.spectral_centroid(y=audio, sr=sr))
    spectral_bandwidth = np.mean(librosa.feature.spectral_bandwidth(y=audio, sr=sr))
    rms = librosa.feature.rms(y=audio)[0]
    rms_mean = np.mean(rms)
    rms_std = np.std(rms)
    rms_dynamic_range = rms_std / (rms_mean + 1e-10)

    onset_env = librosa.onset.onset_strength(y=audio, sr=sr)
    tempo = librosa.feature.tempo(onset_envelope=onset_env, sr=sr)[0]

    silence_threshold = librosa.db_to_amplitude(-40)
    silence_ratio = np.sum(rms < silence_threshold) / len(rms)

    scores = {ct: 0.0 for ct in ContentType if ct != ContentType.CUSTOM}

    is_speech = spectral_centroid < 3000 and rms_dynamic_range > 0.3
    is_music = tempo > 60 and spectral_bandwidth > 3000

    if duration > 300:
        scores[ContentType.PODCAST] += 3
    elif duration < 120:
        scores[ContentType.VOICE_MEMO] += 2

    if is_speech:
        scores[ContentType.PODCAST] += 2
        scores[ContentType.INTERVIEW] += 2
        scores[ContentType.VOICE_MEMO] += 2

    if is_music:
        scores[ContentType.MUSIC] += 4

    if silence_ratio > 0.2:
        scores[ContentType.INTERVIEW] += 2

    if rms_dynamic_range > 0.6:
        scores[ContentType.OUTDOOR] += 2

    S = np.abs(librosa.stft(audio, n_fft=2048))
    low_energy = np.mean(S[:10, :])
    high_energy = np.mean(S[100:, :])
    if low_energy > high_energy * 3:
        scores[ContentType.OUTDOOR] += 3

    best_type = max(scores, key=scores.get)
    total = sum(scores.values())
    confidence = scores[best_type] / total if total > 0 else 0

    descriptions = {
        ContentType.PODCAST: "Podcast/speech detected. Optimizing for voice clarity.",
        ContentType.VOICE_MEMO: "Voice memo detected. Quick cleanup mode.",
        ContentType.INTERVIEW: "Interview detected. Preserving conversation flow.",
        ContentType.MUSIC: "Musical content detected. Preserving dynamics.",
        ContentType.OUTDOOR: "Outdoor recording detected. Environmental noise reduction.",
    }

    return {
        "type": best_type,
        "confidence": min(confidence, 0.9),
        "description": descriptions.get(best_type, ""),
        "engine": "heuristics",
    }


def get_smart_preset(content_type: ContentType) -> ProcessingOptions:
    """Get optimal processing options for detected content type."""
    preset = SMART_PRESETS.get(content_type.value, SMART_PRESETS["podcast"])
    return ProcessingOptions(**preset)


def analyze_and_suggest(audio: np.ndarray, sr: int) -> dict:
    """Full smart mode: detect + suggest processing chain."""
    detection = detect_content_type(audio, sr)
    preset = get_smart_preset(detection["type"])

    return {
        "detected_type": detection["type"],
        "confidence": detection["confidence"],
        "description": detection["description"],
        "engine": detection.get("engine", "unknown"),
        "ai_suggestions": detection.get("ai_suggestions", []),
        "suggested_options": preset.model_dump(),
    }


def get_editing_suggestions(audio: np.ndarray, sr: int, transcript: str = "") -> list:
    """
    Use local Ollama/Gemma to provide assistive editing suggestions based on content analysis.
    """
    if not _check_ollama_available():
        return []

    prompt = f"""You are an audio editing expert. Based on this podcast transcript excerpt, suggest specific editing improvements.

Transcript: {transcript[:2000]}

Provide 3-5 specific, actionable editing suggestions in JSON array format:
[{{"suggestion": "<description>", "priority": "high|medium|low", "type": "cleanup|enhancement|structure"}}]"""

    response = _query_gemma(prompt)
    if not response:
        return []

    try:
        json_start = response.find("[")
        json_end = response.rfind("]") + 1
        if json_start >= 0 and json_end > json_start:
            return json.loads(response[json_start:json_end])
    except (json.JSONDecodeError, ValueError):
        pass

    return []


def get_dynamic_parameters(
    audio: np.ndarray,
    sr: int,
    enabled_filters: dict,
) -> dict:
    """
    v2.0: Use local Ollama/Gemma to dynamically tune processing parameters based on
    the specific audio characteristics. Instead of using static defaults,
    this analyzes the audio and returns optimized strength values per filter.

    Returns dict of filter_name -> { strength, reason } overrides.
    Falls back to conservative defaults if Gemma is unavailable.
    """
    import librosa

    # Extract audio features for analysis
    duration = len(audio) / sr
    preview = audio[:int(min(30, duration) * sr)]

    rms = librosa.feature.rms(y=preview)[0]
    rms_mean = float(np.mean(rms))
    rms_db = float(20 * np.log10(rms_mean + 1e-10))

    spectral_centroid = float(np.mean(librosa.feature.spectral_centroid(y=preview, sr=sr)))
    spectral_bandwidth = float(np.mean(librosa.feature.spectral_bandwidth(y=preview, sr=sr)))
    zcr = float(np.mean(librosa.feature.zero_crossing_rate(preview)))

    # Estimate SNR (simple: ratio of speech energy to noise floor)
    silence_threshold = librosa.db_to_amplitude(-40)
    speech_frames = rms[rms > silence_threshold]
    noise_frames = rms[rms <= silence_threshold]
    snr_estimate = 0.0
    if len(noise_frames) > 0 and np.mean(noise_frames) > 0:
        snr_estimate = float(20 * np.log10(
            np.mean(speech_frames) / (np.mean(noise_frames) + 1e-10)
        ))

    # Get list of active filters
    active_filters = [k for k, v in enabled_filters.items() if v is True]

    if not active_filters:
        return {}

    # Try local Gemma for intelligent tuning
    if _check_ollama_available():
        gemma_result = _get_gemma_tuning(
            active_filters, rms_db, snr_estimate,
            spectral_centroid, spectral_bandwidth, zcr, duration
        )
        if gemma_result:
            logger.info(f"Ollama/Gemma dynamic tuning: {len(gemma_result)} filters adjusted")
            return gemma_result

    # Fallback: heuristic-based tuning
    logger.info("Using heuristic dynamic tuning (Gemma unavailable)")
    return _get_heuristic_tuning(active_filters, rms_db, snr_estimate, spectral_centroid)


def _get_gemma_tuning(
    active_filters: list,
    rms_db: float,
    snr_estimate: float,
    spectral_centroid: float,
    spectral_bandwidth: float,
    zcr: float,
    duration: float,
) -> Optional[dict]:
    """Query local Ollama/Gemma for per-filter parameter tuning."""

    filters_str = ", ".join(active_filters)

    prompt = f"""You are an expert audio engineer tuning a podcast/speech processing pipeline.

AUDIO ANALYSIS:
- RMS level: {rms_db:.1f} dB (higher = louder)
- Estimated SNR: {snr_estimate:.1f} dB (higher = cleaner audio)
- Spectral centroid: {spectral_centroid:.0f} Hz
- Spectral bandwidth: {spectral_bandwidth:.0f} Hz
- Zero crossing rate: {zcr:.4f}
- Duration: {duration:.1f}s

ACTIVE FILTERS: {filters_str}

For each active filter, recommend a strength value (0.0 to 1.0) that will produce NATURAL sounding results.
Rules:
- For clean audio (SNR > 20dB), use LOW noise reduction (0.3-0.5)
- For noisy audio (SNR < 10dB), use MODERATE noise reduction (0.6-0.8), never higher
- Studio sound and EQ should always be subtle (0.4-0.7)
- Breath removal should be gentle (0.3-0.5) to sound natural
- NEVER use 1.0 for any filter — always leave some natural character

Respond with JSON only:
{{{", ".join(f'"{f}": {{"strength": 0.5, "reason": ""}}' for f in active_filters)}}}"""

    response = _query_gemma(prompt)
    if not response:
        return None

    try:
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            data = json.loads(response[json_start:json_end])
            # Validate and cap all strength values
            result = {}
            for key, val in data.items():
                if key in active_filters and isinstance(val, dict):
                    strength = float(val.get("strength", 0.5))
                    # Safety caps: never below 0.1, never above 0.85
                    strength = max(0.1, min(0.85, strength))
                    result[key] = {
                        "strength": strength,
                        "reason": str(val.get("reason", f"Ollama/Gemma tuned via {OLLAMA_MODEL or 'local model'}")),
                    }
            return result
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning(f"Failed to parse Gemma tuning: {e}")

    return None


def _get_heuristic_tuning(
    active_filters: list,
    rms_db: float,
    snr_estimate: float,
    spectral_centroid: float,
) -> dict:
    """Fallback heuristic parameter tuning based on audio analysis."""

    result = {}

    # Determine audio quality tier
    if snr_estimate > 25:
        quality = "clean"
    elif snr_estimate > 15:
        quality = "moderate"
    else:
        quality = "noisy"

    # Conservative strength defaults per quality tier
    strengths = {
        "clean":    {"noise": 0.3, "speech": 0.4, "enhance": 0.5},
        "moderate": {"noise": 0.5, "speech": 0.5, "enhance": 0.6},
        "noisy":    {"noise": 0.7, "speech": 0.6, "enhance": 0.5},
    }
    s = strengths[quality]

    noise_filters = ["remove_noise", "wind_noise_remover", "buzzing_noise_remover",
                     "static_noise_remover", "reverb_echo_remover"]
    speech_filters = ["remove_filler_words", "eliminate_hesitations", "remove_stuttering",
                      "remove_breaths", "remove_mouth_sounds"]
    enhance_filters = ["studio_sound", "auto_eq", "normalize", "keep_music",
                       "frequency_restoration"]

    for f in active_filters:
        if f in noise_filters:
            result[f] = {"strength": s["noise"], "reason": f"Heuristic: {quality} audio → {s['noise']}"}
        elif f in speech_filters:
            result[f] = {"strength": s["speech"], "reason": f"Heuristic: {quality} audio → {s['speech']}"}
        elif f in enhance_filters:
            result[f] = {"strength": s["enhance"], "reason": f"Heuristic: {quality} audio → {s['enhance']}"}
        else:
            result[f] = {"strength": 0.5, "reason": "Default"}

    return result
