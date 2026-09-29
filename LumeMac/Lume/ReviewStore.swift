import SwiftUI
import AppKit
import UniformTypeIdentifiers

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
    @Published var decisions: [String: ReviewDecision] = [:]
    @Published var selectedID: String?
    @Published var category = "Todas"
    @Published var decisionFilter = "Todas"
    @Published var search = ""
    @Published var tense = "passado"
    @Published var includeItalics = false
    @Published var useLanguageTool = false
    @Published var isBusy = false
    @Published var canCancel = false
    @Published var jobLabel = ""
    @Published var status = "Escolha um manuscrito ou abra um relatório existente."
    @Published var errorText: String?
    @Published var logURL: URL?
    @Published var hasUnsavedDecisions = false

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
    var pendingCount: Int {
        report?.findings.filter { decision(for: $0) == .pending }.count ?? 0
    }
    var filteredFindings: [Finding] {
        (report?.findings ?? []).filter { finding in
            (layerFilter == "Todas" || (finding.layer ?? "linguistica") == layerFilter)
                && (moduleFilter == "Todas" || finding.module == moduleFilter)
                && (severityFilter == "Todas" || finding.severity == severityFilter)
                && (category == "Todas" || finding.category == category)
                && (decisionFilter == "Todas" || decision(for: finding).rawValue == decisionFilter)
                && (search.isEmpty || (finding.text + " " + finding.chapter).localizedCaseInsensitiveContains(search))
        }
    }

    func decision(for finding: Finding) -> ReviewDecision { decisions[finding.id] ?? .pending }

    func chooseBackend() {
        guard !isBusy, embeddedEngine == nil else { return }
        let panel = NSOpenPanel()
        panel.title = "Selecione a pasta do analisador"
        panel.message = "Escolha Analisador, incluída no projeto, ou sua pasta fonte-revisor já instalada."
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
        status = pythonExists ? "Analisador selecionado. Use Verificar para conferir a instalação."
                              : "Analisador selecionado. Clique em Preparar para instalar as dependências."
    }

    func chooseDocument() {
        guard !isBusy else { return }
        let panel = NSOpenPanel()
        panel.title = "Escolher manuscrito"
        panel.allowedContentTypes = [UTType(filenameExtension: "docx") ?? .data]
        panel.allowsMultipleSelection = false
        guard panel.runModal() == .OK, let url = panel.url else { return }
        guard url.pathExtension.lowercased() == "docx" else {
            errorText = "Escolha um DOCX. No Pages, use Arquivo → Exportar Para → Word."
            return
        }
        guard mayReplaceReport() else { return }
        saveSearchSettings()
        originalURL = nil
        documentURL = url
        restoreSearchSettings()
        screen = .preparation; analysisFailed = false
        report = nil; reportURL = nil; selectedID = nil; decisions = [:]
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
        panel.allowedContentTypes = [UTType(filenameExtension: "docx") ?? .data]
        panel.allowsMultipleSelection = false
        guard panel.runModal() == .OK, let url = panel.url else { return }
        guard url.pathExtension.lowercased() == "docx", url != documentURL else {
            errorText = "Selecione outro DOCX: a versão anterior à revisão."
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

    private func supportDirectory(_ component: String) throws -> URL {
        guard let base = manager.urls(for: .applicationSupportDirectory, in: .userDomainMask).first else {
            throw FonteError.message("A pasta de dados do aplicativo não está disponível.")
        }
        let url = base.appendingPathComponent("FONTE", isDirectory: true).appendingPathComponent(component, isDirectory: true)
        try manager.createDirectory(at: url, withIntermediateDirectories: true)
        return url
    }

    private func decisionURL(for report: EditorialReport) throws -> URL {
        try supportDirectory("Decisoes").appendingPathComponent(report.sha256 + ".json")
    }

    private func readData(_ url: URL) throws -> Data {
        let attrs = try manager.attributesOfItem(atPath: url.path)
        guard let size = attrs[.size] as? NSNumber, size.intValue <= 25_000_000 else {
            throw FonteError.message("O JSON excede o limite de 25 MB desta interface.")
        }
        return try Data(contentsOf: url)
    }

    private func loadReport(_ url: URL) throws {
        let loaded = try JSONDecoder().decode(EditorialReport.self, from: readData(url))
        try loaded.validate()
        var restored: [String: ReviewDecision] = [:]
        let cache = try decisionURL(for: loaded)
        if manager.fileExists(atPath: cache.path) {
            do {
                restored = try parseDecisions(readData(cache), for: loaded)
            } catch {
                // Preserva o arquivo problemático antes de permitir novos salvamentos.
                let backup = cache.deletingPathExtension().appendingPathExtension("recuperacao-\(UUID().uuidString).json")
                try manager.copyItem(at: cache, to: backup)
                errorText = "Não foi possível restaurar as decisões locais. Uma cópia foi preservada em \(backup.path)."
            }
        }
        report = loaded; reportURL = url; decisions = restored
        analysisStages = loaded.metadata.stages ?? []
        screen = .review; analysisFailed = false
        selectedID = loaded.findings.first?.id
        category = "Todas"; decisionFilter = "Todas"; search = ""; layerFilter = "Todas"; moduleFilter = "Todas"; severityFilter = "Todas"
        hasUnsavedDecisions = false
        status = "\(loaded.findings.count) candidatos. Avalie cada trecho no contexto."
    }

    func analyze() { start(.analyze) }
    func install() { start(.install) }
    func diagnose() { start(.diagnose) }

    private func start(_ job: Job) {
        guard !isBusy, let directory = engineDirectory else { return }
        if job == .install && embeddedEngine != nil { return }
        if job == .analyze && (!canAnalyze || !mayReplaceReport()) { return }
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
                   engine.version.compare("0.6.0", options: .numeric) == .orderedAscending {
                    throw FonteError.message("A revisão modular exige FONTE 0.6.0 ou posterior. Restaure o motor embutido desta versão do Lume ou instale a atualização do motor.")
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
                    let result = try await runner.run(executable: executable, arguments: arguments, directory: directory, logURL: log)
                    if job == .analyze { updateProgress(from: log) }
                    if result.cancelled {
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
                    case .install: status = "Analisador preparado. Escolha um DOCX e clique em Analisar."
                    case .diagnose: status = "Instalação verificada. O analisador está disponível."
                    }
                } catch {
                    if job == .analyze { analysisFailed = true }
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
            if stage.state == "running", canCancel { jobLabel = stage.title + "…" }
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
                                decisions: decisions.mapValues(\.rawValue))
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        return try encoder.encode(file)
    }

    private func autosave() throws {
        guard let report = report else { return }
        try payload().write(to: decisionURL(for: report), options: .atomic)
        hasUnsavedDecisions = false
    }

    private func parseDecisions(_ data: Data, for report: EditorialReport) throws -> [String: ReviewDecision] {
        let file = try JSONDecoder().decode(DecisionFile.self, from: data)
        guard file.schemaVersion == 1, file.sha256 == report.sha256 else {
            throw FonteError.message("As decisões pertencem a outra versão do manuscrito.")
        }
        return file.decisions.reduce(into: [:]) { result, entry in
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

    func copyParagraph(_ finding: Finding) {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(finding.text, forType: .string)
        status = "Parágrafo copiado. Use ⌘F no Pages ou Word."
    }

    func revealReport() {
        if let url = reportURL { NSWorkspace.shared.activateFileViewerSelecting([url]) }
    }
    func openHTML() {
        guard let url = reportURL?.deletingPathExtension().appendingPathExtension("html"), manager.fileExists(atPath: url.path) else {
            errorText = "O HTML correspondente não está junto deste JSON. O relatório pode ser revisado nesta janela."
            return
        }
        NSWorkspace.shared.open(url)
    }
    func openLog() {
        if let url = logURL { NSWorkspace.shared.open(url) }
    }
}
