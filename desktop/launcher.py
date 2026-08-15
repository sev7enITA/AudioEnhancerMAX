"""macOS desktop launcher for the local AudioEnhancerMAX server."""

from __future__ import annotations

import fcntl
import json
import logging
import multiprocessing
import os
from pathlib import Path
import plistlib
import signal
import socket
import sys
import threading
import urllib.error
import urllib.request


APP_NAME = "AudioEnhancerMAX"
APP_VERSION = "3.7.0"
APP_BUILD = "3.7.2"
UI_REVISION = "20260815.v37reviewdeck1"
DEFAULT_PORT = 8000
BUNDLE_IDENTIFIER = "com.fabriziodegni.audioenhancermax"


def _distribution_channel() -> str:
    configured = os.getenv("AEMAX_DISTRIBUTION")
    if configured:
        return configured
    if getattr(sys, "frozen", False):
        info_plist = Path(sys.executable).resolve().parents[1] / "Info.plist"
        try:
            with info_plist.open("rb") as stream:
                return str(plistlib.load(stream).get("AEMAXDistribution", "direct"))
        except (OSError, ValueError, plistlib.InvalidFileException):
            pass
    return "direct"


def _support_dir(_distribution: str) -> Path:
    # App Sandbox transparently redirects the normal user Library into this
    # app's container. Adding Library/Containers manually would therefore
    # create a duplicated container path inside the real container.
    path = Path.home() / "Library" / "Application Support" / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _configure_logging(_distribution: str) -> Path:
    log_dir = Path.home() / "Library" / "Logs" / APP_NAME
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "launcher.log"
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return log_path


def _health_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/api/health"


def _frontend_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/?version={APP_VERSION}&ui={UI_REVISION}"


def _is_audioenhancermax(port: int, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(_health_url(port), timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return (
            payload.get("app") == "AudioEnhancerMAX by Fabrizio Degni"
            and payload.get("version") == APP_VERSION
        )
    except (OSError, ValueError, urllib.error.URLError):
        return False


def _port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _select_port() -> int:
    configured = int(os.getenv("AEMAX_PORT", str(DEFAULT_PORT)))
    if _port_available(configured):
        return configured
    if _is_audioenhancermax(configured):
        return configured

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _read_running_port(state_path: Path) -> int | None:
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        return int(state["port"])
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _write_state(state_path: Path, port: int) -> None:
    state_path.write_text(
        json.dumps(
            {
                "app": APP_NAME,
                "version": APP_VERSION,
                "pid": os.getpid(),
                "port": port,
                "url": _frontend_url(port),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> int:
    multiprocessing.freeze_support()
    distribution = _distribution_channel()
    os.environ.setdefault("AEMAX_DISTRIBUTION", distribution)
    if distribution == "app-store":
        os.environ.setdefault("AEMAX_APP_STORE", "1")
    support_dir = _support_dir(distribution)
    log_path = _configure_logging(distribution)
    lock_path = support_dir / "desktop.lock"
    state_path = support_dir / "server.json"

    lock_file = lock_path.open("a+")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        running_port = _read_running_port(state_path)
        if running_port and _is_audioenhancermax(running_port):
            from desktop.native_window import activate_existing_application

            activate_existing_application(BUNDLE_IDENTIFIER)
            return 0
        logging.error("Another desktop instance owns the launcher lock")
        return 1

    os.environ.setdefault("AEMAX_DATA_DIR", str(support_dir))
    os.environ.setdefault("AEMAX_DESKTOP", "1")

    port = _select_port()
    if not _port_available(port) and _is_audioenhancermax(port):
        from desktop.native_window import activate_existing_application

        activate_existing_application(BUNDLE_IDENTIFIER)
        return 0

    _write_state(state_path, port)
    logging.info("Starting %s %s on port %s; log file: %s", APP_NAME, APP_VERSION, port, log_path)

    import uvicorn
    from app.main import app as fastapi_app
    from desktop.native_window import run_native_application

    server = uvicorn.Server(
        uvicorn.Config(
            fastapi_app,
            host="127.0.0.1",
            port=port,
            log_level="info",
            access_log=False,
        )
    )

    server_thread = threading.Thread(
        target=server.run,
        name="AudioEnhancerMAX server",
        daemon=True,
    )

    def request_shutdown(signum: int, _frame: object) -> None:
        logging.info("Received signal %s; stopping local server", signum)
        server.should_exit = True
        try:
            from AppKit import NSApplication

            NSApplication.sharedApplication().terminate_(None)
        except Exception:
            logging.exception("Could not terminate the native application after signal %s", signum)

    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)

    def cleanup_state() -> None:
        try:
            current = json.loads(state_path.read_text(encoding="utf-8"))
            if current.get("pid") == os.getpid():
                state_path.unlink(missing_ok=True)
        except (OSError, ValueError, json.JSONDecodeError):
            pass

    try:
        server_thread.start()
        run_native_application(
            app_name=APP_NAME,
            app_version=APP_VERSION,
            build_number=APP_BUILD,
            distribution=distribution,
            frontend_url=_frontend_url(port),
            health_check=lambda: _is_audioenhancermax(port),
            server=server,
            server_thread=server_thread,
            shutdown_callback=cleanup_state,
        )
    finally:
        server.should_exit = True
        if server_thread.is_alive():
            server_thread.join(timeout=10.0)
        cleanup_state()
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
