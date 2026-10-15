# AudioEnhancerMAX 3.8.2: App Store Metadata

Updated: 15 October 2026
Candidate build: 3.8.2

All fields use factual, non-comparative wording. Recheck character/byte limits in App Store Connect before submission.

## Name

```text
AudioEnhancerMAX
```

## Subtitle: maximum 30 characters

```text
Local audio, reviewed by you
```

## Promotional text: maximum 170 characters where available

```text
Verified processing checkpoints, revision-bound playback and exports, exact-format delivery checks, and portable Project Capsules.
```

## Keywords: maximum 100 bytes

```text
audio,enhance,podcast,transcribe,cleanup,voice,editor,local,whisper,loudness,recording
```

Do not add competitor names, unrelated trending terms, prices or unverifiable superlatives.

## Description: English

```text
AudioEnhancerMAX is a local-first audio production workspace for podcasters, interviewers, journalists, educators, researchers, and voice creators.

REVIEW BEFORE YOU RENDER

Smart Enhance measures common recording risks, including level, estimated noise, clipping, silence, bandwidth, DC offset, and possible mains hum, then proposes deterministic processing settings. The analysis runs locally and does not require a language model to control DSP.

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

## What is new in version 3.8.2

```text
- Completed audio results have distinct revisions, keeping playback, reviews and exports attached to the selected output.
- WAV, MP3 and FLAC delivery checks measure the exact exported file and record its SHA-256.
- Deterministic local DSP can resume from compatible checkpoints that verify source audio, settings, processing steps and application build.
- Changed or corrupt checkpoints restart cleanly. Reprocessing cannot reuse stale audio conversions or display a late result from another file.
- Speech-edit reviews, reports and Project Capsules follow the corresponding completed revision.
- Updated interface wording and public descriptions.

Core processing and bundled Faster-Whisper transcription run locally. Optional services remain independently controlled. Audio and transcript results depend on the source recording.
```

## Review Notes summary

Use the dedicated `releases/app-review/APP_REVIEW_NOTES_3.8.2_BUILD_3.8.2.md` after the final package validation. It should point the reviewer to:

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

1. **Diagnose before processing**: Local measurements explain the selected Smart Enhance profile.
2. **Review every speech edit**: Transcript-linked cut and mute decisions preserve the source.
3. **Undo, redo, then render**: Revisioned decisions keep the workflow reversible.
4. **Choose the delivery target**: Five fixed profiles make format and loudness explicit.
5. **See what actually ran**: Local processing reports disclose engines, options, warnings, and privacy state.
6. **Control every optional path**: External services, local Ollama, and trusted-LAN processing are independent.

## Localizzazione italiana

### Sottotitolo: massimo 30 caratteri

```text
Audio locale, sotto controllo
```

### Testo promozionale: massimo 170 caratteri dove disponibile

```text
Checkpoint DSP verificati, revisioni distinte, controlli sul file esportato e Project Capsule con evidenze locali.
```

### Keyword: massimo 100 byte

```text
audio,migliora,podcast,trascrivi,pulizia,voce,editor,locale,whisper,loudness,registrazione
```

### Descrizione: italiano

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

### Novità della versione 3.8.2: italiano

```text
- Ogni risultato audio completato ha una revisione distinta: riproduzione, confronti ed esportazioni seguono il risultato selezionato.
- I controlli di consegna WAV, MP3 e FLAC misurano il file effettivamente esportato e ne registrano lo SHA-256.
- Il DSP locale deterministico può riprendere da checkpoint compatibili che verificano sorgente, impostazioni, passaggi e build dell’app.
- I checkpoint incompatibili o corrotti ripartono da zero. Una nuova elaborazione non riutilizza conversioni obsolete e non mostra risposte tardive relative a un altro file.
- Revisioni del parlato, report e Project Capsule seguono il risultato completato corrispondente.
- Aggiornati i testi dell’interfaccia e le descrizioni del prodotto.

Elaborazione principale e trascrizione Faster-Whisper inclusa funzionano localmente. I servizi opzionali restano controllabili separatamente. I risultati dipendono dalla registrazione sorgente.
```

## Apple field references

- Platform metadata, field behavior and character limits: https://developer.apple.com/help/app-store-connect/reference/app-information/platform-version-information
- App name/subtitle and privacy policy URL requirements: https://developer.apple.com/help/app-store-connect/reference/app-information/app-information
- Accurate metadata and specific release-change requirements: https://developer.apple.com/app-store/review/guidelines/
