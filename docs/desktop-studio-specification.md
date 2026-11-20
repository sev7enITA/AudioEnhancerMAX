# AudioEnhancerMAX Desktop Studio

**Piattaforma** macOS 13 o superiore su Apple Silicon, interfaccia WKWebView e controlli AppKit. Il percorso principale è il montaggio audio e parlato per podcast e creator. L’anteprima video serve a controllare i contributi social in verticale e orizzontale. I parametri avanzati sono disponibili per i tecnici.

## Workspace e layout

Studio è accessibile dalla navigazione principale. I quattro preset Record, Edit, Mix ed Export portano in primo piano rispettivamente sorgenti e registrazione, timeline e tagli, Inspector audio, mix finale e consolidamento. I pannelli contestuali si possono sganciare, spostare, ridimensionare e riagganciare dentro la finestra Studio. Le stesse operazioni sono disponibili da tastiera e i preset sono ripristinabili.

I fondi usano grigi neutri #121214 e #1E1E22. Il colore evidenzia segnale, testina, selezione e stati significativi. Calm nasconde elementi secondari, mantiene timeline e trasporto e riduce il movimento. La preview 16:9 o 9:16 cambia disposizione e proporzioni senza restringere la timeline. Il player mostra il video sorgente del clip selezionato e segue il playhead del mix. L’esportazione di Studio produce audio WAV o FLAC.

## Timeline, mix ed editing non distruttivo

Il progetto usa coordinate in secondi, riferite al PCM a 48 kHz. Clip, track, posizioni di sorgente, guadagno, automazione e filtri sono un documento di montaggio. Gli originali sono copiati nel progetto con SHA-256 e restano immutabili. Il decoder genera PCM stereo separato per uso interno e picchi per la grafica. Il mix lavora a blocchi e scrive un nuovo file. Il report conserva revisione, operazioni e digest degli asset e del risultato.

- Il corpo sposta la clip tra tracce. I bordi modificano in e out e gli angoli superiori applicano fade. Una sovrapposizione fra fine e inizio sulla stessa traccia applica un crossfade equal-power.
- Lo snapping usa playhead, marker, bordi ed eventi della beat grid. Il BPM è impostabile e Alt esclude temporaneamente lo snapping durante il trascinamento.
- L’Inspector offre anche controlli numerici per trim e fade, guadagno, frequenza di presenza, ratio e soglia. Chiarezza, calore e riduzione di riflessioni brevi corrispondono a DSP riproducibile. Il bypass mantiene le impostazioni e consente di disattivare gli effetti.
- Una traccia può essere silenziata. I punti di automazione conservano tempo relativo alla clip e dB, con interpolazione lineare. L’output segnala eventuale superamento di 0 dBFS.
- Cmd/Ctrl+K cerca gli strumenti dell’app e le azioni registrate di Studio. J/K/L, Spazio e S/B sono rimappabili assieme alle altre scorciatoie presenti nel pannello di configurazione. J naviga indietro in modalità scrub, K ferma e L avanza. Gli input di testo conservano la digitazione.

## Funzioni contestuali e lavoro in background

- Whisper consente trascrizioni locali con timestamp e SRT allineati ai tagli correnti. La trascrizione viene salvata con la sorgente. Dalla frase si può saltare al tempo, tagliarla oppure spostarla sulla testina.
- La rimozione dei silenzi rileva le regioni quiete e sostituisce il clip con i segmenti conservati. History e Undo consentono di ripristinare lo stato precedente. Align to beat sposta l’attacco sulla griglia del BPM già scelto.
- L’isolamento voce appare quando è disponibile Demucs con i pesi locali htdemucs. Produce una sorgente separata da aggiungere alla timeline. Il modello resta un componente opzionale. Nessun testo o media viene inviato a un servizio esterno per queste azioni.
- Decodifica, preview del mix, esportazione, trascrizione e consolidamento girano fuori dal thread dell’interfaccia. Le richieste lunghe espongono stato e progresso. I job di elaborazione concorrenti sono limitati a due. Il report di render è associato alla revisione salvata prima di avviare il job.
- La registrazione richiede autorizzazione esplicita al microfono dal runtime. Stop aggiunge il file registrato come nuova sorgente.

## Persistenza e portabilità

