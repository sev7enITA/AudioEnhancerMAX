# AudioEnhancerMAX 3.7.4: Delivery Review Evidence

Status: implemented, source-tested, packaged and signed as build 3.7.4 on 20 August 2026. Apple-controlled processing and review remain separate gates.

## Wave 1: Delivery Compliance Lab

The Lab analyzes the completed local output and reports:

- integrated programme loudness through the BS.1770 algorithm implemented by `pyloudnorm`;
- an estimated true peak derived from 4× polyphase oversampling;
- sample-peak level and samples at or beyond full scale;
- sample rate, channel count, and duration;
- a rule-level result for podcast, online-video, audiobook, EBU R128 broadcast, source-master, or lossless-archive workflows.

The EBU R128 target is −23 LUFS with ±0.5 LU tolerance and a −1 dBTP ceiling. Other workflow presets are transparent product targets rather than representations that a distributor has certified the file. Every result carries the statement: “Local workflow guidance only; this result is not a regulatory or third-party certification.”

Primary references:

- ITU-R BS.1770-5: https://www.itu.int/rec/R-REC-BS.1770-5-202311-I
- EBU R128 v5: https://tech.ebu.ch/files/live/sites/tech/files/shared/r/r128.pdf

Implementation: `app/services/delivery_compliance.py` and `/api/compliance/*`.

## Wave 2: Evidence Chain and Project Capsule

Each version-2 processing report can retain SHA-256 identifiers for the source and processed artifact. The Project Capsule adds a portable `manifest.json` and packages the processed output with any available processing report, compliance result, transcript, speech EDL, and blind A/B review.

Privacy and safety properties:

- original audio is excluded from the ZIP by default;
- source inclusion requires an explicit UI choice;
- archive names are generated from safe basenames and fixed role folders;
- all listed artifacts receive a SHA-256 digest and byte size;
- the manifest records marketing version, build, execution boundary, creation time, and hash algorithm;
- blind A/B evidence is labeled as a subjective user preference, not an objective quality score.

Implementation: `app/services/project_bundle.py`, report schema 2, `/api/projects/*`, and `/api/reviews/*`.

## UI/UX wave: Review Deck

The post-processing Review Deck unifies delivery checks, blind A/B audition, evidence inspection, and Project Capsule export. The workflow progresses through Diagnose, Process, Review, and Deliver. Target changes trigger a new local measurement; A/B mapping remains hidden until the user decides; the original-audio export control defaults to off.

## Automated evidence

The 26-test focused suite includes:

- target-pass and out-of-tolerance loudness cases;
- explicit silence behavior;
- full-scale clipping counts;
- SHA-256 manifest verification;
- default source exclusion and ZIP path safety;
- processing-report schema 2, build, provenance, and compliance integration;
- all preceding diagnosis, capability, profile, privacy, desktop, and speech-EDL checks.

Run with:

```bash
venv/bin/python -m unittest discover -s tests -v
```

These tests verify implementation behavior. They do not replace perceptual listening review, distributor validation, TestFlight installation, or Apple App Review.
