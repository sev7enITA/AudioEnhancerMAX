import hashlib
import io

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from app import main
from app.services import artifact_store, delivery_compliance, processing_report
from app.utils import audio_io


@pytest.mark.parametrize(("frames", "voice_eq"), [(8640, False), (48000, True)])
def test_mac_handoff_preserves_stereo_and_report_binding(
    monkeypatch, tmp_path, frames, voice_eq
):
    uploads = tmp_path / "uploads"
    outputs = tmp_path / "outputs"
    uploads.mkdir()
    outputs.mkdir()
    for module in (main, audio_io):
        monkeypatch.setattr(module, "UPLOAD_DIR", uploads)
    for module in (
        main,
        audio_io,
        artifact_store,
        delivery_compliance,
        processing_report,
    ):
        monkeypatch.setattr(module, "OUTPUT_DIR", outputs)

    rate = 48000
    left = 0.12 * np.sin(np.arange(frames) * 2 * np.pi * 440 / rate)
    source = np.column_stack((left, np.zeros_like(left)))
    wave = io.BytesIO()
    sf.write(wave, source, rate, format="WAV", subtype="PCM_16")
    source_bytes = wave.getvalue()

    client = TestClient(main.app)
    imported = client.post("/api/upload", files={"file": ("stereo.wav", source_bytes)})
    assert imported.status_code == 200, imported.text
    file_id = imported.json()["file_id"]
    rendered = client.post(
        "/api/process",
        json={
            "file_id": file_id,
            "preserve_channels": True,
            "options": {"auto_eq": voice_eq, "normalize": True, "output_format": "wav"},
        },
    )
    assert rendered.status_code == 200, rendered.text
    result = rendered.json()
    revision = result["revision"]
    audio = client.get(
        f"/api/audio/{file_id}", params={"version": "processed", "revision": revision}
    )
    assert audio.status_code == 200
    samples, rendered_rate = sf.read(io.BytesIO(audio.content), always_2d=True)
    assert samples.shape == source.shape
    assert rendered_rate == rate
    assert np.max(np.abs(samples[:, 0])) > 0.01
    assert not np.any(samples[:, 1])

    report = client.get(result["report_url"])
    assert report.status_code == 200
    assert report.json()["artifact_revision"] == revision
    provenance = report.json()["provenance"]
    assert provenance["source"]["sha256"] == hashlib.sha256(source_bytes).hexdigest()
    assert (
        provenance["processed_output"]["sha256"]
        == hashlib.sha256(audio.content).hexdigest()
    )
