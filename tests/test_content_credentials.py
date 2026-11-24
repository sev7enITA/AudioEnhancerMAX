"""Exercise actual C2PA signing, integrity and source provenance."""
import hashlib
import io
import json
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

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
    assert "x-c2pa-timestamp" not in response.headers
    assert response.headers["x-audio-revision"] == revision
    assert client.get(f"/api/download/{file_id}", params=params).content == unsigned.content
    with c2pa.Reader(fmt, io.BytesIO(response.content)) as reader:
        manifest = reader.get_active_manifest()
        assert "private-name.wav" not in reader.json()
        assert manifest["ingredients"][0]["relationship"] == "parentOf"
        assertion = next(item["data"] for item in manifest["assertions"]
                         if item["label"] == content_credentials.ASSERTION_LABEL)
        report = outputs / f"{file_id}_processed_{revision}.report.json"
        downloaded_report = client.get(f"/api/reports/{file_id}", params={"revision": revision})
        assert downloaded_report.status_code == 200
        assert downloaded_report.content == report.read_bytes()
        assert assertion["processing_report_sha256"] == hashlib.sha256(downloaded_report.content).hexdigest()
        assert assertion["unsigned_export_sha256"] == hashlib.sha256(unsigned.content).hexdigest()
        assert assertion["artifact_revision"] == revision
        assert assertion["executed_steps"] == [{"step": "normalize", "result": "changed"}]
    original_samples, original_rate = sf.read(io.BytesIO(unsigned.content))
    signed_samples, signed_rate = sf.read(io.BytesIO(response.content))
    assert signed_rate == original_rate
    np.testing.assert_array_equal(signed_samples, original_samples)
    result = client.post("/api/content-credentials/inspect", files={"file": (f"result.{fmt}", response.content)})
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "valid"
    assert result.json()["timestamp_trusted"] is False
    assert result.json()["actions"] == ["c2pa.opened", "c2pa.enhanced"]
    assert result.json()["declared_processing_steps"] == [{"step": "normalize", "result": "changed"}]


def test_signed_noop_records_execution_without_claiming_change(api, monkeypatch):
    from app.services import enhancement

    client, _, _ = api
    monkeypatch.setattr(enhancement, "normalize_volume", lambda audio, *_: audio)
    file_id, revision = process(client, wav_bytes(), "source.wav")
    response = signed_request(client, file_id, revision, "wav")
    assert response.status_code == 200, response.text
    with c2pa.Reader("wav", io.BytesIO(response.content)) as reader:
        assertions = {
            item["label"]: item["data"] for item in reader.get_active_manifest()["assertions"]
        }
    assert assertions[content_credentials.ASSERTION_LABEL]["executed_steps"] == [
        {"step": "normalize", "result": "unchanged"},
    ]
    actions = assertions["c2pa.actions.v2"]
    assert actions["allActionsIncluded"] is False
    assert [item["action"] for item in actions["actions"]] == ["c2pa.opened"]


def test_unexecuted_and_unknown_operations_do_not_become_claims(api, tmp_path):
    # Exercise the signed payload with the equivalent of a partially populated
    # report, including a change marker for an operation that did not run.
    source = tmp_path / "unsigned.wav"
    source.write_bytes(wav_bytes())
    signed = tmp_path / "signed.wav"
    status = content_credentials.sign_export(
        source, source, signed, revision="a" * 32, operation="processed",
        app_version="test", report_sha256="1" * 64,
        executed_steps=["normalize", "private transcript", "auto_eq", "normalize"],
        changed_steps=["normalize", "private transcript", "audio_watermark"],
    )
    assert status["actions"] == ["c2pa.opened", "c2pa.enhanced"]
    assert status["declared_processing_steps"] == [
        {"step": "normalize", "result": "changed"},
        {"step": "auto_eq", "result": "unchanged"},
    ]
    with c2pa.Reader(signed) as reader:
        assert "private transcript" not in reader.json()
        assertion = next(item["data"] for item in reader.get_active_manifest()["assertions"]
                         if item["label"] == content_credentials.ASSERTION_LABEL)
    assert assertion["executed_steps"] == [
        {"step": "normalize", "result": "changed"},
        {"step": "auto_eq", "result": "unchanged"},
    ]
    assert assertion["execution_scope"] == "recognized_observed_steps"
    assert assertion["unsigned_export_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()


def test_replaced_export_cannot_be_signed_for_a_revision(api, tmp_path):
    source = tmp_path / "unsigned.wav"
    source.write_bytes(wav_bytes())
    signed = tmp_path / "signed.wav"
    with pytest.raises(content_credentials.CredentialsError, match="export differs"):
        content_credentials.sign_export(
            source, source, signed, revision="a" * 32, operation="processed",
            app_version="test", report_sha256="1" * 64, expected_export_sha256="0" * 64,
        )


def test_keychain_profile_cannot_fall_back_to_existing_test_key(api, tmp_path, monkeypatch):
    client, _, _ = api
    file_id, revision = process(client, wav_bytes(), "source.wav")
    directory = tmp_path / "c2pa"
    assert (directory / "signing-key.pem").exists()
    (directory / "signing.json").write_text(json.dumps({
        "keychain_tag": "missing-key", "tsa_url": "https://tsa.example.com",
    }))

    def missing_key(_label):
        raise OSError("Keychain key missing")

    monkeypatch.setitem(sys.modules, "app.services.c2pa_keychain", SimpleNamespace(signing_key=missing_key))
    assert client.get("/api/content-credentials").json() == {"inspect": True, "sign": False}
    assert signed_request(client, file_id, revision, "wav").status_code == 503


def test_keychain_export_rejects_signed_copy_without_required_timestamp(api, tmp_path, monkeypatch):
    client, _, _ = api
    file_id, revision = process(client, wav_bytes(), "source.wav")
    directory = tmp_path / "c2pa"
    test_key = serialization.load_pem_private_key((directory / "signing-key.pem").read_bytes(), password=None)
    (directory / "signing-key.pem").unlink()
    (directory / "signing.json").write_text(json.dumps({
        "keychain_tag": "pilot", "tsa_url": "https://tsa.example.com/token",
    }))
    keychain_key = SimpleNamespace(
        sign=lambda message: test_key.sign(message, ec.ECDSA(hashes.SHA256())),
        public_key_bytes=lambda: test_key.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint,
        ),
    )
    monkeypatch.setitem(sys.modules, "app.services.c2pa_keychain", SimpleNamespace(signing_key=lambda _: keychain_key))
    real_signer = c2pa.Signer.from_callback

    def signer_without_timestamp(callback, algorithm, certificates, tsa_url):
        assert tsa_url == "https://tsa.example.com/token"
        return real_signer(callback, algorithm, certificates)

    monkeypatch.setattr(c2pa.Signer, "from_callback", staticmethod(signer_without_timestamp))
    response = signed_request(client, file_id, revision, "wav")
    assert response.status_code == 409, response.text
    assert "trusted RFC 3161 timestamp" in response.text


