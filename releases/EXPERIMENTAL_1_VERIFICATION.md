# Experimental 1 package verification

Version **3.9.0**, build **3.9.1**, tag **v3.9.0-experimental.1**.
Source commit: `fc22c9cf74439aaa4f83608e2f132c6f2465597a`.
Verified on one physical Apple Silicon Mac running macOS 27.2 on 23 October 2026.

## Distribution

- Developer ID signature and hardened runtime verified.
- Apple notarization: **Accepted**, submission `914637be-9d49-4df2-8647-4e21e0934af0`.
- Stapling and ticket validation passed; Gatekeeper: **accepted, Notarized Developer ID**.
- File: `AudioEnhancerMAX-v3.9.0-experimental.1-build-3.9.1-macOS-arm64.dmg`
- Size: 132747870 bytes.
- SHA-256: `b234ea6dc60d8b388698109e5dfce93abaa906c63608362edd2f3c611c66f068`

## Packaged application

- Launched the native AppKit/WKWebView application from the final DMG.
- Confirmed the Experimental app name, distinct bundle identifier, version and channel.
- Matched all **71 bundled frontend files** exactly against the build source.
- Built a Music brief in the native window and saved JSON using the macOS Save dialog.
  Parsed the saved file and verified its current and original captions.
- Confirmed six presets, exact preservation of separate lyrics, and HTTP 403 when local
  Ollama editorial permission is disabled.
- Uploaded a synthetic three-second 48 kHz WAV, normalized it, exported WAV, checked
  finite samples and verified the source file hash remained unchanged.
- Ran the experimental packaged app on port 8001 alongside the stable 3.8.3 source
  backend on port 8000. Both reported healthy. Quitting Experimental stopped only
  port 8001; the stable backend remained healthy. Two native windows were not tested.
- The experimental data directory is separate from stable and starts with its own
  privacy preferences. No stable recordings or settings were migrated.

## Automated and earlier feature checks

**135 Python tests, 11 subtests and 19 JavaScript tests passed.**
[GitHub CI passed](https://github.com/sev7enITA/AudioEnhancerMAX/actions/runs/39988714345).
Earlier browser tests covered desktop and mobile, edited-prompt export, stale requests,
permission changes and real local `gemma4:e2b` suggestions. Real-model inference was
not repeated inside the packaged application; the packaged permission-off path was tested.

## Limits

This is an experimental direct download. Stable remains **3.8.3, build 3.8.4**.
Music brief prepares text and does not generate music. No first-time model acquisition,
perceptual audio-quality evaluation, or validation on every supported macOS version was
performed. Apple notarization does not establish App Store approval or feature quality.
