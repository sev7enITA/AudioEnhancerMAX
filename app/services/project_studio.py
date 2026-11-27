"""Local project revisions, portable assets and block-based Studio rendering."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import shutil
import threading
from typing import Annotated, Literal
from uuid import uuid4
import zipfile

import av
import numpy as np
import soundfile as sf
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from scipy.signal import butter, lfilter, sosfilt

from app.config import DATA_DIR, MAX_FILE_SIZE_MB, STUDIO_MEDIA_EXTENSIONS
from app.services.artifact_store import atomic_json, sha256_file


RATE = 48000
BLOCK = 65536
PEAK_FRAMES = 4096
MAX_SECONDS = 7200
MAX_HISTORY = 75
MEDIA_EXTENSIONS = STUDIO_MEDIA_EXTENSIONS
IDENTITY = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,64}$")]
SECONDS = Annotated[float, Field(ge=0, le=MAX_SECONDS, allow_inf_nan=False)]
DB_LOCK = threading.RLock()


class StudioModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StudioTrack(StudioModel):
    id: IDENTITY
    name: str = Field(min_length=1, max_length=80)
    muted: bool = False


class GainPoint(StudioModel):
    time: SECONDS
    db: float = Field(ge=-60, le=12)


class StudioClip(StudioModel):
    id: IDENTITY
    asset_id: IDENTITY
    track_id: IDENTITY
    start: SECONDS = 0
    in_point: SECONDS = 0
    out_point: SECONDS
    fade_in: SECONDS = 0
    fade_out: SECONDS = 0
    gain_db: float = Field(default=0, ge=-60, le=12)
    clarity: float = Field(default=0, ge=0, le=100)
    warmth: float = Field(default=0, ge=0, le=100)
    echo: float = Field(default=0, ge=0, le=100)
    eq_hz: float = Field(default=2200, ge=350, le=10000)
    ratio: float = Field(default=1, ge=1, le=8)
    threshold_db: float = Field(default=-18, ge=-60, le=0)
    effects_bypass: bool = False
    automation: list[GainPoint] = Field(default_factory=list, max_length=100)


class StudioMarker(StudioModel):
    time: SECONDS
    label: str = Field(min_length=1, max_length=80)


class StudioDocument(StudioModel):
    name: str = Field(min_length=1, max_length=80)
    tracks: list[StudioTrack] = Field(min_length=1, max_length=32)
    clips: list[StudioClip] = Field(default_factory=list, max_length=256)
    markers: list[StudioMarker] = Field(default_factory=list, max_length=128)
    bpm: float | None = Field(default=None, ge=30, le=300)
    aspect: Literal["wide", "tall"] = "wide"


class StaleStudioProject(ValueError):
    pass


class MissingStudioMedia(FileNotFoundError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def studio_root() -> Path:
    folder = DATA_DIR / "studio"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def project_path(project_id: str) -> Path:
    return studio_root() / project_id


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(studio_root() / "projects.sqlite3", timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, revision INTEGER NOT NULL, updated TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS revisions (
                project TEXT REFERENCES projects(id), revision INTEGER, document TEXT NOT NULL,
                label TEXT NOT NULL, time TEXT NOT NULL, PRIMARY KEY(project, revision)
            );
            CREATE TABLE IF NOT EXISTS assets (
                project TEXT REFERENCES projects(id), id TEXT, document TEXT NOT NULL,
                PRIMARY KEY(project, id)
            );
        """)
    except Exception:
        connection.close()
        raise
    return connection


def list_projects() -> list[dict]:
    with closing(connect()) as database:
        return [dict(row) for row in database.execute("SELECT * FROM projects ORDER BY updated DESC, id")]


def create_project(name: str) -> dict:
    if not name.strip():
        raise ValueError("Give the project a name.")
    project_id = uuid4().hex
    document = StudioDocument(name=name.strip(), tracks=[StudioTrack(id="track-1", name="Audio 1")])
    stamp = now()
    with DB_LOCK, closing(connect()) as database, database:
        database.execute("INSERT INTO projects VALUES (?, ?, 1, ?)", (project_id, document.name, stamp))
        database.execute("INSERT INTO revisions VALUES (?, 1, ?, ?, ?)",
                         (project_id, document.model_dump_json(), "Created project", stamp))
    return get_project(project_id)


