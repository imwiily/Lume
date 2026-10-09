import SwiftUI
import AppKit
import UniformTypeIdentifiers
import Security

@MainActor
final class ReviewStore: ObservableObject {
    enum Screen: Equatable { case preparation, review }
    @Published private(set) var screen: Screen = .preparation
    @Published private(set) var isAnalyzing = false
    @Published private(set) var analysisFailed = false

    func showPreparation() {
        guard !isBusy else { return }
        screen = .preparation
    }

    func resumeReview() {
        guard !isBusy, report != nil else { return }
        analysisFailed = false
        screen = .review
    }

    @Published var backendURL: URL?
    @Published private(set) var embeddedEngine: EmbeddedEngine?
    @Published var documentURL: URL?
    @Published var originalURL: URL?
    @Published var analysisMode = "ambas"
    @Published var searchSettings = SearchSettings()
    @Published var layerFilter = "Todas"
    @Published var moduleFilter = "Todas"
    @Published var severityFilter = "Todas"
    @Published private(set) var analysisStages: [AnalysisStage] = []
    @Published var report: EditorialReport?
    @Published var reportURL: URL?
    /// Último `falsos-positivos.json` gravado para o relatório aberto.
    @Published private(set) var falsePositivesURL: URL?
    @Published var decisions: [String: ReviewDecision] = [:]
    /// ID do alerta → decisões anteriores divergentes do mesmo fenômeno (identidades que o motor juntou).
    /// Mostradas no inspetor; ficam registradas mesmo depois da decisão do editor.
    @Published private(set) var decisionConflicts: [String: [String]] = [:]
    @Published var selectedID: String?
    @Published var category = "Todas"
    @Published var decisionFilter = "Todas"
    @Published var search = ""
    @Published var tense = "passado"
    @Published var includeItalics = false
    @Published var useLanguageTool = true
    // Coerência com IA (Claude): desligada por padrão; nada é enviado sem confirmação do custo.
    @Published var useCoherenceAI = UserDefaults.standard.bool(forKey: "coherenceAI") {
        didSet { UserDefaults.standard.set(useCoherenceAI, forKey: "coherenceAI") }
    }
    @Published var coherenceModel = UserDefaults.standard.string(forKey: "coherenceModel") ?? "claude-sonnet-5-5" {
        didSet { UserDefaults.standard.set(coherenceModel, forKey: "coherenceModel") }
    }
    @Published var coherenceBudget = UserDefaults.standard.object(forKey: "coherenceBudget") as? Double ?? 1.0 {
        didSet { UserDefaults.standard.set(max(0.05, coherenceBudget), forKey: "coherenceBudget") }
    }
    // Auditoria final com IA: desligada por padrão porque custa dinheiro; mesma chave e mesma confirmação.
    @Published var useAuditAI = UserDefaults.standard.bool(forKey: "auditAI") {
        didSet { UserDefaults.standard.set(useAuditAI, forKey: "auditAI") }
    }
    @Published var auditModel = UserDefaults.standard.string(forKey: "auditModel") ?? "claude-opus-5-5" {
        didSet { UserDefaults.standard.set(auditModel, forKey: "auditModel") }
    }
    @Published var auditBudget = UserDefaults.standard.object(forKey: "auditBudget") as? Double ?? 1.0 {
        didSet { UserDefaults.standard.set(max(0.05, auditBudget), forKey: "auditBudget") }
    }
    @Published private(set) var hasAPIKey = AnthropicKey.exists()
    /// Estimativa de envio dos recursos com IA ligados, mostrada antes de qualquer envio.
    @Published var aiEstimate: AIEstimate?
    private var aiConfirmed = false
    var coherenceActive: Bool { useCoherenceAI && analysisMode != "linguistica" }
    var auditActive: Bool { useAuditAI }
    @Published var isBusy = false
    @Published var canCancel = false
    @Published var jobLabel = ""
    @Published var status = "Escolha um manuscrito ou abra um relatório existente."
    @Published var errorText: String?
    @Published var logURL: URL?
    @Published var hasUnsavedDecisions = false
    /// Parte da mesa à vista: as pendências (trabalho editorial) ou as observações (consulta livre).
    @Published var deskSection: DeskSection = .pendencies
    /// “Revisão concluída” registrada para este texto e esta política, se houver.
    @Published private(set) var closure: ReviewClosure?
    /// Correções gravadas no manuscrito a partir do relatório aberto.
    @Published private(set) var editLog: EditLog?
    /// Decisões da leitura anterior, aplicadas quando a reanálise da mesma obra terminar.
    private var carriedDecisions: CarriedDecisions?

    private enum Job: Equatable { case analyze, install, diagnose }
    private let runner = PythonRunner.shared
    private let manager = FileManager.default

    init() {
        let resolved = EmbeddedEngine.resolve()
        embeddedEngine = resolved.engine
        if let warning = resolved.warning { status = warning }
        if let path = UserDefaults.standard.string(forKey: "backendPath") {
            let candidate = URL(fileURLWithPath: path, isDirectory: true)
            if Self.isBackend(candidate) { backendURL = candidate }
        }
    }

    static func isBackend(_ url: URL) -> Bool {
        FileManager.default.fileExists(atPath: url.appendingPathComponent("fonte/cli.py").path)
            && FileManager.default.fileExists(atPath: url.appendingPathComponent("instalar.sh").path)
    }

    var pythonURL: URL? { embeddedEngine?.executable ?? backendURL?.appendingPathComponent(".venv/bin/python") }
    var engineDescription: String {
        guard let engine = embeddedEngine else { return "Instalação externa de desenvolvimento" }
        return "FONTE " + engine.version + (engine.updated ? " · atualizado" : " · embutido")
    }
    private var engineArguments: [String] { embeddedEngine == nil ? ["-u", "-m", "fonte"] : [] }
    private var engineDirectory: URL? { embeddedEngine?.root ?? backendURL }

    var pythonExists: Bool {
        guard let url = pythonURL else { return false }
        return manager.isExecutableFile(atPath: url.path)
    }
    var canAnalyze: Bool { !isBusy && documentURL != nil && pythonExists }
    var categories: [String] { ["Todas"] + Set(report?.findings.map(\.category) ?? []).sorted() }
    var selectedFinding: Finding? { report?.findings.first { $0.id == selectedID } }
    /// Pendências, impeditivos e observações; relatórios antigos contam tudo como pendência.
    var tally: ReviewTally { ReviewTally(findings: report?.findings ?? [], decision: decision(for:)) }
    var pendingCount: Int { tally.pendingOpen }
    var filteredFindings: [Finding] {
        let section: FindingDestination = deskSection == .pendencies ? .pendencia : .informacao
        let items = (report?.findings ?? []).filter { finding in
            finding.destination == section
            && (layerFilter == "Todas" || (finding.layer ?? "linguistica") == layerFilter)
                && (moduleFilter == "Todas" || finding.module == moduleFilter)
                && (severityFilter == "Todas" || finding.severity == severityFilter)
                && (category == "Todas" || finding.category == category)
                && (decisionFilter == "Todas" || decision(for: finding).rawValue == decisionFilter)
                && (search.isEmpty || (finding.text + " " + finding.chapter).localizedCaseInsensitiveContains(search))
        }
        // Impeditivos primeiro; a ordem do texto continua dentro de cada grupo.
        return items.filter(\.isBlocking) + items.filter { !$0.isBlocking }
    }

