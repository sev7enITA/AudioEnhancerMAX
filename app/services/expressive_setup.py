"""Provision the direct-download Mac voice runtime with locked public components."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import shutil
import ssl
import subprocess
import tarfile
import tempfile
from threading import Lock, Thread
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import HTTPSHandler, HTTPRedirectHandler, ProxyHandler, Request, build_opener

import certifi

from app.services import expressive_voice as voice

_DOWNLOAD_HOSTS = {
    "github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com",
    "files.pythonhosted.org", "huggingface.co", "us.aws.cdn.hf.co", "cas-bridge.xethub.hf.co",
    "cdn-lfs.huggingface.co", "cdn-lfs-us-1.huggingface.co", "cdn-lfs-eu-1.huggingface.co",
}
# Covers the expanded runtime, installer wheels and working space during setup.
_RUNTIME_HEADROOM = 800 * 1024**2
_CHUNK = 1024**2
_guard = Lock()
_job = {"state": "idle", "detail": "", "completed": 0, "total": 0}


class SetupError(RuntimeError):
    """An installation issue that can be shown in the local app."""


def _check_url(url: str) -> None:
    target = urlsplit(url)
    if (target.scheme != "https" or target.hostname not in _DOWNLOAD_HOSTS
            or target.username or target.password or target.port not in (None, 443)):
        raise SetupError("A component source returned an unsupported download address.")


class _LockedRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _download(asset: dict):
    url = asset["url"]
    _check_url(url)
    opener = build_opener(
        ProxyHandler({}), _LockedRedirect(),
        HTTPSHandler(context=ssl.create_default_context(cafile=certifi.where())),
    )
    return opener.open(Request(url, headers={"User-Agent": "AudioEnhancerMAX voice components", "Accept": "*/*"}), timeout=30)


def _verified(path: Path, asset: dict) -> bool:
    if not voice.matches_size(path, asset):
        return False
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest() == asset["sha256"]


def _fetch(asset: dict, target: Path, source: Path | None, advance) -> None:
    if _verified(target, asset):
        advance(asset["bytes"])
        return
    origin = source / asset["path"] if source else None
    if origin and not voice.matches_size(origin, asset):
        raise SetupError(f"The offline folder is missing a valid {Path(asset['path']).name}.")
    target.parent.mkdir(parents=True, exist_ok=True)
    # A verified destination becomes visible only after the entire asset has been checked.
    digest = hashlib.sha256()
    with tempfile.NamedTemporaryFile(prefix=f".{target.name}.part-", dir=target.parent, delete=False) as output:
        temporary = Path(output.name)
        try:
            with (origin.open("rb") if origin else _download(asset)) as reader:
                remaining = asset["bytes"]
                while remaining:
                    block = reader.read(min(_CHUNK, remaining))
                    if not block:
                        raise SetupError(f"Incomplete component: {target.name}. Try setup again.")
                    output.write(block)
                    digest.update(block)
                    remaining -= len(block)
                    advance(len(block))
                if reader.read(1) or digest.hexdigest() != asset["sha256"]:
                    raise SetupError(f"Integrity check failed for {target.name}.")
            output.close()
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)


def _assets() -> list[dict]:
    lock = voice.manifest()
    return [lock["python"], *lock["wheels"], *lock["weights"]]


def prepare_offline_folder(destination: Path) -> None:
    """Fetch the exact public setup kit on a computer that can go online."""
    for asset in _assets():
        print(f"Verifying {asset['path']}", flush=True)
        _fetch(asset, destination / asset["path"], None, lambda _: None)


def _provision(source: Path | None, advance) -> None:
    import fcntl

    root = voice.voice_root()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (root / "setup.lock").open("a") as lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SetupError("Voice setup is already running in another app window.") from exc
        if voice.is_available():
            return
        lock = voice.manifest()
        downloads = root / "setup-components"
        components = [lock["python"], *lock["wheels"]]
        targets = [downloads / asset["path"] for asset in components]
        targets.extend(voice.model_asset_path(asset) for asset in lock["weights"])
        # Reclaim files owned by an earlier installer that was closed before it could clean up.
        for target in targets:
            for partial in target.parent.glob(f".{target.name}.part-*"):
                partial.unlink(missing_ok=True)
        for stage in root.glob("voice-runtime-*"):
            if stage.is_dir() and not stage.is_symlink():
                shutil.rmtree(stage)

        pending = [a for a in lock["weights"] if not voice.matches_size(voice.model_asset_path(a), a)]
        if shutil.disk_usage(root).free < _RUNTIME_HEADROOM + sum(a["bytes"] for a in pending):
            raise SetupError("Free about 4 GB for a fresh installation, then try again.")

        if source is not None and not source.is_dir():
            raise SetupError("Choose an existing offline voice pack folder.")

        for asset in components:
            _fetch(asset, downloads / asset["path"], source, advance)
        for asset in lock["weights"]:
            _fetch(asset, voice.model_asset_path(asset), source, advance)

        with tempfile.TemporaryDirectory(prefix="voice-runtime-", dir=root) as stage:
            folder = Path(stage)
            with tarfile.open(downloads / lock["python"]["path"], "r:gz") as archive:
                archive.extractall(folder, filter="data")
            python = folder / "python/bin/python3.11"
            voice.run_offline(python, [
                "-m", "pip", "install", "--isolated", "--disable-pip-version-check", "--no-index",
                "--no-deps", "--no-cache-dir", "--no-compile",
                *(str(downloads / wheel["path"]) for wheel in lock["wheels"]),
            ], timeout=180)
            voice.run_offline(python, [str(voice.WORKER), "--check"], timeout=60)
            (folder / "python").rename(root / "managed-v1")
        # Component archives are expendable after the independent runtime has passed its check.
        for asset in components:
            (downloads / asset["path"]).unlink(missing_ok=True)


def _advance(size: int) -> None:
    with _guard:
        _job["completed"] += size


def _install(source: Path | None) -> None:
    detail = ""
    try:
        _provision(source, _advance)
    except SetupError as exc:
        detail = str(exc)
    except (URLError, TimeoutError):
        detail = "Public voice components could not be downloaded. Try again or use an offline folder."
    except (OSError, subprocess.SubprocessError, tarfile.TarError):
        detail = "The local runtime could not be installed or started. Check available space and try again."
    finally:
        with _guard:
            _job.update(state="failed" if detail else "idle", detail=detail)


def status() -> dict:
    lock = voice.manifest()
    with _guard:
        result = dict(_job)
    if result["state"] != "installing":
        if voice.is_available():
            result.update(state="ready", detail="")
        elif not voice.platform_available():
            result.update(state="unsupported", detail=f"Expressive voices require Apple Silicon and macOS {lock['min_macos']} or later.")
    return {**result, "download_bytes": sum(asset["bytes"] for asset in _assets())}


def start(source: str | None) -> dict:
    if not voice.platform_available() or voice.is_available():
        return status()
    folder = Path(source).expanduser() if source else None
    if folder is not None and not folder.is_absolute():
        raise SetupError("Enter the full path to the offline voice pack folder.")
    with _guard:
        if _job["state"] != "installing":
            _job.update(state="installing", detail="", completed=0, total=sum(a["bytes"] for a in _assets()))
            Thread(target=_install, args=(folder,), name="voice-pack-setup", daemon=True).start()
    return status()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare a copyable offline voice pack on a connected machine.")
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    prepare_offline_folder(args.directory)
