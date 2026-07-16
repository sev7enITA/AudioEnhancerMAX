# Changelog

All notable changes to AudioEnhancerMAX are documented here.

## [3.5.2] - 2026-07-16

### Added

- Apple Silicon macOS desktop launcher and repeatable `.app`/`.dmg` packaging workflow.
- Community Roadmap pages with feature proposals and interest signaling.
- Bespoke SVG interface icon set and local SourceForge award fallback.
- macOS packaging documentation covering data locations, external services, model downloads, signing, and notarization status.

### Changed

- Mutable desktop data now uses `~/Library/Application Support/AudioEnhancerMAX` in frozen builds.
- Public presentation and roadmap links now target the `sev7enITA` repository.

### Security and governance

- The desktop server binds to loopback by default.
- The release documentation distinguishes bundled processing components from network-dependent TTS, external Ollama integration, downloadable model weights, and FFmpeg-dependent formats.

## [3.5.1] — 2026-07-07

### Release Hardening
- Fixed clean-clone packaging by allowing `app/models/` to be tracked again.
- Added API input validation for file IDs, download formats, audio versions, batch IDs, and preset names.
- Replaced unsafe `tempfile.mktemp()` usage with atomically created temporary files.
- Restricted default CORS origins to local development URLs; LAN exposure now requires explicit `AEMAX_CORS_ORIGINS`.
- Added `edge-tts` and `kokoro` to runtime dependencies to match the current TTS implementation.
- Smart Mode now reports the detected Ollama/Gemma model instead of hard-coding a model name in responses.

### Public Relaunch
- Updated README, website, landing page, and contribution links for `sev7enITA/AudioEnhancerMAX`.
- Added SourceForge Rising Star recognition to the public presentation.
- Reframed public claims around local-first processing, explicit optional external services, and AI governance transparency.
- Added real documentation pages for getting started, features, API, edge computing, onboarding, FAQ, and translation notes.
- Synced the app-served landing page with the deployable `web/` site.

### Android Worker
- Aligned Android worker metadata with the existing v1.2.0 APK release.
- Documented JDK 17/21 requirement and the known JDK 25 build incompatibility.

## [3.5.0] — 2026-04-27 🚀 MAJOR RELEASE

### ⚡ Non-Blocking Server Architecture
- Complete `asyncio.to_thread()` refactor — server stays responsive during 20+ minute Whisper/Demucs jobs
- `/api/health` responds instantly even under full CPU load (transcription, diarization, DSP pipeline)
- Each DSP filter step runs in its own thread for maximum event-loop freedom
- `AbortController` with 3s timeout on all frontend polling — no more stalled requests

### 📡 Real-Time Streaming Transcription (SSE)
- **NEW**: `POST /api/transcribe/stream` — Server-Sent Events endpoint for segment-by-segment delivery
- Text appears in the UI within seconds of starting — no more blank screen for 20 minutes
- Auto-download in SRT, VTT, JSON, or TXT with proper subtitle timestamps
- Custom output filename — user chooses the file name before starting
- Client-side SRT/VTT formatters with precise `HH:MM:SS,mmm` timestamps

### 💾 Crash-Resilient Incremental Delivery
- Transcripts saved to disk after EVERY segment (`{file_id}_transcript.json`)
- `GET /api/transcribe/resume/{file_id}` detects partial transcripts from interrupted sessions
- Robust frontend fallback: if the `done` SSE event is lost, accumulated segments are used automatically
- Previous checkpoint/resume system for DSP pipeline preserved from v3.1

### 🖥️ System Monitor v2 (Complete Rewrite)
- **Dual-thread architecture**: psutil (CPU/RAM/disk/net) + macmon pipe (GPU/ANE/power/thermal)
- `psutil.cpu_percent()` warmup at init eliminates zero-reading bug
- macmon continuous pipe reader — non-blocking, dedicated thread
- Atomic data merge: psutil as base dict, macmon overlay for Apple Silicon metrics
- CPU/GPU temperature display (°C) with color-coded badges and thermal pressure indicator

