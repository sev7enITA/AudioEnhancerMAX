import Foundation

enum CompanionDistribution {
    static var appStore: Bool {
        #if AEMAX_APP_STORE
        return true
        #else
        return false
        #endif
    }

    static func appStoreURL(listingID: String) -> URL? {
        guard (6...16).contains(listingID.utf8.count), listingID.first != "0",
              listingID.utf8.allSatisfy({ (48...57).contains($0) }),
              listingID != "6791591803" else { return nil }
        return URL(string: "https://apps.apple.com/app/id\(listingID)")
    }
}

#if !AEMAX_APP_STORE
import CryptoKit
import Darwin

enum CompanionUpdateError: LocalizedError {
    case invalidFeed, expiredFeed, invalidRelease, untrustedLocation, downloadFailed, exceedsLimit, wrongFile

    var errorDescription: String? {
        switch self {
        case .invalidFeed: "Could not validate the signed update feed."
        case .expiredFeed: "The update feed is outside its validity period."
        case .invalidRelease: "The update feed contains an invalid iOS release."
        case .untrustedLocation: "The selected repository redirected to an unrecognized location."
        case .downloadFailed: "Could not complete the request. Check the network and retry."
        case .exceedsLimit: "The response exceeds the allowed size."
        case .wrongFile: "The archive size or SHA-256 differs from the signed release."
        }
    }
}

enum CompanionUpdateSource: String, CaseIterable, Identifiable {
    case github, sourceforge
    var id: Self { self }
    var label: String { self == .github ? "GitHub" : "SourceForge" }

    func archiveURL(_ release: CompanionUpdateRelease) -> URL {
        switch self {
        case .github:
            URL(string: "https://github.com/sev7enITA/AudioEnhancerMAX/releases/download")!
                .appendingPathComponent(release.tag).appendingPathComponent(release.filename)
        case .sourceforge:
            URL(string: "https://downloads.sourceforge.net/project/audioenhancermax")!
                .appendingPathComponent(release.tag).appendingPathComponent(release.filename)
        }
    }

    func allows(_ url: URL, release: CompanionUpdateRelease) -> Bool {
        guard let host = UpdateLocation.httpsHost(url) else { return false }
        switch self {
        case .github:
            let path = url.path
            let assetPath = "^/github-production-release-asset(?:-[a-f0-9]+)?/1292611395/[a-zA-Z0-9-]{16,80}$"
            return url == archiveURL(release) || (host == "release-assets.githubusercontent.com"
                && path.range(of: assetPath, options: .regularExpression) == path.startIndex..<path.endIndex)
        case .sourceforge:
            return (host == "downloads.sourceforge.net" || host.hasSuffix(".dl.sourceforge.net"))
                && url.path == archiveURL(release).path
        }
    }
}

private enum UpdateLocation {
    static func httpsHost(_ url: URL) -> String? {
        guard url.scheme?.lowercased() == "https", url.user == nil, url.password == nil, url.fragment == nil,
              url.port == nil || url.port == 443 else { return nil }
        return url.host?.lowercased()
    }
}

struct CompanionUpdateRelease: Decodable, Sendable {
    let version: String
    let build: Int
    let packageID: String
    let filename: String
    let sha256: String
    let sizeBytes: Int
    let tag: String

    enum CodingKeys: String, CodingKey {
        case version, build, filename, sha256, tag
        case packageID = "package_id"
        case sizeBytes = "size_bytes"
    }

    static let maximumBytes = 200 * 1024 * 1024

    static func versionParts(_ version: String) -> [Int]? {
        let parts = version.split(separator: ".", omittingEmptySubsequences: false)
        guard parts.count == 3, parts.allSatisfy({ validNumber($0, maxDigits: 5) }) else { return nil }
        return parts.compactMap { Int($0) }
    }

    private static func validNumber(_ value: Substring, maxDigits: Int) -> Bool {
        (1...maxDigits).contains(value.utf8.count) && (value.count == 1 || value.first != "0")
            && value.utf8.allSatisfy { (48...57).contains($0) }
    }

    func validate() throws {
        let base = "v\(version)"
        let prefix = base + "-mobile-beta."
        let betaNumber = tag.dropFirst(prefix.count)
        let validTag = tag == base || (tag.hasPrefix(prefix)
            && Self.validNumber(betaNumber, maxDigits: 4) && betaNumber != "0")
        guard Self.versionParts(version) != nil, (1...Int(Int32.max)).contains(build),
              packageID == "com.fabriziodegni.audioenhancermax.companion",
              filename == "AudioEnhancerCompanion-\(version)-build-\(build)-unsigned-xcarchive.zip",
              validTag,
              sha256.utf8.count == 64, sha256.utf8.allSatisfy({ (48...57).contains($0) || (97...102).contains($0) }),
              (1...Self.maximumBytes).contains(sizeBytes) else { throw CompanionUpdateError.invalidRelease }
    }

