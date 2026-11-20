"""Local creation and validation of embedded C2PA Content Credentials."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO
from urllib.parse import urlsplit

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
PROCESSING_ACTIONS = {
    "remove_noise": ("c2pa.enhanced", "Applied background-noise reduction"),
    "wind_noise_remover": ("c2pa.enhanced", "Applied wind-noise filtering"),
    "buzzing_noise_remover": ("c2pa.enhanced", "Applied hum filtering"),
    "static_noise_remover": ("c2pa.enhanced", "Applied static-noise filtering"),
    "reverb_echo_remover": ("c2pa.enhanced", "Applied reverb and echo processing"),
    "remove_mouth_sounds": ("c2pa.enhanced", "Applied mouth-sound processing"),
    "remove_filler_words": ("c2pa.edited", "Edited filler words"),
    "eliminate_hesitations": ("c2pa.edited", "Edited hesitations"),
    "remove_stuttering": ("c2pa.edited", "Edited stutters"),
    "remove_breaths": ("c2pa.enhanced", "Applied breath processing"),
    "remove_long_silences": ("c2pa.edited", "Edited silent passages"),
    "keep_music": ("c2pa.edited", "Applied music isolation"),
    "auto_eq": ("c2pa.enhanced", "Applied automatic equalization"),
    "studio_sound": ("c2pa.enhanced", "Applied studio sound processing"),
    "frequency_restoration": ("c2pa.enhanced", "Applied frequency restoration"),
    "normalize": ("c2pa.enhanced", "Normalized audio level"),
    "audio_watermark": ("c2pa.watermarked.unbound", "Embedded an audio watermark"),
    "speech_edl_render": ("c2pa.edited", "Rendered approved speech edits"),
}
TRUST_DIRECTORY = RESOURCE_DIR / "app" / "resources" / "c2pa"
TRUST_SNAPSHOT_NEXT_UPDATE = datetime(2027, 2, 2, 17, 24, 49, tzinfo=timezone.utc)
OFFLINE_SETTINGS = {
    "core": {"allowed_network_hosts": [], "decode_identity_assertions": False},
    "verify": {
        "remote_manifest_fetch": False,
        "ocsp_fetch": False,
        "ocsp_fetch_should_override": False,
        "verify_trust": True,
    },
}


def _trust_snapshot_expired() -> bool:
    return datetime.now(timezone.utc) >= TRUST_SNAPSHOT_NEXT_UPDATE


def _trust_anchors() -> list[dict]:
    """Use the shipped public lists until the publisher's next-update date."""
    if _trust_snapshot_expired():
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


def _validation_context(c2pa, *, timestamp_host: str | None = None):
    core = OFFLINE_SETTINGS["core"]
    if timestamp_host:
        core = {**core, "allowed_network_hosts": [timestamp_host]}
    return c2pa.Context.from_dict({
        **OFFLINE_SETTINGS,
        "core": core,
        "trust": {"anchors": _trust_anchors()},
    })


class CredentialsUnavailable(RuntimeError):
    """The local SDK or signing identity is unavailable."""


class TimestampTrustExpired(CredentialsUnavailable):
    """The packaged timestamp trust list requires an app update."""


EXPIRED_TRUST_MESSAGE = (
    "The built-in C2PA trust lists have expired. Update AudioEnhancerMAX "
    "to sign with a trusted timestamp. An ordinary export is still available."
)


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


def _keychain_profile(path: Path) -> tuple[str, str, str] | None:
    if path.is_symlink():
        raise ValueError("The C2PA signing config must be a local file.")
    try:
        settings = json.loads(path.read_bytes())
    except FileNotFoundError:
        return None
    if not isinstance(settings, dict) or set(settings) != {"keychain_tag", "tsa_url"}:
        raise ValueError("signing.json must contain keychain_tag and tsa_url.")
    label, url = settings["keychain_tag"], settings["tsa_url"]
    if (not isinstance(label, str) or not isinstance(url, str)
            or any(character.isspace() for character in url)):
        raise ValueError("The C2PA Keychain tag and timestamp URL must be text.")
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.fragment or parsed.port == 0):
        raise ValueError("Configure the HTTPS endpoint of a C2PA timestamp authority.")
    return label, url, parsed.hostname


