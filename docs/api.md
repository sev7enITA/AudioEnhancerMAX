# API Reference

The backend is defined in `app/main.py` and serves the browser UI plus JSON, file, WebSocket, and SSE endpoints.

## System

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | App version, compute backend, Ollama/Gemma status, monitor summary |
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

`file_id` must be a safe storage token. Download `format` is limited to `wav`, `mp3`, or `flac`. Download `version` is limited to `original`, `processed`, `watermarked`, or `tts`.

## Transcription and Diarization

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/transcribe` | Non-streaming transcription |
| POST | `/api/transcribe/stream` | SSE streaming transcription |
| GET | `/api/transcribe/resume/{file_id}` | Check partial transcript state |
| POST | `/api/diarize` | Speaker diarization with pyannote or fallback |

## TTS

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/tts/voices` | List available voices |
| POST | `/api/tts/synthesize` | Generate speech |
| POST | `/api/tts/rewrite` | Preview expressive rewrite |

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
