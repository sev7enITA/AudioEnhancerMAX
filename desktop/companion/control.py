"""Loopback-only owner controls for an opt-in LAN companion session."""

import threading
import io
import ipaddress
import json
import socket
import psutil
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from .gateway import Gateway, APIError
from .pairing import PairingError, is_local_candidate


def no_cache(response: Response):
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(prefix="/api/companion", dependencies=[Depends(no_cache)])
_gateway = None
_starting = None
_revocation_reason = None
_guard = threading.RLock()


class StartRequest(BaseModel):
    host: str


class ConfirmRequest(BaseModel):
    approved: bool


class InviteRequest(BaseModel):
    id: str = Field(pattern=r"^[0-9a-f]{32}$")


def owner_only(request):
    if not request.client or request.client.host not in ("127.0.0.1", "::1"):
        raise HTTPException(403, "Companion controls are available only on this Mac")
    if request.url.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise HTTPException(403, "Use the local desktop address")
    origin = request.headers.get("origin")
    if origin and origin != f"{request.url.scheme}://{request.url.netloc}":
        raise HTTPException(403, "Unexpected origin")


def current():
    with _guard:
        return _gateway


def stop():
    global _gateway, _starting
    with _guard:
        previous = _gateway
        _gateway = None
        _starting = (
            None  # In-flight starts must not publish a session after revocation.
        )
    if previous:
        previous.close()


def suspend_workers():
    gateway = current()
    if gateway is not None:
        gateway.worker.clear()


@router.get("/session")
def session(request: Request):
    owner_only(request)
    gateway = current()
    nearby = (
        gateway.nearby_status()
        if gateway
        else {
            "discovery": "off",
            "requests": [],
            "phone_search": "off",
            "phones": [],
        }
    )
    return {
        "active": gateway is not None,
        "workers": len(gateway.worker.active()) if gateway else 0,
        "reason": _revocation_reason,
        "devices": gateway.connected_devices() if gateway else [],
        "transfers": gateway.transfers() if gateway else [],
        **nearby,
    }


@router.post("/pairing/requests/{request_id}")
def confirm_pairing(request_id: str, payload: ConfirmRequest, request: Request):
    owner_only(request)
    gateway = current()
    if gateway is None:
        raise HTTPException(410, "Pairing session has ended")
    try:
        gateway.decide_pairing(request_id, payload.approved)
    except PairingError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    return {"status": "approved" if payload.approved else "rejected"}


@router.post("/phones/search")
def search_phones(request: Request):
    owner_only(request)
    gateway = current()
    if gateway is None:
        raise HTTPException(409, "Start a companion session first")
    try:
        gateway.search_phones()
    except PairingError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    return gateway.nearby_status()


@router.post("/phones/invite")
def invite_phone(payload: InviteRequest, request: Request):
    owner_only(request)
    gateway = current()
    if gateway is None:
        raise HTTPException(410, "The companion session has ended")
    try:
        gateway.invite_phone(payload.id)
    except PairingError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    return {"status": "sent"}


@router.post("/phones/stop")
def stop_phone_search(request: Request):
    owner_only(request)
    gateway = current()
    if gateway:
        gateway.stop_phone_search()
    return {"phone_search": "off", "phones": []}


@router.get("/pairing")
def pairing_code(request: Request):
    owner_only(request)
    gateway = current()
    pairing = gateway.pairing if gateway else None
    if pairing is None:
        raise HTTPException(409, "Start a companion session first")
    return pairing


@router.get("/imports/{file_id}")
def read_import(file_id: str, request: Request):
    owner_only(request)
    gateway = current()
    if gateway is None:
        raise HTTPException(409, "Start a companion session first")
    try:
        return gateway.import_info(file_id)
    except APIError as exc:
        raise HTTPException(exc.status, exc.message) from exc


@router.get("/imports/{file_id}/{kind}")
def download_delivery(file_id: str, kind: str, revision: str, request: Request):
    owner_only(request)
    if kind not in ("audio", "report"):
        raise HTTPException(404, "Unknown companion delivery")
    gateway = current()
    if gateway is None:
        raise HTTPException(409, "The companion session has ended")
    try:
        audio, audio_hash, report, report_hash = gateway.owner_delivery(
            file_id, revision
        )
    except APIError as exc:
        raise HTTPException(exc.status, exc.message) from exc
    data, sha256, extension, content_type = (
        (audio, audio_hash, "wav", "audio/wav")
        if kind == "audio"
        else (report, report_hash, "json", "application/json")
    )
    return Response(
        data,
        media_type=content_type,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="AudioEnhancerMAX-{revision[:8]}.{extension}"',
            "X-Audio-Revision": revision,
            "X-Content-SHA256": sha256,
        },
    )


