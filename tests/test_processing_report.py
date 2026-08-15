import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from app.services.processing_report import create_processing_report, quality_summary


class ProcessingReportTests(unittest.TestCase):
    def test_report_records_before_after_pipeline_and_privacy(self):
        sr = 16000
        timeline = np.arange(sr) / sr
        audio = (0.1 * np.sin(2 * np.pi * 220 * timeline)).astype(np.float32)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "job_processing_report.json"
            source = root / "source.wav"
            output = root / "output.wav"
            source.write_bytes(b"source")
            output.write_bytes(b"output")
            with patch("app.services.processing_report.report_path", return_value=destination):
                report = create_processing_report(
                    file_id="job",
                    app_version="test",
                    input_summary=quality_summary(audio, sr),
                    output_audio=audio * 0.8,
                    output_sample_rate=sr,
                    options={"normalize": True},
                    active_steps=["normalize"],
                    elapsed_seconds=0.5,
                    app_build="3.7.2",
                    source_path=source,
                    output_path=output,
                    compliance={"status": "pass", "target_id": "podcast"},
                )

            self.assertTrue(destination.is_file())
            self.assertFalse(report["privacy"]["audio_transmitted"])
            self.assertEqual(report["pipeline"][0]["step"], "normalize")
            self.assertIn("quality_score", report["input"])
            self.assertIn("quality_score", report["output"])
            self.assertEqual(report["schema_version"], 2)
            self.assertEqual(report["app_build"], "3.7.2")
            self.assertEqual(len(report["provenance"]["source"]["sha256"]), 64)
            self.assertEqual(report["delivery_compliance"]["status"], "pass")

    def test_report_discloses_trusted_lan_processing(self):
        sr = 8000
        audio = np.zeros(sr, dtype=np.float32)

        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "edge_processing_report.json"
            with patch("app.services.processing_report.report_path", return_value=destination):
                report = create_processing_report(
                    file_id="edge",
                    app_version="test",
                    input_summary=quality_summary(audio, sr),
                    output_audio=audio,
                    output_sample_rate=sr,
                    options={"normalize": True},
                    active_steps=["normalize"],
                    distributed_steps=["normalize"],
                )

            self.assertTrue(report["privacy"]["audio_transmitted"])
            self.assertEqual(report["privacy"]["processing_location"], "local-and-trusted-lan")
            self.assertEqual(report["pipeline"][0]["mode"], "trusted-lan")

    def test_report_records_reviewed_speech_edl(self):
        sr = 8000
        audio = np.zeros(sr, dtype=np.float32)
        edl = {
            "schema_version": 1,
            "revision": 3,
            "candidates": [
                {"id": "edit-0001", "type": "filler", "action": "cut", "decision": "apply"},
                {"id": "edit-0002", "type": "breath", "action": "mute", "decision": "keep"},
            ],
        }

        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "speech_processing_report.json"
            with patch("app.services.processing_report.report_path", return_value=destination):
                report = create_processing_report(
                    file_id="speech",
                    app_version="test",
                    input_summary=quality_summary(audio, sr),
                    output_audio=audio,
                    output_sample_rate=sr,
                    options={"operation": "speech_edl_render"},
                    active_steps=["speech_edl_render"],
                    speech_edl=edl,
                )

            self.assertEqual(report["speech_edits"]["approved_count"], 1)
            self.assertEqual(report["speech_edits"]["approved_by_type"], {"filler": 1})
            self.assertEqual(report["pipeline"][0]["mode"], "reviewed-local")


if __name__ == "__main__":
    unittest.main()
