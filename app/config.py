"""
AudioEnhancerMAX by Fd - Configuration
"""
import os
import sys
from pathlib import Path
from app.release import APP_NAME

# Resource and user-data paths. Frozen macOS builds keep bundled assets in
# PyInstaller's resource directory while mutable data lives outside the .app.
SOURCE_BASE_DIR = Path(__file__).resolve().parent.parent
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", SOURCE_BASE_DIR))
BASE_DIR = RESOURCE_DIR

APP_STORE_MODE = os.getenv("AEMAX_APP_STORE") == "1"
BUNDLED_WHISPER_MODEL_DIR = RESOURCE_DIR / "models" / "faster-whisper-medium"
BUNDLED_WHISPER_MODEL_FILES = (
    "config.json",
    "model.bin",
    "tokenizer.json",
    "vocabulary.txt",
)


def bundled_whisper_model_available() -> bool:
    """Return whether the complete review-safe Whisper model is bundled."""
    return all((BUNDLED_WHISPER_MODEL_DIR / name).is_file() for name in BUNDLED_WHISPER_MODEL_FILES)


def whisper_model_source(requested: str = "medium") -> tuple[str, bool]:
    """Resolve a local model path for Store builds and a model name elsewhere."""
    if bundled_whisper_model_available():
        return str(BUNDLED_WHISPER_MODEL_DIR), True
    if APP_STORE_MODE:
        raise RuntimeError("The App Store build is missing its bundled transcription model.")
    return requested, False

_default_data_dir = SOURCE_BASE_DIR / "app"
if getattr(sys, "frozen", False):
    _default_data_dir = Path.home() / "Library" / "Application Support" / APP_NAME

DATA_DIR = Path(os.getenv("AEMAX_DATA_DIR", str(_default_data_dir))).expanduser()
APP_DIR = DATA_DIR
UPLOAD_DIR = APP_DIR / "uploads"
FRONTEND_DIR = RESOURCE_DIR / "frontend"
OUTPUT_DIR = APP_DIR / "outputs"
PROJECTS_DIR = APP_DIR / "projects"
PRESETS_DIR = APP_DIR / "presets"
TIMING_HISTORY_FILE = APP_DIR / "timing_history.json"
ROADMAP_VOTES_FILE = APP_DIR / "roadmap_votes.json"
PREFLIGHT_STATE_FILE = APP_DIR / "preflight_state.json"
RUNTIME_SETTINGS_FILE = APP_DIR / "runtime_settings.json"
VOICE_PROFILES_DIR = APP_DIR / "voice_profiles"

# MakeMyVoice is an optional, separately versioned local runtime.  The
# adapter discovers it through this explicit override first and through the
# sibling development checkout second; packaged builds never assume that it
# is installed.
_default_makemyvoice_root = SOURCE_BASE_DIR.parent.parent / "MakeMyVoice"
MAKEMYVOICE_ROOT = Path(
    os.getenv("AEMAX_MAKEMYVOICE_ROOT", str(_default_makemyvoice_root))
).expanduser()

# Ensure directories exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
PRESETS_DIR.mkdir(parents=True, exist_ok=True)
VOICE_PROFILES_DIR.mkdir(parents=True, exist_ok=True)

# Audio settings
MAX_FILE_SIZE_MB = 500
ALLOWED_EXTENSIONS = {".mp3", ".mp4", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma"}
DEFAULT_SAMPLE_RATE = 44100
HIGH_QUALITY_SAMPLE_RATE = 48000

# Processing defaults
SILENCE_THRESHOLD_DB = -40
MIN_SILENCE_DURATION_MS = 1000
FILLER_WORDS = [
    "uhm", "uh", "um", "eh", "ehm", "hmm", "hm", "mm",
    "like", "you know", "basically", "actually", "literally",
    "I mean", "sort of", "kind of", "right",
    # Italian filler words
    "ehm", "cioè", "tipo", "praticamente", "insomma",
    "allora", "diciamo", "ecco", "niente", "boh"
]

# Model settings
WHISPER_MODEL = "medium"  # The App Store build bundles this model.
WHISPER_DEVICE = "auto"  # auto, cpu, cuda
TTS_MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"

# DeepFilterNet settings
DEEPFILTER_POST_FILTER = True

# Smart Mode presets
SMART_PRESETS = {
    "podcast": {
        "remove_noise": True,
        "remove_filler_words": True,
        "remove_breaths": True,
        "normalize": True,
        "auto_eq": True,
        "studio_sound": True,
        "noise_reduction_strength": 0.7,
    },
    "voice_memo": {
        "remove_noise": True,
        "remove_long_silences": True,
        "normalize": True,
        "noise_reduction_strength": 0.9,
    },
    "interview": {
        "remove_noise": True,
        "remove_filler_words": False,
        "remove_breaths": True,
        "normalize": True,
        "auto_eq": True,
        "noise_reduction_strength": 0.5,
    },
    "music": {
        "remove_noise": False,
        "keep_music": True,
        "normalize": True,
        "auto_eq": True,
        "noise_reduction_strength": 0.3,
    },
    "outdoor_recording": {
        "remove_noise": True,
        "wind_noise_remover": True,
        "normalize": True,
        "studio_sound": True,
        "noise_reduction_strength": 0.8,
    },
}
