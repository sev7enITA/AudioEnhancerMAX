import C2PA
import Foundation

struct CredentialSummary: Codable, Sendable {
    struct Action: Codable, Sendable {
        let action: String
        let when: String?
        let whenStart: String?
        let whenEnd: String?
    }

    let status: String
    let detail: String
    var embedded: Bool?
    var signer: String?
    var issuer: String?
    var signerTrust: String?
    var timestampStatus: String?
    var timestampTrusted: Bool?
    var processingReportSha256: String?
    var trustSnapshotExpired: Bool?
    var actionTimeline: [Action] = []
    var actions: [String] = []
    var failureCodes: [String] = []

    var reportFingerprint: String? { processingReportSha256 }
    var outcome: String {
        switch status {
        case "valid", "trusted": "Integrity verified"
        case "invalid": "Integrity check failed"
        case "unsigned": "No embedded credentials"
        case "remote_reference": "Remote reference"
        case "unsupported": "Unsupported format"
        case "format_mismatch": "File format mismatch"
        case "indeterminate": "Integrity not established"
        case "validator_unavailable": "Trust data unavailable"
        default: "Could not verify"
        }
    }

    var signerTrustLabel: String? {
        switch signerTrust {
        case "recognized": "Recognized"
        case "unrecognized": "Unrecognized signer"
        case "not_established": "Not established"
        case "trust_list_expired": "Trust list expired"
        default: nil
        }
    }

    var timestampLabel: String? {
        switch timestampStatus {
        case "trusted": "Trusted RFC 3161"
        case "validated_untrusted": "Present, trust not established"
        case "not_established": "Not established"
        case "trust_list_expired": "Trust list expired"
        default: nil
        }
    }
}

enum MobileContentCredentials {
    private static let trustExpiry = ISO8601DateFormatter().date(from: "2027-02-02T17:24:49Z")!

