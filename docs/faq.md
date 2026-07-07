# Troubleshooting / FAQ

## The server starts but Smart Mode is unavailable

Install and start Ollama, then pull the configured Gemma model:

```bash
ollama serve
ollama pull gemma4:e2b
```

The backend can also use other local Gemma-family models exposed by Ollama. Core DSP features work without Ollama.

## FFmpeg errors appear during upload or export

Install FFmpeg and make sure it is on `PATH`:

```bash
brew install ffmpeg
ffmpeg -version
```

## Android worker build fails with Java version errors

Use JDK 17 or 21:

```bash
export JAVA_HOME="/path/to/jdk17-or-jdk21"
cd android-worker
./gradlew assembleDebug
```

JDK 25 is not supported by the current Kotlin/Gradle combination.

## pyannote diarization is unavailable

`pyannote.audio` may require model access and local cache setup. When it is unavailable, AudioEnhancerMAX falls back to an energy-based diarization path.

## I need to use the app from another device

Run LAN mode only on a trusted network:

```bash
export AEMAX_CORS_ORIGINS="http://YOUR_MAC_IP:8000,http://localhost:8000"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Do not expose the app directly to the public internet.
