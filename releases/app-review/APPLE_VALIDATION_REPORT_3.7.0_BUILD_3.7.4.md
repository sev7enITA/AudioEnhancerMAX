# AudioEnhancerMAX 3.7.0 (Build 3.7.4) - Validation Report

Validation date: 20 August 2026

## Release artifact

- Package: `AudioEnhancerMAX-v3.7.0-build-3.7.4-MacAppStore.pkg`
- Package size: 1,834,894,239 bytes (approximately 1.71 GiB)
- Package SHA-256: `b25985c42d54ca7aab92f269b8523404527fd9a32fc3e4667270627b071e8370`
- Review sample SHA-256: `ffeb0404b2297182811be38c8e2f7a0a6fb19e4ba8cfb7efe32d346ce2339ff4`

## Package and identity

- PASS - Installer signature accepted by `pkgutil --check-signature` with trusted timestamp `2026-08-20 20:02:41 +0000`.
- PASS - Installer identity: `3rd Party Mac Developer Installer: Fabrizio Degni (BR9VY292BU)`.
- PASS - Application identity: `3rd Party Mac Developer Application: Fabrizio Degni (BR9VY292BU)`.
- PASS - Extracted PKG payload passed `codesign --verify --deep --strict`.
- PASS - Marketing version 3.7.0, build 3.7.4, bundle ID `com.fabriziodegni.audioenhancermax`, native arm64 executable, minimum macOS 13.0.
- PASS - Mac App Store Connect provisioning profile `AudioEnhancerMAX Mac App Store 3.7` is embedded, targets the same explicit App ID, includes the selected Mac App Distribution certificate, and expires 16 July 2027.
- PASS - The main code signature contains `com.apple.application-identifier=BR9VY292BU.com.fabriziodegni.audioenhancermax` and `com.apple.developer.team-identifier=BR9VY292BU`, matching the embedded profile and resolving Transporter warning 90886 found in superseded build 3.7.3.
- PASS - App Sandbox, user-selected file read/write, network client, and network server entitlements are present.
- PASS - Privacy manifest, third-party notices, Faster-Whisper Medium model, Silero VAD, packaged PyAV codecs, and native frontend are included.

## Native and loopback lifecycle

- PASS - The process appears to macOS as AudioEnhancerMAX, not Python, and runs in the native AppKit/WKWebView shell.
- PASS - `/api/health` reported AudioEnhancerMAX 3.7.0 from the extracted signed payload.
- PASS - The embedded service listened only on `127.0.0.1` during validation.
- PASS - A native AppKit termination request stopped the process and released the loopback port in 0.424 seconds.
- PASS - Trusted-LAN processing and discovery remained disabled at launch.

## Functional validation

- PASS - 26 automated tests completed, including the 16 kHz AutoEQ signal-preservation regression test.
- PASS - Review WAV uploaded and decoded as 16 kHz mono PCM from the signed payload.
- PASS - Podcast processing completed with AutoEQ and loudness normalization; output measured -16.0 LUFS, estimated true peak -1.06 dBTP, zero clipped samples, and output/source RMS ratio 1.035.
- PASS - The processed 24-bit WAV decoded successfully and remained audible after the sample-rate-aware AutoEQ correction.
- PASS - Delivery Compliance exposed six transparent targets and returned rule-level evidence with a non-certification disclaimer.
- PASS - Blind A/B preference persisted locally and revealed the mapping only after the decision.
- PASS - Project Capsule exported a SHA-256 manifest, processed output, compliance result, A/B result, and processing report; original audio remained excluded by default.
- PASS - Processing report schema 2 recorded version/build, source/output SHA-256 hashes, local execution, and no external service used by the job.
- PASS - Five output profiles were exposed: Podcast, YouTube/video, Audiobook, Lossless archive, and Source-quality master.
- PASS - Bundled Faster-Whisper returned 123 English characters across two timestamped segments without downloading a model.
- PASS - Review Deck and public website passed desktop/mobile checks with working navigation and no horizontal overflow.

## Review-boundary evidence

- PASS - `com.apple.security.network.server` has matching functionality: the native WKWebView connects to the app-owned FastAPI/Uvicorn listener bound exclusively to loopback while the app is running.
- PASS - Delivery measurements are described as workflow guidance, not certification; true peak is explicitly a 4x-oversampled estimate.
- PASS - Core DSP, transcription, reports, compliance checks, A/B review, and Project Capsule creation are local.
- PASS - Original audio is preserved and excluded from the portable capsule unless the user opts in.

## Remaining Apple-controlled/manual gates

- PASS - Transporter delivered build 3.7.4 on 20 August 2026 at 22:13 CEST with no delivery issue or warning; wait for App Store Connect processing to complete.
- Add build 3.7.4 to an internal TestFlight group and install it through TestFlight on the physical Mac.
- Record Apple's requested uninterrupted workflow on the latest public macOS available on recording day, including About This Mac, native app identity, loopback lifecycle, processing, review, exports, transcription, and quit.
- Select build 3.7.4 in the macOS 3.7.0 version record, attach the recording, review WAV, and dossier, paste the prepared Review Notes, and reply to Guidelines 2.1 and 2.4.5.
- Replace marketing `[LIVE URL]` placeholders only after the relevant distribution URL is actually live.