    enum Comparison { case newer, same, unavailable }

    func compare(installedVersion: String?, installedBuild: Int?) -> Comparison {
        guard let installedVersion, let installedBuild, installedBuild > 0,
              let old = Self.versionParts(installedVersion), let new = Self.versionParts(version) else { return .unavailable }
        if old == new, installedBuild == build { return .same }
        if build > installedBuild, !new.lexicographicallyPrecedes(old) { return .newer }
        return .unavailable
    }
}

struct CompanionUpdateFeed: Decodable, Sendable {
    private struct SignedEnvelope: Decodable { let payload: String; let signature: String }
    private struct Releases: Decodable { let ios: CompanionUpdateRelease }

    let schema: String
    let issuedAt: Int64
    let expiresAt: Int64
    private let releases: Releases
    var release: CompanionUpdateRelease { releases.ios }

    enum CodingKeys: String, CodingKey {
        case schema, releases
        case issuedAt = "issued_at"
        case expiresAt = "expires_at"
    }

    static let maxBytes = 128 * 1024

    static func decode(_ data: Data, publicKey: P256.Signing.PublicKey, now: Date = .now) throws -> Self {
        guard data.count <= maxBytes,
              let envelope = try? JSONDecoder().decode(SignedEnvelope.self, from: data),
              let payload = Data(base64Encoded: envelope.payload), !payload.isEmpty,
              let der = Data(base64Encoded: envelope.signature),
              let signature = try? P256.Signing.ECDSASignature(derRepresentation: der),
              publicKey.isValidSignature(signature, for: payload),
              let feed = try? JSONDecoder().decode(Self.self, from: payload),
              feed.schema == "audioenhancermax.mobile-updates.v1" else { throw CompanionUpdateError.invalidFeed }
        try feed.validateTime(now)
        try feed.release.validate()
        return feed
    }

    func validateTime(_ now: Date = .now) throws {
        let current = Int64(now.timeIntervalSince1970)
        guard issuedAt > 0, issuedAt <= current + 5 * 60, expiresAt > current,
              expiresAt > issuedAt, expiresAt - issuedAt <= 365 * 24 * 60 * 60 else {
            throw CompanionUpdateError.expiredFeed
        }
    }
}

enum CompanionUpdateService {
    static let feedURL = URL(string: "https://www.fabriziodegni.com/AudioEnhancerMAX/updates/companion-v1.json")!

    static func check(bundle: Bundle = .main) async throws -> CompanionUpdateFeed {
        guard let keyURL = bundle.url(forResource: "companion-update-public", withExtension: "pem"),
              let pem = try? String(contentsOf: keyURL, encoding: .utf8),
              let key = try? P256.Signing.PublicKey(pemRepresentation: pem) else {
            throw CompanionUpdateError.invalidFeed
        }
        let transfer = BoundedUpdateTransfer(limit: CompanionUpdateFeed.maxBytes, allows: { $0 == feedURL })
        let outcome = try await transfer.fetch(feedURL)
        return try CompanionUpdateFeed.decode(outcome.data, publicKey: key)
    }

    static func download(_ feed: CompanionUpdateFeed, from source: CompanionUpdateSource) async throws -> URL {
        let folder = try FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask,
                                                 appropriateFor: nil, create: true)
            .appendingPathComponent("VerifiedCompanionArchives", isDirectory: true)
        return try await download(feed, from: source, in: folder) { url, temp, release, allow in
            let transfer = BoundedUpdateTransfer(limit: release.sizeBytes, sink: temp, exactLength: release.sizeBytes, allows: allow)
            return try await transfer.fetch(url)
        }
    }

    // The transfer fills a unique staging file. Only matching verified bytes reach the existing export path.
    static func download(
        _ feed: CompanionUpdateFeed, from source: CompanionUpdateSource, in folder: URL,
        using transfer: (URL, FileHandle, CompanionUpdateRelease, @escaping (URL) -> Bool) async throws -> UpdateTransferResult
    ) async throws -> URL {
        try feed.validateTime()
        let release = feed.release
        try release.validate()
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        let destination = folder.appendingPathComponent(release.filename)
        let staging = folder.appendingPathComponent(".download-\(UUID().uuidString)")
        guard FileManager.default.createFile(atPath: staging.path, contents: nil, attributes: [.posixPermissions: 0o600]) else {
            throw CompanionUpdateError.downloadFailed
        }
        defer { try? FileManager.default.removeItem(at: staging) }
        let file = try FileHandle(forWritingTo: staging)
        defer { try? file.close() }
        let result = try await transfer(source.archiveURL(release), file, release) { source.allows($0, release: release) }
        try Task.checkCancellation()
        try feed.validateTime()
        guard result.size == release.sizeBytes, result.sha256 == release.sha256 else { throw CompanionUpdateError.wrongFile }
        try file.synchronize()
        try file.close()
        guard rename(staging.path, destination.path) == 0 else { throw CompanionUpdateError.downloadFailed }
        return destination
    }
}

