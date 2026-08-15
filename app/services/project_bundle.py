"""Create a portable, checksum-backed local project capsule."""
from __future__ import annotations

import hashlib
import json
import zipfile
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
    execution_boundary: str = "local",
) -> dict[str, Any]:
    artifacts = [_artifact("source", source_path), _artifact("processed-output", output_path)]
    for role, path in sorted((optional_artifacts or {}).items()):
        if Path(path).is_file():
            artifacts.append(_artifact(role, Path(path)))
    return {
        "schema_version": 1,
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


def export_project_capsule(
    *, file_id: str, app_version: str, app_build: str, source_path: Path,
    output_path: Path, optional_artifacts: dict[str, Path] | None = None,
    include_source: bool = False, execution_boundary: str = "local",
) -> tuple[Path, dict[str, Any]]:
    manifest = build_manifest(
        file_id=file_id, app_version=app_version, app_build=app_build,
        source_path=source_path, output_path=output_path, optional_artifacts=optional_artifacts,
        execution_boundary=execution_boundary,
    )
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    destination = PROJECTS_DIR / f"AudioEnhancerMAX-{file_id}-project-capsule.zip"
    temporary = destination.with_suffix(".tmp")
    included_roles = {"processed-output"}
    if include_source:
        included_roles.add("source")
    included_roles.update((optional_artifacts or {}).keys())
    for item in manifest["artifacts"]:
        item["included_in_capsule"] = item["role"] in included_roles
    paths = {"source": Path(source_path), "processed-output": Path(output_path), **(optional_artifacts or {})}

    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        for item in manifest["artifacts"]:
            role = item["role"]
            if role in included_roles and role in paths:
                safe_name = Path(item["name"]).name
                archive.write(paths[role], arcname=f"artifacts/{role}/{safe_name}")
    temporary.replace(destination)
    return destination, manifest
