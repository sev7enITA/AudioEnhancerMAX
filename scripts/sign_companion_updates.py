#!/usr/bin/env python3
"""Verify two companion artifacts and sign the mobile update feed."""
import argparse
import base64
import hashlib
import json
import plistlib
import re
import stat
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_KEY = ROOT / "app/resources/mobile/companion-update-public.pem"
ANDROID_ID = "com.audioenhancermax.worker"
IOS_ID = "com.fabriziodegni.audioenhancermax.companion"
MAX_ASSET_BYTES = 200 * 1024 * 1024


def command(*args, blob=None):
    return subprocess.run(args, input=blob, check=True, stdout=subprocess.PIPE).stdout


def check_bundled_key(archive, bundle_path):
    entries = [entry for entry in archive.infolist() if entry.filename == bundle_path]
    bundled_key = PUBLIC_KEY.read_bytes()
    if len(entries) != 1 or entries[0].file_size != len(bundled_key) or archive.read(entries[0]) != bundled_key:
        raise ValueError("Packaged companion does not contain the expected update trust key.")


def android_identity(apk, build_tools):
    verified = command(build_tools / "apksigner", "verify", "--print-certs", "--min-sdk-version", "26", apk)
    signers = re.findall(rb"^Signer #\d+ certificate SHA-256 digest: ([0-9a-fA-F]{64})$", verified, re.MULTILINE)
    if len(signers) != 1:
        raise ValueError("Expected a single verified Android signing certificate.")
    details = command(build_tools / "aapt2", "dump", "badging", apk)
    package = re.search(rb"^package: name='([^']+)' versionCode='([0-9]+)' versionName='([^']+)'", details)
    if package is None:
        raise ValueError("APK package, version and build could not be read.")
    bundle, build, version = (part.decode("ascii") for part in package.groups())
    with zipfile.ZipFile(apk) as archive:
        check_bundled_key(archive, "assets/companion-update-public.pem")
    return bundle, version, int(build), signers[0].decode("ascii").lower()


def ios_identity(archive):
    with zipfile.ZipFile(archive) as zip_file:
        entries = zip_file.infolist()
        plists = [entry for entry in entries if re.fullmatch(
            r"[^/]+\.xcarchive/Products/Applications/[^/]+\.app/Info\.plist", entry.filename
        )]
        private_files = {".mobileprovision", ".p12", ".pfx", ".key", ".pem"}
        contains_private_files = any(
            Path(entry.filename).suffix.lower() in private_files
            and Path(entry.filename).name not in {
                "C2PA-TRUST-LIST.pem", "C2PA-TSA-TRUST-LIST.pem", "companion-update-public.pem",
            }
            for entry in entries if not entry.is_dir()
        )
        if len(plists) != 1 or plists[0].file_size > 65536 or contains_private_files:
            raise ValueError("Expected one sanitized iOS developer archive.")
        plist = plistlib.loads(zip_file.read(plists[0]))
        check_bundled_key(zip_file, str(Path(plists[0].filename).with_name(PUBLIC_KEY.name)))
        return plist["CFBundleIdentifier"], plist["CFBundleShortVersionString"], int(plist["CFBundleVersion"])


def asset(path, package_id, version, build, tag):
    size = path.stat().st_size
    if not 0 < size <= MAX_ASSET_BYTES:
        raise ValueError(f"Package size is outside the update limit: {path.name}.")
    with path.open("rb") as source:
        sha = hashlib.file_digest(source, "sha256").hexdigest()
    return dict(package_id=package_id, version=version, build=build, tag=tag,
                filename=path.name, size_bytes=size, sha256=sha)


def release(args):
    if not re.fullmatch(r"[1-9][0-9]{0,3}\.(?:0|[1-9][0-9]{0,3})\.(?:0|[1-9][0-9]{0,3})", args.version):
        raise ValueError("Use a three-part numeric version.")
    if not re.fullmatch(r"v" + re.escape(args.version) + r"-mobile-beta\.[1-9][0-9]{0,2}", args.tag):
        raise ValueError("Tag must use v<version>-mobile-beta.<sequence>.")
    for build in (args.android_build, args.ios_build):
        if not 0 < build <= 2_100_000_000:
            raise ValueError("Build numbers must be positive integers.")
    if args.android.name != f"AudioEnhancerMAX-Companion-v{args.version}-build-{args.android_build}-Android-QA.apk":
        raise ValueError("Unexpected Android artifact filename.")
    if args.ios.name != f"AudioEnhancerCompanion-{args.version}-build-{args.ios_build}-unsigned-xcarchive.zip":
        raise ValueError("Unexpected iOS developer archive filename.")

    bundle, version, build, signer = android_identity(args.android, args.build_tools)
    if (bundle, version, build) != (ANDROID_ID, args.version, args.android_build):
        raise ValueError("Android package identity does not match the release.")
    if signer != args.android_signer.lower():
        raise ValueError("Android signer differs from the established direct channel.")
    if ios_identity(args.ios) != (IOS_ID, args.version, args.ios_build):
        raise ValueError("iOS archive identity does not match the release.")
    android = asset(args.android, ANDROID_ID, args.version, args.android_build, args.tag)
    ios = asset(args.ios, IOS_ID, args.version, args.ios_build, args.tag)
    return {"android": {**android, "signer_sha256": signer}, "ios": ios}


def generate(args):
    if not 1 <= args.valid_days <= 365:
        raise ValueError("The feed validity must be 1 to 365 days.")
    if args.private_key.is_symlink() or not stat.S_ISREG(args.private_key.stat().st_mode):
        raise ValueError("The update signing key must be a regular local file.")
    if args.private_key.stat().st_mode & 0o077:
        raise ValueError("Restrict the private key to its owner before signing.")
    configured = command("openssl", "pkey", "-in", args.private_key, "-pubout", "-outform", "DER")
    trusted = command("openssl", "pkey", "-pubin", "-in", PUBLIC_KEY, "-outform", "DER")
    if configured != trusted:
        raise ValueError("The signing key does not match the key bundled in the companions.")
    now = int(time.time())
    payload = json.dumps({
        "schema": "audioenhancermax.mobile-updates.v1",
        "issued_at": now,
        "expires_at": now + args.valid_days * 86400,
        "releases": release(args),
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = command("openssl", "dgst", "-sha256", "-sign", args.private_key, blob=payload)
    with tempfile.TemporaryDirectory() as temp:
        signed = Path(temp) / "signature.der"
        signed.write_bytes(signature)
        command("openssl", "dgst", "-sha256", "-verify", PUBLIC_KEY, "-signature", signed, blob=payload)
    envelope = {name: base64.b64encode(data).decode("ascii")
                for name, data in (("payload", payload), ("signature", signature))}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=args.output.parent, delete=False) as temp:
        staging = Path(temp.name)
        try:
            temp.write(json.dumps(envelope, indent=2) + "\n")
            temp.flush()
            staging.chmod(0o644)
            staging.replace(args.output)
        finally:
            staging.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("private-key", "build-tools", "android", "ios", "output"):
        parser.add_argument("--" + key, required=True, type=Path)
    for key in ("version", "tag", "android-signer"):
        parser.add_argument("--" + key, required=True)
    for key in ("android-build", "ios-build"):
        parser.add_argument("--" + key, required=True, type=int)
    parser.add_argument("--valid-days", type=int, default=90)
    args = parser.parse_args()
    try:
        generate(args)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError, zipfile.BadZipFile) as error:
        parser.exit(1, f"Could not sign the update feed: {error}\n")


if __name__ == "__main__":
    main()