### ⏱️ Adaptive ETA Engine (Calibrated)
- **FIXED**: Whisper benchmark corrected from 2.5 → 90 secs/60s audio (measured on M3 MAX)
- 3-level estimation: static benchmarks → blended → full history regression
- Time shown as ranges ("15-20 min") for trustworthy UX
- "Stima → pausa → Azione" flow: estimate displayed for 2s before job starts
- Timing history persisted to disk for cross-session learning

### 🎨 Frontend & UX
- **FIXED**: Settings and About panels were invisible — panels moved inside `<main>` container
- **FIXED**: HW polling now active for ALL task types (transcription, diarization, TTS)
- Always-visible Copy & Download buttons (disabled until transcription completes)
- Transcript output area with real-time text and auto-scroll
- Version bumped to v3.5.0 across sidebar, Settings, About, landing page, and API metadata

---

## [3.1.1] — 2026-04-27

### 🔥 Non-Blocking Server Architecture (CRITICAL FIX)
- **FIXED**: Server was unresponsive during heavy processing (Whisper, diarization) — all CPU-bound operations now run via `asyncio.to_thread()` so the event loop stays free
- **FIXED**: `/api/health` endpoint now responds during active transcription/processing — HW metrics are always available
- Each DSP filter step in `process_audio()` is individually threaded for maximum responsiveness

### 📡 Streaming Transcription (NEW)
- **NEW**: `POST /api/transcribe/stream` — Server-Sent Events (SSE) endpoint that streams segments in real-time
- Text appears incrementally in the UI as Whisper processes each audio segment
- No more waiting 10+ minutes with a blank screen — see results within seconds of starting
- **NEW**: `GET /api/transcribe/resume/{file_id}` — check for partial transcripts from interrupted sessions

### 💾 Incremental File Delivery (NEW)
- Transcripts are saved to disk after EACH segment (`{file_id}_transcript.json`)
- If the server crashes or restarts mid-transcription, the partial transcript is preserved
- Next transcription attempt detects the existing partial and can resume or use cached result
- **NEW**: Custom output filename field — choose the transcript filename before starting

### 🖥️ System Monitor v2 (REWRITE)
- **REWRITTEN**: Complete rewrite of `system_monitor.py` with proper dual-thread architecture:
  - Thread 1 (psutil): CPU/RAM/disk/net metrics every 2s with proper warmup
  - Thread 2 (macmon): Continuous pipe reader for GPU/ANE/power/thermal data
- **FIXED**: `psutil.cpu_percent()` warmup at init — no more initial zero readings
- **FIXED**: macmon pipe reading is now non-blocking — dedicated thread drains buffer continuously
- Atomic data merge: psutil as base, macmon overlay for GPU/temp/power

### 🎨 Frontend Fixes
- **FIXED**: Settings and About panels were invisible — removed `style="display:none"` inline overrides that blocked CSS `.panel.active { display: block }`
- **FIXED**: HW polling now starts for ALL activity types (transcription, diarization, TTS) — not just Audio Processing
- **FIXED**: Health fetch uses `AbortController` with 3s timeout — polling doesn't stall on slow responses
- **FIXED**: ETA countdown uses server estimate as anchor — smooth decrement instead of recalculating each tick
- **NEW**: "Stima → pausa → Azione" flow — estimate shown for 2s before transcription begins
- **NEW**: Time ranges ("2-3 min") instead of exact seconds for more trustworthy UX
- Version bumped to v3.1.1 across sidebar, Settings, About, and API metadata

## [3.1.0] — 2026-04-27

### ⏱️ Adaptive Timing Engine (NEW)
- **NEW**: `timing_engine.py` — 3-level adaptive ETA system that learns from real processing times
  - **Level 1**: Static benchmarks calibrated for M3 MAX (first run fallback)
  - **Level 2**: Per-step live progress with server-side remaining time via WebSocket
  - **Level 3**: Persistent history (JSON on disk) — weighted linear regression on past runs for high-accuracy estimates
- Per-step breakdown: each filter reports its estimated and actual time
- Confidence indicator: 📊 high (history-based), 📈 medium (blended), 🧮 low (benchmark only)
- API: `POST /api/estimate` (adaptive), `POST /api/estimate/operation`, `GET /api/estimate/history`

### ♻️ Checkpoint/Resume (NEW)
- **NEW**: Processing pipeline saves intermediate audio after each step to `{file_id}_checkpoints/`
- If a job is interrupted (crash, timeout, network error), resubmitting the same file resumes from the last completed step
- Checkpoint metadata (`meta.json`) tracks completed steps and last audio state
- Checkpoints are automatically cleaned up on successful job completion

