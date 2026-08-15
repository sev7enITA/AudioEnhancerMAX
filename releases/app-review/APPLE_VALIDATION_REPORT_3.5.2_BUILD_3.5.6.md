# AudioEnhancerMAX 3.5.2 (Build 3.5.6) - Validation Report

Validation date: 14 August 2026

## Release artifact

- Package: `AudioEnhancerMAX-v3.5.2-build-3.5.6-MacAppStore.pkg`
- Package size: 1,834,258,893 bytes (approximately 1.71 GiB)
- Package SHA-256: `8999b93afbd85c5dfe060aa8e7eeb4d1fa81b9bdbbe934d1ab9fdaaea929eb06`
- Review sample SHA-256: `ffeb0404b2297182811be38c8e2f7a0a6fb19e4ba8cfb7efe32d346ce2339ff4`

## Package and identity

- PASS - Installer signature accepted by `pkgutil --check-signature` with trusted timestamp `2026-08-14 16:43:12 +0000`.
- PASS - Installer identity: `3rd Party Mac Developer Installer: Fabrizio Degni (BR9VY292BU)`.
- PASS - Application identity: `3rd Party Mac Developer Application: Fabrizio Degni (BR9VY292BU)`.
- PASS - Extracted PKG payload passed `codesign --verify --deep --strict`.
- PASS - Marketing version 3.5.2, build 3.5.6, bundle ID `com.fabriziodegni.audioenhancermax`, native arm64 executable.
- PASS - App Sandbox, user-selected file read/write, network client, and network server entitlements are present.
- PASS - Privacy manifest, third-party notices, Faster-Whisper Medium model, and Silero VAD asset are packaged.

## Native and loopback lifecycle

- PASS - The packaged process appears to macOS as `AudioEnhancerMAX`, not Python.
- PASS - The interface runs in the native AppKit/WKWebView shell without opening an external browser.
- PASS - `/api/health` reported AudioEnhancerMAX 3.5.2 from the extracted signed payload.
- PASS - The embedded server listened only on `127.0.0.1` during validation.
- PASS - Native Quit stopped the process and released the loopback port in under one second.
- PASS - Sandbox data and log paths resolve once under the application container; the prior duplicated container path was removed.

## Functional validation

- PASS - 19 automated unit tests cover deterministic tuning, capability fallback, output profiles, processing reports, runtime privacy, desktop sandbox paths, revisioned speech editing, and trusted-LAN opt-in defaults.
- PASS - Review WAV uploaded and decoded as 16 kHz mono PCM from the signed PKG payload.
- PASS - Lossless Archive profile exported FLAC; the result decoded successfully as FLAC, 16 kHz, mono.
- PASS - Processing report recorded the archive profile, FLAC format, no external service usage, and the local pipeline.
- PASS - Bundled Faster-Whisper transcription returned English text with 123 characters across two timestamped segments without a model download.
- PASS - Runtime controls expose independent permissions for external services, local Ollama editorial assistance, and trusted-LAN processing; trusted-LAN processing and discovery default to off.
- PASS - Website landing and roadmap pages render without horizontal overflow or console/request errors at tested desktop and mobile viewports.

## Remaining Apple-controlled/manual gates

- Upload build 3.5.6 with Transporter and wait for App Store Connect processing.
- Add build 3.5.6 to an internal TestFlight group and reinstall it through TestFlight on the physical Mac.
- Record Apple's requested unedited workflow on the latest public macOS release available at recording time. The current validation Mac is running macOS 27.0 build 26A5406e and must not be represented as the latest public release unless Apple has publicly released that exact build.
- Select build 3.5.6 in the macOS 3.5.2 version record, attach the video, sample, and dossier, paste the Review Notes, and reply to Guidelines 2.1 and 2.4.5.
