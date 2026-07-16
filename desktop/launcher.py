"""macOS desktop launcher for the local AudioEnhancerMAX server."""

from __future__ import annotations

import fcntl
import json
import logging
import multiprocessing
import os
from pathlib import Path
import signal
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser


APP_NAME = "AudioEnhancerMAX"
APP_VERSION = "3.5.2"
DEFAULT_PORT = 8000


def _support_dir() -> Path:
    path = Path.home() / "Library" / "Application Support" / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _configure_logging() -> Path:
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


def _is_audioenhancermax(port: int, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(_health_url(port), timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload.get("app") == "AudioEnhancerMAX by Fd"
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


def _open_when_ready(port: int) -> None:
    url = f"http://127.0.0.1:{port}/"
    for _ in range(120):
        if _is_audioenhancermax(port):
            webbrowser.open(url, new=1, autoraise=True)
            return
        time.sleep(0.25)
    logging.error("The local server did not become healthy at %s", url)


def _write_state(state_path: Path, port: int) -> None:
    state_path.write_text(
        json.dumps(
            {
                "app": APP_NAME,
                "version": APP_VERSION,
                "pid": os.getpid(),
                "port": port,
                "url": f"http://127.0.0.1:{port}/",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> int:
    multiprocessing.freeze_support()
    support_dir = _support_dir()
    log_path = _configure_logging()
    lock_path = support_dir / "desktop.lock"
    state_path = support_dir / "server.json"

    lock_file = lock_path.open("a+")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        running_port = _read_running_port(state_path)
        if running_port and _is_audioenhancermax(running_port):
            webbrowser.open(f"http://127.0.0.1:{running_port}/", new=1, autoraise=True)
            return 0
        logging.error("Another desktop instance owns the launcher lock")
        return 1

    os.environ.setdefault("AEMAX_DATA_DIR", str(support_dir))
    os.environ.setdefault("AEMAX_DESKTOP", "1")

    port = _select_port()
    if not _port_available(port) and _is_audioenhancermax(port):
        webbrowser.open(f"http://127.0.0.1:{port}/", new=1, autoraise=True)
        return 0

    _write_state(state_path, port)
    logging.info("Starting %s %s on port %s; log file: %s", APP_NAME, APP_VERSION, port, log_path)
    threading.Thread(target=_open_when_ready, args=(port,), daemon=True).start()

    import uvicorn
    from app.main import app as fastapi_app

    server = uvicorn.Server(
        uvicorn.Config(
            fastapi_app,
            host="127.0.0.1",
            port=port,
            log_level="info",
            access_log=False,
        )
    )

    def request_shutdown(signum: int, _frame: object) -> None:
        logging.info("Received signal %s; stopping local server", signum)
        server.should_exit = True

    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)

    try:
        server.run()
    finally:
        try:
            current = json.loads(state_path.read_text(encoding="utf-8"))
            if current.get("pid") == os.getpid():
                state_path.unlink(missing_ok=True)
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
