"""Non-destructive speech edit detection, persistence and rendering."""
from __future__ import annotations

import json
import re
import threading
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from app.config import OUTPUT_DIR
from app.services.speech_cleanup import (
    DEFAULT_FILLER_WORDS,
    detect_breaths,
    detect_mouth_sounds,
)


EDL_SCHEMA_VERSION = 1
VALID_DECISIONS = {"keep", "apply"}
MAX_CANDIDATES_PER_TYPE = 250
MAX_HISTORY_ENTRIES = 50
_EDL_LOCK = threading.RLock()


def speech_edl_path(file_id: str) -> Path:
    return OUTPUT_DIR / f"{file_id}_speech_edl.json"


def speech_edl_history_path(file_id: str) -> Path:
    return OUTPUT_DIR / f"{file_id}_speech_edl_history.json"


def _normalize_word(word: str) -> str:
    return re.sub(r"[^\wàèéìòù']+", "", word.lower(), flags=re.UNICODE)


def _flatten_words(transcription: dict[str, Any]) -> list[dict[str, Any]]:
    words: list[dict[str, Any]] = []
    for segment in transcription.get("segments", []):
        for item in segment.get("words", []):
            normalized = _normalize_word(str(item.get("word", "")))
            if not normalized:
                continue
            words.append({
                "index": len(words),
                "word": normalized,
                "display_word": str(item.get("word", "")).strip(),
                "start": max(0.0, float(item.get("start", 0.0))),
                "end": max(0.0, float(item.get("end", 0.0))),
                "probability": float(np.clip(item.get("probability", 0.0), 0.0, 1.0)),
            })
    words.sort(key=lambda item: (item["start"], item["end"]))
    for index, item in enumerate(words):
        item["index"] = index
    return words


