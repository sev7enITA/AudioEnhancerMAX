import SwiftUI
import UIKit
import UniformTypeIdentifiers

struct MusicDraft: Codable, Equatable {
    var description = ""
    var style = "Ambient"
    var instruments = "Piano, soft strings"
    var exclusions = ""
    var vocals = "Instrumental"
    var duration = "30"
    var bpm = "90"
    var lyrics = ""
    var arrangement = "Opening; development; ending"
    var prompt = ""
    var builtSource = ""

    private var source: String {
        [description, style, instruments, exclusions, vocals, duration, bpm, lyrics, arrangement]
            .joined(separator: "\u{001F}")
    }
    var ready: Bool {
        guard !description.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              let seconds = Int(duration), (5...600).contains(seconds),
              let tempo = Int(bpm), (30...240).contains(tempo) else { return false }
        return source.utf8.count <= 12000
    }
    var canExport: Bool {
        ready && !prompt.isEmpty && builtSource == source && prompt.utf8.count <= 12000
    }
    mutating func build() throws {
        guard ready, let seconds = Int(duration), let tempo = Int(bpm) else {
            throw CompanionError.message("Add a direction, duration 5–600 seconds and tempo 30–240 BPM.")
        }
        func clean(_ value: String) -> String { value.trimmingCharacters(in: .whitespacesAndNewlines) }
        var metadata = ["GLOBAL METADATA", clean(description), "Target: \(seconds) seconds · \(tempo) BPM"]
        for (title, value) in [("Style", style), ("Palette", instruments), ("Avoid", exclusions)] {
            if !clean(value).isEmpty { metadata.append("\(title): \(clean(value))") }
        }
        let vocalDirection = clean(vocals).isEmpty ? "Instrumental" : clean(vocals)
        let structure = clean(arrangement).isEmpty ? "Opening, development and controlled ending." : clean(arrangement)
        let result = metadata.joined(separator: "\n")
            + "\n\nVOCAL DETAILS\n\(vocalDirection)\n\nARRANGEMENT\n\(structure)"
        guard result.utf8.count <= 12000 else {
            throw CompanionError.message("Shorten the brief before sharing.")
        }
        prompt = result
        builtSource = source
    }
}

private struct BriefPreset: Codable, Identifiable {
    var id: String { name }
    let name: String
    let summary: String
    let style: String
    let instruments: String
    let exclusions: String
    let vocals: String
    let duration: String
    let bpm: String
    let arrangement: String

    static let templates: [Self] = {
        guard let url = Bundle.main.url(forResource: "music-brief-presets", withExtension: "json"),
              let data = try? Data(contentsOf: url) else { return [] }
        return (try? JSONDecoder().decode([Self].self, from: data)) ?? []
    }()

    func apply(to draft: inout MusicDraft) {
        draft.style = style
        draft.instruments = instruments
        draft.exclusions = exclusions
        draft.vocals = vocals
        draft.duration = duration
        draft.bpm = bpm
        draft.arrangement = arrangement
    }
}

struct MusicBriefView: View {
    @ObservedObject var model: CompanionModel
    @State private var template: BriefPreset?
    @State private var editingDetails = false
    @State private var importing = false
    @State private var textURL: URL?
    @State private var jsonURL: URL?
    @State private var copied = false