struct UpdateTransferResult: Sendable {
    let data: Data
    let size: Int
    let sha256: String
}

private final class BoundedUpdateTransfer: NSObject, URLSessionDataDelegate, @unchecked Sendable {
    private let limit: Int
    private let sink: FileHandle?
    private let exactLength: Int?
    private let allows: (URL) -> Bool
    private let lock = NSLock()
    private var task: URLSessionDataTask?
    private var cancelled = false
    private var continuation: CheckedContinuation<UpdateTransferResult, Error>?
    // Access on the serial URLSession delegate queue after the request starts.
    private var bytes = Data()
    private var count = 0
    private var digestState = SHA256()
    private var failure: Error?
    private var acceptedResponse = false

    init(limit: Int, sink: FileHandle? = nil, exactLength: Int? = nil, allows: @escaping (URL) -> Bool) {
        self.limit = limit
        self.sink = sink
        self.exactLength = exactLength
        self.allows = allows
    }

    func fetch(_ url: URL) async throws -> UpdateTransferResult {
        guard allows(url) else { throw CompanionUpdateError.untrustedLocation }
        return try await withTaskCancellationHandler {
            try Task.checkCancellation()
            return try await withCheckedThrowingContinuation { pending in
                let config = URLSessionConfiguration.ephemeral
                config.urlCache = nil
                config.httpShouldSetCookies = false
                config.timeoutIntervalForRequest = 30
                config.timeoutIntervalForResource = 240
                let queue = OperationQueue()
                queue.maxConcurrentOperationCount = 1
                let session = URLSession(configuration: config, delegate: self, delegateQueue: queue)
                var request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalAndRemoteCacheData)
                request.setValue("identity", forHTTPHeaderField: "Accept-Encoding")
                let next = session.dataTask(with: request)
                let shouldCancel = lock.withLock {
                    continuation = pending
                    task = next
                    return cancelled
                }
                next.resume()
                if shouldCancel { next.cancel() }
            }
        } onCancel: {
            let current = lock.withLock {
                cancelled = true
                return task
            }
            current?.cancel()
        }
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse,
                    newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) {
        if let url = request.url, allows(url) {
            completionHandler(request)
        } else {
            failure = CompanionUpdateError.untrustedLocation
            completionHandler(nil)
        }
    }

    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive response: URLResponse,
                    completionHandler: @escaping (URLSession.ResponseDisposition) -> Void) {
        guard let url = response.url, allows(url) else {
            failure = CompanionUpdateError.untrustedLocation
            completionHandler(.cancel)
            return
        }
        guard let http = response as? HTTPURLResponse, http.statusCode == 200, failure == nil else {
            if failure == nil { failure = CompanionUpdateError.downloadFailed }
            completionHandler(.cancel)
            return
        }
        let advertised = response.expectedContentLength
        guard advertised <= Int64(limit) else {
            failure = CompanionUpdateError.exceedsLimit
            completionHandler(.cancel)
            return
        }
        if let exactLength, advertised >= 0, advertised != Int64(exactLength) {
            failure = CompanionUpdateError.wrongFile
            completionHandler(.cancel)
            return
        }
        acceptedResponse = true
        completionHandler(.allow)
    }

    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive data: Data) {
        guard failure == nil, acceptedResponse else { return }
        guard data.count <= limit - count else {
            failure = CompanionUpdateError.exceedsLimit
            dataTask.cancel()
            return
        }
        do {
            if let sink { try sink.write(contentsOf: data) }
            else { bytes.append(data) }
            digestState.update(data: data)
            count += data.count
        } catch {
            failure = error
            dataTask.cancel()
        }
    }

    func urlSession(_ session: URLSession, task finishedTask: URLSessionTask, didCompleteWithError error: Error?) {
        let result: Result<UpdateTransferResult, Error>
        if let finalError = failure ?? error {
            result = .failure(finalError)
        } else if !acceptedResponse {
            result = .failure(CompanionUpdateError.downloadFailed)
        } else {
            let digest = digestState.finalize().map { String(format: "%02x", $0) }.joined()
            result = .success(UpdateTransferResult(data: bytes, size: count, sha256: digest))
        }
        let pending = lock.withLock {
            task = nil
            let pending = continuation
            continuation = nil
            return pending
        }
        pending?.resume(with: result)
        session.finishTasksAndInvalidate()
    }
}
#endif
