# AudioEnhancerMAX 4.1 BETA

Verify a received media file on Mac, iOS or Android. The workspace brings together its SHA-256 fingerprint, offline C2PA verification and bounded audio measurements. Export a JSON summary to attach to a review.

- **Verify content** reads WAV, MP3, FLAC, M4A, MP4 and MOV. It reports whether the local validator established integrity and signer trust. A remote C2PA reference stays unresolved during offline verification.
- **Audio measurements** report the sampling scope and include peak and RMS levels where the selected file has supported audio. The Mac adds a preview of the waveform. Measures vary with the decoder and preview method, which the report records.
- **Companion Studio** includes waveform-based editing, trim, mute, fades, gain, normalization, Voice EQ, undo and redo, A/B listening and Music brief. The paired Mac connection shows observed worker statistics. Mobile use on the phone can be independent of the Mac.
- **Mac AudioSeal** can optionally measure the AudioSeal 16-bit signal using a separately installed and verified detector. This experimental measurement covers at most the first 10 seconds of the first audio track and has no automatic verdict. [Detector setup and measurement method](https://github.com/sev7enITA/AudioEnhancerMAX/blob/v4.1.0-beta.1/docs/media-verification.md#optional-audioseal-detector-on-mac).

The JSON summary identifies the received bytes and records local checks. It is unsigned. Sharing it can reveal the file fingerprint, verification time and signer details. C2PA addresses supported provenance and package integrity. Audio measurements and AudioSeal signals support a review of the media. Judgments about its origin and content require additional evidence.

## Packages

| Platform | Version | Distribution |
|---|---:|---|
| Apple Silicon Mac, macOS 13+ | 4.1.0 (4.1.0) | Developer ID-signed DMG with Apple notarization and a stapled ticket |
| Android 8+ | 4.1.0 (16) | Signed APK for direct BETA testing. C2PA requires Android 9 or newer. |
| iOS 17+ | 4.1.0 (12) | Unsigned developer archive plus source. Installation on a device requires an eligible Apple signing identity and provisioned device. |

Apple and Google mobile store availability and physical phone testing are pending. The public C2PA examples use a test certificate. The prior stable release is still available separately.

[Site and downloads](https://www.fabriziodegni.com/AudioEnhancerMAX/download.html#beta-4-1-0) · [Verification examples](https://www.fabriziodegni.com/AudioEnhancerMAX/#verify-content-4-1-0) · [Release assets](https://github.com/sev7enITA/AudioEnhancerMAX/releases/tag/v4.1.0-beta.1)
