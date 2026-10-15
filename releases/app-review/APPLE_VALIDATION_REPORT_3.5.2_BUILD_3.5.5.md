# AudioEnhancerMAX 3.5.2 (Build 3.5.5) - Validation Report

Validation date: 19 July 2026

## Release artifact

- Package: `AudioEnhancerMAX-v3.5.2-build-3.5.5-MacAppStore.pkg`
- Package size: 1,830,321,081 bytes (approximately 1.70 GiB)
- Package SHA-256: `9e8c9e9169b803eb24c9939775c5d822b6b4680712f413a091a9badd30c1ea8e`
- Review sample SHA-256: `ffeb0404b2297182811be38c8e2f7a0a6fb19e4ba8cfb7efe32d346ce2339ff4`

## Package, identity, and signing

- PASS - `pkgutil --check-signature` accepted the installer certificate chain.
- PASS - Installer identity: `3rd Party Mac Developer Installer: Fabrizio Degni (BR9VY292BU)`.
- PASS - Installer trusted timestamp: `2026-07-19 11:45:02 +0000`.
- PASS - Application identity: `3rd Party Mac Developer Application: Fabrizio Degni (BR9VY292BU)`.
- PASS - Marketing version 3.5.2 and build 3.5.5.
- PASS - Info.plist names the display name, bundle name, and executable AudioEnhancerMAX.
- PASS - Main executable is native arm64.
- PASS - Entitlements: App Sandbox, user-selected file read/write, network client, and network server.

## Menu and About correction

- PASS - The root application menu is explicitly titled AudioEnhancerMAX instead of inheriting Python's process name.
- PASS - The standard Python About action was removed.
- PASS - `About AudioEnhancerMAX` targets an app-owned selector and creates an app-owned native window.
- PASS - About content includes logo, product version/build, Mac App Store distribution, Fabrizio Degni attribution, purpose, features, privacy boundaries, system requirements, supported formats, safe support guidance, architecture, MIT License, copyright, and official resource links.
- PASS - About window construction and embedded WKWebView initialization completed without exception.

## Existing functional validation retained

- PASS - Native AppKit/WKWebView application window; no default-browser launch.
- PASS - Embedded service bound only to loopback during the core workflow.
- PASS - Native Open panel, WAV upload, Remove Noise processing, and native Save panel.
- PASS - Closing the main window stops the process and releases the loopback port.
- PASS - Packaged Faster-Whisper model, VAD asset, PyAV codecs, privacy manifest, and third-party notices.

## Manual gate

After Transporter processing, install build 3.5.5 through TestFlight and include the corrected application menu and About window in the continuous physical-device recording requested by Apple.
