# Companion updates

Open **About → Updates** to check the release available for your installation. Google Play and App Store installations receive updates through their store. Public companion builds are currently distributed as direct BETA packages.

| Channel | What happens |
|---|---|
| Google Play | The Play build opens the companion’s Google Play product page. Google Play checks the installed version, account eligibility and app signing. |
| App Store | The App Store build opens the companion’s own App Store product page when configured. Apple manages the download and installation. |
| GitHub or SourceForge, Android | Select a repository. The app verifies the signed release data, downloads the candidate and checks its size, SHA-256, package, build and signing certificate against the installed app. Save the verified APK and use the Android installer to confirm the update. |
| GitHub or SourceForge, iOS | Select a repository. The developer build verifies the signed release data and the unsigned Xcode archive’s exact size and SHA-256. Use Xcode and an authorized signing and provisioning setup for installation. |

Both approved direct repositories host identical files. The apps remember the selected source for direct downloads. If the system cannot identify the repository used for installation, choose it in Updates. Each store manages built-in update behavior and signing for its own channel. A QA-signed Android APK retains the direct BETA certificate so users of the previous BETA can update in place.

Direct checks use the [signed public release feed](https://www.fabriziodegni.com/AudioEnhancerMAX/updates/companion-v1.json). The app checks the ECDSA P-256 signature using its bundled public key before reading release fields. It checks time validity and compares the candidate’s build number with the installed one. Package locations are derived from the approved project and verified release tag. Download failures or mismatches stop export. The feeds and direct downloads require HTTPS.

## Publish the next direct companion release

1. Build both companions. Sign the Android APK with the established direct release certificate. Export a sanitized iOS developer archive without provisioning data or private material.
2. Run `python3 scripts/sign_companion_updates.py --help`. Provide the APK, Xcode archive, Android build-tools path, pinned Android certificate fingerprint, approved numeric version and build numbers, mobile BETA tag and local update signing key. The output path is `web/updates/companion-v1.json`.
3. Publish the same filenames and bytes on the [official GitHub repository](https://github.com/sev7enITA/AudioEnhancerMAX/releases) and [official SourceForge project](https://sourceforge.net/projects/audioenhancermax/files/). Verify the public bytes on both before deploying the signed feed.
4. Deploy the feed and website download links. Verify the public feed’s bytes, signature and published package hashes. Test a device with an updater-enabled older build and the same direct signing certificate.

The default validity is 90 days. Re-sign the current release if the feed is due to expire before the next build. Keep the private update key local and owner-readable. Only its public counterpart under `app/resources/mobile/` belongs in source control or a companion bundle. A key rotation requires a planned client update.
