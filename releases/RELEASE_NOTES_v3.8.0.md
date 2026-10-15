# AudioEnhancerMAX 3.8.0

Release date: 15 October 2026. Source and direct macOS release line.

This release makes processing, review and export refer to the same completed audio revision.

## What changed

- Verified local DSP checkpoints include source SHA-256, requested and effective options, ordered steps, application build and runtime versions. Dynamic tuning always examines the original. Float snapshots preserve pipeline precision; legacy, corrupt or incompatible checkpoints restart cleanly.
- Resumption is deliberately disabled for model-dependent and trusted-LAN paths whose complete execution identity is not established.
- Every processed or speech-edited result has an immutable revision. WAV/MP3/FLAC conversions belong to that revision. Requests for a superseded revision return HTTP 409; a missing processed result returns HTTP 404.
- Delivery guidance measures the selected encoded format and records its SHA-256, size, operation and revision. Project Capsules and blind A/B decisions use the corresponding output. A/B remains a subjective preference.
- Starting a new run clears the previous result from review and download controls. Late responses cannot replace evidence for another result.
- REA 6.5.0 research tooling and documented competitor observations are included for developers. Commercial artifacts remain private and excluded. Static analysis is not a claim of DSP equivalence or superior audio quality.
- Previously local JIT-free macOS fixes, personal-voice adapter support and corrected process telemetry are preserved in the repository. Optional engines still depend on installed runtimes and assets.
- The web runtime updates FastAPI, Starlette, python-multipart and multidict. The validated installed build environment reports no known advisories in the 15 October 2026 pip-audit snapshot; this is not a general security certification.

## Validation

75 Python tests and 4 JavaScript state tests passed, including 13 new audio/API regression cases. Tests cover interrupted runs, compatible resumption, changed options/source/build, corrupt snapshots, three-run deterministic repeatability, stale conversions, primary-format changes, stereo conversion, missing-output errors, exact download/compliance hash binding, speech-edit capsules and concurrent-job rejection. The repeatability fixture is synthetic and does not establish perceptual quality on real recordings.

## Distribution status

The 3.8.0 direct-download DMG is a Developer ID build for Apple Silicon, macOS 13+. Apple notarization currently returns HTTP 403 because the developer team must accept an updated agreement. Until notarization succeeds, the new macOS artifact is an explicitly labelled preview; the existing notarized 3.7.0 remains the stable macOS download. No new Mac App Store submission or approval is claimed.

## Operational notes

Keep a single backend worker per data directory. Completed revisions are retained so existing playback URLs remain valid; they consume local disk space. Old pre-revision outputs are adopted using their most recent modification time; rerun processing if the provenance of a legacy result is uncertain. Reports distinguish processing-master facts from export-format delivery measurements. The source is never overwritten.

Aligned residual listening and separately exposed stems remain research work, not delivered features. No competitor proprietary code or models are bundled.
