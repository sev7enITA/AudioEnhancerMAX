# AudioEnhancerMAX 3.7.0 - Distribution Upload Manifest

## Apple / Transporter

Upload only `AudioEnhancerMAX-v3.7.0-build-3.7.2-MacAppStore.pkg`. This package is signed for the Mac App Store and is not a SourceForge download.

## Apple / App Review Information

Use `AudioEnhancerMAX-Apple-Review-Assets-3.7.0-build-3.7.2.zip` as the local operator bundle. Attach the dossier PDF, review WAV, and manually recorded MOV separately where App Store Connect accepts attachments; paste Review Notes and the Resolution Center reply from their Markdown files.

## Hostinger

Extract `AudioEnhancerMAX-Website-3.7.0-Hostinger.zip` into the public directory that serves the official AudioEnhancerMAX path. The archive root already contains `index.html`, `roadmap.html`, `support.html`, `privacy.html`, `accessibility.html`, `css/`, `js/`, and `img/`; do not add another enclosing `web` directory.

## SourceForge

Create the `v3.7.0` folder and upload these public files:

- `AudioEnhancerMAX-v3.7.0-macOS-arm64.dmg`
- `AudioEnhancerMAX-v3.7.0-macOS-arm64.dmg.sha256`
- `AudioEnhancerMAX-Worker-v1.2.0-debug.apk`
- `AudioEnhancerMAX-Worker-v1.2.0-debug.apk.sha256`
- `AudioEnhancerMAX-3.7.0-SourceForge-source.zip`
- `RELEASE_NOTES_v3.7.0.md`
- `CHECKSUMS_v3.7.2.txt`

The DMG is the separate direct-download build signed with `Developer ID Application: Fabrizio Degni (BR9VY292BU)`, accepted by Apple notarization, and stapled. The Android worker is a development/debug companion and must remain visibly labelled **debug**; it is not a production Play Store APK.

Do not upload the Mac App Store PKG to SourceForge. Keep the DMG and PKG channel-specific even though both report version 3.7.0 (build 3.7.2).
