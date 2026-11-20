import SwiftUI

@main struct CompanionApp: App {
    @StateObject private var model = CompanionModel()
    @Environment(\.scenePhase) private var phase

    var body: some Scene {
        WindowGroup {
            CompanionView()
                .environmentObject(model)
                .preferredColorScheme(.dark)
                .tint(WorkspaceColor.mint)
                .onChange(of: phase) { _, next in
                    if next != .active {
                        model.stopWorker()
                        model.stopPlayback()
                        model.suspendPresence()
                    }
                }
        }
    }
}

private struct CompanionView: View {
    @EnvironmentObject private var model: CompanionModel
    @Environment(\.scenePhase) private var phase
    @State private var tab = Page.studio
    @StateObject private var verification = VerificationWorkspace()

    private enum Page { case studio, verify, connection, music, about }

    var body: some View {
        TabView(selection: $tab) {
            NavigationStack { StudioView(openConnection: { tab = .connection }, openVerification: { tab = .verify }) }
                .tabItem { Label("Studio", systemImage: "waveform") }.tag(Page.studio)
            NavigationStack { VerifyContentView(workspace: verification) }
                .tabItem { Label("Verify", systemImage: "checkmark.shield") }.tag(Page.verify)
            NavigationStack { ConnectionView { tab = .studio } }
                .tabItem { Label("Connection", systemImage: "desktopcomputer") }.tag(Page.connection)
            NavigationStack { MusicBriefView(model: model) }
                .tabItem { Label("Music brief", systemImage: "music.note.list") }.tag(Page.music)
            NavigationStack { CompanionAboutView() }
                .tabItem { Label("About", systemImage: "info.circle") }.tag(Page.about)
        }
        .onOpenURL { url in
            guard url.isFileURL else { return }
            tab = .verify
            verification.verify(url)
        }
        .onChange(of: phase) { _, next in
            if next == .background { verification.cancel() }
        }
        .task(id: phase) {
            while phase == .active && !Task.isCancelled {
                await model.refreshConnection()
                do { try await Task.sleep(for: .seconds(5)) }
                catch { break }
            }
        }
        .alert("AudioEnhancerMAX", isPresented: Binding(
            get: { model.error != nil },
            set: { if !$0 { model.error = nil } }
        )) {
            Button("OK") { model.error = nil }
        } message: {
            Text(model.error ?? "")
        }
    }
}

private struct CompanionAboutView: View {
    private let version = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "—"
    private let build = Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "—"

    var body: some View {
        Form {
            Section {
                HStack(spacing: 16) {
                    Image("BrandMark")
                        .resizable()
                        .scaledToFit()
                        .frame(width: 60, height: 60)
                        .accessibilityHidden(true)
                    VStack(alignment: .leading, spacing: 4) {
                        Text("AudioEnhancerMAX").font(.headline)
                        Text("iOS Companion").font(.subheadline).foregroundStyle(.secondary)
                    }
                }
                LabeledContent("Version", value: version)
                LabeledContent("Build", value: build)
                LabeledContent("Channel", value: CompanionDistribution.appStore ? "App Store" : "Developer BETA")
                LabeledContent("Developer", value: "Fabrizio Degni")
            }
            Section {
                NavigationLink {
                    CompanionUpdatesView()
                } label: {
                    Label("Updates", systemImage: "arrow.down.circle")
                }
                .accessibilityIdentifier("companion-updates")
            }
            Section("Support and privacy") {
                Link(destination: URL(string: "https://www.fabriziodegni.com/AudioEnhancerMAX/support.html")!) {
                    Label("Support and contact", systemImage: "questionmark.circle")
                }
                Link(destination: URL(string: "https://www.fabriziodegni.com/AudioEnhancerMAX/privacy.html")!) {
                    Label("Privacy policy", systemImage: "hand.raised")
                }
            }
            #if !AEMAX_APP_STORE
            Section("Project") {
                Link(destination: URL(string: "https://github.com/sev7enITA/AudioEnhancerMAX")!) {
                    Label("Source code and license", systemImage: "curlybraces")
                }
            }
            #endif
        }
        .navigationTitle("About")
    }
}
