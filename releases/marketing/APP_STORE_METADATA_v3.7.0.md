# AudioEnhancerMAX 3.7.0 — App Store Metadata

Prepared: 15 August 2026
Candidate build: 3.7.4

All fields use factual, non-comparative wording. Recheck character/byte limits in App Store Connect before submission.

## Name

```text
AudioEnhancerMAX
```

## Subtitle — maximum 30 characters

```text
Local audio, reviewed by you
```

## Promotional text — maximum 170 characters where available

```text
New in 3.7: reviewable speech editing, local delivery checks, blind A/B listening, SHA-256 evidence, and portable project capsules.
```

## Keywords — maximum 100 bytes

```text
audio,enhance,podcast,transcribe,cleanup,voice,editor,local,whisper,loudness,recording
```

Do not add competitor names, unrelated trending terms, prices or unverifiable superlatives.

## Description — English

```text
AudioEnhancerMAX is a local-first audio production workspace for podcasters, interviewers, journalists, educators, researchers, and voice creators.

REVIEW BEFORE YOU RENDER

Smart Enhance measures common recording risks—including level, estimated noise, clipping, silence, bandwidth, DC offset, and possible mains hum—then proposes deterministic processing settings. The analysis runs locally and does not require a language model to control DSP.

EDIT SPEECH NON-DESTRUCTIVELY

The Precision Speech Editor links local transcription timestamps to reviewable cut and mute decisions. Inspect filler words, repetitions, pauses, breaths, and mouth sounds; preview original and proposed regions; keep or apply each decision; undo or redo revisions; and render to a new output while preserving the source.

DELIVER WITH EXPLICIT PROFILES

Start from five fixed profiles for podcasts, video, audiobooks, lossless archives, and source-quality masters. Validated format and loudness overrides are recorded in the processing report.

KNOW WHAT RAN

Each processing job can produce a readable report with input/output indicators, selected options, resolved profile, pipeline engines, warnings, and privacy state. The canonical JSON remains available for audit and reproducibility.

REVIEW DELIVERY EVIDENCE

The Delivery Compliance Lab measures loudness, estimated true peak, clipping, and sample rate against transparent workflow targets. Randomized blind A/B listening helps you compare before revealing the source. Export a checksum-backed Project Capsule with the processed output and available evidence; original audio remains excluded unless you explicitly include it. Compliance results are workflow guidance, not certification.

LOCAL-FIRST WITH CLEAR BOUNDARIES

The macOS app runs in its own native window and starts a private loopback service on this Mac. Core DSP and packaged Faster-Whisper transcription run locally. Optional Microsoft neural text-to-speech, separate local Ollama assistance, and trusted-LAN workers are disclosed and independently controlled. Trusted-LAN processing is off by default.

Audio results and transcript accuracy depend on the source material. Review important outputs before publication or professional use.

Requires an Apple silicon Mac with macOS 13 or later.
```

## What’s New in Version 3.7

```text
AudioEnhancerMAX 3.7 introduces a reviewable workflow from diagnosis to export.

• Smart Enhance 2 measures common audio risks locally and proposes deterministic Conservative, Balanced, or Maximum settings.
• Precision Speech Editor links transcript words to non-destructive cut/mute decisions with preview, persisted undo/redo, and JSON/CSV EDL export.
• Five fixed delivery profiles cover podcast, video, audiobook, lossless archive, and source-quality master workflows.
• Local processing reports record input/output indicators, selected options, actual engines, warnings, privacy state, and approved speech edits.
• Independent controls gate optional external TTS, separate local Ollama assistance, and trusted-LAN processing; LAN discovery is off by default.
• The Mac app now runs in an AudioEnhancerMAX-owned native window without opening the default browser and closes its private loopback service when the app quits.
• Delivery Compliance Lab measures loudness, estimated true peak, clipping, and sample rate against transparent workflow targets; results are guidance, not certification.
• The Review Deck adds randomized blind A/B listening and a portable Project Capsule with SHA-256 evidence; original audio is excluded by default.
• The App Store package includes the local Faster-Whisper Medium model, Silero VAD, embedded media libraries, privacy manifest, and component notices.

Results depend on the source recording. Review important audio and transcripts before use.
```

## Review Notes summary

Use the dedicated `releases/app-review/APP_REVIEW_NOTES_3.7.0_BUILD_3.7.4.md` after the final package validation. It should point the reviewer to:

1. native launch and About;
2. developer-owned sample upload through the Open panel;
3. Smart Enhance diagnosis and deterministic profile;
4. A/B comparison and explicit export profile;
5. Precision Editor decision, undo/redo and render;
6. local Faster-Whisper transcription;
7. processing report and privacy controls;
8. Delivery Compliance Lab, randomized A/B review and Project Capsule export;
9. native Quit and loopback port release.

