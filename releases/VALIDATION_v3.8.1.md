# AudioEnhancerMAX 3.8.1 validation

15 October 2026. Implementation commit: `6caf035`.

## Verified

- 75 Python tests passed, with 8 unittest subtests and six existing warnings. Four JavaScript state regression tests passed.
- The repository presentation check passed locally and in [GitHub Actions](https://github.com/sev7enITA/AudioEnhancerMAX/actions/runs/38752843138). It checks owned text after decoding HTML entities and also detects JavaScript/CSS escape forms of the prohibited punctuation. Third-party vendored code and licenses are excluded.
- Public presentation link checks and `git diff --check` passed.
- The new macOS arm64 DMG was mounted read-only. Recursive strict Developer ID signature validation passed. The contained app reports version/build 3.8.1/3.8.1, and its embedded frontend files match the source byte for byte.
- The packaged app uploaded and normalized a generated five-second modulated sinusoid, exported MP3, and produced matching content, download-header and compliance SHA-256 values: `7a0b2b0c6c44051da6854aaadba6f2d6f90d5466789c125b1c33ccd817a68370`. This matches the 3.8.0 fixture result; it is not a universal determinism or perceptual-quality requirement.
- SourceForge metadata was saved through the authenticated project administration form and verified on the public project page.
- The build uses a complete local checkout outside Desktop/iCloud.

## Limits

The DMG is Developer ID signed, not notarized or stapled. Apple notarization remains blocked by the developer-team agreement reported as HTTP 403 during the 3.8.0 release. This maintenance release did not retry that unchanged external gate. The existing notarized 3.7.0 remains the stable Mac download.

Audio processing behavior is unchanged. These checks do not establish perceptual audio quality, competitor equivalence, optional-model quality, or production readiness of the experimental trusted-LAN worker.
