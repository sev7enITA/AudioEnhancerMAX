import hashlib
import io
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services import media_verification

CLIENT = TestClient(main.app, base_url="http://127.0.0.1", client=("127.0.0.1", 23456))
ENDPOINT = "/api/media-verification?extension=wav"
BINARY = {"Content-Type": "application/octet-stream"}
SAMPLES = Path(__file__).resolve().parents[1] / "web/c2pa/v4.0.0-beta.1"


def _wav(value=16384):
    with io.BytesIO() as stream:
        with wave.open(stream, "wb") as writer:
            writer.setparams((1, 2, 48_000, 0, "NONE", ""))
            writer.writeframes(value.to_bytes(2, "little", signed=True) * 4_800)
        return stream.getvalue()


def test_report_matches_received_bytes_and_measures_audio():
    original = _wav()
    response = CLIENT.post(ENDPOINT, content=original, headers=BINARY)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    report = response.json()
    assert report["schema"] == media_verification.SCHEMA
    assert report["asset"] == {
        "sha256": hashlib.sha256(original).hexdigest(),
        "size_bytes": len(original),
        "media_type": "audio/wav",
    }
    assert report["audio"]["analyzed_seconds"] == 0.1
    assert report["audio"]["peak_dbfs"] == pytest.approx(-6.02)
    assert report["audio"]["rms_dbfs"] == pytest.approx(-6.02)
    assert len(report["audio"]["waveform_peak"]) == 64


def test_silence_has_no_non_finite_json():
    response = CLIENT.post(ENDPOINT, content=_wav(0), headers=BINARY)
    assert response.status_code == 200
    assert response.json()["audio"]["rms_dbfs"] is None


@pytest.mark.parametrize(("fixture", "status"), [("signed-sample.wav", "valid"), ("altered-sample.wav", "invalid")])
def test_c2pa_fixture_and_report_reference(fixture, status):
    pytest.importorskip("c2pa")
    original = (SAMPLES / fixture).read_bytes()
    report = CLIENT.post(ENDPOINT, content=original, headers=BINARY).json()
    assert report["asset"]["sha256"] == hashlib.sha256(original).hexdigest()
    assert report["credentials"]["status"] == status
    assert report["credentials"]["processing_report_sha256"] == hashlib.sha256(
        (SAMPLES / "processing-report.json").read_bytes()
    ).hexdigest()


def test_failed_audio_parse_still_fingerprints_the_received_file():
    original = b"not wave data"
    report = CLIENT.post(ENDPOINT, content=original, headers=BINARY).json()
    assert report["asset"]["sha256"] == hashlib.sha256(original).hexdigest()
    assert report["audio"]["status"] == "unreadable_audio"


def test_local_origin_type_and_bounded_body(monkeypatch):
    assert CLIENT.post(ENDPOINT, content=b"a", headers={**BINARY, "Origin": "https://example.org"}).status_code == 403
    assert CLIENT.post(ENDPOINT, content=b"a").status_code == 415
    assert CLIENT.post(ENDPOINT, content=b"", headers=BINARY).status_code == 422
    assert CLIENT.post("/api/media-verification?extension=m3u8", content=b"a", headers=BINARY).status_code == 415
    monkeypatch.setattr(main, "MAX_FILE_SIZE_MB", 1)
    response = CLIENT.post(ENDPOINT, content=b"a" * (1024 * 1024 + 1), headers=BINARY)
    assert response.status_code == 413
