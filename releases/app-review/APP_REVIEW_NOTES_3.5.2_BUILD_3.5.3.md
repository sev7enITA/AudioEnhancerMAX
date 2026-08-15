# AudioEnhancerMAX 3.5.2 (Build 3.5.3) - App Review Notes

## Review access and setup

No account, login, subscription, in-app purchase, activation key, special hardware, or external installation is required.

1. Launch AudioEnhancerMAX from Applications.
2. The app starts its packaged processing service and opens its interface in the default browser.
3. Wait for the readiness panel to report Ready.
4. Upload the attached `AudioEnhancerMAX-review-sample.wav` file.
5. Enable Auto EQ and Normalize, then select Process Audio.
6. Use the original/processed comparison and export the result as WAV, MP3, or FLAC.
7. Open Transcription and transcribe the same sample. Faster-Whisper Medium and its VAD asset are bundled and run locally without a model download.

The main DSP and transcription workflow remains functional with the Mac disconnected from the internet.

## Purpose and audience

AudioEnhancerMAX is a local audio cleanup and speech-production tool for podcasters, interviewers, journalists, educators, researchers, voice-over creators, and other users who need to improve recordings, compare the result, export audio, or produce a transcript.

## Why `com.apple.security.network.server` is required

AudioEnhancerMAX is a packaged desktop application whose user interface communicates with an embedded FastAPI/Uvicorn service. At launch, the service binds only to the loopback interface (`127.0.0.1`) on port 8000, or another available local port. The user's browser then initiates an inbound TCP connection to that local service. The service is not exposed on a public interface and stops when the app exits. This inbound loopback connection requires the `com.apple.security.network.server` entitlement.

The app also contains an optional Edge Cluster feature for a user-controlled trusted local network. It is disabled at launch and performs no discovery until the user explicitly selects Enable and discover. When enabled, it uses local UDP discovery and connects only to worker addresses on the user's LAN. This optional feature also requires server/client network access. The core audio and transcription workflow does not require Edge Cluster.

## External services

- Core audio processing: entirely local, using packaged PyAV/FFmpeg libraries and DSP modules. No external `ffmpeg` or `ffprobe` executable is installed or invoked.
- Transcription: entirely local, using the packaged Faster-Whisper Medium model. No runtime model download is required.
- Microsoft Edge Neural TTS: optional. Only text entered by the user is sent to Microsoft's speech service when the user explicitly requests speech synthesis. Internet availability and voice availability may vary by region.
- Local Ollama/Gemma: optional and not required. If the user already runs Ollama on `127.0.0.1`, the app can use it for editing suggestions; otherwise deterministic local fallback behavior is used.
- Edge Cluster: optional and disabled by default. It communicates only with trusted worker computers explicitly enabled or added by the user on the local network.

There are no analytics SDKs, advertising SDKs, account services, payment services, cloud audio storage services, or social/UGC publishing services in this build.

## Regional behavior

Core DSP, local export, and local transcription are the same in every region. Optional Microsoft Edge Neural TTS voice availability may vary by network or region. No other feature or content is region-specific.

## Regulated industries and protected material

The app is a general-purpose audio production utility. It is not intended for medical diagnosis, treatment, financial transactions, gambling, legal certification, or another regulated service. The review sample is developer-created speech and contains no protected third-party content.

## Supported hardware and OS

- Apple silicon Mac (arm64)
- macOS 13.0 or later
- No additional hardware is required

Technical validation for this build was completed on a physical MacBook Pro with Apple M3 Max and 64 GB RAM. The final review video must be recorded on the latest public macOS release, macOS Tahoe 26.5.2, and attached under App Review Information before resubmission.

## Reviewer attachment

- `AudioEnhancerMAX-review-sample.wav`
- Physical-device screen recording following `SCREEN_RECORDING_SCRIPT.md`
- `AudioEnhancerMAX-App-Review-Dossier-3.5.2-build-3.5.3.pdf`
