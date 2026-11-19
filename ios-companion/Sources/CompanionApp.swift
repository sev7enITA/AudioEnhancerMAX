import SwiftUI
import UniformTypeIdentifiers

private let canvas=Color(red:0.03,green:0.04,blue:0.05)
private let violet=Color(red:0.65,green:0.57,blue:1)
private let cyan=Color(red:0.3,green:0.85,blue:0.91)
private let amber=Color(red:1,green:0.74,blue:0.40)

@main struct CompanionApp:App {
    @StateObject private var model=CompanionModel()
    @Environment(\.scenePhase) private var phase
    var body:some Scene {
        WindowGroup {
            CompanionView().environmentObject(model).preferredColorScheme(.dark).tint(violet)
                .onChange(of:phase){_,next in if next != .active{model.stopWorker();model.stopPlayback();model.suspendPresence()}}
        }
    }
}
struct CompanionView:View {
    @EnvironmentObject var model:CompanionModel
    @Environment(\.scenePhase) private var phase
    @State private var tab=0
    @State private var importing=false
    @State private var importBrief=false
    @State private var pairing=""
    @State private var scanning=false
    @State private var nearbyMode:NearbyMacSheet.Mode?
    @State private var briefURL:URL?
    @State private var scrubTime=0.0
    @State private var scrubbing=false
    var body:some View {
        TabView(selection:$tab) {
            NavigationStack{editor}
                .fileImporter(isPresented:$importing,allowedContentTypes:model.importFilter.contentTypes) { result in
                    switch result {
                    case .success(let url): Task{await model.importAudio(url)}
                    case .failure(let error): model.error=error.localizedDescription
                    }
                }.tabItem{Label("Studio",systemImage:"waveform")}.tag(0)
            NavigationStack{mac}.tabItem{Label("Connection",systemImage:"desktopcomputer")}.tag(1)
            NavigationStack{brief}
                .fileImporter(isPresented:$importBrief,allowedContentTypes:[.json],onCompletion:openBrief)
                .tabItem{Label("Music brief",systemImage:"text.alignleft")}.tag(3)
        }
        .task(id:phase) {
            while phase == .active && !Task.isCancelled {
                await model.refreshConnection()
                do {try await Task.sleep(for:.seconds(5))} catch {break}
            }
        }
        .sheet(isPresented:$scanning) {
            PairingScannerSheet { raw in
                scanning=false
                guard (try? Pairing.parse(raw)) != nil else {
                    model.error="This is not an AudioEnhancerMAX pairing QR code. Show a new code in the Mac app's Edge Cluster."
                    return
                }
                pairing=""
                Task { await model.connect(raw) }
            }
        }
        .sheet(item:$nearbyMode) { NearbyMacSheet(mode:$0) }
        .alert("AudioEnhancer",isPresented:Binding(get:{model.error != nil},set:{if !$0{model.error=nil}})) {Button("OK"){model.error=nil}} message:{Text(model.error ?? "")}
        .onChange(of:model.music){_,_ in briefURL=nil}
    }
    private func openBrief(_ result:Result<URL,Error>) {
        do {
            let url=try result.get()
            let access=url.startAccessingSecurityScopedResource()
            defer{if access{url.stopAccessingSecurityScopedResource()}}
            guard (try url.resourceValues(forKeys:[.fileSizeKey]).fileSize ?? Int.max)<65536 else{throw CompanionError.message("Brief JSON is too large.")}
            model.music=try JSONDecoder().decode(MusicDraft.self,from:Data(contentsOf:url))
        } catch{model.error=error.localizedDescription}
    }
    private func title(_ eyebrow:String,_ heading:String,_ text:String)->some View {
        VStack(alignment:.leading,spacing:10){Text(eyebrow.uppercased()).font(.caption.weight(.semibold)).tracking(2).foregroundStyle(cyan)
            Text(heading).font(.largeTitle.bold());Text(text).font(.subheadline).foregroundStyle(.secondary)}.frame(maxWidth:.infinity,alignment:.leading).padding(.vertical,12)
    }
    private var editor:some View {
        ScrollView {
            VStack(alignment:.leading,spacing:24) {
                if model.source==nil {Text("Open a recording").font(.largeTitle.bold())}
                Picker("Import format",selection:$model.importFilter) {
                    ForEach(MediaImportPolicy.Filter.allCases){format in Text(format.label).tag(format)}
                }.pickerStyle(.menu).disabled(model.busy)
                Button{importing=true}label:{Label(model.source==nil ? "Import recording or video" : "Import another file",systemImage:"square.and.arrow.down").frame(maxWidth:.infinity,minHeight:36)}.buttonStyle(.borderedProminent).foregroundStyle(canvas).disabled(model.busy)
                if let wave=model.source {
                    VStack(alignment:.leading,spacing:12){Text(model.name).font(.title2.bold()).lineLimit(2)
                        Text(String(format:"%.2f s · %d Hz · %d channels",wave.duration,wave.rate,wave.channels) + " · source " + model.sourceRevision).font(.caption.monospacedDigit()).foregroundStyle(cyan)
                        SignalOverview(peaks:model.waveformPeaks,duration:wave.duration,playhead:model.playhead,comparison:model.comparison)
                            .frame(height:100).accessibilityLabel("Original waveform, \(wave.duration.formatted()) seconds")}
                    reviewPlayback
                    GroupBox("Clean up") {
                        VStack(alignment:.leading,spacing:14){
                            Toggle("Voice EQ",isOn:$model.voice)
                            DisclosureGroup("Range and levels") {
                                HStack{Text("From");TextField("Start seconds",value:$model.start,format:.number).keyboardType(.decimalPad);Text("to");TextField("End seconds",value:$model.end,format:.number).keyboardType(.decimalPad);Text("s")}
                                Text("Gain \(model.gain.formatted(.number.precision(.fractionLength(1)))) dB").font(.subheadline)
                                Slider(value:$model.gain,in:-24...12,step:0.5).accessibilityLabel("Gain in decibels")
                                Toggle("Normalize peak to −1 dBFS",isOn:$model.normalize)
                                if !model.importAnalysis.isEmpty{Text(model.importAnalysis).font(.caption).textSelection(.enabled)}
                            }
                        }.padding(.top,8)
                    }.disabled(model.busy)
                    Button{Task{await model.edit()}}label:{Label(model.busy ? "Working…":"Improve on this device",systemImage:"slider.horizontal.3").frame(maxWidth:.infinity,minHeight:36)}.buttonStyle(.borderedProminent).foregroundStyle(canvas).disabled(model.busy)
                    reviewExports
                    Button{tab=1}label:{Label(model.connected ? "Send to \(model.macName)" : "Connect a Mac",systemImage:"desktopcomputer")}.buttonStyle(.bordered).disabled(model.busy)
                } else {
                    Text("Edit locally. Files are filtered by the chosen format. Some providers show disabled files.").foregroundStyle(.secondary)
                }
                if model.busy{ProgressView("Working…")}
                Text("Companion \(Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "?") · build \(Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "?")").font(.caption.monospaced()).foregroundStyle(.secondary)
            }.padding(20)
        }.background(canvas).navigationTitle("Studio").navigationBarTitleDisplayMode(.inline)
    }
    private var reviewPlayback:some View {
        GroupBox("Listen") {
            VStack(alignment:.leading,spacing:14){
                if model.comparison != nil || model.resultURL==nil {
                    let first=model.comparison?.sourceStart ?? 0
                    let last=model.comparison.map{$0.sourceStart+$0.duration} ?? model.source?.duration ?? 0.01
                    Slider(value:Binding(
                        get:{max(first,min(last,scrubbing ? scrubTime : model.playhead))},
                        set:{scrubTime=$0;if !scrubbing{model.seekPlayback($0)}}
                    ),in:first...last,onEditingChanged:{ editing in
                        if editing{scrubTime=max(first,min(last,model.playhead))}
                        else{model.seekPlayback(scrubTime)}
                        scrubbing=editing
                    }).accessibilityLabel("Playback position in the original recording")
                }
                ViewThatFits(in:.horizontal) {
                    HStack{playbackControls}
                    VStack(alignment:.leading){playbackControls}
                }
                Text("\(model.playhead.formatted(.number.precision(.fractionLength(1)))) s · \(model.playbackState)").font(.caption).accessibilityAddTraits(.updatesFrequently)
                if model.comparison != nil{Toggle("Match listening levels",isOn:$model.matchListeningLevels)}
                else if model.resultURL != nil{Text("Independent playback for this saved result.").font(.caption)}
            }.frame(maxWidth:.infinity,alignment:.leading).padding(.top,8)
        }
    }
    @ViewBuilder private var playbackControls:some View {
        Button("A · Original"){model.play(model.originalURL)}.buttonStyle(.bordered)
                    Button("B · Result"){model.play(model.resultURL)}.buttonStyle(.bordered).disabled(model.resultURL==nil)
        Button{model.stopPlayback()}label:{Image(systemName:"stop.fill")}.accessibilityLabel("Stop playback").disabled(model.playbackState=="Stopped")
    }
    private var reviewExports:some View {
        VStack(alignment:.leading,spacing:12) {
            if let url=model.resultURL {
                Text("Result · \(model.resultRevision)").font(.caption.monospaced())
                ShareLink(item:url){Label("Export WAV",systemImage:"square.and.arrow.up")}.buttonStyle(.borderedProminent).foregroundStyle(canvas).disabled(model.busy)
            }
                if model.videoSourceURL != nil {
                    Text("Video audio extracted. To export a synchronized video copy, improve the full duration without trimming. Only the audio is replaced; other auxiliary tracks are not exported.").font(.caption)
                    Button("Prepare MP4 with improved audio"){Task{await model.exportVideo()}}.disabled(model.resultURL==nil || model.busy)
                    if let url=model.videoResultURL{ShareLink(item:url){Label("Export MP4 copy",systemImage:"video")}}
                }
                if let url=model.reportURL{ShareLink(item:url){Label("Export Mac report",systemImage:"doc.text")}}
        }.frame(maxWidth:.infinity,alignment:.leading)
    }
    private var mac:some View {
        Form {
            Section{title("Encrypted connection","Your Mac connection",model.paired ? "Your connection and processing mode at a glance." : "Keep both devices on the same Wi-Fi or hotspot. Find your Mac, let it find this device, or scan its pairing QR code.")}
            if model.paired {
                Section(model.connected ? "Connected · encrypted" : "Saved Mac · checking / offline") {
                    Text(model.macName).font(.title2.bold())
                    Text(model.macEndpoint).font(.callout.monospaced())
                    Text(model.workerRunning ? "Mode: Audio transfer + help Mac with Voice EQ" : "Mode: Audio transfer · processing contribution off")
                    Text(model.latencyMs.map{"Last round trip: \($0) ms (not Wi-Fi signal strength)"} ?? "No recent response. Keep the Mac session and this app open.").font(.caption)
                }
            }
            Section("Connection") {
                if !model.paired {
                Button { nearbyMode = .findMac } label: {
                    Label("Find your Mac",systemImage:"wifi").frame(maxWidth:.infinity,minHeight:36)
                }.buttonStyle(.borderedProminent).disabled(model.busy).accessibilityIdentifier("find-nearby-mac")
                Button { nearbyMode = .discoverable } label: {
                    Label("Make this device discoverable",systemImage:"antenna.radiowaves.left.and.right").frame(maxWidth:.infinity,minHeight:36)
                }.buttonStyle(.bordered).disabled(model.busy).accessibilityIdentifier("make-phone-discoverable")
                Button { scanning=true } label: {
                    Label("Scan QR code",systemImage:"qrcode.viewfinder").frame(maxWidth:.infinity,minHeight:36)
                }.buttonStyle(.bordered).disabled(model.busy).accessibilityIdentifier("scan-pairing-qr")
                DisclosureGroup("Manual pairing alternative") {
                    SecureField("Private pairing code",text:$pairing).textInputAutocapitalization(.never).autocorrectionDisabled()
                    Button("Connect"){Task{await model.connect(pairing);if model.macState.hasPrefix("Connected"){pairing=""}}}.disabled(pairing.isEmpty || model.busy)
                }
                }
                if model.busy {Text(model.macState).foregroundStyle(cyan).accessibilityIdentifier("mac-state")}
                if model.paired{Button("Reconnect"){Task{await model.reconnect()}}.disabled(model.busy);Button("Disconnect / change Mac",role:.destructive){model.disconnect()}.disabled(model.busy)}
            }
            Section("Device assessment") {
                Text(model.assessmentText).font(.callout)
                Button("Run local assessment again"){Task{await model.assessDevice()}}.disabled(model.busy || model.workerRunning)
                Toggle("Help Mac process audio",isOn:Binding(get:{model.workerRunning},set:{if $0{model.startWorker()}else{model.stopWorker()}})).disabled(model.busy || (!model.connected && !model.workerRunning))
                Text(model.workerRunning ? "Voice EQ active · \(model.completedChunks) chunks completed · \(model.workerState)" : "Optional. Uses this same connection with no second pairing.")
                Text("Voice EQ only. Keep the app open. Backgrounding, heat, local editing or sending audio stops the contribution. Enable trusted-LAN processing on the Mac to use it. No AI models are delegated to this device.").font(.caption)
            }
            Section("Process on Mac") {
                Text(model.name)
                Toggle("Send current result",isOn:$model.sendResult).disabled(model.resultURL==nil || model.busy)
                if model.source != nil {Text(model.transferSelection).font(.caption)}
                Picker("Profile",selection:$model.remoteProfile){Text("Voice EQ + level").tag("voice");Text("Level only").tag("level")}
                Button(model.connected ? "Send to \(model.macName)" : "Send to Mac"){Task{await model.processOnMac()}}.disabled(!model.connected || model.originalURL==nil || model.busy || model.hasPendingJob)
                if model.hasPendingJob {Button("Recover job"){Task{await model.recover()}}.disabled(!model.connected || model.busy)}
                Text("This sends the selected audio over the encrypted local connection. The Mac result is checked against its SHA-256. Keep the Mac app and session open.").font(.caption)
                if model.busy{ProgressView(model.macState)}
                else {Text(model.macState).foregroundStyle(cyan)}
            }
            if model.resultURL != nil{Section{reviewExports}}
        }.navigationTitle("Connection")
    }
    private var brief:some View {
        Form {
            Section{title("Local · text only","Shape the music.","Build a music brief without a model or network. Your draft saves automatically; this does not generate audio.")}
            Section("Directions") {
                Menu("Choose a preset") {
                    ForEach(["Podcast intro","Narration bed","Documentary arc","Calm focus","Energetic opener","Acoustic story"],id:\.self){preset in Button(preset){model.music.style=preset;model.music.instruments=preset=="Acoustic story" ? "Acoustic guitar, piano":"Piano, strings, gentle percussion"}}
                }
                TextField("Describe the music",text:$model.music.description,axis:.vertical).lineLimit(3...6)
                TextField("Style",text:$model.music.style)
                TextField("Instruments",text:$model.music.instruments)
                TextField("Avoid",text:$model.music.exclusions)
                TextField("Vocals",text:$model.music.vocals)
                HStack{TextField("Seconds",text:$model.music.duration).keyboardType(.numberPad);Text("seconds");TextField("BPM",text:$model.music.bpm).keyboardType(.numberPad);Text("BPM")}
                TextField("Arrangement",text:$model.music.arrangement,axis:.vertical)
                TextField("Separate lyrics",text:$model.music.lyrics,axis:.vertical)
                Button("Build brief"){do{try model.music.build()}catch{model.error=error.localizedDescription}}
            }
            Section("Editable prompt") {
                TextEditor(text:$model.music.prompt).frame(minHeight:180)
                if !model.music.canExport{Text("Build again after changing directions. Lyrics stay separate.").font(.caption).foregroundStyle(.secondary)}
                ShareLink(item:model.music.prompt){Label("Share prompt",systemImage:"square.and.arrow.up")}.disabled(!model.music.canExport)
                Button("Prepare JSON export"){do{briefURL=try model.briefExport()}catch{model.error=error.localizedDescription}}.disabled(!model.music.canExport)
                if let briefURL{ShareLink(item:briefURL){Label("Share JSON",systemImage:"doc")}}
                Button("Import saved JSON"){importBrief=true}
            }
        }.navigationTitle("Music brief")
    }
}
private struct SignalOverview:View {
    let peaks:[Float]
    let duration:Double
    let playhead:Double
    let comparison:AudioComparison?
    var body:some View {
        Canvas{context,size in
            if let comparison {
                let from=CGFloat(comparison.sourceStart/duration)*size.width
                let width=CGFloat(comparison.duration/duration)*size.width
                context.fill(Path(CGRect(x:from,y:0,width:width,height:size.height)),with:.color(amber.opacity(0.13)))
            }
            var path=Path()
            for i in peaks.indices {
                let x=CGFloat(i)*size.width/CGFloat(peaks.count),height=CGFloat(peaks[i])*size.height/2
                path.move(to:CGPoint(x:x,y:size.height/2-height));path.addLine(to:CGPoint(x:x,y:size.height/2+height))
            }
            context.stroke(path,with:.color(cyan),lineWidth:2)
            let play=CGFloat(max(0,min(1,playhead/duration)))*size.width
            var playheadPath=Path()
            playheadPath.move(to:CGPoint(x:play,y:0))
            playheadPath.addLine(to:CGPoint(x:play,y:size.height))
            context.stroke(playheadPath,with:.color(amber),lineWidth:2)
        }
    }
}
