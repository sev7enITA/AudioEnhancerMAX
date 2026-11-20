# Revision-bound processing and delivery (3.8)

Processing and speech-edit rendering return `revision` and an immutable `output_url`. Preserve that revision when requesting downloads, compliance, reviews and capsules. Old output URLs remain readable, but APIs reject a superseded revision with 409. A processed request never silently returns the original.

- `GET /api/download/{id}?version=processed&format=mp3&revision=...` resolves the current revision's MP3. Response headers include `X-Audio-Revision`, `X-Audio-SHA256` and `Cache-Control: no-store`.
- `GET /api/compliance/{id}?version=speech_edit&format=flac&revision=...&target_id=podcast` measures those exact encoded bytes and returns `artifact_sha256`, `format`, `size_bytes`, `revision` and `version`.
- `GET /api/reports/{id}?version=processed&revision=...` retrieves the immutable master report; conversions have separate format-specific compliance evidence.
- `POST /api/reviews/{id}/blind-ab` and `POST /api/projects/{id}/export` accept `output_version` (`processed` or `speech_edit`) and `revision`. Capsule requests also accept `format`. Source audio remains opt-in.

The UI measures the chosen format before downloading and labels the completed revision. A new operation invalidates the prior UI result immediately. Changing controls alone does not reprocess audio; a completed revision describes the previous successful operation until Process is pressed.

## Workspace action history

The local history records imports, completed analysis, spectral previews, saved speech decisions, rendering outcomes and prepared exports. The SHA-256 of the uploaded bytes links repeated imports with identical content. Names, playback activity and suggestions alone do not link assets. Downloading the original returns the bytes uploaded, including the original container when the workspace uses a decoded copy.

Each render records its revision ID, output fingerprint, and the exact processing-report fingerprint when available. The report distinguishes completed steps from steps that changed the signal in a sample and sample-rate comparison. A reused checkpoint and work attributed only to a group of distributed filters carry their own evidence status.

The C2PA-signed copy embeds the applicable source link, observed processing for the exported revision, and the SHA-256 of its processing report. The local timeline also includes events independent of that signed copy, such as analysis, preview and other revisions. The signed assertion excludes private paths, transcript text and watermark identifier values.

## Checkpoint contract

The identity combines original bytes, requested and resolved/tuned options, step order, app version/build, engine inventory and DSP package versions. Diagnosis and tuning always run on the original. Snapshots retain the exact float dtype and samples, have SHA-256 receipts and an atomic metadata pointer. Only valid ordered prefixes can resume. Legacy WAV snapshots, corruption or an identity change restart cleanly.

Neural/model-dependent and trusted-LAN execution paths restart rather than assert an unverified model/worker identity. Run one backend worker per data directory. Completed outputs are retained; disk cleanup is a separate user-controlled operation.

## Tests and limits

`python -m pytest -q` passed 75 cases; `node --test tests/test_review_state.cjs` passed 4 on 15 October 2026. Thirteen audio/API cases use generated fixtures. Three repeated deterministic normalization runs had a zero decoded-sample difference in this runtime; interrupted/resumed DSP matched the corresponding clean run. This is a measured fixture baseline, not a universal hash/null threshold or a perceptual-quality claim.

Aligned residual playback and independently exposed stems are not included in this release.
