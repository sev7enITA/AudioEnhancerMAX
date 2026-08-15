import unittest

import numpy as np
import pyloudnorm as pyln

from app.services.delivery_compliance import evaluate_measurements, measure_audio


class DeliveryComplianceTests(unittest.TestCase):
    def test_podcast_target_passes_for_measured_minus_16_lufs(self):
        sample_rate = 48000
        timeline = np.arange(sample_rate * 2) / sample_rate
        audio = (0.1 * np.sin(2 * np.pi * 440 * timeline)).astype(np.float32)
        meter = pyln.Meter(sample_rate)
        audio = pyln.normalize.loudness(audio, meter.integrated_loudness(audio), -16.0)

        result = evaluate_measurements(measure_audio(audio, sample_rate), "podcast")

        self.assertEqual(result["status"], "pass")
        self.assertAlmostEqual(result["measurements"]["integrated_loudness_lufs"], -16.0, places=1)

    def test_out_of_tolerance_loudness_fails(self):
        measurements = {
            "integrated_loudness_lufs": -10.0,
            "estimated_true_peak_dbtp": -4.0,
            "sample_peak_dbfs": -4.1,
            "clipped_sample_count": 0,
            "sample_rate_hz": 48000,
            "channels": 1,
            "duration_seconds": 2.0,
            "true_peak_method": "test",
        }
        result = evaluate_measurements(measurements, "podcast")
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["rules"][0]["id"], "integrated-loudness")

    def test_silence_is_explicit_and_not_clipped(self):
        measurements = measure_audio(np.zeros(48000, dtype=np.float32), 48000)
        result = evaluate_measurements(measurements, "broadcast-r128")
        self.assertIsNone(measurements["integrated_loudness_lufs"])
        self.assertEqual(measurements["clipped_sample_count"], 0)
        self.assertEqual(result["status"], "fail")

    def test_full_scale_samples_are_counted(self):
        audio = np.array([0.0, 1.0, -1.0, 0.5] * 12000, dtype=np.float32)
        measurements = measure_audio(audio, 48000)
        self.assertEqual(measurements["clipped_sample_count"], 24000)


if __name__ == "__main__":
    unittest.main()
