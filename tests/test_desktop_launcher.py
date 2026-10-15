import tempfile
import unittest
from pathlib import Path
import plistlib
from unittest.mock import patch

from desktop.launcher import _bundle_metadata, _support_dir


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
                fake_home / "Library" / "Application Support" / "AudioEnhancerMAX",
            )
            self.assertNotIn("Containers", support_dir.parts)


if __name__ == "__main__":
    unittest.main()