## Screenshot captions

1. **Diagnose before processing** — Local measurements explain the selected Smart Enhance profile.
2. **Review every speech edit** — Transcript-linked cut and mute decisions preserve the source.
3. **Undo, redo, then render** — Revisioned decisions keep the workflow reversible.
4. **Choose the delivery target** — Five fixed profiles make format and loudness explicit.
5. **See what actually ran** — Local processing reports disclose engines, options, warnings, and privacy state.
6. **Control every optional path** — External services, local Ollama, and trusted-LAN processing are independent.

## Localizzazione italiana

### Sottotitolo — massimo 30 caratteri

```text
Audio locale, sotto controllo
```

### Testo promozionale — massimo 170 caratteri dove disponibile

```text
Novità 3.7: Smart Enhance deterministico, editing da trascrizione, cinque profili di consegna, report locali e controlli privacy espliciti.
```

### Keyword — massimo 100 byte

```text
audio,migliora,podcast,trascrivi,pulizia,voce,editor,locale,whisper,loudness,registrazione
```

### Descrizione — italiano

```text
AudioEnhancerMAX è uno spazio di produzione audio local-first per podcaster, intervistatori, giornalisti, docenti, ricercatori e creator vocali.

CONTROLLA PRIMA DI ESPORTARE

Smart Enhance misura localmente rischi comuni della registrazione, tra cui livello, rumore stimato, clipping, silenzi, banda, offset DC e possibile ronzio di rete. Propone quindi impostazioni deterministiche: nessun modello linguistico controlla la catena DSP.

MODIFICA IL PARLATO SENZA DISTRUGGERE LA SORGENTE

Precision Speech Editor collega i timestamp della trascrizione locale a decisioni di taglio o silenziamento. Puoi esaminare filler, ripetizioni, pause, respiri e rumori della bocca, confrontare originale e proposta, annullare o ripristinare revisioni ed esportare un nuovo file preservando la sorgente.

CONSEGNA CON PROFILI ESPLICITI

Parti da cinque profili fissi per podcast, video, audiolibri, archivi lossless e master alla qualità sorgente. Le modifiche a formato e loudness sono validate e registrate nel report.

VEDI COSA È STATO ESEGUITO

Ogni lavorazione può produrre un report leggibile con indicatori input/output, opzioni selezionate, profilo risolto, motori effettivi, avvisi e stato privacy. Il JSON canonico resta disponibile per audit e riproducibilità.

LOCAL-FIRST, CON CONFINI CHIARI

L’app macOS funziona in una finestra nativa e avvia un servizio privato loopback sul Mac. DSP e trascrizione Faster-Whisper inclusa funzionano localmente. Microsoft TTS opzionale, Ollama locale separato e worker LAN fidati sono dichiarati e controllabili in modo indipendente. La LAN fidata è disattivata per impostazione predefinita.

I risultati audio e l’accuratezza della trascrizione dipendono dalla sorgente. Controlla sempre gli output importanti.

Richiede un Mac Apple silicon con macOS 13 o successivo.
```

### Novità della versione 3.7 — italiano

```text
AudioEnhancerMAX 3.7 introduce un flusso verificabile dalla diagnosi all’esportazione.

• Smart Enhance 2 misura localmente i rischi comuni e propone impostazioni deterministiche Conservative, Balanced o Maximum.
• Precision Speech Editor collega le parole trascritte a decisioni non distruttive di taglio/silenziamento, con anteprima, undo/redo persistente ed export EDL JSON/CSV.
• Cinque profili fissi coprono podcast, video, audiolibri, archivi lossless e master alla qualità sorgente.
• I report locali registrano indicatori, opzioni, motori effettivi, avvisi, privacy e modifiche approvate.
• Controlli indipendenti regolano TTS esterno, Ollama locale e worker LAN; la LAN è disattivata per impostazione predefinita.
• L’app Mac usa ora una finestra nativa AudioEnhancerMAX senza aprire il browser e chiude il servizio privato loopback all’uscita.
• Il pacchetto App Store include Faster-Whisper Medium, Silero VAD, librerie multimediali, privacy manifest e avvisi dei componenti.

I risultati dipendono dalla registrazione sorgente: controlla audio e trascrizioni importanti prima dell’uso.
```

## Apple field references

- Platform metadata, field behavior and character limits: https://developer.apple.com/help/app-store-connect/reference/app-information/platform-version-information
- App name/subtitle and privacy policy URL requirements: https://developer.apple.com/help/app-store-connect/reference/app-information/app-information
- Accurate metadata and specific release-change requirements: https://developer.apple.com/app-store/review/guidelines/
