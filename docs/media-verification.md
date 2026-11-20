# Verify content

Open **Verify content** on Mac or **Verify** in the companion and select a supported local file. The app fingerprints the bytes it receives and runs the checks against a private snapshot. Sharing an attachment from another app may deliver a converted file. Compare the SHA-256 with an independently obtained original when the distinction matters.

The report groups the file fingerprint, C2PA checks and audio measurements. It is a separate unsigned JSON document. A C2PA reference to a processing report is the hash declared by the manifest. Compare it with the SHA-256 of the exact processing report bytes independently. A missing or unresolved credential leaves the provenance unknown. For a real review, interpret integrity, signer trust and timing separately.

The apps accept WAV, MP3, FLAC, M4A, MP4 and MOV for verification. Android limits media to 100 MiB and further limits C2PA reads based on available memory. Mac and iOS accept up to 500 MiB. Available decoders depend on the platform. Android C2PA requires Android 9 or later. The audio measurements are from a limited prefix. The Mac downmixes the first track to mono at 48 kHz and analyzes up to 30 seconds. Near-full-scale samples and the peak envelope describe this preview. Channel-specific clipping, edits later in a file and the authenticity of a recording require other evidence.

## Optional AudioSeal detector on Mac

The experimental measurement targets Meta AudioSeal 16-bit. On the Mac download the **AudioSeal Detector Pack** from the [release page](https://github.com/sev7enITA/AudioEnhancerMAX/releases/tag/v4.1.0-beta.1), unzip it, and place `audioseal-detector.onnx` in `~/Library/Application Support/AudioEnhancerMAX/models/`. Create the folder if necessary. The app checks the exact size and SHA-256 before loading the graph. Return to **Verify content**, select the AudioSeal option and choose the file.

- AudioSeal detector source checkpoint is [Meta AudioSeal](https://huggingface.co/facebook/audioseal/tree/3c19eba53390776cf2cc9ed5f6c9ac67ce72ecba), under the MIT licence.
- The ONNX graph is the [pinned ONNX port](https://huggingface.co/synath/audioseal-onnx/tree/aacb1186bedc8118960e5ce8a7849861bf9a4c6c) with SHA-256 `3ff3991c4bf4426c5aed8b122610833cb4cd7e02535d6edeae6380199f809ca2` and size 34,759,744 bytes.
- AudioSeal reads the first audio track downmixed to 16 kHz mono. It reports the fraction of analyzed samples above the model’s 0.5 signal threshold over a prefix of 1 to 10 seconds. The result is a model measurement specific to this watermark scheme. Numerical agreement on controlled examples gives no estimate of false positives or false negatives in actual recordings.

The detector does not fetch a model or send audio. Remove the pack file to disable it. Speech anti-spoofing models and other watermark families remain in evaluation, subject to domain validation and distribution review.
