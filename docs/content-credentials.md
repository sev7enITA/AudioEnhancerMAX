# Content Credentials in AudioEnhancerMAX

The desktop build can embed a signed C2PA manifest in WAV, MP3 and FLAC exports from Enhance and Speech Editor. In the result panel, choose the delivery format, open **Content Credentials** and select **Export signed copy**. The export keeps the ordinary download available and leaves the source and processing master intact.

The signature binds the exported file to a manifest naming AudioEnhancerMAX and its version, recording the operation, and linking to the source as a parent ingredient. When a supported original import has an ingest record, its existing embedded credential can be inherited even if the editor used a decoded WAV copy. Older imports without that record use the source identified by the processing report. An upstream credential can carry its own disclosures, so inspect that credential before sharing a signed export publicly.

The AudioEnhancerMAX assertion records the output revision, SHA-256 of the exact processing report, and SHA-256 of the unsigned export. Use the **Processing Report** JSON download to compare the report fingerprint. The app adds no transcript, original filename, full processing report or processing settings to its own assertion. The metadata identifies the signing certificate. The credential records what the issuer asserts about provenance and lets recipients check the file binding and signature. Ownership, recording consent and accuracy of the underlying content require separate evidence.

## Configure a signing identity

The verifier works without a signing identity. To enable export, place these PEM files in the desktop app data directory under `c2pa`:

- `signing-chain.pem` contains the leaf certificate first, followed by its issuing chain.
- `signing-key.pem` contains the corresponding unencrypted ES256 / NIST P-256 private key. On macOS and Linux set its permissions to `0600`. Keep the parent directory private.

On macOS direct builds the usual path is `~/Library/Application Support/AudioEnhancerMAX/c2pa`. Source installations use `AEMAX_DATA_DIR` if supplied, otherwise the repository’s `app` data directory. Keep the credential outside the code repository. Open the Content Credentials panel again after configuring it. AudioEnhancerMAX performs signing locally and omits an external timestamp service. Verification uses the packaged official signer and TSA trust-list snapshots dated 4 November 2026. When the earliest published next-update date passes (2 February 2027, 17:02 UTC), the app falls back to integrity verification until an updated build supplies new anchors. It checks embedded credentials without remote manifest or live OCSP fetches. The PEM snapshots provide anchors for the SDK and do not apply the richer historical status fields of the official JSON lists.

This release exposes software signing for evaluation with a locally configured identity. For a production signing profile, plan the issuer, protected key storage, certificate rotation, timestamping and trust-list recognition. A private test CA produces a valid signature that public validators can report as unrecognized. The C2PA Conformance Program has a separate evaluation and onboarding process. [Signing certificates](https://opensource.contentauthenticity.org/docs/signing/get-cert/) · [C2PA Conformance Program](https://c2pa.org/conformance/) · [Production enrollment plan](c2pa-production-enrollment.md)

## Verify a file

Open **Verify Content Credentials** above the recording details. The local inspector accepts WAV, MP3, FLAC, M4A, MP4 and MOV. It distinguishes a recognized certificate from an intact signature whose signer is unrecognized, a failed validation and an asset without embedded credentials. Copying the signed file preserves the binding. Transcoding and other downstream changes can remove the manifest or invalidate its binding. Companion apps can hand off work to the desktop through their existing workflow. This implementation covers desktop exports and the desktop inspector.

A technical demonstration can pair the same synthetic recording before and after signing. Inspect the signed WAV with the app and the Content Authenticity Initiative’s C2PA Tool, then change one sample in a duplicate and verify that validation fails. [Audio provenance guidance](https://spec.c2pa.org/specifications/specifications/2.4/music/guidance_applying_content_credential_music_assets.html) · [C2PA Tool](https://opensource.contentauthenticity.org/docs/c2patool/docs/usage/)

## Suggested launch copy

Italiano: «AudioEnhancerMAX supporta le Content Credentials C2PA negli export desktop WAV, MP3 e FLAC. Con un certificato di firma configurato, puoi allegare all’audio una provenienza firmata e verificare l’integrità del file in locale.»

English: “AudioEnhancerMAX supports C2PA Content Credentials for desktop WAV, MP3 and FLAC exports. With a signing certificate configured, you can attach signed provenance to your audio and check the file’s integrity locally.”

Use this wording for a build that includes the feature. Explain the test issuer when showing a sample. Reserve claims about official conformance or recognition for the relevant independent result.
