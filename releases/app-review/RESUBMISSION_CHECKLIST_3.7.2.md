# Final Resubmission Checklist — AudioEnhancerMAX 3.7.0 build 3.7.2

## Automated and signed-artifact gates

- [ ] All focused automated tests pass.
- [ ] Frontend desktop/mobile independent review passes.
- [ ] PKG and extracted app signatures pass strict verification.
- [ ] Version is 3.7.0, build is 3.7.2, bundle ID is `com.fabriziodegni.audioenhancermax`, architecture is arm64.
- [ ] Sandbox, user-selected read/write, network client, and justified network server entitlements match the signed app.
- [ ] Privacy manifest, licenses, bundled Faster-Whisper Medium, and Silero VAD are present.
- [ ] Native launch, About identity, 127.0.0.1 listener, native Quit, and port release pass.
- [ ] Review WAV upload, processing, compliance, blind A/B, Project Capsule, report, WAV/MP3/FLAC, and local transcription pass from the signed payload.
- [ ] PKG SHA-256 and sample SHA-256 match the final dossier and validation report.

## Apple-controlled/manual gates

- [ ] Upload build 3.7.2 using Transporter; wait for **Complete** and resolve every warning.
- [ ] Complete export-compliance questions if requested.
- [ ] Add build 3.7.2 to Internal Testing and reinstall through TestFlight on the physical Mac.
- [ ] Repeat the complete workflow from the TestFlight install.
- [ ] Record one continuous 3–5 minute video on the latest public macOS available that day; show exact version/build and hide the serial number.
- [ ] Capture all App Store screenshots from the same TestFlight build.
- [ ] Select build 3.7.2 in the macOS 3.7.0 version record.
- [ ] Paste the prepared Review Notes and attach video, review WAV, and dossier PDF.
- [ ] App purpose, target audience, access, external services, regional behavior, regulated-industry status, and third-party-material status are all answered.
- [ ] Reply to Guidelines 2.1 and 2.4.5 with the loopback-listener explanation.
- [ ] Do not claim App Store availability until Apple approval and storefront publication are live.
