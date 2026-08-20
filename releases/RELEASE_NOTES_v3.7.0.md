# AudioEnhancerMAX 3.7.0

Release date: 20 August 2026
Mac App Store candidate build: 3.7.2
Target: Apple Silicon, macOS 13 or later

## Release headline

**Local-first audio production, now reviewable from diagnosis to export.**

AudioEnhancerMAX 3.7 is a substantial workflow release. It moves the app from a collection of processing tools toward a reviewable production environment: the app diagnoses measurable audio risks, proposes deterministic processing, lets the user approve transcript-linked edits, records what happened, and exports through explicit delivery profiles.

## Eight foundations delivered

### 1. Smart Enhance 2

- Measures level, estimated signal-to-noise ratio, clipping, silence, DC offset, spectral balance, bandwidth and possible 50/60 Hz hum locally.
- Offers Conservative, Balanced and Maximum processing profiles.
- Selects DSP parameters from deterministic measurements; Ollama/Gemma does not control the processing chain.
- Discloses the engine or fallback actually available in the installed distribution.

Smart Enhance is assistive analysis, not a guarantee that damaged source audio can be perfectly reconstructed. Results should be reviewed with A/B listening.

### 2. Precision Speech Editor

- Links Faster-Whisper word timestamps to an Edit Decision List (EDL).
- Generates review candidates for filler words, repetitions, pauses, breaths and mouth sounds.
- Supports manual word/range selections for `cut` or duration-preserving `mute` decisions.
- Defaults candidates to Keep; only user-approved changes are rendered.
- Provides original/proposed preview, persisted bounded undo/redo, and JSON/CSV EDL export.
- Preserves the uploaded source and renders edits to a new output.

### 3. Native macOS experience

- Runs inside an AudioEnhancerMAX-owned AppKit window powered by WKWebView.
- Does not open the default web browser.
- Uses the AudioEnhancerMAX application menu and product-specific About window instead of Python identity.
- Uses native Open and Save panels for sandbox-safe file access.
- Starts a private service on `127.0.0.1` and terminates it when the app quits or its main window closes.

### 4. Explicit delivery profiles

Five fixed starting profiles reduce export guesswork:

- Podcast: lossless WAV, normalized to -16 LUFS.
- YouTube/video: WAV, normalized to -14 LUFS.
- Audiobook: lossless WAV, normalized to -18 LUFS.
- Lossless archive: FLAC with source loudness preserved.
- Source-quality master: WAV with source loudness preserved.

WAV/MP3/FLAC, normalization and target-loudness overrides are validated and recorded in the processing report.

### 5. Processing and governance reports

- Creates a local JSON report for processed and speech-edited exports.
- Records input/output summaries, selected options, resolved output profile, actual pipeline engines, warnings and privacy state.
- Presents a readable, printable report in the interface while retaining the canonical JSON download.
- Records whether optional external or trusted-LAN processing was used.

Quality indicators are diagnostic summaries, not laboratory certification or an objective promise of perceptual improvement.

### 6. Enforceable runtime boundaries

- Independent settings control external services, local Ollama editorial assistance and trusted-LAN processing.
- Trusted-LAN discovery and processing are disabled by default.
- Core DSP and packaged Faster-Whisper transcription remain local.
- Microsoft Edge Neural TTS is optional and sends only user-entered synthesis text after an explicit request.
- Local Ollama is optional and restricted to editorial prose/expressive rewrite assistance.
- The capability registry reports packaged engines, fallbacks and unavailable features instead of presenting them as universally available.

### 7. Delivery Compliance Lab

- Measures integrated loudness using the BS.1770 method, plus a 4× oversampled true-peak estimate, sample clipping, sample rate, channels, and duration.
- Provides transparent targets for podcast, online video, audiobook, EBU R128 broadcast, source-master, and archive workflows.
- Returns rule-level pass, warning, or failure evidence and preserves the result locally.
- Clearly labels the result as workflow guidance rather than regulatory or third-party certification.

### 8. Evidence Chain, Project Capsule, and Review Deck

- Records SHA-256 provenance for the original and processed artifacts.
- Exports a portable ZIP containing the processed output and available processing report, compliance result, transcript, EDL, and blind A/B decision.
- Excludes original audio from the capsule by default; inclusion requires an explicit user choice.
- Adds a focused Review Deck for delivery checks, randomized blind A/B listening, evidence inspection, and capsule export.
- Stores blind A/B results as subjective user-review evidence, never as an objective quality score.

## Packaging changes

- Marketing version is `3.7.0`; the current App Store candidate is build `3.7.2`.
- The App Store package targets native arm64 and macOS 13 or later.
- Faster-Whisper Medium and Silero VAD assets are bundled for local transcription without runtime model download.
- PyAV provides embedded FFmpeg libraries for media decoding and encoding in the Store distribution.
- The package contains the privacy manifest, sandbox entitlements, third-party notices and component licenses.
- Demucs source separation and Kokoro voice cloning are not exposed in the Mac App Store build when their required runtime assets are unavailable.
- The separate SourceForge DMG is signed with Developer ID Application, uses hardened runtime and secure timestamps, and was accepted by Apple notarization and stapled on 20 August 2026.
- Gatekeeper accepts both the stapled DMG and its enclosed app as `Notarized Developer ID`; notarization submission ID: `0dfffff8-8d97-4fcf-bb3b-01f5dbeda7e2`.
- The SourceForge Android worker asset is version 1.2.0 (`versionCode` 3) and remains explicitly labelled as a debug companion build.

## Compatibility and boundaries

- Apple Silicon only for the current macOS package.
- Core source execution remains available on supported Python environments, but packaged capability availability can differ.
- Transcript accuracy depends on language, recording quality, overlap and source conditions; high-stakes transcripts require human review.
- Deterministic bandwidth extension does not recreate original missing information.
- Approximate MFCC speaker-change fallback must not be marketed as production-grade neural diarization.
- App Store availability must not be claimed until Apple approves the submitted build.

## Validation evidence

The final 3.7.2 source is covered by 26 automated tests, including delivery-threshold, silence, clipping, SHA-256 manifest, source opt-in, ZIP path-safety, and 16 kHz AutoEQ signal-preservation checks. The signed 3.7.2 package passed signature, payload, native launch, local processing, Delivery Compliance, blind A/B evidence, Project Capsule, local Faster-Whisper transcription, and native lifecycle validation. On 20 August 2026 the direct-download DMG additionally passed Apple notarization, stapling, Gatekeeper assessment, deep signature verification, arm64 inspection, bundle-identifier verification, and version verification. Transporter processing, TestFlight installation, and Apple review remain separate Apple-controlled gates for the Mac App Store package.

See:

- `releases/marketing/CLAIMS_EVIDENCE_MATRIX_v3.7.0.md`
- `releases/marketing/APP_STORE_METADATA_v3.7.0.md`
- `releases/marketing/LAUNCH_CAMPAIGN_v3.7.0.md`
- `CHANGELOG.md`
