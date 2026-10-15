# AudioEnhancerMAX 3.7.0 — Social and Email Copy

> For publication after 28 August 2026, use the updated and status-qualified
> copy in `COMUNICATI_STAMPA_2026-08-28_IT.md` or
> `PRESS_RELEASES_2026-08-28_EN.md`. The Reddit section in the Italian file is
> written as a substantive follow-up to the July r/AudioAI post rather than a
> duplicate launch announcement.

Replace `[LIVE URL]` only after the release channel is actually live.

## Copy italiana — post di lancio

```text
AudioEnhancerMAX 3.7 nasce da un principio: l’automazione può proporre, ma sei tu a decidere cosa entra nell’output.

Smart Enhance deterministico, editing collegato alla trascrizione, controlli di consegna misurabili, A/B cieco e Project Capsule con evidenza SHA-256, ora in una vera finestra Mac.

[LIVE URL]
```

## Copy italiana — LinkedIn

```text
Molti strumenti audio chiedono di fidarsi del risultato. Con AudioEnhancerMAX 3.7 ho voluto rendere verificabile l’intero flusso.

Smart Enhance misura localmente i problemi comuni e propone impostazioni deterministiche. Precision Speech Editor trasforma i timestamp della trascrizione in decisioni reversibili di taglio o silenziamento. Cinque profili rendono espliciti formato e loudness. Un report locale registra motori, opzioni, avvisi, privacy e modifiche approvate. Il Delivery Compliance Lab controlla loudness, true peak stimato, clipping e sample rate; l’A/B cieco non rivela l’originale prima della scelta; il Project Capsule raccoglie le evidenze con hash SHA-256 e lascia fuori l’audio originale per impostazione predefinita.

Su macOS l’app funziona ora in una finestra nativa, mantiene il servizio principale su 127.0.0.1 e lo chiude insieme all’app. TTS esterno, Ollama locale e worker LAN rimangono percorsi opzionali, separati e dichiarati.

AudioEnhancerMAX 3.7: ascolta il cambiamento, verifica ogni decisione.

[LIVE URL]
```

## Email italiana — lancio

Oggetto:

```text
AudioEnhancerMAX 3.7 — ascolta il cambiamento, verifica ogni decisione
```

Corpo:

```text
AudioEnhancerMAX 3.7 è disponibile su [LIVE URL].

Le principali novità:

• Smart Enhance misura localmente i rischi più comuni e propone impostazioni deterministiche.
• Precision Speech Editor rende reversibili e verificabili le modifiche collegate alla trascrizione.
• Cinque profili fissi esplicitano loudness e formato di consegna.
• I report locali mostrano opzioni, motori effettivi, avvisi, privacy e modifiche approvate.
• L’app Mac si apre in una finestra nativa e mantiene il proprio servizio privato sul Mac.

Risultati audio e trascrizioni dipendono sempre dalla sorgente: gli output importanti vanno controllati. Questo limite non è nascosto, ma fa parte del prodotto.

Note di rilascio: [LIVE URL]
```

## Launch post — compact

```text
AudioEnhancerMAX 3.7 is built around one idea: automation may propose, but you review what becomes part of the output.

New: deterministic Smart Enhance, transcript-linked editing, local delivery checks, blind A/B listening, and SHA-256 Project Capsules—all inside a native Mac window.

Build 3.7.5 fixes the macOS filter crash by removing the packaged librosa/Numba/llvmlite JIT path. The notarized app completed a 12-step filter chain without crashing and preserved the input duration.

[LIVE URL]
```

## Launch post — technical

```text
AudioEnhancerMAX 3.7 turns audio cleanup into a traceable workflow:

• deterministic local diagnosis and DSP selection
• Faster-Whisper word timestamps
• revisioned, non-destructive cut/mute EDL
• five fixed output profiles with auditable overrides
• per-job engine/privacy report
• loudness, estimated true-peak, clipping, and sample-rate delivery guidance
• randomized blind A/B and checksum-backed Project Capsule export
• loopback-only native Mac shell

No “magic quality” claims—just visible decisions and evidence.

[LIVE URL]
```

## LinkedIn post

```text
Most audio tools ask you to trust the output. With AudioEnhancerMAX 3.7, I wanted the workflow itself to be reviewable.

Smart Enhance measures common recording risks locally and proposes deterministic settings. The Precision Speech Editor links transcription timestamps to reversible cut or mute decisions. Five delivery profiles make format and loudness explicit. A local report records what actually ran, including engines, warnings, privacy state, and approved edits.

The Mac application now runs in its own native window, keeps its core service on 127.0.0.1, and closes that service with the app. Optional external TTS, local Ollama assistance, and trusted-LAN workers remain separately disclosed and controlled.

AudioEnhancerMAX 3.7: hear the change, see every decision.

[LIVE URL]
```

## Community/Reddit post

```text
I’m the developer of AudioEnhancerMAX, an MIT-licensed local-first audio workspace. Version 3.7 is a substantial change, and I’d value technical feedback on the workflow rather than promotional votes.

The new foundation includes deterministic audio diagnosis, three Smart Enhance profiles, a revisioned transcript-linked cut/mute EDL, five fixed delivery profiles, and a local per-job processing report. Ollama does not choose DSP parameters. Trusted-LAN processing is off by default, and optional external TTS is independently gated.

I’ve published the implementation boundaries and claim-to-test matrix here: [LIVE URL]

Areas where feedback would be particularly useful: word-timestamp edit precision, cut vs mute ergonomics, delivery-profile defaults, and what evidence belongs in a processing report.
```

Disclose affiliation and follow each community’s self-promotion rules. Do not request upvotes or coordinated reviews.

## Three-post launch thread

```text
1/ AudioEnhancerMAX 3.7 is now a reviewable audio workflow, not just a filter dashboard. Smart Enhance diagnoses locally; the user approves the result.

2/ Precision Speech Editor connects word timestamps to reversible cut/mute decisions. Preview, keep/apply, undo/redo, export the EDL, and preserve the source.

3/ Five delivery profiles + a local processing report make output choices and actual engines visible. Optional external/LAN paths remain explicit. Details: [LIVE URL]
```

## Pre-launch email

Subject options:

```text
AudioEnhancerMAX 3.7: every edit becomes reviewable
A new local-first workflow is coming to AudioEnhancerMAX
From audio diagnosis to export—with an audit trail
```

Body:

```text
AudioEnhancerMAX 3.7 is nearly ready.

This release is centered on control: deterministic Smart Enhance profiles, transcript-linked cut and mute decisions, persisted undo/redo, five delivery profiles, and a local report that records what actually ran.

The Mac app also runs in its own native window without opening the browser. Core DSP and packaged transcription remain local, while optional external, Ollama, and trusted-LAN paths are separately controlled.

I’ll share the verified build, release notes, and a complete evidence matrix when the release channel is live.
```

## Launch email

Subject:

```text
AudioEnhancerMAX 3.7 — hear the change, see every decision
```

Body:

```text
AudioEnhancerMAX 3.7 is available at [LIVE URL].

What changed:

• Smart Enhance now measures common audio risks locally and proposes deterministic settings.
• Precision Speech Editor makes transcript-linked cut/mute decisions reversible and reviewable.
• Five fixed delivery profiles make loudness and format choices explicit.
• Per-job reports disclose selected options, actual engines, warnings, privacy state, and approved edits.
• The Mac app runs in an AudioEnhancerMAX-owned native window and keeps its private service on this Mac.

Audio and transcript results still depend on the source material, so important outputs should be reviewed. That boundary is part of the product—not hidden in the small print.

Release notes: [LIVE URL]
```
