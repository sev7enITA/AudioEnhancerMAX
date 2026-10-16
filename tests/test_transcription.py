"""Exercise both transcription paths against the installed VAD option contract."""
import json
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest
from faster_whisper.vad import VadOptions

from app.services import transcription


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("empty_vad", [False, True])
def test_transcription_accepts_pinned_vad_options_and_preserves_results(
    tmp_path, streaming, empty_vad
):
    calls = []
    segment = SimpleNamespace(
        start=0.1, end=0.8, text=" Test audio.", avg_logprob=-0.2,
        words=[SimpleNamespace(word=" Test", start=0.1, end=0.4, probability=0.9)],
    )

    def decode(path, **kwargs):
        assert transcription.Path(path).is_file()
        calls.append(kwargs)
        if kwargs["vad_filter"]:
            # Real dependency constructor catches unsupported names before inference.
            options = VadOptions(**kwargs["vad_parameters"])
            assert options.onset == 0.35
            assert options.offset == 0.20
            assert options.offset < options.onset
            assert options.min_silence_duration_ms == 500
            assert options.speech_pad_ms == 400
        result = [] if empty_vad and kwargs["vad_filter"] else [segment]
        return iter(result), SimpleNamespace(language="en")

    model = SimpleNamespace(transcribe=decode)
    audio = np.zeros(16000, dtype=np.float32)
    with patch.object(transcription, "_model", model):
        if streaming:
            output_path = tmp_path / "transcript.json"
            events = list(transcription.transcribe_streaming(
                audio, 16000, language="en", output_path=output_path,
            ))
            assert [e["type"] for e in events] == ["segment", "done"]
            result = events[-1]
            saved = json.loads(output_path.read_text())
            assert saved["complete"] is True
            assert saved["text"] == result["text"]
        else:
            result = transcription.transcribe(audio, 16000, language="en")

    assert result["text"] == "Test audio."
    assert result["language"] == "en"
    assert result["segments"][0]["start"] == 0.1
    assert result["segments"][0]["end"] == 0.8
    assert result["duration"] == 1.0
    assert [call["vad_filter"] for call in calls] == ([True, False] if empty_vad else [True])
    assert all(call["word_timestamps"] for call in calls)
