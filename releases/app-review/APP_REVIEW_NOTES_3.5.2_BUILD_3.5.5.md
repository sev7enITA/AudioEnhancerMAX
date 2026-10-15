# AudioEnhancerMAX 3.5.2 (Build 3.5.5) - App Review Notes

## Review access and setup

No account, login, subscription, in-app purchase, activation key, special hardware, or external installation is required.

1. Launch AudioEnhancerMAX from Applications.
2. The interface opens in the app's native macOS window. The default browser is not launched.
3. The macOS application menu is labeled AudioEnhancerMAX. `About AudioEnhancerMAX` is an app-owned window and does not show Python runtime metadata.
4. Select the upload area and choose the attached `AudioEnhancerMAX-review-sample.wav` with the standard macOS Open panel.
5. Enable Remove Noise and select Process Audio.
6. Compare Original and Processed audio, then export WAV, MP3, or FLAC with the standard macOS Save panel.
7. Open Speech to Text and transcribe the same sample. Faster-Whisper Medium and its VAD asset are bundled and run locally without a model download.
8. Close the main window or quit the app. The embedded loopback service stops and its port is released.

The main DSP, export, and transcription workflow remains functional with the Mac disconnected from the internet.

## Product identity and About window

The first macOS menu is explicitly named AudioEnhancerMAX. The app supplies its own About window containing the product logo, marketing version and build number, distribution, creator and maintainer, purpose, core capabilities, privacy and data-flow boundaries, system requirements, supported file formats, support and safe-reporting guidance, architecture, MIT License, copyright, and links to official support, privacy, accessibility, GitHub, SourceForge, tickets, and releases.

## Purpose and audience

AudioEnhancerMAX is a local audio cleanup and speech-production tool for podcasters, interviewers, journalists, educators, researchers, voice-over creators, and other users who need to improve recordings, compare results, export audio, or produce a transcript.

## Why `com.apple.security.network.server` is required

AudioEnhancerMAX contains a native AppKit window with an embedded WKWebView. At launch, the same application process starts an embedded FastAPI/Uvicorn processing service bound exclusively to the loopback interface (`127.0.0.1`) on port 8000, or another available local port. The embedded WKWebView initiates an inbound TCP connection to this private local service. Nothing is bound to a LAN or public interface during the core workflow.

The loopback listener exists only while AudioEnhancerMAX is running. Closing the main window or quitting the app stops Uvicorn, terminates the app process, and releases the listening port. This inbound loopback connection is matching functionality for `com.apple.security.network.server`.

The optional Edge Cluster feature is disabled at launch and performs no discovery until explicitly enabled. Core processing and transcription do not require Edge Cluster.

## Sandbox entitlements

- `com.apple.security.app-sandbox`: App Sandbox.
- `com.apple.security.files.user-selected.read-write`: user-selected input and export locations through standard macOS panels.
- `com.apple.security.network.client`: embedded WKWebView and explicitly requested optional network features.
- `com.apple.security.network.server`: app-owned inbound loopback listener and optional user-enabled trusted-LAN functionality.

## External services and regional behavior

- Core audio processing: local, using packaged PyAV/FFmpeg libraries and DSP modules.
- Transcription: local, using the packaged Faster-Whisper Medium model; runtime download is disabled.
- Microsoft Edge Neural TTS: optional; user-entered text is transmitted only after an explicit synthesis request and availability can vary by region.
- Local Ollama/Gemma: optional and not required.
- Edge Cluster: optional, disabled by default, and limited to trusted local workers explicitly enabled by the user.

There are no analytics, advertising, account, payment, cloud-audio-storage, or social/UGC publishing services in this build. Core DSP, local export, and local transcription behave consistently across regions.

## Supported hardware and validation

- Apple silicon Mac (arm64)
- macOS 13.0 or later
- No additional hardware required

Build 3.5.5 was packaged as a signed sandboxed Mac App Store installer. Application and installer identities, trusted timestamp, checksum, native arm64 executable, Info.plist product identity, required entitlements, native-window launch, loopback lifecycle, file panels, processing, and export workflow were validated.

Apple's final requested video should be recorded through TestFlight/App Store delivery on a physical Apple silicon Mac running the latest public macOS release available on the recording date. Include the exact macOS build number in Review Notes.

## Reviewer attachments

- `AudioEnhancerMAX-review-sample.wav`
- `AudioEnhancerMAX-3.5.2-build-3.5.5-physical-macOS.mov`
- `AudioEnhancerMAX-App-Review-Dossier-3.5.2-build-3.5.5.pdf`