def _signer(c2pa):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    chain, key = _signing_files()
    try:
        profile = _keychain_profile(chain.with_name("signing.json"))
        certificates = chain.read_text(encoding="ascii")
        leaf = x509.load_pem_x509_certificates(certificates.encode("ascii"))[0]
        public_key = leaf.public_key()
        if not isinstance(public_key, ec.EllipticCurvePublicKey) or not isinstance(public_key.curve, ec.SECP256R1):
            raise ValueError("The signing certificate must use P-256.")
        if profile is not None:
            if _trust_snapshot_expired():
                raise TimestampTrustExpired(EXPIRED_TRUST_MESSAGE)
            from app.services.c2pa_keychain import signing_key

            label, url, host = profile
            mac_key = signing_key(label)
            expected = public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
            if mac_key.public_key_bytes() != expected:
                raise ValueError("The Keychain key must match the signing certificate.")
            return c2pa.Signer.from_callback(mac_key.sign, c2pa.C2paSigningAlg.ES256, certificates, tsa_url=url), host
        if key.is_symlink():
            raise OSError("Signing credentials unavailable")
        if os.name == "posix" and (stat.S_IMODE(key.stat().st_mode) & 0o077):
            raise OSError("Signing key permissions are too broad")
        private_key = serialization.load_pem_private_key(key.read_bytes(), password=None)
        if (not isinstance(private_key, ec.EllipticCurvePrivateKey)
                or not isinstance(private_key.curve, ec.SECP256R1)
                or private_key.public_key().public_numbers() != public_key.public_numbers()):
            raise ValueError("The P-256 key must match the leaf certificate")

        def sign(message: bytes) -> bytes:
            return private_key.sign(message, ec.ECDSA(hashes.SHA256()))

        return c2pa.Signer.from_callback(sign, c2pa.C2paSigningAlg.ES256, certificates), None
    except (ImportError, OSError, TypeError, ValueError, c2pa.C2paError) as exc:
        raise CredentialsUnavailable(
            "Configure a C2PA signing certificate and its matching P-256 Keychain key or local test key. "
            "Check the app data c2pa folder. On macOS/Linux a test key must have mode 0600."
        ) from exc


