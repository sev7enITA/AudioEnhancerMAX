import json
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.services.apple_acceleration import detect_host_chip, is_mps_available
from app.services.system_monitor import SystemMonitor
from app.services.timing_engine import TimingEngine


class HostCapabilitiesTests(unittest.TestCase):
    def test_macos_chip_model_comes_from_sysctl(self):
        with patch("app.services.apple_acceleration.sys.platform", "darwin"), patch(
            "app.services.apple_acceleration.subprocess.run"
        ) as run:
            for chip in ("Apple M1", "Apple M4 Pro", "Apple M5", ""):
                with self.subTest(chip=chip):
                    run.return_value = SimpleNamespace(stdout=f"{chip}\n")
                    self.assertEqual(detect_host_chip(), chip or None)
            self.assertEqual(run.call_args.args[0], ["/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string"])
            run.side_effect = subprocess.CalledProcessError(1, "sysctl")
            self.assertIsNone(detect_host_chip())

    def test_missing_or_unusable_optional_pytorch_disables_mps(self):
        broken_mps = SimpleNamespace(
            backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: True))
        )
        with patch.dict("sys.modules", {"torch": broken_mps}):
            self.assertTrue(is_mps_available())
        with patch.dict("sys.modules", {"torch": SimpleNamespace(backends=SimpleNamespace())}):
            self.assertFalse(is_mps_available())
        with patch.dict("sys.modules", {"torch": None}):
            self.assertFalse(is_mps_available())


class HardwareMonitorTests(unittest.TestCase):
    def setUp(self):
        with patch("app.services.system_monitor.detect_host_chip", return_value="Apple M1"):
            self.monitor = SystemMonitor()

    def test_optional_sensors_are_unmeasured_until_the_first_sample(self):
        snapshot = self.monitor.get_stats()
        self.assertEqual(snapshot["chip"], "Apple M1")
        self.assertIsNone(snapshot["gpu_percent"])
        self.assertIsNone(snapshot["ane_power_watts"])
        self.assertIsNone(snapshot["thermal_pressure"])
        self.assertIsNone(snapshot["power_watts"])
        self.assertFalse(snapshot["macmon_available"])

    def test_measured_zero_and_ane_power_are_distinct_from_missing_values(self):
        self.monitor._parse_macmon_line(json.dumps({
            "cpu_usage_pct": 0,
            "gpu_usage": [420, 0],
            "ane_power": 0,
            "sys_power": 11.2,
            "temp": {"cpu_temp_avg": 97.5},
        }))
        idle = self.monitor.get_stats()
        self.assertTrue(idle["macmon_available"])
        self.assertEqual(idle["gpu_percent"], 0)
        self.assertEqual(idle["soc_cpu_percent"], 0)
        self.assertEqual(idle["ane_power_watts"], 0)
        self.assertEqual(idle["cpu_temp_c"], 97.5)
        self.assertIsNone(idle["ane_percent"])
        self.assertIsNone(idle["thermal_pressure"])

        self.monitor._psutil_data = {"ram_percent": 38}
        self.monitor._parse_macmon_line('{"ane_power": 10.25, "gpu_usage": [null, false], "all_power": 5}')
        self.monitor._update_snapshot_and_history()
        next_sample = self.monitor.get_stats()
        self.assertEqual(next_sample["ane_power_watts"], 10.25)
        self.assertEqual(next_sample["ram_percent"], 38)
        self.assertIsNone(next_sample["power_watts"])
        self.assertIsNone(next_sample["gpu_percent"])
        self.assertIsNone(next_sample["cpu_temp_c"])
        self.assertEqual(self.monitor.get_history()["gpu_percent"], [None])

    def test_old_sensor_samples_expire_even_when_no_new_sample_arrives(self):
        with patch("app.services.system_monitor.time.monotonic", return_value=100):
            self.monitor._parse_macmon_line('{"gpu_usage": [800, 0.5]}')
            self.assertEqual(self.monitor.get_stats()["gpu_percent"], 50)
        with patch("app.services.system_monitor.time.monotonic", return_value=106):
            snapshot = self.monitor.get_stats()
        self.assertFalse(snapshot["macmon_available"])
        self.assertIsNone(snapshot["gpu_percent"])

    def test_optional_macmon_runs_only_on_native_apple_silicon(self):
        with patch("app.services.system_monitor.sys.platform", "linux"):
            self.assertIsNone(self.monitor._find_macmon())
        with patch("app.services.system_monitor.sys.platform", "darwin"), patch.object(
            self.monitor, "_platform", "x86_64"
        ):
            self.assertIsNone(self.monitor._find_macmon())


class TimingReferenceTests(unittest.TestCase):
    def test_history_and_reference_estimates_are_labelled_by_evidence(self):
        with patch.object(TimingEngine, "_load_history"):
            engine = TimingEngine()
        step = "studio_sound"
        initial = engine.get_adaptive_estimate([step], 60)
        self.assertEqual((initial["source"], initial["confidence"]), ("benchmark", "low"))
        self.assertIn("riferimento iniziale", initial["breakdown_text"])
        self.assertIn("senza misure registrate", engine.estimate_operation("diarize", 60)["reason"])

        for _ in range(3):
            engine._record_timing("filter_timings", step, 60, 0.4)
        self.assertEqual(engine.get_adaptive_estimate([step], 60)["confidence"], "medium")
        mixed = engine.get_adaptive_estimate([step, "remove_noise"], 60)
        self.assertEqual(mixed["source"], "history+benchmark")
        self.assertEqual(mixed["confidence"], "low")
