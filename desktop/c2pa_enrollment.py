"""Create the public certificate request from the desktop app's Keychain identity."""
from __future__ import annotations

import argparse
import fcntl
from pathlib import Path
import re


def write_certificate_request(argv: list[str], support_dir: Path) -> int:
    parser = argparse.ArgumentParser(prog="AudioEnhancerMAX --c2pa-csr")
    parser.add_argument("--tag", required=True, help="Local identifier for this signing key")
    parser.add_argument("--common-name", required=True, help="Product CN agreed with the CA")
    parser.add_argument("--organization", required=True, help="Registered organization name")
    parser.add_argument("--country", required=True, help="Two-letter country code")
    parser.add_argument("--organizational-unit", help="Product OU if required by the CA")
    parser.add_argument("--output", required=True, type=Path, help="New PEM file for the public CSR")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z]{2}", args.country):
        parser.error("country must be a two-letter country code")
    if args.output.exists():
        parser.error("the output file already exists")

    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID

        from app.services.c2pa_keychain import certificate_request, signing_key

        names = [
            x509.NameAttribute(NameOID.COUNTRY_NAME, args.country.upper()),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, args.organization),
            x509.NameAttribute(NameOID.COMMON_NAME, args.common_name),
        ]
        if args.organizational_unit:
            names.append(x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, args.organizational_unit))
        directory = support_dir / "c2pa"
        directory.mkdir(mode=0o700, exist_ok=True)
        with (directory / "enrollment.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            key = signing_key(args.tag, create=True)
            request = certificate_request(key, x509.Name(names))
        with args.output.open("xb") as output:
            output.write(request)
    except (ImportError, OSError, ValueError) as exc:
        parser.exit(1, f"C2PA enrollment: {exc}\n")
    print(f"Public C2PA certificate request written to {args.output}")
    return 0
