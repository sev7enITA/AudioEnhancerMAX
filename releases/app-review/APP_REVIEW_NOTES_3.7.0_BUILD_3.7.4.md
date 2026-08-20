# AudioEnhancerMAX 3.7.0 (Build 3.7.4) — App Review Notes

## Access and typical workflow

No account, login, purchase, activation key, special hardware, sample credential, or external installation is required.

1. Launch AudioEnhancerMAX. The interface opens in an app-owned AppKit/WKWebView window; the default browser is not opened.
2. Choose the attached `AudioEnhancerMAX-review-sample.wav` with the standard macOS Open panel.
3. Run Smart Enhance or choose a delivery profile and process the file.
4. In the Review Deck, inspect the local Delivery Compliance result, complete a randomized blind A/B comparison, and export a Project Capsule. Original audio is excluded from the capsule unless the reviewer explicitly enables “Include original audio.”
5. Open the Processing Report to inspect the selected profile, pipeline engines, privacy boundary, delivery checks, and SHA-256 provenance; export WAV, MP3, or FLAC with the standard Save panel.
6. Open Precision Speech Editor, review a transcript-linked cut/mute decision, preview it, undo/redo, and render to a new file.
7. Open Speech to Text to transcribe the same sample locally with the bundled Faster-Whisper Medium model.
8. Quit the app. The embedded loopback listener stops and its port is released.

The core DSP, export, Delivery Compliance Lab, Project Capsule, Processing Report, Precision Editor, and packaged transcription workflow works without an external service. Delivery Compliance results are workflow guidance, not regulatory or third-party certification. Blind A/B results are subjective reviewer preferences, not objective quality scores.

## Purpose and target audience

AudioEnhancerMAX is a local-first audio cleanup, review, and speech-production utility for podcasters, interviewers, journalists, educators, researchers, voice-over creators, and other Mac users. It solves the problem of opaque audio automation by making diagnosis, editorial changes, delivery checks, execution boundaries, and export evidence visible and reviewable.

## Why `com.apple.security.network.server` is required

The native WKWebView connects inbound to an embedded FastAPI/Uvicorn service in the same application. The service binds exclusively to `127.0.0.1` on port 8000 or another available loopback port. It is not exposed to the LAN or internet during the core workflow. Closing the main window or choosing Quit stops Uvicorn and releases the port. This app-owned inbound loopback listener is the matching functionality for `com.apple.security.network.server`.

The separate Edge Cluster feature is optional, disabled at launch, and performs no LAN discovery until the user explicitly enables trusted-LAN processing.

## External services, tools, and regional behavior

- Core DSP, media export, delivery checks, evidence capsules, reports, Precision Editor, and Faster-Whisper transcription are local.
- Microsoft Edge Neural TTS is optional; only user-entered text is sent after an explicit synthesis request. It can be disabled in Privacy & Offline settings.
- Local Ollama/Gemma editorial assistance is optional, independently controllable, and does not select DSP parameters.
- Trusted-LAN workers are optional, disabled by default, and independently controllable.
- No analytics, advertising, account, payment, subscription, cloud audio storage, or UGC publishing service is included.

Core features are consistent across regions. Optional online TTS availability can vary by network or region.

## Regulated content and third-party material

The app is a general-purpose audio production utility. It is not a medical, financial, gambling, legal-certification, or other regulated service. The supplied review WAV is developer-created and contains no protected third-party material.

## Tested configuration and attachments

The signed arm64 PKG is tested on a physical MacBook Pro (Mac15,9), Apple M3 Max, 64 GB RAM. The continuous reviewer recording must identify the exact public macOS version/build used on the recording date.

Attachments:

- `AudioEnhancerMAX-review-sample.wav`
- `AudioEnhancerMAX-3.7.0-build-3.7.4-physical-macOS.mov`
- `AudioEnhancerMAX-App-Review-Dossier-3.7.0-build-3.7.4.pdf`
