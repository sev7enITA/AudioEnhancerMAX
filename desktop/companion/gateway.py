"""Bounded, TLS-pinned mobile API. The desktop application remains loopback-only.

A pairing credential grants access only to this gateway session's imports/jobs.
No generic URL proxy, settings mutation, file browser or desktop-data enumeration.
"""

from __future__ import annotations
import concurrent.futures
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import http.server
import ipaddress
import json
import math
import re
import secrets
import socket
import ssl
import struct
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from .pairing import PAIRING_PATHS, PairingError, PairingRequests

MAX_AUDIO = 20 * 1024 * 1024
MAX_CHUNK = 2 * 1024 * 1024
MAX_RESULT = 32 * 1024 * 1024
PROTOCOL = 1
DEVICE_ID = re.compile(r"[A-Za-z0-9-]{1,64}")
FILE_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
REVISION = re.compile(r"[a-f0-9]{32}")


class APIError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise APIError(502, "Unexpected desktop redirect")


def wav_shape(data):
    """Validate bounded mono/stereo PCM or IEEE-float WAV, including RIFF padding."""
    if len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise APIError(422, "Invalid WAV header")
    if struct.unpack_from("<I", data, 4)[0] + 8 != len(data):
        raise APIError(422, "Invalid RIFF size")
    fmt = payload = None
    pos = 12
    while pos + 8 <= len(data):
        tag, size = data[pos : pos + 4], struct.unpack_from("<I", data, pos + 4)[0]
        pos += 8
        if size > len(data) - pos:
            raise APIError(422, "Truncated WAV chunk")
        if tag == b"fmt ":
            if size < 16 or fmt is not None:
                raise APIError(422, "Invalid WAV format")
            fmt = struct.unpack_from("<HHIIHH", data, pos)
        if tag == b"data":
            if payload is not None:
                raise APIError(422, "Duplicate WAV data")
            payload = memoryview(data)[pos : pos + size]
        pos += size + (size % 2)
    if pos != len(data):
        raise APIError(422, "Invalid RIFF padding or trailing data")
    if fmt is None or payload is None:
        raise APIError(422, "Missing WAV chunks")
    kind, channels, rate, byte_rate, align, bits = fmt
    if (
        (kind, bits) not in ((1, 16), (1, 24), (1, 32), (3, 32))
        or channels not in (1, 2)
        or not 8000 <= rate <= 96000
    ):
        raise APIError(422, "Use PCM16/24/32 or float32 WAV, mono/stereo, 8–96 kHz")
    if (
        align != channels * bits // 8
        or byte_rate != rate * align
        or len(payload) % align
        or not payload
    ):
        raise APIError(422, "Invalid sample layout")
    if kind == 3 and any(
        not math.isfinite(v[0]) for v in struct.iter_unpack("<f", payload)
    ):
        raise APIError(422, "Non-finite samples")
    return rate, channels, len(payload) // align


