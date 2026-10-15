# Current 3.8.2 direct preview

The new Developer ID DMG is awaiting Apple notarization because the team must accept an updated agreement (HTTP 403 on 15 October 2026). The notarized 3.7.0 remains the stable Mac download. The 3.8 source and build scripts require Python 3.11+. Direct builds use optional/runtime-managed transcription models; App Store builds have a separate bundled-model workflow. No new App Store approval is claimed.

# AudioEnhancerMAX for macOS

AudioEnhancerMAX v3.7.0 provides an Apple Silicon desktop package. Current App Store candidate builds start a loopback-only FastAPI service and render the local interface in an app-owned AppKit/WKWebView window. They do not open the default browser. Closing the main window or quitting the app stops the service.

## First-launch readiness

The desktop interface performs a local readiness check before enabling the workspace. The user does not enter commands or dependency paths. The check covers:

- supported macOS version and Apple Silicon architecture;
- memory and free disk capacity;
- writable private application storage;
- packaged Python and DSP modules;
- media codecs;
- optional Metal acceleration and local Ollama/Gemma availability.

The setup action creates only the app's private data directories and records the result for the current version. It does not transmit diagnostics, request administrator privileges, invoke a package manager, or install third-party software. A missing mandatory component is treated as an incomplete distribution package and blocks startup.

## Privacy and data locations

- The server binds to `127.0.0.1`; it is not exposed to the LAN.
- Uploads, outputs, presets, timing history, roadmap votes, and launcher state are stored in `~/Library/Application Support/AudioEnhancerMAX`.
- Launcher logs are stored in `~/Library/Logs/AudioEnhancerMAX/launcher.log`.
- Local-network access is used only for trusted edge workers that the user elects to connect.

## Included and external components

The `.app` includes the Python runtime, backend, browser frontend, and installed processing libraries. It does not embed user recordings, generated outputs, model caches, Ollama, or Ollama models. Model-backed features can download model weights on first use, depending on the selected engine. Edge Neural TTS is network-dependent. Ollama-assisted features require a separate local Ollama installation and compatible model.

Compressed formats that rely on FFmpeg require FFmpeg to be installed separately. WAV and formats handled directly by libsndfile do not require FFmpeg.

Direct-download DMGs retain these documented external boundaries and must not be represented as the Mac App Store package. The App Store build sets `AEMAX_APP_STORE=1`; in that mode the readiness check requires FFmpeg and FFprobe inside the signed app bundle and rejects fallback to Homebrew or another system installation.

Model assets require the same treatment before App Store submission: a feature may use a bundled model or an explicitly disclosed resource download, but it must not silently obtain executable code. Ollama integration remains optional and cannot be a prerequisite for the core audio workflow.

## Build locally

```bash
./scripts/build_macos_app.sh
```

The build produces a DMG containing the signed application and keeps the unpackaged `.app` as an intermediate build artifact:

- `dist/macos/AudioEnhancerMAX.app`
- `dist/macos/AudioEnhancerMAX-v3.7.0-macOS-arm64.dmg`
- a SHA-256 checksum alongside the DMG

The direct-distribution build requires an installed `Developer ID Application` identity with its private key. It signs every nested Mach-O component and the application with hardened runtime and a secure timestamp, then signs the DMG.

For a public, notarized build, first store Apple notarization credentials in the macOS Keychain with `notarytool`, then run:

```bash
AEMAX_NOTARY_PROFILE="AudioEnhancerMAX-notary" ./scripts/build_macos_app.sh
```

When `AEMAX_NOTARY_PROFILE` is set, the script submits the signed DMG to Apple, waits for acceptance, staples and validates the ticket, checks the result with Gatekeeper, and only then writes the final SHA-256 sidecar. Without that variable the output is Developer ID signed but intentionally not submitted for notarization.

The published 3.7.0 direct-download DMG was accepted by Apple notarization on 20 August 2026, stapled successfully, and accepted by Gatekeeper as `Notarized Developer ID`.
