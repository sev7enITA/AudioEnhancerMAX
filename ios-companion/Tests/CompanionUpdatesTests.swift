import CryptoKit
import XCTest
@testable import AudioEnhancerCompanion

final class CompanionUpdatesTests: XCTestCase {
    private let now = Date(timeIntervalSince1970: 1_800_000_000)
    private let artifact = Data("valid fixture archive bytes".utf8)

    private func hash(_ bytes: Data) -> String {
        SHA256.hash(data: bytes).map { String(format: "%02x", $0) }.joined()
    }

    private func signedFeed(
        key: P256.Signing.PrivateKey,
        issued: Int = 1_799_999_900,
        expires: Int = 1_800_010_000,
        fields: [String: Any] = [:],
        alterPayloadAfterSigning: Bool = false
    ) throws -> Data {
        let release: [String: Any] = [
            "version": "4.1.1", "build": 13, "package_id": "com.fabriziodegni.audioenhancermax.companion",
            "filename": "AudioEnhancerCompanion-4.1.1-build-13-unsigned-xcarchive.zip",
            "sha256": hash(artifact), "size_bytes": artifact.count, "tag": "v4.1.1-mobile-beta.1",
        ]
        var payload = try JSONSerialization.data(withJSONObject: [
            "schema": "audioenhancermax.mobile-updates.v1",
            "issued_at": issued, "expires_at": expires,
            "releases": ["ios": release.merging(fields) { _, new in new }],
        ], options: .sortedKeys)
        let signature = try key.signature(for: payload).derRepresentation
        if alterPayloadAfterSigning { payload.append(32) }
        return try JSONSerialization.data(withJSONObject: [
            "payload": payload.base64EncodedString(), "signature": signature.base64EncodedString(),
        ])
    }

    func testSignedPayloadUsesExactBytesAndOnlyCurrentOrNewerBuild() throws {
        let key = P256.Signing.PrivateKey()
        let valid = try CompanionUpdateFeed.decode(signedFeed(key: key), publicKey: key.publicKey, now: now)
        XCTAssertEqual(valid.release.tag, "v4.1.1-mobile-beta.1")
        XCTAssertEqual(valid.release.compare(installedVersion: "4.1.0", installedBuild: 12), .newer)
        XCTAssertEqual(valid.release.compare(installedVersion: "4.1.1", installedBuild: 13), .same)
        XCTAssertEqual(valid.release.compare(installedVersion: "4.2.0", installedBuild: 12), .unavailable)
        XCTAssertEqual(valid.release.compare(installedVersion: "4.1.0", installedBuild: 14), .unavailable)
        XCTAssertThrowsError(try CompanionUpdateFeed.decode(
            signedFeed(key: key, alterPayloadAfterSigning: true), publicKey: key.publicKey, now: now))
        XCTAssertThrowsError(try CompanionUpdateFeed.decode(
            signedFeed(key: key), publicKey: P256.Signing.PrivateKey().publicKey, now: now))
    }

    func testRejectsExpiredFutureOrOverlongFeedAndWrongAssetShape() throws {
        let key = P256.Signing.PrivateKey()
        for (issue, expiry) in [
            (1_799_999_900, 1_800_000_000),
            (1_800_000_301, 1_800_010_000),
            (1_799_999_900, 1_900_010_000),
        ] {
            XCTAssertThrowsError(try CompanionUpdateFeed.decode(signedFeed(key: key, issued: issue, expires: expiry),
                                                                 publicKey: key.publicKey, now: now))
        }
        for fields: [String: Any] in [
            ["filename": "../companion.ipa"],
            ["package_id": "com.other.app"],
            ["tag": "v4.1.1-mobile-beta.1/extra"],
            ["sha256": String(repeating: "G", count: 64)],
            ["size_bytes": CompanionUpdateRelease.maximumBytes + 1],
        ] {
            XCTAssertThrowsError(try CompanionUpdateFeed.decode(signedFeed(key: key, fields: fields),
                                                                 publicKey: key.publicKey, now: now))
        }
    }

