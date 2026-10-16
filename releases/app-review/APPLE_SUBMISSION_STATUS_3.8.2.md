# AudioEnhancerMAX 3.8.2: Mac App Store submission status

16 October 2026. Current candidate: version **3.8.2**, internal build **3.8.3**. Source correction merged through PR 8.

## Confirmed Apple delivery and installed testing

- Transporter delivered build 3.8.2 on 16 October 2026 at 00:10. App Store Connect processed it and made it ready for internal testing.
- The owner-only `Release Validation` group contains build 3.8.2 and one tester. Automatic distribution remains disabled.
- TestFlight installed the app in `/Applications/AudioEnhancerMAX.app`. Version/build 3.8.2/3.8.2, Apple receipt, bundle identifier and recursive strict signature verification passed.
- On a physical MacBook Pro (Mac15,9), Apple M3 Max, 64 GB RAM, macOS 27.2 (26B5112a), the app opened its native window and passed its readiness check. The native Open panel imported the developer sample.
- With optional external services, local Ollama and trusted-LAN processing disabled, upload, normalization and WAV/MP3/FLAC exports passed exact-format hash and revision checks.
- Transcription failed before inference: the pinned Faster-Whisper VAD constructor rejects the `threshold` argument. Build 3.8.2 must not be submitted as the corrected candidate.

## Corrected candidate

Both normal and streaming transcription now use explicit speech/silence thresholds accepted by Faster-Whisper 1.1.0. Requests is declared explicitly so clean installations can import the runtime. The correction passed 79 Python tests, 8 subtests and 4 JavaScript regressions. Real transcription of the developer sample passed in both paths using the installed app's unmodified bundled Medium model. GitHub PR 8 CI passed before merge.

- Marketing version and build: **3.8.2 / 3.8.3**.
- Bundle identifier: `com.fabriziodegni.audioenhancermax`; team: `BR9VY292BU`.
- Package: `AudioEnhancerMAX-v3.8.2-build-3.8.3-MacAppStore.pkg`.
- Size: 1,533,353,751 bytes.
- SHA-256: `33c442996fc70b56b2a1bf990990c6ce691f6c33d97f4935c5ea8eaff2a49e1a`.
- Package build, recursive application signature verification and installer signature verification passed.
- App Sandbox, selected-file read/write, loopback server and network client entitlements are retained. No security protections were bypassed.
- Build inputs and artifacts remain local outside Desktop/iCloud. The Store package is not a direct-download installer.

The corrected package has not yet been uploaded. Its Apple-distributed runtime, continuous review recording and final App Review submission remain pending. Source/model tests do not establish TestFlight runtime success or perceptual audio quality.

## Account and listing

The account holder accepted the required Apple agreement on 15 October. English and Italian metadata, reviewer notes, sample ZIP and loopback listener justification are saved. The privacy label is published as Other User Content used for App Functionality, not linked to identity or tracking. Automatic release after App Review approval is selected.

The editable Store version is 3.8.2, but the existing rejected submission is historical and still has build 3.5.2 attached. Neither the renamed version nor successful TestFlight delivery constitutes a new App Review submission or approval.

## Remaining steps

1. Upload the signed 3.8.2 (3.8.3) package and confirm successful Apple processing.
2. Assign it to the existing internal group, update through TestFlight, and repeat the full checklist in `RESUBMISSION_CHECKLIST_3.8.2.md`.
3. Capture current screenshots and a continuous physical-Mac recording beginning with launch. Answer Apple's seven existing review questions using actual results and device/OS details.
4. Replace build 3.5.2 with verified build 3.8.3, update review notes and attachments, and resubmit.
5. Report storefront availability only after Apple approval and visible publication.

Prepared copy: `../marketing/APP_STORE_METADATA_v3.8.2.md` and `APP_REVIEW_NOTES_3.8.2_BUILD_3.8.3.md`.
