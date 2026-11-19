"""Discover app-specific Bonjour advertisements and send user-selected invitations."""

import ctypes as c
from dataclasses import dataclass
import ipaddress
import json
import select
import socket
import threading
import time
from urllib.parse import urlsplit

import psutil

from .discovery import _dns_service
from .pairing import HEX_32, PairingError, is_local_candidate


PHONE_SERVICE = b"_aemax-phone._udp"
ADDED = 2
IPV4 = 1
SEARCH_TTL = 90
RESOLVE_TTL = 4
MAX_QUERIES = 16
BROWSE_CB = c.CFUNCTYPE(
    None,
    c.c_void_p,
    c.c_uint32,
    c.c_uint32,
    c.c_int32,
    c.c_char_p,
    c.c_char_p,
    c.c_char_p,
    c.c_void_p,
)
RESOLVE_CB = c.CFUNCTYPE(
    None,
    c.c_void_p,
    c.c_uint32,
    c.c_uint32,
    c.c_int32,
    c.c_char_p,
    c.c_char_p,
    c.c_uint16,
    c.c_uint16,
    c.c_void_p,
    c.c_void_p,
)
ADDRESS_CB = c.CFUNCTYPE(
    None,
    c.c_void_p,
    c.c_uint32,
    c.c_uint32,
    c.c_int32,
    c.c_char_p,
    c.c_void_p,
    c.c_uint32,
    c.c_void_p,
)


def _phone_id(txt):
    attributes = {}
    offset = 0
    while offset < len(txt):
        size = txt[offset]
        offset += 1
        if not size or offset + size > len(txt):
            return None
        key, sep, value = txt[offset : offset + size].partition(b"=")
        offset += size
        if not sep or key in attributes:
            return None
        attributes[key] = value
    if attributes.get(b"v") != b"1":
        return None
    identifier = attributes.get(b"id", b"").decode("ascii", errors="replace")
    return identifier if HEX_32.fullmatch(identifier) else None


def _browser_library():
    library = _dns_service()
    pointer = c.POINTER(c.c_void_p)
    library.DNSServiceBrowse.argtypes = [
        pointer,
        c.c_uint32,
        c.c_uint32,
        c.c_char_p,
        c.c_char_p,
        BROWSE_CB,
        c.c_void_p,
    ]
    library.DNSServiceResolve.argtypes = [
        pointer,
        c.c_uint32,
        c.c_uint32,
        c.c_char_p,
        c.c_char_p,
        c.c_char_p,
        RESOLVE_CB,
        c.c_void_p,
    ]
    library.DNSServiceGetAddrInfo.argtypes = [
        pointer,
        c.c_uint32,
        c.c_uint32,
        c.c_uint32,
        c.c_char_p,
        ADDRESS_CB,
        c.c_void_p,
    ]
    for method in (
        library.DNSServiceBrowse,
        library.DNSServiceResolve,
        library.DNSServiceGetAddrInfo,
    ):
        method.restype = c.c_int32
    return library


@dataclass(frozen=True)
class Phone:
    identity: str
    name: str
    host: str
    port: int


@dataclass
class Query:
    reference: object
    callback: object
    key: tuple | None
    deadline: float


