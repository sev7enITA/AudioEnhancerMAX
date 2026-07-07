"""
AudioEnhancerMAX by Fd — Text-to-Speech Service v2.0
Engines:
  1. Edge Neural TTS — Microsoft neural voices, 400+ voices, 100+ languages
  2. Kokoro TTS — Local 82M-param model, very expressive (English)

Expressive Mode:
  Uses a local Ollama LLM, preferably a Gemma-family model, to rewrite text in natural spoken style
  before passing it to the TTS engine. Adds pauses, filler words, emphasis,
  and conversational rhythm for human-like delivery.
"""
import asyncio
import json
import os
import numpy as np
import urllib.request
import urllib.error
from typing import Optional, List
from pathlib import Path
import tempfile
import logging
import soundfile as sf

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════
# Voice Registry
# ══════════════════════════════════════════════════════════

VOICE_MAP = {
    # Italian
    "it_giuseppe":  "it-IT-GiuseppeMultilingualNeural",
    "it_diego":     "it-IT-DiegoNeural",
    "it_isabella":  "it-IT-IsabellaNeural",
    "it_elsa":      "it-IT-ElsaNeural",
    # English
    "en_aria":      "en-US-AriaNeural",
    "en_guy":       "en-US-GuyNeural",
    "en_jenny":     "en-US-JennyNeural",
    "en_davis":     "en-US-DavisNeural",
    "en_sonia":     "en-GB-SoniaNeural",
    # Spanish
    "es_elena":     "es-AR-ElenaNeural",
    "es_tomas":     "es-AR-TomasNeural",
    # French
    "fr_denise":    "fr-FR-DeniseNeural",
    "fr_henri":     "fr-FR-HenriNeural",
    # German
    "de_katja":     "de-DE-KatjaNeural",
    "de_conrad":    "de-DE-ConradNeural",
}

LANG_DEFAULTS = {
    "it": "it-IT-GiuseppeMultilingualNeural",
    "en": "en-US-AriaNeural",
    "es": "es-AR-ElenaNeural",
    "fr": "fr-FR-DeniseNeural",
    "de": "de-DE-KatjaNeural",
    "pt": "pt-BR-FranciscaNeural",
    "ja": "ja-JP-NanamiNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
    "ko": "ko-KR-SunHiNeural",
    "ru": "ru-RU-SvetlanaNeural",
    "ar": "ar-SA-ZariyahNeural",
    "hi": "hi-IN-SwaraNeural",
}

# Kokoro voice presets
KOKORO_VOICES = {
    "kokoro_heart":    {"id": "af_heart",   "name": "Heart ❤️",       "lang": "a", "gender": "female"},
    "kokoro_bella":    {"id": "af_bella",   "name": "Bella",          "lang": "a", "gender": "female"},
    "kokoro_adam":     {"id": "am_adam",     "name": "Adam",           "lang": "a", "gender": "male"},
    "kokoro_michael":  {"id": "am_michael", "name": "Michael",        "lang": "a", "gender": "male"},
    "kokoro_emma":     {"id": "bf_emma",    "name": "Emma 🇬🇧",      "lang": "b", "gender": "female"},
    "kokoro_george":   {"id": "bm_george",  "name": "George 🇬🇧",    "lang": "b", "gender": "male"},
}

