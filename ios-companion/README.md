# AudioEnhancerMAX iOS Companion 4.1.1 (13)

Native SwiftUI companion for iOS 17+. This preview is validated with the simulator and an unsigned device archive; it is not a TestFlight or App Store release. Installing on an iPhone requires development signing and provisioning.

## Current features

- Studio imports phone recordings using AVFoundation: M4A/AAC/ALAC, WAV, MP3, FLAC, CAF/AIFF and audio from MP4/MOV. Native codec support remains device-dependent. Mono/stereo, 8–96 kHz; 100 MiB source and 64 MiB decoded PCM limits. Ogg/AMR support is not promised on iOS.
- Select **Import format** before Import. The persisted selection supplies specific UTTypes. There is no generic `.data` fallback. Actual container signatures and video-track presence enforce the selection before replacing the workspace. M4A/AAC accepts audio-only containers, while Video requires video. Files may display disabled items that do not match.
- Studio lets you scrub the waveform, drag the In and Out markers, enter exact times, and loop a selection. Keep a selected range or silence it while preserving the timeline. Apply gain, peak normalization to −1 dBFS, fades, and Voice EQ. Undo or redo edit settings before rendering a WAV revision. A/B review aligns the source and the revision, with optional playback-only level matching. The original and the last rendered revision remain available while you edit.
- MP4 with exactly one H.264 video track and one AAC audio track can retain a private copy. Improve the full duration, prepare an MP4 copy and share it. Audio is re-encoded while video orientation/timing are retained. Full frame count, sample rate and channels must match; trimmed results remain WAV-only. Auxiliary tracks are not exported. New imports/results invalidate prepared video exports.
- In **Connection**, use **Find your Mac** while **Nearby pairing** is open in the Mac app's **Mobile devices and transfers** section. Allow iOS Local Network access, keep both devices on the same Wi-Fi or hotspot, and confirm the same eight-digit code on both devices. QR and manual pairing are also available. Pinned TLS protects transfer. The screen displays the destination, input identity, upload, processing, verification and result. The app checks source and output hashes reported by the 4.0 bridge. The Mac transfer limit is 20 MiB WAV. A single pairing also supports optional foreground Voice EQ contribution.
- To begin from the Mac, choose **Let your Mac find this device** on the phone, search for nearby phones in the Mac app, and send an invitation. Accept the invitation on the phone and compare the eight digits on both devices. Visibility ends when the sheet closes, the app goes into the background, or the 90-second window expires.
- The **Mac acceleration** card shows accepted chunks, audio seconds, last Voice EQ compute time, and the measured local DSP rate. The rate compares audio duration to compute time. Round-trip latency is displayed in the connection card. Foreground contribution runs Voice EQ (`auto_eq`), up to 2 MiB per chunk. Backgrounding, heat, editing, transfer, or an explicit stop can pause contribution.
- **Content Credentials** checks an original WAV, MP3, FLAC, M4A, MP4 or MOV file on the phone. The offline reader reports embedded manifest integrity, signer trust and timestamp trust individually. AudioEnhancerMAX processing-report fingerprints are displayed when present.
- **Music brief** offers five editable starting points, duration matching from the active recording, structured preview, copy, TXT/JSON sharing, JSON import and separate lyrics.
- **Verify Content** opens WAV, MP3, FLAC, M4A, MP4 and MOV from Files. The app is also registered as an alternate viewer for these formats so users can open a selected file from another app. Verification takes a temporary private snapshot up to 500 MiB and uses the same bytes for SHA-256, byte count, C2PA and audio measurements.
- The verifier lists the signer, issuer and action declarations bound to a validated manifest. It reports signer trust and RFC 3161 timestamp trust independently. Audio measurements use the first audio track for up to 30 seconds at the native rate and channels, at most stereo and 96 kHz. Sample peak and RMS are in dBFS. Near-full-scale percentage uses a 0.999 amplitude threshold. Silence has no finite dBFS value.
- **Export JSON report** shares `audioenhancermax.media-verification.v1` with the asset fingerprint, credential verdict and audio measurements. The report excludes source paths and file contents. The snapshot is removed on completion or cancellation.
- **About** shows the installed version and build, the BETA channel, the developer and links to support, privacy, source code and the MIT license.

## Updates and distribution

Open **About → Updates** in the developer build. Choose GitHub or SourceForge, then check the signed release feed. The app remembers your choice. Download the unsigned Xcode archive and share it with your Mac after the size and SHA-256 pass validation. Xcode handles signing and deployment to registered devices.

Use the `AudioEnhancerCompanionStore` scheme to archive the `Store` configuration for Apple's distribution channel. Its Updates screen uses App Store updates. Set `AEMAX_IOS_APP_STORE_ID` only to the verified iOS companion listing ID to enable its direct listing link. The App Store scheme excludes the repository downloader at compile time. Development IPA files are limited to their provisioned devices.

Pairing lives in Keychain with ThisDeviceOnly protection. Restarting the Mac session requires a new pairing. Local files persist in the app until replaced or removed. No audio upload is implicit.

## Build and verify

```sh
xcodegen generate --spec ios-companion/project.yml
xcodebuild -project ios-companion/AudioEnhancerCompanion.xcodeproj -scheme AudioEnhancerCompanion -destination 'platform=iOS Simulator,id=YOUR_SIMULATOR_ID' test
```

Simulator builds use ad-hoc signing for Keychain. The project is generated from `project.yml`; regenerate after adding files. Core/native-media tests cover signatures, selected filters, original preservation, stereo DSP, waveform tail coverage, MP3/AAC/FLAC/ALAC/CAF/AIFF/PCM24 import and video replacement/timing. Live Mac integration tests use private session fixtures in an isolated test checkout. Keep those fixtures outside version control. Verify on physical phones and hotspots before distribution.

Test Files and the cloud document providers used by your audience on a physical iPhone, including picker rejection and Mac handoff over Wi-Fi or hotspot.
