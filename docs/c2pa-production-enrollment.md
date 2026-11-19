# Riconoscimento C2PA per AudioEnhancerMAX Mac

Stato verificato il 19 novembre 2026. La build diretta 3.9.1 integra creazione e verifica di manifesti per il flusso desktop. AudioEnhancerMAX non risulta elencato nella Conforming Products List. Il certificato Developer ID e la notarizzazione riguardano la distribuzione Mac. La fiducia nei manifesti audio dipende dal certificato di firma C2PA e dalla lista usata dal validatore. [Programma di conformità](https://c2pa.org/conformance/) · [Lista ufficiale dei prodotti](https://github.com/c2pa-org/conformance-public/blob/main/conforming-products/conforming-products-list.json) · [Politica dei certificati](https://github.com/c2pa-org/conformance-public/blob/main/docs/v0.2/C2PA%20Certificate%20Policy.md)

## Percorso raccomandato

1. **Presentare l’Expression of Interest come Generator Product.** Indicare il prodotto e il perimetro Mac diretto, l’entità giuridica registrata, il referente e il modello di firma per installazione. Valutare col programma se presentare separatamente la conformità del verificatore. La funzione di verifica richiede evidenze proprie anche quando fa parte di un prodotto che firma. [Expression of Interest](https://docs.google.com/forms/d/e/1FAIpQLScERZH5rKfoeSu3y6gGbkllkyeAhmF0G-kXS0eXpb2vR238Rg/viewform?usp=header) · [Regole del programma v0.2](https://github.com/c2pa-org/conformance-public/blob/main/docs/v0.2/C2PA%20Conformance%20Program.md)
2. **Completare accordo e intake.** Il programma fornisce il processo di onboarding e di valutazione. Preparare il documento Generator Product Security Architecture, dichiarare i formati e i tipi di ingredienti, fornire esempi firmati e i risultati del test harness per la verifica. Richiedere la valutazione al livello compatibile con l’architettura dimostrata. Il programma pubblica zero costi per domanda e iscrizione alla lista. L’eventuale lavoro di implementazione e i servizi della CA hanno costi separati. Non è stato trovato un tempo pubblico garantito per la valutazione. [Programma e tariffario](https://github.com/c2pa-org/conformance-public/blob/main/docs/v0.2/C2PA%20Conformance%20Program.md#conformance-program-fee-schedule) · [Template dell’architettura](https://github.com/c2pa-org/conformance-public/blob/main/docs/v0.2/C2PA%20Generator%20Product%20Security%20Architecture%20Document%20Template.md)
3. **Ottenere l’esito e rivolgersi a una CA presente nella C2PA Trust List.** Nel percorso standard si usa il record del prodotto riconosciuto per l’enrollment. Il certificato è per un’istanza del prodotto Generator conforme. Chiedere alla CA come gestisce identità, generazione delle chiavi, rinnovi e revoca per un’app Mac installata dagli utenti. La policy prevede una procedura specifica per la pubblicazione sotto embargo. [C2PA Trust List](https://github.com/c2pa-org/conformance-public/blob/main/trust-list/C2PA-TRUST-LIST.json) · [Politica dei certificati](https://github.com/c2pa-org/conformance-public/blob/main/docs/v0.2/C2PA%20Certificate%20Policy.md)
4. **Verificare l’effettivo riconoscimento.** Firmare un campione con l’istanza autorizzata, verificare integrità, catena e stato `Trusted` con un validatore esterno aggiornato. Valutare una TSA della lista ufficiale per una data di firma attestata, con comportamento di rete dichiarato. Ripetere il test su file alterato e dopo una rotazione di test. [Lista TSA](https://github.com/c2pa-org/conformance-public/blob/main/trust-list/C2PA-TSA-TRUST-LIST.json) · [Specifica C2PA](https://spec.c2pa.org/specifications/specifications/2.5/specs/C2PA_Specification.html)

## Scelta preliminare della CA

| Opzione | Condizioni pubbliche consultate | Implicazione |
| --- | --- | --- |
| [SSL.com](https://www.ssl.com/products/content-authenticity/content-credentials/c2pa/) | Un certificato Level 1 per un anno a $0 con conformance record idoneo. La pagina del piano indica 2.500 timestamp annui. | Prima richiesta per un pilota. Confermare per iscritto quota, rinnovi, firma desktop e modalità di custodia per istanza. |
| [Trufo](https://trufo.ai/products/c2pa-certs) | Offerta da $50/mese. Documenta firma Edge ES256 e gestione dell’emissione. | Alternativa da valutare per il provisioning di più installazioni. |
| [DigiCert](https://docs.digicert.com/en/device-trust-manager/manage-certificates/issue-specialized-certificates/issue-c2pa-claim-signing-certificates.html) | Documenta l’emissione con Device Trust Manager a partire da un prodotto in lista. | Alternativa per un flusso gestito. Richiedere un preventivo. |

Importi e quote sono indicazioni pubblicate dai fornitori e vanno confermati prima di prendere impegni.

## Lavoro tecnico prima dell’intake

- **Gestione della chiave.** Il PEM di prova è un file non cifrato con accesso limitato. Per il livello iniziale servono protezione della chiave persistente, controllo d’accesso, durata motivata della presenza in chiaro e rotazione. Per Mac Apple Silicon la direzione da verificare è una chiave P-256 generata per istanza con Keychain o Secure Enclave, CSR collegata alla chiave e firma tramite callback. Concordare con programma e CA gli elementi di prova e l’enrollment prima di fissare un livello dichiarato. [Requisiti di sicurezza Generator](https://github.com/c2pa-org/conformance-public/blob/main/docs/v0.2/C2PA%20Generator%20Product%20Security%20Requirements.md) · [Secure Enclave](https://developer.apple.com/documentation/security/protecting-keys-with-the-secure-enclave)
- **Manifesti e harness.** Verificare i requisiti aggiuntivi v0.2 per le versioni della specifica ammesse, incluso specVersion, completezza delle azioni e digitalSourceType dove richiesto. Preparare il passaggio di asset, ancore CA/TSA di prova e tempo di verifica al harness con esito crJSON. Le prove applicative esistenti coprono integrità e rilevamento di manomissione. La valutazione richiede il proprio insieme di campioni. [Requisiti aggiuntivi](https://github.com/c2pa-org/conformance-public/blob/main/docs/v0.2/Additional%20Conformance%20Requirements%20Against%20the%20Content%20Credentials%20Specification.md) · [Fixture pubbliche](https://github.com/c2pa-org/public-testfiles)
- **Fiducia nel tempo.** Decidere con la CA come gestire timestamp RFC 3161, revoca, aggiornamento della trust list e rotazione. La build preparata usa la configurazione locale, con firma senza TSA e verifica dei manifesti incorporati. Un certificato di prova scaduto può cambiare il responso live della demo.
- **Confini.** Presentare inizialmente la build diretta Mac per Apple Silicon e i formati effettivamente testati. Specificare a parte l’eventuale certificazione Validator, il Mac App Store e le app mobile. Conservare le ricevute della valutazione e del test indipendente con il numero di build.

## Testo pronto per la domanda EOI

**Product:** AudioEnhancerMAX for Mac, direct distribution for Apple Silicon

**Applicant:** [registered legal entity, jurisdiction and authorized contact]

**Scope:** Generator Product for embedded audio Content Credentials in WAV, MP3 and FLAC exports from Enhance and Speech Editor. The desktop verifier can inspect existing embedded credentials. We intend to confirm the appropriate evaluation scope for this capability.

**Signing architecture:** Local test deployment currently uses an ES256 software signer. For production we are evaluating instance-bound P-256 keys backed by macOS key storage, a C2PA Trust List CA and a timestamping policy. We would like to confirm the intake evidence required for this desktop architecture before selecting an assurance level.

**Evidence available:** Reproducible macOS build, synthetic signed WAV, tamper test, SDK and CLI validation results, revision and source linkage tests.

**Questions:** Please confirm applicant and signing-instance requirements, available evaluation harness and sample format, compatibility of hardware-backed macOS keys with the intended enrollment, and the expected review sequence.

Bozza pronta per revisione. La denominazione registrata, il referente autorizzato e l’architettura di produzione richiedono conferma prima dell’invio.
