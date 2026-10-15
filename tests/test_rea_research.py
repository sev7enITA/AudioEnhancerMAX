"""Evidence receipts must not turn failed or partial runs into successful research."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "rea_research", Path(__file__).resolve().parents[1] / "scripts" / "rea_research.py")
rea = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rea)


class ReaResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.artifact = self.root / "app with spaces.js"
        self.artifact.write_text("export const value = 1;\n")
        self.args = argparse.Namespace(
            artifact=self.artifact, kind="javascript", provider=None, target="adobe-podcast",
            output_root=self.root / "results", version_label="test fixture", timeout=5,
            dry_run=False)
        self.which = patch.object(rea.shutil, "which", return_value="/example/npx")
        self.which.start()
        self.addCleanup(self.which.stop)

    def fake_result(self, content, code=0, mutate=False):
        def execute(command, output, errors, timeout):
            output.write_text(content)
            errors.write_text("diagnostic")
            if mutate:
                self.artifact.write_text("changed")
            return code, False
        return execute

    def receipt(self, result):
        return json.loads(Path(result["receipt"]).read_text())

    def test_dry_run_preserves_paths_without_writing(self):
        self.args.dry_run = True
        result, code = rea.record_inspection(self.args)
        self.assertEqual(code, 0)
        self.assertIn(str(self.artifact.resolve()), result["command"])
        self.assertIn("rea-agents@6.5.0", result["command"])
        self.assertFalse(self.args.output_root.exists())

    def test_reports_cannot_change_analyzed_directory(self):
        self.args.artifact = self.root
        with self.assertRaisesRegex(ValueError, "outside the artifact"):
            rea.record_inspection(self.args)

    def test_decompile_requires_an_explicit_provider_and_procedure(self):
        self.args.kind = "decompile"
        with self.assertRaisesRegex(ValueError, "explicit --provider"):
            rea.command_for(self.args)
        self.args.provider = "ghidra"
        with self.assertRaisesRegex(ValueError, "explicit --procedure"):
            rea.command_for(self.args)
        self.args.procedure = "-symbol with spaces"
        _, command = rea.command_for(self.args)
        self.assertIn("--procedure=-symbol with spaces", command)
        self.args.kind = "native"
        with self.assertRaisesRegex(ValueError, "only to --kind decompile"):
            rea.command_for(self.args)

    def test_raw_interpretation_requires_complete_explicit_context(self):
        self.args.kind = "decompile"
        self.args.provider = "ghidra"
        self.args.procedure = "0xb0ec10"
        self.args.raw_architecture = "arm64"
        with self.assertRaisesRegex(ValueError, "--entry-point together"):
            rea.command_for(self.args)
        self.args.entry_point = "0xb0ec10"
        _, command = rea.command_for(self.args)
        self.assertIn("raw-binary", command)
        self.assertIn("arm64", command)
        self.args.provider = "hopper"
        with self.assertRaisesRegex(ValueError, "Raw analysis needs Ghidra"):
            rea.command_for(self.args)

    def test_pseudocode_strings_and_warnings_are_preserved(self):
        self.args.kind = "decompile"
        self.args.provider = "ghidra"
        self.args.procedure = "0x1000"
        for body, status in (("int f() { return 0; }", "recorded"),
                             ("/* WARNING: truncated control flow */", "recorded_partial"),
                             (None, "recorded_partial")):
            with self.subTest(body=body), patch.object(rea, "run_command", self.fake_result(
                    json.dumps({"evidence_id": "native", "normalized_result": body}))):
                result, code = rea.record_inspection(self.args)
            self.assertEqual(code, 0)
            self.assertEqual(result["status"], status)
            self.assertEqual(self.receipt(result)["decompilation"]["body_available"], bool(body))

    def test_failed_process_preserves_evidence_without_success(self):
        with patch.object(rea, "run_command", self.fake_result('{"evidence_id":"partial"}', 1)):
            result, code = rea.record_inspection(self.args)
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(json.loads(Path(result["evidence"]).read_text())["evidence_id"], "partial")
        self.assertEqual(self.receipt(result)["return_code"], 1)

    def test_bad_json_is_not_a_successful_inspection(self):
        for text in ("not json", "{}", '{"ok":false,"error":"unavailable"}',
                     '{"normalized_result":[1]}',
                     '{"normalized_result":{"graph":{"coverage":[]}}}'):
            with self.subTest(text=text), patch.object(rea, "run_command", self.fake_result(text)):
                result, code = rea.record_inspection(self.args)
            self.assertEqual(code, 1)
            self.assertEqual(result["status"], "failed")

    def test_changed_artifact_is_flagged(self):
        with patch.object(rea, "run_command", self.fake_result('{"evidence_id":"example"}', mutate=True)):
            result, code = rea.record_inspection(self.args)
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "artifact_changed")

    def test_partial_graph_remains_explicit_even_with_success_exit(self):
        evidence = {"evidence_id": "partial", "normalized_result": {
            "graph": {"coverage": {"status": "partial", "truncated": True,
                                     "families": [{"unknown_ids": ["long-id"] * 10000}]}}}}
        with patch.object(rea, "run_command", self.fake_result(json.dumps(evidence))):
            result, code = rea.record_inspection(self.args)
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "recorded_partial")
        self.assertEqual(self.receipt(result)["analysis_coverage"]["graph"]["status"], "partial")
        self.assertLess(len(json.dumps(result)), 5000)

    def test_success_retains_identity_and_private_receipt(self):
        original = self.artifact.read_bytes()
        with patch.object(rea, "run_command", self.fake_result('{"evidence_id":"example"}')):
            result, code = rea.record_inspection(self.args)
        self.assertEqual(code, 0)
        receipt = self.receipt(result)
        self.assertEqual(receipt["artifact_sha256_before"], receipt["artifact_sha256_after"])
        self.assertEqual(self.artifact.read_bytes(), original)
        self.assertEqual(receipt["evidence_sha256"], rea.digest(Path(result["evidence"])))
        self.assertEqual(Path(result["receipt"]).parent.stat().st_mode & 0o077, 0)

    @unittest.skipUnless(sys.platform != "win32", "POSIX process group cleanup")
    def test_timeout_stops_descendants(self):
        marker = self.root / "unexpected-child-output"
        child = "import time; from pathlib import Path; time.sleep(0.6); Path(" + repr(str(marker)) + ").write_text('alive')"
        parent = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c'," + repr(child) + "]); time.sleep(60)"
        code, timed_out = rea.run_command(
            [sys.executable, "-c", parent], self.root / "out", self.root / "err", 0.15)
        self.assertTrue(timed_out)
        self.assertNotEqual(code, 0)
        time.sleep(0.7)
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
