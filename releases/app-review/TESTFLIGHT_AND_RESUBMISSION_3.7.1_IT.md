# TestFlight e nuova submission — AudioEnhancerMAX 3.7.0 build 3.7.1

1. In App Store Connect crea o seleziona la versione macOS `3.7.0`.
2. Apri Transporter e accedi con l’Apple ID associato ad App Store Connect.
3. Trascina `AudioEnhancerMAX-v3.7.0-build-3.7.1-MacAppStore.pkg` e scegli Deliver.
4. Attendi l’elaborazione; apri AudioEnhancerMAX > TestFlight > macOS > build 3.7.1.
5. Aggiungi la build a un gruppo Internal Testing e installala sullo stesso Mac tramite TestFlight.
6. Verifica menu AudioEnhancerMAX, About, finestra stand-alone, Smart Enhance, Precision Editor, profilo di consegna, processing report, export e trascrizione.
7. Verifica in Privacy & Offline che servizi esterni, assistenza Ollama e trusted LAN siano controllabili separatamente e che trusted LAN sia disattivata al primo avvio.
8. Registra il video continuo richiesto da Apple su un Mac fisico con l’ultima versione pubblica di macOS disponibile in quel momento.
9. Nella versione macOS 3.7.0 seleziona build 3.7.1, incolla `APP_REVIEW_NOTES_3.7.0_BUILD_3.7.1.md` e allega video, WAV e dossier PDF.

TestFlight può essere usato sullo stesso Mac e non richiede un secondo computer. Non effettua però il downgrade di macOS: se il Mac usa macOS 27 beta, quella registrazione non dimostra il requisito “latest public macOS”. Al 14 agosto 2026 Apple elenca macOS Tahoe 26.6 come release pubblica più recente; verifica di nuovo Software Update il giorno della registrazione.

Riferimento Apple: https://support.apple.com/en-us/128067