def media_paths(project_id: str, item: dict) -> tuple[Path, Path]:
    directory = project_path(project_id) / "media"
    identity = item["id"]
    return directory / (identity + item["suffix"]), directory / (identity + "-pcm.wav")


def read_assets(connection: sqlite3.Connection, project_id: str) -> list[dict]:
    return [json.loads(row["document"]) for row in connection.execute(
        "SELECT document FROM assets WHERE project=? ORDER BY rowid", (project_id,)
    )]


def get_project(project_id: str, revision: int | None = None) -> dict:
    with DB_LOCK, closing(connect()) as database:
        project = database.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if project is None:
            raise FileNotFoundError("Project not found.")
        selected = project["revision"] if revision is None else revision
        row = database.execute("SELECT document FROM revisions WHERE project=? AND revision=?",
                               (project_id, selected)).fetchone()
        if row is None:
            raise FileNotFoundError("Project revision not found.")
        assets = read_assets(database, project_id)
        history = [dict(item) for item in database.execute(
            "SELECT revision,label,time FROM revisions WHERE project=? ORDER BY revision DESC", (project_id,)
        )]
    for item in assets:
        original, pcm = media_paths(project_id, item)
        item["available"] = original.is_file() and pcm.is_file()
        item["has_transcript"] = transcript_path(project_id, item["id"]).is_file()
    return {"id": project_id, "revision": selected, **StudioDocument.model_validate_json(row["document"]).model_dump(),
            "assets": assets, "history": history}


def save_project(project_id: str, base_revision: int, document: StudioDocument, label: str) -> dict:
    with DB_LOCK, closing(connect()) as database, database:
        row = database.execute("SELECT revision FROM projects WHERE id=?", (project_id,)).fetchone()
        if row is None:
            raise FileNotFoundError("Project not found.")
        if row["revision"] != base_revision:
            raise StaleStudioProject("The project changed in another window. Reload the latest version.")
        durations = {item["id"]: item["duration"] for item in read_assets(database, project_id)}
        tracks = {track.id for track in document.tracks}
        if len(tracks) != len(document.tracks) or len({clip.id for clip in document.clips}) != len(document.clips):
            raise ValueError("Track and clip identifiers must be unique.")
        for clip in document.clips:
            length = clip.out_point - clip.in_point
            if (clip.track_id not in tracks or clip.asset_id not in durations or length < 0.01
                    or clip.out_point > durations.get(clip.asset_id, 0) + 1 / RATE
                    or clip.start + length > MAX_SECONDS
                    or max(clip.fade_in, clip.fade_out) > length + 1 / RATE
                    or any(point.time > length + 1 / RATE for point in clip.automation)):
                raise ValueError("A clip goes outside its media, track or project limits.")
        stamp = now()
        next_revision = base_revision + 1
        database.execute("INSERT INTO revisions VALUES (?, ?, ?, ?, ?)",
                         (project_id, next_revision, document.model_dump_json(), label, stamp))
        database.execute("UPDATE projects SET name=?, revision=?, updated=? WHERE id=?",
                         (document.name, next_revision, stamp, project_id))
        database.execute("DELETE FROM revisions WHERE project=? AND revision<=?",
                         (project_id, next_revision - MAX_HISTORY))
    return get_project(project_id)


def restore_project(project_id: str, base_revision: int, revision: int) -> dict:
    restored = get_project(project_id, revision)
    payload = {field: restored[field] for field in StudioDocument.model_fields}
    return save_project(project_id, base_revision, StudioDocument.model_validate(payload), f"Restored revision {revision}")


def read_asset(project_id: str, asset_id: str) -> dict:
    with closing(connect()) as database:
        row = database.execute("SELECT document FROM assets WHERE project=? AND id=?",
                               (project_id, asset_id)).fetchone()
    if row is None:
        raise FileNotFoundError("Asset not found.")
    return json.loads(row["document"])


