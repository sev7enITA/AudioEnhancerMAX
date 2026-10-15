# AudioEnhancerMAX 3.8.2 validation

15 October 2026.

- 75 Python tests passed, with 8 unittest subtests and six existing warnings. Four JavaScript state regression tests passed.
- Repository presentation, link and punctuation checks passed. Public descriptions and feature lists were inspected for consistency with the delivered audio workflow.
- The macOS arm64 DMG was mounted read-only. Recursive strict Developer ID signature validation passed. The contained application reports version/build 3.8.2/3.8.2, and its embedded frontend files match the source byte for byte.
- The packaged application uploaded and normalized a generated five-second modulated sinusoid, exported MP3, and produced matching content, download-header and compliance SHA-256 values: `7a0b2b0c6c44051da6854aaadba6f2d6f90d5466789c125b1c33ccd817a68370`. This matches the earlier 3.8 fixture results; it is not a universal determinism or perceptual-quality requirement.
- SourceForge metadata was saved through the authenticated project administration form and verified on the public project page.
- The build uses a complete local checkout outside Desktop/iCloud.

## Limits

The DMG is Developer ID signed, not notarized or stapled. The Apple developer-team agreement still needs acceptance before notarization can complete. The existing notarized 3.7.0 remains the stable Mac download.

Audio processing behavior is unchanged. These checks do not establish perceptual audio quality, optional-model quality, or production readiness of the experimental trusted-LAN worker. The GitHub workflow records remote CI results separately.
