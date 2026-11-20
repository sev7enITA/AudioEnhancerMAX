import AVFoundation
import Foundation
import ImageIO
import UniformTypeIdentifiers

struct MediaMetadata: Codable, Sendable {
    enum Status: String, Codable, Sendable {
        case read, unreadable
        case noTracks = "no_tracks"
        case formatMismatch = "format_mismatch"
    }

    struct Track: Codable, Sendable {
        let index: Int
        let mediaType: String
        let codecs: [String]
        var durationSeconds: Double?
        var sampleRateHz: Double?
        var channels: Int?
        var bitDepth: Int?
        var width: Int?
        var height: Int?
        var nominalFrameRate: Double?
    }

    struct LocalTag: Codable, Sendable {
        let label: String
        let value: String
    }

    let status: Status
    var reader: String?
    var container: String?
    var durationSeconds: Double?
    var trackCount: Int?
    var tracks: [Track] = []
    var tagNamespaces: [String] = []
    var localTags: [LocalTag] = []
    var artworkExif: ArtworkExif?

    var technicalExport: MediaMetadata {
        var copy = self
        copy.localTags = []
        copy.artworkExif = nil
        return copy
    }
}

struct ArtworkExif: Codable, Sendable {
    enum Status: String, Codable, Sendable {
        case read
        case notFound = "not_found"
        case notCheckedSize = "not_checked_size"
        case unreadable
    }

    let status: Status
    var cameraMake: String?
    var cameraModel: String?
    var lensMake: String?
    var lensModel: String?
    var exposureSeconds: Double?
    var fNumber: Double?
    var iso: Int?
    var focalLengthMillimeters: Double?
}

enum MediaMetadataReader {
    private static let trackLimit = 16
    private static let artworkAssetLimit = 16 * 1024 * 1024
    private static let artworkLimit = 4 * 1024 * 1024

    static func inspect(_ asset: AVURLAsset, format: VerificationFormat, sizeBytes: Int) async throws -> MediaMetadata {
        var namespaces = Set((try? await asset.load(.availableMetadataFormats))?.map(namespaceName) ?? [])
        let duration = (try? await asset.load(.duration)).flatMap { seconds($0.seconds) }
        let common: [AVMetadataItem]?
        if sizeBytes <= artworkAssetLimit { common = try? await asset.load(.commonMetadata) }
        else { common = nil }
        let artwork = try await inspectArtwork(common, sizeBytes: sizeBytes)
        let tags = try await readLocalTags(asset, common: common, sizeBytes: sizeBytes)
        let mediaTracks: [AVAssetTrack]
        do {
            mediaTracks = try await asset.load(.tracks)
        } catch {
            try Task.checkCancellation()
            return MediaMetadata(status: .unreadable, reader: "AVFoundation", container: format.rawValue.uppercased(),
                                 durationSeconds: duration, tagNamespaces: namespaces.sorted(), localTags: tags, artworkExif: artwork)
        }
        var descriptions: [MediaMetadata.Track] = []
        for (index, track) in mediaTracks.prefix(trackLimit).enumerated() {
            try Task.checkCancellation()
            namespaces.formUnion((try? await track.load(.availableMetadataFormats))?.map(namespaceName) ?? [])
            descriptions.append(await describe(track, index: index + 1))
        }
        try Task.checkCancellation()
        let status: MediaMetadata.Status = mediaTracks.isEmpty ? ((duration ?? 0) > 0 ? .noTracks : .unreadable) : .read
        return MediaMetadata(status: status, reader: "AVFoundation", container: format.rawValue.uppercased(),
                             durationSeconds: duration, trackCount: mediaTracks.count, tracks: descriptions,
                             tagNamespaces: namespaces.sorted(), localTags: tags, artworkExif: artwork)
    }

