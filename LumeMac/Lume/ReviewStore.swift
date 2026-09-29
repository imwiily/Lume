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
    @Published var decisions: [String: ReviewDecision] = [:]
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
    @Published private(set) var hasAPIKey = AnthropicKey.exists()
    @Published var coherenceEstimate: CoherenceEstimate?
    private var coherenceConfirmed = false
    var coherenceActive: Bool { useCoherenceAI && analysisMode != "linguistica" }
    @Published var isBusy = false
    @Published var canCancel = false
    @Published var jobLabel = ""
    @Published var status = "Escolha um manuscrito ou abra um relatório existente."
    @Published var errorText: String?
    @Published var logURL: URL?
    @Published var hasUnsavedDecisions = false

    private enum Job: Equatable { case analyze, install, diagnose, estimate }
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

    func analyze() {
        guard coherenceActive, !coherenceConfirmed else { return start(.analyze) }
        guard hasAPIKey else {
            errorText = "Configure a chave da API da Anthropic para usar a Coerência com IA, ou desligue a opção."
            return
        }
        start(.estimate)
    }

    func confirmCoherence() {
        coherenceEstimate = nil
        coherenceConfirmed = true
        start(.analyze)
    }

    func cancelCoherence() {
        coherenceEstimate = nil
        status = "Análise cancelada antes de enviar qualquer texto."
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

    private var coherenceProject: URL? {
        guard let document = documentURL else { return nil }
        let name = document.deletingPathExtension().lastPathComponent
        let safe = String(name.map { $0.isLetter || $0.isNumber || $0 == "-" || $0 == " " ? $0 : "-" })
        return try? supportDirectory("Coerencia").appendingPathComponent(safe, isDirectory: true)
    }
    func install() { start(.install) }
    func diagnose() { start(.diagnose) }

    private func start(_ job: Job) {
        guard !isBusy, let directory = engineDirectory else { return }
        if job == .install && embeddedEngine != nil { return }
        if job == .estimate && (!canAnalyze || !mayReplaceReport()) { return }
        if job == .analyze && (!canAnalyze || (!coherenceConfirmed && !mayReplaceReport())) { return }
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
                if coherenceActive, coherenceConfirmed, let project = coherenceProject {
                    guard let key = AnthropicKey.read() else {
                        coherenceConfirmed = false
                        throw FonteError.message("Não foi possível ler a chave da API nas Chaves do macOS. Configure-a novamente.")
                    }
                    environment["ANTHROPIC_API_KEY"] = key
                    arguments += ["--coerencia-ia", "--coerencia-projeto", project.path, "--coerencia-modelo", coherenceModel,
                                  "--coerencia-teto", String(format: "%.2f", locale: Locale(identifier: "en_US_POSIX"), coherenceBudget)]
                }
                coherenceConfirmed = false
                jobLabel = "Analisando o manuscrito…"
            case .estimate:
                guard let input = documentURL, let python = pythonURL, let project = coherenceProject else { return }
                executable = python
                saveSearchSettings()
                let config = try supportDirectory("Configuracoes").appendingPathComponent(jobID + ".json")
                try searchSettings.encoded().write(to: config, options: .atomic)
                // Só lê o manuscrito e o estado do projeto; não chama a API.
                arguments = engineArguments + ["coerencia-estimar", input.path, "--coerencia-projeto", project.path,
                                               "--coerencia-modelo", coherenceModel, "--config", config.path]
                jobLabel = "Calculando o custo da Coerência com IA…"
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
                        analysisFailed = true
                        status = "Análise interrompida. O manuscrito foi preservado."
                        return
                    }
                    guard result.exitCode == 0 else {
                        let details = String(PythonRunner.tail(log).suffix(1800))
                        if job == .estimate {
                            throw FonteError.message("Não foi possível estimar a Coerência com IA. Se o motor selecionado for anterior a esta versão do Lume, use Motor de análise → Restaurar embutido.\n\n\(details)")
                        }
                        throw FonteError.message("A operação não foi concluída (código \(result.exitCode)).\n\n\(details)")
                    }
                    switch job {
                    case .analyze: try loadReport(output.appendingPathComponent("relatorio.json"))
                    case .estimate:
                        let prefix = "LUME_ESTIMATIVA "
                        guard let line = PythonRunner.tail(log).split(separator: "\n").last(where: { $0.hasPrefix(prefix) }),
                              let estimate = try? JSONDecoder().decode(CoherenceEstimate.self, from: Data(line.dropFirst(prefix.count).utf8)) else {
                            throw FonteError.message("O motor não devolveu a estimativa da Coerência com IA.")
                        }
                        coherenceEstimate = estimate
                        status = "Confira o envio e o custo estimado antes de continuar."

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

/// Estimativa do motor (`coerencia-estimar`) antes de qualquer envio à API.
struct CoherenceEstimate: Decodable {
    let modelo: String
    let capitulos: Int
    let aEnviar: Int
    let titulosAEnviar: [String]
    let caracteres: Int
    let custoEstimadoUsd: Double
    let custoMaximoUsd: Double

    enum CodingKeys: String, CodingKey {
        case modelo, capitulos, caracteres
        case aEnviar = "a_enviar", titulosAEnviar = "titulos_a_enviar"
        case custoEstimadoUsd = "custo_estimado_usd", custoMaximoUsd = "custo_maximo_usd"
    }

    var summary: String {
        guard aEnviar > 0 else {
            return "Nenhum capítulo mudou desde a última análise: nada será enviado e não há custo. As contradições já encontradas voltam ao relatório."
        }
        let lista = titulosAEnviar.prefix(6).joined(separator: ", ") + (titulosAEnviar.count > 6 ? "…" : "")
        return String(format: "%d de %d capítulos serão enviados à Anthropic (%@).\nCusto estimado: US$ %.2f (até US$ %.2f).\nOs demais capítulos não são enviados.",
                      aEnviar, capitulos, lista, custoEstimadoUsd, custoMaximoUsd)
    }
}

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
