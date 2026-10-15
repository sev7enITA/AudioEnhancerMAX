# AudioEnhancerMAX 3.8 claims and evidence

| Public claim | Evidence | Boundary |
|---|---|---|
| Verified DSP resumption | `tests/test_revision_delivery.py`, checkpoint source/options/build/hash checks | Neural and LAN paths do not resume |
| Current conversions | Reprocess A/B, WAV-to-FLAC primary switch, stale revision tests | Existing pre-revision files use documented migration |
| Exact-export delivery evidence | Downloaded-byte SHA-256 equals measured artifact, including MP3 and speech-edit FLAC | Guidance, not certification |
| Current result UI | Four JavaScript state regressions | Not a full accessibility or all-browser audit |
| Local operation | Complete local source tree, loopback server, runtime privacy gates | Optional TTS/LAN boundaries remain explicit |
| 75 Python tests + 4 JS tests | Local release validation, 2026-10-15 | Synthetic/functional coverage, not universal audio-quality proof |
| Signed direct Mac preview | Developer ID package | Apple notarization blocked by team agreement; stable 3.7 remains available |

Optional neural components and MakeMyVoice require their own available runtimes. The Android debug worker remains experimental and disabled by default. No App Store publication claim.
