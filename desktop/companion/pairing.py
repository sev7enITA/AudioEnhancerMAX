"""Short-lived, mutually compared pairing requests for a single Mac session."""

from collections import deque
from dataclasses import dataclass
import hashlib
import hmac
import ipaddress
import re
import secrets
import time


SERVICE_TYPE = "_aemax-pair._tcp"
LOCAL_SUBNETS = tuple(
    ipaddress.IPv4Network(net)
    for net in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)
PAIRING_PATHS = frozenset(
    {"/v1/pairing/start", "/v1/pairing/reveal", "/v1/pairing/finish"}
)
HEX_32 = re.compile(r"[0-9a-f]{32}")
HEX_64 = re.compile(r"[0-9a-f]{64}")
REQUEST_TTL = 90
MAX_REQUESTS = 8
STARTS_PER_MINUTE = 12
MAX_DEVICES = 16


class PairingError(ValueError):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)


def is_local_candidate(address):
    address = ipaddress.ip_address(address)
    return any(address in network for network in LOCAL_SUBNETS)


def comparison_code(fingerprint, client_nonce, server_nonce):
    transcript = f"AEMAX-PAIR-1|{fingerprint}|{client_nonce}|{server_nonce}".encode(
        "ascii"
    )
    return f"{int(hashlib.sha256(transcript).hexdigest()[:8], 16) % 100000000:08d}"


@dataclass
class PendingRequest:
    device: str
    name: str
    commitment: str
    server_nonce: str
    expires_at: float
    code: str | None = None
    status: str = "pending"
    token: str | None = None


class PairingRequests:
    """The gateway guards all access with its session lock."""

    def __init__(self, endpoint, fingerprint):
        self.endpoint = endpoint
        self.fingerprint = fingerprint
        self.requests = {}
        self.tokens = {}
        self.starts = deque()

    def _expire(self, now):
        for key, request in tuple(self.requests.items()):
            if request.expires_at <= now:
                del self.requests[key]
        while self.starts and self.starts[0] <= now - 60:
            self.starts.popleft()

    def start(self, device, name, commitment):
        if not isinstance(commitment, str) or not HEX_64.fullmatch(commitment):
            raise PairingError(400, "Invalid pairing request")
        now = time.monotonic()
        self._expire(now)
        for key, request in self.requests.items():
            if request.device == device and hmac.compare_digest(
                request.commitment, commitment
            ):
                return {"request_id": key, "server_nonce": request.server_nonce}
        if len(self.requests) >= MAX_REQUESTS or len(self.starts) >= STARTS_PER_MINUTE:
            raise PairingError(
                429, "Too many pairing requests. Wait briefly and try again."
            )
        key = secrets.token_hex(16)
        nonce = secrets.token_hex(32)
        self.requests[key] = PendingRequest(
            device, name, commitment, nonce, now + REQUEST_TTL
        )
        self.starts.append(now)
        return {"request_id": key, "server_nonce": nonce}

    def exchange(self, device, request_id, nonce, *, reveal):
        if (
            not isinstance(request_id, str)
            or not HEX_32.fullmatch(request_id)
            or not isinstance(nonce, str)
            or not HEX_64.fullmatch(nonce)
        ):
            raise PairingError(400, "Invalid pairing confirmation")
        self._expire(time.monotonic())
        request = self.requests.get(request_id)
        if request is None or request.device != device:
            raise PairingError(410, "Pairing request expired. Select your Mac again.")
        commitment = hashlib.sha256(nonce.encode("ascii")).hexdigest()
        if not hmac.compare_digest(request.commitment, commitment):
            raise PairingError(
                400, "The pairing confirmation does not match the request"
            )
        if reveal:
            request.code = comparison_code(
                self.fingerprint, nonce, request.server_nonce
            )
            return {"status": request.status}
        if request.code is None:
            raise PairingError(409, "Compare the pairing code first")
        result = {"status": request.status}
        if request.status == "approved":
            if request.token is None:
                request.token = secrets.token_urlsafe(32)
                self.tokens[device] = request.token
            result["pairing"] = {
                "protocol": 1,
                "endpoint": self.endpoint,
                "fingerprint": self.fingerprint,
                "token": request.token,
            }
        return result

    def pending(self):
        self._expire(time.monotonic())
        return [
            {"id": key, "name": request.name, "code": request.code}
            for key, request in self.requests.items()
            if request.code is not None and request.status == "pending"
        ]

    def decide(self, request_id, approved):
        self._expire(time.monotonic())
        request = self.requests.get(request_id)
        if request is None or request.code is None or request.status != "pending":
            raise PairingError(410, "Pairing request is no longer open")
        if approved and request.device not in self.tokens:
            reserved = set(self.tokens) | {
                item.device
                for item in self.requests.values()
                if item.status == "approved"
            }
            if request.device not in reserved and len(reserved) >= MAX_DEVICES:
                raise PairingError(
                    409, "Device limit reached. Start a new companion session."
                )
        request.status = "approved" if approved else "rejected"

    def authorized(self, device, header):
        token = self.tokens.get(device)
        return token is not None and hmac.compare_digest(
            header, f"Bearer {token}".encode("ascii")
        )
