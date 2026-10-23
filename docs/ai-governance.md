# AI Governance Notes

AudioEnhancerMAX is designed as a local-first, AI-assisted audio tool. It is not an autonomous decision system and should not be presented as one.

## Core Principles

- Be explicit about where data goes.
- Preserve original media.
- Treat AI outputs as assistive, reviewable artifacts.
- Prefer measurable claims over broad marketing claims.
- Document optional external services when they are used.

## Data Flow Summary

| Function | Default Processing Location | External Data Transfer |
| --- | --- | --- |
| Upload and enhancement | Local host | None by default |
| Faster-Whisper transcription | Local host | None when models are local |
| Ollama/Gemma Smart Mode | Local host | None when Ollama runs locally |
| Kokoro TTS | Local host | None when installed locally |
| Edge Neural TTS | Microsoft Edge TTS service | Text is sent externally when selected |
| Android edge workers | Trusted LAN devices | Audio chunks are sent to selected worker devices |
| SourceForge badge | Browser to SourceForge | Browser requests badge metadata/script |

## Explainability Boundaries

### Music brief assistant (experimental channel)

Music prompts and original presets are assembled locally without a model. Optional
Ollama suggestions require the existing editorial permission and use a fixed loopback
connection. The separate lyrics field is excluded; the editable prompt is included.
Suggestions are kept separate until the user appends them and may conflict with creative
constraints, so review is required. This feature generates text only and does not call
MiniMax. See [data flow and limitations](music-brief-assistant.md).

### Version 3.8.3: privacy recovery and capsule evidence

Valid saved privacy preferences are preserved. Missing, unreadable or malformed preferences disable all three optional permissions until the user saves their choices: external services, local Ollama assistance and trusted-LAN processing. The settings panel explains the recovery state. This does not block downloads of transcription models or constitute a system-wide network firewall.

New speech renders retain the full edit list that produced their audio, including the source transcript and word timings available to the editor. A project capsule exports that snapshot, not a later draft or a newer transcription. Older renders without this evidence remain exportable with a warning; their missing history is not reconstructed from current decisions. Capsules for ordinary DSP output do not attach unrelated editorial drafts.

The capsule manifest records the selected audio revision. Each included file's SHA-256 and byte count are calculated from the same stream written to its ZIP entry. Processing location is `unknown` when the report is unavailable, invalid or not bound to the selected audio revision and master hash. These checks establish internal consistency, not trusted authorship, voice-owner consent, regulatory compliance or perceptual quality.

These changes are included in the direct 3.8.3/build 3.8.4 package. See the [packaged verification and its limits](../releases/DIRECT_BUILD_3.8.4.md). The separate App Store candidate remains 3.8.2/build 3.8.3.

The app can explain selected filters, preset options, timing estimates, and whether Smart Mode or dynamic tuning was used. It does not yet provide a full formal model card, confidence calibration report, or per-sample causal explanation for every DSP transformation.

For production governance, pair AudioEnhancerMAX output with:

- the original input file
- selected options or preset name
- transcript export, if used
- notes on any external engine, such as Edge Neural TTS
- human review of sensitive transcripts or speaker labels

## Claims Policy

Use these terms:

- `local-first`
- `AI-assisted`
- `optional external TTS`
- `trusted LAN workers`
- `measured on this hardware`

Avoid absolute claims unless they are true for the specific workflow:

- `100% local`
- `zero cloud`
- `unlimited`
- `perfect`
- `fully explainable`
- `guaranteed broadcast quality`
