import Combine
import CryptoKit
import Foundation
import Network
import Security

struct NearbyMac: Equatable, Identifiable, Sendable {
    static let serviceType = "_aemax-pair._tcp"

    let name: String
    let endpoint: URL
    let fingerprint: String

    var id: String { "\(endpoint.absoluteString)|\(fingerprint)" }

    init?(name: String, text: [String: String]) {
        guard Set(text.keys) == ["v", "host", "port", "fp"],
              text["v"] == "1",
              let host = text["host"], Self.isPrivateIPv4(host),
              let portText = text["port"], let port = UInt16(portText),
              port > 0, String(port) == portText,
              let fingerprint = text["fp"], Self.isHex(fingerprint, length: 64),
              let endpoint = URL(string: "https://\(host):\(port)") else { return nil }

        let cleanedName = String(name.unicodeScalars.filter {
            !CharacterSet.controlCharacters.contains($0)
        }.prefix(80)).trimmingCharacters(in: .whitespacesAndNewlines)
        self.name = cleanedName.isEmpty ? "AudioEnhancerMAX Mac" : cleanedName
        self.endpoint = endpoint
        self.fingerprint = fingerprint
    }

    private static func isPrivateIPv4(_ address: String) -> Bool {
        let components = address.split(separator: ".", omittingEmptySubsequences: false)
        let octets = components.compactMap { component -> UInt8? in
            guard let octet = UInt8(component), String(octet) == component else { return nil }
            return octet
        }
        guard components.count == 4, octets.count == 4 else { return false }
        return octets[0] == 10
            || (octets[0] == 172 && (16...31).contains(octets[1]))
            || (octets[0] == 192 && octets[1] == 168)
    }

    static func isHex(_ value: String, length: Int) -> Bool {
        value.utf8.count == length && value.utf8.allSatisfy {
            (48...57).contains($0) || (97...102).contains($0)
        }
    }

    func accept(_ pairing: Pairing) throws -> Pairing {
        let approved = try pairing.validated()
        guard approved.endpoint == endpoint.absoluteString, approved.fingerprint == fingerprint else {
            throw CompanionError.message("This Mac's identity changed. Search again or use its QR code.")
        }
        return approved
    }
}

@MainActor final class NearbyMacBrowser: ObservableObject {
    @Published private(set) var matches: [NearbyMac] = []
    @Published private(set) var message = "Looking for Macs on your local network…"
    private var browser: NWBrowser?

    func start() {
        stop()
        message = "Looking for Macs on your local network…"
        let next = NWBrowser(
            for: .bonjourWithTXTRecord(type: NearbyMac.serviceType, domain: "local."),
            using: .tcp
        )
        browser = next
        next.stateUpdateHandler = { [weak self, weak next] state in
            Task { @MainActor in
                guard let self, let next, self.browser === next else { return }
                self.update(state)
            }
        }
        next.browseResultsChangedHandler = { [weak self, weak next] results, _ in
            Task { @MainActor in
                guard let self, let next, self.browser === next else { return }
                self.read(results)
            }
        }
        next.start(queue: .main)
    }

    func stop() {
        let previous = browser
        browser = nil
        previous?.cancel()
        matches = []
    }

    private func update(_ state: NWBrowser.State) {
        switch state {
        case .ready:
            message = "No Macs found yet. Open Nearby pairing on the Mac and check the shared Wi-Fi or hotspot."
        case .waiting(let error), .failed(let error):
            matches = []
            if case .dns(-65570) = error {
                // kDNSServiceErr_PolicyDenied is returned when iOS Local Network access is denied.
                message = "Allow Local Network access for AudioEnhancer in iPhone Settings, then try again."
            } else {
                message = "Local network search is unavailable. Check Wi-Fi or use the Mac's QR code."
            }
        case .setup, .cancelled:
            break
        @unknown default:
            break
        }
    }

    private func read(_ results: Set<NWBrowser.Result>) {
        var discovered: [String: NearbyMac] = [:]
        for result in results {
            guard case .service(let name, _, _, _) = result.endpoint,
                  case .bonjour(let record) = result.metadata,
                  let mac = NearbyMac(name: name, text: record.dictionary) else { continue }
            discovered[mac.id] = mac
        }
        matches = discovered.values.sorted {
            let order = $0.name.localizedStandardCompare($1.name)
            return order == .orderedSame ? $0.id < $1.id : order == .orderedAscending
        }
    }
}

struct NearbyChallenge: Equatable, Sendable {
    let requestID: String
    let clientNonce: String
    let code: String

    var credentials: [String: String] {
        ["request_id": requestID, "client_nonce": clientNonce]
    }

    static func commitment(_ clientNonce: String) -> String {
        SHA256.hash(data: Data(clientNonce.utf8)).map { String(format: "%02x", $0) }.joined()
    }

    static func confirmationCode(fingerprint: String, clientNonce: String, serverNonce: String) -> String {
        let input = "AEMAX-PAIR-1|\(fingerprint)|\(clientNonce)|\(serverNonce)"
        let digest = SHA256.hash(data: Data(input.utf8))
        let word = digest.prefix(4).reduce(UInt32(0)) { ($0 << 8) | UInt32($1) }
        let digits = String(word % 100_000_000)
        return String(repeating: "0", count: 8 - digits.count) + digits
    }
}

