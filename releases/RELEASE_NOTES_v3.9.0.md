# AudioEnhancerMAX 3.9.0

Stable direct release, build 3.9.2. Released 27 October 2026 for Apple Silicon Macs running macOS 13 or later. Free, MIT-licensed source. No account or subscription is required for the core local workflow.

## New in stable

The Music brief assistant moves from Experimental 1 into the stable app. Start with one of six original presets, describe the desired music, set styles, instruments, exclusions, vocal mode, duration, BPM and arrangement directions, then build an editable structured prompt. Lyrics stay in a separate field. Copy the current prompt or export a JSON record that preserves source fields, the original prompt and your edits.

Optional Ollama refinements require explicit permission and an installed local model. Suggestions remain separate until you review and append them. The core builder runs locally without a model or network. This feature prepares text; it does not generate music or use a MiniMax API.

The release also updates pinned dependencies and restores the stable app identity while retaining the earlier experimental download for users who want a separate preview installation.

## Existing audio workflow

Local audio cleanup, EQ and loudness processing; reviewable speech edits; five output profiles; WAV, MP3 and FLAC export; local transcription after a model is available; result-bound processing reports and SHA-256 project capsules remain available. Optional engines have separate requirements. See the [installation guide](../docs/macos-app.md) and [Music brief guide](../docs/music-brief-assistant.md).

## Install, upgrade and rollback

Quit the old stable app, open the DMG and replace AudioEnhancerMAX in Applications. The stable data folder is retained. Experimental 1 remains separate and its data is not migrated automatically. Back up Application Support before a downgrade. [Previous stable 3.8.3](https://github.com/sev7enITA/AudioEnhancerMAX/releases/tag/v3.8.3) remains available.

## Boundaries reviewers should know

- Music brief drafts last for the current session. Copy or export before closing; JSON re-import is not available.
- Transcription needs a model download on first use unless cached. Accuracy requires review.
- Bundled PyAV provides core codecs. External FFmpeg is not needed for the packaged core workflow.
- Ollama and its models, Kokoro, Demucs, DeepFilterNet and MakeMyVoice are separate optional components. Edge Neural TTS uses Microsoft's external service.
- Loudness/peak guidance is workflow information, not third-party certification. Output quality depends on the recording and settings.
- This is a direct macOS release. No App Store approval is asserted.

## Evidence and demonstration

See [package verification](DIRECT_BUILD_3.9.2.md) for the exact artifact, checks and limits. The [4:33 workflow tour](https://www.youtube.com/watch?v=b2WYm-Mtw-c) has English narration and English/Italian subtitles. It was recorded with Experimental 1, so its version badge differs from this stable release. The Music brief workflow shown is now included in 3.9.0.

Report reproducible problems through [GitHub issues](https://github.com/sev7enITA/AudioEnhancerMAX/issues), including version, macOS version, steps and relevant error text. Avoid uploading private recordings or secrets in a public report.
