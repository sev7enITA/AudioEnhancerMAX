import C2PA
import SwiftUI
import UniformTypeIdentifiers

private let credentialFormats = [
    "wav": "audio/wav", "mp3": "audio/mpeg", "flac": "audio/flac",
    "m4a": "audio/mp4", "mp4": "video/mp4", "mov": "video/quicktime",
]

struct CredentialSummary: Sendable {
    let outcome: String
    let detail: String
    var signer: String?
    var signerTrust: String?
    var timestamp: String?
    var reportFingerprint: String?
}

enum MobileContentCredentials {
    private static let trustExpiry = ISO8601DateFormatter().date(from: "2027-02-02T17:24:49Z")!

    static func inspect(_ url: URL, bundle: Bundle = .main) -> CredentialSummary {
        guard let format = credentialFormats[url.pathExtension.lowercased()] else {
            return CredentialSummary(outcome: "Unsupported format", detail: "Choose WAV, MP3, FLAC, M4A, MP4 or MOV.")
        }
        let granted = url.startAccessingSecurityScopedResource()
        defer { if granted { url.stopAccessingSecurityScopedResource() } }
        do {
            guard let count = try url.resourceValues(forKeys: [.fileSizeKey]).fileSize else {
                throw CocoaError(.fileReadUnknown)
            }
            guard count <= 500 * 1024 * 1024 else {
                return CredentialSummary(outcome: "File too large", detail: "Choose a file up to 500 MB.")
            }
            let expired = Date() >= trustExpiry
            let anchors: [[String: String]] = try expired ? [] : [
                ("manifest", "C2PA-TRUST-LIST"), ("tsa", "C2PA-TSA-TRUST-LIST"),
            ].map { kind, file in
                guard let url = bundle.url(forResource: file, withExtension: "pem") else {
                    throw CocoaError(.fileNoSuchFile)
                }
                return ["trust_kind": kind, "trust_anchors": try String(contentsOf: url, encoding: .ascii)]
            }
            let settings: [String: Any] = [
                "core": ["allowed_network_hosts": [String](), "decode_identity_assertions": false],
                "verify": [
                    "verify_after_reading": true, "verify_trust": true, "verify_timestamp_trust": true,
                    "ocsp_fetch": false, "remote_manifest_fetch": false,
                ],
                "trust": ["anchors": anchors],
            ]
            let json = String(decoding: try JSONSerialization.data(withJSONObject: settings), as: UTF8.self)
            let context = try C2PAContext(
                settings: C2PASettings(json: json),
                onProgress: { _ in Task.isCancelled ? .cancel : .continue },
                httpResolver: { _ in throw URLError(.notConnectedToInternet) }
            )
            let stream = try Stream(readFrom: url)
            let reader = try Reader(context: context, format: format, stream: stream)
            let object = try JSONSerialization.jsonObject(with: Data(try reader.json().utf8))
            return summarize(object as? [String: Any] ?? [:], embedded: reader.isEmbedded(), expired: expired)
        } catch {
            let reason = error.localizedDescription.lowercased()
            if reason.contains("remote manifest") || reason.contains("remotemanifest") {
                return CredentialSummary(outcome: "Remote reference",
                                         detail: "This file points to an online manifest. The check stays offline.")
            }
            if reason.contains("manifestnotfound") || reason.contains("manifest not found") ||
                reason.contains("no manifest") || reason.contains("jumbfnotfound") {
                return CredentialSummary(outcome: "No embedded credentials",
                                         detail: "The selected file contains no readable embedded C2PA manifest.")
            }
            return CredentialSummary(outcome: "Could not verify", detail: "Check that the file opens and has a supported format.")
        }
    }

