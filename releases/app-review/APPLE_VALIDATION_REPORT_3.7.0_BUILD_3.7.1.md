# AudioEnhancerMAX 3.7.0 (Build 3.7.1) — Validation Report

Validation date: 14 August 2026

## Release artifact

- Package: `AudioEnhancerMAX-v3.7.0-build-3.7.1-MacAppStore.pkg`
- Package size: 1,834,261,057 bytes (approximately 1.71 GiB)
- Package SHA-256: `08919485e1e26b1736553a956e335ee4548598ce9ce11b37341852dcddd5ce5b`
- Review sample SHA-256: `ffeb0404b2297182811be38c8e2f7a0a6fb19e4ba8cfb7efe32d346ce2339ff4`

## Package and identity

- PASS — Installer signature accepted by `pkgutil --check-signature` with trusted timestamp `2026-08-14 17:25:57 +0000`.
- PASS — Installer identity: `3rd Party Mac Developer Installer: Fabrizio Degni (BR9VY292BU)`.
- PASS — Application identity: `3rd Party Mac Developer Application: Fabrizio Degni (BR9VY292BU)`.
- PASS — Extracted PKG payload passed `codesign --verify --deep --strict`.
- PASS — Marketing version 3.7.0, build 3.7.1, bundle ID `com.fabriziodegni.audioenhancermax`, native arm64 executable.
- PASS — App Sandbox, user-selected file read/write, network client and network server entitlements are present.
- PASS — Privacy manifest, third-party notices, Faster-Whisper Medium model and Silero VAD asset are packaged.

## Native and loopback lifecycle

- PASS — The packaged process appears to macOS as `AudioEnhancerMAX`, not Python.
- PASS — The interface runs in the native AppKit/WKWebView shell without opening an external browser.
- PASS — `/api/health` reported AudioEnhancerMAX 3.7.0 from the extracted signed payload.
- PASS — The embedded server listened only on `127.0.0.1` during validation.
- PASS — Native Quit released the loopback port in 0.683 seconds; the process then exited.
- PASS — Trusted-LAN processing and discovery remained disabled at launch.

## Functional validation

- PASS — 19 automated unit tests cover deterministic tuning, capability fallback, output profiles, processing reports, runtime privacy, desktop sandbox paths, revisioned speech editing and trusted-LAN opt-in defaults.
- PASS — Review WAV uploaded and decoded as 16 kHz mono PCM from the signed PKG payload.
- PASS — Lossless Archive profile exported FLAC; the result decoded successfully as FLAC, 16 kHz, mono.
- PASS — Auto EQ and loudness normalization completed; WAV, MP3 and FLAC downloads each decoded successfully as 16 kHz mono audio.
- PASS — Processing report recorded app version 3.7.0, archive profile, FLAC format, local processing and no external-service use by the job.
- PASS — Bundled Faster-Whisper transcription returned English text with 123 characters across two timestamped segments without a model download.
- PASS — Runtime controls exposed independent permissions for external services, local Ollama editorial assistance and trusted-LAN processing.
- PASS — Five output profiles were exposed: Podcast, YouTube/video, Audiobook, Lossless archive and Source-quality master.
- PASS — Website landing and roadmap passed independent desktop/mobile evaluation after correction of mobile navigation, word wrapping and supporting-text contrast.

## Marketing evidence validation

- PASS — English and Italian App Store subtitles, promotional text, keywords, descriptions and What’s New copy fit the documented Apple field limits.
- PASS — Claims matrix maps public wording to implementation and test/package evidence.
- PASS — No unsupported performance percentage, universal quality promise, App Store availability claim or false six-profile claim is present in the launch assets.
- PASS — Roadmap separates delivered 3.7 foundations from research candidates and community signals.

## Remaining Apple-controlled/manual gates

- Upload build 3.7.1 with Transporter and wait for App Store Connect processing.
- Add build 3.7.1 to an internal TestFlight group and reinstall it through TestFlight on the physical Mac.
- Record Apple’s requested unedited workflow on the latest public macOS available at recording time. Apple lists macOS Tahoe 26.6 as the current public release on 14 August 2026; verify again on recording day.
- Select build 3.7.1 in the macOS 3.7.0 version record, attach the video, sample and dossier, paste the Review Notes, and reply to Guidelines 2.1 and 2.4.5.
- Replace campaign `[LIVE URL]` placeholders only after the distribution URL is actually live.
