import SwiftUI

@MainActor
final class VerificationWorkspace: ObservableObject {
    @Published private(set) var report: MediaVerificationReport?
    @Published private(set) var export: VerificationJSON?
    @Published private(set) var fileName = ""
    @Published private(set) var working = false
    @Published private(set) var error: String?
    @Published var expectedFingerprint = "" {
        didSet { updateExport() }
    }
    private var operation: Task<Void, Never>?
    private var revision = UUID()

    var fingerprintCheck: MediaFingerprintComparison.Check {
        guard let report else { return .empty }
        return MediaFingerprintComparison.check(expected: expectedFingerprint, actual: report.asset.sha256)
    }

    func verify(_ url: URL) {
        cancel()
        report = nil
        expectedFingerprint = ""
        fileName = ""
        error = nil
        guard MobileMediaVerification.accepts(url) else {
            error = "Choose a local \(VerificationFormat.inputFormats) file."
            return
        }
        fileName = String(url.lastPathComponent.prefix(160).filter { !$0.isNewline })
        working = true
        let current = revision
        let scan = Task.detached(priority: .userInitiated) { try await MobileMediaVerification.verify(url) }
        operation = Task {
            do {
                let result = try await withTaskCancellationHandler { try await scan.value } onCancel: { scan.cancel() }
                try Task.checkCancellation()
                guard revision == current else { return }
                report = result
                updateExport()
            } catch {
                guard !Task.isCancelled, revision == current else { return }
                self.error = (error as? CompanionError)?.localizedDescription ?? "Could not read the selected file. Try opening a local copy in Files."
            }
            if revision == current {
                working = false
                operation = nil
            }
        }
    }

    private func updateExport() {
        export = nil
        guard let report else { return }
        let comparison: MediaFingerprintComparison?
        if case .compared(let record) = fingerprintCheck { comparison = record } else { comparison = nil }
        do {
            let data = try report.json(comparison: comparison)
            export = VerificationJSON(contents: data, fileName: "verification-\(report.asset.sha256.prefix(12)).json")
        } catch {
            self.error = "Could not prepare the JSON report."
        }
    }

    func failToOpen() { error = "Could not open the file. Choose it again in Files." }

    func cancel() {
        revision = UUID()
        operation?.cancel()
        operation = nil
        working = false
    }
}

struct VerifyContentView: View {
    @ObservedObject var workspace: VerificationWorkspace
    @State private var picking = false

    var body: some View {
        ScrollView {
            VStack(spacing: 14) {
                introduction
                if let report = workspace.report {
                    fingerprint(report.asset)
                    if let metadata = report.metadata { MediaMetadataCard(metadata: metadata) }
                    credentials(report.credentials)
                    audio(report.audio)
                    if let export = workspace.export {
                        ShareLink(item: export, preview: SharePreview("Media verification report", image: Image("BrandMark"))) {
                            Label("Export JSON report", systemImage: "square.and.arrow.up")
                                .frame(maxWidth: .infinity, minHeight: 30)
                        }
                        .buttonStyle(.borderedProminent)
                        .foregroundStyle(WorkspaceColor.background)
                        .accessibilityIdentifier("export-verification-report")
                    }
                }
            }
            .padding(.horizontal, 16).padding(.vertical, 12)
            .frame(maxWidth: 740).frame(maxWidth: .infinity)
        }
        .background(WorkspaceColor.background)
        .scrollDismissesKeyboard(.interactively)
        .navigationTitle("Verify Content")
        .navigationBarTitleDisplayMode(.inline)
        .fileImporter(isPresented: $picking, allowedContentTypes: VerificationFormat.contentTypes) { result in
            switch result {
            case .success(let url): workspace.verify(url)
            case .failure: workspace.failToOpen()
            }
        }
    }

