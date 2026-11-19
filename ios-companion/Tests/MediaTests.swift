import XCTest
import AVFoundation
import CryptoKit
@testable import AudioEnhancerCompanion

final class MediaTests:XCTestCase {
    func testNativeSelectedFormatRejectsMismatchAndKeepsWorkspace() async throws {
        let folder=FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at:folder,withIntermediateDirectories:true)
        defer{try? FileManager.default.removeItem(at:folder)}
        let audio=try fixture("phone","m4a")
        let imported=try await MediaImport.read(audio,folder:folder,filter:.m4a)
        XCTAssertGreaterThan(imported.wave.duration,0)
        do{_ = try await MediaImport.read(audio,folder:folder,filter:.wav);XCTFail("M4A accepted by WAV filter")}catch{}
        do{_ = try await MediaImport.read(try fixture("short","mp4"),folder:folder,filter:.m4a);XCTFail("Video accepted by audio filter")}catch{}
        XCTAssertTrue((try FileManager.default.contentsOfDirectory(atPath:folder.path)).isEmpty)
    }
    func fixture(_ name:String,_ ext:String) throws -> URL {try XCTUnwrap(Bundle(for:Self.self).url(forResource:name,withExtension:ext))}
    func testSignaturesAndTimelineGuard() throws {
        XCTAssertEqual(try MediaImportPolicy.classify(Data("RIFF1234WAVE".utf8)),.wav)
        XCTAssertEqual(try MediaImportPolicy.classify(Data("ID3".utf8)),.mp3)
        XCTAssertEqual(try MediaImportPolicy.classify(Data([0,0,0,32])+Data("ftypisom".utf8)),.mp4)
        for bytes in [Data([0xff,0xd8,0xff,0xe0]),Data("not audio".utf8)] {XCTAssertThrowsError(try MediaImportPolicy.classify(bytes))}
        let source=try Wave(samples:[Float](repeating:0.1,count:48000),rate:48000,channels:1)
        XCTAssertNoThrow(try MediaImportPolicy.validateReplacement(source,source:source))
        XCTAssertThrowsError(try MediaImportPolicy.validateReplacement(source.edited(start:0,end:0.5,gain:0,normalize:false,voice:false),source:source))
    }
    func testSmartphoneRecordingsAndAnalysis() async throws {
        let folder=FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at:folder,withIntermediateDirectories:true)
        defer{try? FileManager.default.removeItem(at:folder)}
        for (name,ext) in [("phone","m4a"),("phone","aac"),("phone","flac"),("phone24","wav"),("phone","caf"),("phone","aiff"),("phone-alac","m4a")] {
            let original=try fixture(name,ext), hash=SHA256.hash(data:try Data(contentsOf:original)).map{String(format:"%02x",$0)}.joined()
            let media=try await MediaImport.read(original,folder:folder)
            XCTAssertEqual(media.wave.duration,2,accuracy:0.12,"\(name).\(ext)")
            XCTAssertNil(media.video);XCTAssertTrue(media.analysis.contains(hash));XCTAssertTrue(media.analysis.contains("48000"))
        }
    }
    func testNinetySecondStereoRecordingExceedsOldLimit() async throws {
        let folder=FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at:folder,withIntermediateDirectories:true)
        defer{try? FileManager.default.removeItem(at:folder)}
        let media=try await MediaImport.read(fixture("phone90","m4a"),folder:folder)
        XCTAssertEqual(media.wave.duration,90,accuracy:0.1)
        XCTAssertGreaterThan(media.wave.samples.count*4,20*1024*1024)
    }
    @MainActor func testDeviceAssessmentIsMeasuredAndBounded() async throws {
        try await DeviceAssessment.measure()
        XCTAssertGreaterThan(try XCTUnwrap(DeviceAssessment.measuredMs),0)
        XCTAssertEqual(DeviceAssessment.snapshot()["benchmark"] as? String,"voice-eq-2s-48k-mono-v1")
        XCTAssertLessThan(DeviceAssessment.header().count,4096)
    }
    func testNativeMP3AndMP4DecodeReplaceAndReadBack() async throws {
        let folder=FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at:folder,withIntermediateDirectories:true)
        defer{try? FileManager.default.removeItem(at:folder)}
        let mp3=try await MediaImport.read(fixture("short","mp3"),folder:folder)
        XCTAssertNil(mp3.video);XCTAssertEqual(mp3.wave.duration,2,accuracy:0.05)
        let original=try fixture("short","mp4"), originalHash=SHA256.hash(data:try Data(contentsOf:original))
        let media=try await MediaImport.read(original,folder:folder)
        XCTAssertNotNil(media.video);XCTAssertEqual(media.wave.duration,2,accuracy:0.05)
        let edited=try media.wave.edited(start:0,end:media.wave.duration,gain:-12,normalize:false,voice:false)
        let wav=folder.appendingPathComponent("edit.wav"), output=folder.appendingPathComponent("copy.mp4")
        try edited.encoded().write(to:wav)
        try await MediaImport.replaceAudio(video:try XCTUnwrap(media.video),result:wav,source:media.wave,output:output)
        let reread=try await MediaImport.read(output,folder:folder)
        XCTAssertEqual(reread.wave.duration,media.wave.duration,accuracy:0.002)
        let rms: (Wave)->Double = {sqrt($0.samples.reduce(0){$0+Double($1*$1)}/Double($0.samples.count))}
        XCTAssertEqual(rms(reread.wave)/rms(media.wave),pow(10,-12.0/20),accuracy:0.03)
        XCTAssertEqual(SHA256.hash(data:try Data(contentsOf:original)),originalHash)
        let asset=AVURLAsset(url:output), sourceAsset=AVURLAsset(url:original)
        let duration=try await asset.load(.duration), sourceDuration=try await sourceAsset.load(.duration)
        XCTAssertEqual(duration.seconds,sourceDuration.seconds,accuracy:0.002)
        // Keep a synthetic native export for independent stream/frame inspection.
        let proof=FileManager.default.urls(for:.documentDirectory,in:.userDomainMask)[0].appendingPathComponent("qa-video-export.mp4")
        try? FileManager.default.removeItem(at:proof);try FileManager.default.copyItem(at:output,to:proof)
    }
    func testOffsetAndRotationArePreserved() async throws {
        let folder=FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at:folder,withIntermediateDirectories:true)
        defer{try? FileManager.default.removeItem(at:folder)}
        let original=try fixture("offset-rotated","mp4")
        let media=try await MediaImport.read(original,folder:folder)
        let wav=folder.appendingPathComponent("audio.wav"), output=folder.appendingPathComponent("copy.mp4")
        try media.wave.encoded().write(to:wav)
        try await MediaImport.replaceAudio(video:try XCTUnwrap(media.video),result:wav,source:media.wave,output:output)
        let before=try await MediaImport.videoTracks(AVURLAsset(url:original)), after=try await MediaImport.videoTracks(AVURLAsset(url:output))
        let oldTransform=try await before.video.load(.preferredTransform), newTransform=try await after.video.load(.preferredTransform)
        XCTAssertEqual(oldTransform,newTransform)
        let oldRange=try await before.audio.load(.timeRange), newRange=try await after.audio.load(.timeRange)
        XCTAssertEqual(oldRange.start.seconds,newRange.start.seconds,accuracy:0.03)
        XCTAssertEqual(oldRange.duration.seconds,newRange.duration.seconds,accuracy:0.002)
    }
    @MainActor func testRejectedImportPreservesWorkspaceAndAudioImportClearsVideo() async throws {
        let model=CompanionModel()
        await model.importAudio(try fixture("short","mp4"))
        XCTAssertNil(model.error);XCTAssertNotNil(model.videoSourceURL)
        await model.edit();XCTAssertNotNil(model.resultURL)
        await model.exportVideo();XCTAssertNil(model.error);XCTAssertNotNil(model.videoResultURL)
        let video=model.videoSourceURL, source=model.source?.samples, result=model.resultURL
        await model.importAudio(try fixture("silent","mp4"))
        XCTAssertNotNil(model.error);XCTAssertEqual(video,model.videoSourceURL);XCTAssertEqual(source,model.source?.samples);XCTAssertEqual(result,model.resultURL)
        model.error=nil
        let restored=CompanionModel();XCTAssertEqual(restored.videoSourceURL,video)
        await model.importAudio(try fixture("short","mp3"))
        XCTAssertNil(model.error);XCTAssertNil(model.videoSourceURL);XCTAssertNil(model.videoResultURL);XCTAssertNil(model.resultURL)
        XCTAssertFalse(FileManager.default.fileExists(atPath:try XCTUnwrap(video).path))
    }
    func testVideoWithoutAudioFailsWithoutRetainedCopy() async throws {
        let folder=FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at:folder,withIntermediateDirectories:true)
        defer{try? FileManager.default.removeItem(at:folder)}
        do{_ = try await MediaImport.read(fixture("silent","mp4"),folder:folder);XCTFail("Missing audio must fail")}catch{}
        XCTAssertEqual(try FileManager.default.contentsOfDirectory(atPath:folder.path),[])
    }
}
