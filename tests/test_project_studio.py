import hashlib
import io
import json
import time
import zipfile

from fastapi.testclient import TestClient
import numpy as np
import soundfile as sf

from app.main import app
from app.services import project_studio as studio


def source_bytes():
    buffer = io.BytesIO()
    phase = np.arange(studio.RATE)
    samples = (np.sin(2 * np.pi * 220 * phase / studio.RATE) * 0.15).astype(np.float32)
    sf.write(buffer, samples, studio.RATE, format="WAV", subtype="PCM_24")
    return buffer.getvalue()


def template(project, asset):
    doc = {field: project[field] for field in studio.StudioDocument.model_fields}
    doc["clips"] = [
        {"id": "clip-one", "asset_id": asset["id"], "track_id": "track-1", "start": 0, "out_point": 0.7,
         "fade_in": 0.05, "automation": [{"time": 0, "db": -4}, {"time": 0.7, "db": 0}]},
        {"id": "clip-two", "asset_id": asset["id"], "track_id": "track-1", "start": 0.5, "in_point": 0.1,
         "out_point": 0.8, "clarity": 10, "warmth": 15, "echo": 10},
    ]
    return doc


def complete(client, url, revision, kind):
    started = client.post(url + "/jobs", json={"revision": revision, "kind": kind})
    assert started.status_code == 202, started.text
    identity = started.json()["id"]
    for _ in range(100):
        current = client.get(f"{url}/jobs/{identity}").json()
        if current["status"] != "running":
            assert current["status"] == "complete", current
            return current["result"]
        time.sleep(0.02)
    raise AssertionError("Studio job did not complete")


def test_studio_revision_render_pack_and_reopen(tmp_path, monkeypatch):
    monkeypatch.setattr(studio, "DATA_DIR", tmp_path)
    client = TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 14011))
    projects = "/api/studio/projects"
    assert client.get(projects, headers={"Origin": "https://example.org"}).status_code == 403
    project = client.post(projects, json={"name": "Podcast clips"}).json()
    url = f"{projects}/{project['id']}"
    original = source_bytes()
    asset = client.post(url + "/assets", files={"file": ("clip.wav", original)}).json()
    document = template(project, asset)
    saved = client.put(url, json={"revision": 1, "label": "Trim and overlap", "document": document})
    assert saved.status_code == 200, saved.text
    revision = saved.json()["revision"]
    assert revision == 2
    assert client.put(url, json={"revision": 1, "label": "Stale edit", "document": document}).status_code == 409
    assert client.get(url).json()["clips"][1]["start"] == 0.5

    result = complete(client, url, revision, "render")
    output = client.get(result["url"]).content
    proof = client.get(result["report_url"]).json()
    assert proof["output_sha256"] == hashlib.sha256(output).hexdigest()
    assert proof["source_sha256"][asset["id"]] == hashlib.sha256(original).hexdigest()
    pcm, rate = sf.read(io.BytesIO(output))
    assert (len(pcm), rate) == (57600, 48000)
    assert np.max(np.abs(pcm[:400])) < np.max(np.abs(pcm[3500:7000]))
    assert studio.crossfades(saved.json()["clips"]) == {"clip-one": [(0.5, 0.7, False)], "clip-two": [(0.5, 0.7, True)]}
    assert client.get(f"{url}/assets/{asset['id']}/media?original=true").content == original

    package = client.get(complete(client, url, revision, "consolidate")["url"]).content
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        root = "AudioEnhancerMAX Project/"
        manifest = json.loads(archive.read(root + "Project.json"))
        assert archive.read(root + manifest["assets"][0]["file"]) == original
    reopened = client.post(projects + "/from-package", files={"file": ("session.zip", package)})
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["id"] != project["id"]
    assert len(reopened.json()["clips"]) == 2
    restored = client.post(url + "/restore", json={"revision": revision, "target": 1})
    assert restored.status_code == 200
    assert restored.json()["clips"] == []


def test_relink_requires_the_exact_original(tmp_path, monkeypatch):
    monkeypatch.setattr(studio, "DATA_DIR", tmp_path)
    path = "/api/studio/projects"
    client = TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 14011))
    project = client.post(path, json={"name": "Relink"}).json()
    url = f"{path}/{project['id']}"
    source = source_bytes()
    item = client.post(url + "/assets", files={"file": ("original.wav", source)}).json()
    original, _ = studio.media_paths(project["id"], item)
    original.unlink()
    assert client.get(url).json()["assets"][0]["available"] is False
    endpoint = f"{url}/assets/{item['id']}/relink"
    assert client.post(endpoint, files={"file": ("different.wav", b"other bytes")}).status_code == 422
    assert not original.exists()
    assert client.post(endpoint, files={"file": ("moved.wav", source)}).status_code == 200
    assert original.read_bytes() == source
