"""Exercise actual C2PA signing, integrity and source provenance."""
import hashlib
import io
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from app import main
from app.services import artifact_store, content_credentials, delivery_compliance, processing_report, smart_mode, speech_editor
from app.utils import audio_io

c2pa = pytest.importorskip("c2pa")
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID, ObjectIdentifier


@pytest.fixture
def signing_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(content_credentials, "DATA_DIR", tmp_path)
    folder = tmp_path / "c2pa"
    folder.mkdir()
    now = datetime.now(timezone.utc)
    root_key = ec.generate_private_key(ec.SECP256R1())
    leaf_key = ec.generate_private_key(ec.SECP256R1())
    root_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "AudioEnhancerMAX test CA")])
    leaf_name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "AudioEnhancerMAX test signer"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "AudioEnhancerMAX test only"),
    ])

    def issue(subject, issuer, key, is_ca):
        builder = (
            x509.CertificateBuilder()
            .subject_name(subject).issuer_name(issuer)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=30))
            .add_extension(x509.BasicConstraints(ca=is_ca, path_length=None), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
            .add_extension(x509.KeyUsage(
                digital_signature=True, content_commitment=False, key_encipherment=False,
                data_encipherment=False, key_agreement=False, key_cert_sign=is_ca, crl_sign=is_ca,
                encipher_only=False, decipher_only=False,
            ), critical=True)
        )
        if not is_ca:
            builder = builder.add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(root_key.public_key()), critical=False,
            ).add_extension(x509.ExtendedKeyUsage([
                ObjectIdentifier("1.3.6.1.4.1.62558.2.1"),
                x509.oid.ExtendedKeyUsageOID.EMAIL_PROTECTION,
            ]), critical=False)
        return builder.sign(root_key, hashes.SHA256())

    root = issue(root_name, root_name, root_key, True)
    leaf = issue(leaf_name, root_name, leaf_key, False)
    chain_path = folder / "signing-chain.pem"
    chain_path.write_bytes(leaf.public_bytes(serialization.Encoding.PEM) + root.public_bytes(serialization.Encoding.PEM))
    key_path = folder / "signing-key.pem"
    key_path.touch(mode=0o600)
    key_path.write_bytes(leaf_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption(),
    ))
    return root.public_bytes(serialization.Encoding.PEM).decode('ascii')


@pytest.fixture
def api(tmp_path, signing_identity, monkeypatch):
    uploads, outputs = tmp_path / "uploads", tmp_path / "outputs"
    uploads.mkdir()
    outputs.mkdir()
    for module in (main, audio_io):
        monkeypatch.setattr(module, "UPLOAD_DIR", uploads)
    for module in (main, audio_io, artifact_store, delivery_compliance, processing_report, speech_editor):
        monkeypatch.setattr(module, "OUTPUT_DIR", outputs)
    monkeypatch.setattr(smart_mode, "get_dynamic_parameters", lambda *args: {})
    return TestClient(main.app, base_url="http://127.0.0.1", client=("127.0.0.1", 40000)), uploads, outputs


def wav_bytes():
    audio = .12 * np.sin(np.arange(48000) * (2 * np.pi * 440 / 48000))
    data = io.BytesIO()
    sf.write(data, audio, 48000, format="WAV")
    return data.getvalue()


def process(client, content, name):
    upload = client.post("/api/upload", files={"file": (name, content)})
    assert upload.status_code == 200, upload.text
    file_id = upload.json()["file_id"]
    response = client.post("/api/process", json={"file_id": file_id, "options": {"normalize": True}})
    assert response.status_code == 200, response.text
    return file_id, response.json()["revision"]


def signed_request(client, file_id, revision, fmt):
    return client.post(f"/api/content-credentials/export/{file_id}", json={
        "revision": revision, "format": fmt, "version": "processed",
    })


@pytest.mark.parametrize("fmt", ("wav", "flac", "mp3"))
def test_real_signed_export_round_trip(api, fmt):
    client, _, outputs = api
    file_id, revision = process(client, wav_bytes(), "private-name.wav")
    params = {"revision": revision, "format": fmt}
    unsigned = client.get(f"/api/download/{file_id}", params=params)
    response = signed_request(client, file_id, revision, fmt)
    assert response.status_code == 200, response.text
    assert response.headers["x-content-credentials"] == "valid"
    assert response.headers["x-audio-revision"] == revision
    assert client.get(f"/api/download/{file_id}", params=params).content == unsigned.content
    with c2pa.Reader(fmt, io.BytesIO(response.content)) as reader:
        manifest = reader.get_active_manifest()
        assert "private-name.wav" not in reader.json()
        assert manifest["ingredients"][0]["relationship"] == "parentOf"
        assertion = next(item["data"] for item in manifest["assertions"]
                         if item["label"] == content_credentials.ASSERTION_LABEL)
        report = outputs / f"{file_id}_processed_{revision}.report.json"
        assert assertion["processing_report_sha256"] == hashlib.sha256(report.read_bytes()).hexdigest()
        assert assertion["unsigned_export_sha256"] == hashlib.sha256(unsigned.content).hexdigest()
        assert assertion["artifact_revision"] == revision
    original_samples, original_rate = sf.read(io.BytesIO(unsigned.content))
    signed_samples, signed_rate = sf.read(io.BytesIO(response.content))
    assert signed_rate == original_rate
    np.testing.assert_array_equal(signed_samples, original_samples)
    result = client.post("/api/content-credentials/inspect", files={"file": (f"result.{fmt}", response.content)})
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "valid"
    assert {"c2pa.opened", "c2pa.modified"} <= set(result.json()["actions"])


