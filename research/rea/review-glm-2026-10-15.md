# Revisione GLM-5.3 del protocollo audio

15 ottobre 2026. Risposte effettivamente ricevute e lette in ZCode, chat «Revisione tecnica REA AudioEnhancer e test prioritari», modello mostrato dall'interfaccia `GLM-5.3`, modalità `Max`. Questo documento è una sintesi critica delle due risposte, non una trascrizione integrale. L'applicazione è locale; non è stata verificata l'esecuzione del modello sull'hardware locale. Nessuna verifica Gemini è dichiarata.

Sono stati forniti un riepilogo delle evidenze statiche pubbliche Adobe Podcast, il piano di inventario Clear e le ipotesi di verifica sui checkpoint/export di AudioEnhancer. È stato richiesto di rispondere in chat senza leggere o modificare file. Non sono stati inviati binari, registrazioni vocali, credenziali o documenti personali.

## Risposta e valutazione

La prima risposta, completata in 52 secondi secondo l'interfaccia, distingue correttamente struttura del client e semantica del DSP. Osserva che grafi parziali non permettono di dichiarare equivalenza anteprima/export e che i parametri presenti nel job non provano la loro influenza sull'audio.

Tre criteri proposti non sono stati accettati: hash identico tra run come requisito universale; residuo inferiore all'1% come condizione di validità del delta; interpretazione di «demo» come duplicazione del dataset. Anche la soglia universale di −80 dBFS nel null-test non è giustificata senza conoscere codec, dither e ripetibilità.

È stata inviata una richiesta di correzione esplicita. La seconda risposta, completata in 44 secondi, propone:

- confronto PCM anteprima/export con tolleranze ricavate da ripetizioni dello stesso percorso;
- sensibilità ai parametri verificata su segnali responsivi, senza richiedere che ogni parametro cambi ogni ingresso;
- run ripresa confrontata con run pulita avente stessi sorgente, versione e parametri effettivi;
- registrazione di rumore e mute periodici del trial;
- ascolto del residuo originale/elaborato come controllo del materiale rimosso, senza interpretarne l'energia come punteggio di qualità.

Restano due precisazioni editoriali: un null-test anteprima/export non certifica automaticamente l'allineamento originale/elaborato, che va verificato sulla coppia pertinente; artefatti simmetrici nei due bracci non rendono automaticamente valido un confronto percettivo. Le interferenze del trial possono rendere la prova inconcludente. Inoltre la compensazione di gain/tempo non deve nascondere proprio una differenza che il test vuole misurare.

Il [piano finale](audioenhancer-validation-plan.md) incorpora queste correzioni. La revisione del modello è un controllo metodologico aggiuntivo, non una nuova prova del comportamento dei concorrenti o del nostro software. Nessun test audio è stato eseguito da GLM o in conseguenza delle sue risposte.
