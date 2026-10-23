"""Bounded text-only inputs for the music brief assistant."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MusicSection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Literal["Intro", "Verse", "Pre-Chorus", "Chorus", "Bridge", "Instrumental", "Main", "Outro"]
    direction: str = Field(default="", max_length=400)

    @field_validator("direction")
    @classmethod
    def trim_direction(cls, value: str) -> str:
        return value.strip()


class MusicBriefRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = Field(min_length=1, max_length=3000)
    preset_id: str = Field(default="podcast_intro", min_length=1, max_length=64)
    style: str = Field(default="", max_length=120)
    secondary_style: str = Field(default="", max_length=120)
    instrumental: bool = Field(default=True, strict=True)
    bpm: int | None = Field(default=None, ge=20, le=240, strict=True)
    duration_seconds: int = Field(default=30, ge=5, le=300, strict=True)
    instruments: str = Field(default="", max_length=500)
    exclusions: str = Field(default="", max_length=500)
    sections: list[MusicSection] = Field(
        default_factory=lambda: [MusicSection(name=name) for name in ("Intro", "Main", "Outro")],
        min_length=1, max_length=12,
    )
    # Deliberately do not normalize lyrics: they are a separate, source-preserving input.
    lyrics: str = Field(default="", max_length=8000)

    @field_validator("description", "preset_id", "style", "secondary_style", "instruments", "exclusions")
    @classmethod
    def trim_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("description")
    @classmethod
    def require_description(cls, value: str) -> str:
        if not value:
            raise ValueError("Describe the music before building a brief")
        return value


class MusicRefineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    brief: MusicBriefRequest
    caption: str = Field(min_length=1, max_length=16000)

    @field_validator("caption")
    @classmethod
    def require_caption(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Build a music brief before requesting suggestions")
        return value
