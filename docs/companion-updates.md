# Companion updates

Open **About → Updates** to check the release available for your installation. Google Play and App Store installations receive updates through their store. Public companion builds are currently distributed as direct BETA packages.

| Channel | What happens |
|---|---|
| Google Play | The Play build opens the companion’s Google Play product page. Google Play checks the installed version, account eligibility and app signing. |
| App Store | The App Store build opens the companion’s own App Store product page when configured. Apple manages the download and installation. |
| GitHub or SourceForge, Android | Select a repository. The app verifies the signed release data, downloads the candidate and checks its size, SHA-256, package, build and signing certificate against the installed app. Save the verified APK and use the Android installer to confirm the update. |
| GitHub or SourceForge, iOS | Select a repository. The developer build verifies the signed release data and the unsigned Xcode archive’s exact size and SHA-256. Use Xcode and an authorized signing and provisioning setup for installation. |

Both approved direct repositories host identical files. The apps remember the selected source for direct downloads. If the system cannot identify the repository used for installation, choose it in Updates. Each store manages built-in update behavior and signing for its own channel. Android 4.1.7 BETA (build 21) starts the production signing channel. Users of a test-signed build need to export any saved work they want to keep before reinstalling once.

Current Android builds use the [signed Android feed](https://www.fabriziodegni.com/AudioEnhancerMAX/updates/android-v1.json). iOS and older test-signed Android builds use the [original companion feed](https://www.fabriziodegni.com/AudioEnhancerMAX/updates/companion-v1.json). The app checks the ECDSA P-256 signature using its bundled public key before reading release fields. It checks time validity and compares the candidate’s build number with the installed one. Package locations are derived from the approved project and verified release tag. Download failures or mismatches stop export. The feeds and direct downloads require HTTPS.

## Publish the next direct companion release

1. Build a non-debuggable Android release APK and sign it with the dedicated production app key. For Play, build the store-specific AAB and sign it with the separate upload key. Configure Play App Signing with the APK production key.
2. For Android, run `scripts/sign_companion_updates.py --android-only` with the APK, build-tools directory, pinned release certificate fingerprint, version, build, tag and existing update signing key. Write the result to `web/updates/android-v1.json`. Preserve the original feed for existing iOS and test-signed Android installations.
3. Publish the identical APK on the [official GitHub repository](https://github.com/sev7enITA/AudioEnhancerMAX/releases) and [official SourceForge project](https://sourceforge.net/projects/audioenhancermax/files/). Verify both public copies before deploying the Android feed and website links.
4. Verify the public feed signature and hashes. Test installation on a clean device and update separately from an older Android build signed by the production key when one is available.

The default validity is 90 days. Re-sign the current release if the feed is due to expire before the next build. Keep the private update key local and owner-readable. Only its public counterpart under `app/resources/mobile/` belongs in source control or a companion bundle. A key rotation requires a planned client update.
