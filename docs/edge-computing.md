# Edge Computing Setup

AudioEnhancerMAX can offload selected DSP filters to trusted Android devices on the same LAN.

## Architecture

- Mac or workstation runs the FastAPI master.
- Android worker runs a native Kotlin foreground service.
- Worker exposes HTTP on port `8877`.
- Discovery uses UDP broadcast on the local network.

## Build the Android Worker

```bash
cd android-worker
export JAVA_HOME="/path/to/jdk17-or-jdk21"
export ANDROID_HOME="/path/to/android-sdk"
./gradlew assembleDebug
```

Use JDK 17 or JDK 21. JDK 25 is not currently compatible with the checked-in Android/Kotlin toolchain.

## Run

1. Install the APK on the Android device.
2. Connect the device to the same Wi-Fi network as the master.
3. Start the worker from the app.
4. Confirm the worker appears in the cluster panel or add it manually by IP.

## Safety Notes

Edge workers are intended for trusted LANs only. Do not accept untrusted workers, and do not expose the master API to the public internet without authentication and a reverse proxy policy.
