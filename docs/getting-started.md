# Getting Started

AudioEnhancerMAX is a local-first FastAPI application with a static browser UI.

## 1. Clone

```bash
git clone https://github.com/sev7enITA/AudioEnhancerMAX.git
cd AudioEnhancerMAX
```

## 2. Create the environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 3. Install system tools

Install FFmpeg for audio conversion:

```bash
brew install ffmpeg
```

Optional Apple Silicon monitor:

```bash
brew install macmon
```

Optional local AI:

```bash
brew install ollama
ollama pull gemma4:e2b
```

`gemma4:e2b` is the preferred model when available. The backend also auto-detects other local Gemma-family models exposed by Ollama.

## 4. Run

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open `http://127.0.0.1:8000`.

## LAN Mode

Use LAN mode only on a trusted network:

```bash
export AEMAX_CORS_ORIGINS="http://192.168.1.20:8000,http://localhost:8000"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Do not expose the development server directly to the public internet.
