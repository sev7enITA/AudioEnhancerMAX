# AudioEnhancerMAX 3.8.3, build 3.8.4

Local audio editing with AI governance built in.

This maintenance release strengthens the connection between your privacy choices, editing decisions and exported evidence. It is the latest direct download for Apple Silicon Macs running macOS 13 or later, available free under the MIT license.

## Changes

- Optional services remain disabled when saved privacy preferences are missing, invalid or unreadable. The interface explains how to recover; valid saved choices remain intact.
- Project Capsules preserve the speech decisions and transcript used by a new render, even when you edit or transcribe again later. Older renders without sufficient evidence receive an explicit warning.
- Capsule hashes and sizes describe the exact bytes in the archive. Missing or unbound processing reports produce an unknown execution boundary rather than an assumed local result.
- File import reads bounded chunks and decodes in a worker, keeping other API requests responsive. Failed imports remove partial files. Decoding still uses memory for the audio and this is not a general memory cap.
- Includes the local transcription correction and revision-bound processing, exports and checkpoints from the 3.8 branch.

## Downloads and Apple status

The direct DMG is Developer ID signed, Apple notarized and stapled. The separate Mac App Store submission remains version 3.8.2/build 3.8.3, last verified Waiting for Review on 17 October 2026. Notarization does not mean App Store approval.

[Download 3.8.3](https://github.com/sev7enITA/AudioEnhancerMAX/releases/download/v3.8.3/AudioEnhancerMAX-v3.8.3-build-3.8.4-macOS-arm64.dmg) · [SourceForge mirror](https://sourceforge.net/projects/audioenhancermax/files/v3.8.3/) · [Compare with the earlier 3.7.0 release](https://fabriziodegni.com/AudioEnhancerMAX/#download).

## Verification and limits

101 Python tests, 8 subtests and 5 JavaScript tests passed. The final mounted DMG passed processing, normal/streaming transcription, speech-edit apply/undo/redo/render, WAV/MP3/FLAC export, privacy recovery and capsule-integrity checks on a physical Apple Silicon Mac. Capsule evidence remained bound to the rendered decisions after later edits and a replaced transcript.

Transcription used an existing Medium model cache with offline flags. First-time model download, every supported macOS version and perceptual audio quality are outside this verification. Direct models may download on first use. Reports and hashes support review; they do not certify transcription accuracy, speaker consent or legal compliance.

[Exact package evidence](DIRECT_BUILD_3.8.4.md). Historical releases and the existing Apple submission are preserved.
