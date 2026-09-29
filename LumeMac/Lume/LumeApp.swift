import SwiftUI
import AppKit

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
    func applicationDidFinishLaunching(_ notification: Notification) {
        #if DEBUG
        if let folder = ProcessInfo.processInfo.environment["LUME_SNAPSHOT"] {
            Task { @MainActor in await Snapshot.run(into: URL(fileURLWithPath: folder)); exit(0) }
        }
        #endif
    }
    func applicationWillTerminate(_ notification: Notification) {
        PythonRunner.shared.cancel()
    }
}

@main
@MainActor
struct LumeApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var delegate
    @StateObject private var store = ReviewStore()

    var body: some Scene {
        Window("Lume", id: "main") {
            ContentView().environmentObject(store)
                .frame(minWidth: 1040, minHeight: 680)
        }
        .defaultSize(width: 1280, height: 820)
        .commands {
            CommandGroup(replacing: .newItem) {
                Button("Escolher manuscrito…") { store.chooseDocument() }
                    .keyboardShortcut("o").disabled(store.isBusy)
                Button("Abrir relatório JSON…") { store.chooseReport() }
                    .keyboardShortcut("o", modifiers: [.command, .shift]).disabled(store.isBusy)
            }
            CommandGroup(after: .saveItem) {
                Button("Exportar decisões…") { store.exportDecisions() }
                    .keyboardShortcut("s").disabled(store.report == nil || store.isBusy)
            }
        }
    }
}

#if DEBUG
/// Renderiza as telas principais em PNG, nos modos claro e escuro, sem janela visível.
@MainActor
enum Snapshot {
    static func render(_ store: ReviewStore, name: String, dark: Bool, into folder: URL) async {
        let view = NSHostingView(rootView: ContentView().environmentObject(store))
        view.appearance = NSAppearance(named: dark ? .darkAqua : .aqua)
        view.frame = NSRect(x: 0, y: 0, width: 1280, height: 820)
        let window = NSWindow(contentRect: view.frame, styleMask: [.borderless], backing: .buffered, defer: false)
        window.contentView = view
        window.appearance = view.appearance
        try? await Task.sleep(nanoseconds: 700_000_000)
        view.layoutSubtreeIfNeeded()
        guard let rep = view.bitmapImageRepForCachingDisplay(in: view.bounds) else { return }
        view.cacheDisplay(in: view.bounds, to: rep)
        try? rep.representation(using: .png, properties: [:])?
            .write(to: folder.appendingPathComponent("\(name)-\(dark ? "escuro" : "claro").png"))
    }

    static func run(into folder: URL) async {
        try? FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        let env = ProcessInfo.processInfo.environment
        // Ícone do app: símbolo na grade de ícones do macOS (824 de 1024, com sombra).
        let icon = ImageRenderer(content: LumeMark(size: 824, glowing: true)
            .shadow(color: .black.opacity(0.3), radius: 18, y: 12)
            .frame(width: 1024, height: 1024))
        icon.scale = 1
        if let image = icon.cgImage {
            try? NSBitmapImageRep(cgImage: image).representation(using: .png, properties: [:])?
                .write(to: folder.appendingPathComponent("icone-1024.png"))
        }
        for dark in [false, true] {
            let store = ReviewStore()
            await render(store, name: "1-inicio", dark: dark, into: folder)
            store.debugShowReading([
                AnalysisStage(module: "linguistic", title: "Linguístico", state: "completed", finding_count: 42, coverage: "", detail: ""),
                AnalysisStage(module: "morphosyntactic", title: "Morfossintático", state: "running", finding_count: 0, coverage: "", detail: "", done: 420, total: 1274, unit: "parágrafos"),
                AnalysisStage(module: "global_coherence", title: "Coerência com IA", state: "pending", finding_count: 0, coverage: "", detail: ""),
            ])
            await render(store, name: "2-lendo", dark: dark, into: folder)
            store.debugReset()
            if let report = env["LUME_SNAPSHOT_REPORT"] {
                try? store.debugLoadReport(URL(fileURLWithPath: report))
                if let index = env["LUME_SNAPSHOT_INDEX"].flatMap(Int.init), store.filteredFindings.indices.contains(index) {
                    store.selectedID = store.filteredFindings[index].id
                }
                await render(store, name: "3-mesa", dark: dark, into: folder)
                store.selectedID = nil
                await render(store, name: "4-mesa-vazia", dark: dark, into: folder)
            }
        }
    }
}
#endif
