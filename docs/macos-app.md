# AudioEnhancerMAX for macOS

AudioEnhancerMAX v3.5.2 introduces an Apple Silicon desktop package. Opening the app starts a loopback-only FastAPI server and opens the local interface in the default browser. Closing the app stops the server.

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

The GitHub v3.5.2 DMG retains these documented external boundaries. It must not be represented as the Mac App Store package. The App Store build will set `AEMAX_APP_STORE=1`; in that mode the readiness check requires FFmpeg and FFprobe inside the signed app bundle and rejects fallback to Homebrew or another system installation.

Model assets require the same treatment before App Store submission: a feature may use a bundled model or an explicitly disclosed resource download, but it must not silently obtain executable code. Ollama integration remains optional and cannot be a prerequisite for the core audio workflow.

## Build locally

```bash
./scripts/build_macos_app.sh
```

The build produces a DMG containing the signed application and keeps the unpackaged `.app` as an intermediate build artifact:

- `dist/macos/AudioEnhancerMAX.app`
- `dist/macos/AudioEnhancerMAX-v3.5.2-macOS-arm64.dmg`
- a SHA-256 checksum alongside the DMG

The local script applies ad-hoc signing so the bundle can be verified after packaging. Public distribution should use a Developer ID Application certificate and Apple notarization. Ad-hoc signing is not equivalent to notarization, and macOS Gatekeeper may still warn on first launch.
