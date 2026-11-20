# AudioEnhancerMAX 4.0 BETA

Clean up audio, compare the original and the revision on the same timeline, and export with a report linked to that revision.

## Mac workspace

- Import and clean, listen and edit, then export from the same workspace. Keep the waveform and transport visible during review. Use command search to reach advanced tools.
- Preview cleanup on a short excerpt. Compare original and revision at the same playback position with optional playback level matching. Export levels remain independent.
- Navigate a local Faster-Whisper transcript to review proposed cuts and mutes. Undo and redo decisions before export. The render maps playback positions across transcript-driven cuts. The source recording is preserved.
- Review the delivery format and checks before export. The processing report documents the revision being delivered.

## Content Credentials and export

- Inspect C2PA manifests locally. With a configured signing identity, export a signed WAV, MP3 or FLAC copy with the SHA-256 of its exact processing report in the manifest.
- Protect a signing key in macOS Keychain and verify an RFC 3161 timestamp before releasing a timestamped copy. When the configured trust list has expired, ordinary export remains available.
- Optionally embed an audio watermark in a WAV or FLAC revision and review it before signing. The watermark writes an identifier into the audio samples. C2PA signs provenance metadata for the export.
- Download samples to compare a signed WAV, an altered copy, the manifest and the report. The sample uses a test signing authority. Verifiers can assess file integrity, signer trust and timestamp trust separately.

## Android and iOS companions

- Choose the media format before import. The app validates the file before replacing the session.
- Review the waveform, trim, compare original and edit, and use playback level matching. The playhead stays aligned after trimming.
- Discover nearby Macs over Wi-Fi or let a Mac invite your discoverable phone. Confirm the same eight-digit code on both devices. QR pairing is also available.
- Send audio to a paired Mac using an encrypted local connection. Track transfer progress and verify the output and its report with SHA-256.
- About shows version, build, developer, support, privacy and license information. The original AudioEnhancerMAX artwork is used throughout the release.

| Package | Availability |
| --- | --- |
| Mac 4.0.0, build 4.0.5 | Signed and notarized direct DMG. Requires Apple Silicon and macOS 13 or later. |
| Android 4.0.0, build 14 | Direct QA APK. Requires Android 8.0 or later. |
| iOS 4.0.0, build 10 | Source and unsigned developer archive. Requires iOS or iPadOS 17 or later and signing for device installation. |

Pairing requires the same reachable local network. Tests covered a real Mac, iOS Simulator and Android Emulator. First-hand pairing on physical phones remains part of BETA validation.

The stable Mac release remains [3.9.0](https://github.com/sev7enITA/AudioEnhancerMAX/releases/tag/v3.9.0). The previous [3.9.1 BETA](https://github.com/sev7enITA/AudioEnhancerMAX/releases/tag/v3.9.1) remains available. Back up the app data folder before switching builds.

[Official website](https://www.fabriziodegni.com/AudioEnhancerMAX/) · [Companion guide](https://www.fabriziodegni.com/AudioEnhancerMAX/companion.html) · [Support](https://www.fabriziodegni.com/AudioEnhancerMAX/support.html) · [Privacy](https://www.fabriziodegni.com/AudioEnhancerMAX/privacy.html)
