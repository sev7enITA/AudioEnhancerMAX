import unittest
from unittest.mock import patch

from app.services.capability_registry import get_capability_registry


class CapabilityRegistryTests(unittest.TestCase):
    @patch("app.services.capability_registry._package_version", return_value="1.0")
    @patch("app.services.capability_registry._module_available")
    @patch("app.services.capability_registry.bundled_whisper_model_available", return_value=True)
    def test_registry_exposes_real_fallbacks(self, _bundled, module_available, _version):
        available = {"faster_whisper", "noisereduce", "edge_tts"}
        module_available.side_effect = lambda name: name in available

        registry = get_capability_registry()

        self.assertEqual(registry["schema_version"], 1)
        self.assertEqual(registry["engines"]["noise_reduction"]["id"], "spectral-gating")
        self.assertEqual(registry["engines"]["noise_reduction"]["mode"], "dsp-fallback")
        self.assertEqual(registry["engines"]["diarization"]["mode"], "heuristic-fallback")
        self.assertTrue(registry["transcription_bundled"])
        self.assertFalse(registry["neural_denoise"])


if __name__ == "__main__":
    unittest.main()