### 📊 System Monitor Fix
- **FIXED**: CPU/GPU/RAM stats showing zeros — fixed `psutil.cpu_percent()` warmup and macmon JSON parsing
- **FIXED**: macmon `gpu_usage` is `[freq_mhz, pct_float]` array, not a single float — now parsed correctly
- **NEW**: CPU and GPU temperature display (°C) in processing dashboard HW panel
- **NEW**: Thermal pressure indicator (nominal/moderate/serious/critical) derived from CPU temp
- **NEW**: Color-coded temperature badges: green (normal), yellow (>80°C), red (>90°C, pulsing)
- Memory data now sourced from macmon for unified memory accuracy on Apple Silicon

### 🎯 Frontend ETA Improvements
- WebSocket handler now consumes server-side `estimated_remaining_seconds`, `eta_confidence`, `per_step_estimates`
- Initial "anchor" estimate displayed immediately when processing starts (before any step runs)
- Step counter: "step 3/8" shown alongside ETA
- Confidence badge in ETA reason text: "📊 alta precisione" / "📈 precisione media" / "🧮 stima iniziale"
- Transcription pre-fetches adaptive estimate from `/api/estimate/operation` before starting
- `etaHistory` now persisted to `localStorage` — survives page refresh for instant re-estimates

### 🔧 Backend
- Version bumped to 3.1.0 (FastAPI + health endpoint + frontend)
- Health API enriched: `cpu_temp_c`, `gpu_temp_c`, `swap_used_gb`
- `ProgressTracker` enhanced: `send_estimate()` for initial anchor, ETA fields in all progress payloads
- New files: `app/services/timing_engine.py`

---

## [3.0.0] — 2026-04-20

### ⬡ Metal GPU Acceleration
- **NEW**: Apple Metal GPU (PyTorch MPS) for Demucs music separation — up to 3x faster source separation
- **NEW**: Centralized `apple_acceleration.py` module — configures MPS, Apple Accelerate (vDSP), ARM NEON, MPS GC allocator at startup
- **NEW**: Environment auto-configuration: `PYTORCH_MPS_HIGH_WATERMARK_RATIO`, `PYTORCH_ENABLE_MPS_FALLBACK`, `PYTORCH_MPS_ALLOCATOR_POLICY`
- CTranslate2 4.7.1 ARM NEON confirmed active for faster-whisper inference
- pyannote.audio diarization already on MPS (verified)
- API: `GET /api/acceleration` — shows active hardware acceleration configuration

### 📱 Android Companion App (NEW)
- **NEW**: Native Kotlin Android worker app (`android-worker/`)
- Material 3 UI with real-time task status, connection indicator, and device stats
- HTTP server on port 8080 for receiving DSP tasks from the Mac master
- Auto-discovery: smartphone pings master via UDP on startup — zero configuration
- Supports: noise removal, studio sound, auto EQ, normalization, frequency restoration
- Compatible with Samsung S24 Ultra, Xiaomi 17 Ultra, and any Android 8+ device via Termux

### 🏁 DSP Benchmark System
- **NEW**: Built-in benchmark suite testing FFT, FIR filtering, spectral gating, and resampling
- Runs automatically at server startup (background thread, non-blocking)
- M3 Max baseline: 112 ops/s overall (FFT 264 ops/s, Resample 356 ops/s)
- API: `GET /api/benchmark` — compare Mac master vs all Edge workers
- Benchmark score displayed in processing dashboard and About panel

### 📊 Enhanced Processing Dashboard
- **NEW**: Per-core CPU heatmap (16 cells, red/yellow/green by load) — shows P-cores vs E-cores activity
- **NEW**: Power consumption (watts), CPU frequency (GHz), ANE percentage, benchmark score chips
- Health API enriched: `cpu_per_core`, `cpu_freq_ghz`, `gpu_freq_ghz`, `timestamp`, `benchmark_score`
- Filter capability badges: `⬡ Metal` (green) for GPU-accelerated, `ML` (amber) for AI inference, `Edge` (cyan) for distributable

