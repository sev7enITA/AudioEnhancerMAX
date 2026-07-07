# 📱 AudioEnhancerMAX — Android Edge Worker

**App nativa Android per il calcolo distribuito con AudioEnhancerMAX.**

Questa app trasforma il tuo smartphone Android in un **nodo di calcolo** per la pipeline di elaborazione audio di AudioEnhancerMAX. Installa l'APK, premi START e il tuo telefono inizierà a processare chunk audio inviati dal Mac master.

## ✨ Features

- 🎵 **12 filtri DSP** — Noise reduction, studio sound, EQ, compressor, normalizer, e altro
- 🌐 **Auto-discovery** — Il Mac master trova automaticamente il telefono sulla rete LAN
- 📡 **HTTP Server integrato** — API REST compatibile al 100% con il cluster manager
- 🔋 **Foreground Service** — Continua a funzionare in background con notifica persistente
- 🎨 **Material 3 Dark UI** — Interfaccia moderna con status in tempo reale

## 📦 Installazione

### Da APK Pre-compilato (Consigliato)

1. Scarica `app-debug.apk` dalla sezione [Releases](../../releases)
2. Trasferisci l'APK sul tuo dispositivo Android
3. Abilita "Installa da sorgenti sconosciute" nelle impostazioni
4. Apri il file APK per installarlo

### Da Sorgente

Requisiti:
- JDK 17 oppure JDK 21. Evita JDK 25: la toolchain Kotlin/Gradle corrente non lo interpreta correttamente.
- Android SDK (API 35)
- Android Build Tools 36.1.0

```bash
cd android-worker
export JAVA_HOME="/path/to/jdk17-or-jdk21"
export ANDROID_HOME="/path/to/android-sdk"
./gradlew assembleDebug
```

L'APK si troverà in `app/build/outputs/apk/debug/app-debug.apk`.

## 🚀 Utilizzo

1. **Avvia l'app** sul tuo smartphone Android
2. **Premi START WORKER** — il server HTTP si avvia sulla porta 8877
3. **Connetti alla stessa rete Wi-Fi** del Mac con AudioEnhancerMAX
4. Il worker verrà **scoperto automaticamente** tramite UDP broadcast
5. Oppure aggiungilo manualmente dalla dashboard inserendo l'IP del telefono

## 🏗️ Architettura

```
┌─────────────────────────────────┐
│     Android Edge Worker APK     │
├─────────────────────────────────┤
│  UI: Jetpack Compose Material 3 │
│  HTTP: NanoHTTPD (porta 8877)   │
│  DSP: Kotlin puro (FFT, IIR)   │
│  Discovery: UDP broadcast:9999  │
│  Service: Foreground + WakeLock │
└─────────────────────────────────┘
         ↕  Wi-Fi LAN  ↕
┌─────────────────────────────────┐
│   Mac Master (AudioEnhancerMAX) │
│   cluster_manager.py            │
└─────────────────────────────────┘
```

## 📡 API (Compatibile con cluster_manager.py)

| Endpoint | Metodo | Descrizione |
|----------|--------|-------------|
| `/worker/health` | GET | Health check + capabilities |
| `/worker/status` | GET | Stato corrente (CPU, RAM) |
| `/worker/process` | POST | Processa chunk audio (multipart WAV) |

## 🎛️ Filtri DSP Disponibili

| Filtro | Descrizione |
|--------|-------------|
| `remove_noise` | Spectral gating con soglia adattiva |
| `studio_sound` | Chain broadcast: HPF → Warm → Presence → De-esser → Compressor → Limiter |
| `auto_eq` | Profilo broadcast per voce |
| `normalize` | Peak normalization |
| `wind_noise_remover` | Butterworth HPF + spectral gating |
| `buzzing_noise_remover` | Notch filter 50/60Hz + armoniche |
| `static_noise_remover` | Spectral gating stazionario |
| `reverb_echo_remover` | Sottrazione spettrale |
| `remove_breaths` | Riduzione respiri (max 80%) |
| `remove_long_silences` | Rimozione silenzi > 1s |
| `remove_mouth_sounds` | Riduzione click labiali |
| `frequency_restoration` | Restauro frequenze |

## 📱 Requisiti

- Android 8.0 (API 26) o superiore
- Connessione Wi-Fi sulla stessa rete del Mac
- ~14 MB di spazio

## 📄 License

MIT — Parte del progetto [AudioEnhancerMAX](../)
