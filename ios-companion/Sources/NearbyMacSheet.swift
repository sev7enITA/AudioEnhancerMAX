import SwiftUI

struct NearbyMacSheet: View {
    enum Mode: String, Identifiable {
        case findMac, discoverable

        var id: Self { self }
        var title: String { self == .findMac ? "Find your Mac" : "Discoverable device" }
        var retryTitle: String { self == .findMac ? "Search again" : "Make this device visible again" }
    }

    let mode: Mode
    @Environment(\.dismiss) private var dismiss
    @Environment(\.scenePhase) private var scenePhase
    @EnvironmentObject private var model: CompanionModel
    @StateObject private var discovery = NearbyMacBrowser()
    @StateObject private var visibility = NearbyPhoneVisibility()
    @State private var stage = Stage.searching
    @State private var attempt: NearbyPairingClient?
    @State private var operation: Task<Void, Never>?

    private enum Stage {
        case searching
        case discoverable
        case requesting(NearbyMac)
        case comparing(NearbyMac, NearbyChallenge)
        case waiting
        case failed(String)
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 14) {
                    switch stage {
                    case .searching:
                        pairingStep("Search over Wi-Fi", symbol: "wifi",
                                    message: "Open Nearby pairing under Mobile devices and transfers on the Mac. Both devices need the same Wi-Fi or hotspot.")
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Nearby Macs").font(.headline)
                            if discovery.matches.isEmpty {
                                Label(discovery.message, systemImage: "antenna.radiowaves.left.and.right")
                                    .foregroundStyle(WorkspaceColor.muted)
                            }
                            ForEach(discovery.matches) { mac in invitationButton(mac) }
                            Button("Refresh search", systemImage: "arrow.clockwise") { discovery.start() }
                        }.workspaceCard()
                    case .discoverable:
                        pairingStep("Find this device from your Mac", symbol: "iphone.radiowaves.left.and.right",
                                    message: "Open Mobile devices and transfers on the Mac, then search for nearby phones.")
                        VStack(alignment: .leading, spacing: 12) {
                            Label(visibility.message, systemImage: visibility.active ? "dot.radiowaves.left.and.right" : "wifi.slash")
                                .foregroundStyle(visibility.active ? WorkspaceColor.mint : WorkspaceColor.muted)
                                .accessibilityIdentifier("phone-discovery-status")
                            if !visibility.active { Button(mode.retryTitle) { reset() } }
                            ForEach(visibility.invitations) { mac in invitationButton(mac) }
                        }.workspaceCard()
                    case .requesting(let mac):
                        ProgressView("Requesting a code from \(mac.name)…").workspaceCard(padding: 22)
                    case .comparing(let mac, let challenge):
                        codeCard(mac, challenge: challenge)
                    case .waiting:
                        ProgressView("Waiting for confirmation on the Mac…").workspaceCard(padding: 22)
                    case .failed(let message):
                        pairingStep("Pairing needs attention", symbol: "exclamationmark.triangle", message: message)
                        Button(mode.retryTitle, systemImage: "arrow.clockwise") { reset() }.buttonStyle(.borderedProminent)
                    }
                }
                .padding(16)
                .frame(maxWidth: 620)
                .frame(maxWidth: .infinity)
            }
            .background(WorkspaceColor.background)
            .navigationTitle(mode.title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { cancel(); dismiss() }
                }
            }
        }
        .onAppear { reset() }
        .onDisappear { cancel() }
        .onChange(of: scenePhase) { _, next in
            if next == .background {
                cancel()
                stage = .failed("Nearby pairing paused while the app was in the background. Start a fresh pairing request.")
            }
        }
    }

    private func pairingStep(_ title: String, symbol: String, message: String) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Image(systemName: symbol).font(.title2).foregroundStyle(WorkspaceColor.mint).accessibilityHidden(true)
            Text(title).font(.title2.bold())
            Text(message).font(.subheadline).foregroundStyle(WorkspaceColor.muted)
        }.workspaceCard(padding: 20)
    }

    private func codeCard(_ mac: NearbyMac, challenge: NearbyChallenge) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Compare the code").font(.title2.bold())
            Text("Check the eight digits on \(mac.name) and confirm on both devices.")
                .font(.subheadline).foregroundStyle(WorkspaceColor.muted)
            Text("\(challenge.code.prefix(4)) \(challenge.code.suffix(4))")
                .font(.system(.largeTitle, design: .monospaced, weight: .bold))
                .minimumScaleFactor(0.7)
                .foregroundStyle(WorkspaceColor.mint)
                .frame(maxWidth: .infinity, minHeight: 64)
                .background(WorkspaceColor.background, in: RoundedRectangle(cornerRadius: 12))
                .accessibilityLabel("Confirmation code \(challenge.code.map { String($0) }.joined(separator: " "))")
                .accessibilityIdentifier("nearby-confirmation-code")
            Button { finish(challenge) } label: {
                Label("Codes match", systemImage: "checkmark.shield")
                    .frame(maxWidth: .infinity, minHeight: 28)
            }
            .buttonStyle(.borderedProminent)
            .foregroundStyle(WorkspaceColor.background)
            .accessibilityIdentifier("nearby-confirm-codes")
            Button("Codes do not match", role: .destructive) {
                cancel()
                stage = .failed("Pairing cancelled. Decline this request on your Mac before trying again.")
            }
        }.workspaceCard(padding: 20)
    }

    private func invitationButton(_ mac: NearbyMac) -> some View {
        Button { begin(mac) } label: {
            HStack(alignment: .center, spacing: 12) {
                Image(systemName: "desktopcomputer").font(.title2).foregroundStyle(WorkspaceColor.mint).accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 4) {
                    Text(mode == .discoverable ? "Accept invitation from \(mac.name)" : mac.name)
                        .font(.subheadline.weight(.semibold))
                    if let host = mac.endpoint.host {
                        Text(host).font(.caption.monospacedDigit()).foregroundStyle(WorkspaceColor.muted)
                    }
                }
                Spacer()
                Image(systemName: "chevron.right").font(.caption.weight(.bold)).accessibilityHidden(true)
            }
            .padding(12)
            .background(WorkspaceColor.background, in: RoundedRectangle(cornerRadius: 12))
        }.buttonStyle(.plain)
    }

    private func reset() {
        cancel()
        if mode == .findMac {
            stage = .searching
            discovery.start()
        } else {
            stage = .discoverable
            visibility.start()
        }
    }

    private func cancel() {
        discovery.stop()
        visibility.stop()
        operation?.cancel()
        operation = nil
        attempt?.cancel()
        attempt = nil
    }

    private func begin(_ mac: NearbyMac) {
        switch stage {
        case .searching where discovery.matches.contains(mac):
            break
        case .discoverable where visibility.active && visibility.invitations.contains(mac):
            break
        default:
            return
        }
        cancel()
        let client = NearbyPairingClient(mac: mac, device: model.device)
        attempt = client
        stage = .requesting(mac)
        operation = Task {
            do {
                let challenge = try await client.begin()
                try Task.checkCancellation()
                stage = .comparing(mac, challenge)
                operation = nil
            } catch {
                guard !Task.isCancelled else { return }
                fail(error)
            }
        }
    }

    private func finish(_ challenge: NearbyChallenge) {
        guard case .comparing(_, let current) = stage, current == challenge,
              let client = attempt else { return }
        stage = .waiting
        operation = Task {
            do {
                let pairing = try await client.confirm(challenge)
                try Task.checkCancellation()
                if await model.connect(pairing) {
                    dismiss()
                } else if !Task.isCancelled {
                    let message = model.error ?? "The Mac approved the pairing but the connection could not be saved."
                    model.error = nil
                    fail(CompanionError.message(message))
                }
            } catch {
                guard !Task.isCancelled else { return }
                fail(error)
            }
        }
    }

    private func fail(_ error: Error) {
        attempt?.cancel()
        attempt = nil
        operation = nil
        if error is URLError {
            stage = .failed("Could not reach or verify the Mac. Check the shared Wi-Fi or hotspot and Local Network access in iPhone Settings.")
        } else {
            stage = .failed(error.localizedDescription)
        }
    }
}
