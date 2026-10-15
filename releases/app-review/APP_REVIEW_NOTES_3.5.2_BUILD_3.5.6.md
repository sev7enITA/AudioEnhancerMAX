# AudioEnhancerMAX 3.5.2 (Build 3.5.6) - App Review Notes

## Access and typical workflow

No account, login, purchase, activation key, special hardware, or external installation is required.

1. Launch AudioEnhancerMAX. The UI opens in an app-owned AppKit/WKWebView window; the default browser is not opened.
2. Choose the attached `AudioEnhancerMAX-review-sample.wav` with the standard macOS Open panel.
3. Select a delivery profile or audio cleanup option, process the file, compare the result, open the local processing report, and export with the standard Save panel.
4. Open Speech to Text to transcribe the same sample locally with the bundled Faster-Whisper Medium model.
5. Quit the app. The embedded loopback listener stops and its port is released.

The core DSP, export, report, and transcription workflow works offline.

## Purpose and audience

AudioEnhancerMAX is a local-first audio cleanup and speech-production utility for podcasters, interviewers, journalists, educators, researchers, and voice-over creators. It preserves source files while providing enhancement, delivery profiles, local quality reports, transcription, and a review-first non-destructive speech edit list.

## Why `com.apple.security.network.server` is required

The native WKWebView connects to an embedded FastAPI/Uvicorn service in the same application. The service binds exclusively to `127.0.0.1` on port 8000 or another available loopback port. It is not exposed to the LAN or internet during the core workflow. Closing the main window or choosing Quit stops Uvicorn and releases the port. This app-owned inbound loopback connection is the matching functionality for `com.apple.security.network.server`.

The separate Edge Cluster feature is optional, disabled at launch, and performs no LAN discovery until the user explicitly enables trusted-LAN processing.

## External services and regions

- Core processing, export, reports, and Faster-Whisper transcription are local.
- Microsoft Edge Neural TTS is optional; only user-entered text is sent after an explicit synthesis request. It can be disabled in Privacy & Offline settings.
- Local Ollama/Gemma editorial assistance is optional, independently controllable, and not required for deterministic DSP.
- Trusted-LAN workers are optional and independently controllable.
- No analytics, ads, account, payment, cloud audio storage, or UGC publishing service is included.

Core features are consistent across regions. Optional online TTS availability can vary by network or region. The app is a general-purpose audio utility, is not a regulated service, and the supplied sample is developer-created.

## Tested configuration and attachments

The signed arm64 PKG was validated on a physical MacBook Pro (Mac15,9), Apple M3 Max, 64 GB RAM. The current development OS on that Mac is macOS 27.0 build 26A5406e; this is technical validation only. Apple's requested continuous video must be recorded from the TestFlight build on the latest public macOS release available at recording time.

Attachments:

- `AudioEnhancerMAX-review-sample.wav`
- `AudioEnhancerMAX-3.5.2-build-3.5.6-physical-macOS.mov`
- `AudioEnhancerMAX-App-Review-Dossier-3.5.2-build-3.5.6.pdf`
