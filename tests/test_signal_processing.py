import unittest

import numpy as np

from app.services.silence_removal import detect_silences
from app.services.super_resolution import restore_frequencies
from app.utils.signal_processing import istft, mfcc, resample_audio, stft


class SignalProcessingTests(unittest.TestCase):
    def setUp(self):
        self.sample_rate = 16000
        timeline = np.arange(self.sample_rate * 2) / self.sample_rate
        self.audio = (0.2 * np.sin(2 * np.pi * 220 * timeline)).astype(np.float32)

    def test_stft_round_trip_preserves_signal_and_length(self):
        spectrum = stft(self.audio, n_fft=1024, hop_length=256)
        restored = istft(
            spectrum, n_fft=1024, hop_length=256, length=len(self.audio)
        )
        self.assertEqual(len(restored), len(self.audio))
        self.assertLess(float(np.sqrt(np.mean((self.audio - restored) ** 2))), 1e-5)

    def test_short_input_is_padded_safely(self):
        short = self.audio[:100]
        restored = istft(stft(short), length=len(short))
        self.assertEqual(len(restored), len(short))
        self.assertTrue(np.all(np.isfinite(restored)))

    def test_resampling_has_expected_length(self):
        result = resample_audio(self.audio, self.sample_rate, 48000)
        self.assertEqual(len(result), len(self.audio) * 3)

    def test_frequency_restoration_is_finite(self):
        result, rate = restore_frequencies(self.audio, self.sample_rate, 48000)
        self.assertEqual(rate, 48000)
        self.assertEqual(len(result), len(self.audio) * 3)
        self.assertTrue(np.all(np.isfinite(result)))

    def test_mfcc_shape_is_stable(self):
        result = mfcc(self.audio, self.sample_rate, n_mfcc=13)
        self.assertEqual(result.shape[0], 13)
        self.assertGreater(result.shape[1], 1)

    def test_silence_detection_uses_jit_free_rms(self):
        audio = np.concatenate([np.zeros(self.sample_rate * 2), self.audio])
        silences = detect_silences(audio, self.sample_rate, min_duration_ms=1000)
        self.assertTrue(silences)
        self.assertLessEqual(silences[0][0], self.sample_rate // 20)


if __name__ == "__main__":
    unittest.main()
