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

    /// Telas do Validador de decisões com resultados sintéticos: nada é enviado e nenhuma decisão real muda.
    static func renderValidator(report: String, document: String?, dark: Bool, into folder: URL) async {
        let base = store(report: report, document: document)
        guard let findings = base.report?.findings, findings.count >= 3 else { return }
        let kinds: [ReviewDecision] = [.style, .falsePositive, .intentional, .accepted, .error]
        for (index, finding) in findings.prefix(8).enumerated() { base.decisions[finding.id] = kinds[index % kinds.count] }
        base.selectedID = nil
        base.deskSection = .validation
        await render(base, name: "12-validador-mesa", dark: dark, into: folder)

        func estimate(_ pending: Int, reused: Int = 0, lost: Int = 0, minimum: Double = 0.68) -> ValidatorEstimate {
            ValidatorEstimate(triagem: "claude-haiku-5-5", juiz: "claude-sonnet-5-5", elegiveis: pending + reused + lost,
                              aAvaliar: pending, reaproveitadas: reused, naoLocalizadas: lost,
                              titulosAEnviar: ["Capítulo 1", "Capítulo 2", "Capítulo 3", "Capítulo 4", "Capítulo 5", "Capítulo 6", "Capítulo 7"],
                              custoEstimadoUsd: 0.2932, custoMaximoUsd: 0.7573, tetoMinimoUsd: minimum,
                              pedidosTriagem: 13, pedidosJuizEstimados: 9, pedidosJuizMaximo: 24)
        }
        func desk(_ s: ReviewStore) -> ReviewStore { s.deskSection = .validation; s.selectedID = nil; return s }
        let confirm = desk(store(report: report, document: document))
        confirm.decisions = base.decisions
        confirm.validatorEstimate = estimate(71, lost: 3)
        await render(confirm, name: "13-validador-confirmar", dark: dark, into: folder)
        confirm.validatorBudget = 0.25
        await render(confirm, name: "14-validador-teto-baixo", dark: dark, into: folder)
        confirm.validatorEstimate = estimate(0, reused: 12)
        await render(confirm, name: "15-validador-sem-envio", dark: dark, into: folder)

        let ids = findings.prefix(4).map(\.id)
        func item(_ n: Int, _ state: String, issue: Bool = false, long: Bool = false) -> ValidatedDecision {
            ValidatedDecision(id: ids[n], decisao: base.decisions[ids[n]]?.rawValue ?? "", estado: state, classe: "A",
                              modeloFinal: "claude-sonnet-5-5",
                              explicacao: long ? String(repeating: "O verbo está no singular enquanto o sujeito está no plural, o que quebra a concordância. ", count: 4)
                                               : "O verbo está no singular e o sujeito no plural: isso quebra a concordância.",
                              evidencias: ["as caixas que estava"], recomendacao: "Reconsiderar a decisão; a forma “estavam” corrige.",
                              questaoIndependente: issue ? ValidatorIssue(trecho: "a cliente", explicacao: "Falta o acento indicativo de crase.") : nil)
        }
        func summary(_ evaluated: Int, _ missing: Int, partial: Bool) -> ValidatorSummary {
            ValidatorSummary(elegiveis: evaluated + missing, avaliadas: evaluated, naoAvaliadas: missing, contestadas: 2,
                             reaproveitadas: 5, interrompida: partial, custoUsd: 0.1342)
        }
        let results = desk(store(report: report, document: document))
        results.decisions = base.decisions
        results.validation = DecisionValidation(summary: summary(71, 0, partial: false),
                                                contested: [item(0, "contestada", long: true), item(1, "contestada", issue: true)],
                                                independent: [item(2, "apontamento_inadequado", issue: true)], unevaluated: 0)
        await render(results, name: "16-validador-resultados", dark: dark, into: folder)
        results.validation = DecisionValidation(summary: summary(40, 31, partial: true),
                                                contested: [item(0, "contestada")], independent: [], unevaluated: 31)
        await render(results, name: "17-validador-parcial", dark: dark, into: folder)
        results.validation = DecisionValidation(summary: summary(71, 0, partial: false), contested: [], independent: [], unevaluated: 0)
        await render(results, name: "18-validador-vazio", dark: dark, into: folder)
    }

    /// Validador V5 (padrão): fluxo visual com fixtures. Nada é enviado e nenhuma decisão real muda.
    static func renderSecondOpinion(report: String, document: String?, fixture: String, dark: Bool, into folder: URL) async {
        guard let raw = try? Data(contentsOf: URL(fileURLWithPath: fixture)),
              let object = try? JSONSerialization.jsonObject(with: raw) as? [String: Any],
              let estimateObject = object["estimate"], let resultsObject = object["results"],
              let estimate = try? JSONDecoder().decode(ValidatorV5Estimate.self, from: JSONSerialization.data(withJSONObject: estimateObject)),
              let results = try? JSONDecoder().decode(ValidatorV5Results.self, from: JSONSerialization.data(withJSONObject: resultsObject))
        else { return }
        func make(key: Bool = true, withResults: Bool = true) -> ReviewStore {
            let s = store(report: report, document: document)
            s.validatorBackend = .v5
            s.debugSetOpenAIKeyPresent(key)
            for item in results.items { s.decisions[item.id] = ReviewDecision(rawValue: item.previousDecision ?? "") ?? .pending }
            if withResults { s.secondOpinion.debugShow(phase: .finished, results: results) }
            s.recomputeAssessments()
            s.deskSection = .validation
            return s
        }
        let size = NSSize(width: 1280, height: 980)
        await render(make(), size: size, name: "20-validacao-resumo", dark: dark, into: folder)
        let filtered = make()
        filtered.assessmentFilter = .possibleError
        await render(filtered, size: size, name: "21-validacao-filtro-possivel-erro", dark: dark, into: folder)
        let none = make(withResults: false)
        await render(none, size: size, name: "22-validacao-sem-analise", dark: dark, into: folder)
        let confirm = make()
        confirm.secondOpinion.debugShow(phase: .awaitingAuthorization, estimate: estimate, results: results)
        await render(confirm, size: size, name: "23-validacao-confirmar", dark: dark, into: folder)
        let changed = make()
        changed.secondOpinion.debugShow(phase: .awaitingAuthorization, estimate: estimate, results: results,
                                        notice: "A estimativa mudou desde que foi mostrada (texto, decisões, versão ou custo). Confira e confirme de novo.")
        await render(changed, size: size, name: "24-validacao-estimativa-mudou", dark: dark, into: folder)
        let stale = make()
        if let target = results.items.first(where: { $0.paragraph == 10 }) ?? results.items.first {
            stale.decisions[target.id] = stale.decisions[target.id] == .style ? .error : .style
        }
        await render(stale, size: size, name: "25-validacao-desatualizada", dark: dark, into: folder)
        for (name, paragraph) in [("26-inspetor-possivel-erro", 10), ("27-inspetor-inconclusiva", 56), ("28-inspetor-revisao", 42)] {
            guard let item = results.items.first(where: { $0.paragraph == paragraph }) else { continue }
            let s = make()
            s.deskSection = .pendencies
            s.selectedID = item.id
            await render(s, size: NSSize(width: 1280, height: 1000), name: name, dark: dark, into: folder)
        }
        let noKey = make(key: false, withResults: false)
        await render(noKey, size: size, name: "29-validacao-sem-chave", dark: dark, into: folder)
        let keys = make()
        await render(AnyView(KeySheet().environmentObject(keys)), size: NSSize(width: 600, height: 620),
                     name: "30-chaves", dark: dark, into: folder)
    }

    static func run(into folder: URL) async {
        try? FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        let env = ProcessInfo.processInfo.environment
        // Ligar a IA nas capturas grava em UserDefaults; os valores do autor voltam no fim.
        let defaults = UserDefaults.standard
        let saved = ["auditAI", "coherenceAI", ValidatorBackend.defaultsKey].map { ($0, defaults.object(forKey: $0)) }
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
            if let report = env["LUME_SNAPSHOT_V5_REPORT"], let fixture = env["LUME_SNAPSHOT_V5_FIXTURE"] {
                await renderSecondOpinion(report: report, document: env["LUME_SNAPSHOT_V5_DOC"], fixture: fixture,
                                          dark: dark, into: folder)
            }
            if let report = env["LUME_SNAPSHOT_REPORT"] {
                await renderValidator(report: report, document: env["LUME_SNAPSHOT_REPORT_DOC"], dark: dark, into: folder)
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
