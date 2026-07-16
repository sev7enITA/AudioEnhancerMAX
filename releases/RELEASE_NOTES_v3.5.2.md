# AudioEnhancerMAX v3.5.2

AudioEnhancerMAX v3.5.2 is a packaging, presentation, and community-roadmap release. It does not claim delivery of the processing features planned for v3.6.

## Added

- Apple Silicon macOS desktop package that starts the loopback-only FastAPI server and opens the interface without Terminal.
- Single-instance launcher with automatic reuse of an already running AudioEnhancerMAX server.
- Community Roadmap and signal board for ranking future feature candidates.
- Bespoke SVG interface icon system and SourceForge Rising Star fallback asset.
- Dedicated macOS data directories for uploads, outputs, presets, timing history, votes, state, and logs.

## macOS package scope

The DMG contains the Python runtime, FastAPI backend, browser frontend, PyTorch/MPS support, and the processing libraries present in the release environment. It targets Apple Silicon and requires macOS 13 or later.

The package does not include recordings, generated outputs, model caches, Ollama, or Ollama models. Some model-backed functions download weights on first use. Edge Neural TTS requires network access. Ollama-assisted functions require a separate local Ollama installation. Compressed formats handled through pydub can require a separate FFmpeg executable.

The current DMG is ad-hoc signed and has not been Apple-notarized. The signature verifies bundle integrity, but Gatekeeper can still show a warning on first launch. A Developer ID certificate and notarization remain release-engineering follow-ups.

## Security and governance

- Desktop HTTP traffic binds to `127.0.0.1` by default.
- Mutable data is stored in `~/Library/Application Support/AudioEnhancerMAX`.
- Launcher logs are stored in `~/Library/Logs/AudioEnhancerMAX/launcher.log`.
- Local-network access is reserved for trusted edge workers selected by the user.
- Public descriptions distinguish local processing, optional network services, external models, and current packaging limitations.

## Artifact

- `AudioEnhancerMAX-v3.5.2-macOS-arm64.dmg`
- SHA-256: `49f1e186a04c1ed52c6155022b250e3588d7e00c1d37a48b5e16b1a5eca46aeb`
