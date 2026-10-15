# Resolution Center Reply — AudioEnhancerMAX 3.7.0 build 3.7.2

Hello App Review Team,

Thank you for the detailed guidance. We have prepared build 3.7.2 and supplied the requested information and physical-Mac evidence.

Regarding `com.apple.security.network.server`: AudioEnhancerMAX presents its interface in an app-owned AppKit/WKWebView window. That WKWebView makes an inbound connection to the FastAPI/Uvicorn service embedded in the same app. The service binds exclusively to the loopback interface `127.0.0.1`, not to the LAN or internet. It starts with the application and terminates when the main window closes or the user chooses Quit; the port is then released. This inbound app-local listener is the functionality that requires the server entitlement.

The separate trusted-LAN Edge Cluster remains disabled at launch and does not discover or contact LAN workers unless the user explicitly enables it. Core DSP, delivery checks, evidence export, reports, Precision Speech Editor, and bundled Faster-Whisper transcription operate locally.

The App Review Notes include:

1. tested physical Mac model and operating system;
2. app purpose, target audience, problem, and value;
3. setup and access instructions with the attached developer-created sample WAV;
4. external services and local/LAN execution boundaries;
5. regional behavior;
6. confirmation that the app is not a regulated service and the sample contains no protected third-party material;
7. a continuous physical-device recording showing launch, typical workflow, native file panels, processing, delivery review, export, local transcription, and application shutdown.

No account, login, purchase, subscription, activation key, special hardware, or external installation is required.

Attachments:

- `AudioEnhancerMAX-3.7.0-build-3.7.2-physical-macOS.mov`
- `AudioEnhancerMAX-review-sample.wav`
- `AudioEnhancerMAX-App-Review-Dossier-3.7.0-build-3.7.2.pdf`

Kind regards,

Fabrizio Degni