    private var introduction: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("On-device verification", systemImage: "checkmark.shield").font(.title2.bold())
            Text("Read a file’s metadata, fingerprint, C2PA Content Credentials and decoded audio levels on this device.")
                .font(.subheadline).foregroundStyle(WorkspaceColor.muted)
            Button { picking = true } label: {
                Label("Choose a file", systemImage: "folder").frame(maxWidth: .infinity, minHeight: 30)
            }
            .buttonStyle(.borderedProminent)
            .foregroundStyle(WorkspaceColor.background)
            .disabled(workspace.working)
            .accessibilityIdentifier("choose-verification-file")
            Text("\(VerificationFormat.inputFormats) · up to 500 MiB")
                .font(.caption).foregroundStyle(WorkspaceColor.muted)
            if workspace.working {
                ProgressView("Checking \(workspace.fileName)…")
                Button("Cancel verification", role: .cancel, action: workspace.cancel)
            }
            if let error = workspace.error {
                Label(error, systemImage: "exclamationmark.circle").font(.subheadline).foregroundStyle(.orange)
            }
        }.workspaceCard(padding: 20)
    }

    private func fingerprint(_ asset: MediaVerificationReport.Asset) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("File fingerprint", systemImage: "number").font(.headline)
            Text(workspace.fileName).font(.subheadline.weight(.semibold)).lineLimit(2)
            LabeledContent("File size", value: "\(asset.sizeBytes.formatted()) bytes")
            LabeledContent("Media type", value: asset.mediaType)
            Text("SHA-256").font(.caption.weight(.semibold)).foregroundStyle(WorkspaceColor.muted)
            Text(asset.sha256).font(.footnote.monospaced()).textSelection(.enabled)
                .accessibilityIdentifier("verification-sha256")
            Divider()
            Text("Compare SHA-256").font(.subheadline.weight(.semibold))
            Text("Paste the expected SHA-256 from a trusted source. The comparison checks the file bytes. C2PA signer trust is reported separately.")
                .font(.caption).foregroundStyle(WorkspaceColor.muted)
            TextField("Expected SHA-256", text: $workspace.expectedFingerprint,
                      prompt: Text("Expected SHA-256").foregroundStyle(WorkspaceColor.muted))
                .font(.footnote.monospaced())
                .textFieldStyle(.plain)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .keyboardType(.asciiCapable)
                .padding(.horizontal, 12)
                .frame(minHeight: 44)
                .background(WorkspaceColor.background, in: RoundedRectangle(cornerRadius: 8))
                .overlay { RoundedRectangle(cornerRadius: 8).strokeBorder(WorkspaceColor.line) }
                .accessibilityIdentifier("expected-sha256")
            switch workspace.fingerprintCheck {
            case .empty:
                Text("No fingerprint comparison yet.")
                    .font(.caption).foregroundStyle(WorkspaceColor.muted)
            case .invalid:
                Label("Enter exactly 64 hexadecimal characters.", systemImage: "exclamationmark.circle")
                    .font(.subheadline).foregroundStyle(.orange)
                    .accessibilityIdentifier("fingerprint-comparison-result")
            case .compared(let comparison):
                let matches = comparison.result == .match
                Label(matches ? "SHA-256 matches the expected fingerprint." : "SHA-256 differs from the expected fingerprint.",
                      systemImage: matches ? "checkmark.circle" : "exclamationmark.circle")
                    .font(.subheadline).foregroundStyle(matches ? WorkspaceColor.mint : .orange)
                    .accessibilityIdentifier("fingerprint-comparison-result")
            }
        }.workspaceCard()
    }

    private func credentials(_ credentials: CredentialSummary) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("C2PA Content Credentials", systemImage: "checkmark.shield").font(.headline)
            Text(credentials.outcome).font(.title3.weight(.semibold))
                .foregroundStyle(credentials.status == "invalid" ? .orange : WorkspaceColor.mint)
                .accessibilityIdentifier("verification-credentials-status")
            Text(credentials.detail).font(.subheadline).foregroundStyle(WorkspaceColor.muted)
            if let signer = credentials.signer { LabeledContent("Signer", value: signer) }
            if let issuer = credentials.issuer { LabeledContent("Issuer", value: issuer) }
            if let trust = credentials.signerTrustLabel { LabeledContent("Signer trust", value: trust) }
            if let timestamp = credentials.timestampLabel { LabeledContent("Timestamp trust", value: timestamp) }
            if !credentials.actionTimeline.isEmpty {
                Divider()
                Text("Actions declared in the validated manifest").font(.subheadline.weight(.semibold))
                ForEach(Array(credentials.actionTimeline.enumerated()), id: \.offset) { item in
                    VStack(alignment: .leading, spacing: 3) {
                        Label(actionTitle(item.element.action), systemImage: "circle")
                        if let date = item.element.when {
                            Text(date).font(.caption.monospacedDigit()).foregroundStyle(WorkspaceColor.muted)
                        } else if let start = item.element.whenStart ?? item.element.whenEnd {
                            Text([start, item.element.whenStart == nil ? nil : item.element.whenEnd].compactMap { $0 }.joined(separator: " → "))
                                .font(.caption.monospacedDigit()).foregroundStyle(WorkspaceColor.muted)
                        }
                    }
                }
                Text("Action dates come from the manifest. A trusted timestamp is reported separately.")
                    .font(.caption).foregroundStyle(WorkspaceColor.muted)
            }
            if let report = credentials.reportFingerprint {
                Text("Linked processing report SHA-256").font(.caption.weight(.semibold)).foregroundStyle(WorkspaceColor.muted)
                Text(report).font(.footnote.monospaced()).textSelection(.enabled)
            }
            if !credentials.failureCodes.isEmpty {
                DisclosureGroup("Validation details") {
                    Text(credentials.failureCodes.joined(separator: "\n"))
                        .font(.caption.monospaced()).textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            Text("C2PA reports provenance and file integrity. It does not determine whether a recording depicts a real event.")
                .font(.caption).foregroundStyle(WorkspaceColor.muted)
        }.workspaceCard()
    }

    private func audio(_ result: AudioVerification) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("Audio measurements", systemImage: "waveform").font(.headline)
            if result.status == "measured" {
                measurementLine("Analyzed", result.analyzedSeconds.map { $0.formatted(.number.precision(.fractionLength(2))) + " s" })
                measurementLine("Sample rate", result.sampleRateHz.map { $0.formatted() + " Hz" })
                measurementLine("Channels", result.channels.map { String($0) })
                measurementLine("Sample peak", result.peakDbfs.map(formatLevel) ?? "Silence")
                measurementLine("RMS", result.rmsDbfs.map(formatLevel) ?? "Silence")
                measurementLine("Near full scale", result.nearFullScalePercent.map { $0.formatted(.number.precision(.fractionLength(3))) + "%" })
                Text("First audio track, up to 30 s at its native rate and channels. Near full scale means at least 99.9% of full amplitude.")
                    .font(.caption).foregroundStyle(WorkspaceColor.muted)
            } else {
                Text(result.status == "no_audio_track" ? "No audio track detected." :
                     result.status == "decode_limit" ? "Audio exceeds the supported channel or sample-rate limits." : "This audio could not be decoded on this device.")
                    .font(.subheadline).foregroundStyle(WorkspaceColor.muted)
            }
        }.workspaceCard()
    }

    private func measurementLine(_ label: String, _ value: String?) -> some View {
        LabeledContent(label, value: value ?? "—").monospacedDigit()
    }

    private func formatLevel(_ level: Double) -> String {
        level.formatted(.number.precision(.fractionLength(2))) + " dBFS"
    }

    private func actionTitle(_ code: String) -> String {
        switch code {
        case "c2pa.opened": "Opened"
        case "c2pa.created": "Created"
        case "c2pa.modified": "Modified"
        case "c2pa.placed": "Placed"
        case "c2pa.published": "Published"
        default: code
        }
    }
}


