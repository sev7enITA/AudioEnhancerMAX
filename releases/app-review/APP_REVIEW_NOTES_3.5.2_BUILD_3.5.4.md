# AudioEnhancerMAX 3.5.2 (Build 3.5.4) - App Review Notes

## Review access and setup

No account, login, subscription, in-app purchase, activation key, special hardware, or external installation is required.

1. Launch AudioEnhancerMAX from Applications.
2. The interface opens in the app's native macOS window. The default browser is not launched.
3. Select the upload area and choose the attached `AudioEnhancerMAX-review-sample.wav` with the standard macOS Open panel.
4. Enable Remove Noise and select Process Audio.
5. Compare Original and Processed audio, then export WAV, MP3, or FLAC with the standard macOS Save panel.
6. Open Speech to Text and transcribe the same sample. Faster-Whisper Medium and its VAD asset are bundled and run locally without a model download.
7. Close the main window or quit the app. The embedded loopback service stops and its port is released.

The main DSP, export, and transcription workflow remains functional with the Mac disconnected from the internet.

## Purpose and audience

AudioEnhancerMAX is a local audio cleanup and speech-production tool for podcasters, interviewers, journalists, educators, researchers, voice-over creators, and other users who need to improve recordings, compare results, export audio, or produce a transcript.

## Why `com.apple.security.network.server` is required

AudioEnhancerMAX contains a native AppKit window with an embedded WKWebView. At launch, the same application process starts an embedded FastAPI/Uvicorn processing service bound exclusively to the loopback interface (`127.0.0.1`) on port 8000, or another available local port. The embedded WKWebView initiates an inbound TCP connection to this private local service. Nothing is bound to a LAN or public interface during the core workflow.

The loopback listener exists only while AudioEnhancerMAX is running. Closing the main window or quitting the app stops Uvicorn, terminates the app process, and releases the listening port. This inbound loopback connection is matching functionality for `com.apple.security.network.server`.

The app also contains an optional Edge Cluster feature for a user-controlled trusted local network. It is disabled at launch and performs no discovery until the user explicitly enables it. Core audio processing and transcription do not require Edge Cluster.

## Other sandbox entitlements

- `com.apple.security.app-sandbox`: enables App Sandbox.
- `com.apple.security.files.user-selected.read-write`: allows the user to select input audio and save exports through standard macOS panels.
- `com.apple.security.network.client`: supports the embedded WKWebView connection and explicitly requested optional network features.

## External services and tools

- Core audio processing: local, using packaged PyAV/FFmpeg libraries and DSP modules. No external `ffmpeg` or `ffprobe` executable is installed or invoked.
- Transcription: local, using the packaged Faster-Whisper Medium model. Runtime model download is disabled.
- Microsoft Edge Neural TTS: optional. Only user-entered text is sent when the user explicitly requests synthesis; availability can vary by region or network.
- Local Ollama/Gemma: optional and not required. If the user already runs Ollama on `127.0.0.1`, the app can use it for editing suggestions; otherwise local fallback behavior is used.
- Edge Cluster: optional, disabled by default, and limited to trusted local workers explicitly enabled or added by the user.

There are no analytics, advertising, account, payment, cloud-audio-storage, or social/UGC publishing services in this build.

## Regional behavior and regulated content

Core DSP, local export, and local transcription behave consistently across regions. Optional Microsoft TTS availability may vary by network or region. AudioEnhancerMAX is a general-purpose audio production utility, not a medical, financial, gambling, or legal-certification service. The supplied sample is developer-created and contains no protected third-party material.

## Supported hardware and validation

- Apple silicon Mac (arm64)
- macOS 13.0 or later
- No additional hardware required

Automated and interactive validation was completed on a physical MacBook Pro (Mac15,9), Apple M3 Max, 64 GB RAM. Build 3.5.4 was verified as a signed sandboxed app: native-window launch, Open panel, WAV upload, noise removal, completed processed audio, Save panel, graceful shutdown, and loopback-port release all passed.

Apple's requested final video should be recorded through the TestFlight/App Store delivery path on a physical Apple silicon Mac running the latest public macOS release available on the recording date. Include the exact macOS build number in Review Notes.

## Reviewer attachments

- `AudioEnhancerMAX-review-sample.wav`
- `AudioEnhancerMAX-3.5.2-build-3.5.4-physical-macOS.mov`
- `AudioEnhancerMAX-App-Review-Dossier-3.5.2-build-3.5.4.pdf`
