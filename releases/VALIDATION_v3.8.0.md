# AudioEnhancerMAX 3.8.0 validation

15 October 2026. Implementation commit: `3b81a73c35b862fe556ae8961f33a97336c06763`.

## Verified locally

- 75 Python tests passed, including 13 revision/checkpoint regression cases; 8 unittest subtests also passed. Six warnings concern deprecated framework hooks/test-client support and one deliberately constant synthetic clipping fixture.
- Four JavaScript state regressions passed: invalidation on failed processing, rejection of stale compliance, disabled downloads during processing, and rejection of a result for a replaced file.
- Browser smoke: upload a generated five-second modulated sinusoid, normalize to -16 LUFS, select MP3 delivery, download MP3. Download SHA-256 equals the compliance artifact SHA-256.
- Signed-DMG smoke: mount read-only, verify Developer ID signature recursively with strict validation, launch the contained arm64 application against separate temporary data, upload/process/export the synthetic fixture over loopback HTTP, compare download header/content/compliance SHA-256. Passed. Bundle version/build: 3.8.0/3.8.0. Embedded frontend files match the source tree byte for byte.
- Browser and packaged fixture MP3 SHA-256: `7a0b2b0c6c44051da6854aaadba6f2d6f90d5466789c125b1c33ccd817a68370`. This is a fixture result, not a universal determinism requirement.
- `pip check` passed. The installed build environment returned no known advisories in the 15 October 2026 `pip-audit` snapshot.
- Website local asset/link checks and repository presentation policy checks passed. `git diff --check` passed.
- Release work was performed from a complete checkout outside Desktop/iCloud. No source placeholders are required for compilation.

## Limits

Apple notarization returned HTTP 403: the developer team must accept an agreement. The DMG is signed but not notarized or stapled; it is distributed as a preview. Stable macOS remains the existing notarized 3.7.0 artifact. No Mac App Store release is claimed.

The synthetic tests do not establish perceptual audio quality, competitor equivalence, optional-model quality, or production readiness of the experimental trusted-LAN worker. Only deterministic local DSP paths use resumable checkpoints. Keep one backend worker per data directory.

The current GitHub workflow runs the Python/JavaScript suite on Linux; its execution result is recorded separately by GitHub Actions. Local test results do not imply a remote CI pass.
