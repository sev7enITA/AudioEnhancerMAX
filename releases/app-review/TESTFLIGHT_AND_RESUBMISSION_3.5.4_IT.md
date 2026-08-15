# TestFlight e nuova submission - build 3.5.4

## Che cos'e TestFlight

TestFlight e il canale Apple per installare e provare una build caricata in App Store Connect prima della pubblicazione. Non crea una seconda app e non richiede un secondo Mac: puoi aggiungere il tuo Apple ID come tester interno e installare la build sullo stesso Mac.

TestFlight non risolve pero il requisito specifico di Apple sul video: la registrazione finale deve essere fatta su un Mac fisico con l'ultima versione pubblica di macOS. Se il tuo unico Mac usa macOS 27 beta, TestFlight puo verificare la distribuzione ma quel sistema potrebbe non soddisfare la richiesta del revisore.

## Caricamento con Transporter

1. Apri Transporter e accedi con l'Apple ID associato ad App Store Connect.
2. Trascina `AudioEnhancerMAX-v3.5.2-build-3.5.4-MacAppStore.pkg` nella finestra.
3. Seleziona Deliver.
4. Attendi l'email di elaborazione Apple; per un pacchetto di circa 1.7 GiB puo essere necessario attendere.
5. In App Store Connect apri AudioEnhancerMAX, poi TestFlight, macOS e build 3.5.4.
6. Completa eventuali domande su crittografia/esportazione e le informazioni beta richieste.

## Test interno sullo stesso Mac

1. In TestFlight crea un gruppo Internal Testing, se non esiste.
2. Aggiungi il tuo utente App Store Connect come tester interno.
3. Aggiungi la build 3.5.4 al gruppo.
4. Installa l'app TestFlight dal Mac App Store, accetta l'invito e installa AudioEnhancerMAX 3.5.4.
5. Esegui upload, Remove Noise, confronto, export e trascrizione.
6. Verifica che l'interfaccia resti nella finestra nativa e che, chiudendo l'app, il listener locale sparisca.

Per i tester interni non serve una TestFlight Beta App Review separata. I tester esterni richiedono invece un gruppo esterno e la prima build puo dover essere approvata da Apple.

## Resubmission

1. Registra il video continuo richiesto da Apple su un Mac fisico con l'ultima versione pubblica di macOS.
2. Nella versione macOS 3.5.2 seleziona la nuova build 3.5.4.
3. Incolla `APP_REVIEW_NOTES_3.5.2_BUILD_3.5.4.md` nel campo Review Notes.
4. Allega il video, il WAV di esempio e il dossier PDF.
5. Rispondi nel Resolution Center spiegando che `network.server` serve esclusivamente al collegamento inbound tra WKWebView nativa e servizio embedded su `127.0.0.1`, attivo solo durante la vita dell'app.
6. Seleziona Resubmit to App Review.
