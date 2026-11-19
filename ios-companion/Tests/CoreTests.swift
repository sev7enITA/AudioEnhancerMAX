import XCTest
@testable import AudioEnhancerCompanion

final class CoreTests:XCTestCase {
    func testComparisonAlignsTrimAndOnlyChangesListeningLevel() throws {
        let source=try Wave(samples:(0..<24000).map{(8000..<16000).contains($0) ? 0.2:0.8},rate:8000,channels:1)
        let result=try source.edited(start:1,end:2,gain:20*log10(2),normalize:false,voice:false)
        let span=try XCTUnwrap(AudioComparison.match(source:source,result:result,sourceStart:1))
        XCTAssertEqual(span.sourceStart,1)
        XCTAssertEqual(span.duration,1)
        XCTAssertTrue(span.contains(1.5))
        XCTAssertFalse(span.contains(0.9))
        XCTAssertFalse(span.contains(2))
        XCTAssertEqual(span.originalGain,1)
        XCTAssertEqual(span.resultGain,0.5,accuracy:1e-6)
        XCTAssertEqual(result.samples[0],0.4,accuracy:1e-6)
        XCTAssertNil(AudioComparison.match(source:source,result:result,sourceStart:2.5))
        let silence=try Wave(samples:[Float](repeating:0,count:8000),rate:8000,channels:1)
        XCTAssertEqual(AudioComparison.match(source:source,result:silence,sourceStart:1)?.originalGain,1)
    }
    func testWaveformBinsCoverTailShortClipsAndBothChannels() throws {
        let tail=try Wave(samples:(0..<149).map{$0==148 ? 0.8:0},rate:48000,channels:1).overview()
        XCTAssertEqual(tail.last,0.8);XCTAssertEqual(tail.count,100)
        XCTAssertTrue(try Wave(samples:[-0.5],rate:48000,channels:1).overview().allSatisfy{$0==0.5})
        XCTAssertEqual(try Wave(samples:[0,0.9,0.3,0],rate:48000,channels:2).overview(bins:2),[0.9,0.3])
    }
    func testSelectedImportFormatAndContentTypes() throws {
        XCTAssertTrue(MediaImportPolicy.Filter.wav.accepts(.wav))
        XCTAssertFalse(MediaImportPolicy.Filter.mp3.accepts(.wav))
        XCTAssertTrue(MediaImportPolicy.Filter.m4a.accepts(.mp4))
        XCTAssertFalse(MediaImportPolicy.Filter.m4a.accepts(.mp4,hasVideo:true))
        XCTAssertTrue(MediaImportPolicy.Filter.video.accepts(.mp4,hasVideo:true))
        XCTAssertFalse(MediaImportPolicy.Filter.video.accepts(.mp4))
        XCTAssertThrowsError(try MediaImportPolicy.Filter.flac.validate(.mp3))
        for filter in MediaImportPolicy.Filter.allCases {
            XCTAssertFalse(filter.contentTypes.isEmpty)
            if filter != .all {XCTAssertFalse(filter.contentTypes.contains(.data))}
        }
    }
    func testStereoRoundTripAndIndependentChannels() throws {
        let wave=try Wave(samples:[0.25,-0.5,0.1,0.7],rate:48000,channels:2)
        let read=try Wave(data:wave.encoded())
        XCTAssertEqual(read.samples,wave.samples);XCTAssertEqual(read.channels,2);XCTAssertEqual(read.frames,2)
        let stereo=try Wave(samples:(0..<200).map{$0%2==0 ? 0.2:0},rate:8000,channels:2).autoEQ()
        XCTAssertEqual(stereo.samples.count,200);XCTAssertTrue(stride(from:1,to:200,by:2).allSatisfy{stereo.samples[$0]==0})
    }
    func testCoreReadsMacCompatiblePCM24() throws {
        let fixture=try XCTUnwrap(Bundle(for:Self.self).url(forResource:"phone24",withExtension:"wav"))
        let wave=try Wave(data:Data(contentsOf:fixture))
        XCTAssertEqual(wave.channels,1)
        XCTAssertTrue(wave.samples.contains{ $0 < 0 })
        XCTAssertTrue(wave.samples.contains{ $0 > 0 })
        XCTAssertLessThanOrEqual(wave.samples.map(abs).max() ?? .infinity,1)
    }
    func testTrimDoesNotMutateOriginalAndPreservesTail() throws {
        let wave=try Wave(samples:[Float](repeating:0.2,count:4811),rate:48000,channels:1)
        let full=try wave.edited(start:0,end:wave.duration,gain:0,normalize:false,voice:false)
        XCTAssertEqual(full.samples,wave.samples)
        let part=try wave.edited(start:0.01,end:0.05,gain:6,normalize:false,voice:false)
        XCTAssertEqual(part.frames,1920);XCTAssertEqual(wave.frames,4811)
        XCTAssertThrowsError(try wave.edited(start:-1,end:1,gain:0,normalize:true,voice:false))
    }
    func testNormalizeAndMalformedWave() throws {
        let wave=try Wave(samples:[0.25,-0.5],rate:48000,channels:1)
        let result=try wave.edited(start:0,end:wave.duration,gain:0,normalize:true,voice:false)
        XCTAssertEqual(abs(result.samples[1]),Float(pow(10,-1.0/20)),accuracy:1e-6)
        XCTAssertThrowsError(try Wave(data:wave.encoded().dropLast()))
        XCTAssertThrowsError(try Wave(samples:[.nan],rate:48000,channels:1))
    }
    func testPortableEQGolden() throws {
        let wave=try Wave(samples:[0.5]+[Float](repeating:0,count:63),rate:48000,channels:1).autoEQ()
        let expected:[Float]=[0.2537388801574707, 0.3574135899543762, -0.017744405195116997, -0.0826520249247551, 0.025471916422247887, -0.03540879487991333, -0.026337983086705208, -0.016061006113886833, -0.021267317235469818, -0.016432220116257668, -0.014093846082687378, -0.012847471050918102, -0.010575912892818451, -0.008943693712353706, -0.007497862447053194, -0.006224635522812605]
        for i in expected.indices {XCTAssertEqual(wave.samples[i],expected[i],accuracy:0.00001)}
    }
    func testBriefPersistenceInvalidationAndSeparateLyrics() throws {
        var draft=MusicDraft();draft.description="A calm opening";draft.lyrics="Not part of the prompt"
        try draft.build();XCTAssertTrue(draft.canExport);XCTAssertFalse(draft.prompt.contains(draft.lyrics))
        XCTAssertEqual(try JSONDecoder().decode(MusicDraft.self,from:JSONEncoder().encode(draft)),draft)
        draft.bpm="100";XCTAssertFalse(draft.canExport)
        draft.duration="0";XCTAssertThrowsError(try draft.build())
    }
    func testPairingRejectsUnsafeAndWrongProtocol() throws {
        func code(_ endpoint:String,_ version:Int=1)->String {"{\"protocol\":\(version),\"endpoint\":\"\(endpoint)\",\"fingerprint\":\"\(String(repeating:"a",count:64))\",\"token\":\"\(String(repeating:"b",count:32))\"}"}
        XCTAssertNoThrow(try Pairing.parse(code("https://192.168.1.2:4321")))
        for url in ["http://192.168.1.2:4321","https://user:pass@localhost","https://localhost/path","https://localhost?query=yes"] {XCTAssertThrowsError(try Pairing.parse(code(url)))}
        XCTAssertThrowsError(try Pairing.parse(code("https://localhost",2)))
    }
}
