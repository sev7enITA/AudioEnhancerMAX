import SwiftUI

enum WorkspaceColor {
    static let background = Color(red: 0.035, green: 0.055, blue: 0.08)
    static let surface = Color(red: 0.065, green: 0.096, blue: 0.135)
    static let line = Color.white.opacity(0.13)
    static let mint = Color(red: 0.30, green: 0.94, blue: 0.77)
    static let blue = Color(red: 0.44, green: 0.73, blue: 1)
    static let muted = Color(red: 0.66, green: 0.72, blue: 0.81)
}

extension View {
    func workspaceCard(padding: CGFloat = 16) -> some View {
        self.padding(padding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(WorkspaceColor.surface, in: RoundedRectangle(cornerRadius: 20))
            .overlay { RoundedRectangle(cornerRadius: 20).strokeBorder(WorkspaceColor.line) }
    }
}

struct StudioView: View {
    @EnvironmentObject private var model: CompanionModel
    let openConnection: () -> Void
    @State private var importing = false

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                if let source = model.source {
                    recording(source)
                    edits(source.duration)
                    deliver
                } else {
                    importHero
                }
                ContentCredentialsCard().workspaceCard()
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .frame(maxWidth: 740)
            .frame(maxWidth: .infinity)
        }
        .background(WorkspaceColor.background)
        .navigationTitle("Studio")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if model.source != nil {
                ToolbarItem(placement: .primaryAction) {
                    Menu {
                        Picker("Format", selection: $model.importFilter) { formatOptions }
                        Button("Choose a file", systemImage: "folder") { importing = true }
                    } label: {
                        Label("Import", systemImage: "folder.badge.plus")
                    }.disabled(model.busy)
                }
            }
        }
        .fileImporter(isPresented: $importing, allowedContentTypes: model.importFilter.contentTypes) { result in
            switch result {
            case .success(let url): Task { await model.importAudio(url) }
            case .failure(let error): model.error = error.localizedDescription
            }
        }
    }

    private var formatOptions: some View {
        ForEach(MediaImportPolicy.Filter.allCases) { format in Text(format.label).tag(format) }
    }

    private var importHero: some View {
        VStack(alignment: .leading, spacing: 18) {
            Image("BrandMark").resizable().scaledToFit().frame(width: 62, height: 62).accessibilityHidden(true)
            Text("Your next edit").font(.largeTitle.bold())
            Text("Trim, shape and compare an audio or video recording. Your source stays intact.")
                .foregroundStyle(WorkspaceColor.muted)
            Picker("Import format", selection: $model.importFilter) { formatOptions }
                .pickerStyle(.menu)
                .padding(.vertical, 5)
            Button {
                importing = true
            } label: {
                Label("Open recording", systemImage: "folder")
                    .frame(maxWidth: .infinity, minHeight: 30)
            }
            .buttonStyle(.borderedProminent)
            .foregroundStyle(WorkspaceColor.background)
            .disabled(model.busy)
            if model.busy { ProgressView("Opening…") }
        }
        .workspaceCard(padding: 21)
    }

    private func recording(_ source: Wave) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            VStack(alignment: .leading, spacing: 5) {
                Text(model.name).font(.title3.weight(.semibold)).lineLimit(2)
                Text("\(timecode(source.duration))  ·  \(source.rate.formatted()) Hz  ·  \(source.channels == 2 ? "Stereo" : "Mono")")
                    .font(.caption.monospacedDigit()).foregroundStyle(WorkspaceColor.muted)
            }
            EditableWaveform(peaks: model.waveformPeaks, duration: source.duration,
                             selection: model.studioEdit.start...model.studioEdit.end,
                             minimumSelection: 1 / Double(source.rate), playhead: model.playhead, onSeek: model.seekPlayback,
                             onMoveIn: { model.start = $0 }, onMoveOut: { model.end = $0 })
                .frame(height: 138)
            HStack(spacing: 12) {
                Text(timecode(model.playhead))
                    .font(.system(.title3, design: .monospaced, weight: .semibold))
                    .foregroundStyle(WorkspaceColor.mint)
                    .accessibilityLabel("Playhead, \(model.playhead.formatted(.number.precision(.fractionLength(2)))) seconds")
                Spacer(minLength: 0)
                toggleLoop
                Button(action: model.togglePlayback) {
                    Image(systemName: model.playbackState == "Stopped" || model.playbackState == "Playback error" ? "play.fill" : "pause.fill")
                        .frame(width: 42, height: 42)
                        .background(WorkspaceColor.mint, in: Circle())
                        .foregroundStyle(WorkspaceColor.background)
                }
                .buttonStyle(.plain)
                .accessibilityLabel(model.playbackState == "Stopped" || model.playbackState == "Playback error" ? "Play" : "Pause")
                .disabled(model.busy)
            }
            Picker("Listen to", selection: Binding(get: { model.playbackIsOriginal }, set: { model.selectPlayback(original: $0) })) {
                Text("A · Source").tag(true)
                Text("B · Revision").tag(false).disabled(model.resultURL == nil)
            }
            .pickerStyle(.segmented)
            .disabled(model.busy || model.resultURL == nil)
            if model.comparison != nil {
                Toggle("Match listening levels", isOn: $model.matchListeningLevels)
                    .font(.subheadline)
            } else if model.resultURL != nil {
                Text("This revision plays on a separate timeline.").font(.caption).foregroundStyle(WorkspaceColor.muted)
            }
        }
        .workspaceCard()
    }

    private var toggleLoop: some View {
        Button {
            model.loopSelection.toggle()
        } label: {
            Image(systemName: "repeat")
                .frame(width: 42, height: 42)
                .foregroundStyle(model.loopSelection ? WorkspaceColor.mint : WorkspaceColor.muted)
                .background(model.loopSelection ? WorkspaceColor.mint.opacity(0.14) : .clear, in: Circle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Loop selection")
        .accessibilityAddTraits(model.loopSelection ? .isSelected : [])
        .disabled(!model.canLoopSelection && !model.loopSelection)
    }

    private func edits(_ duration: Double) -> some View {
        VStack(alignment: .leading, spacing: 15) {
            HStack {
                Text("Edit selection").font(.headline)
                Spacer()
                Button(action: model.undoEdit) {
                    Image(systemName: "arrow.uturn.backward").frame(width: 35, height: 35)
                }.disabled(!model.editHistory.canUndo).accessibilityLabel("Undo edit")
                Button(action: model.redoEdit) {
                    Image(systemName: "arrow.uturn.forward").frame(width: 35, height: 35)
                }.disabled(!model.editHistory.canRedo).accessibilityLabel("Redo edit")
            }.buttonStyle(.plain)
            HStack(spacing: 10) {
                editPoint("In", value: Binding(get: { model.start }, set: { model.start = $0 }),
                          onPlayhead: { model.start = model.playhead })
                editPoint("Out", value: Binding(get: { model.end }, set: { model.end = $0 }),
                          onPlayhead: { model.end = model.playhead })
            }
            HStack {
                Text("\(timecode(model.studioEdit.end - model.studioEdit.start)) selected")
                    .font(.caption.monospacedDigit()).foregroundStyle(WorkspaceColor.muted)
                Spacer()
                Button("Select all") { model.changeEdit { $0.start = 0; $0.end = duration } }.font(.caption.weight(.semibold))
            }
            Picker("Selection action", selection: binding(\.rangeAction)) {
                ForEach(StudioEdit.RangeAction.allCases) { action in Text(action.title).tag(action) }
            }
            .pickerStyle(.segmented)
            .accessibilityHint("Keep trims the recording to this range. Silence leaves the timeline in place.")
            Divider()
            Text("Level and fades").font(.headline)
            Toggle("Normalize peak to −1 dBFS", isOn: binding(\.normalize))
            if !model.studioEdit.normalize {
                EditSlider("Gain", value: binding(\.gain), range: -24...12, step: 0.5, unit: "dB")
            }
            EditSlider("Fade in", value: binding(\.fadeIn), range: 0...5, step: 0.05, unit: "s")
            EditSlider("Fade out", value: binding(\.fadeOut), range: 0...5, step: 0.05, unit: "s")
            Toggle("Voice EQ", isOn: binding(\.voice))
            if model.hasUnrenderedEdit {
                Label("Changes ready to render", systemImage: "pencil.circle")
                    .font(.caption.weight(.semibold)).foregroundStyle(WorkspaceColor.mint)
            }
            Button {
                Task { await model.edit() }
            } label: {
                Label("Render revision", systemImage: "slider.horizontal.3")
                    .frame(maxWidth: .infinity, minHeight: 30)
            }
            .buttonStyle(.borderedProminent)
            .foregroundStyle(WorkspaceColor.background)
            if model.busy { ProgressView() }
        }
        .disabled(model.busy)
        .workspaceCard()
    }

    private func binding<Value>(_ key: WritableKeyPath<StudioEdit, Value>) -> Binding<Value> {
        Binding(get: { model.studioEdit[keyPath: key] }, set: { newValue in
            model.changeEdit { $0[keyPath: key] = newValue }
        })
    }

    private func editPoint(_ label: String, value: Binding<Double>, onPlayhead: @escaping () -> Void) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(label).font(.caption.weight(.semibold)).foregroundStyle(WorkspaceColor.muted)
            HStack(spacing: 4) {
                TextField("\(label) seconds", value: value, format: .number.precision(.fractionLength(0...3)))
                    .font(.callout.monospacedDigit()).keyboardType(.numbersAndPunctuation)
                    .accessibilityLabel("\(label) point in seconds")
                Text("s").font(.caption).foregroundStyle(WorkspaceColor.muted)
            }
            Button(action: onPlayhead) {
                Label("Set at playhead", systemImage: "timeline.selection")
                    .font(.caption.weight(.semibold)).lineLimit(1).minimumScaleFactor(0.75)
            }.accessibilityLabel("Set \(label) at playhead")
        }
        .padding(10)
        .background(WorkspaceColor.background, in: RoundedRectangle(cornerRadius: 12))
    }

    private var deliver: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Export and transfer").font(.headline)
            if let url = model.resultURL {
                ShareLink(item: url) {
                    Label("Share WAV revision", systemImage: "square.and.arrow.up")
                }.disabled(model.busy)
                if model.hasUnrenderedEdit {
                    Text("Sharing uses the last rendered revision.")
                        .font(.caption).foregroundStyle(WorkspaceColor.muted)
                }
            }
            Button(action: openConnection) {
                Label(model.connected ? "Send to \(model.macName)" : "Connect a Mac", systemImage: "desktopcomputer")
            }
            if model.videoSourceURL != nil {
                Button("Prepare MP4 with improved audio", systemImage: "video") { Task { await model.exportVideo() } }
                    .disabled(model.resultURL == nil || model.busy)
                if let url = model.videoResultURL { ShareLink(item: url) { Label("Share MP4", systemImage: "square.and.arrow.up") } }
                Text("Video export uses a full-length audio revision. Auxiliary tracks are omitted.")
                    .font(.caption).foregroundStyle(WorkspaceColor.muted)
            }
            if let url = model.reportURL { ShareLink(item: url) { Label("Share Mac report", systemImage: "doc.text") } }
            if !model.importAnalysis.isEmpty {
                DisclosureGroup("Recording details") {
                    Text(model.importAnalysis).font(.caption).textSelection(.enabled)
                }
            }
        }
        .workspaceCard()
    }
}

