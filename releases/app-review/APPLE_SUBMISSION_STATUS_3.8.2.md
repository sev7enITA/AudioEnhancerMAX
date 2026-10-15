# AudioEnhancerMAX 3.8.2: Mac App Store submission status

15 October 2026. Application source commit: `d46c48d97022a862d6238359de9ac67f3cc20043`.

## Prepared and verified

- Marketing version and build: 3.8.2 / 3.8.2.
- Bundle identifier: `com.fabriziodegni.audioenhancermax`; team: `BR9VY292BU`.
- Package: `AudioEnhancerMAX-v3.8.2-build-3.8.2-MacAppStore.pkg`.
- Size: 1,533,354,042 bytes.
- SHA-256: `f38e8e081f35a341da3dd3b968e9eccb575ca4cea4abe2fd9ed8ba54b46c5ecf`.
- Mac App Store application and installer identities are valid. Installer signature verification and recursive strict verification of the extracted application passed.
- App Sandbox, selected-file read/write, loopback server and network client entitlements match the explicit application and team identifiers.
- The distribution provisioning profile expires on 16 July 2027. Bundled Faster-Whisper Medium, Silero VAD, media runtime, privacy manifest and component notices are included.
- English and Italian listing text and reviewer notes are prepared. Public release text remains focused on the delivered audio workflow.
- Build inputs and artifacts are local outside Desktop/iCloud. This Store package must not be published as a direct-download installer.

## Account and listing updates

- The account holder accepted the required Apple Developer agreement on 15 October 2026. Safari shows restored Developer resources and an active Free Apps Agreement in App Store Connect.
- Delivery of the exact package was retried through authenticated Transporter. Package analysis succeeded and the upload started. The last observed state is **Uploading to App Store Connect**; delivery and processing are not yet confirmed.
- The editable Store version is now 3.8.2. English and Italian descriptions, promotional text, keywords, and subtitles are saved.
- Reviewer notes, the developer-created review sample ZIP, and the loopback listener justification are saved in App Review Information and App Sandbox Information.
- The privacy label is published as Other User Content used for App Functionality, not linked to identity and not used for tracking, consistent with the bundled privacy manifest and optional text-to-speech disclosure.
- Automatic release after App Review approval is selected.
- TestFlight is installed and authenticated on the physical Mac. The internal `Release Validation` group contains only the account holder; automatic distribution is disabled. TestFlight description, feedback address, marketing URL, and privacy URL are saved.

## Not completed

The upload is still in progress and has variable throughput. No successful delivery, processed 3.8.2 TestFlight build, new review submission, or App Store publication is claimed.

The existing rejected submission is from July and still has build 3.5.2 attached. Changing the editable version label to 3.8.2 does not mean Apple has reviewed or rejected the new candidate. Replace the old build only when the verified 3.8.2 build is available.

Apple's existing correspondence requests a physical-device recording beginning with app launch, the tested device/OS, and details about the app's purpose, access, external services, regional behavior, and relevant regulated or third-party material. The response and recording must describe the actual installed candidate.

Direct execution of the extracted distribution payload was stopped by macOS before application startup because no eligible local provisioning profile was available for this production signature. This is distinct from structural signature verification. Validate the Store-signed runtime through the authorized TestFlight installation; earlier direct-download smoke tests do not substitute for this channel check.

## Remaining steps

1. Confirm successful Transporter delivery and Apple processing of build 3.8.2.
2. Add that build to the owner-only internal group, install it through TestFlight, and perform the physical-Mac checks in `RESUBMISSION_CHECKLIST_3.8.2.md`.
3. Capture current screenshots and the continuous review recording; reply to the seven points in Apple's existing correspondence with verified results.
4. Select build 3.8.2, verify the final metadata and attachments, and resubmit for review.
5. Report storefront availability only after Apple approval and visible publication.

Prepared copy: `releases/marketing/APP_STORE_METADATA_v3.8.2.md` and `releases/app-review/APP_REVIEW_NOTES_3.8.2_BUILD_3.8.2.md`.
