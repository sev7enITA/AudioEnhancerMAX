import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from app.services.project_bundle import build_manifest, export_project_capsule, sha256_file


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