private struct EditSlider: View {
    let title: String
    @Binding var value: Double
    let range: ClosedRange<Double>
    let step: Double
    let unit: String
    @State private var drag: Double?

    init(_ title: String, value: Binding<Double>, range: ClosedRange<Double>, step: Double, unit: String) {
        self.title = title
        self._value = value
        self.range = range
        self.step = step
        self.unit = unit
    }

    var body: some View {
        VStack(spacing: 1) {
            HStack {
                Text(title).font(.subheadline)
                Spacer()
                Text("\((drag ?? value).formatted(.number.precision(.fractionLength(0...2)))) \(unit)")
                    .font(.caption.monospacedDigit()).foregroundStyle(WorkspaceColor.muted)
            }
            Slider(value: Binding(get: { drag ?? value }, set: { updated in
                if drag != nil { drag = updated } else { value = updated }
            }), in: range, step: step, onEditingChanged: { editing in
                if editing { drag = value }
                else if let drag { value = drag; self.drag = nil }
            })
            .accessibilityLabel(title)
            .accessibilityValue("\((drag ?? value).formatted()) \(unit)")
        }
    }
}

private struct EditableWaveform: View {
    private enum GestureTarget { case cursor, start, end, scroll }

    let peaks: [Float]
    let duration: Double
    let selection: ClosedRange<Double>
    let minimumSelection: Double
    let playhead: Double
    let onSeek: (Double) -> Void
    let onMoveIn: (Double) -> Void
    let onMoveOut: (Double) -> Void
    @State private var target: GestureTarget?
    @State private var gestureTime: Double?

