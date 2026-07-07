#!/bin/bash
# ═══════════════════════════════════════════════════════════
# AudioEnhancerMAX by Fd — One-Click Setup Script
# Optimized for Apple Silicon M3 MAX
# ═══════════════════════════════════════════════════════════

set -e

echo ""
echo "⚡ AudioEnhancerMAX by Fd — Setup"
echo "══════════════════════════════════════════════"
echo ""

# ── Check prerequisites ──
echo "🔍 Checking prerequisites..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Install with: brew install python@3.11"
    exit 1
fi
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "  ✓ Python $PYTHON_VERSION"

# Check FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "📦 Installing FFmpeg..."
    brew install ffmpeg
fi
echo "  ✓ FFmpeg installed"

# Check Ollama
if command -v ollama &> /dev/null; then
    echo "  ✓ Ollama installed"
    OLLAMA_OK=true
else
    echo "  ⚠ Ollama not found. Install from https://ollama.com/"
    echo "    Gemma 4 Smart Mode will use fallback heuristics."
    OLLAMA_OK=false
fi

# ── Create virtual environment ──
echo ""
echo "🐍 Setting up Python virtual environment..."

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "  ✓ Virtual environment created"
else
    echo "  ✓ Virtual environment exists"
fi

source venv/bin/activate

# ── Install PyTorch with MPS (Apple Silicon) ──
echo ""
echo "🍎 Installing PyTorch for Apple Silicon (MPS)..."
pip install --quiet --upgrade pip
pip install --quiet torch torchvision torchaudio

# Verify MPS
python3 -c "
import torch
if torch.backends.mps.is_available():
    print('  ✓ Apple Metal (MPS) acceleration available')
else:
    print('  ⚠ MPS not available — falling back to CPU')
"

# ── Install core dependencies ──
echo ""
echo "📦 Installing core dependencies..."
pip install --quiet \
    fastapi==0.115.6 \
    "uvicorn[standard]==0.34.0" \
    python-multipart==0.0.20 \
    websockets==14.2 \
    aiofiles==24.1.0 \
    pydantic==2.10.4

echo "  ✓ Web framework installed"

# ── Audio processing libraries ──
echo ""
echo "🎵 Installing audio processing libraries..."
pip install --quiet \
    pydub==0.25.1 \
    soundfile==0.13.1 \
    librosa==0.10.2.post1 \
    numpy==1.26.4 \
    scipy==1.14.1 \
    resampy==0.4.3 \
    noisereduce==3.0.3 \
    pyloudnorm==0.1.1

echo "  ✓ Audio libraries installed"

# ── Spotify Pedalboard ──
echo ""
echo "🎚️ Installing Pedalboard (Spotify)..."
pip install --quiet pedalboard==0.9.16
echo "  ✓ Pedalboard installed"

# ── DeepFilterNet ──
echo ""
echo "🧠 Installing DeepFilterNet..."
pip install --quiet deepfilternet || {
    echo "  ⚠ DeepFilterNet install failed. Will use noisereduce fallback."
}

# ── faster-whisper (STT) ──
echo ""
echo "📝 Installing faster-whisper (Speech-to-Text)..."
pip install --quiet faster-whisper==1.1.0
echo "  ✓ faster-whisper installed"

# ── Text-to-Speech engines ──
echo ""
echo "🗣️ Installing Text-to-Speech engines..."
pip install --quiet edge-tts kokoro TTS==0.22.0 || {
    echo "  ⚠ TTS install had issues. Edge/Kokoro/Coqui features may be limited."
}

# ── Demucs (Meta source separation) ──
echo ""
echo "🎶 Installing Demucs (Meta)..."
pip install --quiet demucs==4.0.1 || {
    echo "  ⚠ Demucs install had issues. 'Keep Music' feature may be limited."
}

# ── pyannote.audio (Speaker Diarization) ──
echo ""
echo "👥 Installing pyannote.audio (Speaker Diarization)..."
pip install --quiet pyannote.audio || {
    echo "  ⚠ pyannote install failed. Will use energy-based fallback."
}

# ── Create directories ──
echo ""
echo "📁 Creating directories..."
mkdir -p app/uploads app/outputs presets
echo "  ✓ Directories ready"

# ── Pull Gemma 4 model via Ollama ──
if [ "$OLLAMA_OK" = true ]; then
    echo ""
    echo "🧠 Pulling Gemma 4 E2B model via Ollama..."
    echo "   (This may take a few minutes for first download)"

    # Start Ollama if not running
    if ! pgrep -x "ollama" > /dev/null; then
        echo "   Starting Ollama..."
        ollama serve &
        sleep 3
    fi

    ollama pull gemma4:e2b 2>/dev/null || {
        echo "  ⚠ Could not pull gemma4:e2b. Trying gemma3:4b as fallback..."
        ollama pull gemma3:4b 2>/dev/null || {
            echo "  ⚠ No Gemma model pulled. Smart Mode will use heuristics."
        }
    }
fi

# ── Final summary ──
echo ""
echo "═══════════════════════════════════════════════"
echo "⚡ AudioEnhancerMAX by Fd — Setup Complete!"
echo "═══════════════════════════════════════════════"
echo ""
echo "To start the application:"
echo ""
echo "  source venv/bin/activate"
echo "  uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
echo ""
echo "Then open: http://localhost:8000"
echo "For LAN access, use --host 0.0.0.0 only on a trusted network and set AEMAX_CORS_ORIGINS explicitly."
echo ""
echo "To start Ollama (for Smart Mode):"
echo "  ollama serve"
echo ""