def _candidate(
    edit_type: str,
    start: float,
    end: float,
    *,
    label: str,
    confidence: float,
    detector: str,
    action: str,
    evidence: str,
    text: str = "",
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    start = max(0.0, float(start))
    end = max(start, float(end))
    return {
        "id": "",
        "type": edit_type,
        "label": label,
        "start": round(start, 3),
        "end": round(end, 3),
        "duration": round(end - start, 3),
        "confidence": round(float(np.clip(confidence, 0.0, 1.0)), 3),
        "detector": detector,
        "action": action,
        "decision": "keep",
        "text": text,
        "evidence": evidence,
        "parameters": parameters or {},
    }


def detect_text_edits(
    words: list[dict[str, Any]],
    custom_fillers: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Detect filler words, repeated words and excess intra-speech pauses."""
    normalized_fillers = {_normalize_word(item) for item in DEFAULT_FILLER_WORDS if " " not in item}
    normalized_fillers.update(_normalize_word(item) for item in (custom_fillers or []) if " " not in item)
    phrase_fillers = [
        tuple(_normalize_word(part) for part in item.split())
        for item in [*DEFAULT_FILLER_WORDS, *(custom_fillers or [])]
        if " " in item
    ]
    candidates: list[dict[str, Any]] = []

    for index, word in enumerate(words):
        if word["word"] in normalized_fillers:
            candidates.append(_candidate(
                "filler", word["start"], word["end"],
                label="Filler word",
                confidence=word["probability"],
                detector="faster-whisper-word-timestamps",
                action="cut",
                text=word["display_word"],
                evidence=f"Recognized as filler with probability {word['probability']:.0%}.",
            ))

        for phrase in phrase_fillers:
            phrase_words = tuple(item["word"] for item in words[index:index + len(phrase)])
            if phrase_words == phrase:
                phrase_slice = words[index:index + len(phrase)]
                probability = min(item["probability"] for item in phrase_slice)
                candidates.append(_candidate(
                    "filler", phrase_slice[0]["start"], phrase_slice[-1]["end"],
                    label="Filler phrase",
                    confidence=probability,
                    detector="faster-whisper-word-timestamps",
                    action="cut",
                    text=" ".join(item["display_word"] for item in phrase_slice),
                    evidence=f"Recognized as filler phrase with minimum word probability {probability:.0%}.",
                ))

        if index + 1 < len(words):
            following = words[index + 1]
            gap = following["start"] - word["end"]
            if word["word"] == following["word"] and len(word["word"]) > 1 and gap <= 0.8:
                confidence = min(word["probability"], following["probability"])
                candidates.append(_candidate(
                    "repetition", word["start"], word["end"],
                    label="Repeated word",
                    confidence=confidence,
                    detector="faster-whisper-adjacent-word-match",
                    action="cut",
                    text=word["display_word"],
                    evidence=f"The same word occurs again after {max(0.0, gap):.2f}s.",
                ))

            if 0.5 < gap < 2.0:
                retained_gap = 0.15
                candidates.append(_candidate(
                    "hesitation", word["end"] + retained_gap, following["start"],
                    label="Excess pause",
                    confidence=min(0.9, 0.58 + (gap - 0.5) * 0.2),
                    detector="word-gap-analysis",
                    action="cut",
                    text=f"{word['display_word']} ... {following['display_word']}",
                    evidence=f"Detected a {gap:.2f}s gap; the proposal preserves {retained_gap:.2f}s.",
                    parameters={"original_gap_seconds": round(gap, 3), "retained_gap_seconds": retained_gap},
                ))

    return candidates


def detect_acoustic_edits(audio: np.ndarray, sr: int) -> list[dict[str, Any]]:
    """Detect breath and mouth-click candidates without modifying the source."""
    candidates: list[dict[str, Any]] = []
    for start_sample, end_sample in detect_breaths(audio, sr, sensitivity=0.7)[:MAX_CANDIDATES_PER_TYPE]:
        duration = (end_sample - start_sample) / sr
        confidence = 0.52 + min(0.22, max(0.0, 0.7 - abs(duration - 0.45)) * 0.25)
        candidates.append(_candidate(
            "breath", start_sample / sr, end_sample / sr,
            label="Possible breath",
            confidence=confidence,
            detector="spectral-breath-heuristic",
            action="mute",
            evidence=f"Low-energy spectral event lasting {duration:.2f}s.",
            parameters={"fade_ms": 20},
        ))

    for start_sample, end_sample in detect_mouth_sounds(audio, sr, sensitivity=0.5)[:MAX_CANDIDATES_PER_TYPE]:
        duration = (end_sample - start_sample) / sr
        candidates.append(_candidate(
            "mouth_click", start_sample / sr, end_sample / sr,
            label="Possible mouth click",
            confidence=0.48,
            detector="spectral-flux-heuristic",
            action="mute",
            evidence=f"Short high-frequency transient lasting {duration * 1000:.0f}ms.",
            parameters={"fade_ms": 3},
        ))
    return candidates


def _summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(item["type"] for item in candidates)
    selected = [item for item in candidates if item["decision"] == "apply"]
    return {
        "total_candidates": len(candidates),
        "selected_candidates": len(selected),
        "candidate_duration_seconds": round(sum(item["duration"] for item in candidates), 3),
        "selected_duration_seconds": round(sum(item["duration"] for item in selected), 3),
        "by_type": dict(sorted(counts.items())),
    }


def build_speech_edl(
    *,
    file_id: str,
    audio: np.ndarray,
    sr: int,
    transcription: dict[str, Any],
    custom_fillers: Iterable[str] | None = None,
) -> dict[str, Any]:
    words = _flatten_words(transcription)
    candidates = detect_text_edits(words, custom_fillers) + detect_acoustic_edits(audio, sr)
    candidates.sort(key=lambda item: (item["start"], item["end"], item["type"]))
    candidates = candidates[:1000]
    for index, item in enumerate(candidates, start=1):
        item["id"] = f"edit-{index:04d}"

    edl = {
        "schema_version": EDL_SCHEMA_VERSION,
        "file_id": file_id,
        "revision": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "duration_seconds": round(len(audio) / sr, 3),
            "sample_rate": sr,
            "language": transcription.get("language", ""),
            "transcription_engine": "faster-whisper-word-timestamps",
        },
        "transcript": transcription.get("text", ""),
        "source_words": words,
        "candidates": candidates,
        "summary": _summary(candidates),
        "history": {"can_undo": False, "can_redo": False, "position": 1, "total": 1},
        "policy": {
            "non_destructive": True,
            "default_decision": "keep",
            "manual_review_required": True,
            "limitations": [
                "Breath and mouth-click detections are heuristic candidates.",
                "Repeated-word detection does not identify every syllabic stutter.",
            ],
        },
    }
    with _EDL_LOCK:
        save_speech_edl(edl)
        _write_history(file_id, {"cursor": 0, "entries": [_capture_state(edl)]})
    return edl


def save_speech_edl(edl: dict[str, Any]) -> None:
    destination = speech_edl_path(edl["file_id"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(edl, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(destination)


def load_speech_edl(file_id: str) -> dict[str, Any] | None:
    with _EDL_LOCK:
        return _load_speech_edl_unlocked(file_id)


def _load_speech_edl_unlocked(file_id: str) -> dict[str, Any] | None:
    try:
        return json.loads(speech_edl_path(file_id).read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def _capture_state(edl: dict[str, Any]) -> dict[str, Any]:
    return {
        "decisions": {
            item["id"]: item.get("decision", "keep")
            for item in edl.get("candidates", [])
        },
        "manual_candidates": [
            dict(item) for item in edl.get("candidates", [])
            if item.get("detector") == "manual-transcript-selection"
        ],
    }


def _load_history(file_id: str, edl: dict[str, Any]) -> dict[str, Any]:
    try:
        history = json.loads(speech_edl_history_path(file_id).read_text(encoding="utf-8"))
        if not isinstance(history.get("entries"), list) or not history["entries"]:
            raise ValueError("empty history")
        history["cursor"] = max(0, min(int(history.get("cursor", 0)), len(history["entries"]) - 1))
        return history
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"cursor": 0, "entries": [_capture_state(edl)]}


def _write_history(file_id: str, history: dict[str, Any]) -> None:
    destination = speech_edl_history_path(file_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(destination)


def _set_history_status(edl: dict[str, Any], history: dict[str, Any]) -> None:
    cursor = int(history["cursor"])
    total = len(history["entries"])
    edl["history"] = {
        "can_undo": cursor > 0,
        "can_redo": cursor < total - 1,
        "position": cursor + 1,
        "total": total,
    }


def _append_history(edl: dict[str, Any], history: dict[str, Any]) -> None:
    entries = history["entries"][:int(history["cursor"]) + 1]
    entries.append(_capture_state(edl))
    if len(entries) > MAX_HISTORY_ENTRIES:
        entries = entries[-MAX_HISTORY_ENTRIES:]
    history["entries"] = entries
    history["cursor"] = len(entries) - 1
    _set_history_status(edl, history)


def _apply_history_state(edl: dict[str, Any], snapshot: dict[str, Any]) -> None:
    auto_candidates = [
        item for item in edl.get("candidates", [])
        if item.get("detector") != "manual-transcript-selection"
    ]
    candidates = auto_candidates + [dict(item) for item in snapshot.get("manual_candidates", [])]
    decisions = snapshot.get("decisions", {})
    for item in candidates:
        item["decision"] = decisions.get(item["id"], "keep")
    candidates.sort(key=lambda item: (item["start"], item["end"], item["id"]))
    edl["candidates"] = candidates
    edl["summary"] = _summary(candidates)


def _commit(edl: dict[str, Any], history: dict[str, Any]) -> dict[str, Any]:
    edl["revision"] = int(edl["revision"]) + 1
    edl["updated_at"] = datetime.now(timezone.utc).isoformat()
    edl["summary"] = _summary(edl["candidates"])
    _append_history(edl, history)
    save_speech_edl(edl)
    _write_history(edl["file_id"], history)
    return edl


def update_speech_edl(
    edl: dict[str, Any],
    decisions: Iterable[dict[str, str]],
    expected_revision: int,
) -> dict[str, Any]:
    with _EDL_LOCK:
        current = _load_speech_edl_unlocked(edl["file_id"])
        if current is None:
            raise ValueError("Speech edit list is unavailable")
        if int(current.get("revision", 0)) != int(expected_revision):
            raise ValueError("Speech edit list changed; reload it before saving decisions")
        history = _load_history(current["file_id"], current)
        candidates = {item["id"]: item for item in current["candidates"]}
        changed = False
        for change in decisions:
            candidate_id = change.get("candidate_id", "")
            decision = change.get("decision", "")
            if candidate_id not in candidates:
                raise KeyError(f"Unknown speech edit candidate: {candidate_id}")
            if decision not in VALID_DECISIONS:
                raise ValueError(f"Invalid speech edit decision: {decision}")
            changed = changed or candidates[candidate_id].get("decision") != decision
            candidates[candidate_id]["decision"] = decision
        if not changed:
            _set_history_status(current, history)
            return current
        return _commit(current, history)


def add_manual_speech_edit(
    edl: dict[str, Any],
    edit: dict[str, Any],
    expected_revision: int,
) -> dict[str, Any]:
    """Add a transcript-linked proposal without touching source audio."""
    with _EDL_LOCK:
        current = _load_speech_edl_unlocked(edl["file_id"])
        if current is None:
            raise ValueError("Speech edit list is unavailable")
        if int(current.get("revision", 0)) != int(expected_revision):
            raise ValueError("Speech edit list changed; reload it before adding an edit")
        start = float(edit["start"])
        end = float(edit["end"])
        duration = float(current.get("source", {}).get("duration_seconds", 0.0))
        if end <= start or end > duration + 0.001:
            raise ValueError("Manual edit range is outside the source timeline")
        if edit["action"] not in {"cut", "mute"}:
            raise ValueError("Manual edit action must be cut or mute")
        history = _load_history(current["file_id"], current)
        numeric_ids = [
            int(match.group(1)) for item in current["candidates"]
            if (match := re.fullmatch(r"edit-([0-9]{4})", str(item.get("id", ""))))
        ]
        next_id = max(numeric_ids, default=0) + 1
        if next_id > 9999:
            raise ValueError("Speech edit list reached its candidate limit")
        candidate = _candidate(
            "manual_selection",
            start,
            end,
            label="Manual transcript selection",
            confidence=1.0,
            detector="manual-transcript-selection",
            action=edit["action"],
            text=str(edit.get("text", "")),
            evidence="Time range selected explicitly by the user from the local transcript.",
            parameters={
                "word_start": edit.get("word_start"),
                "word_end": edit.get("word_end"),
                "fade_ms": 20 if edit["action"] == "mute" else 30,
            },
        )
        candidate["id"] = f"edit-{next_id:04d}"
        candidate["decision"] = edit.get("decision", "keep")
        current["candidates"].append(candidate)
        current["candidates"].sort(key=lambda item: (item["start"], item["end"], item["id"]))
        return _commit(current, history)


def navigate_speech_edl_history(
    edl: dict[str, Any], expected_revision: int, direction: str,
) -> dict[str, Any]:
    with _EDL_LOCK:
        current = _load_speech_edl_unlocked(edl["file_id"])
        if current is None:
            raise ValueError("Speech edit list is unavailable")
        if int(current.get("revision", 0)) != int(expected_revision):
            raise ValueError("Speech edit list changed; reload it before navigating history")
        history = _load_history(current["file_id"], current)
        delta = -1 if direction == "undo" else 1
        target = int(history["cursor"]) + delta
        if target < 0 or target >= len(history["entries"]):
            raise ValueError(f"Nothing to {direction}")
        history["cursor"] = target
        _apply_history_state(current, history["entries"][target])
        current["revision"] = int(current["revision"]) + 1
        current["updated_at"] = datetime.now(timezone.utc).isoformat()
        _set_history_status(current, history)
        save_speech_edl(current)
        _write_history(current["file_id"], history)
        return current


def _render_equal_power_cuts(
    audio: np.ndarray,
    ranges: list[tuple[int, int]],
    crossfade_samples: int,
) -> np.ndarray:
    """Remove original-coordinate ranges with equal-power splice joins."""
    if not ranges:
        return audio
    normalized = sorted(
        (max(0, start), min(len(audio), end))
        for start, end in ranges
        if end > start
    )
    merged: list[tuple[int, int]] = []
    for start, end in normalized:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    result = audio
    for start, end in reversed(merged):
        left = result[:start]
        right = result[end:]
        fade = min(crossfade_samples, len(left), len(right))
        if fade <= 1:
            result = np.concatenate((left, right))
            continue
        phase = np.linspace(0.0, np.pi / 2.0, fade, dtype=np.float32)
        joined = left[-fade:] * np.cos(phase) + right[:fade] * np.sin(phase)
        result = np.concatenate((left[:-fade], joined, right[fade:]))
    return result.astype(np.float32, copy=False)


def render_speech_edl(audio: np.ndarray, sr: int, edl: dict[str, Any]) -> np.ndarray:
    """Render approved decisions while preserving the original source file."""
    result = np.asarray(audio, dtype=np.float32).copy()
    approved = [item for item in edl.get("candidates", []) if item.get("decision") == "apply"]

    for item in approved:
        start = max(0, min(len(result), int(float(item["start"]) * sr)))
        end = max(start, min(len(result), int(float(item["end"]) * sr)))
        if end <= start:
            continue
        if item["action"] == "mute":
            requested_fade_ms = float(item.get("parameters", {}).get("fade_ms", 20))
            fade = min((end - start) // 2, max(1, int(sr * requested_fade_ms / 1000)))
            envelope = np.zeros(end - start, dtype=np.float32)
            if fade:
                envelope[:fade] = np.linspace(1.0, 0.0, fade)
                envelope[-fade:] = np.linspace(0.0, 1.0, fade)
            result[start:end] *= envelope

    cuts = [
        (int(float(item["start"]) * sr), int(float(item["end"]) * sr))
        for item in approved
        if item["action"] == "cut"
    ]
    if cuts:
        result = _render_equal_power_cuts(result, cuts, crossfade_samples=max(1, int(sr * 0.03)))
    return result


def render_candidate_preview(
    audio: np.ndarray,
    sr: int,
    candidate: dict[str, Any],
    *,
    apply: bool,
    context_seconds: float = 0.8,
) -> np.ndarray:
    window_start = max(0.0, float(candidate["start"]) - context_seconds)
    window_end = min(len(audio) / sr, float(candidate["end"]) + context_seconds)
    preview = audio[int(window_start * sr):int(window_end * sr)].copy()
    if not apply:
        return preview
    local_candidate = dict(candidate)
    local_candidate["start"] = float(candidate["start"]) - window_start
    local_candidate["end"] = float(candidate["end"]) - window_start
    local_candidate["decision"] = "apply"
    return render_speech_edl(preview, sr, {"candidates": [local_candidate]})
