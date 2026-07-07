# Feature Guide

## Audio Cleanup

- AI noise removal through DeepFilterNet when available, with noisereduce fallback.
- Specific noise tools for wind, buzzing, static, reverb, echo, breaths, mouth sounds, and long silences.
- Conservative wet/dry mixing is used in key filters to preserve natural voice texture.

## Enhancement

- Studio sound chain for warmth, presence, de-essing, compression, and limiting.
- Auto EQ profiles for voice-forward output.
- LUFS normalization for podcast and broadcast targets.
- Frequency restoration and optional Demucs music preservation.

## AI Workflow

- Smart Mode classifies the content type and suggests processing options.
- Dynamic parameter tuning adjusts filter strength based on the input signal.
- Editing suggestions combine transcript context and audio analysis when Ollama/Gemma is available.

## Transcription

- Faster-Whisper transcription with word-level timestamps.
- Streaming transcription endpoint for real-time UI updates.
- Export formats: TXT, SRT, VTT, and JSON.
- Partial transcripts are saved incrementally for crash resilience.

## Text-to-Speech

- Kokoro local voices for expressive English narration when installed locally.
- Edge Neural voices for multilingual synthesis as an optional external TTS engine; selected text is sent to Microsoft Edge TTS when used.
- Expressive rewrite mode can prepare text for more natural spoken delivery.

## Monitoring and ETA

- System monitor tracks CPU, GPU, ANE, RAM, power, and thermal state where supported.
- Adaptive ETA engine learns from real processing history and reports per-step timing.

## Edge Workers

- Android worker app receives safe DSP tasks from the master node.
- UDP discovery and manual registration are supported on trusted local networks.
