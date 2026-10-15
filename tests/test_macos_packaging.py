import unittest
from pathlib import Path
import sys
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class MacOSPackagingTests(unittest.TestCase):
    def test_app_store_runtime_has_no_jit_dependencies(self):
        requirements = (
            ROOT / "packaging/macos/requirements-runtime-app-store.txt"
        ).read_text().lower()
        for forbidden in ("librosa", "numba", "llvmlite"):
            self.assertNotIn(forbidden, requirements)
        package_lines = {
            line.strip().lower()
            for line in requirements.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        self.assertFalse(any(line.startswith("tts==") for line in package_lines))

    def test_spec_excludes_jit_dependencies(self):
        spec = (ROOT / "packaging/macos/AudioEnhancerMAX.spec").read_text()
        for forbidden in ("librosa", "numba", "llvmlite"):
            self.assertIn(f'"{forbidden}"', spec)

    def test_preflight_does_not_require_removed_jit_or_ml_engines(self):
        from app.services.preflight import CORE_MODULES

        self.assertNotIn("librosa", CORE_MODULES)
        self.assertNotIn("torch", CORE_MODULES)

    def test_store_preflight_accepts_accelerate_without_optional_torch(self):
        from app.services.preflight import _mps_check

        with (
            patch("app.services.preflight.APP_STORE_MODE", True),
            patch.dict(sys.modules, {"torch": None}),
        ):
            result = _mps_check()

        self.assertEqual(result["status"], "pass")

    def test_app_store_entitlements_do_not_allow_unsigned_executable_memory(self):
        entitlements = (
            ROOT / "packaging/macos/app-store-entitlements.plist"
        ).read_text()
        self.assertNotIn("allow-unsigned-executable-memory", entitlements)
        self.assertNotIn("allow-jit", entitlements)

    def test_next_app_store_build_number_is_unique(self):
        script = (ROOT / "scripts/build_macos_app_store.sh").read_text()
        self.assertIn('AEMAX_BUILD_NUMBER:-3.8.2', script)

    def test_app_store_build_requires_distribution_profile(self):
        script = (ROOT / "scripts/build_macos_app_store.sh").read_text()
        self.assertIn("Mac App Store provisioning profile not found", script)
        self.assertNotIn("not embedded (no restricted entitlements)", script)

    def test_direct_build_uses_current_build_number(self):
        script = (ROOT / "scripts/build_macos_app.sh").read_text()
        self.assertIn('AEMAX_BUILD_NUMBER:-3.8.2', script)

    def test_direct_build_uses_jit_free_runtime(self):
        script = (ROOT / "scripts/build_macos_app.sh").read_text()
        self.assertIn("requirements-runtime-direct.txt", script)
        direct_requirements = (
            ROOT / "packaging/macos/requirements-runtime-direct.txt"
        ).read_text()
        self.assertIn("requirements-runtime-app-store.txt", direct_requirements)


if __name__ == "__main__":
    unittest.main()
