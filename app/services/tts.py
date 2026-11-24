"""Local macOS speech synthesis and optional local expressive editing."""
import hashlib
import http.client
import json
import logging
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Optional

import numpy as np
import soundfile as sf

from app.config import APP_STORE_MODE
from app.services import expressive_voice

logger = logging.getLogger(__name__)
_SAY = Path("/usr/bin/say")
_VOICE_ROW = re.compile(r"^(.+?)\s+([a-z]{2,3}(?:[_-][A-Za-z0-9]+)+)\s+#", re.MULTILINE)

class LocalSpeechUnavailable(RuntimeError):
    """An actionable issue with an installed system voice."""


def macos_tts_available() -> bool:
    return sys.platform == "darwin" and _SAY.is_file()


def get_available_voices() -> list[dict]:
    if not macos_tts_available():
        return []
    try:
        result = subprocess.run(
            [str(_SAY), "-v", "?"], capture_output=True, encoding="utf-8", errors="replace",
            timeout=8, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    voices = {}
    for name, locale in _VOICE_ROW.findall(result.stdout):
        name = name.strip()
        language = locale.replace("_", "-")
        key = hashlib.sha256(f"{name}|{language}".encode("utf-8")).hexdigest()[:20]
        voice_id = f"macos_{key}"
        voices[voice_id] = {"id": voice_id, "name": name, "language": language, "engine": "macos"}
    return list(voices.values())


def _resolve_macos_voice(voice_id: str, language: str) -> dict:
    voices = get_available_voices()
    if not voices:
        raise LocalSpeechUnavailable("No macOS speech voices were found. Add a voice in macOS Accessibility settings, then refresh the voice list.")
    if voice_id not in ("", "default"):
        for voice in voices:
            if voice["id"] == voice_id:
                return voice
        raise ValueError("Select an installed macOS voice in Text to Speech.")
    language = language.lower().replace("_", "-")
    matching = [voice for voice in voices if voice["language"].lower().split("-")[0] == language.split("-")[0]]
    if not matching:
        raise ValueError("Select an installed macOS voice for the requested language.")
    preferred = {"it": "Alice", "en": "Samantha"}.get(language.split("-")[0])
    return next((voice for voice in matching if voice["name"].split(" (")[0] == preferred), matching[0])


def _synthesize_macos(text: str, voice: str, speed: float) -> tuple:
    with tempfile.TemporaryDirectory(prefix="aemax-speech-") as directory:
        source = Path(directory) / "script.txt"
        output = Path(directory) / "speech.wav"
        source.write_text(text, encoding="utf-8")
        command = [
            str(_SAY), "-v", voice, "-r", str(round(175 * speed)), "-f", str(source),
            "--file-format=WAVE", "--data-format=LEI16@22050", "-o", str(output),
        ]
        try:
            subprocess.run(command, check=True, timeout=180, capture_output=True)
            return sf.read(output, dtype="float32")
        except subprocess.TimeoutExpired as exc:
            raise LocalSpeechUnavailable("Local speech synthesis timed out. Try a shorter script.") from exc
        except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
            raise LocalSpeechUnavailable("macOS could not generate speech with this voice. Try another installed voice.") from exc


def _ollama_request(path: str, timeout: float, payload: dict | None = None) -> dict:
    connection = http.client.HTTPConnection("127.0.0.1", 11434, timeout=timeout)
    try:
        if payload is None:
            connection.request("GET", path)
        else:
            connection.request("POST", path, json.dumps(payload), {"Content-Type": "application/json"})
        response = connection.getresponse()
        if response.status != 200:
            raise RuntimeError(f"Local Ollama returned HTTP {response.status}")
        return json.load(response)
    finally:
        connection.close()


REWRITE_PROMPTS = {
    "it": """Riscrivi questo testo come se fosse letto ad alta voce da un conduttore di podcast coinvolgente e naturale.

REGOLE:
- Aggiungi pause naturali usando "..." per le pause brevi
- Aggiungi intercalari dove suona naturale: "ecco", "guardate", "insomma", "in pratica", "diciamo"
- Varia la lunghezza delle frasi - alterna frasi corte e lunghe
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
- Vary sentence length - alternate short and long sentences
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
    model = find_local_ollama_model()
    if not model:
        logger.warning("No Ollama model available - returning original text")
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

        result = _ollama_request("/api/chat", timeout=60, payload=payload)
        rewritten = result.get("message", {}).get("content", "").strip().strip('"\'`')
        if rewritten.startswith("```"):
            rewritten = rewritten.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        return rewritten if len(rewritten) > 10 else text

    except Exception as e:
        logger.warning(f"Gemma rewrite failed: {e} - using original text")
        return text


def find_local_ollama_model(timeout: float = 5) -> str:
    """Select an installed model without a remote Ollama endpoint."""
    try:
        models = _ollama_request("/api/tags", timeout=timeout).get("models", [])
        available = [
            model["name"] for model in models
            if model.get("name") and model.get("size", 0) > 0
            and not model.get("remote_model") and not model.get("remote_host")
            and not model["name"].lower().endswith(("-cloud", ":cloud"))
        ]
        for prefix in ("gemma", "qwen", "llama", "mistral"):
            preferred = next((name for name in available if name.startswith(prefix)), "")
            if preferred:
                return preferred
        return available[0] if available else ""
    except (OSError, ValueError, TypeError, RuntimeError, http.client.HTTPException):
        return ""


def synthesize_speech(
    text: str,
    language: str = "en",
    voice_id: str = "default",
    speed: float = 1.0,
    pitch: float = 1.0,
    warmth: float = 0.5,
    style: str = "neutral",
    clone_voice_path: Optional[str] = None,
    voice_profile_id: Optional[str] = None,
    expressive: bool = False,
    engine: str = "auto",
) -> tuple:
    """Generate speech with an installed on-device voice."""
    if engine not in ("auto", "macos", "voice-clone", expressive_voice.ENGINE):
        raise ValueError("This app generates speech locally. Select an installed voice.")

    is_voice_clone = bool(voice_profile_id) or engine == "voice-clone"
    if clone_voice_path and not voice_profile_id:
        raise RuntimeError("A raw voice sample is not a clone profile. Create or select a named personal voice.")
    if is_voice_clone and APP_STORE_MODE:
        raise RuntimeError("Personal voice cloning is not included in the Mac App Store build.")
    if is_voice_clone and not voice_profile_id:
        raise ValueError("No personal voice profile was selected")

    is_expressive_voice = not is_voice_clone and (engine == expressive_voice.ENGINE or (voice_id or "").startswith("qwen3_"))
    voice = None if is_voice_clone or is_expressive_voice else _resolve_macos_voice(voice_id or "default", language)
    rewritten_text = rewrite_expressive(text, language, style) if expressive else None
    if rewritten_text is not None:
        text = rewritten_text

    delivery_speed = max(0.5, min(2.0, speed * {"energetic": 1.10, "calm": 0.90, "expressive": 1.05}.get(style, 1.0)))
    clone_metadata = {}
    if is_voice_clone:
        from app.services.voice_profiles import synthesize_voice_profile
        audio, sr, clone_metadata = synthesize_voice_profile(text, voice_profile_id, speed=delivery_speed)
        engine_used = clone_metadata.get("engine", "makemyvoice")
    elif is_expressive_voice:
        if not expressive_voice.is_available(voice_id or ""):
            if voice_id == expressive_voice.PAOLA_ID:
                raise LocalSpeechUnavailable("Eve requires the local Qwen3 Base model and voice runtime.")
            raise LocalSpeechUnavailable("The Qwen3 voice runtime or model is missing. Install the local voice pack, then refresh voices.")
        audio, sr, clone_metadata = expressive_voice.synthesize(text, voice_id or "", style, speed)
        engine_used = expressive_voice.ENGINE
    else:
        audio, sr = _synthesize_macos(text, voice["name"], delivery_speed)
        engine_used = "macos"
        voice_id = voice["id"]
    audio = _apply_pitch(audio, sr, pitch)

    # ── Step 3: Post-processing ──
    audio = _apply_warmth(audio, sr, warmth, style)

    metadata = {
        "engine": engine_used,
        "expressive": expressive,
        "rewritten_text": rewritten_text,
        "voice_id": voice_id,
        "execution": "local-cpu",
        "voice_name": voice["name"] if voice else None,
        **clone_metadata,
    }

    return audio, sr, metadata


# ══════════════════════════════════════════════════════════
# Post-Processing
# ══════════════════════════════════════════════════════════

def _apply_pitch(audio: np.ndarray, sr: int, pitch: float) -> np.ndarray:
    """Shift a cloned voice while preserving its duration."""
    if abs(float(pitch) - 1.0) < 0.01:
        return audio
    try:
        import pedalboard as pb

        steps = 12.0 * np.log2(max(0.5, min(2.0, float(pitch))))
        board = pb.Pedalboard([pb.PitchShift(semitones=float(steps))])
        shifted = board(np.asarray(audio, dtype=np.float32), int(sr))
        return np.asarray(shifted, dtype=np.float32).reshape(np.asarray(audio).shape)
    except Exception as exc:
        logger.warning("Personal voice pitch shift unavailable: %s", exc)
        return audio

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
