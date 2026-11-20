# 4.1 BETA code assessment

The assessment covers the new verification paths, input and output handling, and claims made by each platform. The second reviewer ran on the Mac in LM Studio using **Qwen3.8 27B Uncensored, Q6_K**. Its two reviews covered the desktop diff and the mobile verification, PCM metering, URI policy and model loading code. The release checks below use actual test results.

| Area | Review outcome |
|---|---|
| Input handling | Verification uses a bounded copy and hashes the bytes it actually copies. Desktop rejects unexpected types and mismatched headers before probing. Mobile works from a private local copy and uses provider permissions. |
| Request isolation | The Mac verification API accepts loopback same-origin use and at most one active verification. Android accepts a single read-granted content URI and prompts the user before analysis. iOS coordinates reads and releases the security scope before using its own copy. |
| Resource limits | Desktop caps incoming media at 500 MiB and measures at most 30 seconds. iOS also caps media at 500 MiB and bounds PCM format and sample count. Android caps received media at 100 MiB and applies a lower dynamic native validation budget. A heap failure or ambiguity in the Android JNI hash path produces an inconclusive result. |
| Audio evidence | Decoder and scope are recorded. Non-finite samples and empty decoded buffers are rejected. The desktop waveform remains on screen and is omitted from the JSON. |
| C2PA evidence | Verifiers distinguish integrity, signer trust, remote references and unavailable or ambiguous results. A report hash read from an invalid Mac manifest is labelled an unverified claim. The release fixture matches the processing report against the exact manifest hash. |
| Model loading | The optional ONNX graph is opened as a regular file and checked for an exact size and SHA-256. ONNX Runtime consumes the same bytes that were checked. Controlled-reference comparison matched six fixture fractions, with maximum per-sample score difference below 0.000008. |
| Cleanup | The Mac uses a temporary file scoped to each request. The companion apps delete their private snapshots on ordinary completion, cancellation and handled error. Android also prunes stale private verification snapshots. |

The model proposed some fixes that the source did not require. It flagged an iOS security-scope lifetime problem even though downstream readers consume the completed private copy. It also described a model file replacement race even though the digest is checked on the exact immutable bytes passed to the runtime. The Android metering loop discards the remainder of a buffer only after the defined preview limit. Those points were checked against the call sites rather than counted as resolved vulnerabilities.

Remaining limits include physical-phone and third-party Files-provider coverage, native decoder behavior for uncommon media, and fresh C2PA trust data before the bundled trust snapshot expires. The public sample uses a test certificate. The six AudioSeal comparisons evaluate implementation parity on controlled examples. Field performance and classifier false-positive rates are unevaluated.
