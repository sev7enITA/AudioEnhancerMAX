# AudioEnhancerMAX 3.7.0: Evidence-Led Launch Campaign

Updated: 28 August 2026

## Campaign idea

**Hear the change. See every decision.**

Version 3.7 is positioned around control rather than automation hype. The product story is that audio cleanup becomes reviewable: diagnosis is measurable, Smart Enhance settings are deterministic, speech edits require approval, delivery checks expose their rules, and a checksum-backed capsule carries the available evidence.

## Audience and message

| Audience | Problem | 3.7 message | Evidence asset |
| --- | --- | --- | --- |
| Podcasters and interviewers | Cleanup is slow and automated cuts can damage pacing | Review transcript-linked cut/mute decisions and export from a podcast profile | 60-90 second Precision Editor demo |
| Journalists and researchers | Source preservation and traceability matter | Keep the original, render approved decisions to a new file, retain JSON report/EDL | Source/output/report walkthrough |
| Educators and voice creators | Too many audio settings and delivery formats | Start from five explicit delivery profiles and see applied overrides | Output-profile carousel |
| Producers and delivery teams | It is easy to miss loudness, peak, or clipping problems | Inspect rule-level local delivery guidance before export | Compliance Lab walkthrough |
| Collaborative researchers | Outputs and decisions are difficult to hand off with provenance | Export a SHA-256 Project Capsule; include the original only by explicit choice | Capsule manifest demo |
| Privacy-conscious Mac users | “AI audio” often hides data flows | Core DSP and packaged transcription are local; optional paths are independently controlled | What-runs-where diagram |
| Open-source developers | Claims can drift from actual packaged capabilities | Capability registry exposes actual engines and fallbacks | Code-to-UI proof ledger |

## Message hierarchy

1. **Primary:** Local-first audio production, reviewed by the user.
2. **Proof:** deterministic Smart Enhance + revisioned Precision Editor + processing report.
3. **Delivery:** five fixed profiles, transparent compliance guidance, blind A/B listening, and a portable evidence capsule.
4. **Trust:** native Mac window, loopback-only core service, explicit optional data paths.
5. **Call to action:** download/review the release only from the live approved channel; until then, follow the release candidate on GitHub.

## Launch assets

### Required before public launch

- Final signed 3.7.5 PKG and checksum.
- TestFlight installation on the physical Mac.
- Apple-requested continuous 3-5 minute reviewer video.
- Six App Store screenshots from the packaged build.
- One 16:9 launch video, 60-90 seconds.
- One 20-30 second vertical cut using the same verified workflow.
- Developer-owned before/after WAV pair, level-matched for comparison.
- Processing report JSON from that exact example.
- Release notes, claims matrix, privacy page, support page and roadmap.
- App Store description, What’s New, keywords and Review Notes.

### Recommended launch folder structure

```text
AudioEnhancerMAX-3.7-launch/
  app-store/
  screenshots/
  video/
  audio-demo/
  press/
  social/
  evidence/
```

## Demonstration script: 75 seconds

1. **0-7 s:** Launch AudioEnhancerMAX as a native Mac app; title: “Hear the change. See every decision.”
2. **7-18 s:** Upload the developer-owned WAV and show local diagnosis.
3. **18-30 s:** Select Balanced Smart Enhance; show the measured reasons, not an unsupported quality score claim.
4. **30-48 s:** Open Precision Editor, select transcript words, create a cut or mute, preview, undo and redo.
5. **48-58 s:** Choose Podcast and inspect loudness, estimated true peak, clipping, and sample-rate rules.
6. **58-67 s:** Complete one blind A/B round and export the Project Capsule with original audio left off.
7. **67-72 s:** Open the report: profile, engines, provenance, privacy state, and approved edits.
8. **72-75 s:** Close the app; end card: “AudioEnhancerMAX 3.7: local-first audio, reviewed by you.”

Use only the packaged app. Keep the mouse and clock visible for the Apple review version; edit pacing only for the public campaign version.

