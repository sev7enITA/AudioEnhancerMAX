# Direct release 3.9.0, build 3.9.2

Verification date: 27 October 2026. Apple Silicon, macOS 13+. Direct distribution, separate from App Store review.

Apple notarization accepted submission `83ffdd9b-db2a-4ac3-a23d-b2d7c0a02cfd`. The ticket is stapled to the DMG and validates successfully. Gatekeeper accepts both the disk image and the enclosed app as Notarized Developer ID.

- Post-stapling SHA-256: `4b258e3c5b0ccc94788eae3d2215a86b3acbdbfc678151d16dcac2fb97b0d162`.
- Size: 132,911,847 bytes.

## Application source and package

- Application source commit: `8079c262fc0b163c259b265172dd95a04520ff3c`.
- File: `AudioEnhancerMAX-v3.9.0-build-3.9.2-macOS-arm64.dmg`.
- Bundle version/build: 3.9.0 / 3.9.2; stable identity `com.fabriziodegni.audioenhancermax`.
- App and disk image passed Developer ID signature verification. The signed app was tested from the read-only DMG on a physical Apple M3 Max running macOS 27.2.
- Packaged frontend bytes match the application source. Python 3.11.15 arm64 runtime.

## Automated and dependency checks

135 Python tests, 11 subtests and 19 JavaScript tests passed. Source compilation, JavaScript syntax and diff whitespace checks passed. The build environment passed `pip check`. `pip-audit` reported no known vulnerabilities on 27 October after updating aiohttp 3.14.4, certifi 2026.10.19, filelock 4.2.1, Pillow 13.0.0, yarl 1.25.1 and setuptools 84.1.0. Dependency checks describe the packages scanned, not a general security certification or a full native-library audit.

## Signed-package workflow checks

- Native AppKit/WKWebView launch, stable badge and correct version/build; readiness has no mandatory blockers.
- Six Music brief presets build locally; separate lyrics preserve whitespace; malformed descriptions are rejected. Refinement is rejected while its permission is disabled.
- Native Music brief generation, manual editing and JSON save. The actual selected save path was checked; original and edited captions remain distinct.
- Native file selection, audio processing and WAV save; saved audio decodes successfully.
- API processing with noise reduction, EQ and loudness normalization, plus WAV/MP3/FLAC exports. Each export hash matches its response metadata. MP3 re-import exercises bundled codecs.
- Local normal and streaming transcription complete using the existing Medium model cache.
- Speech candidates default to Keep. Manual mute, undo, redo and rendering complete while preserving the source.
- Processed and speech-edit capsules contain the expected revision. Every included artifact matches its manifest size and SHA-256; source audio remains excluded by default.
- Source bytes and privacy settings are unchanged by the verification workflow.
- Closing the app stops its loopback service.

Stable upgrade data preservation and Experimental data separation are covered by launcher regressions. The final package retains the established stable identity; no automatic Experimental-data migration is performed.

## Scope and limits

The sample is developer-created. Its 16 kHz rate produces an expected Podcast-target notice; noise reduction alone is not a finished podcast master. First-time model download, every macOS version, concurrent Stable/Experimental windows, optional engine inference and perceptual audio quality are outside these package checks. Ollama refinements have source-level mocked regressions and a packaged disabled-permission check, not a new live inference-quality validation.

Music brief is text only, with session-only drafts and no JSON re-import. Initial transcription model acquisition can require network access. Optional neural/voice engines have separate requirements. Apple notarization does not establish App Store approval or application functionality.
