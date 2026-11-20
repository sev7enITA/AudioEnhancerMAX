import hashlib
import io
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from app import main
from app.services import artifact_store, delivery_compliance, processing_report, smart_mode, workspace_history
from app.utils import audio_io


def test_workspace_source_history_and_exact_original(tmp_path, monkeypatch):
    uploads = tmp_path / "uploads"
    outputs = tmp_path / "outputs"
    uploads.mkdir()
    outputs.mkdir()
    for module in (main, audio_io):
        monkeypatch.setattr(module, "UPLOAD_DIR", uploads)
    for module in (main, artifact_store, audio_io, delivery_compliance, processing_report):
        monkeypatch.setattr(module, "OUTPUT_DIR", outputs)
    monkeypatch.setattr(workspace_history, "DATA_DIR", tmp_path)
    monkeypatch.setattr(smart_mode, "get_dynamic_parameters", lambda *args: {})
    client = TestClient(main.app, base_url="http://127.0.0.1", client=("127.0.0.1", 23456))
    rejected = client.post("/api/upload", files={"file": ("corrupt.wav", b"not a WAV")})
    assert rejected.status_code == 422
    assert not list(uploads.iterdir())

    media = io.BytesIO()
    signal = 0.12 * np.sin(np.arange(48_000) * (2 * np.pi * 440 / 48_000))
    sf.write(media, signal, 48_000, format="FLAC")
    raw = media.getvalue()
    sha256 = hashlib.sha256(raw).hexdigest()

    def upload(content, name="recording.flac"):
        response = client.post("/api/upload", files={"file": (name, content)})
        assert response.status_code == 200, response.text
        return response.json()

    def history(file_id):
        response = client.get(f"/api/workspace/{file_id}/history")
        assert response.status_code == 200, response.text
        return response.json()["events"]

    source = upload(raw)
    file_id = source["file_id"]
    assert source["source_sha256"] == sha256
    assert [event["action"] for event in history(file_id)] == ["source_imported"]
    assert client.get(f"/api/reports/{file_id}").status_code == 404
    assert client.post(f"/api/smart-mode/{file_id}").status_code == 200
    assert client.get(f"/api/reports/{file_id}").status_code == 404

    original = client.get(f"/api/download/{file_id}", params={"version": "original"})
    assert original.content == raw
    assert original.headers["content-type"] == "audio/flac"

    render = client.post("/api/process", json={"file_id": file_id, "options": {"normalize": True}})
    assert render.status_code == 200, render.text
    revision = render.json()["revision"]
    report = client.get(f"/api/reports/{file_id}", params={"revision": revision})
    assert report.status_code == 200
    assert report.json()["executed_steps"] == ["normalize"]
    assert report.json()["changed_steps"] == ["normalize"]
    latest = history(file_id)[0]
    assert latest["action"] == "revision_rendered"
    assert latest["revision"] == revision
    assert latest["details"]["processing_report_sha256"] == hashlib.sha256(report.content).hexdigest()
    assert [event["action"] for event in history(file_id)] == [
        "revision_rendered", "processing_started", "export_prepared", "analysis_completed", "source_imported",
    ]

    identical = upload(raw, "same-bytes.flac")
    prior = history(identical["file_id"])
    assert prior[0]["action"] == "source_imported" and prior[1]["revision"] == revision
    alternative = io.BytesIO()
    sf.write(alternative, signal * 0.5, 48_000, format="FLAC")
    assert len(history(upload(alternative.getvalue())["file_id"])) == 1


def test_history_append_and_pagination(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace_history, "DATA_DIR", tmp_path)
    assert workspace_history.record_event("recording", "source_imported", source_sha256="a" * 64)
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert all(pool.map(lambda index: workspace_history.record_event("recording", "analysis_completed", index=index), range(8)))
    first = workspace_history.read_history("recording", limit=5)
    second = workspace_history.read_history("recording", before=first["next_before"], limit=5)
    combined = first["events"] + second["events"]
    assert len({event["id"] for event in combined}) == 9
    assert combined[-1]["action"] == "source_imported"
    assert second["next_before"] is None
