import SwiftUI

struct CompanionUpdatesView: View {
    #if AEMAX_APP_STORE
    var body: some View {
        Form {
            Section("App Store") {
                Text("Open the iOS companion in the App Store to manage updates.")
                if let listing = Bundle.main.object(forInfoDictionaryKey: "AEMAXIOSAppStoreID") as? String,
                   let url = CompanionDistribution.appStoreURL(listingID: listing) {
                    Link(destination: url) { Label("Open in App Store", systemImage: "arrow.up.right.square") }
                } else {
                    Text("The iOS companion listing is unavailable. Use the Updates section in the App Store.")
                        .foregroundStyle(.secondary)
                }
            }
        }
        .navigationTitle("Updates")
    }
    #else
    @AppStorage("companionUpdateSource") private var sourcePreference = ""
    @State private var release: CompanionUpdateFeed?
    @State private var sharedArchive: URL?
    @State private var status: String?
    @State private var operation: Task<Void, Never>?
    @State private var work: String?

    private var source: CompanionUpdateSource? { CompanionUpdateSource(rawValue: sourcePreference) }

    var body: some View {
        Form {
            Section("Developer archive") {
                Text("Save a verified unsigned Xcode archive to Files or share it with a Mac. Xcode handles signing and installation.")
                Picker("Repository", selection: $sourcePreference) {
                    Text("Choose a source").tag("")
                    ForEach(CompanionUpdateSource.allCases) { source in
                        Text(source.label).tag(source.rawValue)
                    }
                }
                .disabled(work != nil)
                .accessibilityIdentifier("companion-update-source")
                Button("Check for updates", systemImage: "arrow.clockwise") { check() }
                    .disabled(source == nil || work != nil)
                    .accessibilityIdentifier("companion-check-updates")
                if let work {
                    ProgressView(work)
                    Button("Cancel", role: .cancel) { operation?.cancel() }
                }
                if let status {
                    Text(status).font(.subheadline).foregroundStyle(.secondary)
                        .accessibilityIdentifier("companion-update-status")
                }
            }
            if let release, let source {
                Section("Verified release metadata") {
                    LabeledContent("Version", value: "\(release.release.version) (\(release.release.build))")
                    LabeledContent("Archive size", value: ByteCountFormatter.string(fromByteCount: Int64(release.release.sizeBytes), countStyle: .file))
                    Button("Download from \(source.label)", systemImage: "arrow.down.circle") { download(release, from: source) }
                        .disabled(work != nil)
                        .accessibilityIdentifier("companion-download-update")
                }
            }
            if let sharedArchive {
                Section("Saved archive") {
                    ShareLink(item: sharedArchive) { Label("Share verified archive", systemImage: "square.and.arrow.up") }
                        .accessibilityIdentifier("companion-share-update")
                }
            }
        }
        .navigationTitle("Updates")
        .onDisappear { operation?.cancel() }
    }

    private func check() {
        guard source != nil, work == nil else { return }
        release = nil
        run("Checking signed release…") {
            let feed = try await CompanionUpdateService.check()
            let installedVersion = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String
            let installedBuild = (Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String).flatMap { Int($0) }
            try Task.checkCancellation()
            switch feed.release.compare(installedVersion: installedVersion, installedBuild: installedBuild) {
            case .newer:
                release = feed
                status = "A newer developer release is available."
            case .same:
                release = feed
                status = "You’re on the latest developer build."
            case .unavailable:
                status = "No newer developer archive is available for this build."
            }
        }
    }

    private func download(_ feed: CompanionUpdateFeed, from source: CompanionUpdateSource) {
        guard work == nil else { return }
        run("Downloading from \(source.label)…") {
            let url = try await CompanionUpdateService.download(feed, from: source)
            try Task.checkCancellation()
            sharedArchive = url
            status = "Archive saved. SHA-256 and size verified."
        }
    }

    private func run(_ label: String, action: @escaping @MainActor () async throws -> Void) {
        work = label
        status = nil
        operation = Task {
            defer {
                work = nil
                operation = nil
            }
            do {
                try await action()
            } catch {
                status = if Task.isCancelled { "Request cancelled." }
                         else { (error as? CompanionUpdateError)?.localizedDescription ?? "Could not complete the request. Try again." }
            }
        }
    }
    #endif
}
