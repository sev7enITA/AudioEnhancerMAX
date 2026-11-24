from types import SimpleNamespace
from unittest.mock import patch
import socket
from desktop.companion import control
from test_control import request
from fastapi import HTTPException
import pytest


def test_loopback_alias_and_vpn_never_advertised():
    def address(ip):
        return SimpleNamespace(family=socket.AF_INET, address=ip)

    entries = {
        "lo0": [address("172.30.196.206")],
        "utun8": [address("10.8.0.2")],
        "en0": [address("10.207.58.62")],
        "en4": [address("192.168.2.3")],
    }
    stats = {key: SimpleNamespace(isup=key != "en4") for key in entries}
    with (
        patch.object(control.psutil, "net_if_addrs", return_value=entries),
        patch.object(control.psutil, "net_if_stats", return_value=stats),
    ):
        assert control.network_addresses() == [
            {"interface": "en0", "address": "10.207.58.62"}
        ]


def test_network_change_revokes_session_without_owner_lock():
    closed = []
    gateway = SimpleNamespace(close=lambda: closed.append(control.current()))
    with (
        patch.object(control, "_gateway", gateway),
        patch.object(control, "host_available", return_value=False),
    ):
        assert control.revoke_if_network_changed(gateway, "10.34.4.52")
        assert control.current() is None
        assert control.session(request())["reason"] == "network_changed"
    assert closed == [None]


def test_old_monitor_cannot_revoke_new_session():
    old = SimpleNamespace(close=lambda: pytest.fail("Wrong session closed"))
    new = object()
    with (
        patch.object(control, "_gateway", new),
        patch.object(control, "host_available", return_value=False),
    ):
        assert not control.revoke_if_network_changed(old, "10.34.4.52")
        assert control.current() is new


def test_start_rejects_address_no_longer_assigned():
    with (
        patch.object(control, "network_addresses", return_value=[]),
        pytest.raises(HTTPException) as exc,
    ):
        control.start(control.StartRequest(host="10.34.4.52"), request())
    assert exc.value.status_code == 400


def test_watchdog_closes_real_tls_listener_after_address_disappears():
    import http.server
    import threading
    from test_gateway import Backend
    from desktop.companion.gateway import Gateway

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Backend)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    gateway = Gateway(server.server_port)
    try:
        gateway.start("127.0.0.1")
        port = gateway.server.server_port
        with (
            patch.object(control, "_gateway", gateway),
            patch.object(control, "host_available", return_value=False),
        ):
            monitor = threading.Thread(
                target=control.watch_network, args=(gateway, "127.0.0.1"), daemon=True
            )
            monitor.start()
            monitor.join(5)
            assert not monitor.is_alive()
            assert control.current() is None
            with pytest.raises(OSError):
                socket.create_connection(("127.0.0.1", port), timeout=1)
    finally:
        gateway.close()
        server.shutdown()
        server.server_close()
