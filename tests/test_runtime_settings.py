import tempfile
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from app import main
from app.services import runtime_settings
from app.services.runtime_settings import load_runtime_settings, save_runtime_settings, runtime_settings_status


@pytest.mark.parametrize('contents', ['{', '[]', 'null', 'true', '{}',
    '{"external_services_allowed":"false","ollama_editorial_allowed":false,"trusted_lan_processing_allowed":false}',
    '{"external_services_allowed":0,"ollama_editorial_allowed":false,"trusted_lan_processing_allowed":false}',
    b'\xff'])
def test_invalid_saved_preferences_disable_all_services_and_can_be_repaired(tmp_path, monkeypatch, contents):
    path = tmp_path / 'privacy.json'
    monkeypatch.setattr(runtime_settings, 'RUNTIME_SETTINGS_FILE', path)
    opted_out = {key: False for key in runtime_settings._DEFAULTS}
    save_runtime_settings(opted_out)
    path.write_bytes(contents if isinstance(contents, bytes) else contents.encode())
    client = TestClient(main.app)
    response = client.get('/api/settings/privacy')
    assert response.status_code == 200
    assert response.json()['status'] == 'invalid'
    assert response.json()['warning']
    assert load_runtime_settings() == opted_out
    assert all(not runtime_settings.external_service_allowed(service) for service in ('edge-tts', 'ollama', 'trusted-lan'))
    repaired = client.patch('/api/settings/privacy', json=opted_out)
    assert repaired.status_code == 200
    assert client.get('/api/settings/privacy').json()['status'] == 'saved'


def test_missing_or_unreadable_preferences_never_reenable_services(tmp_path, monkeypatch):
    path = tmp_path / 'privacy.json'
    monkeypatch.setattr(runtime_settings, 'RUNTIME_SETTINGS_FILE', path)
    assert runtime_settings_status()['status'] == 'missing'
    assert not any(load_runtime_settings().values())
    path.mkdir()  # Deterministic read error, including when tests run as root.
    assert runtime_settings_status()['status'] == 'unavailable'
    assert not any(load_runtime_settings().values())


def test_invalid_updates_preserve_previous_permissions(tmp_path, monkeypatch):
    path = tmp_path / 'privacy.json'
    monkeypatch.setattr(runtime_settings, 'RUNTIME_SETTINGS_FILE', path)
    saved = save_runtime_settings({'external_services_allowed': False, 'ollama_editorial_allowed': True,
                                   'trusted_lan_processing_allowed': False})
    client = TestClient(main.app)
    for value in ('false', 0, None):
        invalid = {**saved, 'external_services_allowed': value}
        assert client.patch('/api/settings/privacy', json=invalid).status_code == 422
        with pytest.raises(ValueError):
            save_runtime_settings(invalid)
        assert json.loads(path.read_text()) == saved


class RuntimeSettingsTests(unittest.TestCase):
    def test_trusted_lan_is_opt_in_by_default(self):
        with tempfile.TemporaryDirectory() as temporary, \
             patch("app.services.runtime_settings.RUNTIME_SETTINGS_FILE", Path(temporary) / "missing.json"):
            loaded = load_runtime_settings()

        self.assertFalse(loaded["trusted_lan_processing_allowed"])

    def test_privacy_boundaries_are_persisted_locally(self):
        with tempfile.TemporaryDirectory() as temporary, \
             patch("app.services.runtime_settings.RUNTIME_SETTINGS_FILE", Path(temporary) / "privacy.json"):
            saved = save_runtime_settings({
                "external_services_allowed": False,
                "ollama_editorial_allowed": True,
                "trusted_lan_processing_allowed": False,
            })
            loaded = load_runtime_settings()

        self.assertEqual(saved, loaded)
        self.assertFalse(loaded["external_services_allowed"])
        self.assertFalse(loaded["trusted_lan_processing_allowed"])


if __name__ == "__main__":
    unittest.main()
