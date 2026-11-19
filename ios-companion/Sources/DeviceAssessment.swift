import Foundation
import UIKit

@MainActor enum DeviceAssessment {
    static var measuredMs:Double?
    static var measuredAt:String?
    static var roundTripMs:Int?
    static func measure() async throws {
        let ms=try await Task.detached(priority:.utility) {
            let wave=try Wave(samples:(0..<96000).map{Float(0.2*sin(2 * Double.pi * 440 * Double($0)/48000))},rate:48000,channels:1)
            _ = try wave.autoEQ()
            var values=[Double]()
            for _ in 0..<3 {let begin=ProcessInfo.processInfo.systemUptime;let result=try wave.autoEQ();guard result.samples.count==96000 else{throw CompanionError.message("Incomplete assessment")};values.append((ProcessInfo.processInfo.systemUptime-begin)*1000)}
            return values.sorted()[1]
        }.value
        measuredMs=ms;measuredAt=ISO8601DateFormatter().string(from:Date())
    }
    static func snapshot()->[String:Any] {
        UIDevice.current.isBatteryMonitoringEnabled=true
        var info=utsname();uname(&info)
        let model=withUnsafeBytes(of:&info.machine){String(bytes:$0.prefix(while:{$0 != 0}),encoding:.utf8) ?? UIDevice.current.model}
        let process=ProcessInfo.processInfo
        let thermal:String
        switch process.thermalState {case .nominal:thermal="nominal";case .fair:thermal="fair";case .serious:thermal="serious";case .critical:thermal="critical";@unknown default:thermal="unavailable"}
        var value:[String:Any]=["schema":1,"model":model,"os":"iOS \(UIDevice.current.systemVersion)","ram_bytes":process.physicalMemory,"thermal":thermal,"charging":UIDevice.current.batteryState == .charging || UIDevice.current.batteryState == .full]
        if UIDevice.current.batteryLevel>=0{value["battery_percent"]=Int((UIDevice.current.batteryLevel*100).rounded())}
        if let ms=measuredMs{value["voice_eq_ms"]=ms;value["benchmark"]="voice-eq-2s-48k-mono-v1";value["benchmark_at"]=measuredAt}
        if let ms=roundTripMs{value["round_trip_ms"]=ms}
        return value
    }
    static func header()->String {((try? JSONSerialization.data(withJSONObject:snapshot())) ?? Data()).base64EncodedString()}
    static func summary()->String {
        let a=snapshot()
        let test=measuredMs.map{String(format:"Voice EQ: %.1f ms for 2 s mono / 48 kHz (median of 3).",$0)+($0<2000 ? " Suitable for foreground Voice EQ." : " Prefer Mac processing for this workload.")} ?? "Voice EQ has not been measured yet."
        let battery=(a["battery_percent"] as? Int).map{"\($0)%"} ?? "unavailable"
        return "\(a["model"] ?? "iOS device") · \(a["os"] ?? "iOS")\n\(ProcessInfo.processInfo.activeProcessorCount) logical cores · \(String(format:"%.1f",Double(ProcessInfo.processInfo.physicalMemory)/1073741824)) GiB RAM\nBattery: \(battery) · Thermal state: \(a["thermal"] ?? "unavailable")\n\(test)\nLocal DSP only. Network overhead excluded; no AI-model capability is inferred."
    }
}
