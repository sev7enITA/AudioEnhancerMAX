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
