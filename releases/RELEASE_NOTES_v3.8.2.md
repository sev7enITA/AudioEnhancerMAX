# AudioEnhancerMAX 3.8.2

Release date: 15 October 2026.

This maintenance release aligns the website, desktop landing page, release descriptions and feature lists around the delivered audio workflow: verified DSP checkpoints, completed output revisions, exact-format delivery checks and Project Capsules. Audio processing behavior is unchanged from 3.8.0.

## Distribution

The macOS arm64 DMG is a Developer ID signed preview for macOS 13+. Apple notarization remains pending. The required account agreement was accepted on 15 October 2026. The existing notarized 3.7.0 remains the stable Mac download. The separate App Store candidate was submitted on 16 October 2026; approval and publication remain pending.

Source archives exclude user recordings, private voice profiles and credentials. Third-party vendored sources and licenses are preserved.

## Mac App Store follow-up: 16 October 2026

Internal build 3.8.3 corrects a local transcription error under version 3.8.2. Apple delivered and processed the package on 16 October. Verification of the TestFlight-installed app passed for local processing, transcription, speech editing and exports. Version 3.8.2 with build 3.8.3 was submitted on 16 October 2026 at 16:52 Europe/Rome, and Apple confirmed Waiting for Review. The reviewer response with the recording link was sent. App Store approval and publication remain pending. The original direct-download 3.8.2 artifacts were unchanged at that submission. See the direct-build update below.

## Direct download alignment: 18 October 2026

The corrected preview is **version 3.8.2, build 3.8.3**, with a distinct filename: `AudioEnhancerMAX-v3.8.2-build-3.8.3-macOS-arm64.dmg`. It includes the local transcription correction already tested in the separate TestFlight build. The old DMG remains a historical artifact and is not the corrected build.

The new DMG is Developer ID signed. Apple notarization is still pending. **Both versions are available for users to choose:** [3.7.0, stable and notarized](https://github.com/sev7enITA/AudioEnhancerMAX/releases/tag/v3.7.0), and this internally validated 3.8.2/build 3.8.3 signed preview. The [website comparison](https://fabriziodegni.com/AudioEnhancerMAX/#download) presents both downloads and their changelogs with equal prominence. Direct transcription models are runtime-managed and may download on first use; the App Store package bundles its model separately.

Validation: 79 Python tests and 4 JavaScript tests passed. The mounted direct DMG passed processing, normal and streaming transcription, speech-edit apply/undo/redo/render, WAV/MP3/FLAC export hashes and Project Capsule integrity checks. The developer-owned 8-second sample used an existing Medium model cache with Hugging Face and Transformers offline flags. This does not establish first-time setup, perceptual audio quality, Apple notarization or App Store approval. [Build evidence and SHA-256](DIRECT_BUILD_3.8.3.md).
