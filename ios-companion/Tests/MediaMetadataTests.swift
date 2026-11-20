import XCTest
@testable import AudioEnhancerCompanion

final class MediaMetadataTests: XCTestCase {
    private func fixture(_ name: String, ext: String) throws -> URL {
        try XCTUnwrap(Bundle(for: Self.self).url(forResource: name, withExtension: ext))
    }

    func testRealAlbumArtworkExifStaysOutOfTechnicalExport() async throws {
        for (name, ext, tag) in [("fixture-mp3-cover-exif", "mp3", "ID3"), ("fixture-aac-cover-exif", "m4a", "iTunes / MP4")] {
            let result = try await MobileMediaVerification.verify(fixture(name, ext: ext))
            let metadata = try XCTUnwrap(result.metadata)
            XCTAssertEqual(metadata.status, .read)
            XCTAssertTrue(metadata.tagNamespaces.contains(tag), metadata.tagNamespaces.joined(separator: ","))
            let exif = try XCTUnwrap(metadata.artworkExif)
            XCTAssertEqual(exif.status, .read)
            XCTAssertEqual(exif.cameraMake, "QA Camera Corp")
            XCTAssertEqual(exif.cameraModel, "Fixture Body")
            XCTAssertEqual(try XCTUnwrap(exif.exposureSeconds), 1.0 / 125, accuracy: 0.000001)
            XCTAssertEqual(exif.fNumber, 2.8)
            XCTAssertEqual(exif.iso, 200)
            XCTAssertTrue(metadata.localTags.contains { $0.label == "Title" })
            let encoded = try result.json()
            let document = try XCTUnwrap(JSONSerialization.jsonObject(with: encoded) as? [String: Any])
            let fields = try XCTUnwrap(document["metadata"] as? [String: Any])
            XCTAssertNil(fields["artwork_exif"])
            XCTAssertEqual((fields["local_tags"] as? [[String: Any]])?.count, 0)
            let json = String(decoding: encoded, as: UTF8.self)
            XCTAssertFalse(json.contains("QA Camera Corp"))
            XCTAssertFalse(json.contains("QA audio"))
            XCTAssertFalse(json.contains("Road test"))
            XCTAssertFalse(json.contains("Road AAC"))
            XCTAssertFalse(json.localizedCaseInsensitiveContains("GPS"))
        }
    }

    func testNativeWavAndQuickTimeDescriptionsAndPrivacy() async throws {
        let wav = try await MobileMediaVerification.verify(fixture("fixture-pcm24-bwf", ext: "wav"))
        let pcm = try XCTUnwrap(wav.metadata?.tracks.first)
        XCTAssertEqual(pcm.mediaType, "audio")
        XCTAssertEqual(pcm.bitDepth, 24)
        XCTAssertEqual(pcm.sampleRateHz, 16_000)
        XCTAssertEqual(wav.metadata?.artworkExif?.status, .notFound)
        let generic = try await MobileMediaVerification.verify(fixture("fixture-avc-aac", ext: "mov"))
        XCTAssertEqual(Set(generic.metadata?.tracks.map(\.mediaType) ?? []), ["audio", "video"])
        XCTAssertFalse(generic.metadata?.localTags.contains { $0.label == "Camera make" } ?? true)
        let mov = try await MobileMediaVerification.verify(fixture("fixture-native-camera", ext: "mov"))
        let meta = try XCTUnwrap(mov.metadata)
        XCTAssertEqual(meta.status, .read)
        XCTAssertEqual(Set(meta.tracks.map(\.mediaType)), ["audio", "video"])
        XCTAssertTrue(meta.tagNamespaces.contains("QuickTime metadata"))
        XCTAssertEqual(meta.localTags.first { $0.label == "Camera make" }?.value, "QA Video Camera")
        XCTAssertEqual(meta.localTags.first { $0.label == "Camera model" }?.value, "Native Fixture")
        XCTAssertNil(meta.localTags.first { $0.label.localizedCaseInsensitiveContains("location") })
        let json = String(decoding: try mov.json(), as: UTF8.self)
        XCTAssertFalse(json.localizedCaseInsensitiveContains("camera make"))
        XCTAssertFalse(json.contains("QA Video Camera"))
        XCTAssertFalse(json.contains("+41.88+012.49"))
    }

