import test_gateway as fixture
import unittest


class PresenceTests(unittest.TestCase):
    setUpClass = classmethod(fixture.GatewayTests.setUpClass.__func__)
    tearDownClass = classmethod(fixture.GatewayTests.tearDownClass.__func__)
    setUp = fixture.GatewayTests.setUp
    tearDown = fixture.GatewayTests.tearDown
    call = fixture.GatewayTests.call

    # Reuse the real TLS listener fixture, not its tests.
    def test_authenticated_presence_is_distinct_from_worker(self):
        headers = {
            "X-Device-ID": "phone-1",
            "X-Device-Name": "Android test device",
            "X-Device-Cores": "8",
        }
        assert self.call("/v1/status", headers=headers)[0] == 200
        peers = self.g.connected_devices()
        assert len(peers) == 1
        assert peers[0]["name"] == "Android test device"
        assert peers[0]["address"] == "127.0.0.1"
        assert peers[0]["cores"] == 8 and peers[0]["online"]
        assert peers[0]["mode"] == "audio_transfer"
        assert self.g.worker.active() == []
        self.call("/v1/worker/next", headers=headers)
        assert self.g.connected_devices()[0]["mode"] == "worker"
        self.call("/v1/worker/stop", "POST", b"", headers=headers)
        assert self.g.connected_devices()[0]["mode"] == "audio_transfer"

    def test_unauthenticated_request_cannot_create_presence(self):
        assert (
            self.call("/v1/status", auth=False, headers={"X-Device-ID": "intruder"})[0]
            == 401
        )
        assert self.g.connected_devices() == []

    def test_offline_timeout_retains_identity_without_claiming_online(self):
        self.call("/v1/status", headers={"X-Device-ID": "phone-1"})
        with self.g.lock:
            self.g.peers["phone-1"]["seen"] -= 21
        peer = self.g.connected_devices()[0]
        assert not peer["online"] and peer["last_seen_seconds"] >= 21
