# Antinode Clear 1.1.6: prima analisi nativa

15 ottobre 2026. Analisi statica del pacchetto macOS ufficiale, senza installazione o esecuzione del plug-in. Le osservazioni descrivono questo artefatto; non attestano qualità audio, prestazioni o equivalenza con AudioEnhancer.

## Artefatto e provenienza

La [pagina ufficiale di download](https://antinodeaudio.com/clear-download) espone il [percorso macOS](https://clear.api.supertone.ai/api/installer?platform=darwin&arch=arm64), che restituisce un redirect temporaneo al pacchetto. È stato conservato il percorso stabile, non il link firmato temporaneo.

| Elemento | Identità |
| --- | --- |
| Pacchetto acquisito | 134.568.452 byte; SHA-256 `6eb6bb93906bdc0df6f4de6275c98bd74609e5e25f203002c628965f917ea85f` |
| Versione dai plist AU/VST/VST3/AAX | `1.1.6`, identificatore `com.supertone.vcd3` |
| Binario VST3 selezionato | 65.167.024 byte; SHA-256 `8bb9eae3a5c49b48318dde907403c16156962631b8862d74079e4955d0b5fa2f` |
| Architetture | x86_64 e arm64; la vista REA seleziona arm64 |
| Slice arm64 | offset nel container `34340864`, dimensione `30826160`, UUID `1C7AE49F-2C9F-3835-91C9-BC43FB414A29` |
| REA Mach-O Evidence | `ev_b0935a50d672a615ffbb356d5ba2ce5e140a560c28b770b3efcb2a718b4f5755` |

`pkgutil --check-signature` ha verificato firma Developer ID Installer Supertone Inc. e notarizzazione Apple, timestamp 26 agosto 2026. `codesign --verify --strict` sul binario VST3 ha restituito codice zero. Questi controlli identificano distribuzione e integrità, non correttezza dell'algoritmo.

L'espansione con `pkgutil --expand-full` ha prodotto 44 file, circa 261 MB, nelle cartelle di ricerca. Non sono stati eseguiti script dell'installer. Il materiale è in `private/clear-1.1.6-2026-10-15/`; l'evidenza REA completa in `private/runs/antinode-clear-20261015T034053Z-sk5yk3re/`.

## Osservazioni e limiti

| ID | Osservazione statica | Evidenza e limite |
| --- | --- | --- |
| CLEAR-01 | Sono esportate due famiglie di API, `voiceclarity` e `voiceclarity_eco`, con creazione/distruzione, sample rate, buffer, latenza, elaborazione e svuotamento dei buffer. | Export REA: `voiceclarity__speech_enhancer__process` a `0xb033bc`, `process_separated` a `0xb035bc`; famiglia eco presente nella stessa vista. Il nome eco non misura il risparmio CPU e non dimostra quale modalità usi una sessione. |
| CLEAR-02 | La funzione pubblica della latenza chiama una funzione Rust `SpeechEnhancer::latency`; il calcolo usa anche buffer corrente e dimensione ottimale. | Disassemblaggio LLVM arm64 a `0xb03370` e `0xb0ec10`, verificato insieme ai getter: buffer a offset struttura `0x360`, dimensione ottimale a `0x50`. È evidenza ottenuta con LLVM, distinta da REA. Non sono stati misurati millisecondi né latenza end-to-end nell'host. |
| CLEAR-03 | Il wrapper `process_separated` suddivide l'ingresso in blocchi e prepara più buffer opzionali prima della chiamata interna omonima. | Disassemblaggio LLVM a `0xb035bc`, chiamata a `0xb0ece4`. I nomi dei componenti e le loro proprietà di ricostruzione non sono dimostrati dal solo wrapper. |
| CLEAR-04 | Sono presenti simboli ONNX/protobuf, stringhe ONNX Runtime e riferimenti a moduli Rust per buffer, STFT e PQMF. | Export/import, stringhe e percorsi di compilazione nel binario. I nomi di file modello candidati sono indizi; non provano architettura completa, pesi attivi o ordine del grafo DSP. Non sono stati estratti o riutilizzati pesi nel prodotto. |

REA avverte che import ed export uniscono `dyld_info` e `nm`: i simboli rimossi o nascosti possono mancare; gli elenchi non sono esaustivi. La vista raccoglie 27 dipendenze, ma la presenza di una libreria o di una stringa non prova l'esecuzione del relativo ramo. I file LLVM, i controlli di firma e l'inventario hanno origine negli strumenti di sistema e non ricevono artificialmente un Evidence ID REA.

## Verifica mirata con Ghidra 12.1.4

Il [provider nativo](native-environment.md) è stato compilato e verificato. Il primo tentativo di decompilare la funzione a `0xb0ec10` importando l'intera slice arm64 è terminato con `provider_timeout` dopo il limite REA di 330.000 ms. La ricevuta in `private/runs/antinode-clear-20261015T040317Z-7rfbjj62/` registra il fallimento; gli hash prima/dopo coincidono. Il log conserva avvisi dell'analisi delle librerie. **Non è stata completata la decompilazione dell'intero binario.**

Per rispondere alla domanda circoscritta sui buffer è stato selezionato l'intervallo `0xb0ec10-0xb0ec80` della slice verificata: 112 byte, SHA-256 `0e042969210d845bc922decec9996744aa3cb87952ddb371c0fd755d021fa69f`. La slice arm64 ha SHA-256 `8eae2a3e34f4d7e05f3cf5da5f4555efe03f52c217d0c75334b82c1df44e6ce7` ed è stata confrontata byte per byte con il container originale. Le due ricevute di derivazione conservano offset e impronte.

REA/Ghidra ha analizzato il frammento come `raw-binary`, con architettura arm64 e indirizzo di caricamento/ingresso esplicitamente fissato a `0xb0ec10`. Evidenza: `ev_e0de71c1a6c45c107b2e7cc267c63ec58a89d1eb31611d48a9cb0702c1a9e0aa`. La stessa evidenza è stata ottenuta con la CLI e poi con il wrapper del progetto, ricevuta `private/runs/antinode-clear-20261015T040908Z-xokmqbtx/`.

Il pseudocodice legge gli offset `0x360` e `0x50`, corroborando la dipendenza dai buffer osservata in LLVM. È stato classificato **`recorded_partial`**: la chiamata esterna di errore non è inclusa nel frammento e il decompilatore segnala `Control flow encountered bad instruction data` e troncamento del controllo. Il pseudocodice non è sorgente originale né una specifica numerica verificata; l'interpretazione conservativa riguarda le letture dei campi, non una formula DSP completa. Nessun frammento è stato eseguito o ricompilato nel prodotto.

## Conseguenze per AudioEnhancer

Il requisito utile è rendere espliciti identità dell'output, comportamento dei buffer, latenza e significato dei componenti. Prima di introdurre ascolto delta o controlli per stem occorre verificare gli output realmente prodotti dal nostro motore e la loro corrispondenza temporale. Il [piano di validazione](audioenhancer-validation-plan.md) separa il null-test anteprima/export dal residuo originale/elaborato e definisce le prove sui checkpoint e sulle conversioni.

Non sono stati eseguiti benchmark audio o CPU. Le interferenze della modalità demo vanno registrate prima di qualunque confronto e non attribuite al DSP. RX, Audition e Waves Clarity richiedono ancora artefatti ottenuti dai rispettivi flussi di accesso ufficiali; la loro documentazione non sostituisce un'analisi dei binari.
