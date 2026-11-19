import concurrent.futures
import hashlib
import http.client
import http.server
import json
import ssl
import struct
import threading
import time
import unittest
from unittest.mock import patch
from desktop.companion.gateway import (
    Gateway,
    WorkerBroker,
    APIError,
    MAX_AUDIO,
    wav_shape,
)
from desktop.companion.dsp import voice_eq


def wav(values=None, rate=48000, channels=2):
    values = values or [0.2, -0.3] * 100
    raw = struct.pack("<" + "f" * len(values), *values)
    return (
        b"RIFF"
        + struct.pack("<I", 36 + len(raw))
        + b"WAVEfmt "
        + struct.pack(
            "<IHHIIHH", 16, 3, channels, rate, rate * channels * 4, channels * 4, 32
        )
        + b"data"
        + struct.pack("<I", len(raw))
        + raw
    )


class Backend(http.server.BaseHTTPRequestHandler):
    audio = wav()
    tamper = False
    has_report = True
    mismatched_report = False
    source_sha256 = None

    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/api/health":
            self.send({"app": "AudioEnhancerMAX test", "version": "test"})
        elif self.path.startswith("/api/audio/testfile?"):
            self.send(self.audio)
        elif self.path == "/api/reports/testfile?revision=" + "a" * 32:
            self.send(
                {
                    "artifact_revision": "a" * 32,
                    "provenance": {
                        "source": {"sha256": self.source_sha256},
                        "processed_output": {
                            "sha256": "bad"
                            if self.mismatched_report
                            else self.audio_sha256()
                        },
                    },
                }
            )
        else:
            self.send_error(404)

    def audio_sha256(self):
        return hashlib.sha256(self.audio).hexdigest()

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if self.path == "/api/upload":
            upload = body.split(b"\r\n\r\n", 1)[1].rsplit(b"\r\n--", 1)[0]
            Backend.source_sha256 = hashlib.sha256(upload).hexdigest()
            self.send(
                {
                    "file_id": "testfile",
                    "duration_seconds": 1,
                    "size_bytes": len(upload),
                    "filename": "mobile.wav",
                }
            )
        elif self.path == "/api/process":
            assert json.loads(body)["preserve_channels"] is True
            self.send(
                {
                    "revision": "a" * 32,
                    "artifact_sha256": "bad" if self.tamper else self.audio_sha256(),
                    "report_url": "/api/reports/testfile" if self.has_report else None,
                    "report_summary": {"test": True},
                }
            )
        else:
            self.send_error(404)

    def send(self, value):
        data = value if isinstance(value, bytes) else json.dumps(value).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class GatewayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Backend)
        threading.Thread(target=cls.backend.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.backend.shutdown()
        cls.backend.server_close()

    def setUp(self):
        Backend.tamper = False
        Backend.has_report = True
        Backend.mismatched_report = False
        Backend.audio = wav()
        self.g = Gateway(self.backend.server_port)
        self.pair = self.g.start()

    def tearDown(self):
        self.g.close()

    def call(self, path, method="GET", body=None, auth=True, headers=None):
        conn = http.client.HTTPSConnection(
            "127.0.0.1",
            self.g.server.server_port,
            context=ssl._create_unverified_context(),
            timeout=5,
        )
        h = {"X-Device-ID": "phone-1"}
        if auth:
            h["Authorization"] = "Bearer " + self.g.token
        h.update(headers or {})
        conn.request(method, path, body, h)
        response = conn.getresponse()
        data = response.read()
        conn.close()
        return response.status, data

    def test_tls_pin_and_authentication(self):
        conn = http.client.HTTPSConnection(
            "127.0.0.1",
            self.g.server.server_port,
            context=ssl._create_unverified_context(),
        )
        conn.connect()
        self.assertEqual(
            hashlib.sha256(conn.sock.getpeercert(binary_form=True)).hexdigest(),
            self.pair["fingerprint"],
        )
        conn.close()
        self.assertEqual(self.call("/v1/status", auth=False)[0], 401)
        self.assertEqual(self.call("/v1/status")[0], 200)

    def test_bound_before_read(self):
        self.assertEqual(
            self.call(
                "/v1/files", "POST", b"", headers={"Content-Length": str(MAX_AUDIO + 1)}
            )[0],
            413,
        )
        self.assertEqual(
            self.call(
                "/v1/files", "POST", b"", headers={"Transfer-Encoding": "chunked"}
            )[0],
            400,
        )

    def test_nearby_code_requires_owner_approval_and_binds_token_to_device(self):
        from desktop.companion.pairing import comparison_code

        nonce = "12" * 32
        commitment = hashlib.sha256(nonce.encode()).hexdigest()

        def submit(action, payload, device="phone-1"):
            status, data = self.call(
                f"/v1/pairing/{action}",
                "POST",
                json.dumps(payload).encode(),
                auth=False,
                headers={"X-Device-ID": device},
            )
            return status, json.loads(data)

        status, challenge = submit("start", {"commitment": commitment})
        self.assertEqual(status, 200)
        self.assertEqual(submit("start", {"commitment": commitment})[1], challenge)
        payload = {"request_id": challenge["request_id"], "client_nonce": nonce}
        self.assertEqual(self.g.nearby_status()["requests"], [])
        self.assertEqual(submit("finish", payload)[0], 409)
        self.assertEqual(
            submit("reveal", {**payload, "client_nonce": "23" * 32})[0], 400
        )
        self.assertEqual(submit("reveal", payload)[1], {"status": "pending"})
        self.assertEqual(
            self.g.nearby_status()["requests"][0]["code"],
            comparison_code(self.pair["fingerprint"], nonce, challenge["server_nonce"]),
        )
        self.assertEqual(submit("finish", payload, device="different-phone")[0], 410)
        self.assertEqual(submit("finish", payload)[1], {"status": "pending"})
        self.assertEqual(self.call("/v1/status", auth=False)[0], 401)

        self.g.decide_pairing(challenge["request_id"], True)
        status, confirmed = submit("finish", payload)
        self.assertEqual(status, 200)
        self.assertEqual(confirmed["status"], "approved")
        self.assertEqual(confirmed["pairing"]["fingerprint"], self.pair["fingerprint"])
        self.assertNotEqual(confirmed["pairing"]["token"], self.pair["token"])
        self.assertEqual(submit("finish", payload)[1], confirmed)
        header = {"Authorization": "Bearer " + confirmed["pairing"]["token"]}
        self.assertEqual(self.call("/v1/status", auth=False, headers=header)[0], 200)
        self.assertEqual(
            self.call(
                "/v1/status",
                auth=False,
                headers={**header, "X-Device-ID": "different-phone"},
            )[0],
            401,
        )
        with patch(
            "desktop.companion.pairing.time.monotonic",
            return_value=time.monotonic() + 91,
        ):
            self.assertEqual(submit("finish", payload)[0], 410)
            self.assertEqual(
                self.call("/v1/status", auth=False, headers=header)[0], 200
            )

    def test_ownership_and_no_generic_proxy(self):
        self.assertEqual(
            self.call(
                "/v1/jobs",
                "POST",
                b'{"file_id":"private-desktop-file","profile":"voice"}',
            )[0],
            404,
        )
        self.assertEqual(self.call("/api/settings")[0], 404)
        self.assertEqual(self.call("/v1/jobs/other/audio")[0], 404)

    def test_import_job_hash_report(self):
        source = wav()
        status, data = self.call(
            "/v1/files", "POST", source, headers={"X-Audio-Extension": "wav"}
        )
        self.assertEqual(status, 200)
        source_hash = hashlib.sha256(source).hexdigest()
        self.assertEqual(json.loads(data)["sha256"], source_hash)
        self.assertEqual(self.g.transfers()[0]["status"], "imported")
        self.assertEqual(self.g.import_info("testfile")["filename"], "mobile.wav")
        self.assertEqual(
            self.call(
                "/v1/jobs",
                "POST",
                b'{"file_id":"testfile","profile":"voice"}',
                headers={"X-Device-ID": "phone-2"},
            )[0],
            404,
        )
        status, data = self.call(
            "/v1/jobs", "POST", b'{"file_id":"testfile","profile":"voice"}'
        )
        self.assertEqual(status, 200)
        key = json.loads(data)["id"]
        for _ in range(100):
            state = json.loads(self.call("/v1/jobs/" + key)[1])
            if state["status"] not in ("queued", "processing"):
                break
            time.sleep(0.01)
        self.assertEqual(state["status"], "completed")
        audio = self.call("/v1/jobs/" + key + "/audio")[1]
        report = json.loads(self.call("/v1/jobs/" + key + "/report")[1])
        self.assertEqual(
            self.call("/v1/jobs/" + key + "/audio", headers={"X-Device-ID": "phone-2"})[
                0
            ],
            404,
        )
        self.assertEqual(hashlib.sha256(audio).hexdigest(), report["sha256"])
        self.assertEqual(report["source_sha256"], source_hash)
        self.assertEqual(report["revision"], "a" * 32)
        self.assertEqual(self.g.transfers()[0]["revision"], report["revision"])
        saved_audio, audio_hash, saved_report, report_hash = self.g.owner_delivery(
            "testfile", report["revision"]
        )
        self.assertEqual(saved_audio, audio)
        self.assertEqual(audio_hash, report["sha256"])
        self.assertEqual(hashlib.sha256(saved_report).hexdigest(), report_hash)
        self.assertEqual(report_hash, report["report_sha256"])

    def test_corrupt_backend_output_is_never_published(self):
        self.call("/v1/files", "POST", wav(), headers={"X-Audio-Extension": "wav"})
        Backend.tamper = True
        self.g.jobs["job"] = {"status": "queued"}
        self.g.remote_job("job", "testfile", "voice")
        self.assertEqual(self.g.jobs["job"]["status"], "failed")
        self.assertNotIn("audio", self.g.jobs["job"])

    def test_changed_layout_is_never_published(self):
        self.call("/v1/files", "POST", wav(), headers={"X-Audio-Extension": "wav"})
        Backend.audio = wav(channels=1)
        self.g.jobs["job"] = {"status": "queued"}
        self.g.remote_job("job", "testfile", "voice")
        self.assertEqual(self.g.jobs["job"]["status"], "failed")
        self.assertNotIn("audio", self.g.jobs["job"])

    def test_missing_report_never_claims_verified_transfer(self):
        self.call("/v1/files", "POST", wav(), headers={"X-Audio-Extension": "wav"})
        Backend.has_report = False
        self.g.jobs["job"] = {"status": "queued"}
        self.g.remote_job("job", "testfile", "voice")
        self.assertEqual(self.g.jobs["job"]["status"], "failed")
        self.assertIn("report is unavailable", self.g.jobs["job"]["message"])
        self.assertNotIn("audio", self.g.jobs["job"])

    def test_mismatched_report_never_claims_verified_transfer(self):
        self.call("/v1/files", "POST", wav(), headers={"X-Audio-Extension": "wav"})
        Backend.mismatched_report = True
        self.g.jobs["job"] = {"status": "queued"}
        self.g.remote_job("job", "testfile", "voice")
        self.assertEqual(self.g.jobs["job"]["status"], "failed")
        self.assertIn("report does not match", self.g.jobs["job"]["message"])
        self.assertNotIn("audio", self.g.jobs["job"])

    def test_repeated_start_and_revocation(self):
        with self.assertRaises(APIError):
            self.g.start()
        self.g.close()
        with self.assertRaises(APIError):
            self.g.route("GET", "/v1/status", b"", {})
        with self.assertRaises(APIError):
            self.g.start()

    def test_bad_wav(self):
        for data in (b"bad", wav()[:-1], wav([float("nan"), 0]), wav() + b"x"):
            with self.assertRaises(APIError):
                wav_shape(data)


class BrokerTests(unittest.TestCase):
    def setUp(self):
        self.b = WorkerBroker()
        self.b.poll("phone-1")
        self.pool = concurrent.futures.ThreadPoolExecutor(1)

    def tearDown(self):
        self.b.close()
        self.pool.shutdown()

    def task(self):
        future = self.pool.submit(self.b.dispatch, "phone-1", wav())
        for _ in range(100):
            task = self.b.poll("phone-1")
            if task:
                return future, task
            time.sleep(0.001)
        self.fail("No worker task")

    def test_exact_stereo_shape_and_lease(self):
        future, task = self.task()
        with self.assertRaises(APIError):
            self.b.complete("other", task["id"], wav())
        with self.assertRaises(APIError):
            self.b.complete("phone-1", task["id"], wav(channels=1))
        self.b.complete("phone-1", task["id"], wav())
        self.assertEqual(future.result(1), wav())
        with self.assertRaises(APIError):
            self.b.complete("phone-1", task["id"], wav())

    def test_stop_unblocks_fallback(self):
        future, task = self.task()
        self.b.stop("phone-1")
        with self.assertRaises(APIError):
            future.result(1)
        with self.assertRaises(APIError):
            self.b.complete("phone-1", task["id"], wav())

    def test_device_bound(self):
        for i in range(2, 5):
            self.b.poll("phone-" + str(i))
        with self.assertRaises(APIError):
            self.b.poll("fifth")

    def test_eq_preserves_channels_and_length(self):
        source = [0.2, 0] * 100
        result = voice_eq(source, 48000, 2)
        self.assertEqual(len(result), len(source))
        self.assertTrue(all(x == 0 for x in result[1::2]))


if __name__ == "__main__":
    unittest.main()
