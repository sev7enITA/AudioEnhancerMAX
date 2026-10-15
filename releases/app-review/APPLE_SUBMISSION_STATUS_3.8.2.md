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

## Not completed

Transporter identified the correct app, version and build. Delivery was attempted and rejected by Apple with HTTP 403: required contracts are missing. The package has not been delivered to App Store Connect. No review submission, TestFlight availability or App Store publication is claimed.

Direct execution of the extracted distribution payload was stopped by macOS before application startup because no eligible local provisioning profile was available for this production signature. This is distinct from structural signature verification. Validate the Store-signed runtime through an authorized TestFlight installation after delivery is unblocked; do not treat the earlier direct-download smoke tests as a substitute for that channel check.

## Next steps after account access is restored

1. The account holder must resolve Apple's required agreement status.
2. Retry delivery of the exact package and confirm successful processing in App Store Connect.
3. Review the existing App Review correspondence and validate the delivered build through TestFlight.
4. Apply the prepared listing and review notes, supply requested evidence, select the verified build and submit it for review.
5. Claim storefront availability only after Apple approval and visible publication.

Prepared copy: `releases/marketing/APP_STORE_METADATA_v3.8.2.md` and `releases/app-review/APP_REVIEW_NOTES_3.8.2_BUILD_3.8.2.md`.