def copy_recording(source, destination: Path) -> str:
    digest = hashlib.sha256()
    size = 0
    with destination.open("wb") as stream:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            size += len(chunk)
            if size > MAX_FILE_SIZE_MB * 1024 * 1024:
                raise ValueError(f"Media exceeds the {MAX_FILE_SIZE_MB} MB import limit.")
            stream.write(chunk)
            digest.update(chunk)
    if size == 0:
        raise ValueError("The file is empty.")
    return digest.hexdigest()


def prepare_audio(source: Path, destination: Path) -> dict:
    """Decode by frame into reusable PCM and produce peak buckets in one pass."""
    peaks = []
    pending = np.empty(0, dtype=np.float32)
    count = 0
    try:
        with av.open(str(source), mode="r") as container:
            stream = next(iter(container.streams.audio), None)
            if stream is None:
                raise ValueError("This media has no supported audio track.")
            video = any(not bool(track.disposition & av.stream.Disposition.attached_pic)
                        for track in container.streams.video)
            resampler = av.AudioResampler(format="fltp", layout="stereo", rate=RATE)
            with sf.SoundFile(destination, mode="w", samplerate=RATE, channels=2, format="WAV", subtype="PCM_24") as output:
                for frame in container.decode(stream):
                    count, pending = append_pcm(resampler.resample(frame), output, count, pending, peaks)
                count, pending = append_pcm(resampler.resample(None), output, count, pending, peaks)
    except av.error.FFmpegError as exc:
        raise ValueError("Could not decode this media as audio.") from exc
    if count < RATE // 100:
        raise ValueError("The source contains less than 10 ms of audio.")
    if pending.size:
        peaks.append(float(pending.max()))
    factor = max(1, math.ceil(len(peaks) / 4000))
    return {"duration": count / RATE, "video": video,
            "peaks": [round(float(max(peaks[index:index + factor])), 4) for index in range(0, len(peaks), factor)]}


def append_pcm(frames, output, count, pending, peaks):
    for frame in frames or ():
        samples = frame.to_ndarray()
        if not np.isfinite(samples).all():
            raise ValueError("The source contains invalid audio samples.")
        count += samples.shape[1]
        if count > RATE * MAX_SECONDS:
            raise ValueError("A Studio source can contain up to two hours of audio.")
        output.write(samples.T)
        levels = np.concatenate((pending, np.max(np.abs(samples), axis=0)))
        full = len(levels) // PEAK_FRAMES * PEAK_FRAMES
        if full:
            peaks.extend(np.clip(levels[:full].reshape(-1, PEAK_FRAMES).max(axis=1), 0, 1))
        pending = levels[full:]
    return count, pending


def import_asset(project_id: str, filename: str, source, relink_id: str | None = None) -> dict:
    state = get_project(project_id)
    old = read_asset(project_id, relink_id) if relink_id else None
    if old is None and len(state["assets"]) >= 256:
        raise ValueError("A Studio project can contain up to 256 media sources.")
    display = Path(filename or "audio").name[:160]
    suffix = old["suffix"] if old else Path(display).suffix.lower()
    if suffix not in MEDIA_EXTENSIONS:
        raise ValueError("Choose a supported audio or video file.")
    identity = old["id"] if old else uuid4().hex
    item = {"id": identity, "name": display, "suffix": suffix}
    original, pcm = media_paths(project_id, item)
    original.parent.mkdir(parents=True, exist_ok=True)
    nonce = uuid4().hex
    staged_original = original.with_name(f".{nonce}-original{suffix}")
    staged_pcm = pcm.with_name(f".{nonce}-pcm.wav")
    try:
        digest = copy_recording(source, staged_original)
        if old and digest != old["sha256"]:
            raise ValueError("This file differs from the original. Choose the exact missing source.")
        metadata = prepare_audio(staged_original, staged_pcm)
        item.update(metadata, sha256=digest, pcm_sha256=sha256_file(staged_pcm))
        if old:
            item = {**old, "pcm_sha256": item["pcm_sha256"]}
        serialized = json.dumps(item, ensure_ascii=False)
        try:
            with DB_LOCK, closing(connect()) as database, database:
                staged_original.replace(original)
                staged_pcm.replace(pcm)
                database.execute("INSERT OR REPLACE INTO assets VALUES (?, ?, ?)",
                                 (project_id, identity, serialized))
        except Exception:
            if not old:
                original.unlink(missing_ok=True)
                pcm.unlink(missing_ok=True)
            raise
    finally:
        staged_original.unlink(missing_ok=True)
        staged_pcm.unlink(missing_ok=True)
    return {**item, "available": True}