    var body: some View {
        GeometryReader { proxy in
            Canvas { context, size in
                let position: (Double) -> CGFloat = { min(size.width, max(0, $0 / duration * size.width)) }
                let left = position(target == .start ? min(gestureTime ?? selection.lowerBound, selection.upperBound - minimumSelection) : selection.lowerBound)
                let right = position(target == .end ? max(gestureTime ?? selection.upperBound, selection.lowerBound + minimumSelection) : selection.upperBound)
                context.fill(Path(CGRect(x: left, y: 0, width: right - left, height: size.height)),
                             with: .color(WorkspaceColor.mint.opacity(0.10)))

                var grid = Path()
                for mark in 0...8 {
                    let x = CGFloat(mark) * size.width / 8
                    grid.move(to: CGPoint(x: x, y: 0))
                    grid.addLine(to: CGPoint(x: x, y: size.height))
                }
                grid.move(to: CGPoint(x: 0, y: size.height / 2))
                grid.addLine(to: CGPoint(x: size.width, y: size.height / 2))
                context.stroke(grid, with: .color(WorkspaceColor.line), lineWidth: 0.55)

                let step = size.width / CGFloat(max(1, peaks.count))
                var active = Path(), inactive = Path()
                for (index, peak) in peaks.enumerated() {
                    let x = (CGFloat(index) + 0.5) * step
                    let h = max(1, CGFloat(peak) * size.height * 0.44)
                    let from = CGPoint(x: x, y: size.height / 2 - h)
                    let to = CGPoint(x: x, y: size.height / 2 + h)
                    if left <= x && x <= right {
                        active.move(to: from); active.addLine(to: to)
                    } else {
                        inactive.move(to: from); inactive.addLine(to: to)
                    }
                }
                let stroke = StrokeStyle(lineWidth: min(3, max(1, step * 0.59)), lineCap: .round)
                context.stroke(active, with: .color(WorkspaceColor.mint), style: stroke)
                context.stroke(inactive, with: .color(WorkspaceColor.blue.opacity(0.45)), style: stroke)

                for marker in [left, right] {
                    let x = min(size.width - 2, max(1, marker))
                    context.fill(Path(CGRect(x: x, y: 0, width: 2, height: size.height)),
                                 with: .color(WorkspaceColor.mint.opacity(0.66)))
                    context.fill(Path(roundedRect: CGRect(x: min(size.width - 8, max(0, x - 3)), y: 0, width: 8, height: 19), cornerRadius: 3),
                                 with: .color(WorkspaceColor.mint))
                }
                let cursor = min(size.width - 1, position(target == .cursor ? gestureTime ?? playhead : playhead))
                context.fill(Path(CGRect(x: cursor, y: 0, width: 1.5, height: size.height)), with: .color(.white))
            }
            .background(WorkspaceColor.background)
            .clipShape(RoundedRectangle(cornerRadius: 10))
            .contentShape(Rectangle())
            .simultaneousGesture(DragGesture(minimumDistance: 0)
                .onChanged { value in
                    let width = proxy.size.width
                    if target == nil {
                        let horizontal = abs(value.translation.width)
                        let vertical = abs(value.translation.height)
                        if vertical >= 8, vertical > horizontal {
                            target = .scroll
                        } else if horizontal >= 5 {
                            let left = abs(value.startLocation.x - selection.lowerBound / duration * width)
                            let right = abs(value.startLocation.x - selection.upperBound / duration * width)
                            target = min(left, right) <= 16 ? (left <= right ? .start : .end) : .cursor
                        }
                    }
                    gestureTime = time(at: value.location.x, width: width)
                }
                .onEnded { value in
                    let time = time(at: value.location.x, width: proxy.size.width)
                    switch target {
                    case .start: onMoveIn(time)
                    case .end: onMoveOut(time)
                    case .scroll: break
                    default: onSeek(time)
                    }
                    target = nil
                    gestureTime = nil
                })
        }
        .accessibilityLabel("Waveform playhead")
        .accessibilityValue("\(playhead.formatted(.number.precision(.fractionLength(2)))) seconds")
        .accessibilityHint("Swipe up or down to move the playhead, or set the In and Out points below.")
        .accessibilityAdjustableAction { direction in
            switch direction {
            case .increment: onSeek(min(duration, playhead + 0.1))
            case .decrement: onSeek(max(0, playhead - 0.1))
            @unknown default: break
            }
        }
    }

    private func time(at x: CGFloat, width: CGFloat) -> Double { duration * min(1, max(0, x / max(1, width))) }
}

private func timecode(_ time: Double) -> String {
    let millis = Int((max(0, time.isFinite ? time : 0) * 1000).rounded())
    return String(format: "%02d:%02d.%03d", millis / 60_000, (millis / 1000) % 60, millis % 1000)
}
