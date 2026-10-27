# AudioEnhancerMAX for macOS

The current stable direct-download release is **3.9.0, build 3.9.2**, for Apple Silicon and macOS 13 or later. [Release notes](../releases/RELEASE_NOTES_v3.9.0.md) · [Package verification](../releases/DIRECT_BUILD_3.9.2.md).

## Install and upgrade

Download the DMG and its SHA-256 sidecar from the [official release](https://github.com/sev7enITA/AudioEnhancerMAX/releases/tag/v3.9.0) or [SourceForge mirror](https://sourceforge.net/projects/audioenhancermax/files/v3.9.0/). Open the disk image and drag AudioEnhancerMAX to Applications. Quit an existing stable instance before replacing the app. Open the installed app normally; do not disable Gatekeeper.

The stable app preserves `~/Library/Application Support/AudioEnhancerMAX`. Back up that folder before a downgrade if you want a complete rollback point. The previous [3.8.3 release](https://github.com/sev7enITA/AudioEnhancerMAX/releases/tag/v3.8.3) remains available. Experimental 1 has a separate app name, bundle identity and data folder. It can remain installed alongside stable; there is no automatic migration from Experimental.

The application starts a loopback-only FastAPI service and renders its interface in an AppKit/WKWebView window. Closing the main window or quitting stops its service.

## First-launch readiness

The local readiness screen checks the operating system and architecture, available memory and disk, writable app storage, packaged Python/DSP modules and codecs. Optional integrations are reported separately. Setup creates private data directories and records the result for the current version. It does not install third-party software or transmit diagnostics. Missing mandatory components block startup with an actionable error.

## Data and privacy

- The desktop server binds to `127.0.0.1`.
- Stable uploads, outputs, presets, preferences and launcher state live in `~/Library/Application Support/AudioEnhancerMAX`.
- Launcher logs live in `~/Library/Logs/AudioEnhancerMAX/launcher.log`.
- Processing creates new outputs and preserves imported originals.
- Music brief drafts remain in the current session. Copy or export JSON before quitting; JSON re-import is not supported.
- Optional external or LAN services require the relevant permission and explicit workflow selection.

## Included and optional components

The DMG includes Python, the local interface, DSP libraries, PyAV with bundled FFmpeg codec libraries, and the Faster-Whisper runtime. Core compressed-media import/export does not require an external FFmpeg executable or Homebrew.

Transcription models are downloaded on first use unless already cached; subsequent inference is local. Models and user recordings are not embedded in the app. Local Music brief construction does not need a model or network. Optional editorial suggestions require a separately installed local Ollama model and explicit permission. Music brief prepares text only; it does not generate music or call MiniMax.

Kokoro, Demucs, DeepFilterNet and MakeMyVoice have separate runtime/model requirements. Their source integrations do not mean those engines are bundled in this DMG. Edge Neural TTS sends entered text to Microsoft when that service is selected. Trusted LAN processing is optional. See [privacy guidance](../web/privacy.html).

This release is direct distribution. A separate App Store workflow exists; this package and its checks do not establish Store approval.

## Reproduce the direct build

Use an arm64 Python 3.11 environment whose macOS deployment target is no newer than 13, the pinned requirements in `packaging/macos`, and a valid Developer ID Application signing identity with its private key.

```bash
AEMAX_PYTHON="/absolute/path/to/venv/bin/python" \
AEMAX_NOTARY_PROFILE="AudioEnhancerMAX-notary" \
./scripts/build_macos_app.sh
```

The notary profile must already be stored in macOS Keychain. The script signs nested code and the app with hardened runtime, signs the DMG, submits it to Apple, waits for acceptance, staples and validates the ticket, checks Gatekeeper and then writes the final SHA-256 sidecar. Without the profile, the artifact is signed but not notarized and must not be described as notarized.

Default outputs are `dist/macos/AudioEnhancerMAX-v3.9.0-build-3.9.2-macOS-arm64.dmg` and its `.sha256` file. The unpackaged `.app` is an intermediate artifact; validate the signed app inside the final disk image.
