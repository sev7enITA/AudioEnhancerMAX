import CryptoKit
import XCTest
@testable import AudioEnhancerCompanion

final class MediaVerificationTests: XCTestCase {
    func testSameAssetYieldsExactFingerprintCredentialsAndTechnicalMeasurements() async throws {
        let fixtures = Bundle(for: Self.self)
        let url = try XCTUnwrap(fixtures.url(forResource: "signed-sample", withExtension: "wav", subdirectory: "v4.0.0-beta.1"))
        let expected = try Data(contentsOf: url)
        let digest = SHA256.hash(data: expected).map { String(format: "%02x", $0) }.joined()
        let report = try await MobileMediaVerification.verify(url)
        XCTAssertEqual(report.asset.sha256, digest)
        XCTAssertEqual(report.asset.sizeBytes, expected.count)
        XCTAssertEqual(report.asset.mediaType, "audio/wav")
        XCTAssertEqual(report.credentials.status, "valid")
        XCTAssertEqual(report.credentials.signerTrust, "unrecognized")
        XCTAssertEqual(report.credentials.issuer, "AudioEnhancerMAX test only")
        XCTAssertEqual(Set(report.credentials.actions), ["c2pa.opened", "c2pa.modified"])
        XCTAssertTrue(report.credentials.failureCodes.contains("signingCredential.untrusted"))
        XCTAssertEqual(report.audio.status, "measured")
        XCTAssertGreaterThan(try XCTUnwrap(report.audio.analyzedSeconds), 0)
        XCTAssertLessThanOrEqual(try XCTUnwrap(report.audio.analyzedSeconds), MobileMediaVerification.previewSeconds)

        let document = try XCTUnwrap(JSONSerialization.jsonObject(with: report.json()) as? [String: Any])
        XCTAssertEqual(document["schema"] as? String, "audioenhancermax.media-verification.v1")
        let asset = try XCTUnwrap(document["asset"] as? [String: Any])
        XCTAssertEqual(asset["size_bytes"] as? Int, expected.count)
        XCTAssertEqual(asset["sha256"] as? String, digest)
        let audio = try XCTUnwrap(document["audio"] as? [String: Any])
        XCTAssertNotNil(audio["peak_dbfs"] as? Double)
        XCTAssertNotNil(audio["sample_rate_hz"] as? Int)
        let credentials = try XCTUnwrap(document["credentials"] as? [String: Any])
        XCTAssertEqual(credentials["actions"] as? [String], report.credentials.actions)
        XCTAssertEqual(credentials["processing_report_sha256"] as? String, report.credentials.reportFingerprint)
        XCTAssertFalse(String(decoding: try report.json(), as: UTF8.self).contains(url.path))
    }

    func testAnalysisStopsAtThirtySecondsAndMeasuresNativeChannels() async throws {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("\(UUID().uuidString).wav")
        defer { try? FileManager.default.removeItem(at: url) }
        let sampleRate = 8_000
        let wave = try Wave(samples: Array(repeating: Float(0.5), count: 35 * sampleRate), rate: sampleRate, channels: 1)
        try wave.encoded().write(to: url, options: .atomic)
        let report = try await MobileMediaVerification.verify(url)
        XCTAssertEqual(report.credentials.status, "unsigned")
        XCTAssertEqual(report.audio.status, "measured")
        XCTAssertEqual(report.audio.sampleRateHz, sampleRate)
        XCTAssertEqual(report.audio.channels, 1)
        XCTAssertEqual(report.audio.analyzedSeconds, 30)
        XCTAssertEqual(report.audio.sampleCount, 30 * sampleRate)
        XCTAssertEqual(try XCTUnwrap(report.audio.peakDbfs), -6.02, accuracy: 0.001)
        XCTAssertEqual(try XCTUnwrap(report.audio.rmsDbfs), -6.02, accuracy: 0.001)
        XCTAssertEqual(report.audio.nearFullScalePercent, 0)
    }

    func testAnAlteredAssetHasItsOwnFingerprintWithoutValidatedActions() async throws {
        let fixtures = Bundle(for: Self.self)
        let url = try XCTUnwrap(fixtures.url(forResource: "altered-sample", withExtension: "wav", subdirectory: "v4.0.0-beta.1"))
        let digest = SHA256.hash(data: try Data(contentsOf: url)).map { String(format: "%02x", $0) }.joined()
        let report = try await MobileMediaVerification.verify(url)
        XCTAssertEqual(report.asset.sha256, digest)
        XCTAssertEqual(report.credentials.status, "invalid")
        XCTAssertTrue(report.credentials.actions.isEmpty)
        XCTAssertTrue(report.credentials.failureCodes.contains("assertion.dataHash.mismatch"))
        XCTAssertEqual(report.audio.status, "measured")
    }

    func testRemoteURLAndOversizedLocalFileAreRejectedBeforeReading() async throws {
        let remote = try XCTUnwrap(URL(string: "https://example.invalid/media.wav"))
        XCTAssertFalse(MobileMediaVerification.accepts(remote))
        let file = FileManager.default.temporaryDirectory.appendingPathComponent("\(UUID().uuidString).wav")
        XCTAssertTrue(FileManager.default.createFile(atPath: file.path, contents: nil))
        defer { try? FileManager.default.removeItem(at: file) }
        let handle = try FileHandle(forWritingTo: file)
        try handle.truncate(atOffset: UInt64(MobileMediaVerification.maximumBytes) + 1)
        try handle.close()
        do {
            _ = try await MobileMediaVerification.verify(file)
            XCTFail("Files over the cap must be rejected")
        } catch {
            XCTAssertTrue(error.localizedDescription.contains("500 MiB"))
        }
    }

    func testFormatMismatchStillReportsTheExactBytes() async throws {
        let file = FileManager.default.temporaryDirectory.appendingPathComponent("\(UUID().uuidString).mp3")
        defer { try? FileManager.default.removeItem(at: file) }
        let bytes = try Wave(samples: [0.5, -0.5], rate: 8_000, channels: 1).encoded()
        try bytes.write(to: file, options: .atomic)
        let report = try await MobileMediaVerification.verify(file)
        let digest = SHA256.hash(data: bytes).map { String(format: "%02x", $0) }.joined()
        XCTAssertEqual(report.asset.sha256, digest)
        XCTAssertEqual(report.asset.sizeBytes, bytes.count)
        XCTAssertEqual(report.asset.mediaType, "application/octet-stream")
        XCTAssertEqual(report.credentials.status, "format_mismatch")
        XCTAssertEqual(report.audio.status, "unreadable_audio")
    }
}
