# Precision Speech Editor

Precision Speech Editor converts speech-cleanup detections into a non-destructive Edit Decision List (EDL). Analysis never modifies the uploaded source, and every candidate defaults to **Keep**.

## Detectors

- Filler words and phrases: Faster-Whisper word timestamps and confidence.
- Repeated words: adjacent normalized word match.
- Excess pauses: measured gaps between word timestamps while preserving a natural 150ms gap.
- Possible breaths: local spectral heuristic with a duration-preserving mute proposal.
- Possible mouth clicks: local spectral-flux heuristic with a short duration-preserving mute proposal.

Breath and mouth-click detections are candidates, not factual labels. The UI discloses the detector and confidence for every item.

## Workflow

1. Upload audio and open **Precision Editor**.
2. Run local analysis and wait for word-level transcription.
3. Listen to **Original** and **Proposed** for each candidate.
4. Leave the decision at Keep or explicitly select Apply.
5. Render approved edits to a new WAV file.
6. Compare Original/Processed and export the reviewed result.

## API

- `POST /api/speech-editor/analyze` creates a new EDL.
- `GET /api/speech-editor/{file_id}` retrieves the saved EDL.
- `PATCH /api/speech-editor/{file_id}` saves decisions with optimistic revision checks.
- `GET /api/speech-editor/{file_id}/preview/{candidate_id}?mode=original|applied` streams a local WAV preview.
- `POST /api/speech-editor/{file_id}/render` renders approved edits while retaining the original source.

The EDL is stored as `{file_id}_speech_edl.json` in private application output storage. Revision mismatches return HTTP 409 so one stale interface cannot overwrite more recent decisions.

Approved word and pause candidates use equal-power `cut` joins. Acoustic candidates use `mute`, preserving timeline duration with short boundary fades. Every render also updates the canonical processing report with EDL revision, approved counts, action types, quality indicators and source-preservation evidence.

## Current limitations

- Syllabic stutters are not comprehensively detected.
- Acoustic breath and click detectors are heuristic and require listening review.
- Editing currently produces a flattened output; project interchange formats are planned for a later release.
