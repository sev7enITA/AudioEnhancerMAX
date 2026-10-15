# AudioEnhancerMAX: Technology & State-of-the-Art Audit

**Data del report:** 14 agosto 2026
**Prodotto esaminato:** AudioEnhancerMAX 3.5.2, build Mac App Store 3.5.5
**Ambito:** algoritmi audio, ASR, diarizzazione, TTS, SLM, accelerazione Apple Silicon, dipendenze, ricerca sperimentale asiatica ed early-adopter community.

## Verdetto esecutivo

AudioEnhancerMAX **non utilizza oggi lo stato dell'arte in modo uniforme**. La base DSP e l'architettura local-first sono valide, ma diverse funzioni avanzate sono implementate con modelli ormai superati, euristiche, fallback semplici oppure motori opzionali che non fanno parte della build Mac App Store.

La valutazione corretta è:

| Area | Stato agosto 2026 | Verdetto |
|---|---|---|
| DSP, I/O e loudness | Maturo e affidabile | Buona base, non elemento differenziante SOTA |
| Trascrizione locale | Faster-Whisper Medium, CPU int8 | Solida, ma non più SOTA per accuratezza o Apple Silicon |
| Riduzione rumore nella build Store | DeepFilterNet non incluso; fallback `noisereduce` | Non SOTA |
| Pulizia parlato | Whisper + regole lessicali/spettrali | Utile ma prevalentemente euristica |
| Diarizzazione nella build Store | pyannote 3.1 opzionale/non incluso; fallback MFCC | Non competitiva |
| TTS nella build Store | Microsoft Edge TTS esterno; Kokoro bloccato | Non local-first e non SOTA |
| Smart Mode / SLM | Gemma via Ollama su feature numeriche | SLM moderno, integrazione audio debole |
| Separazione sorgenti | Demucs opzionale e non incluso nello Store | Modello precedente alla generazione RoFormer |
| Super-resolution | AudioSR opzionale; fallback armonico | Fallback non neurale, non SOTA |
| Watermarking | Spread spectrum/LSB proprietario | Dimostrativo, non robusto allo standard attuale |
| Runtime Apple Silicon | PyTorch MPS + CTranslate2 CPU | Funziona, ma non sfrutta pienamente MLX/Core ML/ANE |
| Riproducibilità build | `requirements.txt` divergente dal payload | Da correggere prima di accelerare la roadmap |

In breve: **il prodotto ha una buona ossatura, ma oggi è più “ampio” che “profondo”**. Espone molte capacità, mentre solo una parte di esse dispone di un motore realmente moderno, incluso, verificato e riproducibile nella build distribuita.

## 1. Cosa usa realmente la build Mac App Store

L'audit ha confrontato sorgente, script di build e indice ricorsivo dell'archivio PyInstaller contenuto nel `.pkg` firmato.

### Componenti verificati nel payload

- Faster-Whisper e CTranslate2, con modello **Whisper Medium** incluso nel bundle.
- Silero VAD incluso come asset ONNX di Faster-Whisper.
- PyTorch 2.11.0 e torchaudio 2.11.0.
- NumPy 1.26.4, SciPy 1.17.1 e librosa 0.11.0.
- Pedalboard e `noisereduce` presenti nell'archivio Python.
- Kokoro ed Edge TTS presenti nel payload Python, anche se Kokoro viene disabilitato esplicitamente in modalità App Store.
- FastAPI 0.135.3, Uvicorn 0.44.0, Pydantic 2.12.5 e PyAV 17.0.0.

### Motori non inclusi o non attivi nella build Store

- DeepFilterNet non è presente nel payload: `remove_noise` passa quindi a spectral gating con `noisereduce`.
- Demucs non è incluso e `keep_music` viene rifiutato in modalità App Store.
- pyannote non è incluso: la diarizzazione ricade sul fallback MFCC/energia.
- AudioSR non risulta parte della build: la “frequency restoration” ricade sull'estensione armonica deterministica.
- Ollama/Gemma è un processo/app esterno, non un motore incorporato.

### Problema di riproducibilità