    func decision(for finding: Finding) -> ReviewDecision { decisions[finding.id] ?? .pending }

    func chooseBackend() {
        guard !isBusy, embeddedEngine == nil else { return }
        let panel = NSOpenPanel()
        panel.title = "Selecione a pasta do analisador"
        panel.message = "Escolha a pasta fonte, incluída no projeto, ou sua pasta fonte-revisor já instalada."
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.allowsMultipleSelection = false
        guard panel.runModal() == .OK, let url = panel.url else { return }
        guard Self.isBackend(url) else {
            errorText = "Esta pasta não contém o analisador. Selecione a pasta que contém instalar.sh e a subpasta fonte."
            return
        }
        backendURL = url
        UserDefaults.standard.set(url.path, forKey: "backendPath")
        status = pythonExists ? "Motor FONTE selecionado. Use Verificar para conferir a instalação."
                              : "Motor FONTE selecionado. Clique em Preparar para instalar as dependências."
    }

    /// Formatos que o motor lê: Word e Pages.
    static let manuscriptExtensions = ["docx", "pages"]
    static var manuscriptTypes: [UTType] { manuscriptExtensions.map { UTType(filenameExtension: $0) ?? .data } }
    static func isManuscript(_ url: URL) -> Bool { manuscriptExtensions.contains(url.pathExtension.lowercased()) }

    func chooseDocument() {
        guard !isBusy else { return }
        let panel = NSOpenPanel()
        panel.title = "Escolher manuscrito"
        panel.allowedContentTypes = Self.manuscriptTypes
        panel.allowsMultipleSelection = false
        guard panel.runModal() == .OK, let url = panel.url else { return }
        openDocument(url)
    }

    /// Mesmo caminho para o painel e para arrastar o arquivo até a janela.
    func openDocument(_ url: URL) {
        guard !isBusy else { return }
        guard Self.isManuscript(url) else {
            errorText = "Escolha um arquivo Word (.docx) ou um documento do Pages (.pages)."
            return
        }
        guard mayReplaceReport() else { return }
        saveSearchSettings()
        originalURL = nil
        documentURL = url
        restoreSearchSettings()
        screen = .preparation; analysisFailed = false
        report = nil; reportURL = nil; falsePositivesURL = nil; selectedID = nil; decisions = [:]; editLog = nil
        carriedDecisions = nil
        category = "Todas"; decisionFilter = "Todas"; search = ""; layerFilter = "Todas"; moduleFilter = "Todas"; severityFilter = "Todas"
        status = "Manuscrito selecionado. O arquivo original será preservado."
    }

    private var searchSettingsKey: String? {
        documentURL.map { "lume.searchSettings." + $0.standardizedFileURL.path }
    }

    func saveSearchSettings() {
        guard let key = searchSettingsKey else { return }
        do { UserDefaults.standard.set(try searchSettings.encoded(), forKey: key) }
        catch { errorText = error.localizedDescription }
    }

    private func restoreSearchSettings() {
        guard let key = searchSettingsKey, let data = UserDefaults.standard.data(forKey: key) else {
            searchSettings = SearchSettings(); return
        }
        do { searchSettings = try SearchSettings.decode(data) }
        catch {
            searchSettings = SearchSettings()
            errorText = "A configuração salva não pôde ser lida. Confira os filtros antes de analisar."
        }
    }

    func importSearchSettings() {
        guard !isBusy else { return }
        let panel = NSOpenPanel(); panel.allowedContentTypes = [.json]
        panel.title = "Importar configuração de busca"
        guard panel.runModal() == .OK, let url = panel.url else { return }
        do {
            let data = try readData(url)
            guard data.count <= 200_000 else { throw FonteError.message("Configuração maior que 200 KB.") }
            searchSettings = try SearchSettings.decode(data)
            saveSearchSettings()
            status = "Configuração importada. Os filtros serão usados na próxima análise."
        } catch { errorText = error.localizedDescription }
    }

    func exportSearchSettings() {
        let panel = NSSavePanel(); panel.allowedContentTypes = [.json]
        panel.nameFieldStringValue = "lume-busca.json"
        guard panel.runModal() == .OK, let url = panel.url else { return }
        do { try searchSettings.encoded().write(to: url, options: .atomic) }
        catch { errorText = error.localizedDescription }
    }

    func chooseOriginal() {
        guard !isBusy else { return }
        let panel = NSOpenPanel()
        panel.title = "Original para comparar com o manuscrito revisado"
        panel.allowedContentTypes = Self.manuscriptTypes
        panel.allowsMultipleSelection = false
        guard panel.runModal() == .OK, let url = panel.url else { return }
        guard Self.isManuscript(url), url != documentURL else {
            errorText = "Selecione outro arquivo: a versão anterior à revisão."
            return
        }
        originalURL = url
    }

    func chooseReport() {
        guard !isBusy else { return }
        let panel = NSOpenPanel()
        panel.title = "Abrir relatorio.json"
        panel.allowedContentTypes = [.json]
        guard panel.runModal() == .OK, let url = panel.url, mayReplaceReport() else { return }
        do {
            saveSearchSettings()
            carriedDecisions = nil
            try loadReport(url)
            documentURL = nil; originalURL = nil
        } catch { errorText = error.localizedDescription }
    }

    // Só bloqueia a troca quando uma falha real impediu salvar decisões.
    private func mayReplaceReport() -> Bool {
        if hasUnsavedDecisions {
            errorText = "Há decisões que não foram salvas. Exporte-as antes de abrir outro documento."
            return false
        }
        return true
    }

    private func supportRoot() throws -> URL {
        guard let base = manager.urls(for: .applicationSupportDirectory, in: .userDomainMask).first else {
            throw FonteError.message("A pasta de dados do aplicativo não está disponível.")
        }
        return base.appendingPathComponent("FONTE", isDirectory: true)
    }

    private func supportDirectory(_ component: String) throws -> URL {
        let url = try supportRoot().appendingPathComponent(component, isDirectory: true)
        try manager.createDirectory(at: url, withIntermediateDirectories: true)
        return url
    }

    private func decisionURL(for report: EditorialReport) throws -> URL {
        try supportDirectory("Decisoes").appendingPathComponent(report.sha256 + ".json")
    }

    private func readData(_ url: URL) throws -> Data {
        let attrs = try manager.attributesOfItem(atPath: url.path)
        // Trava contra arquivos absurdos, não contra livros longos: um romance de 13 mil parágrafos
        // gera relatório de uns 36 MB, lido em cerca de 1 s com 240 MB de memória.
        guard let size = attrs[.size] as? NSNumber, size.intValue <= 200_000_000 else {
            throw FonteError.message("O JSON excede o limite de 200 MB desta interface.")
        }
        return try Data(contentsOf: url)
    }

