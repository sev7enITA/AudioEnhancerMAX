# AudioEnhancerMAX Android Companion 4.1.2 (19)

Native Compose companion, Android 8/API 26 or later, target API 35 for direct QA packages. The direct QA APK is built in release mode and uses the existing QA signing key. The package ID is `com.audioenhancermax.worker`.

## Current features

- Studio imports WAV PCM16/24/32 or float32, MP3, M4A/AAC, FLAC, Ogg/Opus, AMR and MP4/MOV/3GP using codecs installed on the device. Exact codec support varies by device. One audio track, mono/stereo, 8–96 kHz; 100 MiB source and 64 MiB decoded PCM limits.
- Choose a format filter before import or select **Browse media** for a broader picker. The selection persists and supplies MIME hints to the Android document provider. Studio checks file signatures and audio/video tracks after selection. **Import compatibility** explains limits for each container, including device-dependent decoding.
- Studio puts a zoomable waveform, playback and A/B comparison above the edit controls. Set exact In and Out points, loop the selection, keep or silence that range, and render gain, fades, peak normalization or Voice EQ to WAV. Undo and redo recent rendered revisions. The source stays available for comparison. Playback level matching leaves exported levels intact.
- Eligible H.264/AAC video can retain a private copy. Improve the full duration, then prepare and export an MP4 copy. Audio is re-encoded as AAC; video and rotation pass through. Exactly matched frame count, rate and channels are required. Auxiliary tracks are not exported. Unsuitable video timelines still permit audio-only editing. New imports/results invalidate prepared video exports.
- In **Connection → Find nearby Macs**, select the Mac and compare the eight-digit number displayed on both screens. Confirm on the phone and then approve on the Mac. Pairing pins the Mac TLS certificate. QR and manual private pairing remain available. On Mac open **Edge Cluster → Mobile devices & connections**. Use the same Wi-Fi or a hotspot that allows devices to communicate. A single pairing covers Mac audio transfer and optional foreground Voice EQ contribution.
- **Make this phone discoverable** lets the Mac find the phone and invite it. Choose the invitation to compare the same eight-digit number. Opening this mode publishes a temporary phone name and request ID on the local network. It ends when you leave Connection, tap Stop, accept an invitation, or wait 90 seconds.
- Before sending, the app shows the destination and source or result fingerprint. Mac transfer is limited to 20 MiB decoded WAV. The app shows upload, processing, verification and completion. Completed audio and report are associated using SHA-256. Device information, Voice EQ benchmark and round-trip latency are available.
- The worker only accepts `auto_eq`, at most 2 MiB per chunk. It stops on backgrounding, heat, local editing, upload or explicit stop; the Mac can fall back locally. No phone HTTP server, continuous background processing or second pairing is required.
- **Verify Content** opens WAV, MP3, FLAC, M4A, MP4 or MOV from Files or from a single Android share with read access. It computes the size and SHA-256 of the original bytes, checks embedded C2PA on Android 9 or later, and reports certificate issuer, signer and timestamp trust, validated actions and linked processing report hashes. A hash-only reader mismatch stays inconclusive. The temporary copy is removed after checking.
- **Media metadata** shows available technical container/track facts offline. ADTS AAC, Ogg, AMR and 3GP can also be checked for metadata and audio measurements when Android reads their tracks. Stored text tags, selected Broadcast WAV fields and JPEG cover EXIF are revealed on request. JPEG cover EXIF is checked in media files up to 12 MiB and cover images up to 2 MiB when exposed by Android. Location and device identifiers are omitted. Shared JSON includes technical metadata only from this section.
- Verification accepts files up to 100 MiB. Large media may exceed the device’s C2PA reader budget while the original byte digest remains available. Audio measurements describe peak, RMS and near-full-scale samples in up to the first 30 decoded seconds. Choose **Share JSON report** to export the versioned local report.
- **Music brief** offers five editable starting points, duration matching from the active recording, structured preview, copy, TXT/JSON sharing, JSON import and separate lyrics.
- The connection dashboard reports accepted Voice EQ chunks, audio seconds, compute time, measured local throughput and the Mac round-trip time. Counters update after the Mac accepts each chunk.
- **About** shows the installed version and build, developer, project site, support, privacy policy and project licence.
- **What's new** opens the first time an installed build launches and can be reopened from **About**. The overview links to the companion guide and support.
- **About → Updates** hands marketplace installations back to their store. A direct installation remembers the selected GitHub or SourceForge repository because the same APK can come from either. Check the signed feed, then download from the selected source. The app verifies the package size, SHA-256, package ID, newer build and signing certificate. Save the verified APK through Android Files and open it there when you are ready to install.

Credentials use Android Keystore AES-GCM, backups are disabled, redirects/cleartext are disabled. Stopping/restarting the Mac session requires a new pairing. No audio is sent until explicitly requested.

## Build and verify

Use JDK 17 or 21 with the installed Android SDK (JDK 25 is incompatible with this Gradle/Kotlin combination).

```sh
./gradlew :app:testDebugUnitTest :app:assembleDebug :app:lintDebug :app:assembleDebugAndroidTest
./gradlew connectedDebugAndroidTest
```

The custom native instrumentation runner checks codecs, MIME intent extras, selected-format rejection, video replacement and preservation of original fixtures. JVM tests cover content signatures, PCM limits, stereo DSP, waveform tail coverage, pairing and text briefs. The optional Mac integration test skips without an isolated QA pairing fixture. Never commit session credentials.

The debug APK is written to `app/build/outputs/apk/debug/app-debug.apk`. Before distributing an artifact, verify its compiled manifest, signing identity and SHA-256. Validate file providers, hotspot pairing and playback on physical devices before promoting the preview.

For a Google Play submission, run `./gradlew -Paemax.playStoreOnly=true :app:bundleRelease` and sign the Android App Bundle with the Play Console upload key. This setting targets API 36 and locks the app to the official Google Play listing regardless of installer attribution. It leaves the direct repository chooser and downloader unavailable. Review the current [target API requirements](https://support.google.com/googleplay/android-developer/answer/11926878).

The launcher and About artwork are rendered from [the original vector](../packaging/macos/AudioEnhancerMAX.svg). The adaptive foreground is centred within the Android masking safe area. [The Google Play listing artwork](branding/google-play-icon.png) is a separate 512 × 512 PNG with transparent margins.