    func testOnlySelectedRepositoryAndOfficialMirrorsMayRedirect() throws {
        let key = P256.Signing.PrivateKey()
        let release = try CompanionUpdateFeed.decode(signedFeed(key: key), publicKey: key.publicKey, now: now).release
        let github = CompanionUpdateSource.github, sourceforge = CompanionUpdateSource.sourceforge
        XCTAssertTrue(github.allows(github.archiveURL(release), release: release))
        XCTAssertTrue(github.allows(try XCTUnwrap(URL(string: "https://release-assets.githubusercontent.com/github-production-release-asset/1292611395/925bdb37-2e5c-4815-985e-d0e4826ac01b?ticket=fake")),
                                    release: release))
        let sfPath = sourceforge.archiveURL(release).path
        XCTAssertTrue(sourceforge.allows(try XCTUnwrap(URL(string: "https://netix.dl.sourceforge.net\(sfPath)")), release: release))
        XCTAssertFalse(github.allows(sourceforge.archiveURL(release), release: release))
        XCTAssertFalse(sourceforge.allows(github.archiveURL(release), release: release))
        for bad in [
            "http://release-assets.githubusercontent.com/file",
            "https://release-assets.githubusercontent.com.evil.test/file",
            "https://name@release-assets.githubusercontent.com/file",
            "https://release-assets.githubusercontent.com:444/file",
            "https://release-assets.githubusercontent.com/github-production-release-asset/1292611396/925bdb37-2e5c-4815-985e-d0e4826ac01b",
            "https://github.com/sev7enITA/AudioEnhancerMAX/releases/download/elsewhere",
        ] {
            XCTAssertFalse(github.allows(try XCTUnwrap(URL(string: bad)), release: release))
        }
        for bad in [
            "https://mirror.dl.sourceforge.net.evil.test\(sfPath)",
            "https://mirror.dl.sourceforge.net/project/unknown/asset.zip",
            "https://sourceforge.net\(sfPath)",
        ] {
            XCTAssertFalse(sourceforge.allows(try XCTUnwrap(URL(string: bad)), release: release))
        }
    }

    func testFailedTransferKeepsPreviousVerifiedExport() async throws {
        let key = P256.Signing.PrivateKey()
        let current = Int(Date().timeIntervalSince1970)
        let feed = try CompanionUpdateFeed.decode(signedFeed(key: key, issued: current - 1, expires: current + 300),
                                                   publicKey: key.publicKey)
        let folder = FileManager.default.temporaryDirectory.appendingPathComponent("update-test-\(UUID())")
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: false)
        defer { try? FileManager.default.removeItem(at: folder) }
        let saved = folder.appendingPathComponent(feed.release.filename)
        let existing = Data("keep previous export".utf8)
        try existing.write(to: saved)
        for bad in [Data(artifact.dropLast()), Data(repeating: 1, count: artifact.count)] {
            do {
                _ = try await CompanionUpdateService.download(feed, from: .github, in: folder) { _, file, _, _ in
                    try file.write(contentsOf: bad)
                    return .init(data: Data(), size: bad.count, sha256: self.hash(bad))
                }
                XCTFail("A mismatched transfer must fail")
            } catch {
                XCTAssertEqual(try Data(contentsOf: saved), existing)
                XCTAssertEqual(try FileManager.default.contentsOfDirectory(atPath: folder.path), [feed.release.filename])
            }
        }
        let committed = try await CompanionUpdateService.download(feed, from: .github, in: folder) { url, file, release, allows in
            XCTAssertTrue(allows(url))
            XCTAssertEqual(release.sizeBytes, artifact.count)
            try file.write(contentsOf: artifact)
            return .init(data: Data(), size: artifact.count, sha256: self.hash(artifact))
        }
        XCTAssertEqual(committed, saved)
        XCTAssertEqual(try Data(contentsOf: saved), artifact)
    }

    func testAppStoreLinkRequiresExactIOSListingConfiguration() {
        XCTAssertNil(CompanionDistribution.appStoreURL(listingID: ""))
        XCTAssertNil(CompanionDistribution.appStoreURL(listingID: "6791591803"))
        XCTAssertNil(CompanionDistribution.appStoreURL(listingID: "https://apps.apple.com/app/id123456789"))
        XCTAssertEqual(CompanionDistribution.appStoreURL(listingID: "123456789")?.absoluteString, "https://apps.apple.com/app/id123456789")
        XCTAssertNotNil(Bundle.main.url(forResource: "companion-update-public", withExtension: "pem"))
    }
}
