"""Advertise the current Mac listener through the system Bonjour daemon."""

import ctypes as c
import select
import socket
import threading

from .pairing import SERVICE_TYPE


REGISTER_CALLBACK = c.CFUNCTYPE(
    None,
    c.c_void_p,
    c.c_uint32,
    c.c_int32,
    c.c_char_p,
    c.c_char_p,
    c.c_char_p,
    c.c_void_p,
)


def _dns_service():
    library = c.CDLL("/usr/lib/libSystem.B.dylib")
    library.DNSServiceRegister.argtypes = [
        c.POINTER(c.c_void_p),
        c.c_uint32,
        c.c_uint32,
        c.c_char_p,
        c.c_char_p,
        c.c_char_p,
        c.c_char_p,
        c.c_uint16,
        c.c_uint16,
        c.c_char_p,
        REGISTER_CALLBACK,
        c.c_void_p,
    ]
    library.DNSServiceRegister.restype = c.c_int32
    library.DNSServiceRefSockFD.argtypes = [c.c_void_p]
    library.DNSServiceRefSockFD.restype = c.c_int
    library.DNSServiceProcessResult.argtypes = [c.c_void_p]
    library.DNSServiceProcessResult.restype = c.c_int32
    library.DNSServiceRefDeallocate.argtypes = [c.c_void_p]
    library.DNSServiceRefDeallocate.restype = None
    return library


class NearbyAdvertisement:
    def __init__(self, interface, host, port, fingerprint):
        self.state = "starting"
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._serve,
            args=(interface, host, port, fingerprint),
            daemon=True,
            name="companion-bonjour",
        )
        self._thread.start()

    def _serve(self, interface, host, port, fingerprint):
        reference = c.c_void_p()
        library = None

        @REGISTER_CALLBACK
        def registered(_reference, _flags, error, _name, _regtype, _domain, _context):
            self.state = "ready" if error == 0 else "unavailable"

        try:
            library = _dns_service()
            index = socket.if_nametoindex(interface)
            machine = socket.gethostname().rstrip(".").removesuffix(".local")
            name = (
                ("AudioEnhancerMAX · " + machine).encode()[:63].decode(errors="ignore")
            )
            fields = [
                part.encode("ascii")
                for part in (
                    "v=1",
                    f"host={host}",
                    f"port={port}",
                    f"fp={fingerprint}",
                )
            ]
            txt = b"".join(bytes((len(field),)) + field for field in fields)
            error = library.DNSServiceRegister(
                c.byref(reference),
                0,
                index,
                name.encode(),
                SERVICE_TYPE.encode(),
                b"local.",
                None,
                socket.htons(port),
                len(txt),
                txt,
                registered,
                None,
            )
            if error:
                raise OSError(error, "Bonjour registration failed")
            fd = library.DNSServiceRefSockFD(reference)
            if fd < 0:
                raise OSError("Bonjour registration has no socket")
            while not self._stop.is_set() and self.state != "unavailable":
                readable, _, _ = select.select([fd], [], [], 0.25)
                if readable and library.DNSServiceProcessResult(reference):
                    raise OSError("Bonjour registration ended")
        except (OSError, AttributeError, ValueError):
            self.state = "unavailable"
        finally:
            if library is not None and reference.value:
                library.DNSServiceRefDeallocate(reference)

    def close(self):
        self._stop.set()
        self._thread.join(timeout=1)
