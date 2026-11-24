"""The visual credential must obey the same owner/session boundary as pairing."""

from types import SimpleNamespace
from unittest.mock import patch
import pytest
from fastapi import HTTPException
from starlette.requests import Request
from desktop.companion import control


def request(client="127.0.0.1", host=b"127.0.0.1:8002", origin=None):
    headers = [(b"host", host)]
    if origin:
        headers.append((b"origin", origin))
    return Request(
        {
            "type": "http",
            "scheme": "http",
            "server": ("127.0.0.1", 8002),
            "client": (client, 12345),
            "path": "/api/companion/qr",
            "query_string": b"",
            "headers": headers,
        }
    )


def test_qr_requires_active_session():
    with (
        patch.object(control, "current", return_value=None),
        pytest.raises(HTTPException) as exc,
    ):
        control.qr_image(request())
    assert exc.value.status_code == 409


@pytest.mark.parametrize(
    "req",
    [
        request(client="192.168.1.5"),
        request(host=b"evil.example:8002"),
        request(origin=b"https://evil.example"),
    ],
)
def test_visual_credential_and_network_list_are_owner_only(req):
    for endpoint in (control.qr_image, control.addresses):
        with pytest.raises(HTTPException) as exc:
            endpoint(req)
        assert exc.value.status_code == 403


def test_visual_credential_is_local_svg_and_never_cacheable():
    pair = {
        "protocol": 1,
        "endpoint": "https://192.168.1.2:4321",
        "fingerprint": "a" * 64,
        "token": "b" * 32,
    }
    with patch.object(control, "current", return_value=SimpleNamespace(pairing=pair)):
        response = control.qr_image(request())
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert b"<svg" in response.body and b"<path" in response.body
    assert pair["token"].encode() not in response.body
    assert b"<script" not in response.body and b"href=" not in response.body
