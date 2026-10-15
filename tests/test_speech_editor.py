import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from app.services.speech_editor import (
    add_manual_speech_edit,
    build_speech_edl,
    detect_text_edits,
    navigate_speech_edl_history,
    render_candidate_preview,
    render_speech_edl,
    update_speech_edl,
)


class SpeechEditorTests(unittest.TestCase):
    def test_text_detection_creates_review_candidates(self):
        words = [
            {"word": "uh", "display_word": "Uh", "start": 0.0, "end": 0.2, "probability": 0.96},
            {"word": "io", "display_word": "io", "start": 0.35, "end": 0.55, "probability": 0.94},
            {"word": "io", "display_word": "io", "start": 0.65, "end": 0.85, "probability": 0.91},
            {"word": "parlo", "display_word": "parlo", "start": 1.65, "end": 1.95, "probability": 0.92},
        ]

        candidates = detect_text_edits(words)
        types = {item["type"] for item in candidates}

        self.assertIn("filler", types)
        self.assertIn("repetition", types)
        self.assertIn("hesitation", types)
        self.assertTrue(all(item["decision"] == "keep" for item in candidates))

    def test_revisioned_decisions_are_persisted_non_destructively(self):
        edl = {
            "file_id": "job",
            "revision": 1,
            "candidates": [{
                "id": "edit-0001",
                "type": "filler",
                "duration": 0.2,
                "decision": "keep",
            }],
        }

        with patch("app.services.speech_editor._load_speech_edl_unlocked", return_value=edl), \
             patch("app.services.speech_editor._load_history", return_value={"cursor": 0, "entries": [{"decisions": {"edit-0001": "keep"}, "manual_candidates": []}]}), \
             patch("app.services.speech_editor.save_speech_edl"), \
             patch("app.services.speech_editor._write_history"):
            updated = update_speech_edl(
                edl,
                [{"candidate_id": "edit-0001", "decision": "apply"}],
                expected_revision=1,
            )

        self.assertEqual(updated["revision"], 2)
        self.assertEqual(updated["candidates"][0]["decision"], "apply")
        self.assertEqual(updated["summary"]["selected_candidates"], 1)
    def test_manual_transcript_edit_can_be_undone_and_redone(self):
        sr = 1000
        audio = np.zeros(sr * 2, dtype=np.float32)
        transcription = {
            "text": "hello local world",
            "language": "en",
            "segments": [{"words": [
                {"word": "hello", "start": 0.1, "end": 0.4, "probability": 0.99},
                {"word": "local", "start": 0.5, "end": 0.8, "probability": 0.98},
                {"word": "world", "start": 0.9, "end": 1.2, "probability": 0.97},
            ]}],
        }

        with tempfile.TemporaryDirectory() as temporary, \
             patch("app.services.speech_editor.speech_edl_path", side_effect=lambda file_id: Path(temporary) / f"{file_id}.json"), \
             patch("app.services.speech_editor.speech_edl_history_path", side_effect=lambda file_id: Path(temporary) / f"{file_id}-history.json"), \
             patch("app.services.speech_editor.detect_acoustic_edits", return_value=[]):
            edl = build_speech_edl(file_id="manual", audio=audio, sr=sr, transcription=transcription)
            edited = add_manual_speech_edit(edl, {
                "start": 0.5, "end": 1.2, "action": "cut", "decision": "keep",
                "text": "local world", "word_start": 1, "word_end": 2,
            }, expected_revision=1)

            self.assertEqual(len(edited["candidates"]), 1)
            self.assertTrue(edited["history"]["can_undo"])
            undone = navigate_speech_edl_history(edited, edited["revision"], "undo")
            self.assertEqual(len(undone["candidates"]), 0)
            self.assertTrue(undone["history"]["can_redo"])
            redone = navigate_speech_edl_history(undone, undone["revision"], "redo")
            self.assertEqual(redone["candidates"][0]["text"], "local world")

    def test_render_applies_only_approved_candidates(self):
        sr = 1000
        audio = np.linspace(-0.5, 0.5, sr, dtype=np.float32)
        edl = {
            "candidates": [
                {"start": 0.2, "end": 0.4, "action": "cut", "decision": "apply", "parameters": {}},
                {"start": 0.5, "end": 0.6, "action": "cut", "decision": "keep", "parameters": {}},
            ]
        }

        rendered = render_speech_edl(audio, sr, edl)

        self.assertEqual(len(rendered), 770)
        self.assertEqual(len(audio), sr)

    def test_preview_can_compare_original_and_proposed_cut(self):
        sr = 1000
        audio = np.sin(np.arange(sr * 2) / 20).astype(np.float32)
        candidate = {
            "start": 0.8,
            "end": 1.0,
            "action": "cut",
            "decision": "keep",
            "parameters": {},
        }

        original = render_candidate_preview(audio, sr, candidate, apply=False, context_seconds=0.5)
        proposed = render_candidate_preview(audio, sr, candidate, apply=True, context_seconds=0.5)

        self.assertEqual(len(original) - len(proposed), 230)

    def test_mute_preserves_timeline_duration(self):
        sr = 1000
        audio = np.ones(sr, dtype=np.float32)
        edl = {"candidates": [{
            "start": 0.2,
            "end": 0.4,
            "action": "mute",
            "decision": "apply",
            "parameters": {"fade_ms": 20},
        }]}

        rendered = render_speech_edl(audio, sr, edl)

        self.assertEqual(len(rendered), len(audio))
        self.assertEqual(float(rendered[300]), 0.0)


if __name__ == "__main__":
    unittest.main()
