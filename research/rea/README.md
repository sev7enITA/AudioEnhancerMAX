# REA competitor research for AudioEnhancerMAX

This workspace connects REA 6.5.0 to repeatable research on commercial audio products. It is a developer research workflow, separate from the AudioEnhancerMAX processing pipeline. The objective is to understand interaction design, signal-processing controls, data flow and observable audio behavior, then test independently implemented improvements.

## Competitor selection

Checked on 15 October 2026. These products are selected for relevance to AudioEnhancerMAX, not as a worldwide usage ranking: public vendor figures do not establish comparable active-user or market-share statistics.

| Priority | Product | Questions with practical value for AudioEnhancerMAX |
| --- | --- | --- |
| First | [iZotope RX 12 Advanced](https://www.izotope.com/products/rx-advanced) | Spectral selection and repair, dialogue/music/effects stems, review of Repair Assistant suggestions. |
| First | [Adobe Podcast Enhance Speech v2](https://podcast.adobe.com/en/enhancespeech) | Enhancement intensity, voice/background controls, preview and processing-state feedback. |
| First | [Descript](https://www.descript.com/features) | Transcript-linked edits, filler/retake review, undo and Studio Sound. |
| Next | [Auphonic](https://auphonic.com/features) | Speaker leveling, multitrack ducking/bleed, editable gain curves, loudness statistics and multiple outputs. |
| Next | [Adobe Audition 26.5](https://helpx.adobe.com/audition/desktop/introduction/audition-releasenotes.html) | Noise-print restoration, spectral selections, diagnostics and multitrack effects. |
| Next | [Waves Clarity Vx Pro](https://www.waves.com/plugins/clarity-vx-pro) | Voice/ambience control, band solo/bypass/delta, network choice and ECO performance. |
| Secondary | [Antinode Clear, formerly Supertone Clear](https://antinodeaudio.com/clear) | Independent voice, ambience and reverb controls. |

Descript's [pricing page](https://www.descript.com/pricing) declares over six million creators and teams. Auphonic's [about page](https://us.auphonic.com/about_us) declares over two million users. These are vendor statements with different denominators, not comparative evidence of product quality or paid adoption. Local build identity must come from each selected artifact, even when a current product version is documented above.

The machine inventory on 15 October found none of the selected products in the checked system/user Applications and Audio Plug-Ins Components/VST3 directories. This bounded search does not establish that no copies exist elsewhere. Adobe Creative Cloud and Acrobat are not substitutes for Audition.

## Run an inspection

The integration uses Python's standard library and a version-pinned npm invocation. It does not add REA to the application dependencies or expose analysis endpoints in the product UI. Node.js must meet [REA's supported versions](https://github.com/morluto/rea#what-you-can-analyze). The first invocation can populate npm's package cache.

```bash
python3 scripts/rea_research.py targets

# Preview a command without starting an inspection or writing output.
python3 scripts/rea_research.py inspect --target descript \
  --kind javascript --artifact '/absolute/path/to/app.asar' --dry-run

# Analyze an explicitly selected extracted JS tree or ASAR.
python3 scripts/rea_research.py inspect --target descript \
  --kind javascript --artifact '/absolute/path/to/app.asar' \
  --version-label 'version shown by the selected artifact'

# Inspect a selected macOS executable without a decompiler.
python3 scripts/rea_research.py inspect --target izotope-rx \
  --kind macho --artifact '/absolute/path/to/selected/executable'

# Native analysis after configuring an existing engine.
python3 scripts/rea_research.py inspect --target izotope-rx \
  --kind native --provider ghidra --artifact '/absolute/path/to/selected/executable'

# Decompile only an explicitly selected symbol or address.
python3 scripts/rea_research.py inspect --target antinode-clear \
  --kind decompile --provider ghidra --procedure '_selected_symbol' \
  --artifact '/absolute/path/to/selected/executable'
```

`--kind managed` and `--kind plist` support selected .NET assemblies and Apple property lists. Native analysis requires a configured Ghidra, Hopper or IDA provider. On this machine, Ghidra 12.1.4 has been verified from the official release checksum, its macOS arm64 tools built with the existing JDK 21, and its provider checks passed. Codex receives the provider paths through `mcp_servers.rea.env`. Provider installation is not part of the wrapper. For shell use, set `GHIDRA_INSTALL_DIR` and `JAVA_HOME` as shown in [the native environment record](native-environment.md).

Each run creates a unique owner-only directory under `research/rea/private/runs/`, with full `evidence.json`, `stderr.log` and `receipt.json`. The receipt records the exact command, pinned package, timestamps, exit status, evidence hash and input file hashes. Directory identities are supplied by REA evidence. `recorded` means a successful JSON result was retained; inspect its limitations, unknowns and coverage before making a claim. Explicitly partial graphs, pseudocode warnings or absent function bodies produce `recorded_partial`, which still returns exit code zero because usable evidence was retained. Interrupted, failed and timed-out runs retain their diagnostic output and never receive those statuses. A changed input file is flagged separately. Headerless analysis requires an explicit Ghidra provider, `--raw-architecture` and `--entry-point`; preserve the derivation from the original artifact and the context omitted from any selected fragment.

All contents of `private/` are Git-ignored, including vendor bundles and local reports. Keep reusable findings and original implementation requirements in versioned notes; preserve vendor code, captures and proprietary artifacts only in the local evidence area. No automatic target execution, browser login, audio upload or competitor installer download is implemented by this wrapper. Native providers may create their own analysis databases.

The Codex MCP registration and matching skill are user-level and shared with this project's research workflow. A running chat may still need a restart to discover the new tools; the CLI workflow works independently. The installation smoke test verified MCP initialization, 207 advertised tools and a synthetic JavaScript import graph. It did not validate every adapter or analyze a competitor.

## Evidence and study sequence

1. Select one product, exact version/artifact and a feature question from `targets.json`.
2. Preserve acquisition origin, byte identity and the selected scope. Start with static package/resource inspection, then examine only modules relevant to the question.
3. Record observations, inferences and unresolved questions separately, with REA Evidence IDs and source locations. A string or endpoint name is a candidate, not proof that a code path executes.
4. For cloud products, frontend assets can explain client controls, job orchestration and data formats. They cannot establish the architecture, training data, weights or internal algorithms of remote DSP models.
5. Use controlled input/output tests when the question concerns audible behavior. Record exact settings, versions and outputs before comparing. Product accounts and cloud audio submission are distinct from static inspection.
6. Translate supported findings into independent AudioEnhancerMAX requirements; retain attribution and measure the resulting implementation.

The real-artifact investigations are documented in [Adobe Podcast public client analysis](adobe-podcast-public-client.md) [Clear native analysis](clear-native-analysis.md) and [Descript public artifact](descript-public-artifact.md). The [AudioEnhancer validation plan](audioenhancer-validation-plan.md) maps those observations to specific source-code questions and discriminating tests; the [GLM-5.3 review](review-glm-2026-10-15.md) records received responses and corrections. Local acquisitions and full evidence remain under `private/`.

## Audio comparison protocol

Use the same original PCM inputs for every product: clean speech, steady noise, transient noise, reverberant speech, clipped speech, breaths/clicks, overlapping speakers and speech over music. Include Italian and English voices, and retain a clean reference when one exists. Keep listening excerpts short and level-match them; preserve the original exports for measurements.

Record sample rate, channels, format, product/build, settings, processing duration and hardware. Measure integrated loudness, short-term behavior, LRA, true peak using a documented oversampling method, residual noise in marked non-speech regions and retained speech duration. Report latency/CPU only from runtime measurements. Compare intelligibility and artifacts through blinded listening; do not replace listening quality with a single waveform or loudness score. Use intrusive metrics only when a suitable aligned clean reference exists.

AudioEnhancerMAX already documents transcript-linked EDL, undo/redo, five delivery profiles, blind A/B and checksum-backed capsules. Investigate incremental additions: region/stem-specific repair with removed-signal monitoring; speaker-aware multitrack leveling with editable gain; and measured delivery statistics beyond the currently documented estimated true peak. These are research candidates, not verified gaps or implementation commitments.

## Validation

```bash
python3 -m unittest discover -s tests -p 'test_rea_research.py' -v
```

The focused checks cover command planning, path preservation, output isolation, failed/malformed results, artifact changes, evidence identity and timeout cleanup. They do not assess audio quality or competitor feature parity.

## Product follow-through: 3.8

The later [revision delivery implementation](../../docs/revision-delivery.md) applies the checkpoint, export and evidence-state findings. Its tests use synthetic audio; this does not convert the static competitor observations into runtime or audio-quality findings. See [3.8 release status](../../releases/RELEASE_NOTES_v3.8.0.md).
