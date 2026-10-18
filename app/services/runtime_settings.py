"""Persist user-controlled runtime privacy boundaries."""
from __future__ import annotations

import json
import threading
from typing import Any

from app.config import RUNTIME_SETTINGS_FILE


_LOCK = threading.RLock()
_DEFAULTS = {
    "external_services_allowed": False,
    "ollama_editorial_allowed": False,
    "trusted_lan_processing_allowed": False,
}


def runtime_settings_status() -> dict[str, Any]:
    """Read permissions once, retaining an actionable reason for safe defaults."""
    with _LOCK:
        try:
            stored = json.loads(RUNTIME_SETTINGS_FILE.read_text(encoding="utf-8"))
            if not isinstance(stored, dict) or any(type(stored.get(key)) is not bool for key in _DEFAULTS):
                raise ValueError("Privacy settings must contain all three boolean permissions")
        except FileNotFoundError:
            status = "missing"
            warning = "No saved privacy preferences. Optional services are disabled until you save your choices."
        except (ValueError, UnicodeError):
            status = "invalid"
            warning = "Saved privacy preferences could not be read. Optional services are disabled. Review and save your choices."
        except OSError:
            status = "unavailable"
            warning = "Saved privacy preferences are unavailable. Optional services are disabled. Review and save your choices."
        else:
            return {**{key: stored[key] for key in _DEFAULTS}, "status": "saved", "warning": None}
        return {**_DEFAULTS, "status": status, "warning": warning}


def load_runtime_settings() -> dict[str, bool]:
    settings = runtime_settings_status()
    return {key: settings[key] for key in _DEFAULTS}


def save_runtime_settings(settings: dict[str, Any]) -> dict[str, bool]:
    if not isinstance(settings, dict) or any(type(settings.get(key)) is not bool for key in _DEFAULTS):
        raise ValueError("Privacy settings must contain all three boolean permissions")
    normalized = {key: settings[key] for key in _DEFAULTS}
    with _LOCK:
        from app.services.artifact_store import atomic_json
        atomic_json(RUNTIME_SETTINGS_FILE, normalized)
    return normalized


def external_service_allowed(service: str) -> bool:
    settings = load_runtime_settings()
    if service == "ollama":
        return settings["ollama_editorial_allowed"]
    if service == "trusted-lan":
        return settings["trusted_lan_processing_allowed"]
    return settings["external_services_allowed"]
