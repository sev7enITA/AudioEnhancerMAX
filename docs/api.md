# API Reference

The backend is defined in `app/main.py` and serves the browser UI plus JSON, file, WebSocket, and SSE endpoints.

## System

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | App version, compute backend, Ollama/Gemma status, and whole-system/SoC/app-process monitor summary |
| GET | `/api/acceleration` | Apple Silicon and ML acceleration details |
| GET | `/api/benchmark` | Master and worker benchmark summary |
| GET | `/api/system/stats` | Current CPU/GPU/ANE/RAM metrics |
| GET | `/api/system/history` | Recent monitor history |

## Audio

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/upload` | Upload an audio/video file and return metadata |
| GET | `/api/audio/{file_id}` | Stream original or processed audio |
| POST | `/api/process` | Run the enhancement pipeline |
| GET | `/api/download/{file_id}` | Download WAV, MP3, or FLAC output |
| WS | `/ws/progress/{file_id}` | Live processing progress |

`file_id` must be a safe storage token. Download `format` is limited to `wav`, `mp3`, or `flac`. Download `version` is limited to `original`, `processed`, `speech_edit`, `watermarked`, or `tts`.

## Transcription and Diarization

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/transcribe` | Non-streaming transcription |
| POST | `/api/transcribe/stream` | SSE streaming transcription |
| GET | `/api/transcribe/resume/{file_id}` | Check partial transcript state |
| POST | `/api/diarize` | Speaker diarization with pyannote or fallback |

## Precision Speech Editor

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/speech-editor/analyze` | Generate a non-destructive EDL from local word timestamps and acoustic candidates |
| GET | `/api/speech-editor/{file_id}` | Retrieve the persisted EDL |
| PATCH | `/api/speech-editor/{file_id}` | Save Keep/Apply decisions with revision checking |
| GET | `/api/speech-editor/{file_id}/preview/{candidate_id}` | Preview original or proposed candidate audio |
| POST | `/api/speech-editor/{file_id}/render` | Render approved `cut` and `mute` edits to a new output |
| POST | `/api/speech-editor/{file_id}/manual-edit` | Create a reviewable cut/mute proposal from a transcript range |
| POST | `/api/speech-editor/{file_id}/undo` | Undo the current persisted EDL state with revision checking |
| POST | `/api/speech-editor/{file_id}/redo` | Restore the next persisted EDL state with revision checking |
| GET | `/api/speech-editor/{file_id}/export?format=json\|csv` | Export the complete decision list |
| GET | `/api/output-profiles` | List fixed delivery profiles and parameters |
| GET/PATCH | `/api/settings/privacy` | Read or persist external-service, Ollama, and trusted-LAN boundaries |
| GET | `/api/reports/{file_id}` | Retrieve processing and reviewed-EDL evidence |

## Delivery Review and Portable Evidence

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/compliance-targets` | List transparent local delivery-check targets and thresholds |
| GET | `/api/compliance/{file_id}?target_id=podcast` | Measure the processed artifact and return rule-level delivery guidance |
| POST | `/api/reviews/{file_id}/blind-ab` | Persist the revealed result of a subjective blind A/B listening round |
| POST | `/api/projects/{file_id}/export` | Download a checksum-backed Project Capsule ZIP |

Project Capsule JSON accepts `include_source` (default `false`) and `target_id`. The ZIP includes `manifest.json`, the processed output, and any available report, compliance result, transcript, speech EDL, or blind A/B review. Original audio is included only after explicit opt-in. Delivery checks are local workflow guidance, not third-party or regulatory certification.

## TTS

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/tts/voices` | List available voices |
| GET | `/api/voice-profiles` | List named personal voices and the live MakeMyVoice adapter capability |
| POST | `/api/voice-profiles/enroll` | Create a named voice or improve an existing profile from an uploaded sample; explicit owner consent is required |
| PATCH | `/api/voice-profiles/{profile_id}` | Save the profile name and its language/style/speed/pitch/warmth defaults |
| POST | `/api/tts/synthesize` | Generate speech |
| POST | `/api/tts/rewrite` | Preview expressive rewrite |

Personal synthesis sets `engine` to `voice-clone` and supplies `voice_profile_id`. A raw `clone_voice_file_id` without a saved profile is rejected so the sample can never be silently ignored while a stock voice is used. `POST /api/voice-profiles/enroll` references a normal uploaded `file_id`, accepts an optional exact `transcript`, and requires `consent_confirmed: true`.

## Presets and Batch

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/presets` | Built-in and saved presets |
| POST | `/api/presets` | Save custom preset |
| GET | `/api/presets/{preset_id}` | Load preset |
| DELETE | `/api/presets/{preset_id}` | Delete preset |
| POST | `/api/batch` | Start sequential batch processing |
| GET | `/api/batch/{job_id}` | Inspect batch state |

Preset IDs are slugged and restricted to local JSON files in `presets/`.

## Version 3.8 revision contract

Downloads, compliance, reports, A/B decisions and capsules can be bound to the completed output revision. See [revision delivery](revision-delivery.md) for parameters, response hashes and 404/409 behavior.