def session_certificate(directory: Path, address: ipaddress.IPv4Address):
    """Generate the ephemeral identity pinned by the mobile pairing code."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name(
        [x509.NameAttribute(x509.NameOID.COMMON_NAME, "AudioEnhancerMAX Companion")]
    )
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=7))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(address)]), critical=False
        )
        .sign(private_key, hashes.SHA256())
    )
    cert, key = directory / "cert.pem", directory / "key.pem"
    cert.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    key.chmod(0o600)
    return cert, key, certificate.fingerprint(hashes.SHA256()).hex()


def device_name(headers):
    name = headers.get("X-Device-Name", "")
    return (
        "".join(char for char in name if char.isascii() and char.isprintable()).strip()[
            :80
        ]
        or "Mobile companion"
    )


class WorkerBroker:
    def __init__(self):
        self.lock = threading.RLock()
        self.devices = {}
        self.tasks = {}
        self.completed = {}
        self.closed = False

    def poll(self, device):
        if not isinstance(device, str) or not DEVICE_ID.fullmatch(device):
            raise APIError(400, "Invalid device identity")
        with self.lock:
            if self.closed:
                raise APIError(503, "Session closed")
            now = time.monotonic()
            self.devices = {k: v for k, v in self.devices.items() if now - v < 10}
            if device not in self.devices and len(self.devices) >= 4:
                raise APIError(429, "Four workers maximum")
            self.completed = {
                k: v for k, v in self.completed.items() if k in self.devices
            }
            self.completed.setdefault(device, 0)
            self.devices[device] = now
            for task_id, task in self.tasks.items():
                if (
                    task["device"] == device
                    and not task["claimed"]
                    and not task["event"].is_set()
                ):
                    task["claimed"] = True
                    return {"id": task_id, "filter": "auto_eq", "audio": task["audio"]}
            return None

    def stop(self, device):
        with self.lock:
            self.devices.pop(device, None)
            for task in self.tasks.values():
                if task["device"] == device:
                    task["event"].set()

    def active(self):
        with self.lock:
            now = time.monotonic()
            return [d for d, t in self.devices.items() if now - t < 8]

    def describe(self, device):
        with self.lock:
            busy = any(
                t["device"] == device and t["claimed"] and not t["event"].is_set()
                for t in self.tasks.values()
            )
            return {
                "status": "busy" if busy else "online",
                "tasks_completed": self.completed.get(device, 0),
            }

    def dispatch(self, device, audio):
        if len(audio) > MAX_CHUNK:
            raise APIError(413, "Chunk exceeds mobile memory budget")
        shape = wav_shape(audio)
        with self.lock:
            if self.closed or device not in self.active():
                raise APIError(503, "Worker unavailable")
            if any(t["device"] == device for t in self.tasks.values()):
                raise APIError(409, "Worker busy")
            key = uuid.uuid4().hex
            task = {
                "device": device,
                "audio": audio,
                "shape": shape,
                "event": threading.Event(),
                "claimed": False,
                "result": None,
            }
            self.tasks[key] = task
        try:
            if not task["event"].wait(25) or task["result"] is None:
                raise APIError(504, "Worker interrupted; desktop fallback required")
            return task["result"]
        finally:
            with self.lock:
                self.tasks.pop(key, None)

    def complete(self, device, key, audio):
        if len(audio) > MAX_CHUNK:
            raise APIError(413, "Result too large")
        shape = wav_shape(audio)
        with self.lock:
            task = self.tasks.get(key)
            if (
                not task
                or task["device"] != device
                or not task["claimed"]
                or task["event"].is_set()
            ):
                raise APIError(409, "Worker lease expired")
            if shape != task["shape"]:
                raise APIError(422, "Worker changed duration, rate or channels")
            self.completed[device] = self.completed.get(device, 0) + 1
            task["result"] = audio
            task["event"].set()

    def close(self):
        with self.lock:
            self.closed = True
            self.clear()

    def clear(self):
        with self.lock:
            self.devices.clear()
            self.completed.clear()
            for task in self.tasks.values():
                task["event"].set()


class Gateway:
    def __init__(self, backend_port, token=None):
        if not isinstance(backend_port, int) or not 1 <= backend_port <= 65535:
            raise ValueError("Invalid backend port")
        self.backend = f"http://127.0.0.1:{backend_port}"
        self.token = token or secrets.token_urlsafe(32)
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirect()
        )
        self.lock = threading.RLock()
        self.files = {}
        self.peers = {}
        self.jobs = {}
        self.total_bytes = 0
        self.uploading = None
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.worker = WorkerBroker()
        self.worker_allowed = lambda: True
        self.server = None
        self.temp = None
        self.pairing = None
        self.nearby = None
        self.advertisement = None
        self.closed = False

    def advertise(self, interface, host):
        from .discovery import NearbyAdvertisement

        with self.lock:
            if not self.closed and self.pairing and self.server:
                self.advertisement = NearbyAdvertisement(
                    interface,
                    host,
                    self.server.server_port,
                    self.pairing["fingerprint"],
                )

    def nearby_status(self):
        with self.lock:
            return {
                "discovery": self.advertisement.state
                if self.advertisement
                else "unavailable",
                "requests": self.nearby.pending() if self.nearby else [],
            }

    def decide_pairing(self, request_id, approved):
        with self.lock:
            if self.nearby is None:
                raise PairingError(410, "Pairing session has ended")
            self.nearby.decide(request_id, approved)

    def pairing_request(self, path, body, headers):
        device = headers.get("X-Device-ID", "")
        if not DEVICE_ID.fullmatch(device):
            raise PairingError(400, "Invalid device identity")
        value = json.loads(body)
        if not isinstance(value, dict):
            raise PairingError(400, "Invalid pairing request")
        with self.lock:
            if self.nearby is None:
                raise PairingError(410, "Pairing session has ended")
            if path == "/v1/pairing/start":
                return self.nearby.start(
                    device,
                    device_name(headers) or "Mobile companion",
                    value.get("commitment"),
                )
            return self.nearby.exchange(
                device,
                value.get("request_id"),
                value.get("client_nonce"),
                reveal=path == "/v1/pairing/reveal",
            )

    def observe_peer(self, headers, address):
        device = headers.get("X-Device-ID", "")
        if not DEVICE_ID.fullmatch(device):
            return
        name = device_name(headers)
        try:
            cores = max(0, min(256, int(headers.get("X-Device-Cores", "0"))))
        except ValueError:
            cores = 0
        from .assessment import parse_assessment

        assessment = parse_assessment(headers.get("X-Device-Assessment", ""))
        with self.lock:
            if self.closed:
                return
            if device not in self.peers and len(self.peers) >= 16:
                oldest = min(self.peers, key=lambda d: self.peers[d]["seen"])
                del self.peers[oldest]
            self.peers[device] = {
                "id": device,
                "name": name or "Mobile companion",
                "address": address,
                "cores": cores,
                "assessment": assessment,
                "seen": time.monotonic(),
            }

    def connected_devices(self):
        workers = set(self.worker.active())
        with self.lock:
            now = time.monotonic()
            return [
                dict(
                    id=p["id"],
                    name=p["name"],
                    address=p["address"],
                    cores=p["cores"],
                    assessment=p.get("assessment", {}),
                    online=now - p["seen"] < 20,
                    last_seen_seconds=int(now - p["seen"]),
                    mode="worker" if p["id"] in workers else "audio_transfer",
                    tasks_completed=self.worker.describe(p["id"])["tasks_completed"],
                )
                for p in self.peers.values()
            ]

    def transfers(self):
        """Owner-only handoff state. Return no credentials or media bytes."""
        with self.lock:
            incoming = [dict(self.uploading)] if self.uploading else []
            for file_id, source in reversed(tuple(self.files.items())):
                job = next(
                    (
                        item
                        for item in reversed(tuple(self.jobs.values()))
                        if item["file_id"] == file_id
                    ),
                    None,
                )
                incoming.append(
                    {
                        "id": file_id,
                        "device": source["device_name"],
                        "status": job["status"] if job else "imported",
                        "size_bytes": source["info"]["size_bytes"],
                        "filename": source["info"]["filename"],
                        "source_sha256": source["sha256"],
                        "revision": job.get("revision") if job else None,
                        "sha256": job.get("sha256") if job else None,
                        "report_sha256": job.get("report_sha256") if job else None,
                        "message": job.get("message") if job else None,
                    }
                )
            return incoming

    def import_info(self, file_id):
        with self.lock:
            source = self.files.get(file_id) if not self.closed else None
            if source is None:
                raise APIError(404, "Import not found in this session")
            return dict(source["info"])

    def owner_delivery(self, file_id, revision):
        with self.lock:
            if self.closed:
                raise APIError(409, "The companion session has ended")
            for job in self.jobs.values():
                if (
                    job["file_id"] == file_id
                    and job.get("revision") == revision
                    and job["status"] == "completed"
                ):
                    return (
                        job["audio"],
                        job["sha256"],
                        job["report_bytes"],
                        job["report_sha256"],
                    )
        raise APIError(404, "No verified transfer for that revision")

    def upstream(self, path, body=None, headers=None, limit=MAX_RESULT):
        req = urllib.request.Request(
            self.backend + path, data=body, headers=headers or {}
        )
        try:
            with self.opener.open(req, timeout=180) as response:
                data = response.read(limit + 1)
                if len(data) > limit:
                    raise APIError(502, "Desktop response too large")
                return data
        except urllib.error.HTTPError as e:
            # Do not relay private paths, model logs or exception details.
            raise APIError(502, f"Desktop returned HTTP {e.code}; check the Mac") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise APIError(
                503, "Mac is unavailable; open AudioEnhancerMAX and reconnect"
            ) from e

    def remote_job(self, key, file_id, profile):
        with self.lock:
            if self.closed:
                return
            self.jobs[key]["status"] = "processing"
            source = self.files[file_id]
        try:
            options = {
                "auto_eq": profile == "voice",
                "normalize": True,
                "output_format": "wav",
            }
            raw = self.upstream(
                "/api/process",
                json.dumps(
                    {"file_id": file_id, "options": options, "preserve_channels": True}
                ).encode(),
                {"Content-Type": "application/json"},
                1024 * 1024,
            )
            result = json.loads(raw)
            revision = result.get("revision")
            if not isinstance(revision, str) or not REVISION.fullmatch(revision):
                raise APIError(502, "Missing output revision")
            # Download while the result is current, bind to the exact revision/hash.
            query = urllib.parse.urlencode(
                {"version": "processed", "revision": revision}
            )
            audio = self.upstream(f"/api/audio/{file_id}?{query}")
            digest = hashlib.sha256(audio).hexdigest()
            if digest != result.get("artifact_sha256"):
                raise APIError(502, "Output integrity check failed")
            output_shape = wav_shape(audio)
            if source["shape"] != output_shape:
                raise APIError(
                    502, "Mac result changed the audio length, sample rate or channels"
                )
            sample_rate, channels, frames = output_shape
            if not result.get("report_url"):
                raise APIError(
                    502,
                    "Mac processing report is unavailable. Retry the job from the companion.",
                )
            report_bytes = self.upstream(
                f"/api/reports/{file_id}?revision={revision}", limit=1024 * 1024
            )
            report = json.loads(report_bytes)
            provenance = report.get("provenance", {})
            if (
                report.get("artifact_revision") != revision
                or provenance.get("source", {}).get("sha256") != source["sha256"]
                or provenance.get("processed_output", {}).get("sha256") != digest
            ):
                raise APIError(502, "Mac processing report does not match the handoff")
            report_hash = hashlib.sha256(report_bytes).hexdigest()
            with self.lock:
                if self.closed:
                    return
                self.jobs[key].update(
                    status="completed",
                    audio=audio,
                    sha256=digest,
                    revision=revision,
                    report=result.get("report_summary"),
                    duration=frames / sample_rate,
                    sample_rate=sample_rate,
                    channels=channels,
                    report_bytes=report_bytes,
                    report_sha256=report_hash,
                )
        except Exception as e:
            with self.lock:
                if not self.closed:
                    self.jobs[key].update(
                        status="failed",
                        message=e.message
                        if isinstance(e, APIError)
                        else "Processing failed; inspect the Mac",
                    )

    def route(self, method, path, body, headers):
        if self.closed:
            raise APIError(503, "Session closed")
        if method == "GET" and path == "/v1/status":
            health = json.loads(self.upstream("/api/health", limit=65536))
            return {
                "protocol": PROTOCOL,
                "version": health.get("version", "unknown"),
                "status": "connected",
                "max_upload_bytes": MAX_AUDIO,
                "mac_name": socket.gethostname(),
                "build": health.get("build", "unknown"),
                "worker_filter": "Voice EQ",
                "performance": "not measured",
                "profiles": ["voice", "level"],
                "revision_receipts": True,
            }
        device = headers.get("X-Device-ID", "")
        if not DEVICE_ID.fullmatch(device):
            raise APIError(400, "Missing or invalid companion device identity")
        if method == "POST" and path == "/v1/files":
            ext = headers.get("X-Audio-Extension", "").lower()
            if ext != "wav":
                raise APIError(
                    415, "Prepare a WAV copy in the companion app before sending"
                )
            if not body:
                raise APIError(400, "Empty audio")
            source_shape = wav_shape(body)
            source_hash = hashlib.sha256(body).hexdigest()
            with self.lock:
                if self.closed:
                    raise APIError(503, "Session closed")
                if self.uploading:
                    raise APIError(409, "Another import is in progress")
                if (
                    len(self.files) >= 12
                    or self.total_bytes + len(body) > 80 * 1024 * 1024
                ):
                    raise APIError(
                        429, "Session import limit reached; start a new Mac session"
                    )
                self.uploading = {
                    "device": device_name(headers),
                    "status": "importing",
                    "size_bytes": len(body),
                }
            try:
                boundary = secrets.token_hex(24)
                data = (
                    f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="mobile.{ext}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()
                    + body
                    + f"\r\n--{boundary}--\r\n".encode()
                )
                result = json.loads(
                    self.upstream(
                        "/api/upload",
                        data,
                        {"Content-Type": f"multipart/form-data; boundary={boundary}"},
                        1024 * 1024,
                    )
                )
                identifier = result.get("file_id", "")
                if not isinstance(identifier, str) or not FILE_ID.fullmatch(identifier):
                    raise APIError(502, "Invalid desktop import response")
                if result.get("size_bytes") != len(body):
                    raise APIError(502, "Desktop import size does not match the source")
                with self.lock:
                    if self.closed:
                        raise APIError(503, "Session closed")
                    self.files[identifier] = {
                        "info": result,
                        "device": device,
                        "device_name": device_name(headers),
                        "sha256": source_hash,
                        "shape": source_shape,
                    }
                    self.total_bytes += len(body)
                return {
                    "id": identifier,
                    "duration": result.get("duration_seconds"),
                    "sha256": source_hash,
                }
            finally:
                with self.lock:
                    self.uploading = None
        if method == "POST" and path == "/v1/jobs":
            data = json.loads(body)
            if not isinstance(data, dict) or not isinstance(data.get("file_id"), str):
                raise APIError(400, "Invalid job request")
            file_id, profile = data.get("file_id"), data.get("profile")
            if profile not in ("voice", "level"):
                raise APIError(400, "Unknown profile")
            with self.lock:
                if self.closed:
                    raise APIError(503, "Session closed")
                source = self.files.get(file_id)
                if source is None or source["device"] != device:
                    raise APIError(404, "Import not found for this device")
                if any(
                    j["status"] in ("queued", "processing") for j in self.jobs.values()
                ):
                    raise APIError(409, "Mac job already running")
                if len(self.jobs) >= 4:
                    raise APIError(
                        429, "Session result limit reached; start a new Mac session"
                    )
                key = uuid.uuid4().hex
                self.jobs[key] = {
                    "id": key,
                    "status": "queued",
                    "file_id": file_id,
                    "device": device,
                    "source_sha256": source["sha256"],
                }
                self.pool.submit(self.remote_job, key, file_id, profile)
                return {"id": key, "status": "queued"}
        parts = path.split("/")
        if method == "GET" and len(parts) in (4, 5) and parts[1:3] == ["v1", "jobs"]:
            with self.lock:
                job = self.jobs.get(parts[3])
                if job is None or job["device"] != device:
                    raise APIError(404, "Job not found")
                if len(parts) == 4:
                    return {
                        k: v
                        for k, v in job.items()
                        if k
                        not in ("audio", "report", "report_bytes", "file_id", "device")
                    }
                if job["status"] != "completed":
                    raise APIError(409, "Result not ready")
                if parts[4] == "audio":
                    return job["audio"]
                if parts[4] == "report":
                    return {
                        "revision": job["revision"],
                        "sha256": job["sha256"],
                        "source_sha256": job["source_sha256"],
                        "report_sha256": job["report_sha256"],
                        "summary": job["report"],
                    }
        if method == "GET" and path == "/v1/worker/next":
            if not self.worker_allowed():
                raise APIError(
                    403,
                    "Allow trusted local network processing in Mac Preferences to contribute Voice EQ",
                )
            task = self.worker.poll(device)
            if task is None:
                return {"status": "waiting"}
            return (
                task["audio"],
                {"X-Task-ID": task["id"], "X-Filter": task["filter"]},
            )
        if method == "POST" and path == "/v1/worker/stop":
            self.worker.stop(device)
            return {"status": "stopped"}
        if (
            method == "POST"
            and len(parts) == 5
            and parts[1:4] == ["v1", "worker", "result"]
        ):
            if not self.worker_allowed():
                raise APIError(
                    403, "Trusted local network processing was disabled on this Mac"
                )
            self.worker.complete(device, parts[4], body)
            return {"status": "accepted"}
        raise APIError(404, "Unknown companion endpoint")

    def start(self, host="127.0.0.1", port=0):
        if self.closed or self.server is not None:
            raise APIError(409, "Start a fresh gateway session")
        address = ipaddress.ip_address(host)
        if (
            address.version != 4
            or not (address.is_private or address.is_loopback)
            or address.is_unspecified
        ):
            raise ValueError("Select a specific local IPv4 address")
        health = json.loads(self.upstream("/api/health", limit=65536))
        if "AudioEnhancerMAX" not in str(health.get("app", "")):
            raise APIError(502, "This is not an AudioEnhancerMAX backend")
        self.temp = tempfile.TemporaryDirectory(prefix="aemax-companion-")
        cert, key, fingerprint = session_certificate(Path(self.temp.name), address)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(cert, key)
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass  # Never log credentials or audio identifiers.

            def do_GET(self):
                self.safe_handle()

            def do_POST(self):
                self.safe_handle()

            def safe_handle(self):
                try:
                    self.handle_api()
                except (BrokenPipeError, ConnectionResetError, TimeoutError):
                    pass

            def handle_api(self):
                try:
                    self.connection.settimeout(15)
                    nearby = self.command == "POST" and self.path in PAIRING_PATHS
                    if not nearby:
                        header = self.headers.get("Authorization", "").encode("latin-1")
                        device = self.headers.get("X-Device-ID", "")
                        with owner.lock:
                            authorized = not owner.closed and (
                                hmac.compare_digest(
                                    header, f"Bearer {owner.token}".encode("ascii")
                                )
                                or owner.nearby
                                and owner.nearby.authorized(device, header)
                            )
                        if not authorized:
                            raise APIError(401, "Pair this device from the Mac")
                    if self.headers.get("Transfer-Encoding"):
                        raise APIError(400, "Chunked uploads are not supported")
                    if len(self.headers.get_all("Content-Length", [])) > 1:
                        raise APIError(400, "Ambiguous content length")
                    try:
                        length = int(self.headers.get("Content-Length", "0"))
                    except ValueError:
                        raise APIError(400, "Invalid content length")
                    limit = (
                        1024
                        if nearby
                        else MAX_AUDIO
                        if self.path == "/v1/files"
                        else MAX_CHUNK
                        if self.path.startswith("/v1/worker/result/")
                        else 8192
                    )
                    if not 0 <= length <= limit:
                        raise APIError(413, "Request too large")
                    body = self.rfile.read(length)
                    if len(body) != length:
                        raise APIError(400, "Incomplete upload")
                    if nearby:
                        result = owner.pairing_request(self.path, body, self.headers)
                    else:
                        result = owner.route(
                            self.command, self.path, body, self.headers
                        )
                        owner.observe_peer(self.headers, self.client_address[0])
                    extra = {}
                    if isinstance(result, tuple):
                        result, extra = result
                    binary = isinstance(result, bytes)
                    payload = result if binary else json.dumps(result).encode()
                    self.send_response(200)
                    self.send_header(
                        "Content-Type", "audio/wav" if binary else "application/json"
                    )
                    for k, v in extra.items():
                        self.send_header(k, v)
                except Exception as e:
                    status = (
                        e.status
                        if isinstance(e, (APIError, PairingError))
                        else 400
                        if isinstance(e, (ValueError, TypeError))
                        else 500
                    )
                    payload = json.dumps(
                        {
                            "error": str(e)
                            if isinstance(e, (APIError, PairingError))
                            else "Invalid request"
                            if status == 400
                            else "Gateway error"
                        }
                    ).encode()
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(payload)

        class Server(http.server.ThreadingHTTPServer):
            daemon_threads = True

            def __init__(self, *a):
                self.slots = threading.BoundedSemaphore(8)
                super().__init__(*a)

            def process_request(self, request, address):
                if not self.slots.acquire(blocking=False):
                    self.shutdown_request(request)
                    return
                try:
                    super().process_request(request, address)
                except Exception:
                    self.slots.release()
                    raise

            def process_request_thread(self, request, address):
                try:
                    request.settimeout(5)
                    try:
                        connection = context.wrap_socket(request, server_side=True)
                    except OSError:
                        request.close()
                        return
                    super().process_request_thread(connection, address)
                finally:
                    self.slots.release()

        self.server = Server((host, port), Handler)
        self.pairing = {
            "protocol": PROTOCOL,
            "endpoint": f"https://{host}:{self.server.server_port}",
            "fingerprint": fingerprint,
            "token": self.token,
        }
        self.nearby = PairingRequests(self.pairing["endpoint"], fingerprint)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self.pairing

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
            self.token = ""
            self.pairing = None
            self.nearby = None
            advertisement, self.advertisement = self.advertisement, None
            self.files.clear()
            self.jobs.clear()
            self.peers.clear()
            self.uploading = None
        if advertisement:
            advertisement.close()
        self.worker.close()
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        self.pool.shutdown(wait=False, cancel_futures=True)
        if self.temp:
            self.temp.cleanup()