PRESET_VOICES = [
    # Edge Neural — Italian
    {"id": "it_giuseppe", "name": "Giuseppe 🇮🇹", "language": "it", "gender": "male",
     "engine": "edge", "description": "Natural Italian multilingual voice — warm and expressive"},
    {"id": "it_isabella", "name": "Isabella 🇮🇹", "language": "it", "gender": "female",
     "engine": "edge", "description": "Clear Italian female voice — professional tone"},
    {"id": "it_diego", "name": "Diego 🇮🇹", "language": "it", "gender": "male",
     "engine": "edge", "description": "Deep Italian male voice — authoritative"},
    # Edge Neural — English
    {"id": "en_aria", "name": "Aria 🇺🇸", "language": "en", "gender": "female",
     "engine": "edge", "description": "Expressive American female — versatile and natural"},
    {"id": "en_guy", "name": "Guy 🇺🇸", "language": "en", "gender": "male",
     "engine": "edge", "description": "Clear American male — podcast-quality narration"},
    {"id": "en_davis", "name": "Davis 🇺🇸", "language": "en", "gender": "male",
     "engine": "edge", "description": "Deep American male — warm and conversational"},
    {"id": "en_sonia", "name": "Sonia 🇬🇧", "language": "en", "gender": "female",
     "engine": "edge", "description": "British female — elegant and articulate"},
    # Edge Neural — Other
    {"id": "es_elena", "name": "Elena 🇪🇸", "language": "es", "gender": "female",
     "engine": "edge", "description": "Natural Spanish female voice"},
    {"id": "fr_denise", "name": "Denise 🇫🇷", "language": "fr", "gender": "female",
     "engine": "edge", "description": "Warm French female voice"},
    {"id": "de_katja", "name": "Katja 🇩🇪", "language": "de", "gender": "female",
     "engine": "edge", "description": "Professional German female voice"},
    # Kokoro Local — English
    {"id": "kokoro_heart", "name": "Heart ❤️ (Local)", "language": "en", "gender": "female",
     "engine": "kokoro", "description": "Very expressive local voice — warm and emotional"},
    {"id": "kokoro_bella", "name": "Bella (Local)", "language": "en", "gender": "female",
     "engine": "kokoro", "description": "Natural local female — clear and articulate"},
    {"id": "kokoro_adam", "name": "Adam (Local)", "language": "en", "gender": "male",
     "engine": "kokoro", "description": "Deep local male — authoritative narration"},
    {"id": "kokoro_emma", "name": "Emma 🇬🇧 (Local)", "language": "en", "gender": "female",
     "engine": "kokoro", "description": "British female — sophisticated and warm"},
]


def get_available_voices() -> List[dict]:
    """Get list of available voices."""
    return PRESET_VOICES


# ══════════════════════════════════════════════════════════
# Gemma Expressive Rewrite
# ══════════════════════════════════════════════════════════

OLLAMA_BASE_URL = "http://localhost:11434"

REWRITE_PROMPTS = {
    "it": """Riscrivi questo testo come se fosse letto ad alta voce da un conduttore di podcast coinvolgente e naturale.

REGOLE:
- Aggiungi pause naturali usando "..." per le pause brevi
- Aggiungi intercalari dove suona naturale: "ecco", "guardate", "insomma", "in pratica", "diciamo"
- Varia la lunghezza delle frasi — alterna frasi corte e lunghe
- Aggiungi domande retoriche per coinvolgere l'ascoltatore
- Spezza le frasi lunghe in frasi più brevi e parlate
- Mantieni il significato ESATTO, cambia solo lo stile di delivery
- NON aggiungere emoji o formattazione markdown
- Rispondi SOLO con il testo riscritto, nient'altro

Testo originale: {text}""",

    "en": """Rewrite this text as if it's being spoken aloud by an engaging, natural podcast host.

RULES:
- Add natural pauses using "..." for brief pauses
- Add filler words where natural: "you know", "I mean", "look", "right", "actually"
- Vary sentence length — alternate short and long sentences
- Add rhetorical questions to engage the listener
- Break long sentences into shorter spoken phrases
- Keep the EXACT meaning, just change delivery style
- Do NOT add emoji or markdown formatting
- Respond with ONLY the rewritten text, nothing else

Original text: {text}""",

    "default": """Rewrite this text as if it's being spoken aloud by an engaging podcast host.
Keep the same language as the original. Add natural pauses (...), filler words,
rhetorical questions, and vary sentence rhythm. Keep the exact meaning.
Respond with ONLY the rewritten text.

Original text: {text}""",
}


