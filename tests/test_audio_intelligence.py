import unittest

import numpy as np

from app.services.audio_intelligence import analyze_audio_quality, build_processing_profiles
from app.services.smart_mode import get_dynamic_parameters


class AudioIntelligenceTests(unittest.TestCase):
    sample_rate = 16000

    def test_detects_clipping_and_low_bandwidth(self):
        timeline = np.arange(self.sample_rate * 2) / self.sample_rate
        audio = np.clip(2.2 * np.sin(2 * np.pi * 220 * timeline), -1.0, 1.0).astype(np.float32)

        result = analyze_audio_quality(audio, self.sample_rate)
        issue_ids = {item["id"] for item in result["issues"]}

        self.assertIn("clipping", issue_ids)
        self.assertEqual(result["engine"], "audio-intelligence-v1")
        self.assertTrue(result["local_only"])

    def test_broadband_noise_is_reported(self):
        rng = np.random.default_rng(42)
        audio = (rng.normal(0, 0.08, self.sample_rate * 3)).astype(np.float32)

        result = analyze_audio_quality(audio, self.sample_rate)

        self.assertIn("background_noise", {item["id"] for item in result["issues"]})
        self.assertLess(result["metrics"]["estimated_snr_db"], 16)

    def test_profiles_keep_destructive_edits_out_of_balanced_mode(self):
        diagnosis = {
            "issues": [
                {"id": "background_noise", "recommendation": "Reduce noise."},
                {"id": "excessive_silence", "recommendation": "Review silence."},
            ],
            "metrics": {
                "rms_dbfs": -30.0,
                "peak_dbfs": -5.0,
                "hum_50_ratio": 0.01,
                "hum_60_ratio": 0.02,
            },
        }
        capabilities = {
            "neural_denoise": False,
            "demucs_music_separation": False,
        }

        profiles = build_processing_profiles(diagnosis, "podcast", capabilities)

        self.assertTrue(profiles["balanced"]["options"]["remove_noise"])
        self.assertFalse(profiles["balanced"]["options"]["remove_long_silences"])
        self.assertFalse(profiles["balanced"]["options"]["remove_filler_words"])
        self.assertFalse(profiles["maximum"]["options"]["remove_long_silences"])
        self.assertFalse(profiles["maximum"]["options"]["remove_breaths"])
        self.assertFalse(profiles["maximum"]["options"]["remove_mouth_sounds"])

    def test_dynamic_tuning_is_deterministic_and_does_not_require_ollama(self):
        timeline = np.arange(self.sample_rate) / self.sample_rate
        audio = (0.1 * np.sin(2 * np.pi * 220 * timeline)).astype(np.float32)

        result = get_dynamic_parameters(audio, self.sample_rate, {"remove_noise": True})

        self.assertIn("remove_noise", result)
        self.assertIn("Deterministic", result["remove_noise"]["reason"])


if __name__ == "__main__":
    unittest.main()