### ⚙️ Settings Panel (NEW)
- **NEW**: In-app configuration panel with 4 groups: Processing, Edge Cluster, Monitoring, AI Engine
- Settings: output format (WAV/FLAC/MP3), target LUFS, processing priority, worker timeout
- Toggle switches for auto-discovery, DSP offloading, per-core CPU display, dynamic tuning
- Whisper model size selector (base/medium/large-v3)

### ℹ️ About Panel (NEW)
- **NEW**: Comprehensive About page with architecture grid, v3.0 changelog, hardware acceleration status
- Live system info populated from `/api/health` and `/api/acceleration` endpoints
- Update instructions, license info, and credits for all open-source dependencies

### 🌐 Landing Page v3.0
- Complete redesign with cutting-edge aesthetics: animated ambient orbs, glassmorphism nav, scroll-reveal animations
- Feature cards with technology badges (Metal, AI, Edge, DSP)
- Interactive architecture diagram showing master-worker topology
- Benchmark results section with real M3 Max performance data
- Competitor comparison table: vs Adobe Podcast, Descript, Auphonic, iZotope RX 11
- CTA section with clone command and GitHub links
- Standalone HTML — deployable to Hostinger without dependencies

### 🔧 Backend
- Version bumped to 3.0.0 (FastAPI app + health endpoint)
- Sidebar version badge showing `v3.0.0 · M3 Max`
- All new files: `app/services/apple_acceleration.py`, `app/services/benchmark.py`


## [2.0.0] — 2026-04-17

### 🚀 Major — Processing Engine v2.0
- **Fixed metallic audio artifacts** across all filters
- **Noise Removal**: Capped prop_decrease at 0.85, added temporal (100ms) and frequency (500Hz) smoothing, wet/dry mixing
- **Studio Sound**: Broadcast-quality compression (25ms attack, 2:1 ratio, -18dB threshold), de-esser (6kHz -3dB), warmth boost (150Hz +1dB)
- **Specific Noise Filters**: Reduced aggressiveness for wind, static, and reverb removal
- **Speech Cleanup**: Breath removal capped at 80% with 30ms fades, improved mouth click detection
- **Super-Resolution**: Subtler harmonic blending (alpha 0.15), faster rolloff

### 🧠 AI — Ollama/Gemma Dynamic Tuning
- NEW: `get_dynamic_parameters()` — local Ollama/Gemma analyzes extracted audio features and tunes filter strength
- Heuristic fallback with 3-tier quality classification (clean/moderate/noisy)
- Safety caps: all strengths between 0.1 and 0.85

### 📊 System Monitor
- NEW: Real-time CPU, GPU, ANE, RAM, Power, Temperature monitoring
- psutil for CPU/RAM + macmon pipe for Apple Silicon GPU/ANE (no sudo)
- 60-second rolling history for sparkline charts
- API: `GET /api/system/stats`, `GET /api/system/history`

### 🌐 Edge Computing Cluster
- NEW: Turn Android smartphones into compute nodes via Termux
- Cluster manager with UDP auto-discovery and manual registration
- Parallel chunk processing with crossfade reassembly
- Automatic fallback to local processing on worker failure
- Setup script for Termux: `setup_worker.sh`
- API: `GET /api/cluster/status`, `POST /api/cluster/add`, `POST /api/cluster/remove`

### ⏱️ ETA Engine
- NEW: 16 per-filter benchmarks calibrated for M3 MAX
- ETA badges on preset cards and process button
- Live ETA refinement during processing via WebSocket

### 🌐 Landing Page
- NEW: Bilingual (EN/IT) landing page at `/landing`
- All 16+ modules detailed with technology tags
- Competitor comparison table: vs Adobe Podcast, Descript, Auphonic, iZotope RX 11

### 📦 Infrastructure
- Added `psutil`, `httpx` to requirements
- Installed `macmon` for Apple Silicon GPU monitoring
- Startup hooks for System Monitor and Cluster Manager

## [1.0.0] — 2026-04-06

### Initial Release
- 16 audio processing filters
- Whisper Large-v3 transcription
- Ollama/Gemma Smart Mode (content classification)
- Glassmorphism dark UI
- WebSocket real-time progress
- Smart presets (Podcast, Interview, Voice Memo, Music, Outdoor)