    private static func describe(_ track: AVAssetTrack, index: Int) async -> MediaMetadata.Track {
        let formats = ((try? await track.load(.formatDescriptions)) ?? []).prefix(8)
        let codecs = Set(formats.map { fourCC(CMFormatDescriptionGetMediaSubType($0)) }).sorted()
        let duration = (try? await track.load(.timeRange)).flatMap { seconds($0.duration.seconds) }
        var observation = MediaMetadata.Track(index: index, mediaType: mediaTypeName(track.mediaType), codecs: codecs,
                                              durationSeconds: duration)
        if track.mediaType == .audio, let first = formats.first,
           let stream = CMAudioFormatDescriptionGetStreamBasicDescription(first)?.pointee {
            observation.sampleRateHz = number(stream.mSampleRate, through: 2_000_000)
            if (1...1024).contains(stream.mChannelsPerFrame) { observation.channels = Int(stream.mChannelsPerFrame) }
            if (1...64).contains(stream.mBitsPerChannel) { observation.bitDepth = Int(stream.mBitsPerChannel) }
        } else if track.mediaType == .video {
            if let first = formats.first {
                let dimensions = CMVideoFormatDescriptionGetDimensions(first)
                if dimensions.width > 0, dimensions.height > 0 {
                    observation.width = Int(dimensions.width)
                    observation.height = Int(dimensions.height)
                }
            }
            if let frameRate = try? await track.load(.nominalFrameRate) {
                observation.nominalFrameRate = number(Double(frameRate), through: 10_000)
            }
        }
        return observation
    }

    private static func namespaceName(_ format: AVMetadataFormat) -> String {
        switch format {
        case .id3Metadata: "ID3"
        case .iTunesMetadata: "iTunes / MP4"
        case .quickTimeMetadata: "QuickTime metadata"
        case .quickTimeUserData: "QuickTime user data"
        case .isoUserData: "ISO base media user data"
        default: "Other metadata exposed by AVFoundation"
        }
    }

    private static func mediaTypeName(_ type: AVMediaType) -> String {
        switch type {
        case .audio: "audio"
        case .video: "video"
        case .subtitle: "subtitle"
        case .closedCaption: "closed_caption"
        case .text: "text"
        case .metadata: "metadata"
        default: "other"
        }
    }

    private static func fourCC(_ code: FourCharCode) -> String {
        let bytes = [UInt8(truncatingIfNeeded: code >> 24), UInt8(truncatingIfNeeded: code >> 16),
                     UInt8(truncatingIfNeeded: code >> 8), UInt8(truncatingIfNeeded: code)]
        if code != 0, bytes.allSatisfy({ (0x20...0x7E).contains($0) }) {
            return String(decoding: bytes, as: UTF8.self).trimmingCharacters(in: .whitespaces)
        }
        return String(format: "0x%08x", code)
    }

    private static func seconds(_ value: Double) -> Double? {
        value.isFinite && value >= 0 ? value : nil
    }

    private static func number(_ value: Double?, through limit: Double) -> Double? {
        guard let value, value.isFinite, value > 0, value <= limit else { return nil }
        return value
    }

    private static func readLocalTags(_ asset: AVURLAsset, common: [AVMetadataItem]?, sizeBytes: Int) async throws -> [MediaMetadata.LocalTag] {
        guard sizeBytes <= artworkAssetLimit else { return [] }
        let keys: [(AVMetadataKey, String)] = [(.commonKeyTitle, "Title"), (.commonKeyArtist, "Artist"), (.commonKeyAlbumName, "Album")]
        var tags: [MediaMetadata.LocalTag] = []
        for (key, label) in keys {
            try Task.checkCancellation()
            if let item = common?.first(where: { $0.commonKey == key }),
               let value = cleanText(try? await item.load(.stringValue)) {
                tags.append(.init(label: label, value: value))
            }
        }
        let videoKeys: [(AVMetadataIdentifier, String)] = [(.quickTimeMetadataMake, "Camera make"), (.quickTimeMetadataModel, "Camera model")]
        if let items = try? await asset.loadMetadata(for: .quickTimeMetadata) {
            for (key, label) in videoKeys {
                try Task.checkCancellation()
                if let item = items.first(where: { $0.identifier == key }),
                   let value = cleanText(try? await item.load(.stringValue)) {
                    tags.append(.init(label: label, value: value))
                }
            }
        }
        return tags
    }