`requirements.txt` dichiara, fra gli altri, Faster-Whisper 1.1.0, FastAPI 0.115.6, Uvicorn 0.34.0, SciPy 1.14.1, librosa 0.10.2.post1 e Pedalboard 0.9.16. Il payload firmato contiene versioni differenti per diverse dipendenze. Lo script di build installa solo i requisiti PyInstaller/PyObjC e usa il resto dell'ambiente `venv` già esistente.

Conseguenza: due build avviate dallo stesso commit possono contenere librerie diverse. Prima di qualsiasi upgrade algoritmico serve un lockfile completo, hashato e distinto per il canale Mac App Store.

## 2. Analisi per capacità

### 2.1 Riduzione rumore ed enhancement

Il sorgente prova DeepFilterNet e, se non disponibile, usa spectral gating. Nella build esaminata DeepFilterNet non è incluso; quindi il comportamento reale è `noisereduce` con smoothing e dry/wet mix. È un fallback sensato e conservativo, ma non è un denoiser neurale di frontiera.

DeepFilterNet 0.5.6 resta una scelta efficiente per elaborazione real-time, ma l'ultima release ufficiale risale al 2023. Nel frattempo [ClearerVoice-Studio](https://github.com/modelscope/ClearerVoice-Studio), sviluppato dal gruppo Alibaba/ModelScope, offre MossFormer2 a 48 kHz, FRCRN, separazione, target-speaker extraction e speech super-resolution in una piattaforma Apache-2.0. Il relativo [paper del 2025](https://arxiv.org/abs/2506.19398) lo presenta come toolkit orientato al trasferimento dalla ricerca al deployment.

Per due profili differenti meritano un bake-off:

- **Post-produzione ad alta qualità:** ClearerVoice/MossFormer2 48 kHz.
- **Real-time leggero:** DeepFilterNet 3, [DPDFNet](https://github.com/ceva-ip/DPDFNet) ONNX/TFLite o [RNNoise](https://github.com/xiph/rnnoise).

Nessuno deve essere scelto dal README o da una demo. La selezione va fatta su audio italiano reale, rumore non stazionario, riverbero e speaker interferenti, misurando anche la WER dopo enhancement per evitare un audio gradevole ma meno intelligibile.

### 2.2 Trascrizione e forced alignment

Faster-Whisper è ancora un runtime valido: la release corrente 1.2.1 mantiene i vantaggi di CTranslate2 e quantizzazione CPU. Il limite non è principalmente la libreria, ma il checkpoint Whisper Medium e l'esecuzione CPU-only.

Ad agosto 2026 i candidati più importanti sono:

- [Qwen3-ASR 0.6B/1.7B](https://github.com/QwenLM/Qwen3-ASR), Apache-2.0, 52 lingue e dialetti, timestamp/forced alignment e streaming. Il [technical report](https://arxiv.org/abs/2601.21337) dichiara la versione 1.7B SOTA fra gli ASR open-source valutati.
- [NVIDIA Parakeet-TDT 0.6B v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3), CC-BY-4.0, 25 lingue, punteggiatura e timestamp. È molto efficiente, ma le community riportano che v2 e v3 possono scambiarsi la leadership a seconda del dominio: va misurato sul nostro corpus.
- [SenseVoiceSmall](https://github.com/QwenAudio/SenseVoice), particolarmente interessante per cinese, cantonese, inglese, giapponese e coreano, con language ID, emotion recognition e audio-event detection. Non è un sostituto universale per l'italiano, ma è un ottimo backend regionale e un segnale della direzione multimodale.
- [WhisperKit](https://github.com/detail-co/WhisperKit), soluzione Core ML nativa per mantenere Whisper ma spostare l'inferenza su CPU/GPU/ANE Apple.

Raccomandazione: mantenere Whisper Medium come baseline di compatibilità e confrontarlo prima con Qwen3-ASR 0.6B quantizzato e WhisperKit/Core ML. Parakeet va incluso nel benchmark, soprattutto per velocità e long-form, ma senza assumere superiorità universale.

### 2.3 Pulizia di filler, esitazioni, stutter, respiri e mouth clicks

Queste funzioni non costituiscono oggi una pipeline ML SOTA:

- Filler words: word timestamps Whisper + dizionario fisso inglese/italiano.
- Esitazioni: qualsiasi pausa fra 0,5 e 2 secondi viene ridotta a 150 ms.
- Stuttering: vengono rimosse ripetizioni di parole identiche; le ripetizioni sillabiche non sono realmente rilevate.
- Respiri: soglie su RMS, centroide spettrale e zero-crossing rate.
- Mouth sounds: spectral flux e interpolazione locale.

Sono algoritmi trasparenti e leggeri, ma possono produrre falsi positivi e non modellano contesto linguistico, sovrapposizioni o intenzione espressiva. La direzione corretta non è sostituirli tutti con un LLM: serve una **Edit Decision List non distruttiva**, confidenza calibrata, anteprima A/B e approvazione utente. Per i timestamp va valutato Qwen3 ForcedAligner; per i detector acustici servono classificatori dedicati addestrati/validati su respiri e mouth clicks.

### 2.4 Diarizzazione

Il codice usa `pyannote/speaker-diarization-3.1`, ma il modello non è incluso nella build Store. Il fallback divide l'audio in blocchi MFCC e alterna al massimo due speaker: è una demo funzionale, non una diarizzazione affidabile.

Opzioni attuali:

- [pyannote Community-1](https://huggingface.co/pyannote/speaker-diarization-community-1) con pyannote.audio 4.x. La model card dichiara un miglioramento netto rispetto a 3.1 e offre anche una timeline “exclusive” più facile da riconciliare con ASR. Il modello è CC-BY-4.0 ma l'accesso richiede accettazione delle condizioni: la redistribuzione nel Mac App Store va verificata per iscritto.
- [NVIDIA Streaming Sortformer 4spk v2.1](https://huggingface.co/nvidia/diar_streaming_sortformer_4spk-v2.1), CC-BY-4.0, progettato per diarizzazione online e speaker cache.
- [DiariZen](https://github.com/BUTSpeechFIT/DiariZen) e [WeSpeaker](https://github.com/wenet-e2e/wespeaker) sono candidati early-adopter, ma richiedono un audit separato di licenze, pesi, conversione e qualità su Apple Silicon.

Per il prossimo rilascio non va mostrata la diarizzazione come funzione “AI completa” se il backend effettivo è il fallback MFCC.

### 2.5 TTS

La build Store espone Microsoft Edge TTS, che richiede un servizio esterno; Kokoro è incluso nel payload ma bloccato in modalità App Store. Questo è incoerente con il posizionamento completamente locale e aumenta comunque il peso del pacchetto.

Kokoro resta eccellente per velocità e footprint, ma il 2026 ha spostato la frontiera verso:

- [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS), Apache-2.0, 0.6B/1.7B, streaming, voice design, voice cloning e italiano. Il [technical report](https://arxiv.org/abs/2601.15621) descrive controllo fine e cloning da circa tre secondi.
- [Fun-CosyVoice 3](https://github.com/FunAudioLLM/CosyVoice), 0.5B, nove lingue incluso l'italiano, streaming bidirezionale e latenza dichiarata fino a 150 ms.
- Fish Audio S2 Pro, molto forte qualitativamente e sostenuto dalla community, ma con **Fish Audio Research License**, quindi non è la prima scelta per una distribuzione commerciale senza parere legale.
- [MOSS-TTS-Nano](https://github.com/OpenMOSS/MOSS-TTS-Nano), interessante come esperimento CPU/edge, non ancora scelta predefinita di produzione.

Per AudioEnhancerMAX la prima prova dovrebbe essere Qwen3-TTS 0.6B quantizzato, con consenso esplicito per voice cloning, watermark automatico dei contenuti sintetici e test specifici sull'italiano.

### 2.6 Smart Mode e SLM

Il codice preferisce Gemma 4 via Ollama, ma non invia l'audio al modello. Calcola una manciata di feature con librosa (RMS, centroide, banda, tempo, ZCR e rapporto di silenzio) e chiede al modello testuale di classificarle o scegliere valori di intensità.

Gemma 4 è moderno; l'integrazione non lo è. Un LLM non aggiunge informazione acustica a sei statistiche e può produrre confidenze non calibrate. Inoltre Ollama è un'app esterna e la build Store deve restare pienamente funzionale senza di essa.

Direzioni migliori:

1. Classificatore audio dedicato o embedding audio per content/noise scene detection.
2. Modello audio-native locale solo se incorporato e benchmarkato.
3. SLM testuale limitato a spiegazione, ordinamento di suggerimenti e generazione di report; mai come fonte unica di parametri DSP.
4. Output JSON validato con schema, versionamento del prompt e test deterministici.

[Gemma 4](https://ai.google.dev/gemma/docs/core) e i modelli Ollama possono restare nel canale direct/experimental. Per il Mac App Store conviene una pipeline Core ML/MLX incorporata oppure un comportamento interamente deterministico.

### 2.7 Separazione sorgenti

Demucs/HTDemucs resta utile e la build Store lo esclude, ma non rappresenta più da solo la frontiera della separazione musicale. I modelli Band-Split e Mel-Band RoFormer hanno superato Demucs in molti benchmark di music source separation. Il riferimento pratico più attivo è [Music-Source-Separation-Training](https://github.com/ZFTurbo/Music-Source-Separation-Training), mentre i paper [BS-RoFormer](https://arxiv.org/abs/2309.02612) e [Mel-Band RoFormer](https://arxiv.org/abs/2310.01809) documentano il salto architetturale.

Questi modelli sono però pesanti e spesso distribuiti tramite checkpoint community con provenienza/licenze non uniformi. Non vanno inseriti nello Store finché non sono verificati pesi, dataset, licenza commerciale e memoria su Mac base.

### 2.8 Super-resolution e bandwidth extension

La build non include AudioSR. Il fallback ricampiona e copia armoniche attenuate sopra il Nyquist originale: può aggiungere “aria”, ma non ricostruisce informazione e può creare contenuto artificiale.

I candidati più credibili sono ClearerVoice/MossFormer2 SR e [UniverSR](https://arxiv.org/abs/2510.00771), che dichiara un modello unico per speech, musica e suoni ambientali. Entrambi richiedono un test percettivo cieco: le metriche spettrali da sole premiano facilmente alte frequenze inventate.

### 2.9 Watermarking

L'attuale schema spread-spectrum/LSB non dispone di un benchmark di robustezza contro AAC/MP3, resampling, crop, time-stretch, denoise, mix e neural resynthesis.

La baseline moderna è [AudioSeal](https://github.com/facebookresearch/audioseal), MIT anche per i pesi, localizzazione temporale e streaming. [Perth](https://github.com/resemble-ai/Perth) è un'altra alternativa MIT con più tecniche. Anche questi sistemi non sono invulnerabili; [AudioMarkBench](https://arxiv.org/abs/2406.06979) mostra perché la robustezza deve essere misurata contro rimozione e forgery.

Per contenuti TTS sintetici, il watermark dovrebbe diventare automatico e accompagnato da metadata/provenance, non presentato come protezione assoluta.

## 3. Ricerca asiatica ed ecosistemi early-adopter

La ricerca precedente sul progetto non aveva documentato in modo sistematico questi ecosistemi. Questo audit li include esplicitamente.

### Cina e ModelScope

- Alibaba/Qwen: Qwen3-ASR, Qwen3-TTS, SenseVoice e FunASR.
- Alibaba Speech Lab/ModelScope: ClearerVoice-Studio, MossFormer2, FRCRN, WeSpeaker e CosyVoice 3.
- OpenMOSS/MOSI: MOSS-TTS-Nano e modelli MOSS per sintesi leggera.
- Fish Audio: Fish Speech S2, molto seguito ma con licenza da trattare con cautela.
- Xiaomi MiMo: segnali interessanti per ASR bilingue/dialetti e voice stack, ancora da validare indipendentemente.

Questa area è oggi particolarmente forte in ASR multilingue/dialettale, TTS controllabile, speech enhancement e deployment tramite ModelScope/FunASR.

### Giappone e Corea

Il segnale più rilevante per il prodotto non è un singolo checkpoint nazionale, ma l'adozione rapida di Qwen, SenseVoice e runtime Swift/MLX per giapponese e coreano. Il progetto [speech-swift](https://github.com/soniqo/speech-swift) documenta un'intera pipeline Apple Silicon; va considerato sperimentale, non dipendenza di produzione senza benchmark e audit del codice.

Per la Corea, i nuovi benchmark [KVoiceBench/KOpenAudioBench/KMMAU](https://arxiv.org/abs/2605.27984) mostrano che la semplice traduzione di benchmark inglesi non preserva accenti, paralinguistica e vincoli della lingua. Questo principio vale anche per l'italiano: non possiamo dichiarare qualità sulla base di LibriSpeech o benchmark cinesi.

### Apple-Silicon early adopters

- [MLX](https://github.com/ml-explore/mlx), framework Apple per memoria unificata e inferenza nativa.
- [mlx-audio](https://github.com/Blaizzy/mlx-audio) e [mlx-speech](https://github.com/appautomaton/mlx-speech), hub sperimentali per Qwen3, Fish, CosyVoice, Kokoro e altri modelli.
- [Qwen3-ASR Swift/MLX](https://github.com/moona3k/mlx-qwen3-asr) e implementazioni Swift community.
- [WhisperKit](https://github.com/detail-co/WhisperKit), opzione più matura per Core ML e Whisper.

Questi repository sono radar tecnologico, non una distinta base da copiare. Gli issue aperti riportano ancora OOM su audio lunghi, problemi di cache e regressioni di alcuni modelli MLX.

## 4. Cosa emerge da Reddit e dalle community cutting edge

Reddit è stato usato come fonte di segnali e problemi reali, non come prova scientifica.

- Le community Apple Silicon stanno convergendo su Qwen3-ASR/TTS, MLX/Core ML e pipeline Swift native; esempi includono discussioni su [speech-swift](https://www.reddit.com/r/iOSProgramming/comments/1s5v29h/open_source_swift_library_for_ondevice_speech_ai/) e [Qwen3-ASR Swift](https://www.reddit.com/r/Qwen_AI/comments/1r3ixmk/i_opensourced_qwen3asrswift_native_ondevice_asr/).
- I test reali di diarizzazione continuano a segnalare errori con overlap e speaker emotivi anche nei modelli moderni; [Community-1 migliora 3.1 ma non risolve tutto](https://www.reddit.com/r/LocalLLaMA/comments/1qieb5n/best_diarization_model/).
- I progetti emergenti come [Transcria](https://www.reddit.com/r/speechtech/comments/1unepso/transcria_yet_another_opensource_transcription/) combinano preflight acustico, più backend ASR, pyannote/Sortformer e DNSMOS invece di affidarsi a un unico modello.
- La community TTS distingue nettamente Kokoro, rapido e leggero, da modelli più espressivi/clonabili come Qwen3-TTS, CosyVoice, Fish e Chatterbox; non esiste un vincitore universale.
- Per il denoise real-time, sviluppatori e live sound continuano a usare DeepFilterNet/RNNoise/ONNX per latenza e stabilità, mentre modelli più grandi vengono preferiti offline.

Conclusione community: **backend modulari e benchmark per dominio battono la ricerca del “modello migliore” universale**.

## 5. Architettura Apple Silicon raccomandata

Apple dichiara che [Core ML](https://developer.apple.com/documentation/CoreML) sfrutta CPU, GPU e Neural Engine minimizzando memoria e consumo. [MLX](https://github.com/ml-explore/mlx) è il framework Apple più interessante per sperimentazione e porting rapido. PyTorch MPS resta supportato, ma porta nel bundle un runtime molto grande e non garantisce che tutti gli operatori usino il percorso più efficiente.

Target raccomandato:

1. **Core ML / Swift per motori stabili da distribuire**, specialmente VAD, ASR e piccoli classificatori.
2. **MLX per prototipi e modelli generativi**, con promozione a produzione solo dopo stabilità long-form e memory profiling.
3. **ONNX Runtime + CoreML EP** per modelli di enhancement esportabili, usando cache del modello e profiling del compute plan.
4. PyTorch solo per motori che non possono ancora essere convertiti, idealmente nel canale direct o in un helper ben isolato.

Questa migrazione ridurrebbe il pacchetto, che oggi è circa 1,7 GiB, e migliorerebbe cold start, uso memoria e integrazione nativa.

## 6. Vincoli Mac App Store

Le [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/) richiedono app self-contained, sandboxed e prive di download/esecuzione di codice che introduca nuove funzionalità (2.5.2). Una risorsa modello non è automaticamente “codice”, ma un modello che abilita una funzione non visibile in review o una dipendenza da un'app esterna aumenta il rischio.

Regole operative per AudioEnhancerMAX:

- Ogni motore dichiarato nella scheda Store deve essere incluso e funzionare senza Ollama, Homebrew o download manuali.
- Modelli opzionali sperimentali vanno nel canale direct finché il flusso Store non è stato chiarito con Apple.
- Licenza del codice e licenza dei pesi devono essere registrate separatamente.
- Funzioni disabilitate nello Store non devono gonfiare il payload né apparire come disponibili.
- I modelli incorporati devono avere checksum, versione, provenienza, third-party notice e test offline.

## 7. Benchmark gate prima di cambiare modello

Nessun componente deve essere definito SOTA senza superare la baseline su un corpus versionato.

### Corpus minimo

- Italiano e inglese; almeno 100 clip autorizzate.
- Podcast, intervista, voice memo, esterno, musica sotto voce e riunione.
- Rumore stazionario/non stazionario, riverbero, clipping, banda telefonica e speaker sovrapposti.
- Mac M1 base, M3 Max e una macchina con memoria intermedia.

### Metriche

| Capacità | Metriche obbligatorie |
|---|---|
| Denoise | DNSMOS P.835 SIG/BAK/OVRL, STOI, PESQ dove applicabile, WER post-enhancement, RTF, peak RAM |
| ASR | WER/CER, language ID, timestamp error, hallucination rate, RTF, peak RAM, cold start |
| Diarizzazione | DER, JER, overlap F1, speaker-count accuracy |
| TTS | MOS umano, UTMOS come supporto, WER del testo risintetizzato, speaker similarity, time-to-first-audio |
| Source separation | SI-SDR/SDR, bleed vocale, test d'ascolto cieco |
| Super-resolution | test ABX/MOS, intelligibilità, falsi armonici, aliasing |
| Watermark | detection/bit error dopo AAC, MP3, resample, crop, time-stretch, mix, denoise e neural codec |
| Prodotto | dimensione bundle, primo avvio, energia, stabilità su file lunghi, comportamento offline |

### Regola di promozione

Un nuovo backend entra nella build Store solo se:

1. migliora la qualità sul corpus interno;
2. non degrada in modo sostanziale WER/intelligibilità;
3. rientra nei budget di memoria, tempo e dimensione;
4. ha licenza e pesi redistribuibili;
5. passa test offline e sandbox;
6. ha fallback esplicito e UI che mostra il motore realmente usato.

## 8. Roadmap raccomandata

### P0: 1/2 settimane: verità del prodotto e riproducibilità

- Creare `requirements-app-store.lock` con versioni e hash reali.
- Generare automaticamente SBOM e inventory dei modelli dal `.pkg`.
- Mostrare nella UI il motore effettivo, incluso ogni fallback.
- Rinominare badge “ML/AI” quando la funzione è euristica.
- Eliminare dal payload Kokoro e altri moduli bloccati nello Store.
- Aggiungere il benchmark harness e il corpus manifest.

### P1: 3/5 settimane: backend modulari

- Interfacce comuni per ASR, denoise, diarizzazione, TTS e watermark.
- Capability registry derivato dal bundle, non da flag statici.
- Report per job con modello, versione, parametri, local/external e metriche.
- EDL non distruttiva per filler, respiri, mouth clicks e stutter.

### P2: 6/9 settimane: bake-off tecnico

- ASR: Whisper Medium vs WhisperKit vs Qwen3-ASR 0.6B; Parakeet v3 come challenger.
- Denoise: noisereduce vs DeepFilterNet vs DPDFNet vs ClearerVoice 48 kHz.
- Diarizzazione: Community-1 vs Sortformer v2.1 vs DiariZen, dopo audit licenze.
- Apple runtime: PyTorch/MPS vs MLX vs Core ML/ANE.

### P3: 10/12 settimane: candidati differenzianti

- Qwen3-TTS 0.6B italiano, locale, con consenso cloning e watermark.
- AudioSeal per TTS generato.
- ClearerVoice/UniverSR solo se vincono il test percettivo.
- Smart Mode basato su detector acustici e qualità misurata; SLM solo come spiegatore.

## 9. Decisione consigliata

Non conviene inserire contemporaneamente tutti i nuovi modelli. La sequenza con il miglior rapporto impatto/rischio è:

1. **Riproducibilità + benchmark + capability truth.**
2. **Qwen3-ASR/WhisperKit bake-off**, perché trascrizione e timestamp alimentano più funzioni.
3. **Denoiser neurale realmente incluso**, perché oggi la build Store usa spectral gating.
4. **Diarizzazione reale**, eliminando il fallback presentato come funzione completa.
5. **TTS locale italiano + AudioSeal**, con governance della clonazione.
6. **Migrazione progressiva Core ML/MLX**, riducendo dipendenza e peso di PyTorch.

Questa roadmap trasformerebbe AudioEnhancerMAX da raccolta di strumenti con fallback a piattaforma audio locale misurabile, modulare e difendibile davanti sia agli utenti sia ad App Review.

## Fonti principali e criterio di affidabilità

Sono state privilegiate model card ufficiali, repository originali, documentazione Apple/PyTorch/ONNX e paper. Reddit e community sono usati soltanto per individuare regressioni, casi reali ed early-adopter signal.

- [Qwen3-ASR repository](https://github.com/QwenLM/Qwen3-ASR) e [technical report](https://arxiv.org/abs/2601.21337)
- [Qwen3-TTS repository](https://github.com/QwenLM/Qwen3-TTS) e [technical report](https://arxiv.org/abs/2601.15621)
- [SenseVoice](https://github.com/QwenAudio/SenseVoice) e [FunASR](https://github.com/modelscope/FunASR)
- [ClearerVoice-Studio](https://github.com/modelscope/ClearerVoice-Studio)
- [CosyVoice](https://github.com/FunAudioLLM/CosyVoice)
- [pyannote Community-1](https://huggingface.co/pyannote/speaker-diarization-community-1)
- [NVIDIA Sortformer v2.1](https://huggingface.co/nvidia/diar_streaming_sortformer_4spk-v2.1)
- [WhisperKit](https://github.com/detail-co/WhisperKit)
- [Apple MLX](https://github.com/ml-explore/mlx), [Core ML](https://developer.apple.com/documentation/CoreML) e [ONNX CoreML EP](https://onnxruntime.ai/docs/execution-providers/CoreML-ExecutionProvider.html)
- [AudioSeal](https://github.com/facebookresearch/audioseal) e [AudioMarkBench](https://arxiv.org/abs/2406.06979)
- [Apple App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)

---

**Aggiornamento richiesto:** questo audit va rieseguito prima di ogni major release e almeno una volta al trimestre. La classifica dei modelli deve derivare dal benchmark interno versionato, non da claim dei vendor o dal numero di stelle GitHub.

## Nota di avanzamento post-audit: 14 agosto 2026

Le prime remediation sono state implementate nel sorgente dopo l'ispezione del pacchetto firmato: capability registry derivato dai moduli realmente disponibili, Smart Enhance 2.0 deterministico, profili Conservative/Balanced/Maximum, quality report per job e Precision Speech Editor con EDL revisionata e non distruttiva. Ollama/Gemma non controlla più i parametri DSP. Questa nota descrive il sorgente successivo all'audit; le conclusioni sul `.pkg` 3.5.2 build 3.5.5 restano valide finché non viene generata e verificata una nuova build.