def test_expired_trust_list_disables_timestamped_signing_but_preserves_ordinary_export(
    api, tmp_path, monkeypatch,
):
    client, _, _ = api
    file_id, revision = process(client, wav_bytes(), "source.wav")
    signed = signed_request(client, file_id, revision, "wav")
    assert signed.status_code == 200
    (tmp_path / "c2pa" / "signing.json").write_text(json.dumps({
        "keychain_tag": "pilot", "tsa_url": "https://tsa.example.com/token",
    }))
    monkeypatch.setattr(content_credentials, "_trust_snapshot_expired", lambda: True)

    capability = client.get("/api/content-credentials").json()
    assert capability["inspect"] is True
    assert capability["sign"] is False
    assert "trust lists have expired" in capability["sign_error"]
    rejected = signed_request(client, file_id, revision, "wav")
    assert rejected.status_code == 503
    assert rejected.json()["detail"] == capability["sign_error"]
    assert client.get(f"/api/download/{file_id}", params={"revision": revision}).status_code == 200

    inspected = client.post(
        "/api/content-credentials/inspect", files={"file": ("signed.wav", signed.content)},
    ).json()
    assert inspected["status"] == "valid"
    assert inspected["trust_snapshot_expired"] is True


@pytest.mark.parametrize("fmt", ("wav", "flac"))
def test_revision_watermark_survives_lossless_export_and_signing(api, fmt):
    from app.services.watermarking import detect_watermark

    client, _, _ = api
    upload = client.post("/api/upload", files={"file": ("source.wav", wav_bytes())})
    assert upload.status_code == 200
    file_id = upload.json()["file_id"]
    request = {"file_id": file_id, "options": {"watermark_identifier": "episode-04"}}
    request["options"]["output_format"] = "mp3"
    assert client.post("/api/process", json=request).status_code == 400

    request["options"]["output_format"] = fmt
    processed = client.post("/api/process", json=request)
    assert processed.status_code == 200, processed.text
    revision = processed.json()["revision"]
    signed = signed_request(client, file_id, revision, fmt)
    assert signed.status_code == 200, signed.text
    samples, sample_rate = sf.read(io.BytesIO(signed.content), dtype="float32")
    assert detect_watermark(samples, sample_rate) == {
        "detected": True, "payload": "episode-04", "method": "pcm24-revision",
    }
    assert signed_request(client, file_id, revision, "mp3").status_code == 409

    report = client.get(f"/api/reports/{file_id}", params={"revision": revision})
    assert report.status_code == 200
    assert report.json()["pipeline"][0]["step"] == "audio_watermark"
    with c2pa.Reader(fmt, io.BytesIO(signed.content)) as reader:
        assert "episode-04" not in reader.json()
        assertion = next(item["data"] for item in reader.get_active_manifest()["assertions"]
                         if item["label"] == content_credentials.ASSERTION_LABEL)
    assert assertion["processing_report_sha256"] == hashlib.sha256(report.content).hexdigest()
    result = client.post("/api/content-credentials/inspect", files={"file": (f"signed.{fmt}", signed.content)})
    assert result.status_code == 200, result.text
    assert result.json()["actions"] == ["c2pa.opened", "c2pa.watermarked.unbound"]


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
    assert result.json()["declared_processing_steps"] is None
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
    signed_result = content_credentials.sign_export(
        source, source, signed_source, revision="a" * 32, operation="processed",
        app_version="test", report_sha256="1" * 64,
    )
    assert signed_result["actions"] == ["c2pa.opened"]
    assert signed_result["declared_processing_steps"] is None
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
