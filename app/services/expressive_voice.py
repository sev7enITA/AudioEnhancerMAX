"""Qwen3 VoiceDesign inference using verified local files on Apple Silicon."""
from __future__ import annotations

from functools import lru_cache
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import tempfile

import numpy as np
import soundfile as sf

from app.config import APP_STORE_MODE, RESOURCE_DIR

RESOURCES = RESOURCE_DIR / "app/resources/expressive"
WORKER = RESOURCES / "worker.py"
ENGINE = "qwen3-voice-design"
PAOLA_ID = "qwen3_it_paola"
EVE_NAME = "Eve · Italiano"
PAOLA_MODEL = "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit"
PAOLA_REVISION = "e7dd0585652209fa0d7783659aad4e8a324de11c"
_PAOLA_REFERENCE = RESOURCES / "paola"
_SENTENCE = re.compile(r".+?(?:[.!?]+[\"»”’\)\]]*(?=\s|$)|$)", re.DOTALL)
_NO_NETWORK = ("/usr/bin/sandbox-exec", "-p", "(version 1)(allow default)(deny network*)")
_VOICES = {
    "qwen3_en_narrator": (
        "English narrator · Qwen3", "en-US", "English",
        "A natural female narrator with clear American English pronunciation, a warm tone and natural phrase rhythm.",
    ),
    "qwen3_en_host": (
        "English podcast host · Qwen3", "en-GB", "English",
        "A natural male British English podcast host with a warm mid-range voice and conversational emphasis.",
    ),
    "qwen3_it_narrator": (
        "Narratrice italiana · Qwen3", "it-IT", "Italian",
        "A natural Italian female narrator with clear native Italian pronunciation, a warm, conversational tone and natural phrase rhythm.",
    ),
    "qwen3_it_host": (
        "Conduttore italiano · Qwen3", "it-IT", "Italian",
        "A natural Italian male podcast host with clear native Italian pronunciation, a warm mid-range voice and natural conversational emphasis.",
    ),
}


@lru_cache(maxsize=1)
def manifest() -> dict:
    return json.loads((RESOURCES / "assets.json").read_text(encoding="utf-8"))


def voice_root() -> Path:
    default = Path.home() / "Library/Application Support/AudioEnhancerMAX/Expressive Voice"
    return Path(os.getenv("AEMAX_EXPRESSIVE_VOICE_ROOT", str(default))).expanduser()


def model_dir() -> Path:
    lock = manifest()
    return voice_root() / "cache" / ("models--" + lock["model"].replace("/", "--")) / "snapshots" / lock["revision"]


def runtime_python() -> Path:
    root = voice_root()
    managed = root / "managed-v1/bin/python3.11"
    return managed if managed.is_file() else root / "runtime/bin/python"


def platform_available() -> bool:
    if APP_STORE_MODE or platform.system() != "Darwin" or platform.machine() != "arm64":
        return False
    major = platform.mac_ver()[0].split(".")[0]
    return major.isdigit() and int(major) >= manifest()["min_macos"] and os.access(_NO_NETWORK[0], os.X_OK)


def model_asset_path(asset: dict) -> Path:
    return model_dir() / asset["path"].removeprefix("model/")


def matches_size(path: Path, asset: dict) -> bool:
    try:
        return path.is_file() and path.stat().st_size == asset["bytes"]
    except OSError:
        return False


def _runtime_available() -> bool:
    return platform_available() and os.access(runtime_python(), os.X_OK) and WORKER.is_file()


def paola_model_dir() -> Path | None:
    snapshot = Path("models--" + PAOLA_MODEL.replace("/", "--")) / "snapshots" / PAOLA_REVISION
    required = ("config.json", "model.safetensors", "tokenizer_config.json", "vocab.json", "merges.txt",
                "speech_tokenizer/config.json", "speech_tokenizer/model.safetensors")
    for cache in (voice_root() / "cache", Path.home() / ".cache/huggingface/hub"):
        root = cache / snapshot
        if all((root / name).is_file() for name in required):
            return root
    return None


def is_available(voice_id: str = "") -> bool:
    if not _runtime_available():
        return False
    if voice_id == PAOLA_ID:
        return paola_model_dir() is not None and all(
            (_PAOLA_REFERENCE / name).is_file() for name in ("reference.wav", "reference.txt")
        )
    return all(matches_size(model_asset_path(asset), asset) for asset in manifest()["weights"])


def available_voices() -> list[dict[str, str]]:
    voices = [
        {"id": key, "name": name, "language": locale, "engine": ENGINE}
        for key, (name, locale, _, _) in _VOICES.items()
    ] if is_available() else []
    if is_available(PAOLA_ID):
        voices.append({"id": PAOLA_ID, "name": EVE_NAME, "language": "it-IT", "engine": ENGINE})
    return voices


