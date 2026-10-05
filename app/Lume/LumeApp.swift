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
/// Relatórios e documentos vêm de variáveis de ambiente (exemplos sintéticos); nada é enviado à API.
@MainActor
enum Snapshot {
    static func render(_ store: ReviewStore, section: LumeSection = .main, size: NSSize = NSSize(width: 1280, height: 820),
                       name: String, dark: Bool, into folder: URL) async {
        await render(AnyView(ContentView(section: section).environmentObject(store)), size: size,
                     name: name, dark: dark, into: folder)
    }

    static func render(_ root: AnyView, size: NSSize, name: String, dark: Bool, into folder: URL) async {
        // LUME_SNAPSHOT_ONLY=prefixo desenha só as telas cujo nome começa com ele.
        if let only = ProcessInfo.processInfo.environment["LUME_SNAPSHOT_ONLY"], !name.hasPrefix(only) { return }
        // Janela real, com barra de ferramentas, para conferir também o topo.
        // Tamanho mínimo, como a janela real (`.frame(minWidth:minHeight:)` na cena); sem isso o
        // controlador encolhe a janela ao tamanho ideal do conteúdo.
        let controller = NSHostingController(rootView: AnyView(root.frame(minWidth: size.width, minHeight: size.height)))
        controller.sizingOptions = .minSize
        if #available(macOS 14, *) { controller.sceneBridgingOptions = [.toolbars, .title] }
        let window = NSWindow(contentRect: NSRect(origin: CGPoint(x: 40, y: 40), size: size),
                              styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
                              backing: .buffered, defer: false)
        window.contentViewController = controller
        window.toolbarStyle = .unified
        // A janela Sobre usa título oculto, como na cena real (.hiddenTitleBar).
        if name.hasPrefix("sobre") { window.titlebarAppearsTransparent = true; window.titleVisibility = .hidden }
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

    /// Store com motor (só para a tela o considerar pronto) e, se pedido, relatório e documento.
    static func store(report: String? = nil, document: String? = nil, select: ((ReviewStore) -> String?)? = nil) -> ReviewStore {
        let store = ReviewStore()
        if let engine = ProcessInfo.processInfo.environment["LUME_SNAPSHOT_ENGINE"] {
            store.debugUseEngine(URL(fileURLWithPath: engine))
        }
        if let report { try? store.debugLoadReport(URL(fileURLWithPath: report)) }
        if let document { store.documentURL = URL(fileURLWithPath: document) }
        if let select { store.selectedID = select(store) }
        return store
    }

    static func run(into folder: URL) async {
        try? FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        let env = ProcessInfo.processInfo.environment
        // Ligar a IA nas capturas grava em UserDefaults; os valores do autor voltam no fim.
        let defaults = UserDefaults.standard
        let saved = ["auditAI", "coherenceAI"].map { ($0, defaults.object(forKey: $0)) }
        defer { for (key, value) in saved { if let value { defaults.set(value, forKey: key) } else { defaults.removeObject(forKey: key) } } }

        // Ícone do app: símbolo na grade de ícones do macOS (824 de 1024, com sombra).
        let icon = ImageRenderer(content: LumeMark(size: 824, glowing: false).compositingGroup()
            .shadow(color: .black.opacity(0.3), radius: 18, y: 12)
            .frame(width: 1024, height: 1024))
        icon.scale = 1
        if let image = icon.cgImage {
            try? NSBitmapImageRep(cgImage: image).representation(using: .png, properties: [:])?
                .write(to: folder.appendingPathComponent("icone-1024.png"))
        }
        let firstAudit: (ReviewStore) -> String? = { $0.report?.findings.first { $0.module == "audit" }?.id }
        let first: (ReviewStore) -> String? = { $0.filteredFindings.first?.id }
        for dark in [false, true] {
            await render(store(), name: "01-inicio", dark: dark, into: folder)
            if let document = env["LUME_SNAPSHOT_REPORT_DOC"] {
                let preparing = store(document: document)
                preparing.useCoherenceAI = true
                preparing.useAuditAI = true
                await render(preparing, name: "02-preparacao", dark: dark, into: folder)
                preparing.useCoherenceAI = false
                preparing.useAuditAI = false
            }
            let reading = store(document: env["LUME_SNAPSHOT_REPORT_DOC"])
            reading.debugShowReading([
                AnalysisStage(module: "linguistic", title: "Revisão linguística", state: "completed", finding_count: 42, coverage: "partial", detail: ""),
                AnalysisStage(module: "morphosyntactic", title: "Análise morfossintática", state: "completed", finding_count: 17, coverage: "partial", detail: ""),
                AnalysisStage(module: "editorial", title: "Contexto curto", state: "completed", finding_count: 9, coverage: "partial", detail: ""),
                AnalysisStage(module: "global_coherence", title: "Coerência global", state: "skipped", finding_count: 0, coverage: "partial", detail: ""),
                AnalysisStage(module: "audit", title: "Auditoria final", state: "running", finding_count: 0, coverage: "partial", detail: "", done: 2, total: 5, unit: "trechos"),
            ])
            await render(reading, name: "03-analise-auditoria", dark: dark, into: folder)
            if let report = env["LUME_SNAPSHOT_REPORT"] {
                let doc = env["LUME_SNAPSHOT_REPORT_DOC"]
                await render(store(report: report, document: doc, select: first), name: "04-mesa-tempo-contradito-docx", dark: dark, into: folder)
                let resting = store(report: report, document: doc)
                resting.selectedID = nil
                await render(resting, name: "05-mesa-sem-selecao", dark: dark, into: folder)
                await render(store(report: report, document: doc, select: first), size: NSSize(width: 1060, height: 820),
                             name: "06-mesa-estreita", dark: dark, into: folder)
            }
            if let report = env["LUME_SNAPSHOT_AUDIT_REPORT"] {
                await render(store(report: report, document: env["LUME_SNAPSHOT_AUDIT_DOC"], select: firstAudit),
                             name: "07-mesa-auditoria", dark: dark, into: folder)
            }
            if let report = env["LUME_SNAPSHOT_PAGES_REPORT"] {
                await render(store(report: report, document: env["LUME_SNAPSHOT_PAGES_DOC"], select: first),
                             name: "08-mesa-pages", dark: dark, into: folder)
            }
            let settings = store(document: env["LUME_SNAPSHOT_REPORT_DOC"])
            await render(AnyView(SearchSettingsView().environmentObject(settings)), size: NSSize(width: 780, height: 640),
                         name: "09-ajustar", dark: dark, into: folder)
            await render(store(), section: .engine, name: "10-motor", dark: dark, into: folder)
            let logged = store()
            if let log = env["LUME_SNAPSHOT_LOG"] { logged.logURL = URL(fileURLWithPath: log) }
            await render(logged, section: .log, name: "11-registro", dark: dark, into: folder)
            if env["LUME_SNAPSHOT_ENGINE"] != nil {
                await render(AnyView(SobreView().environmentObject(store())), size: NSSize(width: 920, height: 600),
                             name: "sobre", dark: dark, into: folder)
            }
        }
    }
}
#endif
