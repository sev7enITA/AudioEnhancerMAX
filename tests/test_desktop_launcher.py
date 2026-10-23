import tempfile
import json
import unittest
from pathlib import Path
import plistlib
from unittest.mock import patch, MagicMock

from desktop.launcher import _bundle_metadata, _support_dir, _is_audioenhancermax
from app.release import APP_NAME, APP_VERSION, RELEASE_CHANNEL, BUNDLE_IDENTIFIER, DEFAULT_PORT


class DesktopLauncherTests(unittest.TestCase):
    def test_frozen_launcher_uses_bundle_version_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            contents = Path(temp_dir) / "AudioEnhancerMAX.app" / "Contents"
            executable = contents / "MacOS" / "AudioEnhancerMAX"
            executable.parent.mkdir(parents=True)
            executable.touch()
            with (contents / "Info.plist").open("wb") as stream:
                plistlib.dump(
                    {
                        "CFBundleShortVersionString": "3.7.0",
                        "CFBundleVersion": "99",
                    },
                    stream,
                )

            with (
                patch("desktop.launcher.sys.frozen", True, create=True),
                patch("desktop.launcher.sys.executable", str(executable)),
            ):
                self.assertEqual(_bundle_metadata(), ("3.7.0", "99"))

    def test_app_store_support_path_relies_on_sandbox_redirection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_home = Path(temp_dir)
            with patch("desktop.launcher.Path.home", return_value=fake_home):
                support_dir = _support_dir("app-store")

            self.assertEqual(
                support_dir,
                fake_home / "Library" / "Application Support" / APP_NAME,
            )
            self.assertNotIn("Containers", support_dir.parts)

    def test_experimental_identity_is_separate_from_stable(self):
        self.assertNotEqual(APP_NAME, "AudioEnhancerMAX")
        self.assertNotEqual(BUNDLE_IDENTIFIER, "com.fabriziodegni.audioenhancermax")
        self.assertNotEqual(DEFAULT_PORT, 8000)
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_home = Path(temp_dir)
            stable = fake_home / "Library" / "Application Support" / "AudioEnhancerMAX"
            stable.mkdir(parents=True)
            sentinel = stable / "runtime_settings.json"
            sentinel.write_text('{"owner":"stable"}')
            with patch("desktop.launcher.Path.home", return_value=fake_home):
                experimental = _support_dir("direct")
            self.assertNotEqual(experimental, stable)
            self.assertEqual(sentinel.read_text(), '{"owner":"stable"}')
            self.assertFalse((experimental / sentinel.name).exists())

    def test_launcher_does_not_attach_to_other_release_channel(self):
        for channel, expected in (("stable", False), (None, False), (RELEASE_CHANNEL, True)):
            with self.subTest(channel=channel):
                response = MagicMock()
                response.__enter__.return_value.read.return_value = json.dumps({
                    "app": "AudioEnhancerMAX by Fabrizio Degni",
                    "version": APP_VERSION, "release_channel": channel,
                }).encode()
                with patch("desktop.launcher.urllib.request.urlopen", return_value=response):
                    self.assertEqual(_is_audioenhancermax(8001), expected)


if __name__ == "__main__":
    unittest.main()
