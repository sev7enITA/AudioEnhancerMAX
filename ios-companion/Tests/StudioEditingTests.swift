import XCTest
@testable import AudioEnhancerCompanion

final class StudioEditingTests: XCTestCase {
    func testStereoFadesUseTheSameEnvelopeAndPreserveSource() throws {
        let frames = 480
        let samples = (0..<frames).flatMap { _ in [Float(0.5), Float(-0.25)] }
        let wave = try Wave(samples: samples, rate: 8_000, channels: 2)
        let rendered = try wave.render(StudioEdit(start: 0.005, end: 0.055, fadeIn: 0.01, fadeOut: 0.01))
        XCTAssertEqual(rendered.sourceStart, 0.005, accuracy: 0.00001)
        XCTAssertEqual(rendered.wave.frames, 400)
        XCTAssertEqual(rendered.wave.channels, 2)
        XCTAssertEqual(rendered.wave.samples[0], 0)
        XCTAssertEqual(rendered.wave.samples[80], 0.25, accuracy: 0.00001)
        XCTAssertEqual(rendered.wave.samples[81], -0.125, accuracy: 0.00001)
        XCTAssertEqual(rendered.wave.samples[200], 0.5)
        XCTAssertEqual(rendered.wave.samples.suffix(2), [0, 0])
        XCTAssertEqual(wave.samples, samples)
    }

    func testSilencePreservesTimelineAndBothChannels() throws {
        let samples = (0..<800).flatMap { _ in [Float(0.5), Float(-0.25)] }
        let wave = try Wave(samples: samples, rate: 8_000, channels: 2)
        let edit = StudioEdit(start: 0.02, end: 0.06, rangeAction: .silence)
        let result = try wave.render(edit)
        XCTAssertEqual(result.sourceStart, 0)
        XCTAssertEqual(result.wave.frames, 800)
        XCTAssertEqual(Array(result.wave.samples[..<320]), Array(samples[..<320]))
        XCTAssertTrue(result.wave.samples[320..<960].allSatisfy { $0 == 0 })
        XCTAssertEqual(Array(result.wave.samples[960...]), Array(samples[960...]))
        XCTAssertEqual(AudioComparison.match(source: wave, result: result.wave, sourceStart: 0)?.duration, wave.duration)
    }

    func testNormalizeAfterFadesWithoutClipping() throws {
        let wave = try Wave(samples: [Float](repeating: 0.25, count: 80), rate: 8_000, channels: 1)
        let edit = StudioEdit(end: wave.duration, normalize: true, fadeIn: 0.01, fadeOut: 0.01)
        let result = try wave.render(edit).wave
        XCTAssertEqual(result.samples.max() ?? 0, Float(pow(10, -1.0 / 20)), accuracy: 0.00001)
        XCTAssertEqual(result.samples.first, 0)
        XCTAssertEqual(result.samples.last, 0)
        XCTAssertThrowsError(try wave.render(StudioEdit(end: wave.duration, fadeIn: .nan)))
    }

    func testHistoryCanUndoAndRedoANondestructiveRecipe() {
        var history = StudioEditHistory(current: StudioEdit(end: 2))
        var trim = history.current
        trim.start = 1
        history.replace(with: trim)
        XCTAssertTrue(history.canUndo)
        history.undo()
        XCTAssertEqual(history.current.start, 0)
        XCTAssertTrue(history.canRedo)
        history.redo()
        XCTAssertEqual(history.current, trim)
        history.undo()
        var fade = history.current
        fade.fadeIn = 0.2
        history.replace(with: fade)
        XCTAssertFalse(history.canRedo)
    }

    func testMeasuredWorkerRateUsesAcceptedAudioAndDSPTime() throws {
        var usage = WorkerUsage()
        XCTAssertNil(usage.realtimeFactor)
        let accepted = Date(timeIntervalSince1970: 100)
        usage.record(audioSeconds: 2, dspSeconds: 0.5, at: accepted)
        usage.record(audioSeconds: 6, dspSeconds: 1.5, at: accepted)
        usage.record(audioSeconds: 10, dspSeconds: .nan)
        XCTAssertEqual(usage.chunks, 2)
        XCTAssertEqual(usage.audioSeconds, 8)
        XCTAssertEqual(try XCTUnwrap(usage.realtimeFactor), 4, accuracy: 0.00001)
        XCTAssertEqual(usage.lastDSPSeconds, 1.5)
        XCTAssertEqual(usage.lastAcceptedAt, accepted)
    }
}
