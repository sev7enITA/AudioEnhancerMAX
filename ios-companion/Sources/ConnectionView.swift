import SwiftUI

struct ConnectionView: View {
    @EnvironmentObject private var model: CompanionModel
    let openStudio: () -> Void
    @State private var pairing = ""
    @State private var scanning = false
    @State private var nearbyMode: NearbyMacSheet.Mode?
    @State private var confirmingForget = false

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                connection
                worker
                transfers
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .frame(maxWidth: 740)
            .frame(maxWidth: .infinity)
        }
        .background(WorkspaceColor.background)
        .navigationTitle("Connection")
        .navigationBarTitleDisplayMode(.inline)
        .sheet(isPresented: $scanning) {
            PairingScannerSheet { raw in
                scanning = false
                guard (try? Pairing.parse(raw)) != nil else {
                    model.error = "Show a new AudioEnhancerMAX pairing QR code on the Mac."
                    return
                }
                pairing = ""
                Task { await model.connect(raw) }
            }
        }
        .sheet(item: $nearbyMode) { NearbyMacSheet(mode: $0) }
        .confirmationDialog("Forget this Mac?", isPresented: $confirmingForget, titleVisibility: .visible) {
            Button("Forget Mac", role: .destructive, action: model.disconnect)
        } message: {
            Text("This phone will need a new pairing to send audio or contribute processing.")
        }
    }

    private var connection: some View {
        VStack(alignment: .leading, spacing: 15) {
            HStack(spacing: 13) {
                device("iphone", name: "This device")
                HStack(spacing: 5) {
                    Circle().fill(linkTint.opacity(0.45)).frame(width: 4, height: 4)
                    Image(systemName: model.connected ? "lock.fill" : "wifi").font(.subheadline)
                    Circle().fill(linkTint.opacity(0.45)).frame(width: 4, height: 4)
                }.foregroundStyle(linkTint).accessibilityHidden(true)
                device("desktopcomputer", name: model.paired ? model.macName : "Mac")
            }
            Divider()
            HStack(spacing: 8) {
                Circle().fill(linkTint).frame(width: 7, height: 7).accessibilityHidden(true)
                Text(model.connected ? "Connected and encrypted" : model.paired ? "Saved Mac · offline" : "Pair with a Mac")
                    .font(.headline)
                Spacer(minLength: 0)
            }
            if model.paired {
                HStack {
                    if let latency = model.latencyMs {
                        Label("\(latency) ms round trip", systemImage: "gauge.with.dots.needle.50percent")
                    } else {
                        Label("No recent response", systemImage: "wifi.slash")
                    }
                    Spacer()
                    if !model.macBuild.isEmpty { Text("Mac \(model.macBuild)") }
                }
                .font(.caption.monospacedDigit())
                .foregroundStyle(WorkspaceColor.muted)
                if !model.connected {
                    Button("Reconnect", systemImage: "arrow.clockwise") { Task { await model.reconnect() } }
                        .buttonStyle(.borderedProminent).disabled(model.busy)
                }
                DisclosureGroup("Manage connection") {
                    VStack(alignment: .leading, spacing: 10) {
                        Text(model.macEndpoint).font(.caption.monospaced()).foregroundStyle(WorkspaceColor.muted)
                        Button("Forget Mac", systemImage: "trash", role: .destructive) { confirmingForget = true }
                            .disabled(model.busy)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.top, 8)
                }
                .font(.subheadline)
            } else {
                Text("Connect both devices to the same Wi-Fi or hotspot. Open Mobile devices and transfers on the Mac.")
                    .font(.subheadline).foregroundStyle(WorkspaceColor.muted)
                Button {
                    nearbyMode = .findMac
                } label: {
                    Label("Find your Mac", systemImage: "wifi")
                        .frame(maxWidth: .infinity, minHeight: 29)
                }.buttonStyle(.borderedProminent)
                    .foregroundStyle(WorkspaceColor.background)
                    .disabled(model.busy)
                    .accessibilityIdentifier("find-nearby-mac")
                pairingAlternatives
            }
        }
        .workspaceCard(padding: 19)
    }

    private var linkTint: Color { model.connected ? WorkspaceColor.mint : WorkspaceColor.muted }

    private func device(_ symbol: String, name: String) -> some View {
        VStack(spacing: 8) {
            Image(systemName: symbol).font(.title2.weight(.medium))
                .foregroundStyle(linkTint)
                .frame(height: 31).accessibilityHidden(true)
            Text(name).font(.caption.weight(.semibold)).lineLimit(2)
        }
        .frame(maxWidth: .infinity, minHeight: 82)
        .background(WorkspaceColor.background, in: RoundedRectangle(cornerRadius: 15))
    }

    private var pairingAlternatives: some View {
        VStack(spacing: 10) {
            Button {
                nearbyMode = .discoverable
            } label: {
                Label("Let your Mac find this device", systemImage: "antenna.radiowaves.left.and.right")
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .buttonStyle(.bordered).disabled(model.busy)
            .accessibilityIdentifier("make-phone-discoverable")
            Button {
                scanning = true
            } label: {
                Label("Scan Mac pairing QR", systemImage: "qrcode.viewfinder")
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .buttonStyle(.bordered).disabled(model.busy)
            .accessibilityIdentifier("scan-pairing-qr")
            DisclosureGroup("Enter a pairing code manually") {
                SecureField("Private pairing code", text: $pairing)
                    .textInputAutocapitalization(.never).autocorrectionDisabled()
                    .padding(.vertical, 8)
                Button("Connect") {
                    Task {
                        await model.connect(pairing)
                        if model.connected { pairing = "" }
                    }
                }.disabled(pairing.isEmpty || model.busy)
            }.font(.subheadline)
        }
    }

    private var worker: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Mac acceleration").font(.headline)
                    Text(model.workerState).font(.caption.weight(.semibold))
                        .foregroundStyle(model.workerRunning ? WorkspaceColor.mint : WorkspaceColor.muted)
                }
                Spacer()
                Toggle("Help your Mac", isOn: Binding(get: { model.workerRunning }, set: { enabled in
                    if enabled { model.startWorker() } else { model.stopWorker() }
                }))
                .labelsHidden()
                .disabled(model.busy || (!model.connected && !model.workerRunning))
            }
            Text("Shares Voice EQ work with the connected Mac while this app stays open.")
                .font(.subheadline).foregroundStyle(WorkspaceColor.muted)
            metrics
            if let accepted = model.workUsage.lastAcceptedAt {
                Text("Last result accepted \(accepted, format: .dateTime.hour().minute().second())")
                    .foregroundStyle(WorkspaceColor.muted).font(.caption.monospacedDigit())
            } else if model.workerRunning {
                Text("Waiting for the first Voice EQ task.").foregroundStyle(WorkspaceColor.muted).font(.caption)
            }
            DisclosureGroup("Device benchmark and requirements") {
                VStack(alignment: .leading, spacing: 9) {
                    Text(model.assessmentText).textSelection(.enabled)
                    Text("Enable trusted-LAN processing on the Mac. Editing, sending audio, backgrounding or a warm device can pause contribution.")
                    Button("Run Voice EQ benchmark", systemImage: "timer") { Task { await model.assessDevice() } }
                        .disabled(model.busy || model.workerRunning)
                }
                .font(.caption)
                .foregroundStyle(WorkspaceColor.muted)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.top, 9)
            }
            .font(.subheadline)
        }
        .workspaceCard()
    }

    private var metrics: some View {
        let usage = model.workUsage
        return LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
            metric("Accepted chunks", value: usage.chunks.formatted(), symbol: "square.stack.3d.up")
            metric("Audio processed", value: usage.audioSeconds.formatted(.number.precision(.fractionLength(1))) + " s", symbol: "waveform")
            metric("Last Voice EQ", value: usage.lastDSPSeconds.map { ($0 * 1000).formatted(.number.precision(.fractionLength(1))) + " ms" } ?? "—",
                   symbol: "timer")
            metric("Local DSP rate", value: usage.realtimeFactor.map { $0.formatted(.number.precision(.fractionLength(1))) + "×" } ?? "—",
                   symbol: "speedometer")
        }
        .accessibilityHint("DSP rate compares audio duration to the phone's Voice EQ compute time. Transfer time is separate.")
    }

    private func metric(_ title: String, value: String, symbol: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Image(systemName: symbol).foregroundStyle(WorkspaceColor.blue).accessibilityHidden(true)
            Text(value).font(.system(.title3, design: .monospaced, weight: .semibold))
                .lineLimit(1).minimumScaleFactor(0.65)
            Text(title).font(.caption).foregroundStyle(WorkspaceColor.muted)
        }
        .padding(11)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(WorkspaceColor.background, in: RoundedRectangle(cornerRadius: 12))
        .accessibilityElement(children: .combine)
    }

    private var transfers: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Send audio to Mac").font(.headline)
            if model.source == nil {
                Text("Choose a recording in Studio first.").foregroundStyle(WorkspaceColor.muted).font(.subheadline)
                Button("Open Studio", systemImage: "waveform", action: openStudio)
            } else {
                Text(model.name).font(.subheadline.weight(.semibold)).lineLimit(2)
                if model.resultURL != nil {
                    Picker("Send", selection: $model.sendResult) {
                        Text("Source").tag(false)
                        Text("Revision").tag(true)
                    }
                    .pickerStyle(.segmented)
                    .disabled(model.busy || model.hasPendingJob)
                }
                Text(model.transferSelection)
                    .foregroundStyle(WorkspaceColor.muted).font(.caption.monospaced())
                Picker("Profile", selection: $model.remoteProfile) {
                    Text("Voice EQ + level").tag("voice")
                    Text("Level only").tag("level")
                }.disabled(model.busy || model.hasPendingJob)
                if model.hasPendingJob {
                    Button("Recover job", systemImage: "arrow.clockwise.icloud") { Task { await model.recover() } }
                        .buttonStyle(.borderedProminent).disabled(!model.connected || model.busy)
                } else {
                    Button("Send to Mac", systemImage: "arrow.up.right") { Task { await model.processOnMac() } }
                        .buttonStyle(.borderedProminent).disabled(!model.connected || model.busy)
                }
            }
            if model.busy { ProgressView(model.macState) }
            else if model.paired {
                Text(model.macState)
                    .foregroundStyle(WorkspaceColor.muted).font(.caption)
                    .accessibilityIdentifier("mac-state")
            }
            if let url = model.reportURL {
                ShareLink(item: url) { Label("Share verified Mac report", systemImage: "checkmark.shield") }
            }
        }
        .workspaceCard()
    }
}