def available_paths(project_id: str, item: dict) -> tuple[Path, Path]:
    original, pcm = media_paths(project_id, item)
    if not original.is_file() or not pcm.is_file():
        raise MissingStudioMedia(f"Relink the missing source: {item['name']}")
    return original, pcm


def checked_pcm(project_id: str, item: dict) -> Path:
    original, pcm = available_paths(project_id, item)
    if sha256_file(original) != item["sha256"] or (
        item.get("pcm_sha256") and sha256_file(pcm) != item["pcm_sha256"]
    ):
        raise MissingStudioMedia(f"Relink the changed source: {item['name']}")
    return pcm


def clip_end(clip: dict) -> float:
    return clip["start"] + clip["out_point"] - clip["in_point"]


def crossfades(clips: list[dict]) -> dict:
    """Only edge-to-edge overlaps on the same track make equal-power crossfades."""
    changes = {clip["id"]: [] for clip in clips}
    for index, earlier in enumerate(clips):
        for later in clips[index + 1:]:
            start, end = later["start"], clip_end(earlier)
            if (earlier["track_id"] == later["track_id"] and earlier["start"] < start < end
                    and end < clip_end(later)):
                changes[earlier["id"]].append((start, end, False))
                changes[later["id"]].append((start, end, True))
    return changes


class ClipRender:
    """Read sequential clip blocks, keeping filter state between audio blocks."""
    def __init__(self, clip: dict, stream, crossfade):
        self.clip = clip
        self.stream = stream
        self.crossfade = crossfade
        self.first = round(clip["start"] * RATE)
        self.last = round(clip_end(clip) * RATE)
        self.filters = []
        if clip["clarity"] and not clip["effects_bypass"]:
            self.filters.append((butter(1, clip["eq_hz"], "highpass", fs=RATE, output="sos"), clip["clarity"] / 100 * 0.4, None))
        if clip["warmth"] and not clip["effects_bypass"]:
            self.filters.append((butter(1, 210, "lowpass", fs=RATE, output="sos"), clip["warmth"] / 100 * 0.5, None))
        self.delay = np.zeros((int(RATE * 0.035), 2), dtype=np.float32) if clip["echo"] and not clip["effects_bypass"] else None
        self.compressor_state = np.zeros(1)
        self.compressor_alpha = math.exp(-1 / (RATE * 0.025))

    def apply(self, mix, block_start, block_end):
        first, last = max(block_start, self.first), min(block_end, self.last)
        if last <= first:
            return
        clip = self.clip
        offset = first - self.first
        self.stream.seek(min(len(self.stream), round(clip["in_point"] * RATE) + offset))
        audio = self.stream.read(last - first, dtype="float32", always_2d=True, fill_value=0)
        for index, (sos, gain, state) in enumerate(self.filters):
            if state is None:
                state = np.zeros((len(sos), 2, 2))
            filtered, state = sosfilt(sos, audio, axis=0, zi=state)
            audio += (filtered * gain).astype(np.float32)
            self.filters[index] = (sos, gain, state)
        if self.delay is not None:
            # Subtract a bounded, short delayed copy. This control reduces
            # short reflections conservatively and does not invoke an AI model.
            extended = np.concatenate((self.delay, audio), axis=0)
            delayed = extended[:len(audio)]
            self.delay = extended[-len(self.delay):].copy()
            audio -= delayed * (clip["echo"] / 100 * 0.14)

        if clip["ratio"] > 1 and not clip["effects_bypass"]:
            levels, self.compressor_state = lfilter(
                [1 - self.compressor_alpha], [1, -self.compressor_alpha],
                np.max(np.abs(audio), axis=1), zi=self.compressor_state,
            )
            decibels = 20 * np.log10(np.maximum(levels, 1e-6))
            reduction = np.maximum(decibels - clip["threshold_db"], 0) * (1 - 1 / clip["ratio"])
            audio *= (10 ** (-reduction / 20))[:, None]

        relative = np.arange(offset, offset + len(audio)) / RATE
        absolute = relative + clip["start"]
        env = np.full(len(audio), 10 ** (clip["gain_db"] / 20))
        if clip["fade_in"]:
            env *= np.clip(relative / clip["fade_in"], 0, 1)
        if clip["fade_out"]:
            length = clip["out_point"] - clip["in_point"]
            env *= np.clip((length - relative) / clip["fade_out"], 0, 1)
        if clip["automation"]:
            points = sorted((point["time"], point["db"]) for point in clip["automation"])
            times, levels = zip(*points)
            env *= 10 ** (np.interp(relative, times, levels) / 20)
        for start, end, incoming in self.crossfade:
            mask = (absolute >= start) & (absolute < end)
            angle = (absolute[mask] - start) / (end - start) * np.pi / 2
            env[mask] *= np.sin(angle) if incoming else np.cos(angle)
        mix[first - block_start:last - block_start] += audio * env[:, None]


