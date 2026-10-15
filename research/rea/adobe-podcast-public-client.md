# Adobe Podcast public client analysis

The public Adobe Podcast client separates preview mixing, enhancement tracking and export creation. This offers concrete interaction patterns to evaluate for AudioEnhancerMAX: independently auditionable components, explicit processing states and export records tied to the settings the user reviewed. It does not reveal Adobe's remote audio model or establish comparative sound quality.

## Artifact and method

On 15 October 2026, the unauthenticated [Enhance page](https://podcast.adobe.com/enhance) referenced build `ca7050cd2d913a41ab4a`. Its main bundle's literal Webpack filename mapping identified three enhancement-related chunks: `EnhanceSpeech`, `ESV2_EA` and `ESV2_IP`. Those public, same-origin assets were downloaded without executing JavaScript, signing in or uploading audio. Authentication scripts on other origins were excluded.

REA 6.5.0 analyzed two immutable local snapshots. The first contained the HTML and main JavaScript bundle: 626 recovered bundled modules, 457,390 visited AST nodes and zero parse failures. Semantic analysis exhausted the configured 1 GiB worker heap; the overall graph is partial. The focused second snapshot contained the three enhancement chunks: 222,497 bytes, 14 bundled modules, 23,641 visited AST nodes and zero parse failures. Its graph also remains partial because shared dependencies are outside this snapshot, dynamic relationships remain unresolved and semantic node limits were reached. Counts are inventories, not completeness or quality scores.

Full files, acquisition manifests, REA Evidence, diagnostics and receipts remain in the Git-ignored `private/` directory. The versioned [finding ledger](findings-2026-10-15.json) records artifact hashes, Evidence IDs and source locations without distributing vendor code.

## Findings

The findings below combine REA's artifact/module identification with manual static inspection of the identified module. They describe visible code paths; runtime reachability and audible results have not been measured.

| Finding | Static observation | Implication for AudioEnhancerMAX research |
| --- | --- | --- |
| Import states | Per-track state distinguishes original/enhanced media, model version, errors and processing timestamps. Format/size/duration checks precede upload progress and track creation. | Compare the existing preflight and progress model against a documented state sequence; identify only gaps confirmed in our implementation. |
| Preview mixing | Web Audio code creates distinct gain nodes for original, enhanced, isolated speech, background and, in another branch, music. Player selection has merged/original/enhanced fallbacks. | Explore component audition and removed-signal listening in addition to the existing blind A/B workflow. These nodes do not show how remote stems are generated. |
| Export lifecycle | Export requests carry component selection, model version, strength and mute settings. Separate creation/polling state handles ready URLs, errors and timeout. | Test whether exported audio and its capsule retain exactly the parameters used for the reviewed preview. |

The primary location is module `90875` in [the captured EnhanceSpeech bundle](https://podcast.adobe.com/wp_flex_EnhanceSpeech.ca7050cd2d913a41ab4a.js). Source anchors are line 18 for import state, line 198 for export orchestration and line 285 for preview mixing. The build-specific URL may cease to resolve; local digest-bound evidence remains the reference.

REA also classified calls such as `headers.get` and UI property getters as network candidates in the broad bundle. These are not counted as verified service endpoints. Client candidate extraction needs adjudication against call context before it supports architectural claims.

## Remaining evidence

- Actual playback/export behavior needs a controlled runtime session and an agreed audio sample. No audio-quality, latency or feature-parity result is available from these static runs.
- Server DSP architecture, weights, training data and internal restoration algorithms remain unknown.
- Full cross-bundle call resolution would require a separately scoped combined analysis. The current focused findings do not claim complete application reconstruction.
- Native RX, Audition and Clarity studies need the selected local application/plugin artifact and a suitable configured analysis engine. Those applications were not found in the checked installation directories.

The main conclusion is a research direction, not a product change: preserve AudioEnhancerMAX's local processing and reviewable edits while evaluating richer component audition, explicit state transitions and preview/export consistency. The reusable runner and benchmark protocol are described in [REA competitor research](README.md).
