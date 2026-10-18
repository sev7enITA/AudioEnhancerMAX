import json
import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from app.services.project_bundle import build_manifest, export_project_capsule, sha256_file


def test_mutation_during_zip_creation_keeps_archived_bytes_and_hashes_consistent(tmp_path, monkeypatch):
    from app.services import project_bundle
    source = tmp_path / 'source.wav'
    output = tmp_path / 'output.wav'
    edl = tmp_path / 'edl.json'
    source.write_bytes(b'source')
    output.write_bytes(b'output')
    edl.write_text('{"revision":1}')
    original_open = zipfile.ZipFile.open
    mutated = []
    def concurrent_write(archive, name, mode='r', *args, **kwargs):
        filename = name.filename if isinstance(name, zipfile.ZipInfo) else name
        if mode == 'w' and filename.endswith('/edl.json'):
            edl.write_text('{"revision":2222}')
            mutated.append(True)
        return original_open(archive, name, mode, *args, **kwargs)
    monkeypatch.setattr(zipfile.ZipFile, 'open', concurrent_write)
    monkeypatch.setattr(project_bundle, 'PROJECTS_DIR', tmp_path / 'capsules')
    capsule, _ = export_project_capsule(file_id='test', app_version='test', app_build='test',
        source_path=source, output_path=output, optional_artifacts={'speech-edl': edl}, include_source=True)
    assert mutated == [True]
    with zipfile.ZipFile(capsule) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        for item in manifest['artifacts']:
            data = archive.read('artifacts/' + item['role'] + '/' + item['name'])
            assert hashlib.sha256(data).hexdigest() == item['sha256']
            assert len(data) == item['size_bytes']


def test_failed_capsule_does_not_leave_a_partial_zip(tmp_path, monkeypatch):
    import pytest
    from app.services import project_bundle
    source = tmp_path / 'source.wav'
    source.write_bytes(b'source')
    capsules = tmp_path / 'capsules'
    monkeypatch.setattr(project_bundle, 'PROJECTS_DIR', capsules)
    with pytest.raises(FileNotFoundError):
        export_project_capsule(file_id='test', app_version='test', app_build='test',
            source_path=source, output_path=tmp_path / 'missing.wav')
    assert list(capsules.iterdir()) == []


class ProjectBundleTests(unittest.TestCase):
    def test_manifest_contains_verifiable_sha256(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.wav"
            output = root / "output.wav"
            source.write_bytes(b"source-audio")
            output.write_bytes(b"processed-audio")

            manifest = build_manifest(
                file_id="safe-id", app_version="3.7.0", app_build="3.7.2",
                source_path=source, output_path=output,
            )

            self.assertEqual(manifest["hash_algorithm"], "SHA-256")
            self.assertEqual(manifest["artifacts"][0]["sha256"], sha256_file(source))
            self.assertEqual(manifest["artifacts"][1]["sha256"], sha256_file(output))

    def test_capsule_excludes_source_by_default_and_sanitizes_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.wav"
            output = root / "output.wav"
            report = root / "report.json"
            source.write_bytes(b"source-audio")
            output.write_bytes(b"processed-audio")
            report.write_text("{}", encoding="utf-8")

            with patch("app.services.project_bundle.PROJECTS_DIR", root / "capsules"):
                capsule, manifest = export_project_capsule(
                    file_id="safe-id", app_version="3.7.0", app_build="3.7.2",
                    source_path=source, output_path=output,
                    optional_artifacts={"processing-report": report},
                )

            with zipfile.ZipFile(capsule) as archive:
                names = archive.namelist()
                stored_manifest = json.loads(archive.read("manifest.json"))
            self.assertNotIn("artifacts/source/source.wav", names)
            self.assertIn("artifacts/processed-output/output.wav", names)
            self.assertIn("artifacts/processing-report/report.json", names)
            self.assertFalse(any(name.startswith("/") or ".." in Path(name).parts for name in names))
            source_entry = next(item for item in stored_manifest["artifacts"] if item["role"] == "source")
            self.assertFalse(source_entry["included_in_capsule"])
            self.assertEqual(manifest["app_build"], "3.7.2")


if __name__ == "__main__":
    unittest.main()
