"""Persist user-controlled runtime privacy boundaries."""
from __future__ import annotations

import json
import threading
from typing import Any

from app.config import RUNTIME_SETTINGS_FILE


_LOCK = threading.RLock()
_DEFAULTS = {
    "external_services_allowed": True,
    "ollama_editorial_allowed": True,
    "trusted_lan_processing_allowed": False,
}


def load_runtime_settings() -> dict[str, bool]:
    with _LOCK:
        try:
            stored = json.loads(RUNTIME_SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            stored = {}
        return {key: bool(stored.get(key, default)) for key, default in _DEFAULTS.items()}


def save_runtime_settings(settings: dict[str, Any]) -> dict[str, bool]:
    normalized = {
        key: bool(settings.get(key, default))
        for key, default in _DEFAULTS.items()
    }
    with _LOCK:
        RUNTIME_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary = RUNTIME_SETTINGS_FILE.with_suffix(".tmp")
        temporary.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
        temporary.replace(RUNTIME_SETTINGS_FILE)
    return normalized


def external_service_allowed(service: str) -> bool:
    settings = load_runtime_settings()
    if service == "ollama":
        return settings["ollama_editorial_allowed"]
    if service == "trusted-lan":
        return settings["trusted_lan_processing_allowed"]
    return settings["external_services_allowed"]
