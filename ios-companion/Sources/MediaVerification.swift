import AVFoundation
import CryptoKit
import CoreTransferable
import Foundation
import UniformTypeIdentifiers

enum VerificationFormat: String, CaseIterable {
    case wav, mp3, flac, m4a, mp4, mov, aac, caf, aiff, aif, threeGP = "3gp"

    var mimeType: String {
        switch self {
        case .wav: "audio/wav"
        case .mp3: "audio/mpeg"
        case .flac: "audio/flac"
        case .m4a: "audio/mp4"
        case .mp4: "video/mp4"
        case .mov: "video/quicktime"
        case .aac: "audio/aac"
        case .caf: "audio/x-caf"
        case .aiff, .aif: "audio/aiff"
        case .threeGP: "video/3gpp"
        }
    }

    static let inputFormats = "WAV, MP3, FLAC, M4A, AAC, CAF, AIFF, MP4, MOV or 3GP"

    var supportsCredentials: Bool {
        switch self {
        case .wav, .mp3, .flac, .m4a, .mp4, .mov: true
        case .aac, .caf, .aiff, .aif, .threeGP: false
        }
    }

    static var contentTypes: [UTType] { allCases.compactMap { UTType(filenameExtension: $0.rawValue) } }

    func matchesHeader(_ prefix: Data) -> Bool {
        let kind = try? MediaImportPolicy.classify(prefix)
        switch self {
        case .wav:
            return kind == .wav || (prefix.starts(with: "RF64".utf8) && prefix.dropFirst(8).starts(with: "WAVE".utf8))
        case .mp3: return kind == .mp3
        case .flac: return kind == .flac
        case .m4a, .mp4, .threeGP: return kind == .mp4
        case .aac: return kind == .aac
        case .caf: return kind == .caf
        case .aiff, .aif: return kind == .aiff
        case .mov:
            if kind == .mp4 { return true }
            // QuickTime movies produced before the ftyp convention may start with one of these atoms.
            let atom = String(decoding: prefix.dropFirst(4).prefix(4), as: UTF8.self)
            return ["moov", "mdat", "wide", "free", "skip", "pnot"].contains(atom)
        }
    }
}

struct MediaVerificationReport: Codable, Sendable {
    struct Asset: Codable, Sendable {
        let sha256: String
        let sizeBytes: Int
        let mediaType: String
    }

    struct Application: Codable, Sendable {
        let version: String
        let build: String
        let platform: String
    }

    let schema: String
    let generatedAtUtc: String
    let application: Application
    let asset: Asset
    let credentials: CredentialSummary
    let audio: AudioVerification
    var metadata: MediaMetadata?

    func json() throws -> Data {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        encoder.keyEncodingStrategy = .convertToSnakeCase
        var exported = self
        exported.metadata = metadata?.technicalExport
        return try encoder.encode(exported)
    }
}

struct AudioVerification: Codable, Sendable {
    let status: String
    var method: String?
    var sampleRateHz: Int?
    var channels: Int?
    var analyzedSeconds: Double?
    var previewLimitSeconds: Double?
    var peakDbfs: Double?
    var rmsDbfs: Double?
    var nearFullScalePercent: Double?
    var sampleCount: Int?

    static func measure(_ wave: Wave, previewLimit: Double) throws -> Self {
        guard !wave.samples.isEmpty else { return Self(status: "unreadable_audio") }
        var peak = 0.0, squares = 0.0, nearFullScale = 0
        for (index, sample) in wave.samples.enumerated() {
            if index.isMultiple(of: 65536) { try Task.checkCancellation() }
            let magnitude = abs(Double(sample))
            guard magnitude <= 32 else { return Self(status: "unreadable_audio") }
            peak = max(peak, magnitude)
            squares += magnitude * magnitude
            if magnitude >= 0.999 { nearFullScale += 1 }
        }
        func dbfs(_ magnitude: Double) -> Double? {
            guard magnitude > 0 else { return nil }
            return (20 * log10(magnitude) * 100).rounded() / 100
        }
        let count = Double(wave.samples.count)
        return Self(status: "measured", method: "first_audio_track_native_channels_prefix_v1",
                    sampleRateHz: wave.rate, channels: wave.channels, analyzedSeconds: wave.duration,
                    previewLimitSeconds: previewLimit, peakDbfs: dbfs(peak), rmsDbfs: dbfs(sqrt(squares / count)),
                    nearFullScalePercent: Double(nearFullScale) * 100 / count, sampleCount: wave.samples.count)
    }
}

enum MobileMediaVerification {
    static let maximumBytes = 500 * 1024 * 1024
    static let previewSeconds = 30.0

    static func accepts(_ url: URL) -> Bool {
        url.isFileURL && VerificationFormat(rawValue: url.pathExtension.lowercased()) != nil
    }

