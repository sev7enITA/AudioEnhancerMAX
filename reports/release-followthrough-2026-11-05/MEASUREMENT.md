# Channel measurement and field evidence

Activated: 5 November 2026. No paid promotion was purchased or increased.

## What is measured

`web/go.php` records aggregate navigation requests by UTC day, source, campaign, destination and placement. It does not count installs, completed downloads, unique people or active users. A person can click repeatedly and unrecognised automation can appear in the counts. Counts are directional observations, not attribution proof.

The website has no new cookies, local storage, visitor IDs or advertising pixels. The counter persists no IP address, user-agent, referrer, full query string or feedback text. Hosting delivery/security logs are separate. DNT/GPC requests, known preview bots, prefetch, HEAD and test-mode requests do not count. Retention is 90 UTC daily buckets. A fixed destination allowlist prevents arbitrary redirects. Navigation still works if measurement storage fails.

## Campaign links

Use `campaign-links.csv` for the next relevant post or an authorised edit to an existing channel. The inventory is prepared for 12 channels; preparation does not mean all links have been posted. Existing untagged links cannot be attributed retrospectively. Website buttons route through the same endpoint and preserve allowlisted incoming campaign parameters. JavaScript-disabled visits follow the canonical destination but are not counted by these buttons.

Compare identical complete UTC date windows, such as 6-12 November and 13-19 November. Review source/destination counts separately; do not add a download-page visit to a subsequent Store click as if they were two people. Reconcile against Apple first-time downloads and GitHub/SourceForge asset downloads using their own definitions and reporting lag. Do not calculate ROAS or an install conversion rate from these aggregate click counts.

## Private export

In the authenticated Hostinger File Manager for fabriziodegni.com, open `.aemax-metrics` alongside, not inside, `public_html`. Download `counts.json` privately. Do not move it to the website or publish the complete internal marketing audit.

Run `python3 scripts/export_campaign_counts.py /path/to/counts.json /path/to/clicks.csv --from-date 2026-11-06 --to-date 2026-11-12` from the repository. QA source and verification campaign are excluded by default. No public statistics endpoint or credential was created.

Deployment verification recorded exactly one request under `qa|verification-2026-11|download|other`; the private JSON was inspected through File Manager. The first measurement baseline is therefore zero organic campaign clicks. Do not treat that QA request as audience activity.

## Field evidence

Public guide: https://www.fabriziodegni.com/AudioEnhancerMAX/feedback.html

The worksheet generates a report locally. Users choose whether to save it or open the GitHub issue editor. Opening that editor transmits the report to GitHub; final publication occurs only when they submit it. No recording is required and the instructions exclude confidential material.

Aim for 5-10 voluntary independent reports before evaluating additional paid promotion. This is a practical learning target, not a statistical proof threshold or permission to buy advertising. Capture edition/build, macOS/chip, repeatable steps, outcome, listening conditions and relevant evidence in `field-evidence.csv`. Separate developer tests from independent reports. Record negative and blocked outcomes too. Quote a person only with their permission and do not infer a testimonial from a bug report.

The initial ledger is empty. Developer UI/endpoint checks establish the collection mechanism, not real-world adoption or audio quality. Review reports for reproducibility, fix recurring blockers, then reassess any proposed spend with its explicit cost and destination.

## Apple campaign attribution

App Store Connect generated the public provider token `118694520` with media type `8`. It is an attribution identifier, not an authentication credential. Store redirects carry `ct=aemax-202611-{source}` using the same fixed source allowlist. The QA source is excluded. This enables prospective Apple-side attribution separately from website navigation counts; no visitor-level join is made.

Apple currently requires campaign first-time downloads from at least five individuals before campaign data appears; metrics also have thresholds in the selected date range. Reporting is delayed and withheld data must not be recorded as zero. See [Apple campaign-link documentation](https://developer.apple.com/help/app-store-connect-analytics/acquisition/campaign-links/). No paid campaign was created.
