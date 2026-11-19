# AudioEnhancerMAX iOS Companion 4.0.0 (8)

Native SwiftUI companion for iOS 17+. This preview is validated with the simulator and an unsigned device archive; it is not a TestFlight or App Store release. Installing on an iPhone requires development signing and provisioning.

## Current features

- Studio imports phone recordings using AVFoundation: M4A/AAC/ALAC, WAV, MP3, FLAC, CAF/AIFF and audio from MP4/MOV. Native codec support remains device-dependent. Mono/stereo, 8–96 kHz; 100 MiB source and 64 MiB decoded PCM limits. Ogg/AMR support is not promised on iOS.
- Select **Import format** before Import. The persisted selection supplies specific UTTypes. There is no generic `.data` fallback. Actual container signatures and video-track presence enforce the selection before replacing the workspace. M4A/AAC accepts audio-only containers, while Video requires video. Files may display disabled items that do not match.
- Trim, gain, fixed Voice EQ, peak normalization to −1 dBFS and WAV sharing. A/B uses one source playhead across the original and trimmed result. Optional listening level matching only attenuates the louder side during playback. The export keeps the applied gain. The app preserves the original and binds restored results to their source and result fingerprints. Cached waveform peaks cover the final frame of short recordings.
- MP4 with exactly one H.264 video track and one AAC audio track can retain a private copy. Improve the full duration, prepare an MP4 copy and share it. Audio is re-encoded while video orientation/timing are retained. Full frame count, sample rate and channels must match; trimmed results remain WAV-only. Auxiliary tracks are not exported. New imports/results invalidate prepared video exports.
- In **Connection**, use **Find your Mac** while **Nearby pairing** is open in the Mac app's **Mobile devices and transfers** section. Allow iOS Local Network access, keep both devices on the same Wi-Fi or hotspot, and confirm the same eight-digit code on both devices. QR and manual pairing are also available. Pinned TLS protects transfer. The screen displays the destination, input identity, upload, processing, verification and result. The app checks source and output hashes reported by the 4.0 bridge. The Mac transfer limit is 20 MiB WAV. A single pairing also supports optional foreground Voice EQ contribution.
- Foreground worker advertises only portable `auto_eq`, up to 2 MiB per chunk. It stops on backgrounding, heat, editing, upload or explicit stop. No continuous background worker is claimed.
- Music brief stores editable text/JSON and separate lyrics; it does not generate audio.

Pairing lives in Keychain with ThisDeviceOnly protection. Restarting the Mac session requires a new pairing. Local files persist in the app until replaced or removed. No audio upload is implicit.

## Build and verify

```sh
xcodegen generate --spec ios-companion/project.yml
xcodebuild -project ios-companion/AudioEnhancerCompanion.xcodeproj -scheme AudioEnhancerCompanion -destination 'platform=iOS Simulator,id=YOUR_SIMULATOR_ID' test
```

Simulator builds use ad-hoc signing for Keychain. The project is generated from `project.yml`; regenerate after adding files. Core/native-media tests cover signatures, selected filters, original preservation, stereo DSP, waveform tail coverage, MP3/AAC/FLAC/ALAC/CAF/AIFF/PCM24 import and video replacement/timing. Live Mac integration tests use private session fixtures in an isolated test checkout. Keep those fixtures outside version control. Verify on physical phones and hotspots before distribution.

Test Files and the cloud document providers used by your audience on a physical iPhone, including picker rejection and Mac handoff over Wi-Fi or hotspot.
