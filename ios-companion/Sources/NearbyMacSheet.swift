import SwiftUI

struct NearbyMacSheet: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.scenePhase) private var scenePhase
    @EnvironmentObject private var model: CompanionModel
    @StateObject private var discovery = NearbyMacBrowser()
    @State private var stage = Stage.searching
    @State private var attempt: NearbyPairingClient?
    @State private var operation: Task<Void, Never>?

    private enum Stage {
        case searching
        case requesting(NearbyMac)
        case comparing(NearbyMac, NearbyChallenge)
        case waiting
        case failed(String)
    }

    var body: some View {
        NavigationStack {
            List {
                switch stage {
                case .searching:
                    Section {
                        Text("On the Mac, open Nearby pairing in Mobile devices and transfers. Keep both devices on the same Wi-Fi or hotspot.")
                            .foregroundStyle(.secondary)
                    }
                    Section("Nearby Macs") {
                        if discovery.matches.isEmpty {
                            Text(discovery.message).foregroundStyle(.secondary)
                        }
                        ForEach(discovery.matches) { mac in
                            Button { begin(mac) } label: {
                                Label {
                                    VStack(alignment: .leading, spacing: 3) {
                                        Text(mac.name)
                                        if let host = mac.endpoint.host {
                                            Text(host).font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                                        }
                                    }
                                } icon: { Image(systemName: "desktopcomputer") }
                            }
                        }
                        Button("Refresh search") { discovery.start() }
                    }
                case .requesting(let mac):
                    ProgressView("Requesting a confirmation code from \(mac.name)…")
                case .comparing(let mac, let challenge):
                    Section {
                        Text("Compare the eight digits below with the code on \(mac.name). Confirm on both devices when they match.")
                        Text(challenge.code)
                            .font(.largeTitle.monospacedDigit().weight(.semibold))
                            .accessibilityLabel("Confirmation code \(challenge.code.map { String($0) }.joined(separator: " "))")
                            .accessibilityIdentifier("nearby-confirmation-code")
                    }
                    Section {
                        Button("Codes match") { finish(challenge) }
                            .buttonStyle(.borderedProminent)
                            .accessibilityIdentifier("nearby-confirm-codes")
                        Button("Codes do not match", role: .destructive) { search() }
                    }
                case .waiting:
                    ProgressView("Waiting for confirmation on the Mac…")
                case .failed(let message):
                    Section {
                        Text(message).foregroundStyle(.secondary)
                        Button("Search again") { search() }
                    }
                }
                Section {
                    Text("You can also scan the QR code shown on your Mac from the Connection tab.")
                        .font(.footnote).foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Find your Mac")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        cancel()
                        dismiss()
                    }
                }
            }
        }
        .onAppear { search() }
        .onDisappear { cancel() }
        .onChange(of: scenePhase) { _, next in
            if next == .background {
                cancel()
                stage = .failed("Search paused while the app was in the background. Start a fresh pairing request.")
            }
        }
    }

    private func search() {
        cancel()
        stage = .searching
        discovery.start()
    }

    private func cancel() {
        discovery.stop()
        operation?.cancel()
        operation = nil
        attempt?.cancel()
        attempt = nil
    }

    private func begin(_ mac: NearbyMac) {
        guard case .searching = stage else { return }
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
