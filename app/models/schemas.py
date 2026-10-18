"""
AudioEnhancerMAX by Fd - Pydantic Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from enum import Enum


class ContentType(str, Enum):
    PODCAST = "podcast"
    VOICE_MEMO = "voice_memo"
    INTERVIEW = "interview"
    MUSIC = "music"
    OUTDOOR = "outdoor_recording"
    CUSTOM = "custom"


class SmartProfile(str, Enum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    MAXIMUM = "maximum"


class OutputFormat(str, Enum):
    MP3 = "mp3"
    WAV = "wav"
    FLAC = "flac"


class TranscriptFormat(str, Enum):
    TXT = "txt"
    SRT = "srt"
    VTT = "vtt"
    JSON = "json"


# ── Processing Request ──────────────────────────────────

class ProcessingOptions(BaseModel):
    """All available processing toggles and parameters."""

    # Speech Editing & Cleanup
    remove_noise: bool = False
    noise_reduction_strength: float = Field(default=0.7, ge=0.0, le=1.0)

    remove_long_silences: bool = False
    silence_threshold_db: float = Field(default=-40, ge=-80, le=0)
    min_silence_duration_ms: int = Field(default=1000, ge=100, le=10000)

    mute_segments: bool = False  # Replace with silence instead of cut

    remove_mouth_sounds: bool = False
    mouth_sound_sensitivity: float = Field(default=0.5, ge=0.0, le=1.0)

    eliminate_hesitations: bool = False
    remove_stuttering: bool = False

    remove_filler_words: bool = False
    custom_filler_words: Optional[List[str]] = None

    remove_breaths: bool = False
    breath_reduction_strength: float = Field(default=0.8, ge=0.0, le=1.0)

    # Audio Enhancement
    studio_sound: bool = False
    auto_eq: bool = False
    normalize: bool = False
    target_loudness_lufs: float = Field(default=-16.0, ge=-30.0, le=-5.0)
    keep_music: bool = False

    # Specific Noise Removal
    wind_noise_remover: bool = False
    buzzing_noise_remover: bool = False
    buzz_frequency_hz: float = Field(default=50.0, ge=30, le=120)
    static_noise_remover: bool = False
    reverb_echo_remover: bool = False

    # Audio Super-Resolution
    frequency_restoration: bool = False
    target_sample_rate: int = Field(default=48000, ge=16000, le=96000)

    # Smart Mode
    smart_mode: bool = False
    content_type: Optional[ContentType] = None

    # Output
    output_format: OutputFormat = OutputFormat.WAV
    output_profile: Optional[str] = Field(default=None, max_length=64)
    output_profile_overrides: Dict[str, Any] = Field(default_factory=dict)


class ProcessingRequest(BaseModel):
    """Request to process an uploaded audio file."""
    file_id: str
    options: ProcessingOptions


# ── Transcription ──────────────────────────────────

class TranscriptionRequest(BaseModel):
    """Request to transcribe audio to text."""
    file_id: str
    language: Optional[str] = None  # Auto-detect if None
    output_format: TranscriptFormat = TranscriptFormat.TXT


class TranscriptionSegment(BaseModel):
    start: float
    end: float
    text: str
    confidence: float


class TranscriptionResponse(BaseModel):
    text: str
    language: str
    segments: List[TranscriptionSegment]
    duration: float


class SpeechEditorAnalyzeRequest(BaseModel):
    file_id: str
    language: Optional[str] = None
    custom_filler_words: Optional[List[str]] = None


class SpeechEditDecision(BaseModel):
    candidate_id: str = Field(min_length=1, max_length=64)
    decision: Literal["keep", "apply"]


class SpeechEditorUpdateRequest(BaseModel):
    revision: int = Field(ge=1)
    decisions: List[SpeechEditDecision]


class SpeechEditorRenderRequest(BaseModel):
    revision: int = Field(ge=1)
    output_format: OutputFormat = OutputFormat.WAV


class SpeechEditorManualEditRequest(BaseModel):
    revision: int = Field(ge=1)
    start: float = Field(ge=0.0)
    end: float = Field(gt=0.0)
    action: Literal["cut", "mute"]
    decision: Literal["keep", "apply"] = "keep"
    text: str = Field(default="", max_length=500)
    word_start: Optional[int] = Field(default=None, ge=0)
    word_end: Optional[int] = Field(default=None, ge=0)


class RevisionRequest(BaseModel):
    revision: int = Field(ge=1)


class RuntimePrivacySettingsRequest(BaseModel):
    external_services_allowed: bool = Field(strict=True)
    ollama_editorial_allowed: bool = Field(strict=True)
    trusted_lan_processing_allowed: bool = Field(strict=True)


class ProjectCapsuleRequest(BaseModel):
    output_version: Literal["processed", "speech_edit"] = "processed"
    revision: Optional[str] = Field(default=None, max_length=64)
    format: Optional[OutputFormat] = None
    include_source: bool = False
    target_id: str = Field(default="podcast", min_length=1, max_length=64)


class BlindABReviewRequest(BaseModel):
    output_version: Literal["processed", "speech_edit"] = "processed"
    revision: Optional[str] = Field(default=None, max_length=64)
    selected_version: Literal["original", "processed", "no_difference"]
    blind_slot: Literal["A", "B", "tie"]
    target_id: str = Field(default="podcast", min_length=1, max_length=64)


# ── Text-to-Speech ──────────────────────────────────

class TTSVoice(BaseModel):
    id: str
    name: str
    language: str
    gender: str
    description: str


class TTSRequest(BaseModel):
    """Request to generate speech from text."""
    text: str
    voice_id: Optional[str] = "default"
    language: str = "en"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch: float = Field(default=1.0, ge=0.5, le=2.0)
    warmth: float = Field(default=0.5, ge=0.0, le=1.0)
    style: str = "neutral"  # neutral, expressive, calm, energetic
    clone_voice_file_id: Optional[str] = None  # Deprecated one-shot upload hook
    voice_profile_id: Optional[str] = None  # Persistent personal voice profile
    expressive: bool = False  # Use Gemma to rewrite text for natural delivery
    engine: str = "auto"  # "edge", "kokoro", "voice-clone", or "auto"


class VoiceProfileSettings(BaseModel):
    language: str = Field(default="it", min_length=2, max_length=16)
    style: Literal["neutral", "expressive", "calm", "energetic"] = "neutral"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch: float = Field(default=1.0, ge=0.5, le=2.0)
    warmth: float = Field(default=0.5, ge=0.0, le=1.0)


class VoiceProfileEnrollRequest(BaseModel):
    file_id: str
    name: str = Field(min_length=1, max_length=80)
    profile_id: Optional[str] = None
    transcript: str = Field(default="", max_length=20000)
    consent_confirmed: bool = False
    settings: VoiceProfileSettings = Field(default_factory=VoiceProfileSettings)


class VoiceProfileUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    settings: VoiceProfileSettings


class TTSRewriteRequest(BaseModel):
    """Request to rewrite text for expressive spoken delivery using Gemma."""
    text: str
    language: str = "en"
    style: str = "neutral"


class TTSResponse(BaseModel):
    file_id: str
    file_url: str
    duration: float


# ── File Info ──────────────────────────────────

class FileInfo(BaseModel):
    file_id: str
    filename: str
    size_bytes: int
    duration_seconds: float
    sample_rate: int
    channels: int
    format: str
    bitrate: Optional[int] = None
    waveform_url: str


# ── Processing Progress ──────────────────────────────────

class ProgressUpdate(BaseModel):
    file_id: str
    step: str
    progress: float  # 0.0 to 1.0
    message: str
    status: str  # "processing", "completed", "error"


# ── Smart Mode ──────────────────────────────────

class SmartModeResult(BaseModel):
    detected_type: ContentType
    confidence: float
    suggested_options: ProcessingOptions
    description: str
