# Music brief assistant

Status: implemented in the local feature branch, not included in an existing published
macOS package. The assistant prepares editable music prompts. It does not generate,
play, mix, or download music.

## Workflow

1. Open **Music brief** under AI Tools. No audio upload is needed.
2. Choose a preset and apply its directions: Podcast intro, Narration bed, Documentary
   arc, Calm focus, Energetic opener, or Acoustic story. The presets are original
   AudioEnhancerMAX content. Applying a preset preserves the description, lyrics and
   existing prompt; rebuild when ready to use the new directions.
3. Describe the music. Adjust the main and secondary styles, vocal mode, requested
   instruments, exclusions, target duration, optional BPM, and three section directions.
4. Select **Build brief**. The deterministic local builder creates Global Metadata,
   Vocal Details, and Arrangement. Edit the resulting prompt as needed.
5. Copy the current prompt or export JSON. The export keeps the original built prompt,
   edited prompt, source fields, separate lyrics, and any explicitly appended model
   suggestions with their model identity. Changes to the form require a rebuild before
   export so the prompt and its source fields remain consistent.

Tempo, duration and musical instructions are creative targets. This tool cannot verify
how a separate audio model follows them. A secondary style is an influence, not a
guarantee of a particular musical result.

## Optional local suggestions

Enable local Ollama editorial assistance in Settings, then use **Suggest refinements**.
The editable prompt and musical fields are sent to Ollama on `127.0.0.1:11434`. The
separate lyrics field is excluded. Text manually pasted into the prompt is part of the
request. An installed local model is required; no model is downloaded automatically.

The client excludes cloud-named models and checks selected-model metadata for remote
execution. Environment proxies and HTTP redirects are disabled for this connection.
The app does not control a modified or externally reconfigured Ollama installation.
No MiniMax or other generation API is contacted by this feature.

Suggestions appear separately. Review them for conflicts with your creative requirements
before explicitly appending them. They are not guaranteed to satisfy every constraint.
Changing the input or prompt invalidates pending suggestions. Failures and unavailable
models leave the existing draft intact. Requests are serialized; a second concurrent
refinement receives HTTP 409. Revoked permission prevents a new inference request and
discards a result returned after revocation; it cannot recall text already submitted.

Drafts live in the browser tab until copied or exported. There is no automatic draft
persistence or JSON re-import in this version. Exported JSON is a music-brief record,
not an audio Project Capsule or a ready-to-submit MiniMax API request.

## API

| Method | Endpoint | Behavior |
| --- | --- | --- |
| GET | `/api/music/presets` | Six original presets and their visible defaults |
| POST | `/api/music/brief` | Deterministic prompt construction, no model or network required |
| POST | `/api/music/refine` | Separate suggestions using an authorized local Ollama model |

`MusicBriefRequest` is defined in `app/models/music.py`. Description is required;
optional lyrics are retained exactly as received. The API accepts 1 to 12 named sections
in their supplied order, including repeated sections; the initial UI exposes three.
The refinement request wraps `brief` plus the current edited `caption`.

Validation failures return 422; unknown presets return 400. Refinement returns 403 for
disabled permission, 409 when busy, and 503 for missing local models, transport failures
or invalid model output. Responses state `text_only: true`; refinement additionally
states `review_required: true`. No failure is reported as a successful refinement.

## Design provenance

The feature was informed by the structured-caption and section-planning concepts in
[MiniMax Music 3's skill documentation](https://github.com/MiniMax-AI/MiniMax-Music3/blob/945655064d59b98004dd70002e7eb5c8c6e11373/skills/README.md).
Implementation and preset text are original. No upstream template library, skill files,
model weights or inference code are redistributed. No MiniMax compatibility or endorsement
is asserted. A future music-generation integration requires its own runtime, license,
privacy and audio-quality evaluation.

Ollama requests follow its [chat API](https://docs.ollama.com/api/chat), using structured
JSON output without streaming. Model suggestions are editorial proposals, not measured
audio facts.

## Verification

Focused backend tests cover source preservation, bounded inputs, local-only construction,
permission checks, cloud model exclusion, malformed responses, request contention and
transport limits. Frontend tests cover stale results, privacy changes, failure recovery
and current-content export. See exact results and browser evidence in the
[validation record](music-brief-validation-2026-10-23.md). No macOS rebuild, signing, publication or audio generation
is implied by these source-level checks.