    static func inspect(_ url: URL, bundle: Bundle = .main) -> CredentialSummary {
        guard let format = VerificationFormat(rawValue: url.pathExtension.lowercased()) else {
            return CredentialSummary(status: "unsupported", detail: "Choose WAV, MP3, FLAC, M4A, MP4 or MOV.")
        }
        let granted = url.startAccessingSecurityScopedResource()
        defer { if granted { url.stopAccessingSecurityScopedResource() } }
        do {
            let count = try url.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? 0
            guard count > 0, count <= MobileMediaVerification.maximumBytes else {
                return CredentialSummary(status: "unreadable", detail: "Choose a nonempty file of up to 500 MiB.")
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
            let reader = try Reader(context: context, format: format.mimeType, stream: stream)
            let object = try JSONSerialization.jsonObject(with: Data(try reader.json().utf8))
            return summarize(object as? [String: Any] ?? [:], embedded: reader.isEmbedded(), expired: expired)
        } catch let error as CocoaError where error.code == .fileNoSuchFile {
            return CredentialSummary(status: "validator_unavailable", detail: "The bundled trust data could not be read.")
        } catch {
            let reason = error.localizedDescription.lowercased()
            if reason.contains("remote manifest") || reason.contains("remotemanifest") {
                return CredentialSummary(status: "remote_reference",
                                         detail: "The file points to an online manifest. This verification stays offline.",
                                         embedded: false)
            }
            if reason.contains("manifestnotfound") || reason.contains("manifest not found") ||
                reason.contains("no manifest") || reason.contains("jumbfnotfound") {
                return CredentialSummary(status: "unsigned",
                                         detail: "The reader found no readable embedded C2PA manifest.",
                                         embedded: false)
            }
            return CredentialSummary(status: "unreadable", detail: "Check that the file opens and has a supported format.")
        }
    }

    static func summarize(_ document: [String: Any], embedded: Bool, expired: Bool) -> CredentialSummary {
        guard embedded else {
            return CredentialSummary(status: "remote_reference", detail: "This check reads only embedded manifests.",
                                     embedded: false)
        }
        guard let id = document["active_manifest"] as? String,
              let manifests = document["manifests"] as? [String: [String: Any]], let manifest = manifests[id] else {
            return CredentialSummary(status: "unreadable", detail: "The active manifest could not be read.", embedded: true)
        }
        let validation = (document["validation_results"] as? [String: Any])?["activeManifest"] as? [String: Any]
        let successes = validation?["success"] as? [[String: Any]] ?? []
        let failures = validation?["failure"] as? [[String: Any]] ?? []
        let codes = Set(successes.compactMap { $0["code"] as? String })
        let failedCodes = Array(failures.compactMap { code($0["code"]) }.prefix(32))
        let assertions = manifest["assertions"] as? [[String: Any]] ?? []
        let integrity: (status: String, detail: String)
        switch document["validation_state"] as? String {
        case "Trusted":
            integrity = (expired ? "valid" : "trusted", "The asset matches its signed manifest.")
        case "Valid":
            integrity = ("valid", "The asset matches its signed manifest.")
        case "Invalid":
            integrity = ("invalid", "The signature or an integrity check failed.")
        default:
            integrity = ("indeterminate", "The reader did not establish the asset’s integrity.")
        }
        let verified = integrity.status == "valid" || integrity.status == "trusted"
        let matched = Set(successes.compactMap { entry -> String? in
            guard entry["code"] as? String == "assertion.hashedURI.match" else { return nil }
            return (entry["url"] as? String)?.split(separator: "/").last.map(String.init)
        })
        var timeline: [CredentialSummary.Action] = []
        if verified {
            for assertion in assertions {
                guard let label = assertion["label"] as? String,
                      ["c2pa.actions", "c2pa.actions.v2"].contains(label) else { continue }
                let instance = assertion["instance"] as? Int ?? 0
                let identifier = instance > 0 ? "\(label)__\(instance)" : label
                guard matched.contains(identifier),
                      let entries = (assertion["data"] as? [String: Any])?["actions"] as? [[String: Any]] else { continue }
                for entry in entries.prefix(max(0, 32 - timeline.count)) {
                    guard let action = code(entry["action"]) else { continue }
                    timeline.append(.init(action: action, when: stamp(entry["when"]),
                                          whenStart: stamp(entry["whenStart"]), whenEnd: stamp(entry["whenEnd"])))
                }
                if timeline.count == 32 { break }
            }
        }
        let processingLabel = "com.fabriziodegni.audioenhancermax.processing"
        let report = verified && matched.contains(processingLabel) ? assertions.lazy.compactMap { assertion -> String? in
            guard assertion["label"] as? String == processingLabel else { return nil }
            return (assertion["data"] as? [String: Any])?["processing_report_sha256"] as? String
        }.first { $0.range(of: "^[a-fA-F0-9]{64}$", options: .regularExpression) != nil } : nil
        let signerTrust = expired ? "trust_list_expired" : (codes.contains("signingCredential.trusted") ? "recognized" :
            (failedCodes.contains("signingCredential.untrusted") ? "unrecognized" : "not_established"))
        let timestamp: String
        if expired { timestamp = "trust_list_expired" }
        else if codes.contains("timeStamp.validated"), codes.contains("timeStamp.trusted") { timestamp = "trusted" }
        else if codes.contains("timeStamp.validated") { timestamp = "validated_untrusted" }
        else { timestamp = "not_established" }
        let signature = manifest["signature_info"] as? [String: Any]
        return CredentialSummary(
            status: integrity.status, detail: integrity.detail, embedded: true, signer: safeName(signature?["common_name"]),
            issuer: safeName(signature?["issuer"]), signerTrust: signerTrust, timestampStatus: timestamp,
            timestampTrusted: timestamp == "trusted", processingReportSha256: report?.lowercased(),
            trustSnapshotExpired: expired, actionTimeline: timeline, actions: timeline.map(\.action),
            failureCodes: failedCodes
        )
    }

    private static func code(_ value: Any?) -> String? {
        guard let value = value as? String,
              value.range(of: "^[A-Za-z0-9_.-]{1,100}$", options: .regularExpression) != nil else { return nil }
        return value
    }

    private static func safeName(_ value: Any?) -> String? {
        guard let value = value as? String else { return nil }
        let cleaned = String(value.prefix(160).unicodeScalars.filter {
            !CharacterSet.controlCharacters.contains($0) && $0.properties.generalCategory != .format
        })
        return cleaned.isEmpty ? nil : cleaned
    }

    private static func stamp(_ value: Any?) -> String? {
        guard let value = value as? String, value.utf8.count <= 48,
              value.range(of: "^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.+-]+Z?$", options: .regularExpression) != nil else { return nil }
        return value
    }
}
