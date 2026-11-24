"""The owner controls must remain responsive while gateway startup calls back."""

from concurrent.futures import ThreadPoolExecutor
import threading
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from starlette.requests import Request
from desktop.companion import control


def request():
    return Request(
        {
            "type": "http",
            "scheme": "http",
            "server": ("127.0.0.1", 8002),
            "client": ("127.0.0.1", 12345),
            "path": "/api/companion/start",
            "query_string": b"",
            "headers": [(b"host", b"127.0.0.1:8002")],
        }
    )


class ControlTests(unittest.TestCase):
    def tearDown(self):
        control.stop()

    def test_cluster_read_does_not_block_gateway_startup_callback(self):
        observed = []

        class Gateway:
            def __init__(self, port):
                pass

            def start(self, host):
                thread = threading.Thread(
                    target=lambda: observed.append(control.current()), daemon=True
                )
                thread.start()
                thread.join(1)
                if thread.is_alive():
                    raise TimeoutError("Desktop event loop blocked by owner lock")
                return {"test": True}

            def close(self):
                pass

        with patch.object(control, "Gateway", Gateway):
            result = control.start(control.StartRequest(host="127.0.0.1"), request())
        self.assertTrue(result["active"])
        self.assertEqual(observed, [None])

    def test_stop_during_start_cancels_and_closes_unpublished_gateway(self):
        entered = threading.Event()
        release = threading.Event()
        closed = threading.Event()

        class Gateway:
            def __init__(self, port):
                pass

            def start(self, host):
                entered.set()
                release.wait(3)
                return {"test": True}

            def close(self):
                closed.set()

        with patch.object(control, "Gateway", Gateway), ThreadPoolExecutor(1) as pool:
            future = pool.submit(
                control.start, control.StartRequest(host="127.0.0.1"), request()
            )
            try:
                self.assertTrue(entered.wait(1))
                with self.assertRaises(HTTPException) as conflict:
                    control.start(control.StartRequest(host="127.0.0.1"), request())
                self.assertEqual(conflict.exception.status_code, 409)
                control.stop()
            finally:
                release.set()
            with self.assertRaises(HTTPException) as cancelled:
                future.result(timeout=2)
        self.assertEqual(cancelled.exception.status_code, 409)
        self.assertTrue(closed.is_set())
        self.assertIsNone(control.current())

    def test_failed_start_releases_reservation_for_retry(self):
        class Gateway:
            def __init__(self, port):
                pass

            def start(self, host):
                raise OSError("test failure")

            def close(self):
                pass

        with patch.object(control, "Gateway", Gateway):
            for _ in range(2):
                with self.assertRaises(HTTPException) as failure:
                    control.start(control.StartRequest(host="127.0.0.1"), request())
                self.assertEqual(failure.exception.status_code, 400)
