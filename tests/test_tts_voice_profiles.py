import unittest
from unittest.mock import patch

import numpy as np

from app.services.tts import synthesize_speech


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
        ), patch("app.services.tts._synthesize_edge") as edge, patch(
            "app.services.tts._apply_warmth", side_effect=lambda audio, *_: audio
        ):
            audio, sr, metadata = synthesize_speech(
                "Personal speech",
                voice_id="it_elsa",
                voice_profile_id="voice_me",
                engine="voice-clone",
            )

        edge.assert_not_called()
        np.testing.assert_array_equal(audio, generated)
        self.assertEqual(sr, 24000)
        self.assertEqual(metadata["engine"], "future_mmv_engine")
        self.assertEqual(metadata["voice_profile_name"], "My Voice")
        self.assertEqual(metadata["execution"], "local-metal")

    def test_raw_clone_sample_is_rejected_instead_of_ignored(self):
        with self.assertRaisesRegex(RuntimeError, "not a clone profile"):
            synthesize_speech("Hello", clone_voice_path="/tmp/reference.wav")


if __name__ == "__main__":
    unittest.main()
