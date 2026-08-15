# TestFlight e nuova submission — AudioEnhancerMAX 3.7.0 build 3.7.2

## Upload e TestFlight

1. Apri Transporter con lo stesso account Apple Developer usato per l’app.
2. Trascina `AudioEnhancerMAX-v3.7.0-build-3.7.2-MacAppStore.pkg` e scegli **Deliver**.
3. Attendi che App Store Connect mostri lo stato **Complete**. Se resta **Processing** oltre 24 ore, apri un ticket come indicato da Apple.
4. Apri App Store Connect → AudioEnhancerMAX → TestFlight → macOS → versione 3.7.0 → build 3.7.2.
5. Completa eventuali domande su export compliance. Aggiungi la build a un gruppo Internal Testing e installala tramite TestFlight sul Mac fisico.
6. Non usare l’app eseguita dal sorgente per video o screenshot finali.

## Test fisico minimo

- Verifica che menu e finestra mostrino AudioEnhancerMAX, non Python, e apri About.
- Carica `AudioEnhancerMAX-review-sample.wav` dal pannello Open nativo.
- Esegui Smart Enhance/processing e verifica il Review Deck.
- Cambia target nel Delivery Compliance Lab e controlla le regole.
- Completa un A/B cieco e verifica che la mappatura venga rivelata solo dopo la scelta.
- Esporta un Project Capsule lasciando disattivato “Include original audio”; apri il ZIP e verifica `manifest.json` e output.
- Esporta WAV, MP3 e FLAC dal pannello Save nativo.
- Esegui la trascrizione locale.
- Chiudi l’app e verifica che il processo e la porta loopback terminino.

## Nuova submission

1. Nella versione macOS 3.7.0 seleziona la build 3.7.2.
2. Aggiorna What’s New e screenshot affinché corrispondano esattamente alla build TestFlight.
3. Incolla `APP_REVIEW_NOTES_3.7.0_BUILD_3.7.2.md` nel campo Review Notes.
4. Allega video fisico continuo, WAV di prova e dossier PDF.
5. Rispondi nel Resolution Center spiegando che il server entitlement serve esclusivamente al listener inbound su loopback usato dalla WKWebView interna e che il listener termina con l’app.
6. Conferma le sette informazioni richieste da Apple: dispositivo/OS, scopo/pubblico, accesso, servizi esterni, differenze regionali, settore regolato/materiali protetti, video fisico.
7. Invia nuovamente a Review solo dopo il completamento del checklist finale.

Riferimenti Apple: Upload builds, TestFlight Overview, Choose a build to submit e App Review Guidelines nella documentazione ufficiale Apple Developer.