Autosave registra revisioni SQLite e conserva fino a 75 eventi ripristinabili dalla cronologia. L’interfaccia raggruppa modifiche ravvicinate e il database rifiuta scritture basate su revisioni superate. Ripristinare uno stato crea una nuova revisione.

Il progetto conserva una copia delle sorgenti nella propria area. Studio controlla periodicamente questa area, indica le sorgenti offline e permette il relink della copia esatta tramite SHA-256. Consolidate project scarica uno ZIP con una cartella, un manifesto e tutti gli originali importati. Open project ZIP valida e riapre la cartella come un nuovo progetto. Il limite è 500 MB per sorgente, due ore per timeline e 4 GB per pacchetto consolidato. Lo ZIP conserva lo stato di montaggio corrente.

## Rendering e criteri di accettazione

La timeline usa Canvas con percorso WebGL dove disponibile e fallback Canvas 2D, picchi precalcolati, viewport limitato alla zona visibile e aggiornamenti accorpati con requestAnimationFrame. Il renderer non decodifica i media durante lo scrolling. Si misura p95 e p99 del tempo per frame per scroll e zoom, con un progetto a due ore, 256 clip e 32 tracce. I budget di riferimento sono 16,7 ms a 60 Hz e 8,3 ms a 120 Hz su display e hardware compatibili. Per dichiararli raggiunti occorrono sessioni su WKWebView con display fisico, profilo GPU e risultati per risoluzione. [Specifiche WebGL](https://registry.khronos.org/webgl/)

La verifica desktop comprende selezione file AppKit, apertura di WAV e MP4, clip ridimensionabili, snapping e crossfade, 16:9 e 9:16 a 1440×900 e 1024×700, registrazione con hardware autorizzato, ripristino dopo riavvio, ricerca e riordino con tastiera, confronto SHA-256 dopo render e riapertura dello ZIP. Vanno provati anche il focus e gli annunci con VoiceOver e contrasto aumentato sulla build Mac. [WCAG 2.2](https://www.w3.org/TR/WCAG22/) · [Apple HIG](https://developer.apple.com/design/human-interface-guidelines/accessibility)

## Esito della build locale 4.1.6

- La prova sulla build ha coperto importazione, montaggio, automazione, esportazione con SHA-256 verificato sul file scaricato e riapertura del progetto consolidato. La suite Python ha superato 223 test e 27 sottotest. I controlli automatici di accessibilità sullo Studio a 1440×900 e 1024×700 hanno riportato zero violazioni.
- Su WKWebView con GPU Apple, il benchmark di scroll e zoom (256 clip, 32 tracce, viewport 1320×500 a DPR 2) ha misurato una mediana di 33 ms, p95 di 34 ms e p99 di 35 ms fra frame. Anche il controllo con timeline ferma ha misurato 34 ms al p95. La prova resta sopra entrambi i budget di riferimento.
- La registrazione è stata provata con ingresso simulato. Restano da verificare il microfono fisico, VoiceOver e l'esecuzione con i modelli locali Whisper e Demucs.

## Studio nella BETA 4.1.3, build 4.1.7

L'ingresso di Studio offre importazione diretta e un progetto di esempio modificabile su due tracce. Aprire e chiudere il selettore file lascia intatto l'elenco dei progetti. La vista attiva riunisce trasporto, timeline e Inspector. Il monitor video compare quando si seleziona una clip con video.

La testina si aggiorna durante la riproduzione con il tempo effettivo del mix. Il meter legge i picchi dei due canali dell'audio in riproduzione attraverso Web Audio e torna a zero in pausa. La verifica di questo comportamento è distinta dal benchmark di scroll e zoom riportato sopra.

Prima di consegnare una revisione Mac, avanzare versione e build in app/release.py e ricreare il pacchetto. Verificare che Info.plist, /api/health, barra laterale e About mostrino la stessa coppia di valori.

## Punti di ingresso

- Interfaccia, layout, timeline e workflow in frontend/index.html, frontend/js/studio-layout.js, frontend/js/studio-timeline.js e frontend/js/studio-engine.js.
- Schema progetto, istruzioni di montaggio e renderer in app/services/project_studio.py. Richieste locali e job in app/services/project_studio_routes.py.
- Selettore nativo e permessi dichiarati nella finestra desktop e nella configurazione del pacchetto Mac.
