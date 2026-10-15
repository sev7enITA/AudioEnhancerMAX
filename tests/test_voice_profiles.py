import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import soundfile as sf

from app.services import voice_profiles


class VoiceProfileTests(unittest.TestCase):
    def _storage_patches(self, temporary: str):
        root = Path(temporary) / "profiles"
        return (
            patch.object(voice_profiles, "VOICE_PROFILES_DIR", root),
            patch.object(voice_profiles, "REGISTRY_FILE", root / "profiles.json"),
        )

    def test_named_local_profile_persists_sample_and_defaults(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "speaker.wav"
            sr = 24000
            sf.write(source, np.sin(np.arange(sr * 3) / 20).astype(np.float32) * 0.1, sr)
            storage, registry = self._storage_patches(temporary)
            with storage, registry, patch.object(
                voice_profiles,
                "clone_adapter_capabilities",
                return_value={"available": True, "backend": "f5_mlx", "execution": "local-metal"},
            ):
                created = voice_profiles.enroll_voice_profile(
                    source_path=source,
                    name="My Voice",
                    profile_id=None,
                    transcript="This is my exact reference transcript.",
                    consent_confirmed=True,
                    settings={**voice_profiles.DEFAULT_SETTINGS, "warmth": 0.7},
                )
                reference, output_sr, text, profile = voice_profiles.build_profile_reference(created["id"])

            self.assertEqual(created["name"], "My Voice")
            self.assertEqual(created["samples"], 1)
            self.assertEqual(created["settings"]["warmth"], 0.7)
            self.assertEqual(output_sr, sr)
            self.assertGreater(len(reference), sr * 2)
            self.assertIn("exact reference", text)
            self.assertEqual(profile["id"], created["id"])

    def test_makemyvoice_profiles_are_linked_without_copying_voice_audio(self):
        with tempfile.TemporaryDirectory() as temporary:
            mmv = Path(temporary) / "MakeMyVoice"
            bank = mmv / "data" / "voicebank" / "fabfab"
            bank.mkdir(parents=True)
            (mmv / "data" / "voicebank" / "profiles.json").write_text(json.dumps({
                "active": "fabfab",
                "names": {"fabfab": "FabFab"},
            }))
            (bank / "index.json").write_text(json.dumps({
                "entries": [{"file": "clip.wav", "text": "hello", "duration": 7.5}],
            }))
            storage, registry = self._storage_patches(temporary)
            with storage, registry, patch.object(voice_profiles, "MAKEMYVOICE_ROOT", mmv), patch.object(
                voice_profiles,
                "clone_adapter_capabilities",
                return_value={
                    "available": True,
                    "backend": "future_engine",
                    "version": "9.0",
                    "execution": "local-metal",
                    "adapter": "makemyvoice-subprocess-v1",
                },
            ):
                result = voice_profiles.list_voice_profiles()

            self.assertEqual(len(result["profiles"]), 1)
            linked = result["profiles"][0]
            self.assertEqual(linked["id"], "mmv_fabfab")
            self.assertEqual(linked["engine"], "future_engine")
            self.assertEqual(linked["seconds"], 7.5)
            self.assertTrue(linked["available"])

    def test_enrollment_requires_voice_owner_consent(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "speaker.wav"
            sf.write(source, np.zeros(24000 * 3, dtype=np.float32), 24000)
            with self.assertRaisesRegex(ValueError, "consent"):
                voice_profiles.enroll_voice_profile(
                    source_path=source,
                    name="No consent",
                    profile_id=None,
                    transcript="A transcript.",
                    consent_confirmed=False,
                    settings=dict(voice_profiles.DEFAULT_SETTINGS),
                )


if __name__ == "__main__":
    unittest.main()
