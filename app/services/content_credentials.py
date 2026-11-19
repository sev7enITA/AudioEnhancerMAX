"""Local creation and validation of embedded C2PA Content Credentials."""
from __future__ import annotations

import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

from app.config import DATA_DIR, RESOURCE_DIR
from app.services.artifact_store import sha256_file

MEDIA_TYPES = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".flac": "audio/flac",
    ".m4a": "audio/mp4",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
}
ASSERTION_LABEL = "com.fabriziodegni.audioenhancermax.processing"
TRUST_DIRECTORY = RESOURCE_DIR / "app" / "resources" / "c2pa"
TRUST_SNAPSHOT_NEXT_UPDATE = datetime(2027, 2, 2, 17, 2, 28, tzinfo=timezone.utc)
OFFLINE_SETTINGS = {
    "core": {"allowed_network_hosts": [], "decode_identity_assertions": False},
    "verify": {
        "remote_manifest_fetch": False,
        "ocsp_fetch": False,
        "ocsp_fetch_should_override": False,
        "verify_trust": True,
    },
}


def _trust_anchors() -> list[dict]:
    """Use the shipped public lists until the publisher's next-update date."""
    if datetime.now(timezone.utc) >= TRUST_SNAPSHOT_NEXT_UPDATE:
        return []
    return [
        {
            "trust_kind": kind,
            "trust_anchors": (TRUST_DIRECTORY / filename).read_text(encoding="ascii"),
        }
        for kind, filename in (
            ("manifest", "C2PA-TRUST-LIST.pem"),
            ("tsa", "C2PA-TSA-TRUST-LIST.pem"),
        )
    ]


def _validation_context(c2pa):
    return c2pa.Context.from_dict({
        **OFFLINE_SETTINGS,
        "trust": {"anchors": _trust_anchors()},
    })


class CredentialsUnavailable(RuntimeError):
    """The local SDK or signing identity is unavailable."""


class CredentialsError(ValueError):
    """The media or its provenance could not be processed."""


def _sdk():
    try:
        import c2pa
    except (ImportError, OSError, RuntimeError) as exc:
        raise CredentialsUnavailable("The Content Credentials SDK is unavailable in this build.") from exc
    return c2pa


def _signing_files() -> tuple[Path, Path]:
    directory = DATA_DIR / "c2pa"
    return directory / "signing-chain.pem", directory / "signing-key.pem"


def _signer(c2pa):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    chain, key = _signing_files()
    try:
        if not chain.is_file() or not key.is_file() or key.is_symlink():
            raise OSError("Signing credentials unavailable")
        if os.name == "posix" and (stat.S_IMODE(key.stat().st_mode) & 0o077):
            raise OSError("Signing key permissions are too broad")
        certificates = chain.read_bytes()
        public_key = x509.load_pem_x509_certificates(certificates)[0].public_key()
        private_key = serialization.load_pem_private_key(key.read_bytes(), password=None)
        if (not isinstance(private_key, ec.EllipticCurvePrivateKey)
                or not isinstance(private_key.curve, ec.SECP256R1)
                or not isinstance(public_key, ec.EllipticCurvePublicKey)
                or private_key.public_key().public_numbers() != public_key.public_numbers()):
            raise ValueError("The P-256 key must match the leaf certificate")

        def sign(message: bytes) -> bytes:
            return private_key.sign(message, ec.ECDSA(hashes.SHA256()))

        # A local callback only performs the signature. No TSA or remote signer.
        return c2pa.Signer.from_callback(sign, c2pa.C2paSigningAlg.ES256, certificates.decode("ascii"))
    except (OSError, TypeError, ValueError, c2pa.C2paError) as exc:
        raise CredentialsUnavailable(
            "Configure a matching C2PA signing certificate and an ES256 (P-256) private key "
            "in the app data c2pa folder. On macOS/Linux the key must be private (chmod 600)."
        ) from exc


def capabilities() -> dict:
    try:
        c2pa = _sdk()
    except CredentialsUnavailable:
        return {"inspect": False, "sign": False}
    try:
        with _signer(c2pa):
            return {"inspect": True, "sign": True}
    except CredentialsUnavailable:
        return {"inspect": True, "sign": False}


