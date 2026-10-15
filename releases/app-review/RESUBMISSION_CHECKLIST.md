# Mac App Store Resubmission Checklist

## Build and metadata

- [x] Marketing version is 3.7.0.
- [x] Build number is 3.7.1 and is higher than the rejected build.
- [x] Bundle identifier is `com.fabriziodegni.audioenhancermax`.
- [x] Minimum system version is macOS 13.0.
- [x] Architecture is arm64; App Store metadata must clearly state Apple silicon Mac support.
- [x] Main-app entitlements are App Sandbox, user-selected file read/write, network client, and network server.
- [x] The interface opens in a native AppKit/WKWebView window and does not launch the default browser.
- [x] The application menu is labeled AudioEnhancerMAX, not Python.
- [x] About AudioEnhancerMAX is app-owned and shows product, build, author, privacy, support, requirements, architecture, license, and official resources.
- [x] Closing the main window stops the app-owned loopback service and releases its port.
- [x] The installer is signed with Mac App Distribution/Installer identities and a trusted Apple timestamp.
- [x] The packaged model, VAD asset, privacy manifest, and third-party notices are present.
- [ ] Upload build 3.7.1 through Transporter and wait for processing to complete.
- [ ] In TestFlight, add build 3.7.1 to an Internal Testing group and install it on the physical Mac.
- [ ] Select build 3.7.1 in the macOS 3.7.0 version record after validation.

## Guideline 2.1 evidence requested by Apple

- [ ] Record the complete workflow on a physical Apple silicon Mac running the latest public macOS release available on the recording date.
- [ ] Attach the unedited `.mov` under App Review Information.
- [ ] Attach `AudioEnhancerMAX-review-sample.wav`.
- [ ] Paste the content of `APP_REVIEW_NOTES_3.7.0_BUILD_3.7.1.md` into Review Notes.
- [ ] Attach the PDF validation dossier.
- [ ] Confirm the tested Mac model and exact OS build number in Review Notes after recording.

## App Store Connect consistency

- [ ] State that no account, demo login, payment, or special hardware is required.
- [ ] State that the core DSP/export/transcription workflow works offline.
- [ ] Disclose optional Microsoft Edge Neural TTS and that user-entered text is sent only when synthesis is requested.
- [ ] Disclose optional local Ollama and optional user-enabled LAN Edge Cluster.
- [ ] Confirm the App Privacy questionnaire matches the actual data flow, especially user content used for optional TTS app functionality.
- [ ] Ensure screenshots and description do not advertise Demucs music separation, Kokoro voice cloning, or another feature excluded from the App Store build.
- [ ] Ensure support and privacy-policy URLs are live in every storefront.
- [ ] In Resolution Center, explicitly reference Guideline 2.1 and 2.4.5 and explain the loopback server entitlement.

## Final release gate

Do not resubmit until every unchecked item above is complete. The TestFlight upload and Apple's requested physical-device video on the latest public macOS release are the remaining manual gates.