final class NearbyPairingClient: @unchecked Sendable {
    private struct ChallengeResponse: Decodable {
        let requestID: String
        let serverNonce: String

        enum CodingKeys: String, CodingKey {
            case requestID = "request_id"
            case serverNonce = "server_nonce"
        }
    }

    private enum PairingStatus: String, Decodable {
        case pending, approved, rejected
    }

    private struct StatusResponse: Decodable {
        let status: PairingStatus
        let pairing: Pairing?
    }

    private let mac: NearbyMac
    private let device: String
    private let delegate: PinnedSession
    private let session: URLSession

    init(mac: NearbyMac, device: String) {
        self.mac = mac
        self.device = device
        delegate = PinnedSession(endpoint: mac.endpoint, fingerprint: mac.fingerprint)
        let config = URLSessionConfiguration.ephemeral
        config.httpShouldSetCookies = false
        config.urlCache = nil
        config.timeoutIntervalForRequest = 8
        config.timeoutIntervalForResource = 12
        session = URLSession(configuration: config, delegate: delegate, delegateQueue: nil)
    }

    deinit { session.invalidateAndCancel() }

    func cancel() {
        session.invalidateAndCancel()
    }

    func begin() async throws -> NearbyChallenge {
        var nonceBytes = [UInt8](repeating: 0, count: 32)
        let randomStatus = nonceBytes.withUnsafeMutableBytes { bytes in
            guard let address = bytes.baseAddress else { return errSecParam }
            return SecRandomCopyBytes(kSecRandomDefault, bytes.count, address)
        }
        guard randomStatus == errSecSuccess else {
            throw CompanionError.message("Could not create a secure pairing request.")
        }
        let clientNonce = nonceBytes.map { String(format: "%02x", $0) }.joined()
        let start: ChallengeResponse = try await post("start", ["commitment": NearbyChallenge.commitment(clientNonce)])
        guard NearbyMac.isHex(start.requestID, length: 32), NearbyMac.isHex(start.serverNonce, length: 64) else {
            throw CompanionError.message("This Mac returned an invalid pairing request.")
        }
        let challenge = NearbyChallenge(
            requestID: start.requestID,
            clientNonce: clientNonce,
            code: NearbyChallenge.confirmationCode(
                fingerprint: mac.fingerprint, clientNonce: clientNonce, serverNonce: start.serverNonce
            )
        )
        let reveal: StatusResponse = try await post("reveal", challenge.credentials)
        guard reveal.status == .pending, reveal.pairing == nil else {
            throw CompanionError.message("The Mac did not enter the confirmation step. Start pairing again.")
        }
        return challenge
    }

    func confirm(_ challenge: NearbyChallenge) async throws -> Pairing {
        let deadline = ContinuousClock.now.advanced(by: .seconds(90))
        while ContinuousClock.now < deadline {
            try Task.checkCancellation()
            let result: StatusResponse = try await post("finish", challenge.credentials)
            switch result.status {
            case .pending:
                guard result.pairing == nil else {
                    throw CompanionError.message("The Mac sent credentials before approving this request.")
                }
                try await Task.sleep(for: .milliseconds(800))
            case .approved:
                guard let pairing = result.pairing else {
                    throw CompanionError.message("The Mac did not return the approved pairing.")
                }
                return try mac.accept(pairing)
            case .rejected:
                throw CompanionError.message("This pairing was declined on the Mac.")
            }
        }
        throw CompanionError.message("Pairing expired. Search for the Mac again to start a new request.")
    }

    private func post<T: Decodable>(_ phase: String, _ body: [String: String]) async throws -> T {
        let url = mac.endpoint.appendingPathComponent("v1").appendingPathComponent("pairing").appendingPathComponent(phase)
        var request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData)
        request.httpMethod = "POST"
        request.httpBody = try JSONEncoder().encode(body)
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(device, forHTTPHeaderField: "X-Device-ID")
        request.setValue("iOS companion", forHTTPHeaderField: "X-Device-Name")

        let (bytes, response) = try await session.bytes(for: request, delegate: delegate)
        guard let http = response as? HTTPURLResponse else {
            throw CompanionError.message("Invalid response from the Mac.")
        }
        switch http.statusCode {
        case 200:
            break
        case 410:
            throw CompanionError.message("This pairing request expired. Search again on the shared network.")
        case 429:
            throw CompanionError.message("The Mac has too many pairing requests. Wait a moment and try again.")
        default:
            throw CompanionError.message("The Mac could not continue nearby pairing. Open Nearby pairing on the Mac or use its QR code.")
        }
        var data = Data()
        for try await byte in bytes {
            guard data.count < 8192 else {
                throw CompanionError.message("The pairing response from the Mac is too large.")
            }
            data.append(byte)
        }
        do { return try JSONDecoder().decode(T.self, from: data) }
        catch { throw CompanionError.message("This Mac returned an invalid pairing response.") }
    }
}
