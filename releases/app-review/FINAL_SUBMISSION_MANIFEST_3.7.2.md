# AudioEnhancerMAX 3.7.0 build 3.7.2 - Final Submission Manifest

Prepared: 15 August 2026

## Transporter upload

- `dist/macos-app-store/AudioEnhancerMAX-v3.7.0-build-3.7.2-MacAppStore.pkg`
  - Purpose: upload only through Transporter/App Store Connect.
  - Size: 1,834,879,192 bytes.
  - SHA-256: `50f45aab9e049ea2c4809e4adb415602788b48a67a1716462c82e329a937bf7c`.
  - Signature: Apple Mac App Store application + installer identities, trusted timestamp `2026-08-15 03:01:18 +0000`.
  - Do not publish this Mac App Store package on SourceForge; direct distribution needs a separate Developer ID signed and notarized artifact.

## App Review Information attachments

- `output/pdf/AudioEnhancerMAX-App-Review-Dossier-3.7.0-build-3.7.2.pdf` - five-page reviewer dossier.
- `releases/app-review/AudioEnhancerMAX-review-sample.wav` - developer-created review sample.
- `AudioEnhancerMAX-3.7.0-build-3.7.2-physical-macOS.mov` - manual continuous physical-Mac recording; create before resubmission using the supplied script.

## Text to paste in App Store Connect

- `releases/app-review/APP_REVIEW_NOTES_3.7.0_BUILD_3.7.2.md` - Review Notes.
- `releases/app-review/RESOLUTION_CENTER_REPLY_3.7.2.md` - response for Guidelines 2.1 and 2.4.5.
- `releases/marketing/APP_STORE_METADATA_v3.7.0.md` - English and Italian listing copy.

## Operator guides

- `releases/app-review/TESTFLIGHT_AND_RESUBMISSION_3.7.2_IT.md` - Transporter, TestFlight, and resubmission procedure.
- `releases/app-review/SCREEN_RECORDING_SCRIPT_3.7.2.md` - uninterrupted physical-device recording script.
- `releases/app-review/RESUBMISSION_CHECKLIST_3.7.2.md` - final checklist.
- `releases/app-review/APPLE_VALIDATION_REPORT_3.7.0_BUILD_3.7.2.md` - signed-payload evidence and remaining Apple-controlled gates.

## Validation status

- PASS - 26 automated tests.
- PASS - signed installer and deeply signed payload.
- PASS - native arm64 launch and `127.0.0.1`-only listener.
- PASS - upload, AutoEQ, normalization, processing report, Delivery Compliance, blind A/B, and Project Capsule from the signed payload.
- PASS - bundled offline Faster-Whisper transcription.
- PASS - native termination released the loopback port.
- MANUAL - Transporter processing, TestFlight installation, physical-Mac recording, build selection, and final App Review submission.

## Public distribution boundary

- Hostinger receives the contents of `web/` or the prepared website ZIP.
- SourceForge may receive source code, release notes, checksums, and public documentation.
- The Mac App Store PKG remains an App Store Connect/Transporter artifact only.
