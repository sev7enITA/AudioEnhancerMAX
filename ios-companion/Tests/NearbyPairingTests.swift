import Network
import XCTest
@testable import AudioEnhancerCompanion

final class NearbyPairingTests: XCTestCase {
    private let pin = String(repeating: "ab", count: 32)

    private struct LiveFixture: Decodable {
        let text: [String: String]
        let owner: URL
    }

    private func advertisement(host: String = "192.168.2.5", port: String = "4321",
                               fingerprint: String? = nil, version: String = "1") -> [String: String] {
        ["v": version, "host": host, "port": port, "fp": fingerprint ?? pin]
    }

    func testNearbyRecordsRequireAValidPrivateEndpointAndLowercasePin() {
        for host in ["10.0.0.8", "172.16.0.8", "172.31.0.8", "192.168.2.5"] {
            XCTAssertEqual(NearbyMac(name: "Mac", text: advertisement(host: host))?.endpoint.absoluteString,
                           "https://\(host):4321")
        }
        for host in ["127.0.0.1", "172.32.0.8", "192.168.001.8", "1.2.3.4", "192.168.0.256",
                     "::1", "192.168.1.8/path", "192.168.1.8@other.example", "Mac.local"] {
            XCTAssertNil(NearbyMac(name: "Mac", text: advertisement(host: host)), host)
        }
        for port in ["0", "65536", "-1", "01", "٤٤٣"] {
            XCTAssertNil(NearbyMac(name: "Mac", text: advertisement(port: port)), port)
        }
        XCTAssertNil(NearbyMac(name: "Mac", text: advertisement(fingerprint: pin.uppercased())))
        XCTAssertNil(NearbyMac(name: "Mac", text: advertisement(fingerprint: String(pin.dropLast()))))
        XCTAssertNil(NearbyMac(name: "Mac", text: advertisement(version: "2")))
        XCTAssertNil(NearbyMac(name: "Mac", text: advertisement().filter { $0.key != "fp" }))
        XCTAssertEqual(NearbyMac(name: "Test\nMac", text: advertisement())?.name, "TestMac")
    }

    func testCommitmentAndConfirmationCodeMatchWireVector() {
        let client = String(repeating: "01", count: 32)
        let server = String(repeating: "0", count: 63) + "6"
        XCTAssertEqual(NearbyChallenge.commitment(client), "58badd9b455145b487ad24c7f259cc437cc4ffd0784716845249321fb5961cfc")
        XCTAssertEqual(NearbyChallenge.confirmationCode(fingerprint: pin, clientNonce: client, serverNonce: server),
                       "01168209")
    }

    func testAcceptOnlyApprovedPairingForSelectedEndpointAndPin() throws {
        let mac = try XCTUnwrap(NearbyMac(name: "Mac", text: advertisement()))
        let token = String(repeating: "a", count: 32)
        let correct = Pairing(protocol: 1, endpoint: "https://192.168.2.5:4321", fingerprint: pin, token: token)
        XCTAssertEqual(try mac.accept(correct), correct)
        XCTAssertThrowsError(try mac.accept(Pairing(protocol: 1, endpoint: "https://192.168.2.5:1234",
                                                    fingerprint: pin, token: token)))
        XCTAssertThrowsError(try mac.accept(Pairing(protocol: 1, endpoint: correct.endpoint,
                                                    fingerprint: String(repeating: "0", count: 64), token: token)))
        XCTAssertThrowsError(try mac.accept(Pairing(protocol: 1, endpoint: correct.endpoint,
                                                    fingerprint: pin, token: "")))
    }

    func testPhoneInvitationRequiresItsOwnIDAndDatagramSource() throws {
        let id = String(repeating: "af", count: 16)
        let sender = try XCTUnwrap(IPv4Address("192.168.2.5"))
        let payload: [String: Any] = ["v": 1, "id": id, "host": "192.168.2.5",
                                      "port": 4321, "fp": pin, "name": "QA Mac"]
        func parse(_ overrides: [String: Any] = [:], from address: IPv4Address? = nil) throws -> NearbyMac? {
            let data = try JSONSerialization.data(withJSONObject: payload.merging(overrides) { _, other in other })
            return NearbyPhoneInvitation.parse(data, from: address ?? sender, expectedID: id)
        }
        XCTAssertEqual(try parse()?.endpoint.absoluteString, "https://192.168.2.5:4321")
        XCTAssertNil(try parse(["id": String(repeating: "f", count: 32)]))
        XCTAssertNil(try parse(["v": true]))
        XCTAssertNil(try parse(["port": "4321"]))
        XCTAssertNil(try parse(["port": 0]))
        XCTAssertNil(try parse(["fp": pin.uppercased()]))
        XCTAssertNil(try parse(["name": String(repeating: "A", count: 1024)]))
        XCTAssertNil(try parse(from: XCTUnwrap(IPv4Address("192.168.2.6"))))
        XCTAssertNil(try parse(["host": "127.0.0.1"], from: .loopback))
    }

    @MainActor
    func testPhoneVisibilityExpiresAndClearsTheInvitationIdentity() async throws {
        let visibility = NearbyPhoneVisibility(duration: .milliseconds(100))
        visibility.start()
        defer { visibility.stop() }
        XCTAssertTrue(visibility.active)
        let id = try XCTUnwrap(visibility.invitationID)
        XCTAssertTrue(NearbyMac.isHex(id, length: 32))
        for _ in 0..<40 {
            if !visibility.active { break }
            try await Task.sleep(for: .milliseconds(50))
        }
        XCTAssertFalse(visibility.active)
        XCTAssertNil(visibility.invitationID)
        XCTAssertTrue(visibility.invitations.isEmpty)
        XCTAssertTrue(visibility.message.contains("expired"))
    }