## Editorial calendar

### T−7 to T−3: establish the problem

- Post 1: why automatic speech cuts can damage cadence.
- Post 2: what “local” actually means, core, local model, separate local process, trusted LAN, external.
- Post 3: five-second native-window reveal; no availability claim.
- Collect community questions for the launch FAQ.

### T−2 to T−1: show proof

- Publish a before/after sample with the exact selected profile and no exaggerated restoration language.
- Publish the proof ledger: feature, execution boundary, test/package evidence.
- Send a short pre-launch email to existing users and contributors.

### Launch day

- Publish release notes and claims matrix first.
- Update website hero, roadmap, support and privacy pages.
- Publish launch video and one workflow article.
- Announce the actual availability channel only after the artifact is live there.
- Pin a known-boundaries comment linking to the FAQ.

### T+1 to T+14: teach and verify

- Tutorial: Smart Enhance profiles and when to choose Conservative.
- Tutorial: cut versus mute in conversational editing.
- Tutorial: five delivery profiles and override audit.
- Engineering post: why Ollama does not control DSP.
- Privacy post: optional service gates and LAN opt-in.
- Collect opt-in user feedback by workflow; do not incentivize App Store reviews.

## Channel plan

| Channel | Primary asset | CTA |
| --- | --- | --- |
| Website | Launch page + proof ledger | Read release evidence / access live distribution |
| App Store | Accurate screenshots, description, What’s New | Download after approval |
| GitHub | Tagged release, changelog, technical notes | Inspect source / report issue |
| SourceForge | Matching release notes and checksums | Download verified artifact |
| LinkedIn | 45-75 second product narrative | Read how reviewability works |
| X / Mastodon | Proof-led thread | Open claims matrix / demo |
| Reddit/community posts | Technical build story, disclosed affiliation | Discuss workflow; no vote/review manipulation |
| Email | Problem → proof → availability | View release and documentation |

## Measurement plan

Start with baselines; do not invent historical values.

| Funnel stage | KPI | Measurement rule |
| --- | --- | --- |
| Reach | Qualified video views, product-page impressions | Report absolute count and channel/date |
| Interest | Release-note visits, video completion, proof-ledger clicks | Separate owned, organic and paid traffic |
| Evaluation | Verified downloads, TestFlight installs, sample/report downloads | Deduplicate where platform analytics permit |
| Activation | First upload, first completed local process, first export | Only if analytics are explicitly added and disclosed; otherwise use opt-in survey/support signals |
| Trust | Privacy-page visits, report opens, issue quality | Do not interpret page visits as approval |
| Retention | Repeat launch or export at 7/30 days | Requires a consented, privacy-reviewed measurement design |

No analytics SDK is currently claimed in the package. If analytics are added later, update the privacy manifest, privacy policy, App Store answers and claims matrix before release.

## Campaign guardrails

- Never say “available on the Mac App Store” before approval and storefront availability.
- Never use “best,” “state of the art,” “studio quality,” “perfect,” “100% private,” or performance percentages without a published benchmark.
- Avoid competitor names in App Store keywords or metadata.
- Do not incentivize ratings, rankings or reviews.
- Do not publish personal/customer audio without documented permission.
- Treat transcript and diagnostic scores as assistive evidence, not certification.
- Keep optional external Microsoft TTS visible in privacy copy.

## Go/no-go checklist

- [x] Final 3.7.5 package passes the complete automated and signed-payload validation.
- [ ] TestFlight install passes on a physical Mac.
- [ ] App Store screenshots match build 3.7.5 exactly.
- [ ] Every launch claim is Approved in the claims matrix.
- [ ] Privacy policy and App Store privacy answers match actual optional data flows.
- [ ] Store URL is live before any “available now” post.
- [ ] Download links, support URL and privacy URL return successful responses.
- [ ] Campaign audio/video uses developer-owned material.
- [ ] Known limitations are present in release notes and FAQ.
