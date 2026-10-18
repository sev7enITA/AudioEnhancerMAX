# Direct release 3.8.3, build 3.8.4

Verified on 18 October 2026 from the mounted, read-only DMG on a physical Apple Silicon Mac. This package is separate from the existing Mac App Store submission 3.8.2/build 3.8.3.

- File: `AudioEnhancerMAX-v3.8.3-build-3.8.4-macOS-arm64.dmg`
- Size: 134372948 bytes
- SHA-256: `316ff0f7f9ccf4f478e5762431bd7b1bd2a859c570779e81eb46a1d467e16f84`
- Application source: `7194c45ae963da4eb465e6a6be948e5249601f6b`
- Bundle: version 3.8.3, build 3.8.4, direct distribution, Apple Silicon, macOS 13+.
- Application and DMG: strict Developer ID signature verification passed.
- Apple notarization: **Accepted**, submission `83480e36-00d9-4476-bae3-95c0179a5309`.
- Ticket stapling and validation passed. Gatekeeper accepted the DMG as `Notarized Developer ID`.

## Verification

101 Python tests, 8 subtests and 5 JavaScript tests passed. The frozen application was then run directly from this DMG using isolated data:

- Corrupt privacy preferences disabled optional services; invalid string permissions were rejected; valid choices could be saved.
- Audio processing and WAV, MP3 and FLAC exports completed. Download hashes matched response headers and delivery metadata.
- Normal and streaming transcription completed using the developer-owned review sample.
- Speech analysis, manual edit, undo, redo and rendering completed.
- A later decision change and replaced transcript did not alter the rendered edit list and transcript exported in a Project Capsule.
- Every included capsule artifact matched its declared byte size and SHA-256. Original audio was excluded by default; source bytes remained unchanged.
- Packaged frontend files matched the application source.

## Limits and reproduction

Transcription used an existing Faster-Whisper Medium cache with offline flags. This does not verify first model download, every macOS version or perceptual audio quality. Models can download on first use. Notarization is distinct from App Store review and approval.

Build with the pinned Python 3.11 runtime and `scripts/build_macos_app.sh`, setting `AEMAX_MARKETING_VERSION=3.8.3`, `AEMAX_BUILD_NUMBER=3.8.4`, isolated build/dist directories and a locally configured `AEMAX_NOTARY_PROFILE`. Signing and notarization timestamps mean a rebuilt package is not expected to have this exact hash. Verify the published artifact against its manifest.

Machine-readable results: [DIRECT_BUILD_3.8.4.json](DIRECT_BUILD_3.8.4.json). The earlier 3.7.0 release remains available with its own changelog.