def render_audio(project: dict, destination: Path, fmt: str, progress) -> dict:
    """Mix into a private temporary path without holding the complete project in RAM."""
    from contextlib import ExitStack

    muted_tracks = {track["id"] for track in project["tracks"] if track["muted"]}
    clips = sorted(
        (clip for clip in project["clips"] if clip["track_id"] not in muted_tracks),
        key=lambda clip: clip["start"],
    )
    if not clips:
        raise ValueError("Add an unmuted audio clip before rendering.")
    assets = {item["id"]: item for item in project["assets"]}
    length = round(max(map(clip_end, clips)) * RATE)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{uuid4().hex}.{fmt}")
    peak = 0.0
    try:
        with ExitStack() as stack:
            fades = crossfades(clips)
            paths = {asset_id: checked_pcm(project["id"], assets[asset_id]) for asset_id in
                     {clip["asset_id"] for clip in clips}}
            streams = {key: stack.enter_context(sf.SoundFile(path)) for key, path in paths.items()}
            renderers = [ClipRender(clip, streams[clip["asset_id"]], fades[clip["id"]]) for clip in clips]
            output = stack.enter_context(sf.SoundFile(temporary, "w", RATE, 2, format=fmt.upper(), subtype="PCM_24"))
            for offset in range(0, length, BLOCK):
                stop = min(length, offset + BLOCK)
                mix = np.zeros((stop - offset, 2), dtype=np.float32)
                for renderer in renderers:
                    renderer.apply(mix, offset, stop)
                peak = max(peak, float(np.max(np.abs(mix))))
                output.write(np.clip(mix, -1, 1))
                progress(stop / length)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return {"duration": length / RATE, "peak": round(peak, 4), "clipped": peak > 1,
            "sha256": sha256_file(destination), "revision": project["revision"]}


