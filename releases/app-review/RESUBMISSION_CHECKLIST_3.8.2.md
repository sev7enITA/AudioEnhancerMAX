# AudioEnhancerMAX 3.8.2: Store verification checklist

Use `APPLE_SUBMISSION_STATUS_3.8.2.md` for observed delivery and submission status. This checklist describes the verification required before resubmitting the existing Mac App Store application.

## Delivery identity

- Version/build: `3.8.2` / `3.8.2`.
- App Store Connect ID: `6791591803`.
- Bundle: `com.fabriziodegni.audioenhancermax`.
- Package SHA-256: `f38e8e081f35a341da3dd3b968e9eccb575ca4cea4abe2fd9ed8ba54b46c5ecf`.
- Confirm Transporter delivery, successful Apple processing, and the installed TestFlight build independently.
- Use the account holder's internal `Release Validation` group. Automatic distribution is disabled.

## Physical Mac verification

1. Install through TestFlight and confirm version/build and Apple distribution receipt. Do not use the extracted production-signed payload as a substitute.
2. Launch the app-owned window, open About, and record the actual Mac model and operating-system build.
3. Disable optional external services, local Ollama assistance, and trusted-LAN processing in the app for the local workflow test.
4. Select the developer-created review WAV through the native Open panel. Run Smart Enhance or a deterministic profile and inspect the completed output revision.
5. Check WAV, MP3, and FLAC exports against the exact-format Delivery Compliance SHA-256. Verify that reports remain attached to the same completed revision.
6. Export a Project Capsule with original audio excluded. Verify the included artifact hashes and preservation of the input sample.
7. Exercise Precision Speech Editor decisions, undo/redo, and rendering. Confirm bundled transcription produces a transcript locally. Functional checks do not establish transcription accuracy or perceived audio quality.
8. Verify native Save panels, Quit, process termination, and loopback port release.

## Review evidence and metadata

- Capture a continuous recording on the physical Mac, beginning with launch and showing the core workflow. Describe the actual device/OS; do not claim broader testing.
- Capture current screenshots from the installed candidate. Apple's Mac screenshot sizes are 1280 x 800, 1440 x 900, 2560 x 1600, or 2880 x 1800 pixels.
- Use the English and Italian copy from `../marketing/APP_STORE_METADATA_v3.8.2.md` and the matching reviewer notes.
- Attach the review ZIP containing `AudioEnhancerMAX-review-sample.wav`.
- Keep the privacy label consistent with the bundled manifest and disclosed optional text-to-speech service: Other User Content, App Functionality, not linked to identity, not used for tracking.
- Explain the inbound loopback listener in both App Sandbox Information and the response to App Review.
- Answer the seven points in Apple's existing correspondence: recording, tested device/OS, purpose/audience, access/workflow, external services, regional behavior, regulated services/third-party material.
- Replace the previous build `3.5.2` with verified `3.8.2`. The existing rejected submission is historical; renaming the version does not constitute a new review outcome.
- Confirm the intended automatic release after approval, submit, and save the terminal App Store Connect state.
- App Store publication can only be reported after Apple approval and visible storefront availability.

References: [Apple screenshot specifications](https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications), [TestFlight](https://developer.apple.com/testflight/), [App privacy details](https://developer.apple.com/app-store/app-privacy-details/).
