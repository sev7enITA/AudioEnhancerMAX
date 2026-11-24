import unittest
from unittest.mock import patch

import numpy as np

from app.services.tts import find_local_ollama_model, synthesize_speech


class PersonalVoiceTTSTests(unittest.TestCase):
    def test_personal_profile_takes_precedence_over_builtin_voice(self):
        generated = np.linspace(-0.1, 0.1, 2400, dtype=np.float32)
        clone_metadata = {
            "engine": "future_mmv_engine",
            "engine_version": "9.1",
            "execution": "local-metal",
            "voice_profile_id": "voice_me",
            "voice_profile_name": "My Voice",
        }
        with patch(
            "app.services.voice_profiles.synthesize_voice_profile",
            return_value=(generated, 24000, clone_metadata),
        ), patch("app.services.tts._synthesize_macos") as system_voice, patch(
            "app.services.tts._apply_warmth", side_effect=lambda audio, *_: audio
        ):
            audio, sr, metadata = synthesize_speech(
                "Personal speech",
                voice_id="it_elsa",
                voice_profile_id="voice_me",
                engine="voice-clone",
            )

        system_voice.assert_not_called()
        np.testing.assert_array_equal(audio, generated)
        self.assertEqual(sr, 24000)
        self.assertEqual(metadata["engine"], "future_mmv_engine")
        self.assertEqual(metadata["voice_profile_name"], "My Voice")
        self.assertEqual(metadata["execution"], "local-metal")

    def test_legacy_cloud_request_is_rejected_before_any_synthesis_or_rewrite(self):
        with patch("app.services.tts.rewrite_expressive") as rewrite, patch(
            "app.services.tts._synthesize_macos"
        ) as system_voice:
            with self.assertRaisesRegex(ValueError, "generates speech locally"):
                synthesize_speech("Private script", engine="edge", voice_id="it_elsa", expressive=True)
            rewrite.assert_not_called()
            system_voice.assert_not_called()

    @patch("app.services.tts._ollama_request")
    def test_rewrite_selects_installed_models_and_ignores_cloud_aliases(self, request):
        request.return_value = {"models": [
            {"name": "gemma4:cloud", "size": 2048},
            {"name": "gemma4:alias", "size": 2048, "remote_host": "https://ollama.com"},
            {"name": "qwen2.5:7b", "size": 2048},
        ]}
        self.assertEqual(find_local_ollama_model(), "qwen2.5:7b")
        request.assert_called_once_with("/api/tags", timeout=5)

    @patch("app.services.tts.get_available_voices")
    def test_preflight_reports_system_voices_and_recovers_when_missing(self, get_voices):
        from app.services.preflight import _local_tts_check

        get_voices.return_value = []
        missing = _local_tts_check()
        self.assertEqual(missing["status"], "warning")
        self.assertFalse(missing["required"])
        self.assertIn("Refresh voices", missing["resolution"])

        get_voices.return_value = [{"id": "macos_example", "language": "it-IT", "name": "Alice"}]
        ready = _local_tts_check()
        self.assertEqual(ready["status"], "pass")
        self.assertIn("1 macOS", ready["detail"])

    def test_qwen3_voice_dispatches_to_local_worker(self):
        generated = np.linspace(-0.1, 0.1, 2400, dtype=np.float32)
        with patch("app.services.expressive_voice.is_available", return_value=True), patch(
            "app.services.expressive_voice.synthesize",
            return_value=(generated, 24000, {"voice_name": "Narratrice italiana", "execution": "local-metal"}),
        ) as qwen, patch("app.services.tts._synthesize_macos") as macos, patch(
            "app.services.tts._apply_warmth", side_effect=lambda audio, *_: audio
        ):
            audio, rate, metadata = synthesize_speech(
                "Prova italiana", voice_id="qwen3_it_narrator", engine="qwen3-voice-design", style="calm"
            )
        qwen.assert_called_once_with("Prova italiana", "qwen3_it_narrator", "calm", 1.0)
        macos.assert_not_called()
        self.assertEqual(rate, 24000)
        self.assertEqual(metadata["engine"], "qwen3-voice-design")
        self.assertEqual(metadata["execution"], "local-metal")
        np.testing.assert_array_equal(audio, generated)

    def test_raw_clone_sample_is_rejected_instead_of_ignored(self):
        with self.assertRaisesRegex(RuntimeError, "not a clone profile"):
            synthesize_speech("Hello", clone_voice_path="/tmp/reference.wav")


if __name__ == "__main__":
    unittest.main()
