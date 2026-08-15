# AudioEnhancerMAX 3.5.2 (Build 3.5.3) - Validation Report

Validation date: 19 July 2026

## Release artifact

- Package: `AudioEnhancerMAX-v3.5.2-build-3.5.3-MacAppStore.pkg`
- Package size: 1,829,417,187 bytes (approximately 1.7 GB)
- Uncompressed app size: 2,721,021,952 bytes (approximately 2.5 GB)
- Package SHA-256: `b77a113a1b023dc5c0e0b56501aabd19074586719244b44c41ac341f0fb41e8f`
- Review sample SHA-256: `ffeb0404b2297182811be38c8e2f7a0a6fb19e4ba8cfb7efe32d346ce2339ff4`

## Package and code-signing result

- PASS - `pkgutil --check-signature` accepted the package and its certificate chain.
- PASS - Installer identity: `3rd Party Mac Developer Installer: Fabrizio Degni (BR9VY292BU)`.
- PASS - Trusted timestamp: `2026-07-19 09:35:11 +0000`.
- PASS - Application identity: `3rd Party Mac Developer Application: Fabrizio Degni (BR9VY292BU)`.
- PASS - `codesign --verify --deep --strict` accepted the extracted application in a clean temporary path.
- PASS - Main executable is a native arm64 Mach-O binary.
- PASS - Version is 3.5.2 and build is 3.5.3.
- PASS - Main entitlements are limited to App Sandbox, network client, and network server.
- PASS - The package contains the privacy manifest and third-party notices.
- PASS - The package contains no standalone `ffmpeg` or `ffprobe` executable.

## Self-contained runtime result

- PASS - Faster-Whisper Medium model files are packaged.
- PASS - `faster_whisper/assets/silero_vad_v6.onnx` is packaged.
- PASS - PyAV 17.0.0 and its embedded FFmpeg libraries are available.
- PASS - Preflight status is `ready` with 11 passes, zero warnings, and zero blockers.
- PASS - Preflight reports self-contained distribution, no external installation, and no transmitted diagnostics.
- PASS - App Store capabilities hide/disable Kokoro voice cloning and Demucs music separation.
- PASS - Edge Cluster is disabled at launch and performs no discovery until explicitly enabled.
- PASS - The sandboxed launcher uses the application container for data, settings, logs, and lock state.

## Functional smoke test result

Test input: `AudioEnhancerMAX-review-sample.wav`, 8.41975 seconds, mono, 16 kHz PCM.

- PASS - Sandboxed app launched and returned a healthy status.
- PASS - Root UI returned `text/html`; JavaScript returned `application/javascript` without reading a sandbox-forbidden system MIME file.
- PASS - WAV upload and waveform generation completed.
- PASS - Auto EQ plus normalization completed.
- PASS - Processed WAV downloaded and decoded: mono, 16 kHz, 8.42 seconds.
- PASS - Processed MP3 downloaded and decoded: mono, 16 kHz, 8.42 seconds, `audio/mpeg`.
- PASS - Processed FLAC downloaded and decoded: mono, 16 kHz, 8.42 seconds, `audio/flac`.
- PASS - Local-only Faster-Whisper transcription returned two English segments in 15.76 seconds.

Transcription result:

> Audio Enhancer Max Review Sample. This recording verifies local audio enhancement, export, and fully offline transcription.

- PASS - Graceful shutdown completed and stopped the embedded local service.

## Validation hardware

- Physical MacBook Pro, model identifier Mac15,9
- Apple M3 Max
- 64 GB RAM
- Development validation OS: macOS 27.0, build 26A5378n (pre-release)

## Mandatory manual release gate

Apple requested a physical-device screen recording on the latest public OS. The current development machine runs a pre-release OS, so it cannot satisfy that specific evidence request. Before resubmission, repeat the scripted reviewer flow and record it on a physical Apple silicon Mac running macOS Tahoe 26.5.2, the latest public release as of 19 July 2026. Record the exact public OS build number in App Review Notes.
