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
            SobreCommands()
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
        Window("Sobre o Lume", id: "sobre") {
            SobreView().environmentObject(store)
        }
        .windowStyle(.hiddenTitleBar)
        .windowResizability(.contentMinSize)
        .defaultSize(width: 920, height: 600)
    }
}

#if DEBUG
/// Renderiza as telas principais em PNG, nos modos claro e escuro, sem janela visível.
@MainActor
enum Snapshot {
    static func render(_ store: ReviewStore, name: String, dark: Bool, into folder: URL) async {
        await render(AnyView(ContentView().environmentObject(store)), size: NSSize(width: 1280, height: 820),
                     name: name, dark: dark, into: folder)
    }

    static func render(_ root: AnyView, size: NSSize, name: String, dark: Bool, into folder: URL) async {
        // Janela real, com barra de ferramentas, para conferir também o topo.
        let controller = NSHostingController(rootView: root)
        if #available(macOS 14, *) { controller.sceneBridgingOptions = [.toolbars, .title] }
        let window = NSWindow(contentRect: NSRect(origin: CGPoint(x: 40, y: 40), size: size),
                              styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
                              backing: .buffered, defer: false)
        window.contentViewController = controller
        window.toolbarStyle = .unified
        // A janela Sobre usa título oculto, como na cena real (.hiddenTitleBar).
        if name.hasPrefix("5-") { window.titlebarAppearsTransparent = true; window.titleVisibility = .hidden }
        window.appearance = NSAppearance(named: dark ? .darkAqua : .aqua)
        window.setContentSize(size)
        window.orderFrontRegardless()
        try? await Task.sleep(nanoseconds: 1_200_000_000)
        guard let frame = window.contentView?.superview,
              let rep = frame.bitmapImageRepForCachingDisplay(in: frame.bounds) else { return }
        frame.cacheDisplay(in: frame.bounds, to: rep)
        try? rep.representation(using: .png, properties: [:])?
            .write(to: folder.appendingPathComponent("\(name)-\(dark ? "escuro" : "claro").png"))
        window.orderOut(nil)
    }

    static func run(into folder: URL) async {
        try? FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        let env = ProcessInfo.processInfo.environment
        if let engine = env["LUME_SNAPSHOT_ABOUT"] {
            for dark in [false, true] {
                let store = ReviewStore()
                store.debugUseEngine(URL(fileURLWithPath: engine))
                await render(AnyView(SobreView().environmentObject(store)), size: NSSize(width: 920, height: 600),
                             name: "5-sobre", dark: dark, into: folder)
            }
        }
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