def capabilities() -> dict:
    try:
        c2pa = _sdk()
    except CredentialsUnavailable:
        return {"inspect": False, "sign": False}
    try:
        signer, _ = _signer(c2pa)
        with signer:
            return {"inspect": True, "sign": True}
    except TimestampTrustExpired as exc:
        return {"inspect": True, "sign": False, "sign_error": str(exc)}
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
                validation = (reader.get_validation_results() or {}).get("activeManifest") or {}
                failures = validation.get("failure", [])
                successes = {item["code"] for item in validation.get("success", []) if "code" in item}
                actions = [
                    action["action"]
                    for assertion in manifest.get("assertions", [])
                    if assertion.get("label") in {"c2pa.actions", "c2pa.actions.v2"}
                    for action in assertion.get("data", {}).get("actions", [])
                    if isinstance(action.get("action"), str)
                ]
                processing_digest = next((
                    value
                    for assertion in (manifest.get("assertions") or [])
                    if assertion.get("label") == ASSERTION_LABEL
                    if isinstance(data := assertion.get("data"), dict)
                    if isinstance(value := data.get("processing_report_sha256"), str)
                    and len(value) == 64 and all(char in "0123456789abcdefABCDEF" for char in value)
                ), None)
                declared_steps = None
                if state in {"Valid", "Trusted"}:
                    declared_steps = _read_declared_processing_steps(manifest)
                return {
                    "status": {"Trusted": "trusted", "Valid": "valid"}.get(state, "invalid"),
                    "embedded": reader.is_embedded(),
                    "signer": signature.get("issuer"),
                    "actions": actions,
                    "ingredient_count": len(manifest.get("ingredients", [])),
                    "processing_report_sha256": processing_digest,
                    "declared_processing_steps": declared_steps,
                    "failure_codes": [item["code"] for item in failures if "code" in item],
                    "timestamp_trusted": {"timeStamp.trusted", "timeStamp.validated"} <= successes,
                    "trust_snapshot_expired": _trust_snapshot_expired(),
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
    expected_export_sha256: str | None = None,
    executed_steps: list[str] | None = None,
    changed_steps: list[str] | None = None,
) -> dict:
    c2pa = _sdk()
    if export.suffix not in MEDIA_TYPES or parent.suffix not in MEDIA_TYPES:
        raise CredentialsError("This export or its source has an unsupported format.")
    changes, execution = _processing_actions(executed_steps, changed_steps)
    parent_label = "source-media"
    actions = [
        {"action": "c2pa.opened", "parameters": {"ingredientIds": [parent_label]}},
        *changes,
    ]
    processing_evidence = {
        "schema_version": 2,
        "operation": operation,
        "artifact_revision": revision,
        "processing_report_sha256": report_sha256,
    }
    if execution is not None:
        processing_evidence["executed_steps"] = execution
        processing_evidence["execution_scope"] = "recognized_observed_steps"
    manifest = {
        "claim_generator_info": [{"name": "AudioEnhancerMAX", "version": app_version}],
        "title": "AudioEnhancerMAX export",
        "assertions": [
            {"label": "c2pa.actions.v2", "data": {"actions": actions, "allActionsIncluded": False}},
            {"label": ASSERTION_LABEL, "data": processing_evidence},
        ],
    }
    try:
        signer, timestamp_host = _signer(c2pa)
        with (
            signer,
            _validation_context(c2pa, timestamp_host=timestamp_host) as context,
            parent.open("rb") as ingredient,
            export.open("rb") as export_stream,
            tempfile.TemporaryFile() as source,
            destination.open("w+b") as output,
        ):
            digest = hashlib.sha256()
            for chunk in iter(lambda: export_stream.read(1024 * 1024), b""):
                digest.update(chunk)
                source.write(chunk)
            unsigned_hash = digest.hexdigest()
            if expected_export_sha256 is not None and expected_export_sha256 != unsigned_hash:
                raise CredentialsError("The export differs from this revision. Process it again.")
            processing_evidence["unsigned_export_sha256"] = unsigned_hash
            source.seek(0)
            with c2pa.Builder.from_json(manifest, context=context) as builder:
                builder.set_intent(c2pa.C2paBuilderIntent.EDIT)
                builder.add_ingredient(
                    {"title": "Source media", "relationship": "parentOf", "label": parent_label},
                    MEDIA_TYPES[parent.suffix],
                    ingredient,
                )
                builder.sign(signer, MEDIA_TYPES[export.suffix], source, output)
            output.seek(0)
            verification = inspect_stream(output, export.suffix)
        if verification["status"] not in {"valid", "trusted"} or not verification["embedded"]:
            raise CredentialsError("The signed copy did not pass Content Credentials verification.")
        if timestamp_host and not verification["timestamp_trusted"]:
            raise CredentialsError("The configured timestamp authority did not produce a trusted RFC 3161 timestamp.")
        return verification
    except (c2pa.C2paError, OSError) as exc:
        raise CredentialsError("Could not sign this audio with the configured C2PA identity.") from exc


def _processing_actions(
    executed_steps: list[str] | None,
    changed_steps: list[str] | None,
) -> tuple[list[dict[str, str]], list[dict[str, str]] | None]:
    """Project the revision report's observed execution into public, signed facts."""
    if not isinstance(executed_steps, list):
        return [], None
    known_steps = dict.fromkeys(
        step for step in executed_steps if isinstance(step, str) and step in PROCESSING_ACTIONS
    )
    changed = (
        set(changed_steps)
        if isinstance(changed_steps, list) and all(isinstance(step, str) for step in changed_steps)
        else None
    )
    actions = []
    execution = []
    for step in known_steps:
        if changed is None:
            result = "unknown"
        elif step in changed:
            result = "changed"
            action, description = PROCESSING_ACTIONS[step]
            actions.append({"action": action, "description": description})
        else:
            result = "unchanged"
        execution.append({"step": step, "result": result})
    return actions, execution


def _read_declared_processing_steps(manifest: dict) -> list[dict[str, str]] | None:
    """Expose a bounded projection of a cryptographically valid claim."""
    for assertion in manifest.get("assertions") or []:
        data = assertion.get("data")
        if assertion.get("label") != ASSERTION_LABEL or not isinstance(data, dict):
            continue
        steps = data.get("executed_steps")
        if data.get("schema_version") != 2 or not isinstance(steps, list):
            continue
        known_steps = {}
        for entry in steps[:len(PROCESSING_ACTIONS)]:
            if not isinstance(entry, dict):
                continue
            step, result = entry.get("step"), entry.get("result")
            if (isinstance(step, str) and step in PROCESSING_ACTIONS
                    and isinstance(result, str) and result in {"changed", "unchanged", "unknown"}):
                known_steps.setdefault(step, result)
        return [{"step": step, "result": result} for step, result in known_steps.items()]
    return None


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
