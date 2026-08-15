# AudioEnhancerMAX 3.7.0 - Distribution Upload Manifest

## Apple / Transporter

Upload only `AudioEnhancerMAX-v3.7.0-build-3.7.2-MacAppStore.pkg`. This package is signed for the Mac App Store and is not a SourceForge download.

## Apple / App Review Information

Use `AudioEnhancerMAX-Apple-Review-Assets-3.7.0-build-3.7.2.zip` as the local operator bundle. Attach the dossier PDF, review WAV, and manually recorded MOV separately where App Store Connect accepts attachments; paste Review Notes and the Resolution Center reply from their Markdown files.

## Hostinger

Extract `AudioEnhancerMAX-Website-3.7.0-Hostinger.zip` into the public directory that serves the official AudioEnhancerMAX path. The archive root already contains `index.html`, `roadmap.html`, `support.html`, `privacy.html`, `accessibility.html`, `css/`, `js/`, and `img/`; do not add another enclosing `web` directory.

## SourceForge

Upload:

- `AudioEnhancerMAX-3.7.0-SourceForge-source.zip`
- `RELEASE_NOTES_v3.7.0.md`
- `CHECKSUMS_v3.7.2.txt`

Do not upload the Mac App Store PKG. A direct-install Mac binary must first be signed with Developer ID Application, packaged, notarized, and stapled as a separate artifact.
