# AudioEnhancerMAX 3.8.2: Mac App Store submission status

16 October 2026. Apple confirmed **Waiting for Review** for version **3.8.2**, internal build **3.8.3**, submitted at **16:52 Europe/Rome**. Source correction merged through PR 8. Approval and Store publication remain pending. The machine-readable receipt is `SUBMISSION_3.8.2_BUILD_3.8.3.json`.

## Earlier internal candidate: build 3.8.2

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

## Corrected build 3.8.3: Apple delivery and runtime verification

Transporter delivered the corrected package on 16 October 2026 at 14:53 Europe/Rome. Apple processing completed successfully. Build 3.8.3 was assigned to the owner-only Release Validation group and installed through TestFlight. The installed version/build, Apple receipt and recursive strict signature checks passed.

On the physical Mac described above, the Apple-distributed build passed:

- Native launch, developer-sample import, Smart Enhance diagnosis and Quick Clean processing.
- Local normalization and WAV/MP3/FLAC exports with matching artifact hashes and output revisions.
- Full local transcription using the bundled Medium model, including native TXT export.
- Precision Speech Editor analysis, selection, undo, redo and rendering, with the original sample preserved.
- Native WAV and Project Capsule saves. All six capsule artifact hashes were verified; the original audio was excluded as selected.
- Processing Report display and privacy settings with external services, Ollama assistance and trusted-LAN processing disabled.
- Quit: the application process exited and its loopback listener released port 8000.

Five current screenshots were captured from this installed build and prepared at 2880 x 1800 pixels. Their provenance and hashes are in `screenshots-3.8.2-build-3.8.3/manifest.json`. The five new filenames are registered in Apple's Asset Library, but upload and association errors prevented confirmation that they replaced the listing's screenshots. Refreshed Store screenshots are not claimed. The continuous physical-Mac recording is published at a verified direct URL for the reviewer: see `REVIEW_RECORDING_3.8.3.md`. After removing the attachment stuck in processing from the draft, the response with this link was sent at 16:44; App Review displayed two messages. These checks cover one device and OS; they do not establish perceptual audio quality or broader hardware compatibility.

## Account and listing

The account holder accepted the required Apple agreement on 15 October. English and Italian metadata, reviewer notes, sample ZIP and loopback listener justification are saved. The privacy label is published as Other User Content used for App Functionality, not linked to identity or tracking. Automatic release after App Review approval is selected.

Build 3.8.3 replaced the historical build 3.5.2 in the App Review item. The version reached Ready for Review, then Resubmit to App Review succeeded. Apple displayed Waiting for Review for both the submission and version, with Date Submitted Oct 16, 2026 at 4:52 PM. Submission ID: `3b6023b7-27da-4ea8-afe5-afe6da2838f4`. The final resubmission used the saved listing; it does not establish approval or publication.

## Remaining steps

1. Await Apple's review decision. Do not report approval or storefront availability before Apple confirms them.
2. Keep the accepted submission intact. Screenshot replacement remains a documented limitation; do not cancel the submission merely to repeat failed asset operations.
3. Report storefront availability only after Apple approval and visible publication.

Prepared copy: `../marketing/APP_STORE_METADATA_v3.8.2.md` and `APP_REVIEW_NOTES_3.8.2_BUILD_3.8.3.md`.
