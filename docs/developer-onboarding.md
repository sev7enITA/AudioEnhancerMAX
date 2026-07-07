# Developer Onboarding

This project has three main surfaces:

- `app/`: FastAPI backend, Pydantic schemas, audio I/O utilities, progress tracking, and service modules.
- `frontend/`: static application UI served by the backend.
- `web/`: static public website copy for deployment to the official site.
- `android-worker/`: native Android worker for edge DSP.

## Backend Flow

1. Upload stores the original file in `app/uploads/`.
2. Audio is normalized to WAV when needed.
3. Processing requests load the source and run selected services in order.
4. Progress is emitted over WebSocket.
5. Outputs are written to `app/outputs/`.

## Important Services

- `app/services/enhancement.py`: studio sound, Auto EQ, normalization, Demucs music preservation.
- `app/services/specific_noise.py`: wind, buzz, static, reverb, and echo cleanup.
- `app/services/speech_cleanup.py`: filler words, hesitations, stutters, breaths, mouth sounds.
- `app/services/transcription.py`: faster-whisper transcription and streaming.
- `app/services/tts.py`: Edge and Kokoro TTS.
- `app/services/timing_engine.py`: adaptive ETA history.
- `app/services/cluster_manager.py`: worker discovery and task routing.

## Release Checklist

```bash
source venv/bin/activate
python -m compileall -q app
python - <<'PY'
from app.main import app
print(app.version)
PY
```

Also verify:

- `git status --short`
- no ignored source packages are required for import
- `frontend/landing.html` and `web/index.html` are in sync when changing the public site
- Android builds use JDK 17 or 21
