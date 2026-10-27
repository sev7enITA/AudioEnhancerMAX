# AudioEnhancerMAX 3.9.0 Experimental 1

Experimental channel, build 3.9.1. The stable release remains
[3.8.3, build 3.8.4](https://github.com/sev7enITA/AudioEnhancerMAX/releases/tag/v3.8.3).
This prerelease introduces the Music brief assistant for testing and feedback.

## Music brief

- Six original presets for intros, narration, documentaries, focus, energetic openings
  and acoustic storytelling.
- Editable structured prompts covering style, instruments, exclusions, vocals, target
  duration, optional BPM and arrangement. Lyrics remain separate and unchanged.
- Deterministic brief construction works without a model or network connection.
- Optional suggestions from an installed local Ollama model require permission in
  Settings. Suggestions remain separate until explicitly appended.
- Copy and JSON export preserve the current prompt, original prompt and source fields.

This feature prepares text. It does not generate music, call MiniMax, mix a soundtrack,
or guarantee that a separate generator follows timing or musical constraints. Drafts
are kept in the current tab until copied or exported; JSON re-import is not included.

## Install alongside stable

Drag **AudioEnhancerMAX Experimental.app** into Applications. Its app name, bundle
identifier, launcher lock, logs, default port and application data are separate from
the stable application. Both versions can run at the same time.

- Experimental data: `~/Library/Application Support/AudioEnhancerMAX Experimental`
- Experimental logs: `~/Library/Logs/AudioEnhancerMAX Experimental`
- Stable data: `~/Library/Application Support/AudioEnhancerMAX`

No existing stable recordings, projects or privacy choices are migrated. Enable optional
services separately in the experimental app. Ollama and existing model caches are external
resources and may be shared by both installations. Export copies of work you want to keep.
To return to stable, quit Experimental and open AudioEnhancerMAX.

## Requirements and scope

Apple Silicon, macOS 13 or later. No model weights are bundled or downloaded by the
Music brief assistant. Optional Ollama suggestions require a separate local installation
and a compatible installed text model.

The source checks cover the full Python suite and JavaScript state suites. Browser and
live-model validation is recorded in [the Music brief validation report](../docs/music-brief-validation-2026-10-23.md).
The separate package verification record accompanies the release download. Automated
checks and Apple notarization do not establish perceptual audio quality or coverage of
every supported macOS version. This experimental release is not a Mac App Store update.