def run_offline(python: Path, args: list[str], timeout: int) -> None:
    # Use a separate interpreter without inherited app libraries, online credentials or proxy settings.
    env = {
        "HOME": str(Path.home()), "TMPDIR": tempfile.gettempdir(), "PATH": "/usr/bin:/bin",
        "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1",
    }
    subprocess.run([*_NO_NETWORK, str(python), "-I", "-B", *args], env=env,
                   capture_output=True, check=True, timeout=timeout)


def _italian_passages(text: str) -> list[tuple[str, bool]]:
    """Keep neighbouring statements together and separate complete questions."""
    passages: list[tuple[str, bool]] = []
    statements = []
    for sentence in _SENTENCE.findall(text.strip()):
        sentence = sentence.strip()
        if not sentence:
            continue
        if sentence.rstrip("\"»”’)]").endswith("?"):
            if statements:
                passages.append((" ".join(statements), False))
                statements.clear()
            passages.append((sentence, True))
        else:
            statements.append(sentence)
    if statements:
        passages.append((" ".join(statements), False))
    return passages


def _tempo(audio: np.ndarray, rate: int, factor: float) -> np.ndarray:
    """Change duration independently of pitch using the app's bundled FFmpeg libraries."""
    if abs(factor - 1.0) < 0.001:
        return audio
    import av

    frame = av.AudioFrame.from_ndarray(audio.reshape(1, -1), format="flt", layout="mono")
    frame.sample_rate = rate
    graph = av.filter.Graph()
    source = graph.add_abuffer(sample_rate=rate, format="flt", layout="mono")
    sink = graph.add("abuffersink")
    factors = (0.5, factor * 2.0) if factor < 0.5 else (factor,)
    graph.link_nodes(source, *(graph.add("atempo", str(step)) for step in factors), sink)
    graph.configure()
    output = []
    for packet in (frame, None):
        source.push(packet)
        while True:
            try:
                output.append(sink.pull().to_ndarray().reshape(-1))
            except (av.error.BlockingIOError, av.error.EOFError):
                break
    return np.concatenate(output) if output else audio


def _synthesize_paola(text: str, speed: float) -> tuple:
    model = paola_model_dir()
    if model is None or not is_available(PAOLA_ID):
        raise RuntimeError("Eve requires the pinned local Qwen3 Base voice model.")
    passages = _italian_passages(text)
    if not passages:
        raise ValueError("Enter text for Eve to read.")
    with tempfile.TemporaryDirectory(prefix="aemax-paola-") as temp:
        folder = Path(temp)
        request = folder / "request.json"
        request.write_text(json.dumps([passage for passage, _ in passages], ensure_ascii=False), encoding="utf-8")
        try:
            run_offline(runtime_python(), [
                str(WORKER), "--model", str(model), "--language", "Italian",
                "--reference-request", str(request), "--reference-dir", str(_PAOLA_REFERENCE),
            ], timeout=300)
            chunks = []
            for index, (_, question) in enumerate(passages):
                audio, rate = sf.read(folder / f"{index}.wav", dtype="float32")
                # This correction preserves question intonation. The user speed
                # control still applies to the whole reading.
                chunks.append(_tempo(audio, rate, speed * (0.93 if question else 1.0)))
            audio = np.concatenate(chunks)
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            raise RuntimeError("Eve could not synthesize this script locally.") from exc
    return audio, rate, {"voice_name": EVE_NAME, "language": "it-IT", "model": PAOLA_MODEL,
                         "model_revision": PAOLA_REVISION, "execution": "local-metal"}


def synthesize(text: str, voice_id: str, style: str, speed: float) -> tuple:
    if voice_id == PAOLA_ID:
        return _synthesize_paola(text, speed)
    if voice_id not in _VOICES:
        raise ValueError("Select a Qwen3 expressive voice.")
    if not is_available():
        raise RuntimeError("The local Qwen3 voice runtime or model is missing.")
    name, locale, language, description = _VOICES[voice_id]
    direction = {
        "energetic": "Sound lively and engaged, with crisp emphasis.",
        "calm": "Speak gently and calmly, with relaxed phrasing.",
        "expressive": "Vary emphasis and intonation naturally to bring out the meaning.",
    }.get(style, "Keep the reading clear and conversational.")
    pace = "Read slowly." if speed < 0.9 else "Read briskly." if speed > 1.1 else "Use a natural speaking pace."

    with tempfile.TemporaryDirectory(prefix="aemax-qwen3-") as temp:
        folder = Path(temp)
        script, instruction, output = folder / "script.txt", folder / "direction.txt", folder / "speech.wav"
        script.write_text(text, encoding="utf-8")
        instruction.write_text(f"{description} {direction} {pace}", encoding="utf-8")
        try:
            run_offline(runtime_python(), [
                str(WORKER), "--model", str(model_dir()), "--language", language,
                "--text-file", str(script), "--instruct-file", str(instruction), "--output", str(output),
            ], timeout=300)
            audio, rate = sf.read(output, dtype="float32")
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            raise RuntimeError("Qwen3 could not synthesize this script locally.") from exc
    return audio, rate, {"voice_name": name, "language": locale, "model": manifest()["model"], "execution": "local-metal"}