def test_unsigned_tampered_stale_and_cross_origin(api):
    client, uploads, _ = api
    source = wav_bytes()
    file_id, revision = process(client, source, "source.wav")
    inspection = "/api/content-credentials/inspect"
    assert client.post(inspection, files={"file": ("test.wav", source)}).json()["status"] == "missing"
    assert client.post(inspection, files={"file": ("test.wav", source)}, headers={
        "Origin": "https://example.org",
    }).status_code == 403
    signed = signed_request(client, file_id, revision, "wav")
    assert signed.status_code == 200, signed.text
    tampered = bytearray(signed.content)
    audio_offset = tampered.index(b"data") + 8
    tampered[audio_offset + 20] ^= 1
    result = client.post(inspection, files={"file": ("test.wav", bytes(tampered))})
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "invalid"
    assert signed_request(client, file_id, "0" * 32, "wav").status_code == 409
    (uploads / f"{file_id}.wav").write_bytes(source[:-2] + b"\0\0")
    # Ensure the fixture bytes actually changed, independent of the final sample value.
    path = uploads / f"{file_id}.wav"
    data = bytearray(path.read_bytes())
    data[-2] ^= 1
    path.write_bytes(data)
    assert signed_request(client, file_id, revision, "wav").status_code == 409


def test_speech_editor_signs_the_render_without_exposing_the_transcript(api):
    client, uploads, _ = api
    upload = client.post("/api/upload", files={"file": ("speech.wav", wav_bytes())})
    assert upload.status_code == 200, upload.text
    file_id = upload.json()["file_id"]
    audio, sr = sf.read(uploads / f"{file_id}.wav")
    edl = speech_editor.build_speech_edl(
        file_id=file_id, audio=audio, sr=sr,
        transcription={"text": "Private synthetic transcript", "language": "en", "segments": []},
    )
    edl = speech_editor.add_manual_speech_edit(edl, {
        "start": .2, "end": .4, "action": "mute", "decision": "apply",
        "text": "Private synthetic transcript",
    }, expected_revision=edl["revision"])
    render = client.post(f"/api/speech-editor/{file_id}/render", json={
        "revision": edl["revision"], "output_format": "wav",
    })
    assert render.status_code == 200, render.text
    export = client.post(f"/api/content-credentials/export/{file_id}", json={
        "version": "speech_edit", "format": "wav", "revision": render.json()["revision"],
    })
    assert export.status_code == 200, export.text
    with c2pa.Reader("wav", io.BytesIO(export.content)) as reader:
        assert "Private synthetic transcript" not in reader.json()
    inspection = client.post("/api/content-credentials/inspect", files={
        "file": ("speech.wav", export.content),
    })
    assert "c2pa.edited" in inspection.json()["actions"]


def test_inherited_credential_survives_flac_ingest(api, tmp_path):
    client, _, _ = api
    audio, sr = sf.read(io.BytesIO(wav_bytes()))
    source = tmp_path / "source.flac"
    sf.write(source, audio, sr)
    signed_source = tmp_path / "signed.flac"
    content_credentials.sign_export(
        source, source, signed_source, revision="a" * 32, operation="processed",
        app_version="test", report_sha256="1" * 64,
    )
    file_id, revision = process(client, signed_source.read_bytes(), "incoming.flac")
    response = signed_request(client, file_id, revision, "wav")
    assert response.status_code == 200, response.text
    with c2pa.Reader("wav", io.BytesIO(response.content)) as reader:
        assert reader.get_active_manifest()["ingredients"][0]["format"] == "audio/flac"
        assert reader.get_active_manifest()["ingredients"][0]["active_manifest"]


def test_missing_key_allows_verification_but_refuses_signature(api, tmp_path):
    client, _, _ = api
    (tmp_path / "c2pa" / "signing-key.pem").unlink()
    assert client.get("/api/content-credentials").json() == {"inspect": True, "sign": False}
    file_id, revision = process(client, wav_bytes(), "source.wav")
    assert signed_request(client, file_id, revision, "wav").status_code == 503


def test_trust_requires_configured_anchor(api, signing_identity, monkeypatch):
    client, _, _ = api
    file_id, revision = process(client, wav_bytes(), "source.wav")
    signed = signed_request(client, file_id, revision, "wav")
    assert signed.status_code == 200
    assert signed.headers["x-content-credentials"] == "valid"

    monkeypatch.setattr(content_credentials, "_trust_anchors", lambda: [{
        "trust_kind": "manifest", "trust_anchors": signing_identity,
    }])
    result = client.post("/api/content-credentials/inspect", files={"file": ("source.wav", signed.content)})
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "trusted"