    func testMetadataOnlyCAFAndVideoWithoutAudioRemainHonest() async throws {
        let caf = try await MobileMediaVerification.verify(fixture("phone", ext: "caf"))
        XCTAssertEqual(caf.credentials.status, "unsupported")
        XCTAssertEqual(caf.metadata?.status, .read)
        XCTAssertEqual(caf.metadata?.tracks.first?.mediaType, "audio")
        let silent = try await MobileMediaVerification.verify(fixture("silent", ext: "mp4"))
        XCTAssertEqual(silent.metadata?.status, .read)
        XCTAssertEqual(silent.metadata?.tracks.first?.mediaType, "video")
        XCTAssertEqual(silent.audio.status, "no_audio_track")
    }

    func testConditionalCodecProbesUseActualNativeDecoder() async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let cases = [("fixture-nb", "amr"), ("fixture-wb", "awb"), ("fixture-opus", "ogg"), ("fixture-vorbis", "ogg")]
        for (name, ext) in cases {
            guard let input = Bundle(for: Self.self).url(forResource: name, withExtension: ext) else { continue }
            var accepted: [Bool] = []
            for filter in [MediaImportPolicy.Filter.all, .conditional] {
                do {
                    let imported = try await MediaImport.read(input, folder: root, filter: filter)
                    XCTAssertGreaterThan(imported.wave.frames, 0)
                    accepted.append(true)
                } catch {
                    accepted.append(false)
                }
            }
            print("Native compatibility \(name).\(ext): \(accepted[0] ? "decoded" : "unavailable")")
            XCTAssertEqual(accepted[0], accepted[1], "Both routes must offer the same native decoding outcome.")
        }

        for (name, ext) in [("fixture-avc-aac", "3gp"), ("fixture-rf64", "wav")] {
            let report = try await MobileMediaVerification.verify(fixture(name, ext: ext))
            print("Native metadata \(name).\(ext): \(report.metadata?.status.rawValue ?? "missing"), audio \(report.audio.status)")
            if ext == "3gp" {
                XCTAssertEqual(report.credentials.status, "unsupported")
                XCTAssertEqual(report.metadata?.status, .read)
                XCTAssertTrue(report.metadata?.tracks.contains { $0.mediaType == "video" } == true)
            }
        }
    }

    func testStudioPickerAggregatesLiteralFormatRowsAndWelcomeUsesBuildIdentity() {
        let filters = MediaImportPolicy.Filter.allCases.filter { $0 != .all }
        XCTAssertEqual(MediaImportPolicy.Filter.all.extensions, filters.flatMap(\.extensions))
        XCTAssertTrue(MediaImportPolicy.Filter.all.extensions.contains("ogg"))
        XCTAssertTrue(MediaImportPolicy.Filter.all.extensions.contains("amr"))
        XCTAssertTrue(MediaImportPolicy.Filter.all.contentTypes.contains(.audio))
        XCTAssertTrue(MediaImportPolicy.Filter.conditional.accepts(.ogg))
        XCTAssertTrue(MediaImportPolicy.Filter.conditional.accepts(.amr))
        XCTAssertTrue(MediaImportPolicy.Filter.video.extensions.contains("3gp"))
        let current = CompanionBuildIdentity(version: "4.1.2", build: "14")
        XCTAssertTrue(current.showsMediaMetadataNotes)
        XCTAssertTrue(current.needsWelcome(after: "4.1.1+13"))
        XCTAssertFalse(current.needsWelcome(after: current.presentationKey))
        XCTAssertFalse(CompanionBuildIdentity(version: "4.1.3", build: "15").showsMediaMetadataNotes)
    }
}
