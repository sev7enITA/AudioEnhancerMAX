import asyncio
import sys
import unittest
from unittest.mock import patch

from app.main import health
from app.release import APP_VERSION, RELEASE_CHANNEL, RELEASE_LABEL
from app.services.system_monitor import system_monitor


class HealthEndpointTests(unittest.TestCase):
    def test_health_works_without_optional_torch(self):
        with patch.dict(sys.modules, {"torch": None}):
            payload = asyncio.run(health())

        self.assertEqual(payload["status"], "healthy")
        self.assertEqual(payload["version"], APP_VERSION)
        self.assertEqual(payload["release_channel"], RELEASE_CHANNEL)
        self.assertEqual(payload["release_label"], RELEASE_LABEL)
        self.assertIn("build", payload)
        self.assertFalse(payload["mps_available"])

    def test_chip_identity_is_independent_of_the_optional_model_backend(self):
        for metrics, expected_chip in (
            ({"cpu_percent": 1}, None),
            ({"chip": "Apple M1"}, "Apple M1"),
            ({"chip": "Apple M4 Pro"}, "Apple M4 Pro"),
            ({"chip": "Apple M5"}, "Apple M5"),
        ):
            with self.subTest(chip=expected_chip), patch.dict(sys.modules, {"torch": None}), patch.object(
                system_monitor, "get_stats", return_value=metrics
            ):
                payload = asyncio.run(health())

            self.assertEqual(payload["system"]["chip"], expected_chip)
            self.assertFalse(payload["mps_available"])


    def test_health_keeps_missing_sensors_distinct_from_measured_idle(self):
        for optional in ({}, {"gpu_percent": 0.0, "ane_power_watts": 0.0, "macmon_available": True}):
            with self.subTest(optional=optional), patch.object(
                system_monitor, "get_stats", return_value={"cpu_percent": 17.5, "ram_percent": 43, **optional}
            ):
                payload = asyncio.run(health())["system"]

            self.assertEqual(payload["cpu_percent"], 17.5)
            self.assertEqual(payload["ram_percent"], 43)
            self.assertEqual(payload["gpu_percent"], optional.get("gpu_percent"))
            self.assertEqual(payload["ane_power_watts"], optional.get("ane_power_watts"))
            self.assertIsNone(payload["ane_percent"])
            self.assertIsNone(payload["thermal_pressure"])


if __name__ == "__main__":
    unittest.main()
