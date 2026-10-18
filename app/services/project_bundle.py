"""Create a portable, checksum-backed local project capsule."""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
import uuid
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import PROJECTS_DIR


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact(role: str, path: Path) -> dict[str, Any]:
    return {
        "role": role,
        "name": Path(path).name,
        "size_bytes": Path(path).stat().st_size,
        "sha256": sha256_file(Path(path)),
    }


def build_manifest(
    *, file_id: str, app_version: str, app_build: str, source_path: Path,
    output_path: Path, optional_artifacts: dict[str, Path] | None = None,
    execution_boundary: str = "unknown",
) -> dict[str, Any]:
    artifacts = [_artifact("source", source_path), _artifact("processed-output", output_path)]
    for role, path in sorted((optional_artifacts or {}).items()):
        if Path(path).is_file():
            artifacts.append(_artifact(role, Path(path)))
    return _manifest(file_id, app_version, app_build, artifacts, execution_boundary)


def _manifest(file_id, app_version, app_build, artifacts, execution_boundary):
    return {
        "schema_version": 2,
        "product": "AudioEnhancerMAX",
        "app_version": app_version,
        "app_build": app_build,
        "file_id": file_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "execution_boundary": execution_boundary,
        "hash_algorithm": "SHA-256",
        "artifacts": artifacts,
        "verification": "Recompute each file SHA-256 and compare it with this manifest.",
    }


def revision_evidence(master_path: Path, artifact: dict) -> tuple[dict, str, list[str]]:
    """Capture one report read and derive editorial evidence only from that render."""
    inline = {}
    warnings = []
    boundary = "unknown"
    report_path = master_path.with_suffix(".report.json")
    report = None
    try:
        raw = report_path.read_bytes()
        inline["processing-report"] = (report_path.name, raw)
        report = json.loads(raw)
        bound = (
            isinstance(report, dict)
            and report.get("artifact_revision") == artifact["revision"]
            and report.get("provenance", {}).get("processed_output", {}).get("sha256")
            == artifact["exports"][artifact["master_format"]]["sha256"]
        )
        if not bound:
            raise ValueError("Report is not bound to the selected audio revision")
        location = report.get("privacy", {}).get("processing_location")
        if location in {"local", "local-and-trusted-lan"}:
            boundary = location
        else:
            warnings.append("Processing location is not recorded in the revision report.")
    except (OSError, ValueError, TypeError, AttributeError):
        report = None
        warnings.append("Processing report is missing, unreadable or unbound; execution location is unknown.")

    if artifact["version"] == "speech_edit":
        try:
            edits = report["speech_edits"]
            snapshot = edits["edl_snapshot"]
            if (snapshot["revision"] != edits["edl_revision"]
                    or snapshot["revision"] != report["options"]["edl_revision"]
                    or snapshot["file_id"] != artifact["file_id"]
                    or [item["id"] for item in snapshot["candidates"] if item["decision"] == "apply"]
                    != report["options"]["approved_candidate_ids"]):
                raise ValueError("Editorial snapshot does not match its render report")
            transcript = {
                "schema_version": 1,
                "origin": "speech-edl-render-snapshot",
                "artifact_revision": artifact["revision"],
                "edl_revision": snapshot["revision"],
                "language": snapshot["source"].get("language", ""),
                "text": snapshot["transcript"],
                "words": snapshot["source_words"],
            }
            for role, suffix, value in (("speech-edl", "speech-edl", snapshot), ("transcript", "transcript", transcript)):
                inline[role] = (master_path.with_suffix(f".{suffix}.json").name,
                                json.dumps(value, indent=2, ensure_ascii=False).encode("utf-8"))
        except (KeyError, ValueError, TypeError, AttributeError):
            warnings.append("No verified speech EDL snapshot is available for this render; current drafts are not substituted.")
    return inline, boundary, warnings


def export_project_capsule(
    *, file_id: str, app_version: str, app_build: str, source_path: Path,
    output_path: Path, optional_artifacts: dict[str, Path] | None = None,
    include_source: bool = False, execution_boundary: str = "unknown",
    inline_artifacts: dict[str, tuple[str, bytes]] | None = None,
    evidence_warnings: list[str] | None = None,
    artifact_revision: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    # Each digest and ZIP entry consume the very same stream of bytes. A path is
    # never reopened after hashing, even when a mutable sidecar is replaced.
    manifest = _manifest(file_id, app_version, app_build, [], execution_boundary)
    manifest["artifact_revision"] = artifact_revision
    manifest["evidence_warnings"] = list(evidence_warnings or [])
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    destination = PROJECTS_DIR / f"AudioEnhancerMAX-{file_id}-{uuid.uuid4().hex[:12]}-project-capsule.zip"
    temporary = destination.with_suffix(".tmp")
    paths = {"source": Path(source_path), "processed-output": Path(output_path), **(optional_artifacts or {})}
    inline = inline_artifacts or {}
    if set(paths) & set(inline):
        raise ValueError("Capsule roles must have exactly one source")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for role in [*paths, *inline]:
                included = role != "source" or include_source
                if role in inline:
                    name, data = inline[role]
                    stream = io.BytesIO(data)
                else:
                    path = Path(paths[role])
                    name = path.name
                    try:
                        stream = path.open("rb")
                    except FileNotFoundError:
                        if role in {"source", "processed-output"}:
                            raise
                        manifest["evidence_warnings"].append(f"Optional {role} artifact was unavailable during export.")
                        continue
                digest = hashlib.sha256()
                size = 0
                with stream:
                    entry = archive.open(f"artifacts/{role}/{Path(name).name}", "w", force_zip64=True) if included else nullcontext()
                    with entry as target:
                        while chunk := stream.read(1024 * 1024):
                            digest.update(chunk)
                            size += len(chunk)
                            if included:
                                target.write(chunk)
                manifest["artifacts"].append({
                    "role": role, "name": Path(name).name, "size_bytes": size,
                    "sha256": digest.hexdigest(), "included_in_capsule": included,
                })
            archive.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination, manifest