def inspect_stream(stream: BinaryIO, suffix: str) -> dict:
    """Return a small display projection and preserve the SDK's trust distinction."""
    if suffix not in MEDIA_TYPES:
        raise CredentialsError("Select a WAV, MP3, FLAC, M4A, MP4 or MOV file.")
    c2pa = _sdk()
    try:
        with _validation_context(c2pa) as context:
            reader = c2pa.Reader.try_create(MEDIA_TYPES[suffix], stream, context=context)
            if reader is None:
                return {"status": "missing", "embedded": False}
            with reader:
                manifest = reader.get_active_manifest() or {}
                state = reader.get_validation_state()
                signature = manifest.get("signature_info") or {}
                validation = reader.get_validation_results() or {}
                failures = (validation.get("activeManifest") or {}).get("failure", [])
                actions = [
                    action["action"]
                    for assertion in manifest.get("assertions", [])
                    if assertion.get("label") in {"c2pa.actions", "c2pa.actions.v2"}
                    for action in assertion.get("data", {}).get("actions", [])
                    if isinstance(action.get("action"), str)
                ]
                return {
                    "status": {"Trusted": "trusted", "Valid": "valid"}.get(state, "invalid"),
                    "embedded": reader.is_embedded(),
                    "signer": signature.get("issuer"),
                    "actions": actions,
                    "ingredient_count": len(manifest.get("ingredients", [])),
                    "failure_codes": [item["code"] for item in failures if "code" in item],
                }
    except c2pa.C2paError.RemoteManifest:
        return {"status": "remote", "embedded": False}
    except c2pa.C2paError.ManifestNotFound:
        return {"status": "missing", "embedded": False}
    except (c2pa.C2paError, OSError, ValueError) as exc:
        raise CredentialsError("The file could not be read for Content Credentials verification.") from exc


def sign_export(
    export: Path,
    parent: Path,
    destination: Path,
    *,
    revision: str,
    operation: str,
    app_version: str,
    report_sha256: str,
) -> dict:
    c2pa = _sdk()
    if export.suffix not in MEDIA_TYPES or parent.suffix not in MEDIA_TYPES:
        raise CredentialsError("This export or its source has an unsupported format.")
    changes = "c2pa.edited" if operation == "speech_edit" else "c2pa.modified"
    manifest = {
        "claim_generator_info": [{"name": "AudioEnhancerMAX", "version": app_version}],
        "title": "AudioEnhancerMAX export",
        "assertions": [
            {"label": "c2pa.actions.v2", "data": {"actions": [{"action": changes}]}},
            {"label": ASSERTION_LABEL, "data": {
                "schema_version": 1,
                "operation": operation,
                "artifact_revision": revision,
                "processing_report_sha256": report_sha256,
                "unsigned_export_sha256": sha256_file(export),
            }},
        ],
    }
    try:
        with (
            _signer(c2pa) as signer,
            _validation_context(c2pa) as context,
            c2pa.Builder.from_json(manifest, context=context) as builder,
            parent.open("rb") as ingredient,
            export.open("rb") as source,
            destination.open("w+b") as output,
        ):
            builder.set_intent(c2pa.C2paBuilderIntent.EDIT)
            builder.add_ingredient(
                {"title": "Source media", "relationship": "parentOf"},
                MEDIA_TYPES[parent.suffix],
                ingredient,
            )
            builder.sign(signer, MEDIA_TYPES[export.suffix], source, output)
            output.seek(0)
            verification = inspect_stream(output, export.suffix)
        if verification["status"] not in {"valid", "trusted"} or not verification["embedded"]:
            raise CredentialsError("The signed copy did not pass Content Credentials verification.")
        return verification
    except (c2pa.C2paError, OSError) as exc:
        raise CredentialsError("Could not sign this audio with the configured C2PA identity.") from exc


def select_parent(source: Path, report: dict, original_record: Path) -> Path:
    """Use the original container when its ingest record matches the decoded source."""
    provenance = report.get("provenance", {}).get("source", {})
    source_hash = sha256_file(source)
    if provenance.get("name") != source.name or provenance.get("sha256") != source_hash:
        raise CredentialsError("The source differs from the processing report. Process it again.")
    if not original_record.is_file():
        return source
    record = json.loads(original_record.read_text(encoding="utf-8"))
    if record.get("decoded_sha256") != source_hash:
        raise CredentialsError("The original import cannot be linked to this result. Import it again.")
    suffix = record.get("original_suffix")
    if suffix not in MEDIA_TYPES:
        return source
    original = source.with_suffix(suffix)
    if not original.is_file() or sha256_file(original) != record.get("original_sha256"):
        raise CredentialsError("The original import differs from its recorded source. Import it again.")
    return original
