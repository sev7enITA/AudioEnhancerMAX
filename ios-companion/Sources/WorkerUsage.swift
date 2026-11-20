import Foundation

struct WorkerUsage {
    private(set) var chunks = 0
    private(set) var audioSeconds = 0.0
    private(set) var dspSeconds = 0.0
    private(set) var lastDSPSeconds: Double?
    private(set) var lastAcceptedAt: Date?

    var realtimeFactor: Double? {
        guard dspSeconds > 0 else { return nil }
        return audioSeconds / dspSeconds
    }

    mutating func record(audioSeconds: Double, dspSeconds: Double, at time: Date = .now) {
        guard audioSeconds.isFinite, dspSeconds.isFinite, audioSeconds > 0, dspSeconds > 0 else { return }
        chunks += 1
        self.audioSeconds += audioSeconds
        self.dspSeconds += dspSeconds
        lastDSPSeconds = dspSeconds
        lastAcceptedAt = time
    }
}
