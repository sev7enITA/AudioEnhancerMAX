# AudioEnhancerMAX Android Companion 4.0.0 (13)

Native Compose companion, Android 8/API 26 or later, target API 35. This is a local debug preview, not a Google Play release. Package ID remains `com.audioenhancermax.worker`; install updates with the same debug signing key.

## Current features

- Studio imports WAV PCM16/24/32 or float32, MP3, M4A/AAC, FLAC, Ogg/Opus, AMR and MP4/MOV/3GP using codecs installed on the device. Exact codec support varies by device. One audio track, mono/stereo, 8–96 kHz; 100 MiB source and 64 MiB decoded PCM limits.
- Choose **Format** before Import. The selection persists and launches only that format's MIME hints. Content signatures and actual video-track presence enforce the selection if a provider ignores those hints. M4A/AAC is audio-only; Video requires a video track. Other files may remain visible but disabled in a document provider. All supported is available for providers with inaccurate MIME metadata; decoder validation still applies.
- Trim, gain, fixed Voice EQ, peak normalization to −1 dBFS and WAV sharing. The Studio puts the waveform and Listen controls before cleanup. A/B keeps the source playhead on the same passage after a trim. Optional listening level matching only attenuates the louder side during playback. The export keeps the applied gain. The original document and last workspace are preserved. Waveform peaks are cached during import and cover the final frame, including very short clips.
- Eligible H.264/AAC video can retain a private copy. Improve the full duration, then prepare and export an MP4 copy. Audio is re-encoded as AAC; video and rotation pass through. Exactly matched frame count, rate and channels are required. Auxiliary tracks are not exported. Unsuitable video timelines still permit audio-only editing. New imports/results invalidate prepared video exports.
- In **Connection → Find nearby Macs**, select the Mac and compare the eight-digit number displayed on both screens. Confirm on the phone and then approve on the Mac. Pairing pins the Mac TLS certificate. QR and manual private pairing remain available. On Mac open **Edge Cluster → Mobile devices & connections**. Use the same Wi-Fi or a hotspot that allows devices to communicate. A single pairing covers Mac audio transfer and optional foreground Voice EQ contribution.
- **Make this phone discoverable** lets the Mac find the phone and invite it. Choose the invitation to compare the same eight-digit number. Opening this mode publishes a temporary phone name and request ID on the local network. It ends when you leave Connection, tap Stop, accept an invitation, or wait 90 seconds.
- Before sending, the app shows the destination and source or result fingerprint. Mac transfer is limited to 20 MiB decoded WAV. The app shows upload, processing, verification and completion. Completed audio and report are associated using SHA-256. Device information, Voice EQ benchmark and round-trip latency are available.
- The worker only accepts `auto_eq`, at most 2 MiB per chunk. It stops on backgrounding, heat, local editing, upload or explicit stop; the Mac can fall back locally. No phone HTTP server, continuous background processing or second pairing is required.
- Music brief builds persistent editable text/JSON with separate lyrics. It does not generate music.

Credentials use Android Keystore AES-GCM, backups are disabled, redirects/cleartext are disabled. Stopping/restarting the Mac session requires a new pairing. No audio is sent until explicitly requested.

## Build and verify

Use JDK 17 or 21 with the installed Android SDK (JDK 25 is incompatible with this Gradle/Kotlin combination).

```sh
./gradlew :app:testDebugUnitTest :app:assembleDebug :app:lintDebug :app:assembleDebugAndroidTest
./gradlew connectedDebugAndroidTest
```

The custom native instrumentation runner checks codecs, MIME intent extras, selected-format rejection, video replacement and preservation of original fixtures. JVM tests cover content signatures, PCM limits, stereo DSP, waveform tail coverage, pairing and text briefs. The optional Mac integration test skips without an isolated QA pairing fixture. Never commit session credentials.

The debug APK is written to `app/build/outputs/apk/debug/app-debug.apk`. Before distributing an artifact, verify its compiled manifest, signing identity and SHA-256. Validate file providers, hotspot pairing and playback on physical devices before promoting the preview.
