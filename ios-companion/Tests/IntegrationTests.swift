import XCTest
import CryptoKit
@testable import AudioEnhancerCompanion

final class IntegrationTests:XCTestCase {
    private func pairing() throws -> Pairing {
        guard let url=Bundle(for:Self.self).url(forResource:"SessionFixture",withExtension:"json") else{throw XCTSkip("Start an isolated Mac QA backend and provide SessionFixture.json to run TLS integration.")}
        return try Pairing.parse(String(contentsOf:url,encoding:.utf8))
    }
    func testPinnedTLSAndWrongCertificateRejected() async throws {
        let p=try pairing(),api=CompanionClient(p,device:UUID().uuidString)
        defer{api.invalidate()}
        let status=try await api.json("/v1/status");XCTAssertEqual(status["protocol"] as? Int,1)
        let bad=CompanionClient(Pairing(protocol:1,endpoint:p.endpoint,fingerprint:String(repeating:"0",count:64),token:p.token),device:UUID().uuidString)
        defer{bad.invalidate()}
        do{_ = try await bad.json("/v1/status");XCTFail("Wrong pin must be rejected")}catch{}
    }
    @MainActor func testRealMacProcessingKeepsTrimAndBindsReport() async throws {
        let p=try pairing(),model=CompanionModel()
        await model.connect(String(data:try JSONEncoder().encode(p),encoding:.utf8)!)
        XCTAssertTrue(model.paired);XCTAssertNil(model.error)
        var samples=[Float](repeating:0,count:96000)
        let phaseStep=2*Double.pi*440/48000
        for frame in 0..<48000 { samples[frame*2]=Float(sin(Double(frame)*phaseStep)*0.2) }
        let wave=try Wave(samples:samples,rate:48000,channels:2)
        let fixture=FileManager.default.temporaryDirectory.appendingPathComponent("qa-recording.wav")
        try wave.encoded().write(to:fixture)
        let previousFilter=model.importFilter
        model.importFilter = .wav
        defer{model.importFilter=previousFilter;model.disconnect();try? FileManager.default.removeItem(at:fixture)}
        await model.importAudio(fixture)
        XCTAssertEqual(model.source?.frames,48000)
        model.start=0.25;model.end=0.75
        await model.edit()
        let edit=try Data(contentsOf:XCTUnwrap(model.resultURL))
        let editSha=SHA256.hash(data:edit).map{String(format:"%02x",$0)}.joined()
        XCTAssertNil(model.reportURL)
        XCTAssertEqual(model.comparison?.sourceStart,0.25)
        model.remoteProfile="level";await model.processOnMac()
        XCTAssertNil(model.error)
        XCTAssertTrue(model.macState.hasPrefix("Completed · revision"))
        let audio=try Data(contentsOf:XCTUnwrap(model.resultURL))
        let report=try XCTUnwrap(JSONSerialization.jsonObject(with:Data(contentsOf:XCTUnwrap(model.reportURL))) as? [String:Any])
        XCTAssertEqual(SHA256.hash(data:audio).map{String(format:"%02x",$0)}.joined(),report["sha256"] as? String)
        XCTAssertEqual(editSha,report["source_sha256"] as? String)
        let result=try Wave(data:audio)
        XCTAssertEqual(result.frames,24000)
        XCTAssertEqual(result.channels,2)
        XCTAssertEqual(model.comparison?.sourceStart,0.25)
        XCTAssertEqual(CompanionModel().comparison?.sourceStart,0.25)
        XCTAssertEqual(model.source?.frames,48000)
        await model.edit();XCTAssertNil(model.reportURL)
    }
}
