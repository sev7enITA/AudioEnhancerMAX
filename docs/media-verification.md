# Verify content

Open **Verify content** on Mac or **Verify** in the companion and select a supported local file. The app fingerprints the bytes it receives and runs the checks against a private snapshot. Sharing an attachment from another app may deliver a converted file. Compare the SHA-256 with an independently obtained original when the distinction matters.

The report groups the file fingerprint, C2PA checks and audio measurements. The 4.1.2 companion also includes technical track metadata. It is a separate unsigned JSON document. A C2PA reference to a processing report is the hash declared by the manifest. Compare it with the SHA-256 of the exact processing report bytes independently. A missing or unresolved credential leaves the provenance unknown. For a real review, interpret integrity, signer trust and timing separately.

The C2PA reader accepts WAV, MP3, FLAC, M4A, MP4 and MOV. Android limits media to 100 MiB and further limits C2PA reads based on available memory. Mac and iOS accept up to 500 MiB. Android C2PA requires Android 9 or later. The audio measurements are from a limited prefix. The Mac downmixes the first track to mono at 48 kHz and analyzes up to 30 seconds. Near-full-scale samples and the peak envelope describe this preview. Channel-specific clipping, edits later in a file and the authenticity of a recording require other evidence.

## Companion media metadata and format support

In the 4.1.2 companion, **Verify → Media metadata** reads the selected audio or video locally from the same private snapshot as the file fingerprint. Depending on the file and device, the panel can show the container, track codecs, resolution, sample rate, channel count, and selected embedded tags. **Artwork EXIF** displays selected camera and exposure fields when a bounded embedded image contains EXIF. Those fields describe the artwork. A video can carry separate QuickTime camera metadata, and an MP3 can carry ID3 tags. These values can be edited by other software and are independent of the C2PA verdict. The reader omits GPS fields. Descriptive tags and artwork EXIF stay out of the shared JSON.

The mobile apps can also show metadata and available audio measurements beyond the six C2PA formats. Android adds raw AAC, Ogg, AMR and 3GP. iOS adds raw AAC, CAF, AIFF and 3GP.

Studio uses the selected format to filter the file picker, checks the container signature and tracks, then tries the local decoder. Importing for editing requires one readable mono or stereo audio track at 8–96 kHz, a source up to 100 MiB, and up to 64 MiB of decoded PCM. Verify can inspect media that falls outside the editing limits. Metadata availability depends on the file, parser and operating system.

| Family | Studio import and edit | Notes |
| --- | --- | --- |
| WAV | Android and iOS include a native path for PCM 16/24/32-bit and float32 RIFF/WAVE. | Broadcast WAV can be edited when its PCM is compatible. Android Verify shows selected `bext` fields. The RF64 sample was readable in iOS Verify and outside the Android reader's scope. |
| MP3 | Android and iOS use the device decoder for MPEG Layer III. | ID3 tags and attached artwork are independent of the audio stream. |
| M4A / AAC | Android and iOS accept audio-only MPEG-4 and raw AAC/ADTS when decodable. | M4A can contain AAC or ALAC. ALAC availability depends on the local decoder, and raw ADTS usually carries fewer descriptive tags. |
| FLAC | Android and iOS try the native lossless decoder. | Available tags and supported channel layouts depend on the OS and file. |
| Ogg / Opus, AMR | Android opened Ogg Vorbis/Opus and AMR-NB/WB in the emulator. iOS offers a conditional filter that uses the local decoder. | The iOS simulator decoded Ogg Opus. The Vorbis and both AMR fixtures had no usable decoder on that simulator. Ogg is a container. AMR-NB and AMR-WB are distinct codecs at 8 kHz and 16 kHz respectively. |
| CAF / AIFF | The iOS Studio exposes both through AVFoundation. | Audio decoding depends on the codec carried by the container. |
| MP4 / MOV / 3GP | The video picker includes these families where supported. Studio edits the audio track. | MP4 video export requires a compatible H.264 video and AAC audio pair, and an edit that preserves the full audio timeline. A file with no audio can still be inspected in Verify. |

Studio creates WAV revisions. A compatible video export creates a new MP4 with a re-encoded AAC track. Check the original when you need its metadata, auxiliary tracks or credentials.

The companion readers use [Android media extraction](https://developer.android.com/reference/android/media/MediaMetadataRetriever) and [AVFoundation metadata key spaces](https://developer.apple.com/documentation/avfoundation/avmetadataitem). Device codec support follows the [Android media format matrix](https://developer.android.com/media/platform/supported-formats) or the Apple frameworks.

[EXIFfromMP4](https://github.com/Davidebyzero/EXIFfromMP4) covers per-frame EXIF from specific Panasonic GH5 4K/6K Photo recordings. [AryanVBW/Exif](https://github.com/AryanVBW/Exif) is a Python desktop and command-line application. [ExifTool upstream](https://github.com/exiftool/exiftool) is a separate external reference for broader inspection.

## Optional AudioSeal detector on Mac

The experimental measurement targets Meta AudioSeal 16-bit. On the Mac download the **AudioSeal Detector Pack** from the [release page](https://github.com/sev7enITA/AudioEnhancerMAX/releases/tag/v4.1.0-beta.1), unzip it, and place `audioseal-detector.onnx` in `~/Library/Application Support/AudioEnhancerMAX/models/`. Create the folder if necessary. The app checks the exact size and SHA-256 before loading the graph. Return to **Verify content**, select the AudioSeal option and choose the file.

- AudioSeal detector source checkpoint is [Meta AudioSeal](https://huggingface.co/facebook/audioseal/tree/3c19eba53390776cf2cc9ed5f6c9ac67ce72ecba), under the MIT licence.
- The ONNX graph is the [pinned ONNX port](https://huggingface.co/synath/audioseal-onnx/tree/aacb1186bedc8118960e5ce8a7849861bf9a4c6c) with SHA-256 `3ff3991c4bf4426c5aed8b122610833cb4cd7e02535d6edeae6380199f809ca2` and size 34,759,744 bytes.
- AudioSeal reads the first audio track downmixed to 16 kHz mono. It reports the fraction of analyzed samples above the model’s 0.5 signal threshold over a prefix of 1 to 10 seconds. The result is a model measurement specific to this watermark scheme. Numerical agreement on controlled examples gives no estimate of false positives or false negatives in actual recordings.

The detector does not fetch a model or send audio. Remove the pack file to disable it. Speech anti-spoofing models and other watermark families remain in evaluation, subject to domain validation and distribution review.