def consolidate(project: dict, destination: Path, progress) -> dict:
    """Capture a portable folder as a ZIP, including the original byte-for-byte sources."""
    media = {item["id"]: item for item in project["assets"]}
    files = [(identity, available_paths(project["id"], item)[0]) for identity, item in media.items()]
    if sum(path.stat().st_size for _, path in files) > 4 * 1024 ** 3:
        raise ValueError("The project sources exceed the 4 GB package limit.")
    portable = {key: project[key] for key in ("id", "revision", *StudioDocument.model_fields)}
    portable["schema_version"] = 1
    portable["assets"] = [
        {key: media[identity][key] for key in ("id", "name", "sha256", "suffix", "duration", "video")}
        | {"file": f"Media/{path.name}"} for identity, path in files
    ]
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{uuid4().hex}.zip")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("AudioEnhancerMAX Project/Project.json", json.dumps(portable, indent=2, ensure_ascii=False))
            for index, (identity, path) in enumerate(files):
                if sha256_file(path) != media[identity]["sha256"]:
                    raise MissingStudioMedia(f"Relink the changed source: {media[identity]['name']}")
                archive.write(path, f"AudioEnhancerMAX Project/Media/{path.name}")
                progress((index + 1) / len(files))
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return {"sha256": sha256_file(destination), "revision": project["revision"]}


def detect_silences(project_id: str, asset_id: str, progress) -> dict:
    asset = read_asset(project_id, asset_id)
    _, path = available_paths(project_id, asset)
    regions = []
    began = None
    window = RATE // 20
    with sf.SoundFile(path) as stream:
        total = len(stream)
        for start in range(0, total, window):
            samples = stream.read(window, dtype="float32", always_2d=True)
            quiet = np.sqrt(np.mean(np.square(samples))) < 0.0063
            if quiet and began is None:
                began = start
            if not quiet and began is not None:
                if start - began >= RATE * 0.4:
                    regions.append([began / RATE, start / RATE])
                began = None
            progress(min(1, (start + window) / total))
    if began is not None and total - began >= RATE * 0.4:
        regions.append([began / RATE, total / RATE])
    return {"asset_id": asset_id, "regions": regions[:2000]}


def studio_transcript(project_id: str, asset_id: str, progress) -> dict:
    from app.services import transcription

    _, pcm = available_paths(project_id, read_asset(project_id, asset_id))
    cached = transcript_path(project_id, asset_id)
    if cached.is_file():
        return json.loads(cached.read_text(encoding="utf-8"))
    transcription._init_model()
    if transcription._model is None:
        raise ValueError("Install the local Whisper model in Settings before transcribing.")
    progress(0.15)
    result = transcription._transcribe_faster_whisper(pcm)
    segments = [{"start": part["start"], "end": part["end"], "text": part["text"]} for part in result["segments"]]
    data = {"asset_id": asset_id, "segments": segments, "language": result.get("language")}
    atomic_json(cached, data)
    return data


def isolation_repository() -> Path | None:
    import importlib.util

    location = DATA_DIR / "models" / "demucs"
    if location.is_dir() and any(location.glob("*.th")) and all(
        importlib.util.find_spec(name) is not None for name in ("demucs", "torch", "torchaudio")
    ):
        return location
    return None


def isolate_voice(project_id: str, asset_id: str, progress) -> dict:
    repository = isolation_repository()
    if repository is None:
        raise ValueError("Voice isolation requires a local Demucs runtime and the htdemucs model.")
    from demucs.apply import apply_model
    from demucs.pretrained import get_model
    import torch
    import torchaudio

    item = read_asset(project_id, asset_id)
    if item["duration"] > 180:
        raise ValueError("Voice isolation is limited to sources of up to three minutes.")
    _, pcm = available_paths(project_id, item)
    audio, sr = sf.read(pcm, dtype="float32", always_2d=True)
    model = get_model("htdemucs", repo=repository).eval()
    waveform = torch.from_numpy(audio.T.copy())
    if sr != model.samplerate:
        waveform = torchaudio.functional.resample(waveform, sr, model.samplerate)
    progress(0.25)
    with torch.inference_mode():
        separated = apply_model(model, waveform.unsqueeze(0), device="cpu", progress=False)
    vocal = separated[0, list(model.sources).index("vocals")].numpy().T
    progress(0.85)
    import tempfile

    with tempfile.TemporaryFile() as stream:
        sf.write(stream, vocal, model.samplerate, format="WAV", subtype="PCM_24")
        stream.seek(0)
        base = Path(item["name"]).stem[:140]
        return import_asset(project_id, f"{base} – voice.wav", stream)


