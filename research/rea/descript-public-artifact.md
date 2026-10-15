# Descript: artefatto ufficiale e due worklet audio

Verifica del 15 ottobre 2026. Analisi statica parziale, senza installazione o esecuzione dell'applicazione.

## Identità e provenienza

Il pacchetto esaminato è **Descript 114.0.4-release.20250509.32955**, build del maggio 2025. È una versione vecchia servita dal percorso ufficiale di fallback: **non è stata identificata come versione corrente**.

La [pagina ufficiale Mac](https://www.descript.com/download/mac) distribuisce un piccolo installer. Nell'installer 2.2.0 (15), un'altra analisi della stessa indagine ha individuato il percorso `https://web.descript.com/download` agli offset `0xd060d` e `0x20aebd`. La richiesta HEAD a tale percorso, senza il parametro `v2`, ha risolto il [DMG ufficiale acquisito](https://electron.descript.com/Descript-114.0.4-release.20250509.32955.dmg).

| Artefatto | Dimensione | SHA-256 |
|---|---:|---|
| DMG | 277.497.888 byte | `7984bf53297200c74bbaabbdf5f90d094584022071991aeb434cbcd535ba388f` |
| `Contents/Resources/app.asar` | 180.259.254 byte | `c5eef40634674518ab21013a784f21ca861b3389701d5630af7ae1a61bc05e97` |
| NoiseGate worklet | 96.801 byte | `0be6f3f54f00507502b3b93569f135b03afd21eeea0f494a7c96bd92213354d9` |
| Transcription worklet | 1.084 byte | `aeff0d8305f1375990cee4b8001524de493a8e678dd56ecee566c87fa36786b9` |

L'acquisizione ha usato richieste GET pubbliche a intervalli di byte, con controllo del `Content-Range` e conservazione degli header. Alcuni intervalli interrotti sono stati ripresi; il DMG completo è stato ricomposto e sottoposto a SHA-256. Il [receipt](private/descript-full-2026-10-15/acquisition.json) conserva provenienza e hash dei singoli blocchi.

## Inventario e perimetro

Il volume è stato montato con `hdiutil attach -readonly -nobrowse` in un punto di montaggio privato. L'app contiene 257 file regolari, esclusi i collegamenti simbolici, per 617.643.857 byte logici; l'ASAR contiene 1.623 membri. Sono stati estratti soltanto due file JavaScript applicativi, il manifest e i metadati necessari. L'app completa non è stata copiata in `/Applications`.

L'eseguibile principale è Mach-O x86_64. Il plist del framework Electron dichiara `20.0.2`. Il manifest dichiara `beamcoder-prebuild@0.7.1-rc.18`; sono presenti `beamcoder.node` universale x86_64/arm64 e librerie della famiglia FFmpeg. La presenza nel pacchetto non prova quale percorso di elaborazione o esportazione le utilizzi.

REA 6.5.0 ha analizzato esclusivamente i due worklet estratti. Evidenza: `ev_e1ee94301b07d81b2b5bd381bf8f8b0144119c9cba649a89fee720ad525bdbc0`. Il grafo degli artefatti è completo **per questo sottoinsieme**; il grafo semantico è parziale per i limiti di 5.000 nodi per file e 10.000 complessivi. Le osservazioni seguenti derivano anche dalla lettura diretta del codice come testo inerte. Non è stata eseguita una prova audio.

## Osservazioni

**DS-001: Noise gate convenzionale.** Il worklet calcola l'RMS del canale e lo confronta con una soglia. Gestisce cinque stati: Closed, Opening, Open, Holding e Closing. Una funzione applica rampe lineari di guadagno durante apertura e chiusura. Questa evidenza descrive un gate; non dimostra un denoiser neurale, il funzionamento di Studio Sound o la qualità percepita.

**DS-002: Controlli e assunzione sul campionamento.** I descrittori espongono threshold, attack, hold e release, tutti con automazione `k-rate`. I valori predefiniti sono 0,1, 1 ms, 1 ms e 100 ms. I rispettivi intervalli sono 0-1, 0,1-10 ms, 0,1-100 ms e 50-500 ms. Il metodo di elaborazione converte i tempi in campioni usando la costante `44100`; il messaggio GainReduction restituisce lo stato del gate. Il collegamento al grafo principale e gli eventuali ricampionamenti non sono stati analizzati, quindi la costante non basta a dimostrare un difetto.

**DS-003: Acquisizione per la trascrizione.** Il worklet `transcription-processor` legge il primo canale del primo ingresso e converte campioni float in PCM16 little-endian. Accumula buffer da 131.072 byte, li trasferisce con `timeOffset` e `isDone`, emette `first-frame` e `no-data`, e invia un buffer quando riceve `stop`. Ogni invio incrementa l'offset temporale di `131072 / sampleRate / 2`. Il codice riguarda acquisizione e trasporto dei buffer: il riconoscimento vocale, la destinazione remota e la gestione a valle della coda parzialmente riempita restano sconosciuti.

I riferimenti sotto indicano offset a base zero, con fine esclusa, all'interno dei file estratti originali. La minificazione concentra il codice in poche righe.

| Evidenza | File | Riga | Byte |
|---|---|---:|---|
| RMS, rampe, enum | `NoiseGateProcessor.worklet.d1c672dbf1b48195db11.js` | 2 | 10.863-11.498 |
| Registrazione e stati | stesso file | 2 | 95.129-96.384 |
| Messaggi e costante 44100 | stesso file | 2 | 95.287-95.595 |
| Parametri | stesso file | 2 | 96.351-96.713 |
| Buffer per trascrizione | `TranscriptionAudioProcessor.worklet.54bd93cadb52c21f0212.js` | 1 | 19-994 |

Gli offset assoluti dei membri nell'ASAR, gli hash dei derivati e i percorsi delle evidenze REA sono nel [registro strutturato](descript-findings-2026-10-15.json).

## Limiti e chiusura

Restano aperti: versione attuale, effettivo uso di questi worklet, collegamenti al grafo audio, architettura e modelli di Studio Sound, backend di trascrizione, mappatura degli interventi sul testo verso l'audio, implementazione dell'esportazione e misure di qualità o latenza. Le osservazioni possono orientare esperimenti indipendenti su AudioEnhancer; non costituiscono una ricostruzione del prodotto.

Il [detach](private/descript-full-2026-10-15/detach.json) è terminato con codice 0 e risposta `"disk4" ejected.`; il punto di montaggio è risultato vuoto e un successivo inventario `hdiutil` ha confermato l'assenza del DMG tra le immagini montate. Nessuna app avviata, nessun account o trial attivato, nessuna modifica a `/Applications`. L'area privata finale contiene **102 file e occupa circa 281,2 MiB**, entro il budget di 2 GB. Il conteggio esatto dello spazio e le verifiche degli hash sono conservati nel [registro locale di chiusura](private/descript-full-2026-10-15/closure.json).
