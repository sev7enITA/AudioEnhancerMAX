import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from desktop.launcher import _support_dir


class DesktopLauncherTests(unittest.TestCase):
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
