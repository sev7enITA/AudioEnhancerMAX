import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.runtime_settings import load_runtime_settings, save_runtime_settings


class RuntimeSettingsTests(unittest.TestCase):
    def test_trusted_lan_is_opt_in_by_default(self):
        with tempfile.TemporaryDirectory() as temporary, \
             patch("app.services.runtime_settings.RUNTIME_SETTINGS_FILE", Path(temporary) / "missing.json"):
            loaded = load_runtime_settings()

        self.assertFalse(loaded["trusted_lan_processing_allowed"])

    def test_privacy_boundaries_are_persisted_locally(self):
        with tempfile.TemporaryDirectory() as temporary, \
             patch("app.services.runtime_settings.RUNTIME_SETTINGS_FILE", Path(temporary) / "privacy.json"):
            saved = save_runtime_settings({
                "external_services_allowed": False,
                "ollama_editorial_allowed": True,
                "trusted_lan_processing_allowed": False,
            })
            loaded = load_runtime_settings()

        self.assertEqual(saved, loaded)
        self.assertFalse(loaded["external_services_allowed"])
        self.assertFalse(loaded["trusted_lan_processing_allowed"])


if __name__ == "__main__":
    unittest.main()