def rewrite_expressive(text: str, language: str = "en", style: str = "neutral") -> str:
    """
    Use Gemma (local Ollama) to rewrite text in natural spoken style.
    Returns the rewritten text, or original if Gemma is unavailable.
    """
    model = _find_ollama_model()
    if not model:
        logger.warning("No Ollama model available — returning original text")
        return text

    lang_key = language[:2].lower() if language else "en"
    prompt_template = REWRITE_PROMPTS.get(lang_key, REWRITE_PROMPTS["default"])
    prompt = prompt_template.format(text=text)

    # Add style modifier
    if style == "energetic":
        prompt += "\n\nStyle: Energetic and enthusiastic. Use exclamations, short punchy sentences."
    elif style == "calm":
        prompt += "\n\nStyle: Calm and reflective. Use longer pauses, thoughtful phrasing."
    elif style == "expressive":
        prompt += "\n\nStyle: Highly expressive. Strong emotions, dramatic pauses, varied intonation cues."

    try:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a professional voice-over artist who rewrites text for natural spoken delivery. Respond ONLY with the rewritten text, no explanations, no markdown, no quotes."},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "keep_alive": "10m",
            "options": {"temperature": 0.7, "num_predict": 2000},
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{OLLAMA_BASE_URL}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            rewritten = result.get("message", {}).get("content", "").strip()

            # Clean up markdown artifacts
            rewritten = rewritten.strip('"\'`')
            if rewritten.startswith("```"):
                rewritten = rewritten.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            if rewritten and len(rewritten) > 10:
                logger.info(f"✨ Gemma rewrite ({model}): {len(text)} → {len(rewritten)} chars")
                return rewritten
            else:
                logger.warning("Gemma returned empty/short response — using original")
                return text

    except Exception as e:
        logger.warning(f"Gemma rewrite failed: {e} — using original text")
        return text


_ollama_model_cache = None

def _find_ollama_model() -> str:
    """Find a working Gemma/LLM model in Ollama."""
    global _ollama_model_cache
    if _ollama_model_cache:
        return _ollama_model_cache

    preferred = ["gemma3:4b", "gemma4:e2b", "gemma4:e4b", "gemma4:latest", "qwen2.5:7b", "llama3.2:latest", "mistral:7b"]

    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            available = [m.get("name", "") for m in data.get("models", [])]

            for pref in preferred:
                for avail in available:
                    if pref == avail or avail.startswith(pref.split(":")[0]):
                        _ollama_model_cache = avail
                        logger.info(f"🤖 Ollama model for TTS rewrite: {avail}")
                        return avail

            # Any model
            if available:
                _ollama_model_cache = available[0]
                logger.info(f"🤖 Using first available model: {available[0]}")
                return available[0]
    except Exception as e:
        logger.warning(f"Ollama not reachable: {e}")

    return ""


# ══════════════════════════════════════════════════════════
# TTS Engines
# ══════════════════════════════════════════════════════════

def _resolve_voice(voice_id: str, language: str) -> str:
    """Resolve voice ID to edge-tts voice name."""
    if voice_id in VOICE_MAP:
        return VOICE_MAP[voice_id]
    lang_code = language[:2].lower() if language else "en"
    return LANG_DEFAULTS.get(lang_code, "en-US-AriaNeural")


def _style_to_rate_pitch(style: str, speed: float, pitch: float):
    """Convert style + speed + pitch to edge-tts rate/pitch strings."""
    rate_pct = int((speed - 1.0) * 100)
    pitch_hz = int((pitch - 1.0) * 50)

    if style == "energetic":
        rate_pct += 10
        pitch_hz += 5
    elif style == "calm":
        rate_pct -= 10
        pitch_hz -= 3
    elif style == "expressive":
        rate_pct += 5
        pitch_hz += 8

    rate_str = f"+{rate_pct}%" if rate_pct >= 0 else f"{rate_pct}%"
    pitch_str = f"+{pitch_hz}Hz" if pitch_hz >= 0 else f"{pitch_hz}Hz"
    return rate_str, pitch_str


async def _synthesize_edge_async(text: str, voice: str, rate: str, pitch: str, output_path: str):
    """Generate speech using edge-tts (async)."""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(output_path)


def _synthesize_edge(text: str, voice: str, rate: str, pitch: str) -> tuple:
    """Synchronous wrapper for edge-tts."""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        temp_path = tmp.name
    try:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_synthesize_edge_async(text, voice, rate, pitch, temp_path))
        finally:
            loop.close()

        audio, sr = sf.read(temp_path)
        Path(temp_path).unlink(missing_ok=True)
        return audio, sr
    except Exception:
        Path(temp_path).unlink(missing_ok=True)
        raise


def _synthesize_kokoro(text: str, voice_id: str = "af_heart", lang_code: str = "a", speed: float = 1.0) -> tuple:
    """Local TTS with Kokoro — 82M params, very expressive."""
    try:
        # espeak-ng data path for Homebrew installation
        os.environ.setdefault("ESPEAK_DATA_PATH", "/opt/homebrew/Cellar/espeak-ng/1.52.0/share")
        from kokoro import KPipeline

        pipeline = KPipeline(lang_code=lang_code)
        segments = []
        for _, _, audio_chunk in pipeline(text, voice=voice_id, speed=speed):
            segments.append(audio_chunk)

        if not segments:
            raise RuntimeError("Kokoro produced no audio")

        full_audio = np.concatenate(segments)
        logger.info(f"✅ Kokoro TTS: {voice_id} — {len(full_audio)/24000:.1f}s generated")
        return full_audio, 24000

    except ImportError:
        raise RuntimeError("Kokoro TTS not installed. Run: pip install kokoro")
    except Exception as e:
        raise RuntimeError(f"Kokoro synthesis failed: {e}")


