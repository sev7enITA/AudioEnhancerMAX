import hashlib
import io
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import expressive_setup as setup, expressive_voice as voice


def test_public_download_integrity_failure_keeps_previous_asset(tmp_path):
    destination = tmp_path / "model"
    destination.write_bytes(b"previous")
    asset = {"bytes": 4, "sha256": hashlib.sha256(b"good").hexdigest()}

    with patch.object(setup, "_download", return_value=io.BytesIO(b"evil")):
        with pytest.raises(setup.SetupError, match="Integrity check failed"):
            setup._fetch(asset, destination, None, lambda _: None)

    assert destination.read_bytes() == b"previous"
    assert list(tmp_path.iterdir()) == [destination]


def test_offline_install_uses_only_verified_local_files(tmp_path):
    kit = tmp_path / "kit"
    kit.mkdir()
    (kit / "component").write_bytes(b"valid")
    destination = tmp_path / "installed" / "component"
    asset = {"path": "component", "bytes": 5, "sha256": hashlib.sha256(b"valid").hexdigest()}
    with patch.object(setup, "_download") as download:
        setup._fetch(asset, destination, kit, lambda _: None)
        download.assert_not_called()

    assert destination.read_bytes() == b"valid"


def test_component_redirect_stays_on_pinned_public_hosts():
    for url in ("http://github.com/path", "https://127.0.0.1/path", "https://token@github.com/path"):
        with pytest.raises(setup.SetupError):
            setup._check_url(url)
    setup._check_url("https://release-assets.githubusercontent.com/path")
    setup._check_url("https://us.aws.cdn.hf.co/path")


def test_retry_clears_an_interrupted_setup_without_touching_other_files(tmp_path, monkeypatch):
    monkeypatch.setenv("AEMAX_EXPRESSIVE_VOICE_ROOT", str(tmp_path))
    root = tmp_path / "setup-components"
    root.mkdir()
    filename = voice.manifest()["python"]["path"]
    partial = root / f".{filename}.part-abandoned"
    partial.touch()
    unrelated = root / "user-notes.txt"
    unrelated.touch()
    stage = tmp_path / "voice-runtime-abandoned"
    stage.mkdir()

    with patch.object(voice, "is_available", return_value=False), patch.object(
        setup.shutil, "disk_usage", return_value=SimpleNamespace(free=10 * 1024**3)
    ), patch.object(
        setup, "_fetch", side_effect=setup.SetupError("stop before fetching")
    ):
        with pytest.raises(setup.SetupError, match="stop before fetching"):
            setup._provision(tmp_path, lambda _: None)

    assert not partial.exists()
    assert not stage.exists()
    assert unrelated.is_file()


def test_setup_requires_a_matching_loopback_origin():
    base = "http://127.0.0.1:8090"
    body = {"mode": "offline", "folder": "/Volumes/USB/VoicePack"}
    with patch.object(setup, "start", return_value={"state": "installing"}) as start:
        with TestClient(app, base_url=base, client=("127.0.0.1", 51000)) as client:
            assert client.post("/api/tts/voice-pack", json=body).status_code == 403
            assert client.post("/api/tts/voice-pack", json=body, headers={"Origin": "https://example.com"}).status_code == 403
            start.assert_not_called()
            response = client.post("/api/tts/voice-pack", json=body, headers={"Origin": base})
            assert response.status_code == 202
            start.assert_called_once_with(body["folder"])


def test_expressive_voice_profiles_include_english_and_italian():
    with patch.object(voice, "is_available", side_effect=lambda voice_id="": voice_id == ""):
        voices = voice.available_voices()
    assert len(voices) == 4
    assert {item["language"] for item in voices} == {"en-US", "en-GB", "it-IT"}
    assert all(item["engine"] == voice.ENGINE for item in voices)


def test_paola_can_use_base_without_voicedesign_weights():
    with patch.object(voice, "_runtime_available", return_value=True), patch.object(
        voice, "paola_model_dir", return_value=voice.voice_root()
    ), patch.object(voice, "matches_size", return_value=False):
        assert voice.available_voices() == [
            {"id": voice.PAOLA_ID, "name": "Eve · Italiano", "language": "it-IT", "engine": voice.ENGINE}
        ]


def test_paola_preserves_question_punctuation_and_corrects_only_question_tempo():
    passages = voice._italian_passages('Torniamo in studio. Ci siamo quasi. «Ci sei?» Sì.')
    assert passages == [('Torniamo in studio. Ci siamo quasi.', False), ('«Ci sei?»', True), ('Sì.', False)]
    rate = 24000
    tone = np.sin(np.arange(rate * 2) * (2 * np.pi * 220 / rate)).astype(np.float32)
    corrected = voice._tempo(tone, rate, 0.93)
    assert len(corrected) / len(tone) == pytest.approx(1 / 0.93, abs=0.015)
    spectrum = np.abs(np.fft.rfft(corrected))
    assert np.argmax(spectrum) * rate / len(corrected) == pytest.approx(220, abs=1)
