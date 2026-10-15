# TestFlight e nuova submission - build 3.5.6

1. Apri Transporter e accedi con l'Apple ID associato ad App Store Connect.
2. Trascina `AudioEnhancerMAX-v3.5.2-build-3.5.6-MacAppStore.pkg` e scegli Deliver.
3. Attendi l'elaborazione; in App Store Connect apri AudioEnhancerMAX > TestFlight > macOS > build 3.5.6.
4. Aggiungi la build a un gruppo Internal Testing e installala sullo stesso Mac tramite TestFlight.
5. Verifica menu `AudioEnhancerMAX`, About, finestra stand-alone, upload, profilo di consegna, processing report, export e trascrizione.
6. Verifica in Privacy & Offline che servizi esterni, assistenza Ollama e trusted LAN siano controllabili separatamente.
7. Registra il video continuo richiesto da Apple su un Mac fisico con l'ultima versione pubblica di macOS disponibile in quel momento.
8. Nella versione macOS 3.5.2 seleziona build 3.5.6, incolla `APP_REVIEW_NOTES_3.5.2_BUILD_3.5.6.md` e allega video, WAV e dossier PDF.

TestFlight puo essere usato sullo stesso Mac e non richiede un secondo computer. Non effettua pero il downgrade di macOS: se il Mac usa una beta, quella registrazione non dimostra automaticamente il requisito "latest public macOS" richiesto da Apple.