    static func summarize(_ document: [String: Any], embedded: Bool, expired: Bool) -> CredentialSummary {
        guard embedded else {
            return CredentialSummary(outcome: "Remote reference", detail: "This check reads only embedded manifests.")
        }
        guard let id = document["active_manifest"] as? String,
              let manifests = document["manifests"] as? [String: [String: Any]], let manifest = manifests[id] else {
            return CredentialSummary(outcome: "Could not verify", detail: "The active manifest could not be read.")
        }
        let validation = (document["validation_results"] as? [String: Any])?["activeManifest"] as? [String: Any]
        let successes = validation?["success"] as? [[String: Any]] ?? []
        let codes = Set(successes.compactMap { $0["code"] as? String })
        let assertions = manifest["assertions"] as? [[String: Any]] ?? []
        let report = assertions.compactMap { assertion -> String? in
            guard assertion["label"] as? String == "com.fabriziodegni.audioenhancermax.processing" else { return nil }
            return (assertion["data"] as? [String: Any])?["processing_report_sha256"] as? String
        }.first { $0.range(of: "^[a-fA-F0-9]{64}$", options: .regularExpression) != nil }
        let integrity: (outcome: String, detail: String)
        switch document["validation_state"] as? String {
        case "Valid", "Trusted":
            integrity = ("Integrity verified", "The asset matches its signed manifest.")
        case "Invalid":
            integrity = ("Integrity check failed", "The signature or a verification check failed.")
        default:
            integrity = ("Integrity not established", "The reader did not report a usable integrity result.")
        }
        let signerTrust = expired ? "Trust list expired" :
            (codes.contains("signingCredential.trusted") ? "Recognized" : "Not established")
        let timestamp: String
        if expired {
            timestamp = "Trust list expired"
        } else if codes.contains("timeStamp.validated"), codes.contains("timeStamp.trusted") {
            timestamp = "Trusted RFC 3161"
        } else if codes.contains("timeStamp.validated") {
            timestamp = "Present, trust not established"
        } else {
            timestamp = "Not established"
        }
        let issuer = (manifest["signature_info"] as? [String: Any])?["issuer"] as? String
        return CredentialSummary(outcome: integrity.outcome, detail: integrity.detail,
                                 signer: issuer.map { String($0.prefix(160)) }, signerTrust: signerTrust,
                                 timestamp: timestamp, reportFingerprint: report)
    }
}

struct ContentCredentialsCard: View {
    @State private var picker = false
    @State private var selection: URL?
    @State private var summary: CredentialSummary?
    @State private var working = false

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("Content Credentials", systemImage: "checkmark.shield")
                .font(.headline)
            Text("Inspect C2PA in the original file. Verification runs on this phone without uploading the file.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Button { picker = true } label: {
                Label(working ? "Checking credentials…" : "Check a file", systemImage: "doc.text.magnifyingglass")
            }
            .buttonStyle(.borderedProminent)
            .disabled(working)
            if working { ProgressView() }
            if let summary = summary {
                Divider()
                Text(summary.outcome).font(.headline)
                Text(summary.detail).font(.subheadline)
                if let signer = summary.signer { LabeledContent("Signer", value: signer) }
                if let trust = summary.signerTrust { LabeledContent("Signer trust", value: trust) }
                if let timestamp = summary.timestamp { LabeledContent("Timestamp", value: timestamp) }
                if let report = summary.reportFingerprint {
                    Text("Processing report SHA-256").font(.caption)
                    Text(report).font(.footnote.monospaced()).textSelection(.enabled)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .fileImporter(isPresented: $picker, allowedContentTypes: [.audio, .movie, .data]) { result in
            switch result {
            case .success(let url):
                summary = nil
                selection = nil
                selection = url
            case .failure:
                summary = CredentialSummary(outcome: "Could not open the file", detail: "Try selecting it again.")
            }
        }
        .task(id: selection) {
            guard let url = selection else { return }
            working = true
            let operation = Task.detached(priority: .userInitiated) { MobileContentCredentials.inspect(url) }
            let result = await withTaskCancellationHandler {
                await operation.value
            } onCancel: {
                operation.cancel()
            }
            if !Task.isCancelled {
                summary = result
                working = false
                selection = nil
            }
        }
    }
}
