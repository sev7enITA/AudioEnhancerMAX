import Foundation

struct StudioEdit: Codable, Equatable, Sendable {
    enum RangeAction: String, CaseIterable, Codable, Identifiable, Sendable {
        case keep, silence

        var id: Self { self }
        var title: String { self == .keep ? "Keep selection" : "Silence selection" }
    }

    var start = 0.0
    var end = 0.0
    var gain = 0.0
    var normalize = false
    var voice = false
    var fadeIn = 0.0
    var fadeOut = 0.0
    var rangeAction = RangeAction.keep
}

extension Wave {
    func render(_ edit: StudioEdit) throws -> (wave: Wave, sourceStart: Double) {
        guard edit.start.isFinite, edit.end.isFinite, edit.gain.isFinite,
              edit.start >= 0, edit.end <= duration + 0.000001, edit.end > edit.start,
              (-24...12).contains(edit.gain), (0...5).contains(edit.fadeIn),
              (0...5).contains(edit.fadeOut) else {
            throw CompanionError.message("Choose a valid selection, fade and gain.")
        }
        let firstFrame = min(frames - 1, Int((edit.start * Double(rate)).rounded()))
        let lastFrame = min(frames, Int((edit.end * Double(rate)).rounded()))
        guard lastFrame > firstFrame else {
            throw CompanionError.message("The selected range is empty.")
        }

        let sourceStart = edit.rangeAction == .keep ? Double(firstFrame) / Double(rate) : 0
        var output = edit.rangeAction == .keep
            ? try Wave(samples: Array(samples[firstFrame * channels..<lastFrame * channels]), rate: rate, channels: channels)
            : self
        if edit.voice { output = try output.autoEQ() }
        if edit.rangeAction == .silence {
            let range = firstFrame * channels..<lastFrame * channels
            output.samples.replaceSubrange(range, with: repeatElement(0, count: range.count))
        }
        let gain = Float(pow(10, edit.gain / 20))
        let fadeInFrames = min(output.frames - 1, Int((edit.fadeIn * Double(rate)).rounded()))
        let fadeOutFrames = min(output.frames - 1, Int((edit.fadeOut * Double(rate)).rounded()))
        var peak: Float = 0
        for frame in 0..<output.frames {
            let attack = fadeInFrames == 0 ? 1 : min(1, Float(frame) / Float(fadeInFrames))
            let release = fadeOutFrames == 0 ? 1 : min(1, Float(output.frames - frame - 1) / Float(fadeOutFrames))
            for channel in 0..<channels {
                let index = frame * channels + channel
                output.samples[index] *= gain * attack * release
                peak = max(peak, abs(output.samples[index]))
            }
        }
        guard peak.isFinite else { throw CompanionError.message("Audio level is outside the supported range.") }
        let scale = edit.normalize && peak > 0 ? Float(pow(10, -1.0 / 20)) / peak : 1
        for index in output.samples.indices {
            output.samples[index] = min(1, max(-1, output.samples[index] * scale))
        }
        return (output, sourceStart)
    }
}

struct StudioEditHistory {
    private(set) var current = StudioEdit()
    private var previous: [StudioEdit] = []
    private var next: [StudioEdit] = []

    init(current: StudioEdit = StudioEdit()) { self.current = current }

    var canUndo: Bool { !previous.isEmpty }
    var canRedo: Bool { !next.isEmpty }

    mutating func replace(with edit: StudioEdit) {
        guard edit != current else { return }
        previous.append(current)
        if previous.count > 20 { previous.removeFirst() }
        next.removeAll()
        current = edit
    }

    mutating func undo() {
        guard let edit = previous.popLast() else { return }
        next.append(current)
        current = edit
    }

    mutating func redo() {
        guard let edit = next.popLast() else { return }
        previous.append(current)
        current = edit
    }
}
