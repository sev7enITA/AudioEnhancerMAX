# Content Credentials in AudioEnhancerMAX

The desktop build can embed a signed C2PA manifest in WAV, MP3 and FLAC exports from Enhance and Speech Editor. In the result panel, choose the delivery format, open **Content Credentials** and select **Export signed copy**. The export keeps the ordinary download available and leaves the source and processing master intact.

The signature binds the exported file to a manifest naming AudioEnhancerMAX and its version, recording the operation, and linking to the source as a parent ingredient. When a supported original import has an ingest record, its existing embedded credential can be inherited even if the editor used a decoded WAV copy. Older imports without that record use the source identified by the processing report. An upstream credential can carry its own disclosures, so inspect that credential before sharing a signed export publicly.

The AudioEnhancerMAX assertion records the output revision, SHA-256 of the exact processing report, and SHA-256 of the unsigned export. Use the **Processing Report** JSON download to compare the report fingerprint. The app adds no transcript, original filename, full processing report or processing settings to its own assertion. The metadata identifies the signing certificate. The credential records what the issuer asserts about provenance and lets recipients check the file binding and signature. Ownership, recording consent and accuracy of the underlying content require separate evidence.

## Configure a signing identity

The verifier works without a signing identity. The public Mac 3.9.1 BETA build 3.9.10 uses the local test configuration below. The newer direct Mac source adds Keychain signing and timestamp verification.

### Direct Mac Keychain enrollment

After agreeing on the subject and CSR requirements with the certificate authority, generate the CSR with the installed Developer ID app. Using that executable lets macOS associate Keychain access with the signing application. Replace the example subject fields with the legal values agreed for the product.

```sh
/Applications/AudioEnhancerMAX.app/Contents/MacOS/AudioEnhancerMAX --c2pa-csr \
  --tag publication-1 --common-name 'PRODUCT CN' \
  --organization 'REGISTERED ORGANIZATION' --country IT \
  --output ./publication-1.csr.pem
```

The command creates a non-extractable P-256 key in the default macOS Keychain and writes its public PKCS#10 request. Reusing the tag generates a CSR for the same key. Use a new tag for rotation. For source development, run the equivalent command with `python -m desktop.launcher` in the same Python environment used for signing. Provision the real identity from the signed desktop app so access follows the installed executable.

Place the issued leaf followed by its issuing chain in `signing-chain.pem` under your app data `c2pa` directory. Save `signing.json` in that directory. Use the HTTPS endpoint confirmed by your CA or timestamp authority.

```json
{
  "keychain_tag": "publication-1",
  "tsa_url": "https://ts-c2pa.ssl.com/rsa"
}
```

The app matches the leaf certificate against the Keychain public key before signing. Keychain signs locally. The configured TSA receives an RFC 3161 request containing an imprint, and the app embeds the returned timestamp. A configured Keychain export requires a verified timestamp anchored in the packaged TSA trust list. If signing or timestamp validation fails, the app refuses the signed download. Inspect the signed file to see the signer trust and timestamp trust results. For the production enrollment sequence, see [the enrollment plan](c2pa-production-enrollment.md).

### Local test signing

For offline testing, leave `signing.json` absent and place these PEM files in the app data `c2pa` directory:

- `signing-chain.pem` contains the leaf certificate first, followed by its issuing chain.
- `signing-key.pem` contains the corresponding unencrypted ES256 / NIST P-256 private key. On macOS and Linux set its permissions to `0600`. Keep the parent directory private.

On macOS direct builds the usual path is `~/Library/Application Support/AudioEnhancerMAX/c2pa`. Source installations use `AEMAX_DATA_DIR` if supplied, otherwise the repository’s `app` data directory. Store the signing configuration outside the code repository and reopen the Content Credentials panel after configuring it. Local test signing runs offline without a timestamp service. A private test CA produces a valid signature that public validators can report as unrecognized. [Signing certificates](https://opensource.contentauthenticity.org/docs/signing/get-cert/) · [C2PA Conformance Program](https://c2pa.org/conformance/)

Verification uses packaged signer and TSA trust-list snapshots dated 4 November 2026. At their earliest published next-update (2 February 2027, 17:02 UTC), refresh both official trust-list snapshots in a new build to keep timestamped exports available. The inspector continues to check integrity offline, with remote manifest and live OCSP fetches disabled. The SDK uses the public PEM trust anchors. The official JSON lists contain additional historical status information.

## Verify a file

Open **Verify C2PA Content Credentials** above the recording details or use **Open C2PA verifier** from the audio watermark panel. The local inspector accepts WAV, MP3, FLAC, M4A, MP4 and MOV. It distinguishes a recognized certificate from an intact signature whose signer is unrecognized, a failed validation and an asset without embedded credentials. Copying the signed file preserves the binding. Transcoding and other downstream changes can remove the manifest or invalidate its binding. Companion apps can hand off work to the desktop through their existing workflow. This implementation covers desktop exports and the desktop inspector.

A technical demonstration can pair the same synthetic recording before and after signing. Inspect the signed WAV with the app and the Content Authenticity Initiative’s C2PA Tool, then change one sample in a duplicate and verify that validation fails. [Audio provenance guidance](https://spec.c2pa.org/specifications/specifications/2.4/music/guidance_applying_content_credential_music_assets.html) · [C2PA Tool](https://opensource.contentauthenticity.org/docs/c2patool/docs/usage/)

## Suggested launch copy

Italiano: «AudioEnhancerMAX supporta le Content Credentials C2PA negli export desktop WAV, MP3 e FLAC. Con un certificato di firma configurato, puoi allegare all’audio una provenienza firmata e verificare l’integrità del file in locale.»

English: “AudioEnhancerMAX supports C2PA Content Credentials for desktop WAV, MP3 and FLAC exports. With a signing certificate configured, you can attach signed provenance to your audio and check the file’s integrity locally.”

Use this wording for a build that includes the feature. Explain the test issuer when showing a sample. Reserve claims about official conformance or recognition for the relevant independent result.