# ══════════════════════════════════════════════════════════
# Main Synthesis Function
# ══════════════════════════════════════════════════════════

def synthesize_speech(
    text: str,
    language: str = "en",
    voice_id: str = "default",
    speed: float = 1.0,
    pitch: float = 1.0,
    warmth: float = 0.5,
    style: str = "neutral",
    clone_voice_path: Optional[str] = None,
    expressive: bool = False,
    engine: str = "auto",
) -> tuple:
    """
    Generate speech from text.

    Args:
        expressive: If True, uses Gemma to rewrite text for natural spoken delivery
        engine: "edge", "kokoro", or "auto" (auto selects based on voice_id)

    Returns (audio_array, sample_rate, metadata_dict)
    """
    original_text = text
    rewritten_text = None

    # ── Step 1: Expressive rewrite with Gemma ──
    if expressive:
        rewritten_text = rewrite_expressive(text, language, style)
        text = rewritten_text

    # ── Step 2: Determine engine ──
    is_kokoro = voice_id.startswith("kokoro_") or engine == "kokoro"

    if is_kokoro:
        # Kokoro local engine
        kokoro_info = KOKORO_VOICES.get(voice_id, KOKORO_VOICES["kokoro_heart"])
        audio, sr = _synthesize_kokoro(
            text,
            voice_id=kokoro_info["id"],
            lang_code=kokoro_info["lang"],
            speed=speed,
        )
        engine_used = "kokoro"
    else:
        # Edge Neural TTS
        voice = _resolve_voice(voice_id, language)
        rate_str, pitch_str = _style_to_rate_pitch(style, speed, pitch)
        audio, sr = _synthesize_edge(text, voice, rate_str, pitch_str)
        engine_used = "edge"
        logger.info(f"✅ Edge TTS: {voice} — {len(audio)/sr:.1f}s generated")

    # ── Step 3: Post-processing ──
    audio = _apply_warmth(audio, sr, warmth, style)

    metadata = {
        "engine": engine_used,
        "expressive": expressive,
        "rewritten_text": rewritten_text,
        "voice_id": voice_id,
    }

    return audio, sr, metadata


# ══════════════════════════════════════════════════════════
# Post-Processing
# ══════════════════════════════════════════════════════════

def _apply_warmth(audio: np.ndarray, sr: int, warmth: float = 0.5, style: str = "neutral") -> np.ndarray:
    """Apply warmth and style EQ adjustments via pedalboard."""
    try:
        import pedalboard as pb

        effects = []

        if warmth > 0.5:
            boost = (warmth - 0.5) * 6
            effects.append(pb.LowShelfFilter(cutoff_frequency_hz=200, gain_db=boost))
            effects.append(pb.HighShelfFilter(cutoff_frequency_hz=6000, gain_db=-boost * 0.5))
        elif warmth < 0.5:
            cut = (0.5 - warmth) * 6
            effects.append(pb.LowShelfFilter(cutoff_frequency_hz=200, gain_db=-cut))
            effects.append(pb.HighShelfFilter(cutoff_frequency_hz=6000, gain_db=cut * 0.5))

        if style == "energetic":
            effects.extend([
                pb.Compressor(threshold_db=-15, ratio=2.5, attack_ms=5, release_ms=50),
                pb.Gain(gain_db=2.0),
            ])
        elif style == "calm":
            effects.extend([
                pb.Compressor(threshold_db=-25, ratio=1.5, attack_ms=20, release_ms=200),
                pb.LowpassFilter(cutoff_frequency_hz=12000),
            ])

        if effects:
            board = pb.Pedalboard(effects)
            audio_2d = audio.reshape(1, -1) if audio.ndim == 1 else audio
            audio = board(audio_2d, sr)
            audio = audio.flatten() if audio.ndim != 1 else audio

    except ImportError:
        pass

    return np.clip(audio, -1.0, 1.0)