    private var recordingSeconds: Int? {
        guard let duration = model.source?.duration, duration >= 4.5, duration < 600.5 else { return nil }
        return Int(duration.rounded())
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                Text("Turn a scene, recording or project into a shareable music direction.")
                    .font(.subheadline).foregroundStyle(.secondary)
                templatesCard
                directionCard
                previewCard
            }
            .frame(maxWidth: 700)
            .padding()
            .frame(maxWidth: .infinity)
        }
        .scrollDismissesKeyboard(.interactively)
        .navigationTitle("Music brief")
        .fileImporter(isPresented: $importing, allowedContentTypes: [.json], onCompletion: openBrief)
        .task(id: model.music) {
            copied = false
            textURL = nil
            jsonURL = nil
            guard model.music.canExport else { return }
            do {
                textURL = try model.briefTextExport()
                jsonURL = try model.briefExport()
            } catch {
                model.error = error.localizedDescription
            }
        }
    }

    private var templatesCard: some View {
        card("Start from a use case", icon: "square.grid.2x2") {
            ScrollView(.horizontal) {
                HStack {
                    ForEach(BriefPreset.templates) { preset in
                        Button(preset.name) { template = preset }
                            .buttonStyle(.bordered)
                    }
                }
            }
            .scrollIndicators(.hidden)
            if let template {
                Text(template.summary).font(.subheadline).foregroundStyle(.secondary)
                Button("Apply \(template.name) preset") {
                    template.apply(to: &model.music)
                    self.template = nil
                }
            }
        }
    }

    private var directionCard: some View {
        card("Direction", icon: "slider.horizontal.3") {
            field("What should the music do?", text: $model.music.description, lines: 3)
            HStack(alignment: .top, spacing: 12) {
                field("Seconds", text: $model.music.duration).keyboardType(.numberPad)
                field("BPM", text: $model.music.bpm).keyboardType(.numberPad)
            }
            if let seconds = recordingSeconds, Int(model.music.duration) != seconds {
                Button("Match recording · \(seconds) s") { model.music.duration = String(seconds) }
            }
            field("Style and mood", text: $model.music.style)
            field("Structure and timing", text: $model.music.arrangement, lines: 2)
            DisclosureGroup("Palette and vocals", isExpanded: $editingDetails) {
                VStack(alignment: .leading, spacing: 12) {
                    field("Instrument palette", text: $model.music.instruments)
                    field("Avoid", text: $model.music.exclusions)
                    field("Vocal direction", text: $model.music.vocals)
                    field("Separate lyrics for the JSON", text: $model.music.lyrics, lines: 2)
                }.padding(.top, 10)
            }.padding(.vertical, 4)
        }
    }

    private var previewCard: some View {
        card("Brief preview", icon: "text.alignleft") {
            if model.music.canExport {
                Text(model.music.prompt).font(.body).textSelection(.enabled)
                Button(copied ? "Copied" : "Copy brief", systemImage: "doc.on.doc") {
                    UIPasteboard.general.string = model.music.prompt
                    copied = true
                }.buttonStyle(.borderedProminent)
                ViewThatFits(in: .horizontal) {
                    HStack { shareActions }
                    VStack(alignment: .leading) { shareActions }
                }
            } else {
                if !model.music.ready {
                    Text("Add a direction, 5–600 seconds and 30–240 BPM.")
                        .font(.subheadline).foregroundStyle(.secondary)
                }
                Button(model.music.prompt.isEmpty ? "Build preview" : "Refresh preview") {
                    do { try model.music.build() }
                    catch { model.error = error.localizedDescription }
                }.buttonStyle(.borderedProminent).disabled(!model.music.ready)
            }
            Button("Import brief JSON", systemImage: "square.and.arrow.down") { importing = true }
        }
    }

    @ViewBuilder private var shareActions: some View {
        if let textURL { ShareLink(item: textURL) { Label("Share text", systemImage: "square.and.arrow.up") } }
        if let jsonURL { ShareLink(item: jsonURL) { Label("Share JSON", systemImage: "doc") } }
    }

    private func field(_ label: String, text: Binding<String>, lines: Int = 1) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label).font(.caption.weight(.semibold)).foregroundStyle(.secondary)
            TextField(label, text: text, axis: lines == 1 ? .horizontal : .vertical)
                .lineLimit(lines...max(lines, 4))
                .textFieldStyle(.roundedBorder)
                .accessibilityLabel(label)
        }.frame(maxWidth: .infinity)
    }

    private func card<Content: View>(_ title: String, icon: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Label(title, systemImage: icon).font(.headline)
            content()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 20))
    }

    private func openBrief(_ result: Result<URL, Error>) {
        do {
            let url = try result.get()
            let access = url.startAccessingSecurityScopedResource()
            defer { if access { url.stopAccessingSecurityScopedResource() } }
            guard (try url.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? Int.max) <= 65_536 else {
                throw CompanionError.message("Brief JSON is too large.")
            }
            model.music = try JSONDecoder().decode(MusicDraft.self, from: Data(contentsOf: url))
        } catch {
            model.error = error.localizedDescription
        }
    }
}
