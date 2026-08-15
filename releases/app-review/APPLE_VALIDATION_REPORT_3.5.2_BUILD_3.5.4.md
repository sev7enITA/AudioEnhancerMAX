# AudioEnhancerMAX 3.5.2 (Build 3.5.4) - Validation Report

Validation date: 19 July 2026

## Release artifact

- Package: `AudioEnhancerMAX-v3.5.2-build-3.5.4-MacAppStore.pkg`
- Package size: 1,830,313,423 bytes (approximately 1.70 GiB)
- Uncompressed app size: approximately 2.5 GiB
- Package SHA-256: `14ecdce81e0bc4c10ead0789e64b01c0a784c5dfc8d5e1263cdefdd355d19314`
- Review sample SHA-256: `ffeb0404b2297182811be38c8e2f7a0a6fb19e4ba8cfb7efe32d346ce2339ff4`

## Package and code-signing result

- PASS - `pkgutil --check-signature` accepted the package and certificate chain.
- PASS - Installer identity: `3rd Party Mac Developer Installer: Fabrizio Degni (BR9VY292BU)`.
- PASS - Installer trusted timestamp: `2026-07-19 11:22:39 +0000`.
- PASS - Application identity: `3rd Party Mac Developer Application: Fabrizio Degni (BR9VY292BU)`.
- PASS - `codesign --verify --deep --strict` accepted the packaged application in a clean temporary path.
- PASS - Main executable is a native arm64 Mach-O binary.
- PASS - Marketing version is 3.5.2 and build number is 3.5.4.
- PASS - Main entitlements: App Sandbox, user-selected file read/write, network client, and network server.
- PASS - The package contains the privacy manifest and third-party notices.
- PASS - The package contains no standalone `ffmpeg` or `ffprobe` executable.

## Native application and lifecycle result

- PASS - The UI launched inside a native AppKit window using WKWebView; no external browser was opened.
- PASS - The embedded service listened only on `127.0.0.1:8000` during the tested run.
- PASS - Health reported version 3.5.2 and successful local compute availability.
- PASS - The standard macOS Open panel opened without a sandbox crash.
- PASS - The standard macOS Save panel opened for the processed WAV export.
- PASS - Closing the main window stopped the process and released TCP port 8000.

## Functional smoke test result

Test input: `AudioEnhancerMAX-review-sample.wav`, approximately 8.42 seconds, mono, 16 kHz PCM.

- PASS - Sandboxed app launched and returned a healthy status.
- PASS - WAV upload completed through the native Open panel.
- PASS - Remove Noise completed and produced processed audio ready for download.
- PASS - WAV export reached the native Save panel.
- PASS - Earlier packaged-runtime validation also decoded WAV, MP3, and FLAC exports and completed local Faster-Whisper transcription using the bundled model and VAD asset.
- PASS - Edge Cluster remained disabled until explicit user enablement.

## Validation hardware

- Physical MacBook Pro, model identifier Mac15,9
- Apple M3 Max
- 64 GB RAM
- Development validation OS: macOS 27.0 pre-release

## Manual release gate

Apple requested a continuous physical-device screen recording on the latest public operating system. The current development Mac uses a pre-release OS, so the final recording must be captured from a TestFlight/App Store-installed copy on a physical Apple silicon Mac running the latest public macOS release available on the recording date. Record the exact public OS version and build number in App Review Notes.