@router.get("/addresses")
def addresses(request: Request):
    owner_only(request)
    return {"addresses": network_addresses()}


def network_addresses():
    stats = psutil.net_if_stats()
    choices = []
    preferred = None
    # Resolve the system's preferred IPv4 route without sending a packet.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))
            preferred = probe.getsockname()[0]
    except OSError:
        pass
    for interface, entries in psutil.net_if_addrs().items():
        # Never advertise loopback aliases or point-to-point VPN tunnels.
        if interface.startswith(("lo", "utun", "tun", "tap", "awdl", "llw")):
            continue
        if interface not in stats or not stats[interface].isup:
            continue
        for entry in entries:
            if entry.family != socket.AF_INET:
                continue
            ip = ipaddress.ip_address(entry.address)
            if ip.is_private and not (
                ip.is_loopback
                or ip.is_link_local
                or ip.is_unspecified
                or ip.is_reserved
                or ip.is_multicast
            ):
                choices.append({"interface": interface, "address": str(ip)})
    choices.sort(
        key=lambda item: (
            item["address"] != preferred,
            not item["interface"].startswith("en"),
            item["interface"],
            item["address"],
        )
    )
    return choices


def host_available(host):
    return host == "127.0.0.1" or any(
        item["address"] == host for item in network_addresses()
    )


def revoke_if_network_changed(gateway, host):
    global _gateway, _revocation_reason
    if host_available(host):
        return False
    with _guard:
        if _gateway is not gateway:
            return False
        _gateway = None
        _revocation_reason = "network_changed"
    # Closing the listener can wait for its thread. Never hold the owner lock.
    gateway.close()
    return True


def watch_network(gateway, host):
    pause = threading.Event()
    while not pause.wait(2):
        with _guard:
            if _gateway is not gateway:
                return
        try:
            if revoke_if_network_changed(gateway, host):
                return
        except OSError:
            continue  # Retry a transient interface-query failure.


def pairing_svg(pairing):
    # Generate entirely on this Mac. No remote image service or credential URL.
    import qrcode
    from qrcode.image.svg import SvgPathFillImage

    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=4
    )
    qr.add_data(json.dumps(pairing, separators=(",", ":")))
    qr.make(fit=True)
    output = io.BytesIO()
    qr.make_image(image_factory=SvgPathFillImage).save(output)
    return output.getvalue()


@router.get("/qr")
def qr_image(request: Request):
    owner_only(request)
    gateway = current()
    pairing = gateway.pairing if gateway else None
    if pairing is None:
        raise HTTPException(409, "Start a companion session first")
    try:
        svg = pairing_svg(pairing)
    except ImportError as exc:
        raise HTTPException(
            503, "QR rendering is unavailable. Use the manual pairing code."
        ) from exc
    return Response(
        svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.post("/start")
def start(payload: StartRequest, request: Request):
    global _gateway, _starting, _revocation_reason
    owner_only(request)
    selected = next(
        (item for item in network_addresses() if item["address"] == payload.host), None
    )
    if selected is None and payload.host != "127.0.0.1":
        raise HTTPException(
            400, "Network address changed. Refresh networks and start pairing again."
        )
    reservation = object()
    with _guard:
        if _gateway or _starting:
            raise HTTPException(409, "Stop the previous session first")
        _starting = reservation
    gateway = None
    try:
        from app.services.runtime_settings import external_service_allowed

        listener = request.scope.get("server")
        gateway = Gateway(listener[1] if listener else request.url.port or 8000)
        gateway.worker_allowed = lambda: external_service_allowed("trusted-lan")
        # Startup calls back into the desktop HTTP server. Do not hold the
        # lock here: cluster polling on that event loop also calls current().
        pairing = gateway.start(payload.host)
        if selected and is_local_candidate(payload.host):
            gateway.advertise(selected["interface"], payload.host)
    except Exception as e:
        with _guard:
            if _starting is reservation:
                _starting = None
        if gateway:
            gateway.close()
        if isinstance(e, (ValueError, OSError, APIError)):
            raise HTTPException(
                400, "Cannot start companion: verify the local IP and desktop health"
            ) from e
        raise
    with _guard:
        cancelled = _starting is not reservation
        if not cancelled:
            _starting = None
            _gateway = gateway
            _revocation_reason = None
    if cancelled:
        gateway.close()
        raise HTTPException(409, "Session start was cancelled; start a new session")
    threading.Thread(
        target=watch_network,
        args=(gateway, payload.host),
        daemon=True,
        name="companion-network-watch",
    ).start()
    return {"active": True, "pairing": pairing}


@router.post("/stop")
def stop_route(request: Request):
    owner_only(request)
    stop()
    return {"active": False}
