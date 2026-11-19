import XCTest
import Vision
@testable import AudioEnhancerCompanion

final class PairingQrTests: XCTestCase {
    func testReadsMacGeneratedQrAndValidatesPairing() throws {
        let bundle=Bundle(for:Self.self)
        let url=try XCTUnwrap(bundle.url(forResource:"pairing-fixture",withExtension:"png"))
        let expectedURL=try XCTUnwrap(bundle.url(forResource:"pairing-fixture",withExtension:"json"))
        // Use the CPU decoder in simulator tests; the simulator has no camera/ANE.
        let request=VNDetectBarcodesRequest();request.revision=VNDetectBarcodesRequestRevision1
        request.usesCPUOnly=true;request.symbologies=[.qr]
        try VNImageRequestHandler(url:url).perform([request])
        let text=try XCTUnwrap(request.results?.first?.payloadStringValue)
        XCTAssertEqual(try Pairing.parse(text),try Pairing.parse(String(contentsOf:expectedURL)))
    }
    func testRejectsUnrelatedAndOversizedQrContents() {
        for raw in ["https://example.com","{}",String(repeating:"x",count:4096)] {
            XCTAssertThrowsError(try Pairing.parse(raw))
        }
    }
}