class NearbyPhones:
    def __init__(self, interface, host):
        self.state = "searching"
        self.host = host
        self._lock = threading.Lock()
        self._phones = {}
        self._sent = {}
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._serve,
            args=(interface,),
            daemon=True,
            name="companion-phone-browse",
        )
        self._thread.start()

    def _serve(self, interface):
        library = None
        queries = {}
        completed = set()
        expires = time.monotonic() + SEARCH_TTL

        def add(reference, callback, key, deadline):
            queries[reference.value] = Query(reference, callback, key, deadline)

        def remove(key):
            completed.update(ref for ref, query in queries.items() if query.key == key)
            with self._lock:
                self._phones.pop(key, None)

        def resolve_address(key, target, port, identifier):
            reference = c.c_void_p()

            @ADDRESS_CB
            def found(ref, flags, _index, error, _name, address, _ttl, _context):
                if error:
                    completed.add(ref)
                    return
                if (
                    ref in completed
                    or not flags & ADDED
                    or not address
                    or c.string_at(address, 2)[1] != socket.AF_INET
                ):
                    return
                host = socket.inet_ntoa(c.string_at(address, 8)[4:8])
                if ipaddress.ip_address(host) in network and is_local_candidate(host):
                    name = key[1].decode("utf-8", errors="replace")[:80]
                    with self._lock:
                        self._phones[key] = Phone(identifier, name, host, port)
                    completed.add(ref)

            if not library.DNSServiceGetAddrInfo(
                c.byref(reference),
                0,
                key[0],
                IPV4,
                target,
                found,
                None,
            ):
                add(reference, found, key, time.monotonic() + RESOLVE_TTL)

        def resolve_service(key):
            reference = c.c_void_p()

            @RESOLVE_CB
            def resolved(
                ref, _flags, _index, error, _full, target, port, size, txt, _ctx
            ):
                if ref in completed:
                    return
                completed.add(ref)
                if error or not target or not port or not txt or not 0 < size <= 512:
                    return
                identifier = _phone_id(c.string_at(txt, size))
                if identifier:
                    resolve_address(key, target, socket.ntohs(port), identifier)

            index, name, kind, domain = key
            if not library.DNSServiceResolve(
                c.byref(reference),
                0,
                index,
                name,
                kind,
                domain,
                resolved,
                None,
            ):
                add(reference, resolved, key, time.monotonic() + RESOLVE_TTL)

        @BROWSE_CB
        def browsed(ref, flags, index, error, name, kind, domain, _ctx):
            if error:
                self.state = "unavailable"
                completed.add(ref)
                return
            key = (index, name, kind, domain)
            if not flags & ADDED:
                remove(key)
                return
            if (
                name
                and kind
                and domain
                and len(queries) < MAX_QUERIES
                and key not in self._phones
                and len(self._phones) < MAX_QUERIES
                and not any(query.key == key for query in queries.values())
            ):
                resolve_service(key)

        try:
            mask = next(
                entry.netmask
                for entry in psutil.net_if_addrs().get(interface, ())
                if entry.family == socket.AF_INET
                and entry.address == self.host
                and entry.netmask
            )
            network = ipaddress.IPv4Network((self.host, mask), strict=False)
            library = _browser_library()
            reference = c.c_void_p()
            if library.DNSServiceBrowse(
                c.byref(reference),
                0,
                socket.if_nametoindex(interface),
                PHONE_SERVICE,
                b"local.",
                browsed,
                None,
            ):
                raise OSError("Bonjour browse failed")
            add(reference, browsed, None, expires)
            while not self._stop.is_set() and time.monotonic() < expires and queries:
                descriptors = {}
                now = time.monotonic()
                for ref, query in queries.items():
                    fd = library.DNSServiceRefSockFD(query.reference)
                    if fd < 0 or query.deadline <= now:
                        completed.add(ref)
                    else:
                        descriptors[fd] = ref
                if descriptors:
                    readable, _, _ = select.select(list(descriptors), [], [], 0.2)
                    for fd in readable:
                        ref = descriptors[fd]
                        if ref not in completed and library.DNSServiceProcessResult(
                            queries[ref].reference
                        ):
                            completed.add(ref)
                for ref in completed:
                    library.DNSServiceRefDeallocate(queries.pop(ref).reference)
                completed.clear()
            if self.state == "searching":
                self.state = "expired" if time.monotonic() >= expires else "off"
        except (OSError, ValueError, AttributeError, StopIteration):
            self.state = "unavailable"
        finally:
            if library:
                for query in queries.values():
                    library.DNSServiceRefDeallocate(query.reference)
            with self._lock:
                self._phones.clear()

    def phones(self):
        with self._lock:
            return [
                {"id": phone.identity, "name": phone.name}
                for phone in sorted(
                    self._phones.values(), key=lambda phone: phone.name.casefold()
                )
            ]

    def invite(self, identity, pairing):
        with self._lock:
            matches = [
                phone for phone in self._phones.values() if phone.identity == identity
            ]
            if self._stop.is_set() or self.state != "searching" or len(matches) != 1:
                raise PairingError(
                    410, "That phone is no longer available. Search again."
                )
            phone = matches[0]
            now = time.monotonic()
            if now - self._sent.get(identity, -10) < 2:
                raise PairingError(
                    429, "Wait briefly before sending another invitation."
                )
            target = urlsplit(pairing["endpoint"])
            name = (
                "AudioEnhancerMAX · " + socket.gethostname().removesuffix(".local")
            )[:70]
            data = json.dumps(
                {
                    "v": 1,
                    "id": identity,
                    "host": self.host,
                    "port": target.port,
                    "fp": pairing["fingerprint"],
                    "name": name,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode()
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
                    connection.bind((self.host, 0))
                    connection.sendto(data, (phone.host, phone.port))
            except OSError as exc:
                raise PairingError(
                    503, "The phone could not be contacted on this Wi-Fi."
                ) from exc
            self._sent[identity] = now

    def close(self):
        self._stop.set()
        self._thread.join(timeout=1)