    static func verify(_ source: URL, bundle: Bundle = .main) async throws -> MediaVerificationReport {
        guard source.isFileURL, let format = VerificationFormat(rawValue: source.pathExtension.lowercased()) else {
            throw CompanionError.message("Choose a local \(VerificationFormat.inputFormats) file.")
        }
        let folder = FileManager.default.temporaryDirectory.appendingPathComponent("media-verification-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: false, attributes: [.posixPermissions: 0o700])
        defer { try? FileManager.default.removeItem(at: folder) }
        let local = folder.appendingPathComponent("original.\(format.rawValue)")
        let asset = try snapshot(source, to: local, format: format)
        try Task.checkCancellation()
        let credentials: CredentialSummary
        let audio: AudioVerification
        let metadata: MediaMetadata
        if asset.mediaType == format.mimeType {
            credentials = MobileContentCredentials.inspect(local, bundle: bundle)
            try Task.checkCancellation()
            // Restrict both readers to the copied original, including embedded references.
            let localAsset = AVURLAsset(url: local, options: [
                AVURLAssetReferenceRestrictionsKey: AVAssetReferenceRestrictions.forbidAll.rawValue,
                AVURLAssetAllowsCellularAccessKey: false,
            ])
            metadata = try await MediaMetadataReader.inspect(localAsset, format: format, sizeBytes: asset.sizeBytes)
            audio = try await analyzeAudio(localAsset)
        } else {
            credentials = CredentialSummary(status: "format_mismatch", detail: "The file header does not match the selected media format.")
            audio = AudioVerification(status: "unreadable_audio")
            metadata = MediaMetadata(status: .formatMismatch)
        }
        return MediaVerificationReport(
            schema: "audioenhancermax.media-verification.v1",
            generatedAtUtc: ISO8601DateFormatter().string(from: .now),
            application: .init(version: bundle.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "unknown",
                               build: bundle.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "unknown", platform: "ios"),
            asset: asset, credentials: credentials, audio: audio, metadata: metadata
        )
    }

    private static func analyzeAudio(_ asset: AVURLAsset) async throws -> AudioVerification {
        do {
            guard let track = try await asset.loadTracks(withMediaType: .audio).first else {
                return AudioVerification(status: "no_audio_track")
            }
            let metadata = try await track.load(.formatDescriptions)
            guard let format = metadata.first, let description = CMAudioFormatDescriptionGetStreamBasicDescription(format) else {
                return AudioVerification(status: "unreadable_audio")
            }
            guard (1...2).contains(Int(description.pointee.mChannelsPerFrame)),
                  (8_000...96_000).contains(description.pointee.mSampleRate) else {
                return AudioVerification(status: "decode_limit")
            }
            let wave = try await MediaImport.readAudio(asset, track: track, maximumSeconds: previewSeconds)
            try Task.checkCancellation()
            return try AudioVerification.measure(wave, previewLimit: previewSeconds)
        } catch {
            try Task.checkCancellation()
            return AudioVerification(status: "unreadable_audio")
        }
    }

    /// Coordinates the source read and binds the hash to the bytes written to the private snapshot.
    private static func snapshot(_ source: URL, to destination: URL, format: VerificationFormat) throws -> MediaVerificationReport.Asset {
        let access = source.startAccessingSecurityScopedResource()
        defer { if access { source.stopAccessingSecurityScopedResource() } }
        var coordinationError: NSError?
        var result: Result<MediaVerificationReport.Asset, Error>?
        NSFileCoordinator().coordinate(readingItemAt: source, options: .withoutChanges, error: &coordinationError) { url in
            result = Result {
                let properties = try url.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey])
                guard properties.isRegularFile == true, properties.isSymbolicLink != true,
                      let expected = properties.fileSize, expected > 0 else {
                    throw CompanionError.message("Choose a nonempty media file from Files.")
                }
                guard expected <= maximumBytes else { throw CompanionError.message("File exceeds the 500 MiB verification limit.") }

                guard FileManager.default.createFile(atPath: destination.path, contents: nil, attributes: [.posixPermissions: 0o600]) else {
                    throw CompanionError.message("Could not prepare a private copy for verification.")
                }
                let input = try FileHandle(forReadingFrom: url)
                defer { try? input.close() }
                let output = try FileHandle(forWritingTo: destination)
                defer { try? output.close() }
                var hasher = SHA256()
                var count = 0
                var header = Data()
                while let chunk = try input.read(upToCount: 256 * 1024), !chunk.isEmpty {
                    try Task.checkCancellation()
                    if header.count < 64 { header.append(chunk.prefix(64 - header.count)) }
                    count += chunk.count
                    guard count <= maximumBytes else { throw CompanionError.message("File exceeds the 500 MiB verification limit.") }
                    try output.write(contentsOf: chunk)
                    hasher.update(data: chunk)
                }
                guard count == expected else { throw CompanionError.message("The file changed during the read. Select it again.") }
                try output.synchronize()
                let digest = hasher.finalize().map { String(format: "%02x", $0) }.joined()
                let type = format.matchesHeader(header) ? format.mimeType : "application/octet-stream"
                return MediaVerificationReport.Asset(sha256: digest, sizeBytes: count, mediaType: type)
            }
        }
        if let coordinationError { throw coordinationError }
        guard let result else { throw CompanionError.message("Could not open the selected file.") }
        return try result.get()
    }
}

struct VerificationJSON: Transferable {
    let contents: Data
    let fileName: String

    static var transferRepresentation: some TransferRepresentation {
        DataRepresentation(exportedContentType: .json) { $0.contents }
            .suggestedFileName { $0.fileName }
    }
}
