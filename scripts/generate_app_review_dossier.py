#!/usr/bin/env python3
"""Generate the reviewer-facing AudioEnhancerMAX validation dossier."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


NAVY = colors.HexColor("#10233F")
BLUE = colors.HexColor("#2563EB")
PALE_BLUE = colors.HexColor("#EAF2FF")
GREEN = colors.HexColor("#15803D")
AMBER = colors.HexColor("#B45309")
LIGHT = colors.HexColor("#F5F7FA")
MUTED = colors.HexColor("#526174")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--pkg-sha256", required=True)
    parser.add_argument("--sample-sha256", required=True)
    parser.add_argument("--pkg-size", required=True)
    parser.add_argument("--signed-at", required=True)
    parser.add_argument("--marketing-version", default="3.8.3")
    parser.add_argument("--build-number", default="3.8.4")
    parser.add_argument(
        "--review-date",
        default=date.today().strftime("%d %B %Y").lstrip("0"),
    )
    return parser.parse_args()


def header_footer(canvas, doc) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 18 * mm, width, 18 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(18 * mm, height - 11.5 * mm, "AudioEnhancerMAX - Mac App Store Review Dossier")
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(
        18 * mm,
        10 * mm,
        f"Version {doc.aemax_version} - Build {doc.aemax_build} - {doc.aemax_review_date}",
    )
    canvas.drawRightString(width - 18 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        "CoverTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=24, leading=29, textColor=NAVY, alignment=TA_CENTER,
        spaceAfter=8 * mm,
    ))
    styles.add(ParagraphStyle(
        "CoverSub", parent=styles["Normal"], fontSize=12, leading=17,
        textColor=MUTED, alignment=TA_CENTER, spaceAfter=5 * mm,
    ))
    styles.add(ParagraphStyle(
        "Section", parent=styles["Heading1"], fontName="Helvetica-Bold",
        fontSize=15, leading=19, textColor=NAVY, spaceBefore=5 * mm,
        spaceAfter=3 * mm, keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        "Subsection", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=11, leading=14, textColor=BLUE, spaceBefore=3 * mm,
        spaceAfter=1.5 * mm, keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        "BodySmall", parent=styles["BodyText"], fontSize=9.2, leading=13,
        textColor=colors.HexColor("#26364A"), spaceAfter=2.5 * mm,
    ))
    styles.add(ParagraphStyle(
        "Tiny", parent=styles["BodyText"], fontSize=7.2, leading=9.2,
        textColor=MUTED, wordWrap="CJK",
    ))
    styles.add(ParagraphStyle(
        "Status", parent=styles["BodyText"], fontName="Helvetica-Bold",
        fontSize=10, leading=14, textColor=GREEN, alignment=TA_LEFT,
    ))
    return styles


def p(text: str, styles, style: str = "BodySmall") -> Paragraph:
    return Paragraph(text, styles[style])


def status_table(rows, styles, widths=(36 * mm, 122 * mm)) -> Table:
    cooked = []
    for status, detail in rows:
        color = GREEN if status == "PASS" else AMBER
        cooked.append([
            Paragraph(status, ParagraphStyle(
                f"status-{status}", parent=styles["Status"], textColor=color,
            )),
            p(detail, styles),
        ])
    table = Table(cooked, colWidths=list(widths), hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D5DDE8")),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D5DDE8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def main() -> None:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    styles = build_styles()
    width, height = A4
    frame = Frame(18 * mm, 17 * mm, width - 36 * mm, height - 39 * mm,
                  leftPadding=0, rightPadding=0, topPadding=4 * mm, bottomPadding=0)
    doc = BaseDocTemplate(
        str(args.output), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=22 * mm, bottomMargin=17 * mm,
        title=f"AudioEnhancerMAX App Review Dossier {args.marketing_version} build {args.build_number}",
        author="Fabrizio Degni",
    )
    doc.aemax_version = args.marketing_version
    doc.aemax_build = args.build_number
    doc.aemax_review_date = args.review_date
    doc.addPageTemplates([PageTemplate(id="review", frames=[frame], onPage=header_footer)])

    story = [Spacer(1, 24 * mm)]
    story += [
        p("AudioEnhancerMAX", styles, "CoverTitle"),
        p("Mac App Store Resubmission and Validation Dossier", styles, "CoverSub"),
        Table([
            [p("Marketing version", styles), p(args.marketing_version, styles)],
            [p("Build", styles), p(args.build_number, styles)],
            [p("Bundle ID", styles), p("com.fabriziodegni.audioenhancermax", styles)],
            [p("Target", styles), p("Apple silicon Mac (arm64), macOS 13.0 or later", styles)],
            [p("Installer", styles), p("Mac App Store signed PKG", styles)],
        ], colWidths=[45 * mm, 105 * mm], style=TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), PALE_BLUE),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#B8C7DD")),
            ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B8C7DD")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ])),
        Spacer(1, 8 * mm),
        status_table([
            ("PASS", "Build, application signature, installer signature, trusted timestamp, checksum, sandbox entitlements, architecture, deployment target, native-window startup, DSP filter-chain stability, packaged codecs, and bundled models were validated. The focused automated suite contains 51 passing tests."),
            ("ACTION", "Before resubmission, attach Apple's requested continuous physical-device screen recording made on the latest public macOS release available on the recording date."),
        ], styles),
        p("This dossier documents technical validation. It does not replace App Store Connect processing or Apple's own review.", styles, "Tiny"),
    ]

    story += [PageBreak(), p("1. Rejection issues addressed", styles, "Section")]
    story.append(status_table([
        ("PASS", "The UI now runs inside a native AppKit window using WKWebView. Launching the app no longer opens the user's default browser."),
        ("PASS", "The macOS application menu is explicitly labeled AudioEnhancerMAX. Its app-owned About window presents product identity, version/build, author, purpose, privacy boundaries, requirements, support guidance, architecture, license, and official resources without exposing Python runtime metadata."),
        ("PASS", "The com.apple.security.network.server entitlement is retained and documented. The native WKWebView connects inbound to the embedded FastAPI/Uvicorn service bound only to 127.0.0.1. The service terminates when the app quits or its main window closes."),
        ("PASS", "Optional LAN Edge Cluster discovery is disabled at launch and begins only after an explicit user action. Core processing does not expose a LAN or public server."),
        ("PASS", "The previous external FFmpeg/FFprobe dependency was removed. Media decoding and encoding use PyAV with embedded FFmpeg libraries."),
        ("PASS", "Faster-Whisper Medium, tokenizer files, vocabulary, and compatible Silero VAD assets are bundled. Runtime model download is disabled for the App Store build."),
        ("PASS", "The filter crash was traced to librosa importing Numba/llvmlite JIT code inside the hardened package. The shipping runtime now uses NumPy/SciPy DSP helpers and excludes librosa, Numba, llvmlite, TTS, Demucs, DeepFilterNet, and pyannote; no JIT or unsigned-executable-memory entitlement was added."),
        ("PASS", "Features not included in this distribution are removed or disabled in the UI and API, including Demucs music separation and Kokoro voice cloning."),
        ("PASS", "Sandbox data, logs, locks, uploads, outputs, and settings are stored under the app container."),
    ], styles))

    # Keep the package evidence table clear of the footer. The preceding
    # rejection-remediation table is intentionally dense and fills page two.
    story += [PageBreak(), p("2. Signature and package evidence", styles, "Section")]
    signature_rows = [
        [p("Evidence", styles, "Subsection"), p("Result", styles, "Subsection")],
        [p("Application identity", styles), p("3rd Party Mac Developer Application: Fabrizio Degni (BR9VY292BU)", styles)],
        [p("Installer identity", styles), p("3rd Party Mac Developer Installer: Fabrizio Degni (BR9VY292BU)", styles)],
        [p("Trusted timestamp", styles), p(args.signed_at, styles)],
        [p("Entitlements", styles), p("app-sandbox; files.user-selected.read-write; network.client; network.server", styles)],
        [p("Package size", styles), p(args.pkg_size, styles)],
        [p("Package SHA-256", styles), p(args.pkg_sha256, styles, "Tiny")],
        [p("Sample SHA-256", styles), p(args.sample_sha256, styles, "Tiny")],
    ]
    signature_table = Table(signature_rows, colWidths=[46 * mm, 112 * mm], repeatRows=1)
    signature_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (0, -1), PALE_BLUE),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#BCC8D8")),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#BCC8D8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(signature_table)

    story += [p("3. Functional validation", styles, "Section")]
    story.append(status_table([
        ("PASS", "A hardened-runtime re-sign of the candidate payload launched in its native AppKit/WKWebView window without opening an external browser; /api/health and the application endpoints returned successfully. The production App Store signature was separately verified and requires TestFlight/App Store installation for execution."),
        ("PASS", "The standard macOS Open panel selected and uploaded the review WAV under App Sandbox, and the standard Save panel opened for the processed WAV export."),
        ("PASS", "Closing the native main window stopped the application process, stopped the embedded service, and released the loopback port."),
        ("PASS", "Readiness reported ready, zero blockers, packaged PyAV codecs, and the bundled Faster-Whisper Medium model."),
        ("PASS", "Review WAV uploaded and decoded as 16 kHz mono PCM."),
        ("PASS", "A continuous 12-step chain completed without a crash: noise, wind, buzz, static, reverb, mouth-sound, breath, and silence cleanup; Auto EQ; Studio Sound; frequency restoration; and normalization. Output duration matched the 8.41975-second input exactly."),
        ("PASS", "Processed output downloaded and decoded as WAV, MP3, and FLAC with explicit sandbox-safe MIME handling."),
        ("PASS", "Local-only transcription returned real English text from the bundled model and VAD asset; runtime model fetching is disabled for this build."),
        ("PASS", "Delivery Compliance Lab measured loudness, estimated true peak, clipping, and sample rate against a transparent target and returned rule-level evidence. Results are workflow guidance, not certification."),
        ("PASS", "Randomized blind A/B review preserved the A/B mapping until the decision, then stored the revealed subjective preference as local evidence."),
        ("PASS", "Project Capsule exported a SHA-256 manifest, processed output, and available evidence. The original audio remained excluded by default."),
        ("PASS", "Processing report schema 2 recorded build number, source/output SHA-256 provenance, and delivery-compliance evidence."),
        ("PASS", "Edge Cluster status remained disabled until explicit enablement."),
        ("PASS", "The focused regression, packaging, edge-distribution, metadata, health, and JIT-free signal-processing suite completed with 51 passing tests."),
    ], styles))

    story += [p("4. Reviewer setup and app purpose", styles, "Section")]
    story += [
        p("No login, account, subscription, in-app purchase, activation key, special hardware, sample credential, or external installation is required. Launch the app, use the native file panel to upload the supplied WAV, apply audio cleanup, compare the result, export it with the native save panel, then transcribe the same sample.", styles),
        p("AudioEnhancerMAX is intended for podcasters, interviewers, journalists, educators, researchers, voice-over creators, and other users who need local recording cleanup, comparison, export, and transcription.", styles),
    ]

    story += [p("5. External services and regional behavior", styles, "Section")]
    story.append(status_table([
        ("PASS", "Core DSP, media export, and transcription are local and behave consistently across regions."),
        ("PASS", "Microsoft Edge Neural TTS is optional. User-entered text is sent only when the user explicitly requests synthesis; availability can vary by region or network."),
        ("PASS", "Local Ollama/Gemma is optional at 127.0.0.1 and is not required. Deterministic local fallbacks remain available."),
        ("PASS", "LAN Edge Cluster is optional, disabled by default, and limited to user-enabled trusted local workers."),
        ("PASS", "No analytics, advertising, payment, account, cloud-audio-storage, or UGC publishing service is included."),
    ], styles))

    story += [p("6. Regulated content and privacy", styles, "Section")]
    story += [
        p("The app is a general-purpose audio production utility. It is not a medical, financial, gambling, legal-certification, or other regulated service. The attached sample is developer-created and contains no protected third-party material.", styles),
        p("The packaged privacy manifest declares no tracking. App Store Connect privacy answers must remain consistent with the optional Microsoft TTS data flow described above.", styles),
    ]

    story += [p("7. Delivery review and evidence boundaries", styles, "Section")]
    story.append(status_table([
        ("PASS", "Integrated programme loudness uses the BS.1770 method exposed by pyloudnorm. EBU R128 is represented as a transparent -23 LUFS broadcast target with tolerance and peak ceiling."),
        ("PASS", "True peak is explicitly labeled as a 4x-oversampled estimate; no claim of certified metering is made."),
        ("PASS", "The Project Capsule uses SHA-256 artifact identifiers and safe fixed archive paths. Original audio requires an explicit include-source choice."),
        ("PASS", "Blind A/B decisions are described as subjective listening preferences, never as objective quality scores."),
    ], styles))

    story += [p("8. Required final submission evidence", styles, "Section")]
    story.append(status_table([
        ("ACTION", "Record an unedited three-to-five-minute workflow on a physical Apple silicon Mac running the latest public macOS release. Show About This Mac without the serial number, native-window launch, upload, DSP, A/B comparison, WAV/MP3/FLAC export, offline transcription, and quit."),
        ("ACTION", "Attach the recording, AudioEnhancerMAX-review-sample.wav, and this dossier under App Review Information. Paste the prepared Review Notes and include the exact public macOS build number used for the recording."),
        ("ACTION", f"Transporter delivered build {args.build_number} without warning and reports it ready for internal testing. Install and validate it through TestFlight, select it in the version record, then reply in Resolution Center referencing Guidelines 2.1 and 2.4.5."),
    ], styles))

    story += [p("9. Apple and component references", styles, "Section")]
    references = [
        "Apple App Review Guidelines: https://developer.apple.com/app-store/review/guidelines/",
        "Apple App Review information: https://developer.apple.com/app-store/review/",
        "Apple network server entitlement: https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.network.server",
        "Apple user-selected file entitlement: https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.files.user-selected.read-write",
        "Apple upload builds: https://developer.apple.com/help/app-store-connect/manage-builds/upload-builds",
        "Apple macOS package size limits: https://developer.apple.com/help/app-store-connect/reference/app-uploads/maximum-build-file-sizes/",
        "Apple macOS Tahoe updates: https://support.apple.com/en-us/122868",
        "Faster-Whisper Medium model: https://huggingface.co/Systran/faster-whisper-medium",
        "ITU-R BS.1770-5: https://www.itu.int/rec/R-REC-BS.1770-5-202311-I",
        "EBU R128 v5: https://tech.ebu.ch/files/live/sites/tech/files/shared/r/r128.pdf",
    ]
    for item in references:
        story.append(p(item, styles, "Tiny"))

    doc.build(story)
    print(args.output)


if __name__ == "__main__":
    main()