private struct MediaMetadataCard: View {
    let metadata: MediaMetadata

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("Media metadata", systemImage: "list.bullet.rectangle").font(.headline)
                .accessibilityIdentifier("media-metadata-heading")
            switch metadata.status {
            case .read:
                if let container = metadata.container { LabeledContent("Container", value: container) }
                if let duration = metadata.durationSeconds { LabeledContent("Duration", value: displaySeconds(duration)) }
                if let count = metadata.trackCount { LabeledContent("Tracks", value: String(count)) }
                if !metadata.tagNamespaces.isEmpty {
                    LabeledContent("Tag systems", value: metadata.tagNamespaces.joined(separator: ", "))
                }
                DisclosureGroup("Track formats") {
                    VStack(alignment: .leading, spacing: 10) {
                        ForEach(metadata.tracks, id: \.index) { track in
                            trackDetails(track)
                        }
                        if let count = metadata.trackCount, count > metadata.tracks.count {
                            Text("Showing the first \(metadata.tracks.count) tracks.").font(.caption).foregroundStyle(WorkspaceColor.muted)
                        }
                    }.padding(.top, 8)
                }
            case .formatMismatch:
                Text("Metadata unavailable because the file header does not match the selected format.")
                    .font(.subheadline).foregroundStyle(WorkspaceColor.muted)
            case .noTracks:
                Text("iOS reported a container without readable media tracks.")
                    .font(.subheadline).foregroundStyle(WorkspaceColor.muted)
            case .unreadable:
                Text("iOS could not read this file’s track metadata.")
                    .font(.subheadline).foregroundStyle(WorkspaceColor.muted)
            }
            if !metadata.localTags.isEmpty {
                DisclosureGroup("Selected tags on this device") {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(metadata.localTags, id: \.label) { tag in
                            LabeledContent(tag.label, value: tag.value).textSelection(.enabled)
                        }
                        Text("Shared JSON includes technical metadata only.").font(.caption).foregroundStyle(WorkspaceColor.muted)
                    }.padding(.top, 8)
                }
            }
            if let artwork = metadata.artworkExif {
                artworkDetails(artwork)
            }
        }.workspaceCard()
    }

    private func trackDetails(_ track: MediaMetadata.Track) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text("Track \(track.index) · \(track.mediaType.replacingOccurrences(of: "_", with: " ").capitalized)")
                .font(.subheadline.weight(.semibold))
            if !track.codecs.isEmpty { LabeledContent("Codec", value: track.codecs.joined(separator: ", ")) }
            if let duration = track.durationSeconds { LabeledContent("Track duration", value: displaySeconds(duration)) }
            if let rate = track.sampleRateHz { LabeledContent("Sample rate", value: rate.formatted() + " Hz") }
            if let channels = track.channels { LabeledContent("Channels", value: String(channels)) }
            if let bits = track.bitDepth { LabeledContent("Bit depth", value: "\(bits) bit") }
            if let width = track.width, let height = track.height { LabeledContent("Dimensions", value: "\(width) × \(height)") }
            if let fps = track.nominalFrameRate {
                LabeledContent("Nominal frame rate", value: fps.formatted(.number.precision(.fractionLength(2))) + " fps")
            }
        }
        .padding(10)
        .background(WorkspaceColor.background, in: RoundedRectangle(cornerRadius: 12))
    }

    private func artworkDetails(_ artwork: ArtworkExif) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Divider()
            Label("EXIF in embedded artwork", systemImage: "camera.aperture").font(.subheadline.weight(.semibold))
            switch artwork.status {
            case .read:
                let camera = [artwork.cameraMake, artwork.cameraModel].compactMap { $0 }.joined(separator: " ")
                let lens = [artwork.lensMake, artwork.lensModel].compactMap { $0 }.joined(separator: " ")
                if !camera.isEmpty { LabeledContent("Camera", value: camera) }
                if !lens.isEmpty { LabeledContent("Lens", value: lens) }
                if let exposure = artwork.exposureSeconds {
                    let shutter = exposure < 1 ? "1/" + (1 / exposure).formatted(.number.precision(.fractionLength(0...2))) + " s"
                    : exposure.formatted(.number.precision(.fractionLength(0...2))) + " s"
                    LabeledContent("Exposure", value: shutter)
                }
                if let aperture = artwork.fNumber { LabeledContent("Aperture", value: "f/" + aperture.formatted()) }
                if let iso = artwork.iso { LabeledContent("ISO", value: iso.formatted()) }
                if let focal = artwork.focalLengthMillimeters { LabeledContent("Focal length", value: focal.formatted() + " mm") }
                Text("Photo metadata from the embedded image. Selected fields are visible on this device.")
                    .font(.caption).foregroundStyle(WorkspaceColor.muted)
            case .notFound:
                Text("No EXIF was found in the JPEG or TIFF artwork exposed by iOS.")
                    .font(.caption).foregroundStyle(WorkspaceColor.muted)
            case .notCheckedSize:
                Text("Artwork checks are limited to files up to 16 MiB and artwork up to 4 MiB.")
                    .font(.caption).foregroundStyle(WorkspaceColor.muted)
            case .unreadable:
                Text("iOS could not read embedded artwork.")
                    .font(.caption).foregroundStyle(WorkspaceColor.muted)
            }
        }
    }

    private func displaySeconds(_ duration: Double) -> String {
        duration.formatted(.number.precision(.fractionLength(2))) + " s"
    }
}
