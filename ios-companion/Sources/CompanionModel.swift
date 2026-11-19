import Foundation
import SwiftUI
import AVFoundation
import CryptoKit

private struct ResultReceipt: Codable {
    let sourceSha: String
    let resultSha: String
    let comparison: AudioComparison?
    let reportSha: String?
}

@MainActor final class CompanionModel: ObservableObject {
    @Published var assessmentText=DeviceAssessment.summary()
    @Published var importAnalysis=UserDefaults.standard.string(forKey:"importAnalysis") ?? ""
    func assessDevice() async {
        guard !busy,!workerRunning else{return}
        busy=true;defer{busy=false}
        do{try await DeviceAssessment.measure();assessmentText=DeviceAssessment.summary();if let api=client{try? await checkConnection(api)}}catch{self.error=error.localizedDescription}
    }
    @Published var importFilter=MediaImportPolicy.Filter(rawValue:UserDefaults.standard.string(forKey:"importFilter") ?? "all") ?? .all {
        didSet{UserDefaults.standard.set(importFilter.rawValue,forKey:"importFilter")}
    }
    @Published var waveformPeaks:[Float]=[]
    @Published var source:Wave?
    @Published private(set) var videoSourceURL:URL?
    @Published private(set) var videoResultURL:URL?
    @Published var originalURL:URL?
    @Published var resultURL:URL?
    @Published private(set) var reportURL:URL?
    @Published var name="No audio imported"
    @Published var busy=false
    @Published var error:String?
    @Published var connected=false
    @Published var macName="Saved Mac"
    @Published var macEndpoint=""
    @Published var latencyMs:Int?
    func suspendPresence(){connected=false;latencyMs=nil}
    private func checkConnection(_ api:CompanionClient,acceptNew:Bool=false) async throws {
        let began=Date()
        let status=try await api.json("/v1/status")
        try Task.checkCancellation()
        guard acceptNew || client === api else{return}
        latencyMs=Int(Date().timeIntervalSince(began)*1000)
        DeviceAssessment.roundTripMs=latencyMs;assessmentText=DeviceAssessment.summary()
        macName=status["mac_name"] as? String ?? "AudioEnhancerMAX Mac"
        macEndpoint=api.pairing.endpoint;connected=true
    }
    func refreshConnection() async {
        guard let api=client,!busy else{return}
        do {try await checkConnection(api)} catch {connected=false;latencyMs=nil}
    }
    @Published var macState="Not connected"
    @Published var workerState="Stopped"
    @Published var workerRunning=false
    @Published var playbackState="Stopped"
    @Published private(set) var playhead=0.0
    @Published private(set) var comparison:AudioComparison?
    @Published var matchListeningLevels=true { didSet { applyListeningLevel() } }
    @Published private(set) var sourceRevision=""
    @Published private(set) var resultRevision=""
    @Published private(set) var hasPendingJob=UserDefaults.standard.string(forKey:"pendingJob") != nil
    var transferSelection: String {
        sendResult ? "Current result · \(resultRevision)" : "Imported audio · \(sourceRevision)"
    }
    @Published var completedChunks=0
    @Published var start=0.0
    @Published var end=1.0
    @Published var gain=0.0
    @Published var normalize=true
    @Published var voice=false
    @Published var remoteProfile="voice"
    @Published var sendResult=false
    @Published var music=MusicDraft() {didSet {if let data=try? JSONEncoder().encode(music){UserDefaults.standard.set(data,forKey:"musicDraft")}}}
    private var client:CompanionClient?
    private var workerTask:Task<Void,Never>?
    private var stopTask:Task<Void,Never>?
    private var workerEpoch=0
    private var player:AVAudioPlayer?
    private var playbackObserver:PlaybackObserver?
    private var playbackTracking:Task<Void,Never>?
    private var playingOriginal=true
    private var sourceSha=""
    private let folder:URL
    let device:String
    var paired:Bool {client != nil}
    init() {
        let defaults=UserDefaults.standard
        device=defaults.string(forKey:"deviceID") ?? UUID().uuidString
        defaults.set(device,forKey:"deviceID")
        folder=FileManager.default.urls(for:.documentDirectory,in:.userDomainMask)[0]
        if let data=defaults.data(forKey:"musicDraft"),let draft=try? JSONDecoder().decode(MusicDraft.self,from:data){music=draft}
        Task{await assessDevice()}
        if let pairing=PairingStore.load(){client=CompanionClient(pairing,device:device);macEndpoint=pairing.endpoint;macState="Paired · reconnect to check"}
        let original=folder.appendingPathComponent("original.wav")
        if let data=try? Data(contentsOf:original),let wave=try? Wave(data:data){
            source=wave;waveformPeaks=wave.overview();originalURL=original;name=defaults.string(forKey:"audioName") ?? "Saved audio";end=wave.duration
            sourceSha=Self.sha256(data);sourceRevision=String(sourceSha.prefix(8))
        }
        if let videoName=defaults.string(forKey:"videoSource"),videoName.hasPrefix("source-"),!videoName.contains("/"),
           let data=try? Data(contentsOf:original), defaults.string(forKey:"videoWaveHash")==SHA256.hash(data:data).map({String(format:"%02x",$0)}).joined() {
            let url=folder.appendingPathComponent(videoName)
            if FileManager.default.fileExists(atPath:url.path){videoSourceURL=url}
        }
        // Remove only this app's UUID-named abandoned media copies/exports.
        if let files=try? FileManager.default.contentsOfDirectory(at:folder,includingPropertiesForKeys:nil) {
            for file in files where file.pathExtension == "mp4" && file != videoSourceURL {
                for prefix in ["source-","enhanced-"] where file.lastPathComponent.hasPrefix(prefix) {
                    if UUID(uuidString:String(file.deletingPathExtension().lastPathComponent.dropFirst(prefix.count))) != nil {try? FileManager.default.removeItem(at:file)}
                }
            }
        }
        restoreResult(defaults)
    }
    nonisolated private static func sha256(_ data: Data) -> String {
        SHA256.hash(data:data).map{String(format:"%02x",$0)}.joined()
    }
    private func restoreResult(_ defaults:UserDefaults) {
        let receipt=defaults.data(forKey:"resultReceipt").flatMap { try? JSONDecoder().decode(ResultReceipt.self,from:$0) }
        let result:URL
        if let receipt {
            guard Self.validDigest(receipt.resultSha) else { return }
            result=Self.resultFile(receipt.resultSha,in:folder)
        } else {
            guard !defaults.bool(forKey:"versionedWorkspace") else { return }
            result=folder.appendingPathComponent("result.wav")
        }
        guard source != nil, let audio=try? Data(contentsOf:result) else { return }
        let resultSha=Self.sha256(audio)
        if let receipt {
            guard receipt.sourceSha == sourceSha, receipt.resultSha == resultSha else { return }
            comparison=receipt.comparison
            playhead=receipt.comparison?.sourceStart ?? 0
        }
        resultURL=result
        resultRevision=String(resultSha.prefix(8))
        if let receipt, let reportSha=receipt.reportSha, Self.validDigest(reportSha) {
            let metadata=Self.reportFile(reportSha,in:folder)
            if let data=try? Data(contentsOf:metadata), Self.sha256(data)==reportSha { reportURL=metadata }
        } else if receipt==nil {
            let metadata=folder.appendingPathComponent("mac-report.json")
            if let data=try? Data(contentsOf:metadata),
               let report=(try? JSONSerialization.jsonObject(with:data)) as? [String:Any],
               report["sha256"] as? String==resultSha { reportURL=metadata }
        }
    }
    nonisolated private static func validDigest(_ digest:String)->Bool {
        digest.range(of:"^[0-9a-f]{64}$",options:.regularExpression) != nil
    }
    nonisolated private static func resultFile(_ digest:String,in folder:URL)->URL {
        folder.appendingPathComponent("result-\(digest).wav")
    }
    nonisolated private static func reportFile(_ digest:String,in folder:URL)->URL {
        folder.appendingPathComponent("mac-report-\(digest).json")
    }
    private func pruneResultFiles(keeping files:[URL?]) {
        let managed="^(result-[0-9a-f]{64}\\.wav|mac-report-[0-9a-f]{64}\\.json)$"
        let keep=Set(files.compactMap{$0})
        if let entries=try? FileManager.default.contentsOfDirectory(at:folder,includingPropertiesForKeys:nil) {
            for entry in entries where !keep.contains(entry) && entry.lastPathComponent.range(of:managed,options:.regularExpression) != nil {
                try? FileManager.default.removeItem(at:entry)
            }
        }
    }
    private func setResult(digest:String,alignment:AudioComparison?,reportSha:String?=nil) {
        let url=Self.resultFile(digest,in:folder)
        let metadata=reportSha.map { Self.reportFile($0,in:folder) }
        let keep=[resultURL,reportURL,url,metadata]
        stopPlayback()
        let receipt=ResultReceipt(sourceSha:sourceSha,resultSha:digest,comparison:alignment,reportSha:reportSha)
        UserDefaults.standard.set(try? JSONEncoder().encode(receipt),forKey:"resultReceipt")
        resultURL=url
        resultRevision=String(digest.prefix(8))
        comparison=alignment
        playhead=alignment?.sourceStart ?? 0
        reportURL=metadata
        sendResult=true
        invalidateVideoExport()
        pruneResultFiles(keeping:keep)
    }
    private func clearPendingJob() {
        hasPendingJob=false
        let defaults=UserDefaults.standard
        for key in ["pendingJob","pendingSourceSha","pendingSourceStart","pendingWorkspaceSha"] { defaults.removeObject(forKey:key) }
    }
    func importAudio(_ url:URL) async {
        guard !busy else{return};stopWorker();busy=true;defer{busy=false}
        let access=url.startAccessingSecurityScopedResource();defer{if access{url.stopAccessingSecurityScopedResource()}}
        do {
            let storage=folder, filter=importFilter
            let imported=try await Task.detached(priority:.userInitiated){try await MediaImport.read(url,folder:storage,filter:filter)}.value
            let wave=imported.wave, target=folder.appendingPathComponent("original.wav")
            let digest:String
            do {
                digest=try await Task.detached(priority:.userInitiated){
                    let bytes=wave.encoded()
                    try bytes.write(to:target,options:.atomic)
                    return Self.sha256(bytes)
                }.value
            }
            catch {if let video=imported.video{try? FileManager.default.removeItem(at:video)};throw error}
            let previousVideo=videoSourceURL
            videoSourceURL=imported.video;invalidateVideoExport()
            importAnalysis=imported.analysis;UserDefaults.standard.set(importAnalysis,forKey:"importAnalysis")
            let defaults=UserDefaults.standard
            defaults.set(imported.video?.lastPathComponent,forKey:"videoSource")
            defaults.set(imported.video == nil ? nil : digest,forKey:"videoWaveHash")
            if let previousVideo{try? FileManager.default.removeItem(at:previousVideo)}
            resultURL=nil;reportURL=nil
            try? FileManager.default.removeItem(at:folder.appendingPathComponent("result.wav"))
            try? FileManager.default.removeItem(at:folder.appendingPathComponent("mac-report.json"))
            defaults.set(true,forKey:"versionedWorkspace")
            defaults.removeObject(forKey:"resultReceipt")
            clearPendingJob()
            pruneResultFiles(keeping:[])
            source=wave;waveformPeaks=imported.overview;originalURL=target;sendResult=false
            name=url.lastPathComponent;UserDefaults.standard.set(name,forKey:"audioName");start=0;end=wave.duration;gain=0
            stopPlayback()
            sourceSha=digest;sourceRevision=String(digest.prefix(8));resultRevision=""
            comparison=nil;playhead=0
        } catch{self.error=error.localizedDescription}
    }
    func edit() async {
        guard !busy,let source else{return};stopWorker();busy=true;defer{busy=false}
        let s=start,e=end,g=gain,n=normalize,v=voice
        do {
            let folder=self.folder
            let receipt=try await Task.detached(priority:.userInitiated){
                let wave=try source.edited(start:s,end:e,gain:g,normalize:n,voice:v)
                let offset=Double(min(source.frames-1,Int(s*Double(source.rate))))/Double(source.rate)
                let bytes=wave.encoded()
                let digest=Self.sha256(bytes)
                try bytes.write(to:Self.resultFile(digest,in:folder),options:.atomic)
                return (digest,AudioComparison.match(source:source,result:wave,sourceStart:offset))
            }.value
            try? FileManager.default.removeItem(at:folder.appendingPathComponent("mac-report.json"))
            setResult(digest:receipt.0,alignment:receipt.1)
        }catch{self.error=error.localizedDescription}
    }
    private func invalidateVideoExport(){
        if let videoResultURL{try? FileManager.default.removeItem(at:videoResultURL)}
        videoResultURL=nil
    }
    func exportVideo() async {
        guard !busy,let video=videoSourceURL,let result=resultURL,let source else{return}
        stopWorker();stopPlayback();busy=true;defer{busy=false}
        let output=folder.appendingPathComponent("enhanced-\(UUID().uuidString).mp4")
        do {
            try await Task.detached(priority:.userInitiated){try await MediaImport.replaceAudio(video:video,result:result,source:source,output:output)}.value
            invalidateVideoExport();videoResultURL=output
        }catch{try? FileManager.default.removeItem(at:output);self.error=error.localizedDescription}
    }
    private var playingOffset:Double { playingOriginal ? 0 : comparison?.sourceStart ?? 0 }
    private func applyListeningLevel() {
        player?.volume = matchListeningLevels ? (playingOriginal ? comparison?.originalGain : comparison?.resultGain) ?? 1 : 1
    }
    func seekPlayback(_ time:Double) {
        playhead=time
        if let player { player.currentTime=max(0,min(player.duration-0.001,time-playingOffset)) }
    }
    func play(_ url:URL?) {
        guard let url else{return}
        let original=url==originalURL
        let differentTrack=original != playingOriginal
        stopPlayback()
        if differentTrack {
            if let comparison {
                if !comparison.contains(playhead) { playhead=comparison.sourceStart }
            } else { playhead=0 }
        }
        playingOriginal=original
        do {
            try AVAudioSession.sharedInstance().setCategory(.playback);try AVAudioSession.sharedInstance().setActive(true)
            let next=try AVAudioPlayer(contentsOf:url)
            player=next
            playbackObserver=PlaybackObserver{[weak self,weak next] in
                guard let self,let next,self.player===next else{return}
                self.stopPlayback()
                self.playhead=self.comparison?.sourceStart ?? 0
            }
            next.delegate=playbackObserver
            let desired=max(0,playhead-playingOffset)
            next.currentTime=max(0,min(next.duration-0.001,desired))
            applyListeningLevel()
            guard next.play() else{throw CompanionError.message("This audio could not be played.")}
            playbackState=original ? "A · Original":"B · Result"
            playbackTracking=Task{[weak self,weak next] in
                while !Task.isCancelled, let self, let next, self.player===next {
                    self.playhead=self.playingOffset+next.currentTime
                    if original,let span=self.comparison,self.playhead>=span.sourceStart+span.duration {
                        self.stopPlayback()
                        self.playhead=span.sourceStart
                        break
                    }
                    try? await Task.sleep(for:.milliseconds(120))
                }
            }
        } catch{stopPlayback();self.error=error.localizedDescription;playbackState="Playback error"}
    }
    func stopPlayback(){
        if let player { playhead=playingOffset+player.currentTime;player.stop() }
        playbackTracking?.cancel()
        playbackTracking=nil
        player=nil
        playbackObserver=nil
        playbackState="Stopped"
    }
    func connect(_ code:String) async {
        guard !busy else { return }
        do { await connect(try Pairing.parse(code)) }
        catch { self.error = error.localizedDescription; macState = "Connection failed" }
    }

