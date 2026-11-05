# AudioEnhancerMAX: interventi del 5 novembre 2026

## Sito pubblico e SourceForge

- Homepage aggiornata con pulsante Mac App Store, confronto Store 3.8.2 / diretto 3.9.0 e indicazione dell’aggiornamento Store in preparazione.
- Pagina download allineata, vecchio Experimental 1 conservato come archivio.
- SourceForge: descrizione e feature list salvate e rilette nella pagina pubblica. Versione diretta stabile 3.9.0 / build 3.9.2; Store 3.8.2 separato.
- Pubblicazione circoscritta a nove file in `public_html/AudioEnhancerMAX`. Otto file statici verificati byte per byte con SHA-256; endpoint PHP verificato con richieste reali. Copia precedente dei file esistenti conservata in `website-before`.

## Misurazione e prove d’uso

- Contatore aggregato attivo: giorno UTC, canale, campagna, destinazione e posizione del link. Nessun cookie, identificatore visitatore o contenuto del feedback salvato dal contatore.
- Contatori privati in `.aemax-metrics`, fuori da `public_html`. Ispezionato il JSON sul server: una richiesta QA separata dal traffico organico.
- Verificati reindirizzamento Store, esclusione DNT e rifiuto delle destinazioni non autorizzate. Quattro test automatici dell’endpoint passati.
- Pagina pubblica `feedback.html`, generazione locale del rapporto verificata in Safari. Nessun rapporto di prova inviato a GitHub.
- Richiesta tester SourceForge già esistente aggiornata, mantenendo testo e immagine precedenti. Link per il protocollo di prova attivo nel post.
- Inventario di link per 12 canali disponibile in `campaign-links.csv`; le altre destinazioni sono pronte per i prossimi contenuti, non dichiarate già pubblicate.
- Registro delle prove indipendenti inizialmente vuoto. Nessuna testimonianza o risultato d’ascolto inventato. Nessuna spesa promozionale aumentata.

Guida operativa: `MEASUREMENT.md`. Esportatore: `scripts/export_campaign_counts.py`.

## Preparazione Apple

- Worktree isolato: `/Users/fabriziodegni/Projects/AudioEnhancerMAX-store-3.9.0-20261105`.
- Pacchetto Store 3.9.0 / build 3.9.3, 1.53 GB, firmato con certificati Apple di Fabrizio Degni e profilo valido fino al 16 luglio 2027.
- Modello Faster-Whisper Medium e VAD inclusi. Firma ricorsiva strict verificata.
- 45 test Python e 14 test JavaScript superati; 3 subtest Python superati.
- App Store Connect: nuova versione creata in stato Prepare for Submission, descrizione, Novità, note di review e allegato campione salvati. Rilascio manuale selezionato.
- Il pacchetto di distribuzione non è avviabile direttamente con il profilo di produzione: la prova nativa deve utilizzare la build elaborata da Apple/TestFlight. Non è stato aggirato questo controllo.
- Caricamento avviato con Transporter. Ricevuta finale e installazione TestFlight da verificare; nessun invio ad App Review e nessuna pubblicazione della 3.9.0 sono dichiarati qui.

Artefatti e prove Apple: `releases/app-store-3.9.0-20261105` nel worktree Store. Stato finale aggiornato nel messaggio conclusivo e in `status.json`.
