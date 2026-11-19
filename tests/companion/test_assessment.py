import base64
import json
import unittest
from desktop.companion.assessment import parse_assessment


class AssessmentTests(unittest.TestCase):
    def encode(self, value):
        return base64.b64encode(json.dumps(value).encode()).decode()

    def test_valid_measurement_is_labelled_as_device_reported(self):
        result = parse_assessment(
            self.encode(
                {
                    "schema": 1,
                    "model": "Test phone",
                    "ram_bytes": 8 * 1024**3,
                    "voice_eq_ms": 12.5,
                    "benchmark": "voice-eq-2s-48k-mono-v1",
                    "battery_percent": 80,
                    "round_trip_ms": 24,
                }
            )
        )
        self.assertEqual(result["source"], "device-reported")
        self.assertEqual(result["voice_eq_ms"], 12.5)

    def test_unqualified_or_unbounded_measurements_are_discarded(self):
        result = parse_assessment(
            self.encode(
                {
                    "schema": 1,
                    "voice_eq_ms": 1,
                    "benchmark": "fake-ai-score",
                    "ram_bytes": -1,
                    "battery_percent": 101,
                    "round_trip_ms": float("nan"),
                }
            )
        )
        self.assertNotIn("voice_eq_ms", result)
        self.assertNotIn("ram_bytes", result)
        self.assertNotIn("battery_percent", result)
        self.assertNotIn("round_trip_ms", result)

    def test_malformed_and_oversized_headers_do_not_break_presence(self):
        for value in [
            "not-base64",
            "a" * 5000,
            self.encode([]),
            self.encode({"schema": 2}),
        ]:
            self.assertEqual(parse_assessment(value), {})