    @discardableResult
    func connect(_ pairing: Pairing) async -> Bool {
        guard !busy else { return false }
        stopWorker()
        busy = true
        defer { busy = false }
        macState = "Connecting…"
        do {
            let approved = try pairing.validated()
            let next = CompanionClient(approved, device: device)
            do {
                try await checkConnection(next, acceptNew: true)
                try PairingStore.save(approved)
            } catch {
                next.invalidate()
                throw error
            }
            clearPendingJob()
            client?.invalidate()
            client = next
            macState = "Connected · encrypted"
            return true
        } catch {
            connected = false
            macState = "Connection failed"
            if !Task.isCancelled { self.error = error.localizedDescription }
            return false
        }
    }
    func reconnect() async {
        guard let client,!busy else{return};busy=true;defer{busy=false};macState="Connecting…"
        do{try await checkConnection(client);macState="Connected · encrypted"}catch{connected=false;macState="Mac unavailable";self.error=error.localizedDescription}
    }
    func disconnect(){stopWorker();connected=false;macEndpoint="";latencyMs=nil;client?.invalidate();client=nil;PairingStore.clear();clearPendingJob();macState="Not connected"}
    func processOnMac() async {
        guard !busy,let client,let selectedURL=(sendResult ? resultURL:originalURL) else{return};stopWorker();busy=true;defer{busy=false}
        let profile=remoteProfile
        do {
            guard (try selectedURL.resourceValues(forKeys:[.fileSizeKey]).fileSize ?? Int.max)<=20*1024*1024 else{throw CompanionError.message("This edit exceeds the Mac transfer limit of 20 MiB. Improve a shorter range and send that result; local export supports the full recording.")}
            macState="Sending \(transferSelection) to \(macName)…"
            let (audio,digest)=try await Task.detached(priority:.userInitiated){
                let bytes=try Data(contentsOf:selectedURL)
                return (bytes,Self.sha256(bytes))
            }.value
            let (data,_)=try await client.request("/v1/files",method:"POST",body:audio,extension:"wav")
            guard let imported=try JSONSerialization.jsonObject(with:data) as? [String:Any],let fileID=imported["id"] as? String else{throw CompanionError.message("Mac import failed.")}
            if let reportedHash=imported["sha256"] as? String,reportedHash != digest {
                throw CompanionError.message("Mac upload integrity check failed.")
            }
            macState="Starting the Mac job…"
            let job=try await client.json("/v1/jobs",method:"POST",body:["file_id":fileID,"profile":profile])
            guard let id=job["id"] as? String else{throw CompanionError.message("Missing job identity.")}
            let defaults=UserDefaults.standard
            defaults.set(id,forKey:"pendingJob")
            defaults.set(digest,forKey:"pendingSourceSha")
            defaults.set(sendResult ? comparison?.sourceStart : 0.0,forKey:"pendingSourceStart")
            defaults.set(sourceSha,forKey:"pendingWorkspaceSha")
            hasPendingJob=true
            try await retrieve(id,client:client)
        }catch{macState=hasPendingJob ? "Job interrupted · use Recover job":"Send failed · retry";self.error=error.localizedDescription}
    }
    func recover() async {
        guard !busy,let client,let id=UserDefaults.standard.string(forKey:"pendingJob") else{error="No pending job in this app.";return}
        busy=true;defer{busy=false}
        do{try await retrieve(id,client:client)}catch{macState="Recovery failed";self.error=error.localizedDescription}
    }
    private func retrieve(_ id:String,client:CompanionClient) async throws {
        let defaults=UserDefaults.standard
        if let expected=defaults.string(forKey:"pendingWorkspaceSha"),expected != sourceSha {
            clearPendingJob()
            throw CompanionError.message("This Mac job belongs to a different recording.")
        }
        for _ in 0..<90 {
            try Task.checkCancellation()
            let state=try await client.json("/v1/jobs/\(id)")
            if state["status"] as? String=="failed" {
                clearPendingJob();macState="Mac processing failed"
                throw CompanionError.message(state["message"] as? String ?? "Mac processing failed.")
            }
            if state["status"] as? String=="completed" {
                macState="Downloading and verifying the Mac result…"
                let (audio,_)=try await client.request("/v1/jobs/\(id)/audio")
                let hash=await Task.detached(priority:.userInitiated){Self.sha256(audio)}.value
                guard hash==state["sha256"] as? String else{throw CompanionError.message("Result integrity check failed.")}
                let pendingSha=defaults.string(forKey:"pendingSourceSha")
                if let pendingSha,let reported=state["source_sha256"] as? String,reported != pendingSha {
                    throw CompanionError.message("Mac result refers to a different source.")
                }
                let (report,_)=try await client.request("/v1/jobs/\(id)/report")
                guard let metadata=try JSONSerialization.jsonObject(with:report) as? [String:Any], metadata["sha256"] as? String==hash else {throw CompanionError.message("Report integrity check failed.")}
                if let pendingSha,let reported=metadata["source_sha256"] as? String,reported != pendingSha {
                    throw CompanionError.message("Mac report refers to a different source.")
                }
                let folder=self.folder
                let offset=defaults.object(forKey:"pendingSourceStart") as? Double
                let original=source
                let (reportSha,alignment)=try await Task.detached(priority:.userInitiated){
                    let revised=try Wave(data:audio)
                    let matched = original.flatMap { source in
                        offset.flatMap { AudioComparison.match(source:source,result:revised,sourceStart:$0) }
                    }
                    let reportSha=Self.sha256(report)
                    try audio.write(to:Self.resultFile(hash,in:folder),options:.atomic)
                    try report.write(to:Self.reportFile(reportSha,in:folder),options:.atomic)
                    return (reportSha,matched)
                }.value
                setResult(digest:hash,alignment:alignment,reportSha:reportSha)
                macState="Completed · revision \(resultRevision) · SHA-256 verified"
                clearPendingJob()
                return
            }
            macState="Processing on Mac…";try await Task.sleep(for:.seconds(2))
        }
        throw CompanionError.message("Still working on the Mac. Use Recover job later.")
    }
    func startWorker(){
        guard !busy,!workerRunning,let client else{return}
        workerEpoch+=1;let epoch=workerEpoch;let previousStop=stopTask
        workerRunning=true;workerState="Waiting for Mac";UIApplication.shared.isIdleTimerDisabled=true
        workerTask=Task {
            await previousStop?.value
            var stoppedState="Stopped"
            do {
                try Task.checkCancellation()
                while !Task.isCancelled {
                    guard ProcessInfo.processInfo.thermalState != .serious,ProcessInfo.processInfo.thermalState != .critical else{throw CompanionError.message("Worker paused: device is warm.")}
                    let (data,response)=try await client.request("/v1/worker/next")
                    try Task.checkCancellation()
                    if let id=response.value(forHTTPHeaderField:"X-Task-ID") {
                        guard response.value(forHTTPHeaderField:"X-Filter")=="auto_eq",data.count<=2*1024*1024 else{throw CompanionError.message("Unsupported worker task.")}
                        workerState="Processing · Voice EQ"
                        let result=try await Task.detached(priority:.utility){try Wave(data:data).autoEQ().encoded()}.value
                        try Task.checkCancellation()
                        _ = try await client.request("/v1/worker/result/\(id)",method:"POST",body:result)
                        try Task.checkCancellation();completedChunks+=1
                    }
                    workerState="Waiting for Mac";try await Task.sleep(for:.seconds(2))
                }
            }catch{if !Task.isCancelled{self.error=error.localizedDescription;stoppedState="Error · reconnect or retry"}}
            if epoch==workerEpoch {stopWorker(state:stoppedState)}
        }
    }
    func stopWorker(state:String="Stopped"){
        let wasRunning=workerRunning
        workerEpoch+=1
        workerTask?.cancel();workerTask=nil;workerRunning=false;workerState=state;UIApplication.shared.isIdleTimerDisabled=false
        if wasRunning,let client{stopTask=Task{_ = try? await client.request("/v1/worker/stop",method:"POST",body:Data())}}
    }
    func briefExport() throws -> URL {
        guard music.canExport else{throw CompanionError.message("Rebuild the brief after changing its fields.")}
        let data=try JSONEncoder().encode(music)
        guard data.count<=65536 else{throw CompanionError.message("Shorten the brief before exporting.")}
        let url=folder.appendingPathComponent("music-brief.json");try data.write(to:url,options:.atomic);return url
    }

}

private final class PlaybackObserver:NSObject,AVAudioPlayerDelegate {
    let finished:@MainActor ()->Void
    init(_ finished:@escaping @MainActor ()->Void){self.finished=finished}
    func audioPlayerDidFinishPlaying(_ player:AVAudioPlayer,successfully flag:Bool){Task{@MainActor in finished()}}
}