    @MainActor
    func testLiveBonjourReadsTheMacAdvertisement() async throws {
        let fixture = try liveFixture()
        let expected = try XCTUnwrap(NearbyMac(name: "QA Mac", text: fixture.text))
        let browser = NearbyMacBrowser()
        browser.start()
        defer { browser.stop() }
        for _ in 0..<50 {
            if browser.matches.contains(where: { $0.id == expected.id }) { return }
            try await Task.sleep(for: .milliseconds(200))
        }
        XCTFail(browser.message)
    }

    func testLivePinnedPairingMatchesTheMacCodeBeforeApproval() async throws {
        let fixture = try liveFixture()
        let mac = try XCTUnwrap(NearbyMac(name: "QA Mac", text: fixture.text))
        let device = UUID().uuidString
        let anotherPin = fixture.text.merging(["fp": String(repeating: "0", count: 64)]) { _, new in new }
        let unverified = try XCTUnwrap(NearbyMac(name: "QA Mac", text: anotherPin))
        let wrongClient = NearbyPairingClient(mac: unverified, device: device)
        defer { wrongClient.cancel() }
        do {
            _ = try await wrongClient.begin()
            XCTFail("Nearby pairing accepted the wrong TLS fingerprint")
        } catch is URLError {
            // The transport must reject the certificate before posting a pairing request.
        }
        try await approveAndCheck(mac, fixture: fixture, device: device)
    }

    @MainActor
    func testLiveMacFindsPhoneAndSendsInvitationBeforePairing() async throws {
        let fixture = try liveFixture()
        let expected = try XCTUnwrap(NearbyMac(name: "QA Mac", text: fixture.text))
        let visibility = NearbyPhoneVisibility()
        visibility.start()
        defer { visibility.stop() }
        let id = try XCTUnwrap(visibility.invitationID)
        let owner = fixture.owner.appendingPathComponent("api").appendingPathComponent("companion")
        func phones(_ action: String, body: [String: String] = [:]) async throws {
            var request = URLRequest(url: owner.appendingPathComponent("phones").appendingPathComponent(action))
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONEncoder().encode(body)
            let (_, response) = try await URLSession.shared.data(for: request)
            XCTAssertEqual((response as? HTTPURLResponse)?.statusCode, 200)
        }
        try await phones("search")
        var found = false
        for _ in 0..<40 {
            let (data, _) = try await URLSession.shared.data(from: owner.appendingPathComponent("session"))
            let state = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
            let devices = try XCTUnwrap(state["phones"] as? [[String: String]])
            if devices.contains(where: { $0["id"] == id }) {
                found = true
                break
            }
            try await Task.sleep(for: .milliseconds(200))
        }
        XCTAssertTrue(found, "The Mac did not discover the simulator's phone advertisement")
        if found {
            try await phones("invite", body: ["id": id])
            for _ in 0..<25 {
                if !visibility.invitations.isEmpty { break }
                try await Task.sleep(for: .milliseconds(100))
            }
        }
        try await phones("stop")
        let invitation = try XCTUnwrap(visibility.invitations.first)
        XCTAssertEqual(invitation.id, expected.id)
        visibility.stop()
        try await approveAndCheck(invitation, fixture: fixture, device: UUID().uuidString)
    }

    private func approveAndCheck(_ mac: NearbyMac, fixture: LiveFixture, device: String) async throws {
        let client = NearbyPairingClient(mac: mac, device: device)
        defer { client.cancel() }
        let challenge = try await client.begin()

        let owner = fixture.owner.appendingPathComponent("api").appendingPathComponent("companion")
        let (data, _) = try await URLSession.shared.data(from: owner.appendingPathComponent("session"))
        let state = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        let requests = try XCTUnwrap(state["requests"] as? [[String: String]])
        let pending = try XCTUnwrap(requests.first(where: { $0["id"] == challenge.requestID }))
        XCTAssertEqual(pending["code"], challenge.code)

        async let confirmed = client.confirm(challenge)
        try await Task.sleep(for: .milliseconds(200))
        let decisionURL = owner.appendingPathComponent("pairing").appendingPathComponent("requests")
            .appendingPathComponent(challenge.requestID)
        var decision = URLRequest(url: decisionURL)
        decision.httpMethod = "POST"
        decision.setValue("application/json", forHTTPHeaderField: "Content-Type")
        decision.httpBody = Data(#"{"approved":true}"#.utf8)
        let (_, response) = try await URLSession.shared.data(for: decision)
        XCTAssertEqual((response as? HTTPURLResponse)?.statusCode, 200)

        let pairing = try await confirmed
        XCTAssertEqual(pairing.endpoint, mac.endpoint.absoluteString)
        XCTAssertEqual(pairing.fingerprint, mac.fingerprint)
        let paired = CompanionClient(pairing, device: device)
        defer { paired.invalidate() }
        let status = try await paired.json("/v1/status")
        XCTAssertEqual(status["status"] as? String, "connected")
    }

    private func liveFixture() throws -> LiveFixture {
        guard let file = Bundle(for: Self.self).url(forResource: "NearbyFixture", withExtension: "json") else {
            throw XCTSkip("Provide a private simulator fixture from an isolated Mac nearby pairing session.")
        }
        let fixture = try JSONDecoder().decode(LiveFixture.self, from: Data(contentsOf: file))
        guard fixture.owner.scheme == "http", fixture.owner.host == "127.0.0.1", fixture.owner.port != nil else {
            throw XCTSkip("Nearby approval integration uses the test Mac's loopback interface.")
        }
        return fixture
    }
}