def studio_subtitles(project: dict, asset_id: str, progress) -> dict:
    from app.services.transcription import format_as_srt

    words = studio_transcript(project["id"], asset_id, progress)
    parts = []
    muted = {track["id"] for track in project["tracks"] if track["muted"]}
    for clip in project["clips"]:
        if clip["asset_id"] != asset_id or clip["track_id"] in muted:
            continue
        for part in words["segments"]:
            first = max(clip["in_point"], part["start"])
            last = min(clip["out_point"], part["end"])
            if last > first:
                parts.append({"start": clip["start"] + first - clip["in_point"],
                              "end": clip["start"] + last - clip["in_point"], "text": part["text"]})
    parts.sort(key=lambda part: part["start"])
    return {"srt": format_as_srt(parts), "segments": words["segments"], "asset_id": asset_id}


def transcript_path(project_id: str, asset_id: str) -> Path:
    return project_path(project_id) / "transcripts" / f"{asset_id}.json"


def read_transcript(project_id: str, asset_id: str) -> dict:
    read_asset(project_id, asset_id)
    return json.loads(transcript_path(project_id, asset_id).read_text(encoding="utf-8"))


def reopen_portable(upload) -> dict:
    """Read only the expected members of a project package, without extracting paths."""
    root = "AudioEnhancerMAX Project/"
    project_id = None
    success = False
    try:
        with zipfile.ZipFile(upload) as archive:
            index = archive.getinfo(root + "Project.json")
            if index.file_size > 1024 * 1024:
                raise ValueError("The project manifest exceeds 1 MB.")
            with archive.open(index) as stream:
                data = json.loads(stream.read(1024 * 1024 + 1))
            if not isinstance(data, dict) or data.get("schema_version") != 1:
                raise ValueError("This archive is not a supported Studio project.")
            document = StudioDocument.model_validate({key: data[key] for key in StudioDocument.model_fields})
            active = {clip.asset_id for clip in document.clips}
            sources = {item["id"]: item for item in data["assets"] if isinstance(item, dict)}
            if not active.issubset(sources) or len(sources) > 256:
                raise ValueError("The package media list differs from the timeline.")
            total = 0
            members = {}
            for identity, entry in sources.items():
                filename = str(entry["file"])
                digest = str(entry["sha256"])
                suffix = str(entry["suffix"])
                if (filename != f"Media/{identity}{suffix}" or suffix not in MEDIA_EXTENSIONS
                        or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest)):
                    raise ValueError("The package contains an invalid source reference.")
                info = archive.getinfo(root + filename)
                if not 0 < info.file_size <= MAX_FILE_SIZE_MB * 1024 * 1024:
                    raise ValueError("A package source exceeds the import limit.")
                total += info.file_size
                if total > 4 * 1024 ** 3:
                    raise ValueError("The consolidated project exceeds 4 GB.")
                members[identity] = info
            created = create_project(document.name)
            project_id = created["id"]
            imported = {}
            for identity, entry in sources.items():
                with archive.open(members[identity]) as stream:
                    item = import_asset(project_id, Path(str(entry["name"])).stem + entry["suffix"], stream)
                if item["sha256"] != entry["sha256"]:
                    raise ValueError("A source differs from the SHA-256 recorded in the project.")
                imported[identity] = item["id"]
            for clip in document.clips:
                clip.asset_id = imported[clip.asset_id]
            restored = save_project(project_id, created["revision"], document, "Opened consolidated project")
            success = True
            return restored
    except (zipfile.BadZipFile, KeyError, TypeError, AttributeError) as exc:
        raise ValueError("The file is not a readable Studio project package.") from exc
    finally:
        if project_id and not success:
            with DB_LOCK, closing(connect()) as database, database:
                database.execute("DELETE FROM revisions WHERE project=?", (project_id,))
                database.execute("DELETE FROM assets WHERE project=?", (project_id,))
                database.execute("DELETE FROM projects WHERE id=?", (project_id,))
            shutil.rmtree(project_path(project_id), ignore_errors=True)
