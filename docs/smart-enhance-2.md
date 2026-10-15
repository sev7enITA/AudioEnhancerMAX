# Smart Enhance 2.0

Smart Enhance 2.0 is AudioEnhancerMAX's deterministic local diagnosis and recommendation layer. It measures the signal, proposes an explainable processing chain, and records which engine or fallback is used.

## User workflow

1. Upload an audio file.
2. Open **Smart Enhance**.
3. Choose **Conservative**, **Balanced**, or **Maximum**.
4. Review the quality score, measured issues, evidence and proposed steps.
5. Apply the profile, process the file, and compare Original/Processed.
6. Download the JSON Quality Report from the completion bar.

Smart Enhance profiles never enable filler removal, stutter removal, hesitation removal or other destructive timeline edits. Those operations are routed to Precision Speech Editor, where every candidate remains set to Keep until the user approves it.

## Technical contract

- `POST /api/smart-mode/{file_id}?profile=balanced` returns diagnosis, all profiles, the selected options and the resolved processing engines.
- `GET /api/system/capabilities` reports packaged engines and their actual fallback modes.
- `GET /api/reports/{file_id}` returns the evidence generated after a completed processing job.
- Analysis uses representative start/middle/end sections for long-form files and never transmits audio.
- SNR, hum, bandwidth and quality score are signal-derived estimates, not laboratory measurements.
- Ollama/Gemma may generate explicitly requested editorial text but never selects DSP parameters.

## Quality report

The report includes:

- input and output measurements;
- detected issues and recommendations;
- active steps and resolved engines;
- fallback/heuristic warnings;
- processing options and elapsed time;
- an explicit local-processing privacy declaration.

The quality score is intended for before/after comparison and regression detection. It is not a guarantee of subjective sound quality or speech intelligibility.
