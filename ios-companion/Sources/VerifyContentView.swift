import SwiftUI

@MainActor
final class VerificationWorkspace: ObservableObject {
    @Published private(set) var report: MediaVerificationReport?
    @Published private(set) var export: VerificationJSON?
    @Published private(set) var fileName = ""
    @Published private(set) var working = false
    @Published private(set) var error: String?
    private var operation: Task<Void, Never>?
    private var revision = UUID()

    func verify(_ url: URL) {
        cancel()
        report = nil
        export = nil
        error = nil
        guard MobileMediaVerification.accepts(url) else {
            error = "Choose a local WAV, MP3, FLAC, M4A, MP4 or MOV file."
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
                let data = try result.json()
                export = VerificationJSON(contents: data, fileName: "verification-\(result.asset.sha256.prefix(12)).json")
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
            Text("Check a file’s fingerprint, C2PA Content Credentials and decoded audio levels. The app never uploads the file.")
                .font(.subheadline).foregroundStyle(WorkspaceColor.muted)
            Button { picking = true } label: {
                Label("Choose a file", systemImage: "folder").frame(maxWidth: .infinity, minHeight: 30)
            }
            .buttonStyle(.borderedProminent)
            .foregroundStyle(WorkspaceColor.background)
            .disabled(workspace.working)
            .accessibilityIdentifier("choose-verification-file")
            Text("WAV, MP3, FLAC, M4A, MP4, MOV · up to 500 MiB")
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
