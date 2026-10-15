#!/usr/bin/env python3
"""Run pinned REA inspections and retain local evidence outside product runtime."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "research" / "rea" / "targets.json"
PRIVATE = ROOT / "research" / "rea" / "private"
PACKAGE = "rea-agents@6.5.0"
OPERATIONS = {
    "javascript": "analyze-javascript-application",
    "macho": "inspect-macho",
    "managed": "inspect-managed-artifact",
    "plist": "inspect-plist",
    "native": "analyze",
    "decompile": "decompile",
}


def targets():
    return json.loads(REGISTRY.read_text(encoding="utf-8"))["targets"]


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def command_for(args):
    npx = shutil.which("npx")
    if not npx:
        raise ValueError("npx is unavailable; use an existing supported Node.js/npm installation.")
    artifact = args.artifact.expanduser().resolve(strict=True)
    if not artifact.is_file() and not artifact.is_dir():
        raise ValueError("Artifact must be a regular file or directory.")
    native = args.kind in ("native", "decompile")
    if native and not args.provider:
        raise ValueError("Native analysis needs an explicit --provider ghidra, hopper or ida.")
    if args.provider and not native:
        raise ValueError("--provider applies only to native analysis or decompilation.")
    procedure = getattr(args, "procedure", None)
    if args.kind == "decompile" and not procedure:
        raise ValueError("Decompilation needs an explicit --procedure name or address.")
    if procedure and args.kind != "decompile":
        raise ValueError("--procedure applies only to --kind decompile.")
    architecture = getattr(args, "raw_architecture", None)
    entry_point = getattr(args, "entry_point", None)
    if architecture or entry_point:
        if not architecture or not entry_point or not native or args.provider != "ghidra":
            raise ValueError("Raw analysis needs Ghidra, --raw-architecture and --entry-point together.")
    command = [npx, "--yes", "--ignore-scripts", PACKAGE, OPERATIONS[args.kind], str(artifact)]
    if args.kind == "javascript":
        command.extend([
            "--max-heap-mb", "1024", "--analysis-timeout-ms", "60000",
            "--max-semantic-nodes", "10000", "--max-semantic-nodes-per-file", "5000",
        ])
    if args.provider:
        command.extend(["--provider", args.provider])
    if procedure:
        command.append(f"--procedure={procedure}")
    if architecture:
        command.extend(["--target-format", "raw-binary", "--architecture", architecture,
                        "--entry-point", entry_point])
    command.append("--json")
    return artifact, command


def run_command(command, output, errors, timeout):
    """Terminate the owned process group on timeout, retaining partial output."""
    with output.open("wb") as stdout, errors.open("wb") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                   start_new_session=True)
        try:
            return process.wait(timeout=timeout), False
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGTERM)
            else:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
                process.wait()
            if isinstance(exc, KeyboardInterrupt):
                raise
            return process.returncode, True


def record_inspection(args):
    artifact, command = command_for(args)
    output_root = args.output_root.expanduser().resolve()
    # Never write reports into the analyzed tree: that changes artifact identity.
    if artifact.is_dir() and (output_root == artifact or artifact in output_root.parents):
        raise ValueError("Output directory must be outside the artifact tree.")
    if args.dry_run:
        return {"status": "planned", "target": args.target, "command": command,
                "output_root": str(output_root)}, 0
    output_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run = Path(tempfile.mkdtemp(prefix=f"{args.target}-{stamp}-", dir=output_root))
    receipt = {
        "status": "running", "target": args.target, "version_label": args.version_label,
        "started_at": datetime.now(timezone.utc).isoformat(), "rea_package": PACKAGE,
        "artifact": str(artifact), "kind": args.kind, "command": command,
        "artifact_sha256_before": digest(artifact) if artifact.is_file() else None,
        "directory_identity": "Use the subject digest in REA evidence for directories.",
        "coverage_note": "Command success does not establish complete analysis or runtime behavior.",
    }
    manifest = run / "receipt.json"
    write_json(manifest, receipt)
    evidence_path = run / "evidence.json"
    try:
        code, timed_out = run_command(command, evidence_path, run / "stderr.log", args.timeout)
        receipt.update(return_code=code, timed_out=timed_out)
        receipt["status"] = "timed_out" if timed_out else "failed"
        if code == 0 and not timed_out:
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            if not isinstance(evidence, dict) or not evidence or evidence.get("ok") is False or evidence.get("error"):
                raise ValueError("REA returned an unsuccessful or unexpected JSON response.")
            receipt.update(status="recorded", evidence_id=evidence.get("evidence_id"),
                           operation=evidence.get("operation"), subject=evidence.get("subject"))
            normalized = evidence.get("normalized_result")
            if args.kind == "decompile" and (normalized is None or isinstance(normalized, str)):
                warning = isinstance(normalized, str) and "WARNING:" in normalized
                receipt["decompilation"] = {"body_available": bool(normalized),
                                            "pseudocode_has_warnings": warning}
                if warning or not normalized:
                    receipt["status"] = "recorded_partial"
                normalized = {}
            elif normalized is None:
                normalized = {}
            if not isinstance(normalized, dict):
                raise ValueError("REA normalized_result must be an object.")
            for name in ("graph", "semantic_graph"):
                if isinstance(normalized.get(name), dict) and "coverage" in normalized[name]:
                    if not isinstance(normalized[name]["coverage"], dict):
                        raise ValueError("REA graph coverage must be an object.")
            coverage = {name: {key: value for key, value in normalized[name]["coverage"].items()
                               if key in ("status", "truncated", "omitted_count", "omitted_nodes",
                                          "omitted_relations", "limits")}
                        for name in ("graph", "semantic_graph")
                        if isinstance(normalized.get(name), dict) and "coverage" in normalized[name]}
            receipt["analysis_coverage"] = coverage
            receipt["limitations"] = evidence.get("limitations", [])
            if any(c.get("status") == "partial" or c.get("truncated") for c in coverage.values()):
                receipt["status"] = "recorded_partial"
        if artifact.is_file():
            receipt["artifact_sha256_after"] = digest(artifact)
            if receipt["artifact_sha256_before"] != receipt["artifact_sha256_after"]:
                receipt["status"] = "artifact_changed"
    except (OSError, ValueError) as exc:
        receipt.update(status="failed", error=str(exc))
    except KeyboardInterrupt:
        receipt["status"] = "interrupted"
    finally:
        receipt["finished_at"] = datetime.now(timezone.utc).isoformat()
        if evidence_path.exists():
            receipt["evidence_sha256"] = digest(evidence_path)
        write_json(manifest, receipt)
    return {"status": receipt["status"], "receipt": str(manifest),
            "evidence": str(evidence_path), "evidence_id": receipt.get("evidence_id"),
            "analysis_coverage": receipt.get("analysis_coverage")}, (
                0 if receipt["status"] in ("recorded", "recorded_partial") else 1)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("targets", help="List the source-backed competitor shortlist.")
    inspect = commands.add_parser("inspect", help="Inspect an explicitly selected local artifact.")
    inspect.add_argument("--target", required=True, choices=[t["id"] for t in targets()])
    inspect.add_argument("--artifact", type=Path, required=True)
    inspect.add_argument("--kind", required=True, choices=OPERATIONS)
    inspect.add_argument("--provider", choices=("ghidra", "hopper", "ida"))
    inspect.add_argument("--procedure", help="Selected symbol or address for decompilation.")
    inspect.add_argument("--raw-architecture", choices=("6502", "x86", "x86_64", "arm", "arm64"),
                         help="Explicit headerless interpretation; requires --entry-point and Ghidra.")
    inspect.add_argument("--entry-point", help="Load/entry address for explicitly selected raw bytes.")
    inspect.add_argument("--version-label", default="unknown")
    inspect.add_argument("--output-root", type=Path, default=PRIVATE / "runs")
    inspect.add_argument("--timeout", type=int, default=600)
    inspect.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "targets":
            result, code = {"targets": targets()}, 0
        else:
            if args.timeout < 1:
                raise ValueError("--timeout must be positive.")
            result, code = record_inspection(args)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return code
    except (OSError, ValueError) as exc:
        print(f"REA research: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
