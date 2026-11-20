import CryptoKit
import XCTest
@testable import AudioEnhancerCompanion

final class ContentCredentialsTests: XCTestCase {
    func testValidAlteredAndUnsignedAudio() throws {
        let fixtures = Bundle(for: Self.self)
        let folder = "v4.0.0-beta.1"
        let signed = try XCTUnwrap(fixtures.url(forResource: "signed-sample", withExtension: "wav", subdirectory: folder))
        let altered = try XCTUnwrap(fixtures.url(forResource: "altered-sample", withExtension: "wav", subdirectory: folder))
        let unsigned = try XCTUnwrap(fixtures.url(forResource: "phone24", withExtension: "wav"))
        let report = try XCTUnwrap(fixtures.url(forResource: "processing-report", withExtension: "json", subdirectory: folder))
        let digest = SHA256.hash(data: try Data(contentsOf: report)).map { String(format: "%02x", $0) }.joined()

        let verified = MobileContentCredentials.inspect(signed)
        XCTAssertEqual(verified.outcome, "Integrity verified", verified.detail)
        XCTAssertEqual(verified.signerTrust, "unrecognized")
        XCTAssertEqual(verified.reportFingerprint, digest)
        XCTAssertEqual(MobileContentCredentials.inspect(altered).outcome, "Integrity check failed")
        XCTAssertEqual(MobileContentCredentials.inspect(unsigned).outcome, "No embedded credentials")
    }
}