    private static func cleanText(_ value: Any?) -> String? {
        guard let value = value as? String else { return nil }
        let rendered = String(value.prefix(100).unicodeScalars.filter {
            ($0 == " " || !$0.properties.isWhitespace) && !CharacterSet.controlCharacters.contains($0)
                && $0.properties.generalCategory != .format
        }).trimmingCharacters(in: .whitespaces)
        return rendered.isEmpty ? nil : rendered
    }

    private static func inspectArtwork(_ candidates: [AVMetadataItem]?, sizeBytes: Int) async throws -> ArtworkExif {
        // AVFoundation delivers a whole artwork value. Bound the source before asking for any value.
        guard sizeBytes <= artworkAssetLimit else { return ArtworkExif(status: .notCheckedSize) }
        guard let candidates else {
            try Task.checkCancellation()
            return ArtworkExif(status: .unreadable)
        }
        let artwork = candidates.filter { $0.commonKey == .commonKeyArtwork || $0.identifier == .commonIdentifierArtwork }.prefix(4)
        var skippedForSize = false, failedRead = false
        for item in artwork {
            try Task.checkCancellation()
            guard let data = try? await item.load(.dataValue) else { failedRead = true; continue }
            if data.count > artworkLimit { skippedForSize = true; continue }
            if let facts = readArtworkExif(data) { return facts }
        }
        try Task.checkCancellation()
        if skippedForSize { return ArtworkExif(status: .notCheckedSize) }
        return ArtworkExif(status: failedRead ? .unreadable : .notFound)
    }

    static func readArtworkExif(_ data: Data) -> ArtworkExif? {
        guard data.count <= artworkLimit,
              data.starts(with: [0xFF, 0xD8, 0xFF]) || data.starts(with: [0x49, 0x49, 0x2A, 0x00])
                || data.starts(with: [0x4D, 0x4D, 0x00, 0x2A]) else { return nil }
        let options = [kCGImageSourceShouldCache: false] as CFDictionary
        guard let source = CGImageSourceCreateWithData(data as CFData, options),
              let format = CGImageSourceGetType(source) as String?,
              format == UTType.jpeg.identifier || format == UTType.tiff.identifier,
              let properties = CGImageSourceCopyPropertiesAtIndex(source, 0, options) as? [String: Any],
              let exif = properties[kCGImagePropertyExifDictionary as String] as? [String: Any], !exif.isEmpty else {
            return nil
        }
        let tiff = properties[kCGImagePropertyTIFFDictionary as String] as? [String: Any] ?? [:]
        func value(_ key: CFString, limit: Double) -> Double? {
            number((exif[key as String] as? NSNumber)?.doubleValue, through: limit)
        }
        let rawISO = (exif[kCGImagePropertyExifISOSpeedRatings as String] as? [NSNumber])?.first?.intValue
        return ArtworkExif(status: .read,
                           cameraMake: cleanText(tiff[kCGImagePropertyTIFFMake as String]),
                           cameraModel: cleanText(tiff[kCGImagePropertyTIFFModel as String]),
                           lensMake: cleanText(exif[kCGImagePropertyExifLensMake as String]),
                           lensModel: cleanText(exif[kCGImagePropertyExifLensModel as String]),
                           exposureSeconds: value(kCGImagePropertyExifExposureTime, limit: 86_400),
                           fNumber: value(kCGImagePropertyExifFNumber, limit: 200),
                           iso: rawISO.flatMap { (1...1_000_000).contains($0) ? $0 : nil },
                           focalLengthMillimeters: value(kCGImagePropertyExifFocalLength, limit: 100_000))
    }
}
