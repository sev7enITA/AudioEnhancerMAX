import Combine
import Foundation
import Network
import UIKit

enum NearbyPhoneInvitation {
    static let serviceType = "_aemax-phone._udp"

    private struct Payload: Decodable {
        let v: Int
        let id: String
        let host: String
        let port: UInt16
        let fp: String
        let name: String
    }

    static func parse(_ data: Data, from source: IPv4Address, expectedID: String) -> NearbyMac? {
        guard data.count <= 1024,
              NearbyMac.isHex(expectedID, length: 32),
              let payload = try? JSONDecoder().decode(Payload.self, from: data),
              payload.v == 1, payload.id == expectedID,
              payload.host == source.rawValue.map({ String($0) }).joined(separator: ".")
        else { return nil }

        return NearbyMac(name: payload.name, text: [
            "v": "1", "host": payload.host, "port": String(payload.port), "fp": payload.fp,
        ])
    }

    static func sender(of endpoint: NWEndpoint) -> IPv4Address? {
        guard case let .hostPort(host, _) = endpoint else { return nil }
        switch host {
        case let .ipv4(address): return address
        case let .ipv6(address) where address.isIPv4Mapped: return address.asIPv4
        default: return nil
        }
    }
}

@MainActor final class NearbyPhoneVisibility: ObservableObject {
    @Published private(set) var invitations: [NearbyMac] = []
    @Published private(set) var active = false
    @Published private(set) var message = "This device is hidden."

    private struct Receive {
        let connection: NWConnection
        let timer: Task<Void, Never>
    }

    private var listener: NWListener?
    private var timeout: Task<Void, Never>?
    private var receiving: [UUID: Receive] = [:]
    private(set) var invitationID: String?
    private let duration: Duration

    init(duration: Duration = .seconds(90)) {
        self.duration = duration
    }

    func start() {
        stop()
        do {
            let id = try NearbyChallenge.randomHex(byteCount: 16)
            let next = try NWListener(using: .udp, on: .any)
            next.service = NWListener.Service(
                name: "AudioEnhancerMAX · \(UIDevice.current.model)",
                type: NearbyPhoneInvitation.serviceType,
                domain: "local.",
                txtRecord: NWTXTRecord(["v": "1", "id": id])
            )
            invitationID = id
            listener = next
            active = true
            message = "Starting local discovery…"
            next.stateUpdateHandler = { [weak self, weak next] state in
                Task { @MainActor in
                    guard let self, let next, self.listener === next else { return }
                    self.update(state)
                }
            }
            next.newConnectionHandler = { [weak self, weak next] connection in
                Task { @MainActor in
                    guard let self, let next, self.listener === next else {
                        connection.cancel()
                        return
                    }
                    self.receive(connection)
                }
            }
            next.start(queue: .main)
            timeout = Task { [weak self, weak next] in
                do {
                    try await Task.sleep(for: self?.duration ?? .zero)
                    guard let self, let next, self.listener === next else { return }
                    self.stop("Discovery expired. Make this device visible again to receive an invitation.")
                } catch { return }
            }
        } catch {
            stop("Could not start discovery. Check Local Network access or use the Mac's QR code.")
        }
    }

    func stop(_ reason: String = "This device is hidden.") {
        let previous = listener
        listener = nil
        previous?.cancel()
        timeout?.cancel()
        timeout = nil
        for item in receiving.values {
            item.timer.cancel()
            item.connection.cancel()
        }
        receiving.removeAll()
        invitationID = nil
        invitations = []
        active = false
        message = reason
    }

    private func update(_ state: NWListener.State) {
        switch state {
        case .ready:
            message = "This device is visible for up to 90 seconds. Choose it on your Mac to send an invitation."
        case .waiting(let error), .failed(let error):
            if case .dns(-65570) = error {
                stop("Allow Local Network access for AudioEnhancer in Settings, then try again.")
            } else {
                stop("Local discovery is unavailable. Check the shared Wi-Fi or hotspot.")
            }
        case .setup, .cancelled:
            break
        @unknown default:
            break
        }
    }

    private func receive(_ connection: NWConnection) {
        guard receiving.count < 8, let sender = NearbyPhoneInvitation.sender(of: connection.endpoint) else {
            connection.cancel()
            return
        }
        let key = UUID()
        let timer = Task { [weak self] in
            do { try await Task.sleep(for: .seconds(2)) } catch { return }
            self?.finishReceive(key)
        }
        receiving[key] = Receive(connection: connection, timer: timer)
        connection.start(queue: .main)
        connection.receiveMessage { [weak self] data, _, complete, error in
            Task { @MainActor in
                guard let self, self.finishReceive(key), complete, error == nil,
                      let id = self.invitationID, let data,
                      let mac = NearbyPhoneInvitation.parse(data, from: sender, expectedID: id),
                      self.invitations.count < 6, !self.invitations.contains(where: { $0.id == mac.id })
                else { return }
                self.invitations.append(mac)
            }
        }
    }

    @discardableResult
    private func finishReceive(_ key: UUID) -> Bool {
        guard let item = receiving.removeValue(forKey: key) else { return false }
        item.timer.cancel()
        item.connection.cancel()
        return true
    }
}
