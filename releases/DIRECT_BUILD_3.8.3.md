# Direct preview 3.8.2, build 3.8.3

Verified on 18 October 2026. This is the Developer ID direct-download package, separate from TestFlight and the pending Mac App Store submission.

- File: `AudioEnhancerMAX-v3.8.2-build-3.8.3-macOS-arm64.dmg`
- Size: 134274038 bytes
- SHA-256: `d33ceb832100487bc61ea67af8260895a812df3059f7b5f35f9c8e6025e1b6b3`
- Bundle: version `3.8.2`, build `3.8.3`, distribution `direct`, Apple Silicon, macOS 13+.
- Signature: strict verification passed for the application and DMG.
- Notarization: **not completed**. No stapled ticket; Gatekeeper reports `Unnotarized Developer ID`. The recommended stable download remains [3.7.0](https://github.com/sev7enITA/AudioEnhancerMAX/releases/download/v3.7.0/AudioEnhancerMAX-v3.7.0-macOS-arm64.dmg).

The corrected DMG includes the local transcription fix already present in the separate TestFlight build. The earlier file without `build-3.8.3` in its name is retained as a historical preview. It is not the corrected download.

## Verification of this DMG

The application was run from the mounted, read-only DMG on a physical Apple Silicon Mac. Runtime metadata reported version 3.8.2/build 3.8.3. Packaged frontend files matched the source used for this build.

- Local processing and revision-specific WAV, MP3 and FLAC exports passed.
- Exported bytes matched the SHA-256 in response headers and delivery metadata.
- Normal and streaming transcription of the developer-owned review sample completed.
- Precision Speech Editor analysis produced 20 candidates; apply, undo, redo and rendering completed.
- Source bytes were preserved; the Project Capsule excluded the source by default and all included artifact hashes matched.
- Optional external services, local editorial assistance and trusted-LAN processing were disabled.
- 79 Python tests, 8 subtests and 4 JavaScript tests passed.

The transcription check used an existing Faster-Whisper Medium cache with `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`. Direct-download models are runtime-managed and can download on first use. This check does not establish first-time model acquisition, behavior on every supported macOS version, perceptual audio quality, notarization or App Store approval. TestFlight gallery screenshots retain their separate provenance and bundled-model distribution.

## Reproduce the package

Use Python 3.11 and the pinned direct-runtime/build dependencies, then `./scripts/build_macos_app.sh`. The script validates bundle version, build and direct distribution before signing, including when reusing an intermediate bundle. Set `AEMAX_BUILD_DIR` and `AEMAX_DIST_DIR` to isolate packaging output. Final source commit and archive hashes are recorded in the accompanying release manifest.

Apple notarization requires a valid `notarytool` credential profile. Signing alone does not establish notarization. No Mac App Store submission was changed by this alignment.
