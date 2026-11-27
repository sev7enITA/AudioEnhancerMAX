import unittest
from unittest.mock import patch

import numpy as np

from app.services.timed_script import TimedScriptError, parse_scenes, rewrite_script
from app.services.tts import synthesize_speech


class TimedScriptTests(unittest.TestCase):
    def test_italian_clipboard_with_crlf_and_trailing_backslashes(self):
        script = ('"Tempo\tScena\tTesto\\\r\n'
                  '0:00 \N{EN DASH} 0:04\tApertura\tSessanta secondi.\\\r\n'
                  '0:04 \N{EN DASH} 0:09\tGru\tUna leva strategica."')
        scenes = parse_scenes(script)
        self.assertEqual([(s.start_ms, s.end_ms, s.text) for s in scenes], [
            (0, 4000, "Sessanta secondi."), (4000, 9000, "Una leva strategica."),
        ])

    def test_ordinary_text_and_timestamps_in_sentences(self):
        for text in ("Alle 0:04 inizia la scena.", "0:04 \N{EN DASH} 0:09 è un intervallo."):
            self.assertEqual(parse_scenes(text), [])

    def test_errors_identify_invalid_row(self):
        for row in ("0:03 \N{EN DASH} 0:06\tGru\tOverlap", "0:05 \N{EN DASH} 0:04\tGru\tReversed",
                    "0:04 \N{EN DASH} 0:04\tGru\tEmpty interval", "0:04 \N{EN DASH} 0:70\tGru\tBad clock",
                    "0:04 \N{EN DASH} 0:09\tGru\t", "missing tabs"):
            with self.subTest(row=row), self.assertRaisesRegex(TimedScriptError, "Row 3"):
                parse_scenes("Tempo\tScena\tTesto\n0:00 \N{EN DASH} 0:04\tApertura\tPrima.\n" + row)

    def test_preview_rewrites_only_the_spoken_column(self):
        text = "Time\tScene\tText\n00:01:02,500\N{EM DASH}00:01:05.5\tBridge\tHello."
        self.assertEqual(rewrite_script(text, lambda value: value), text)
        scenes = parse_scenes(rewrite_script(text, lambda value: value.upper()))
        self.assertEqual((scenes[0].start_ms, scenes[0].end_ms), (62500, 65500))
        self.assertEqual((scenes[0].name, scenes[0].text), ("Bridge", "HELLO."))

    def test_export_places_short_and_long_lines_at_absolute_offsets(self):
        sr = 16000
        short = np.full(sr // 2, 0.3, dtype=np.float32)
        t = np.arange(24000) / sr
        long = (0.3 * np.cos(2 * np.pi * 220 * t)).astype(np.float32)
        with patch("app.services.tts._synthesize_passage", side_effect=[
            (short, sr, {"rewritten_text": "One."}), (long, sr, {"rewritten_text": "Two."})
        ]) as render:
            audio, rate, info = synthesize_speech(
                "0:01-0:02\tFirst scene\tOne\n0:03\N{EN DASH}0:04\tSecond scene\tTwo", expressive=True)
        self.assertEqual([call.args[0] for call in render.call_args_list], ["One", "Two"])
        self.assertEqual((rate, len(audio), info["accelerated_scenes"]), (sr, 4 * sr, 1))
        np.testing.assert_array_equal(audio[:sr], 0)
        np.testing.assert_array_equal(audio[sr:sr + len(short)], short)
        np.testing.assert_array_equal(audio[sr + len(short):3 * sr], 0)
        fitted = audio[3 * sr:]
        peak_hz = np.argmax(np.abs(np.fft.rfft(fitted))) * rate / len(fitted)
        self.assertAlmostEqual(peak_hz, 220, delta=3)
        self.assertEqual([s.text for s in parse_scenes(info["rewritten_text"])], ["One.", "Two."])

    def test_extremely_dense_scene_is_identified_before_export(self):
        with patch("app.services.tts._synthesize_passage", return_value=(np.ones(48000), 16000, {})):
            with self.assertRaisesRegex(TimedScriptError, "Bridge.*3.00s"):
                synthesize_speech("0:00-0:01\tBridge\tLong sentence")
