# 🚀 AudioEnhancerMAX v3.0.0 — Metal GPU + Edge Cluster Edition

The biggest release yet. Metal GPU acceleration, a native Android companion app, built-in DSP benchmarking, and a completely redesigned landing page.

---

## ⬡ Metal GPU Acceleration
- **Apple Metal GPU** via PyTorch MPS for Demucs music separation — up to 3x faster
- Centralized acceleration module: MPS + Apple Accelerate (vDSP) + ARM NEON + GC allocator
- CTranslate2 4.7.1 ARM NEON confirmed for faster-whisper
- `GET /api/acceleration` — query active hardware acceleration

## 📱 Android Companion App (NEW)
- Native **Kotlin** worker app in `android-worker/`
- Material 3 UI with real-time task status and connection indicator
- HTTP server on port 8080 — receives DSP tasks from Mac master
- **UDP auto-discovery** — zero configuration, plug and process
- Pre-built APKs in `releases/` folder

## 🏁 DSP Benchmark System (NEW)
- FFT, FIR filtering, spectral gating, resampling benchmarks
- M3 Max baseline: **112 ops/s** (FFT 264, Resample 356)
- `GET /api/benchmark` — compare all cluster devices

## 📊 Enhanced Processing Dashboard
- **Per-core CPU heatmap** — 16 cells showing P-cores vs E-cores
- Power watts, CPU frequency, ANE%, benchmark score
- Filter badges: `⬡ Metal` (GPU) · `ML` (AI) · `Edge` (distributed)

## ⚙️ Settings & ℹ️ About Panels (NEW)
- In-app configuration: output format, LUFS target, worker timeout, Whisper model
- About page with architecture grid, changelog, system info, hardware acceleration status

## 🌐 Landing Page v3.0
- Complete redesign: animated ambient orbs, glassmorphism, scroll-reveal
- Standalone HTML — deploy directly to Hostinger
- Benchmark data, feature cards, architecture diagram, comparison table

---

## 📦 Assets

| Asset | Description |
|-------|------------|
| `AudioEnhancerMAX-Worker-v1.2.0-debug.apk` | Android companion worker app |
| `frontend/landing.html` | Standalone landing page for web hosting |

## 🔧 Quick Start

```bash
git clone https://github.com/sev7enITA/AudioEnhancerMAX.git
cd AudioEnhancerMAX
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 · Landing page at http://localhost:8000/landing

---

**Full Changelog**: https://github.com/sev7enITA/AudioEnhancerMAX/compare/v2.0.0...v3.0.0
