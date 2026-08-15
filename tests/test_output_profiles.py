import unittest

from app.services.output_profiles import list_output_profiles, resolve_output_profile


class OutputProfileTests(unittest.TestCase):
    def test_profiles_are_fixed_and_overrides_are_auditable(self):
        profiles = list_output_profiles()
        self.assertGreaterEqual(len(profiles), 5)
        resolved = resolve_output_profile("podcast", {"target_loudness_lufs": -15.0})
        self.assertEqual(resolved["resolved"]["output_format"], "wav")
        self.assertEqual(resolved["resolved"]["target_loudness_lufs"], -15.0)
        self.assertEqual(resolved["overrides"], {"target_loudness_lufs": -15.0})

    def test_unknown_override_is_rejected(self):
        with self.assertRaises(ValueError):
            resolve_output_profile("podcast", {"secret_setting": True})


if __name__ == "__main__":
    unittest.main()