    private func loadReport(_ url: URL) throws {
        let loaded = try JSONDecoder().decode(EditorialReport.self, from: readData(url))
        try loaded.validate()
        var restored: [String: ReviewDecision] = [:]
        var history = InheritedDecisions()
        let cache = try decisionURL(for: loaded)
        if manager.fileExists(atPath: cache.path) {
            do {
                let file = try decisionFile(readData(cache), for: loaded)
                restored = decisionsOf(file)
                for (id, entries) in file.conflicts ?? [:] { history.addConflict(id, entries) }
            } catch {
                // Preserva o arquivo problemático antes de permitir novos salvamentos.
                let backup = cache.deletingPathExtension().appendingPathExtension("recuperacao-\(UUID().uuidString).json")
                try manager.copyItem(at: cache, to: backup)
                errorText = "Não foi possível restaurar as decisões locais. Uma cópia foi preservada em \(backup.path)."
            }
        }
        var inherited = 0
        if restored.isEmpty, !manager.fileExists(atPath: cache.path) {
            let fromEdits = inheritedDecisions(for: loaded)
            restored = fromEdits.decisions
            for (id, entries) in fromEdits.conflicts { history.addConflict(id, entries) }
            // Edições feitas fora do Lume (ou só salvar de novo) mudam o SHA-256: o livro, pelo
            // nome do arquivo, devolve as decisões dos alertas idênticos pelo conteúdo.
            if let book = bookMemory(for: loaded) {
                let fromBook = book.inheritance(for: loaded)
                restored.merge(fromBook.decisions) { fromEdits, _ in fromEdits }
                for (id, entries) in fromBook.conflicts { history.addConflict(id, entries) }
            }
            inherited = restored.count
        }
        // Reanálise: as decisões da leitura anterior completam as que o cache não trouxe.
        var carried = 0
        let carry = carriedDecisions.flatMap { $0.belongs(to: loaded) ? $0 : nil }
        carriedDecisions = nil
        if let carry {
            let before = restored.values.filter { $0 != .pending }.count
            let merged = carry.merge(into: restored, for: loaded)
            restored = merged.decisions
            for (id, entries) in merged.conflicts { history.addConflict(id, entries) }
            carried = restored.values.filter { $0 != .pending }.count - before
        }
        let ids = Set(loaded.findings.map(\.id))
        report = loaded; reportURL = url; decisions = restored
        decisionConflicts = history.conflicts.filter { ids.contains($0.key) }
        falsePositivesURL = falsePositivesFile(next: url).flatMap { manager.fileExists(atPath: $0.path) ? $0 : nil }
        editLog = readEditLog(loaded.sha256)
        analysisStages = loaded.metadata.stages ?? []
        screen = .review; analysisFailed = false
        closure = readClosure(for: loaded)
        deskSection = .pendencies
        selectedID = carry?.selectedID.flatMap { id in loaded.findings.contains { $0.id == id && $0.destination == .pendencia } ? id : nil }
            ?? loaded.findings.first { $0.destination == .pendencia }?.id
        category = "Todas"; decisionFilter = "Todas"; search = ""; layerFilter = "Todas"; moduleFilter = "Todas"; severityFilter = "Todas"
        hasUnsavedDecisions = false
        let counts = ReviewTally(findings: loaded.findings, decision: { restored[$0.id] ?? .pending })
        status = "\(counts.pending) pendências e \(counts.observations) observações. Avalie as pendências no contexto."
        if inherited > 0 || carried > 0 || !decisionConflicts.isEmpty {
            try autosave()
            status = "\(counts.pending) pendências e \(counts.observations) observações. \(inherited + carried) decisões mantidas nos alertas que não mudaram desde a análise anterior."
        }
        if let carry {
            let kept = restored.values.filter { $0 != .pending }.count
            status = "Reanálise concluída: \(counts.pending) pendências e \(counts.observations) observações; \(kept) de \(carry.byID.count) marcações anteriores mantidas nos alertas que continuam no texto."
        }
        if !decisionConflicts.isEmpty {
            status += " \(decisionConflicts.count) alerta(s) com decisões anteriores divergentes: veja no inspetor."
        }
    }

    private func bookURL(_ document: String) throws -> URL {
        try supportDirectory("Livros").appendingPathComponent(BookMemory.fileName(document))
    }

    /// Decisões do livro pelo nome do arquivo; na primeira vez, montadas das decisões já salvas.
    private func bookMemory(for report: EditorialReport) -> BookMemory? {
        guard let url = try? bookURL(report.document) else { return nil }
        guard manager.fileExists(atPath: url.path) else { return migratedBook(for: report) }
        guard let book = try? BookMemory.decode(readData(url)), book.belongs(to: report) else { return nil }
        return book
    }

