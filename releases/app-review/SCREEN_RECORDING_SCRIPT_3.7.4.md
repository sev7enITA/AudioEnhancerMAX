# Apple Physical-Mac Recording Script — build 3.7.4

Target length: one unedited 3–5 minute recording. Install build 3.7.4 through TestFlight. Keep the macOS menu bar and pointer visible; do not expose the Mac serial number, email, or unrelated files.

## Before recording

- Confirm the recording Mac runs the latest public macOS available that day.
- Place only `AudioEnhancerMAX-review-sample.wav` in a clean review folder.
- Quit AudioEnhancerMAX and close browsers/terminals that expose private information.
- Optionally prepare a Terminal command that shows only the loopback listener for the app PID; avoid displaying unrelated processes.

## Continuous sequence

1. **System identity (15–25 s):** open About This Mac, show Mac model and exact macOS version/build, hide serial number, then close it.
2. **Native launch and identity (20–30 s):** launch AudioEnhancerMAX from Applications/TestFlight. Show the app-owned menu name and About AudioEnhancerMAX with version 3.7.0 build 3.7.4.
3. **Loopback evidence (15–25 s):** show that the embedded service listens on `127.0.0.1` while the app is open. Explain that this inbound loopback listener is why `com.apple.security.network.server` is required.
4. **Upload and process (40–60 s):** select the supplied WAV through the native Open panel, show file facts, choose Podcast or Smart Enhance, and process.
5. **Review Deck (45–70 s):** show Podcast delivery rules and measured loudness/estimated true peak/clipping/sample rate. State aloud that this is workflow guidance, not certification. Start a randomized blind A/B round, listen to A and B, choose one, then show the reveal.
6. **Evidence export (25–40 s):** leave “Include original audio” off, export the Project Capsule, and show the ZIP contains `manifest.json`, the processed output, and evidence artifacts. Open the Processing Report and show provenance/privacy briefly.
7. **Core export (25–40 s):** export WAV, MP3, and FLAC through the native Save panel.
8. **Speech workflow (35–55 s):** show one reviewed Precision Editor cut/mute or local Faster-Whisper transcription using the supplied file.
9. **Quit and lifecycle (20–30 s):** choose Quit AudioEnhancerMAX or close its main window. Show that the process stops and the loopback listener disappears.

## Filename and attachment

Save as `AudioEnhancerMAX-3.7.0-build-3.7.4-physical-macOS.mov`. Watch the entire file once before attaching it under App Review Information. The recording must match the submitted TestFlight build exactly.
