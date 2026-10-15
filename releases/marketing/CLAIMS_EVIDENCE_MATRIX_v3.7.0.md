# AudioEnhancerMAX 3.7.0 — Claims and Evidence Matrix

Status date: 28 August 2026

This is the source of truth for launch copy. A public claim is approved only when the corresponding evidence is present in the 3.7 source and, for packaged-app claims, repeated on signed build 3.7.5.

## Approved product claims

| Public claim | Scope/boundary | Primary implementation evidence | Automated or package evidence | Status |
| --- | --- | --- | --- | --- |
| Runs in a native macOS window without opening the default browser | Mac App Store package | `desktop/native_window.py`, `desktop/launcher.py` | Native launch/lifecycle package test | Approved |
| Core service listens only on the Mac loopback interface | Default desktop launch | `desktop/launcher.py` binds `127.0.0.1` | Listener and native-Quit lifecycle check | Approved |
| Smart Enhance analysis is deterministic and local | Diagnosis and parameter selection only | `app/services/audio_intelligence.py`, `app/services/smart_mode.py` | `test_dynamic_tuning_is_deterministic_and_does_not_require_ollama` | Approved |
| Detects measurable risks including clipping, low level, broadband noise, silence, DC offset, bandwidth and possible hum | Diagnostic indicators, not restoration guarantees | `app/services/audio_intelligence.py` | `tests/test_audio_intelligence.py` | Approved with diagnostic wording |
| Three explainable Smart Enhance profiles | Conservative, Balanced, Maximum | `PROFILE_NAMES` in `app/services/audio_intelligence.py` | Profile safety test | Approved |
| Provides non-destructive, transcript-linked speech editing | Source is preserved; render creates a new output | `app/services/speech_editor.py`, speech editor API routes | Seven speech-editor tests | Approved |
| Only user-approved cut/mute decisions are rendered | Precision Editor path | `render_edl`, revision/decision API | `test_render_applies_only_approved_candidates` | Approved |
| Undo/redo persists in the local EDL history | Bounded persisted revision history | `app/services/speech_editor.py` | `test_manual_transcript_edit_can_be_undone_and_redone` | Approved |
| Five fixed delivery profiles | Podcast, YouTube/video, Audiobook, Lossless archive, Source-quality master | `app/services/output_profiles.py` | `tests/test_output_profiles.py` | Approved |
| Export overrides are validated and auditable | WAV/MP3/FLAC, normalization, loudness target | `resolve_output_profile` | Override validation tests and processing report | Approved |
| Generates a local per-job processing report | Processing and reviewed EDL exports | `app/services/processing_report.py` | Three processing-report tests | Approved |
| Reports actual engines and fallbacks | Availability depends on installed/package components | `app/services/capability_registry.py` | `test_registry_exposes_real_fallbacks` | Approved |
| Trusted-LAN processing is opt-in and off by default | Default runtime state and desktop autostart | `app/services/runtime_settings.py`, `app/main.py` | `test_trusted_lan_is_opt_in_by_default` | Approved |
| External service, Ollama and trusted-LAN permissions are independently controlled | Edge TTS is external; Ollama is a separate local process | Runtime settings API and gates | Privacy persistence test plus API-path checks | Approved |
| Faster-Whisper Medium transcription runs locally in the App Store package | Final package only; accuracy varies | `app/services/transcription.py`, bundled model configuration | Final-package transcription and asset inspection | Approved |
| Media decoding/encoding uses embedded PyAV FFmpeg libraries in the Store package | Store distribution only | `app/utils/audio_io.py`, capability registry | Package capability and WAV/FLAC decode checks | Approved |
| Delivery Compliance Lab provides measurable delivery guidance | Local guidance only; not certification | `app/services/delivery_compliance.py` | Four threshold, silence, and clipping tests | Approved with disclaimer |
| Project Capsule exports checksum-backed evidence | Processed output included; original audio opt-in | `app/services/project_bundle.py` | Manifest hash, source exclusion, ZIP content, and path-safety tests | Approved |
| Blind A/B records a user listening preference | Subjective review evidence, not an objective score | Blind A/B API and Review Deck | Mapping/reveal exercised in UI validation | Approved with subjective wording |
| The packaged filter path is JIT-free | Signed Mac runtimes exclude librosa, Numba, llvmlite and unsigned-executable-memory entitlements | `app/utils/signal_processing.py`, package requirements and spec | Package inspection plus notarized 12-step filter-chain test | Approved |
| 51 automated tests cover the 3.7 foundations and stability correction | Focused suite, not proof of every optional legacy engine | `tests/` | Project Python 3.11 test environment | Approved while count remains 51 |

## Claims that require qualification

| Avoid | Use instead | Reason |
| --- | --- | --- |
| “AI automatically fixes every recording” | “Smart Enhance measures common risks and proposes deterministic settings for review.” | Source damage and perceptual outcomes vary. |
| “Studio quality” | “Delivery profiles provide explicit loudness and format starting points.” | No controlled perceptual benchmark supports a universal quality grade. |
| “State of the art” | Name the actual component or algorithm and its boundary. | A broad leadership claim is not established by the current tests. |
| “100% private” | “Core DSP and packaged transcription run locally; optional external and LAN paths are disclosed and controlled.” | Edge TTS is network-dependent and local Ollama is a separate process. |
| “Completely offline” | “Core processing supports an offline/no-external-services workflow after packaged assets are present.” | Optional services and source-mode assets can require network access. |
| “Neural denoising included” | Use the capability registry result for the actual package. | The package may expose deterministic spectral gating instead of DeepFilterNet. |
| “Production-grade diarization” | “Speaker-change fallback is approximate when Pyannote is unavailable.” | Current fallback is heuristic. |
| “Restores missing frequencies” | “Deterministic bandwidth extension adds modeled harmonics; it does not recreate original information.” | Missing source information cannot be proven recovered. |
| “Available on the Mac App Store” | “Mac App Store candidate submitted/in review” until approval. | Store availability is Apple-controlled. |
| “Certified compliant” | “Measured against a transparent delivery target; workflow guidance, not certification.” | The app does not provide third-party or regulatory certification. |

## Evidence rules for campaign assets

1. Screenshots must come from the 3.7.5 packaged app, not the source server.
2. Demo audio must be owned or created by the developer, and the unprocessed input must be retained.
3. A/B examples must use level-matched playback where possible and identify the selected profile/options.
4. Performance numbers may be published only with Mac model, OS build, input duration/format, selected pipeline and sample count.
5. “Local” must identify whether it means in-process core DSP, packaged local model, separate local Ollama, or trusted LAN.
6. Claims about App Store availability, approval, rankings or awards require a public URL or current first-party record.

## Apple metadata basis

Apple requires metadata to accurately reflect the app’s core experience and says significant product changes must be described specifically in Review Notes and What’s New. This matrix is designed to support that requirement:

- https://developer.apple.com/app-store/review/guidelines/
- https://developer.apple.com/help/app-store-connect/reference/app-information/platform-version-information