    /// Migração: relatório mais recente do mesmo livro, com outro SHA-256 e alguma decisão salva.
    private func migratedBook(for report: EditorialReport) -> BookMemory? {
        guard let folder = try? supportDirectory("Relatorios"),
              let jobs = try? manager.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil) else { return nil }
        let reports = jobs.map { $0.appendingPathComponent("relatorio.json") }.compactMap { url -> (URL, Date)? in
            guard let date = try? url.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate else { return nil }
            return (url, date)
        }.sorted { $0.1 > $1.1 }
        for (url, _) in reports {
            guard let old = try? JSONDecoder().decode(EditorialReport.self, from: readData(url)),
                  old.sha256 != report.sha256, BookMemory.bookName(old.document) == BookMemory.bookName(report.document),
                  let source = try? decisionURL(for: old), manager.fileExists(atPath: source.path),
                  let saved = try? parseDecisions(readData(source), for: old),
                  saved.values.contains(where: { $0 != .pending }) else { continue }
            return BookMemory(report: old, decisions: saved)
        }
        return nil
    }

    // MARK: Correção no manuscrito

    /// Só documentos do Pages recebem correções; o DOCX continua somente leitura.
    var canEditManuscript: Bool { report != nil && documentURL?.pathExtension.lowercased() == "pages" }
    func appliedEdit(for finding: Finding) -> AppliedEdit? { editLog?.edits.first { $0.finding == finding.id } }
    func editCount(inParagraph paragraph: Int) -> Int { editLog?.edits.filter { $0.paragraph == paragraph }.count ?? 0 }
    private func edits(inParagraph paragraph: Int) -> [AppliedEdit] { (editLog?.edits ?? []).filter { $0.paragraph == paragraph } }
    /// Parágrafo do alerta como está no arquivo: o do relatório com as correções já gravadas.
    func currentParagraph(for finding: Finding) -> String {
        ManuscriptEditor.currentText(finding.text, edits: edits(inParagraph: finding.paragraph))
    }

    private func editLogURL(_ sha: String) throws -> URL {
        try supportDirectory("Edicoes").appendingPathComponent(sha + ".json")
    }

    private func readEditLog(_ sha: String) -> EditLog? {
        guard let url = try? editLogURL(sha), manager.fileExists(atPath: url.path) else { return nil }
        let decoder = JSONDecoder(); decoder.dateDecodingStrategy = .iso8601
        guard let log = try? decoder.decode(EditLog.self, from: readData(url)), log.schemaVersion == 1, log.origem == sha else {
            errorText = "O histórico de correções deste relatório não pôde ser lido. Analise o manuscrito novamente antes de corrigir."
            return nil
        }
        return log
    }

    /// Depois de correções feitas pelo Lume, a nova análise mantém as decisões dos alertas
    /// idênticos (mesmo ID: mesmo parágrafo, texto, regra e trecho). Nada é herdado por aproximação.
    private func inheritedDecisions(for report: EditorialReport) -> InheritedDecisions {
        guard let folder = try? supportDirectory("Edicoes"),
              let files = try? manager.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil) else { return InheritedDecisions() }
        let decoder = JSONDecoder(); decoder.dateDecodingStrategy = .iso8601
        let ids = Set(report.findings.map(\.id))
        for file in files where file.pathExtension == "json" {
            guard let log = try? decoder.decode(EditLog.self, from: readData(file)),
                  log.atual == report.sha256, log.origem != report.sha256,
                  let source = try? supportDirectory("Decisoes").appendingPathComponent(log.origem + ".json"),
                  let previous = try? JSONDecoder().decode(DecisionFile.self, from: readData(source)) else { continue }
            var result = InheritedDecisions(decisions: previous.decisions.reduce(into: [:]) { result, entry in
                if ids.contains(entry.key), let value = ReviewDecision(rawValue: entry.value), value != .pending {
                    result[entry.key] = value
                }
            })
            for (id, entries) in previous.conflicts ?? [:] where ids.contains(id) { result.addConflict(id, entries) }
            // O alerta que juntou outras ocorrências consulta também o ID de cada uma delas.
            for finding in report.findings {
                let absorbed = (finding.absorvidos ?? []).compactMap { item in
                    previous.decisions[item.id].flatMap(ReviewDecision.init(rawValue:)).map { ($0, item.source) }
                }
                let (decision, conflict) = DecisionHistory.resolve(direct: result.decisions[finding.id], absorbed: absorbed)
                if let decision { result.decisions[finding.id] = decision }
                if let conflict { result.addConflict(finding.id, conflict) }
            }
            return result
        }
        return InheritedDecisions()
    }

    private func confirmFirstEdit(_ document: URL, backup: URL) -> Bool {
        let alert = NSAlert()
        alert.messageText = "Gravar correções em “\(document.lastPathComponent)”?"
        alert.informativeText = "O Lume vai alterar este arquivo usando o Pages, que será aberto. Cada correção troca apenas o trecho destacado do alerta ou, em Editar parágrafo, só a parte alterada daquele parágrafo.\n\nAntes da primeira correção, uma cópia do arquivo como está agora é guardada em:\n\(backup.path)"
        alert.addButton(withTitle: "Gravar correção")
        alert.addButton(withTitle: "Cancelar")
        return alert.runModal() == .alertFirstButtonReturn
    }

    func revealBackup() {
        guard let path = editLog?.copia else { return }
        NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: path)])
    }

    /// Grava no manuscrito a correção do trecho de um alerta. Só age a pedido do autor.
    func applyCorrection(_ replacement: String, for finding: Finding) {
        applyEdit(for: finding) { (finding.start, finding.end, finding.segments.marked, replacement) }
    }

    /// Grava a edição do parágrafo inteiro do alerta, pedida pelo autor em Editar parágrafo.
    /// Só a menor troca contínua vai ao Pages; o restante do parágrafo não é tocado.
    func applyParagraphEdit(_ newText: String, for finding: Finding) {
        applyEdit(for: finding) {
            let change = try ManuscriptEditor.paragraphChange(text: finding.text, edits: self.edits(inParagraph: finding.paragraph),
                                                              newText: newText)
            return (change.start, change.end, change.before, change.after)
        }
    }

    private func applyEdit(for finding: Finding, change: () throws -> (start: Int, end: Int, before: String, after: String)) {
        guard !isBusy, let report = report, let document = documentURL,
              let python = pythonURL, let directory = engineDirectory else { return }
        do {
            guard canEditManuscript else {
                throw FonteError.message("A correção no próprio arquivo está disponível para documentos do Pages.")
            }
            guard appliedEdit(for: finding) == nil else {
                throw FonteError.message("Este alerta já foi corrigido no manuscrito.")
            }
            let expectedSHA = editLog?.atual ?? report.sha256
            guard manager.fileExists(atPath: document.path), try ManuscriptEditor.sha256(document) == expectedSHA else {
                throw FonteError.message("O arquivo escolhido não é o mesmo deste relatório, ou foi alterado fora do Lume. Analise o manuscrito novamente antes de corrigir.")
            }
            let (start, end, before, replacement) = try change()
            let plan = try ManuscriptEditor.plan(text: finding.text, start: start, end: end, replacement: replacement,
                                                 edits: edits(inParagraph: finding.paragraph))
            let backup = try supportDirectory("Copias").appendingPathComponent(report.sha256, isDirectory: true)
                .appendingPathComponent(document.lastPathComponent)
            if editLog == nil {
                guard confirmFirstEdit(document, backup: backup) else { return }
                try manager.createDirectory(at: backup.deletingLastPathComponent(), withIntermediateDirectories: true)
                if !manager.fileExists(atPath: backup.path) { try manager.copyItem(at: document, to: backup) }
                guard try ManuscriptEditor.sha256(backup) == report.sha256 else {
                    throw FonteError.message("A cópia de segurança não confere com o manuscrito analisado. Nada foi alterado.")
                }
            }
            let work = manager.temporaryDirectory.appendingPathComponent("lume-edicao-" + UUID().uuidString, isDirectory: true)
            try manager.createDirectory(at: work, withIntermediateDirectories: true)
            let previous = work.appendingPathComponent("antes." + document.pathExtension)
            let expected = work.appendingPathComponent("esperado.txt")
            try manager.copyItem(at: document, to: previous)
            try Data(plan.resultText.utf8).write(to: expected)
            let log = try supportDirectory("Registros").appendingPathComponent(UUID().uuidString + ".txt")
            let arguments = engineArguments + ["conferir-edicao", previous.path, document.path,
                                               "--paragrafo", String(finding.paragraph), "--esperado", expected.path]
            isBusy = true; jobLabel = "Gravando a correção no Pages…"; errorText = nil; logURL = log
            Task {
                defer { isBusy = false; jobLabel = ""; try? manager.removeItem(at: work) }
                do {
                    try await ManuscriptEditor.runPages(document: document, paragraph: finding.paragraph, plan: plan)
                    let result = try await runner.run(executable: python, arguments: arguments, directory: directory, logURL: log)
                    let prefix = "LUME_EDICAO "
                    let current = try ManuscriptEditor.sha256(document)
                    guard result.exitCode == 0,
                          let line = PythonRunner.tail(log).split(separator: "\n").last(where: { $0.hasPrefix(prefix) }),
                          let checked = try? JSONDecoder().decode([String: String].self, from: Data(line.dropFirst(prefix.count).utf8)),
                          checked["sha256"] == current, current != expectedSHA else {
                        throw FonteError.message("A conferência da correção falhou: o resultado não é exatamente a troca pedida. Se o motor selecionado for anterior a esta versão do Lume, use Motor de análise → Restaurar embutido.\n\n\(String(PythonRunner.tail(log).suffix(600)))")
                    }
                    var updated = editLog ?? EditLog(origem: report.sha256, atual: current, documento: document.lastPathComponent, copia: backup.path)
                    updated.atual = current
                    updated.edits.append(AppliedEdit(finding: finding.id, paragraph: finding.paragraph, start: start, end: end,
                                                     before: before, after: replacement, date: Date()))
                    let encoder = JSONEncoder()
                    encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
                    encoder.dateEncodingStrategy = .iso8601
                    try encoder.encode(updated).write(to: editLogURL(report.sha256), options: .atomic)
                    editLog = updated
                    if [.pending, .error].contains(decision(for: finding)) { decisions[finding.id] = .corrected }
                    try autosave()
                    status = "Correção gravada no manuscrito. A cópia anterior às correções está guardada."
                } catch {
                    // Qualquer falha devolve o arquivo ao estado anterior a esta correção.
                    var restored = ""
                    if (try? ManuscriptEditor.sha256(document)) != expectedSHA {
                        do {
                            _ = try manager.replaceItemAt(document, withItemAt: previous)
                            restored = "\n\nO manuscrito foi devolvido ao estado anterior a esta correção."
                        } catch {
                            restored = "\n\nNão foi possível restaurar o manuscrito automaticamente. A cópia anterior às correções está em \(backup.path)."
                        }
                    }
                    errorText = error.localizedDescription + restored
                    status = "A correção não foi gravada."
                }
            }
        } catch { errorText = error.localizedDescription }
    }

    /// Reanalisar a obra: mesma leitura, mesmas opções, com as decisões já marcadas mantidas.
    var canReanalyze: Bool { report != nil && canAnalyze && !hasUnsavedDecisions }

    func reanalyze() {
        guard canReanalyze, let report else { return }
        carriedDecisions = CarriedDecisions(report: report, decisions: decisions, conflicts: decisionConflicts,
                                            selectedID: selectedID)
        analyze()
    }

    func analyze() {
        guard coherenceActive || auditActive, !aiConfirmed else { return start(.analyze) }
        guard hasAPIKey else {
            errorText = "Configure a chave da API da Anthropic para usar a Coerência ou a Auditoria final com IA, ou desligue essas opções."
            return
        }
        estimateAI()
    }

    func confirmAI() {
        aiEstimate = nil
        aiConfirmed = true
        start(.analyze)
    }

    func cancelAI() {
        aiEstimate = nil
        carriedDecisions = nil
        status = "Análise cancelada antes de enviar qualquer texto."
    }

    /// Estimativas locais (não chamam a API) de cada recurso com IA ligado, em sequência; o
    /// resultado vira uma única confirmação.
    private func estimateAI() {
        guard !isBusy, canAnalyze, mayReplaceReport(), let directory = engineDirectory,
              let input = documentURL, let python = pythonURL else { return }
        do {
            let jobID = UUID().uuidString
            saveSearchSettings()
            let config = try supportDirectory("Configuracoes").appendingPathComponent(jobID + ".json")
            try searchSettings.encoded().write(to: config, options: .atomic)
            var steps: [(audit: Bool, label: String, arguments: [String])] = []
            if coherenceActive, let project = coherenceProject {
                steps.append((false, "Calculando o custo da Coerência com IA…",
                              engineArguments + ["coerencia-estimar", input.path, "--coerencia-projeto", project.path,
                                                 "--coerencia-modelo", coherenceModel, "--config", config.path]))
            }
            if auditActive, let project = auditProject {
                steps.append((true, "Calculando o custo da Auditoria final…",
                              engineArguments + ["auditoria-estimar", input.path, "--auditoria-projeto", project.path,
                                                 "--auditoria-modelo", auditModel, "--tempo", tense, "--config", config.path]))
            }
            guard !steps.isEmpty else { return start(.analyze) }
            isBusy = true; canCancel = false; errorText = nil
            Task {
                defer { isBusy = false; jobLabel = "" }
                var estimate = AIEstimate(coherenceBudget: coherenceBudget, auditBudget: auditBudget)
                do {
                    for (index, step) in steps.enumerated() {
                        jobLabel = step.label
                        let log = try supportDirectory("Registros").appendingPathComponent("\(jobID)-\(index).txt")
                        logURL = log
                        let result = try await runner.run(executable: python, arguments: step.arguments,
                                                          directory: directory, logURL: log, extraEnvironment: [:])
                        let name = step.audit ? "a Auditoria final" : "a Coerência com IA"
                        guard result.exitCode == 0 else {
                            let details = String(PythonRunner.tail(log).suffix(1800))
                            throw FonteError.message("Não foi possível estimar \(name). Se o motor selecionado for anterior a esta versão do Lume, use Motor de análise → Restaurar embutido.\n\n\(details)")
                        }
                        let prefix = step.audit ? "LUME_ESTIMATIVA_AUDITORIA " : "LUME_ESTIMATIVA "
                        guard let line = PythonRunner.tail(log).split(separator: "\n").last(where: { $0.hasPrefix(prefix) }) else {
                            throw FonteError.message("O motor não devolveu a estimativa d\(step.audit ? "a Auditoria final" : "a Coerência com IA").")
                        }
                        let data = Data(line.dropFirst(prefix.count).utf8)
                        if step.audit {
                            estimate.audit = try JSONDecoder().decode(AuditEstimate.self, from: data)
                        } else {
                            estimate.coherence = try JSONDecoder().decode(CoherenceEstimate.self, from: data)
                        }
                    }
                    aiEstimate = estimate
                    status = "Confira o envio e o custo estimado antes de continuar."
                } catch {
                    errorText = error.localizedDescription
                    status = "A estimativa não foi concluída. Nada foi enviado."
                }
            }
        } catch { errorText = error.localizedDescription }
    }

    func saveAPIKey(_ key: String) {
        let key = key.trimmingCharacters(in: .whitespacesAndNewlines)
        guard key.hasPrefix("sk-ant-"), key.count > 60 else {
            errorText = "Essa não parece uma chave completa da API da Anthropic (começa com sk-ant- e tem mais de 100 caracteres). Copie a chave logo após criá-la no console."
            return
        }
        do {
            try AnthropicKey.save(key)
            hasAPIKey = true
            status = "Chave da API guardada nas Chaves do macOS."
        } catch { errorText = error.localizedDescription }
    }

    func removeAPIKey() {
        AnthropicKey.delete()
        hasAPIKey = false
        status = "Chave da API removida das Chaves do macOS."
    }

    private var coherenceProject: URL? { projectFolder("Coerencia") }
    private var auditProject: URL? { projectFolder("Auditoria") }

    /// Pasta por livro em Application Support, pelo nome do arquivo.
    private func projectFolder(_ component: String) -> URL? {
        guard let document = documentURL else { return nil }
        let name = document.deletingPathExtension().lastPathComponent
        let safe = String(name.map { $0.isLetter || $0.isNumber || $0 == "-" || $0 == " " ? $0 : "-" })
        return try? supportDirectory(component).appendingPathComponent(safe, isDirectory: true)
    }
    func install() { start(.install) }
    func diagnose() { start(.diagnose) }

    private func start(_ job: Job) {
        guard !isBusy, let directory = engineDirectory else { return }
        if job == .install && embeddedEngine != nil { return }
        if job == .analyze && (!canAnalyze || (!aiConfirmed && !mayReplaceReport())) { return }
        if job == .diagnose && !pythonExists {
            errorText = "Prepare o analisador antes de verificar a instalação."
            return
        }
        do {
            let jobID = UUID().uuidString
            let log = try supportDirectory("Registros").appendingPathComponent(jobID + ".txt")
            let output = try supportDirectory("Relatorios").appendingPathComponent(jobID, isDirectory: true)
            // Não cria output: a CLI exige uma pasta de saída que ainda não exista.
            let executable: URL
            var arguments: [String]
            var environment: [String: String] = [:]
            switch job {
            case .install:
                executable = URL(fileURLWithPath: "/bin/bash")
                arguments = [directory.appendingPathComponent("instalar.sh").path]
                jobLabel = "Preparando o analisador…"
            case .diagnose:
                guard let python = pythonURL else { return }
                executable = python
                arguments = engineArguments + ["diagnostico"]
                jobLabel = "Verificando a instalação…"
            case .analyze:
                guard let input = documentURL else { return }
                guard let python = pythonURL else { return }
                executable = python
                if let engine = embeddedEngine,
                   engine.version.compare("0.8.1", options: .numeric) == .orderedAscending {
                    throw FonteError.message("A revisão modular exige FONTE 0.8.1 ou posterior. Restaure o motor embutido desta versão do Lume ou instale a atualização do motor.")
                }
                saveSearchSettings()
                let config = try supportDirectory("Configuracoes").appendingPathComponent(jobID + ".json")
                try searchSettings.encoded().write(to: config, options: .atomic)
                arguments = engineArguments + ["revisar", input.path, "--saida", output.path, "--tempo", tense, "--config", config.path]
                if analysisMode != "linguistica" {
                    arguments += ["--modo", analysisMode]
                    if let original = originalURL { arguments += ["--original", original.path] }
                }
                if includeItalics { arguments.append("--incluir-italico") }
                if useLanguageTool && analysisMode != "editorial" { arguments.append("--languagetool") }
                if (coherenceActive || auditActive) && aiConfirmed {
                    guard let key = AnthropicKey.read() else {
                        aiConfirmed = false
                        throw FonteError.message("Não foi possível ler a chave da API nas Chaves do macOS. Configure-a novamente.")
                    }
                    // A chave vai só no ambiente do processo, nunca nos argumentos.
                    environment["ANTHROPIC_API_KEY"] = key
                    let money = { (value: Double) in String(format: "%.2f", locale: Locale(identifier: "en_US_POSIX"), value) }
                    if coherenceActive, let project = coherenceProject {
                        arguments += ["--coerencia-ia", "--coerencia-projeto", project.path, "--coerencia-modelo", coherenceModel,
                                      "--coerencia-teto", money(coherenceBudget)]
                    }
                    if auditActive, let project = auditProject {
                        arguments += ["--auditoria-ia", "--auditoria-projeto", project.path, "--auditoria-modelo", auditModel,
                                      "--auditoria-teto", money(auditBudget)]
                    }
                }
                aiConfirmed = false
                jobLabel = "Analisando o manuscrito…"
            }
            isBusy = true; canCancel = job == .analyze; logURL = log; errorText = nil
            if job == .analyze {
                isAnalyzing = true; analysisFailed = false; screen = .review
                analysisStages = AnalysisStage.pending
            }
            Task {
                let progressTask = Task { @MainActor in
                    guard job == .analyze else { return }
                    while !Task.isCancelled {
                        updateProgress(from: log)
                        do { try await Task.sleep(nanoseconds: 250_000_000) }
                        catch { break }
                    }
                }
                defer {
                    progressTask.cancel()
                    isBusy = false; canCancel = false; jobLabel = ""; isAnalyzing = false
                }
                do {
                    let result = try await runner.run(executable: executable, arguments: arguments, directory: directory,
                                                      logURL: log, extraEnvironment: environment)
                    if job == .analyze { updateProgress(from: log) }
                    if result.cancelled {
                        carriedDecisions = nil
                        analysisFailed = true
                        status = "Análise interrompida. O manuscrito foi preservado."
                        return
                    }
                    guard result.exitCode == 0 else {
                        let details = String(PythonRunner.tail(log).suffix(1800))
                        throw FonteError.message("A operação não foi concluída (código \(result.exitCode)).\n\n\(details)")
                    }
                    switch job {
                    case .analyze: try loadReport(output.appendingPathComponent("relatorio.json"))
                    case .install: status = "Motor FONTE preparado. Escolha um manuscrito e clique em Analisar."
                    case .diagnose: status = "Instalação verificada. O analisador está disponível."
                    }
                } catch {
                    if job == .analyze { analysisFailed = true; carriedDecisions = nil }
                    errorText = error.localizedDescription
                    status = "A operação não foi concluída. Confira o registro para mais detalhes."
                }
            }
        } catch { errorText = error.localizedDescription }
    }

    private func updateProgress(from log: URL) {
        let prefix = "LUME_PROGRESS "
        for line in PythonRunner.tail(log).split(separator: "\n") {
            guard line.hasPrefix(prefix),
                  let data = String(line.dropFirst(prefix.count)).data(using: .utf8),
                  let stage = try? JSONDecoder().decode(AnalysisStage.self, from: data),
                  ReviewModule(rawValue: stage.module) != nil else { continue }
            if let index = analysisStages.firstIndex(where: { $0.module == stage.module }) {
                analysisStages[index] = stage
            }
            if stage.state == "running", canCancel {
                jobLabel = stage.title + (stage.progressText.map { " · " + $0 } ?? "") + "…"
            }
        }
    }

    func importEngine() {
        guard !isBusy, EmbeddedEngine.bundled != nil else { return }
        let panel = NSOpenPanel()
        panel.title = "Instalar atualização do motor"
        panel.message = "Escolha a pasta .lumemotor extraída do pacote recebido. Ela contém código executável: use pacotes de uma origem em que confia."
        panel.canChooseDirectories = true; panel.canChooseFiles = false
        panel.allowsMultipleSelection = false; panel.treatsFilePackagesAsDirectories = true
        guard panel.runModal() == .OK, let url = panel.url else { return }
        guard url.pathExtension == "lumemotor" else {
            errorText = "Selecione a pasta que termina em .lumemotor, não o ZIP nem a pasta runtime."
            return
        }
        manageEngine("--lume-install", package: url)
    }

    func rollbackEngine() { manageEngine("--lume-rollback") }
    func resetEngine() { manageEngine("--lume-reset") }

    private func manageEngine(_ operation: String, package: URL? = nil) {
        guard !isBusy, let controller = EmbeddedEngine.bundled else { return }
        do {
            let log = try supportDirectory("Registros").appendingPathComponent(UUID().uuidString + ".txt")
            var arguments = [operation, "--support", EmbeddedEngine.support.path]
            if let package = package { arguments += ["--package", package.path] }
            isBusy = true; canCancel = false; logURL = log; errorText = nil
            jobLabel = operation == "--lume-install" ? "Verificando e instalando o motor…" : "Restaurando o motor…"
            Task {
                defer { isBusy = false; jobLabel = "" }
                do {
                    let result = try await runner.run(executable: controller.executable, arguments: arguments,
                                                       directory: controller.root, logURL: log)
                    guard result.exitCode == 0 else {
                        throw FonteError.message("O motor anterior foi preservado.\n\n" + String(PythonRunner.tail(log).suffix(2000)))
                    }
                    let resolved = EmbeddedEngine.resolve()
                    embeddedEngine = resolved.engine
                    status = resolved.warning ?? (engineDescription + ". Pronto para analisar; suas decisões foram preservadas.")
                } catch { errorText = error.localizedDescription }
            }
        } catch { errorText = error.localizedDescription }
    }

    func cancel() {
        guard canCancel else { return }
        canCancel = false
        jobLabel = "Interrompendo análise…"
        runner.cancel()
    }

    func setDecision(_ decision: ReviewDecision, for finding: Finding) {
        decisions[finding.id] = decision
        hasUnsavedDecisions = true
        do {
            try autosave()
            status = "Decisão salva neste Mac. Exporte o JSON para compartilhar."
        } catch { errorText = "Não foi possível salvar a decisão: \(error.localizedDescription)" }
    }

    private func payload() throws -> Data {
        guard let report = report else { throw FonteError.message("Abra um relatório primeiro.") }
        let file = DecisionFile(schemaVersion: 1, sha256: report.sha256, document: report.document,
                                decisions: decisions.mapValues(\.rawValue),
                                conflicts: decisionConflicts.isEmpty ? nil : decisionConflicts)
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        return try encoder.encode(file)
    }

    private func autosave() throws {
        guard let report = report else { return }
        try payload().write(to: decisionURL(for: report), options: .atomic)
        // O livro só serve às próximas análises: uma falha nele não invalida a decisão já salva.
        try? BookMemory(report: report, decisions: decisions, conflicts: decisionConflicts).encoded()
            .write(to: bookURL(report.document), options: .atomic)
        hasUnsavedDecisions = false
    }

    // MARK: Encerramento

    private func closureURL(for report: EditorialReport) throws -> URL {
        try supportDirectory("Encerramentos").appendingPathComponent(
            ReviewClosure.fileName(report.sha256, partial: report.metadata.analiseParcial != nil))
    }

    /// O encerramento só vale para o mesmo texto e a mesma política.
    private func readClosure(for report: EditorialReport) -> ReviewClosure? {
        guard let url = try? closureURL(for: report), let data = try? Data(contentsOf: url),
              let record = try? ReviewClosure.decode(data), record.applies(to: report) else { return nil }
        return record
    }

    var canCloseReview: Bool { report != nil && closure == nil && !isBusy && !hasUnsavedDecisions && tally.canClose }

    /// “Encerrar revisão”: registra que o processo terminou, com o que ficou aberto. Nenhum
    /// impeditivo pode estar sem decisão. Não certifica ausência de erros.
    func closeReview() {
        guard canCloseReview, let report else { return }
        let counts = tally
        guard let record = ReviewClosure(report: report, tally: counts) else { return }
        let alert = NSAlert()
        alert.messageText = "Encerrar revisão?"
        var lines = ["Nenhum impeditivo está sem decisão."]
        if let partial = report.metadata.analiseParcial {
            lines.append("Esta análise é parcial: \(partial.components.joined(separator: ", ")) não executou. O encerramento fica registrado como de uma análise parcial e não vale para uma análise completa.")
        }
        if counts.pendingOpen > 0 || counts.observationsOpen > 0 {
            lines.append("Ficam sem decisão \(counts.pendingOpen) pendência(s) e \(counts.observationsOpen) observação(ões); isso fica registrado.")
        }
        let divergent = report.findings.filter { decisionConflicts[$0.id] != nil && decision(for: $0) == .pending }.count
        if divergent > 0 {
            lines.append("\(divergent) alerta(s) com decisões anteriores divergentes continuam sem decisão.")
        }
        lines.append("O encerramento guarda a data, a versão do motor e a versão da política. Ele indica que o processo de revisão terminou, não que o texto não tem erros.")
        alert.informativeText = lines.joined(separator: "\n\n")
        alert.addButton(withTitle: "Encerrar revisão")
        alert.addButton(withTitle: "Cancelar")
        guard alert.runModal() == .alertFirstButtonReturn else { return }
        do {
            try record.encoded().write(to: closureURL(for: report), options: .atomic)
            closure = record
            status = "Revisão concluída. Você pode continuar consultando e decidindo os alertas."
        } catch { errorText = "Não foi possível registrar o encerramento: \(error.localizedDescription)" }
    }

    private func parseDecisions(_ data: Data, for report: EditorialReport) throws -> [String: ReviewDecision] {
        decisionsOf(try decisionFile(data, for: report))
    }

    private func decisionFile(_ data: Data, for report: EditorialReport) throws -> DecisionFile {
        let file = try JSONDecoder().decode(DecisionFile.self, from: data)
        guard file.schemaVersion == 1, file.sha256 == report.sha256 else {
            throw FonteError.message("As decisões pertencem a outra versão do manuscrito.")
        }
        return file
    }

    private func decisionsOf(_ file: DecisionFile) -> [String: ReviewDecision] {
        file.decisions.reduce(into: [:]) { result, entry in
            if let value = ReviewDecision(rawValue: entry.value) { result[entry.key] = value }
        }
    }

    func importDecisions() {
        guard let report = report, !isBusy else { return }
        let panel = NSOpenPanel(); panel.allowedContentTypes = [.json]
        panel.title = "Importar decisões"
        guard panel.runModal() == .OK, let url = panel.url else { return }
        do {
            let loaded = try parseDecisions(readData(url), for: report)
            decisions.merge(loaded) { _, new in new }
            hasUnsavedDecisions = true
            try autosave()
            status = "\(loaded.count) marcações do manuscrito foram importadas e salvas."
        } catch { errorText = error.localizedDescription }
    }

    func exportDecisions() {
        guard report != nil, !isBusy else { return }
        let panel = NSSavePanel(); panel.allowedContentTypes = [.json]
        panel.nameFieldStringValue = "lume-decisoes.json"
        guard panel.runModal() == .OK, let url = panel.url else { return }
        do {
            try payload().write(to: url, options: .atomic)
            hasUnsavedDecisions = false
            status = "Decisões exportadas. Envie esse JSON junto do relatório para trazer feedback."
        } catch { errorText = error.localizedDescription }
    }

    var falsePositiveCount: Int {
        report?.findings.filter { decision(for: $0) == .falsePositive }.count ?? 0
    }

    func exportFalsePositives() {
        guard let report = report, !isBusy else { return }
        guard let file = FalsePositiveExport(report: report, decisions: decisions, exportedAt: Date()) else {
            status = "Nenhum alerta marcado como falso positivo."; return
        }
        do {
            let data = try file.encoded()
            // Ao lado do relatório, sem perguntar; a cada extração o arquivo é refeito com as
            // marcações atuais. Só se a pasta não aceitar gravação o local é perguntado.
            var place = "ao lado do relatório"
            if let url = falsePositivesFile(next: reportURL), (try? data.write(to: url, options: .atomic)) != nil {
                falsePositivesURL = url
            } else {
                place = "no local escolhido"
                let panel = NSSavePanel(); panel.allowedContentTypes = [.json]
                panel.title = "Extrair falsos positivos"
                panel.nameFieldStringValue = "falsos-positivos.json"
                guard panel.runModal() == .OK, let url = panel.url else { return }
                try data.write(to: url, options: .atomic)
                falsePositivesURL = url
            }
            status = "\(file.findings.count) falsos positivos extraídos em “\(falsePositivesURL?.lastPathComponent ?? "")”, \(place). O arquivo contém trechos do manuscrito."
        } catch { errorText = error.localizedDescription }
    }

    private func falsePositivesFile(next report: URL?) -> URL? {
        report?.deletingLastPathComponent().appendingPathComponent("falsos-positivos.json")
    }

    func revealFalsePositives() {
        if let url = falsePositivesURL { NSWorkspace.shared.activateFileViewerSelecting([url]) }
    }

    func copyParagraph(_ finding: Finding) {
        copy(finding.text, status: "Parágrafo copiado. Use ⌘F no Pages ou Word.")
    }

    func copyContext(_ finding: Finding) {
        copy(finding.contextText, status: "Contexto copiado: o título e os parágrafos mostrados na página.")
    }

    func copyMarkedParagraph(_ finding: Finding) {
        copy(finding.markedParagraphText, status: "Parágrafo copiado com o trecho entre asteriscos e o motivo do alerta.")
    }

    private func copy(_ text: String, status message: String) {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(text, forType: .string)
        status = message
    }

    // MARK: Armazenamento

    /// Apaga, depois de confirmar, relatórios, registros e configurações de leituras antigas.
    func cleanStorage() {
        guard !isBusy else { return }
        let support: URL
        do { support = try supportRoot() } catch { errorText = error.localizedDescription; return }
        let temporary = manager.temporaryDirectory
        let keepReport = reportURL?.deletingLastPathComponent()
        let keepLog = logURL
        isBusy = true; jobLabel = "Calculando o espaço ocupado…"; errorText = nil
        Task {
            let plan = await Task.detached(priority: .userInitiated) {
                StorageCleanup.plan(support: support, temporary: temporary, keepReport: keepReport, keepLog: keepLog)
            }.value
            // Relatórios antigos que ficam por causa das decisões guardam texto do manuscrito: avisar sempre.
            let preserved = plan.preserved == 0 ? "" : " \(plan.preserved) \(plan.preserved == 1 ? "relatório antigo fica" : "relatórios antigos ficam") porque \(plan.preserved == 1 ? "guarda" : "guardam") decisões que o relatório mais recente do livro não tem; \(plan.preserved == 1 ? "ele contém" : "eles contêm") trechos do manuscrito e \(plan.preserved == 1 ? "serve" : "servem") à medição da precisão."
            guard !plan.isEmpty else {
                isBusy = false; jobLabel = ""
                status = "Nenhum resíduo de leituras antigas para limpar." + preserved
                return
            }
            let size = ByteCountFormatter.string(fromByteCount: plan.bytes, countStyle: .file)
            let alert = NSAlert()
            alert.messageText = "Liberar \(size)?"
            alert.informativeText = "Serão apagados \(plan.summary). Eles guardam texto de leituras passadas.\n\nFicam o relatório aberto, o mais recente de cada livro, os falsos positivos extraídos, suas decisões, os encerramentos de revisão, o histórico e as cópias de segurança das correções, os projetos com IA e os motores." + (preserved.isEmpty ? "" : "\n\n" + preserved.trimmingCharacters(in: .whitespaces))
            alert.alertStyle = .warning
            alert.addButton(withTitle: "Apagar")
            alert.addButton(withTitle: "Cancelar")
            guard alert.runModal() == .alertFirstButtonReturn else {
                isBusy = false; jobLabel = ""
                status = "Limpeza cancelada; nada foi apagado."
                return
            }
            jobLabel = "Limpando resíduos…"
            let result = await Task.detached(priority: .userInitiated) { plan.apply() }.value
            isBusy = false; jobLabel = ""
            let freed = ByteCountFormatter.string(fromByteCount: result.freed, countStyle: .file)
            status = result.failures == 0 ? "\(freed) liberados. Decisões e cópias de segurança preservadas." + preserved
                : "\(freed) liberados; \(result.failures) itens não puderam ser apagados."
        }
    }

    func revealReport() {
        if let url = reportURL { NSWorkspace.shared.activateFileViewerSelecting([url]) }
    }
    func openLog() {
        if let url = logURL { NSWorkspace.shared.open(url) }
    }
}

