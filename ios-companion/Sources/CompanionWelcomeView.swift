import SwiftUI

struct CompanionBuildIdentity {
    let version: String
    let build: String

    static let installed = CompanionBuildIdentity(
        version: Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "—",
        build: Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "—"
    )

    var presentationKey: String { "\(version)+\(build)" }
    var showsMediaMetadataNotes: Bool { version == "4.1.2" && build == "14" }

    func needsWelcome(after lastPresented: String) -> Bool {
        presentationKey != lastPresented
    }
}

struct CompanionWelcomeView: View {
    @Environment(\.dismiss) private var dismiss
    private let identity = CompanionBuildIdentity.installed

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    hero
                    highlights
                    Button {
                        dismiss()
                    } label: {
                        Label("Continue", systemImage: "arrow.right")
                            .frame(maxWidth: .infinity, minHeight: 36)
                    }
                    .buttonStyle(.borderedProminent)
                    .foregroundStyle(WorkspaceColor.background)
                    .accessibilityIdentifier("dismiss-companion-welcome")
                    resources
                }
                .padding(20)
                .frame(maxWidth: 610)
                .frame(maxWidth: .infinity)
            }
            .background(WorkspaceColor.background)
            .navigationTitle("Welcome")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Close") { dismiss() } } }
        }
    }

    private var hero: some View {
        VStack(alignment: .leading, spacing: 14) {
            Image("BrandMark").resizable().scaledToFit().frame(width: 76, height: 76).accessibilityHidden(true)
            Text("AudioEnhancerMAX").font(.title.weight(.bold))
            Text("iOS Companion · \(identity.version) (\(identity.build))")
                .font(.subheadline.monospacedDigit().weight(.semibold)).foregroundStyle(WorkspaceColor.mint)
                .accessibilityIdentifier("welcome-build-identity")
            Text("Edit recordings on your phone, inspect media and C2PA credentials, and continue on your Mac.")
                .font(.subheadline).foregroundStyle(WorkspaceColor.muted)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(20)
        .background(
            LinearGradient(colors: [WorkspaceColor.surface, WorkspaceColor.blue.opacity(0.16)],
                           startPoint: .topLeading, endPoint: .bottomTrailing),
            in: RoundedRectangle(cornerRadius: 20)
        )
        .overlay { RoundedRectangle(cornerRadius: 20).strokeBorder(WorkspaceColor.line) }
    }

    private var highlights: some View {
        VStack(alignment: .leading, spacing: 15) {
            Text(identity.showsMediaMetadataNotes ? "What’s new" : "Explore the companion")
                .font(.headline)
                .accessibilityAddTraits(.isHeader)
            if identity.showsMediaMetadataNotes {
                highlight("Media metadata", "See codec, duration, track details and supported tag standards in Verify.", "list.bullet.rectangle")
                highlight("Embedded artwork EXIF", "Read camera and exposure fields from eligible photos embedded in a media file.", "camera.aperture")
                highlight("Import format guide", "Find the formats and codec limits for editing in Studio.", "doc.badge.gearshape")
            } else {
                highlight("Studio", "Import and edit audio on your device.", "waveform")
                highlight("Verify", "Inspect media and C2PA Content Credentials.", "checkmark.shield")
                highlight("Connection", "Pair your companion with a Mac on Wi-Fi.", "desktopcomputer")
            }
        }
        .workspaceCard()
    }

    private func highlight(_ title: String, _ summary: String, _ symbol: String) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: symbol)
                .frame(width: 28)
                .foregroundStyle(WorkspaceColor.mint)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 4) {
                Text(title).font(.subheadline.weight(.semibold))
                Text(summary).font(.subheadline).foregroundStyle(WorkspaceColor.muted)
            }
        }
        .accessibilityElement(children: .combine)
    }

    private var resources: some View {
        VStack(alignment: .leading, spacing: 12) {
            #if !AEMAX_APP_STORE
            Link(destination: URL(string: "https://www.fabriziodegni.com/AudioEnhancerMAX/companion.html")!) {
                Label("Official companion page", systemImage: "safari")
            }
            #endif
            Link(destination: URL(string: "https://www.fabriziodegni.com/AudioEnhancerMAX/support.html")!) {
                Label("Support", systemImage: "questionmark.circle")
            }
            Link(destination: URL(string: "https://www.fabriziodegni.com/AudioEnhancerMAX/privacy.html")!) {
                Label("Privacy", systemImage: "hand.raised")
            }
        }.frame(maxWidth: .infinity, alignment: .leading)
    }
}