/// Estimativa do motor (`coerencia-estimar`) antes de qualquer envio à API.
/// Chave da API nas Chaves do macOS, no mesmo serviço usado pelo Coerencia no terminal.
enum AnthropicKey {
    static let service = "coerencia-anthropic"

    /// Consulta só atributos: não lê o segredo nem pede permissão ao abrir o app.
    static func exists() -> Bool {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service,
                                    kSecReturnAttributes as String: true, kSecMatchLimit as String: kSecMatchLimitOne]
        return SecItemCopyMatching(query as CFDictionary, nil) == errSecSuccess
    }

    static func read() -> String? {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service,
                                    kSecReturnData as String: true, kSecMatchLimit as String: kSecMatchLimitOne]
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess, let data = item as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    static func save(_ key: String) throws {
        delete()
        let item: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service,
                                   kSecAttrAccount as String: NSUserName(), kSecValueData as String: Data(key.utf8)]
        let status = SecItemAdd(item as CFDictionary, nil)
        guard status == errSecSuccess else {
            throw FonteError.message("Não foi possível guardar a chave nas Chaves do macOS (código \(status)).")
        }
    }

    static func delete() {
        SecItemDelete([kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service] as CFDictionary)
    }
}

#if DEBUG
// Apenas para inspeção visual (LUME_SNAPSHOT): coloca a interface em estados fixos.
extension ReviewStore {
    func debugLoadReport(_ url: URL) throws { try loadReport(url) }
    func debugShowReading(_ stages: [AnalysisStage]) {
        analysisStages = stages; isAnalyzing = true; screen = .review
    }
    func debugReset() { isAnalyzing = false; screen = .preparation }
    func debugUseEngine(_ root: URL) {
        // Versão do manifesto, para as capturas mostrarem o motor como no app montado.
        let manifest = (try? Data(contentsOf: root.appendingPathComponent("manifest.json")))
            .flatMap { try? JSONDecoder().decode(EngineManifest.self, from: $0) }
        embeddedEngine = EmbeddedEngine(root: root, version: manifest?.engine_version ?? "debug", updated: false)
    }
}
#endif

/// As duas partes da mesa de leitura. Impeditivos aparecem destacados dentro das pendências; o
/// diagnóstico do motor fica em Etapas e alcance, fora do fluxo editorial.
enum DeskSection: String, CaseIterable, Identifiable {
    case pendencies = "Pendências"
    case observations = "Observações"
    var id: String { rawValue }
}
