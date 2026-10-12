import Foundation

/// Ponta a ponta entre o Swift e o motor congelado: o Lume executa os subcomandos da V5 pelo mesmo PythonRunner
/// do app e interpreta as respostas com os modelos reais. A "OpenAI" é um arquivo local de respostas simuladas
/// (variável LUME_V5_TRANSPORTE_SIMULADO): nenhuma chamada de rede, nenhuma chave real.
///
///     swiftc app/Lume/Models.swift app/Lume/ValidatorV5.swift app/Lume/PythonRunner.swift \
///            tests/ValidatorV5EngineCheck.swift -o build/validador-v5-motor
///     build/validador-v5-motor /caminho/Engine.lumemotor/runtime/lume-engine   # a partir da raiz do repositório
@main
struct ValidatorV5EngineCheck {
    static var failures = 0
    static func require(_ condition: Bool, _ message: String) {
        if !condition { failures += 1; print("FALHOU: " + message) }
    }

    static func run(_ engine: URL, _ args: [String], env: [String: String] = [:], tag: String, in dir: URL)
        async throws -> (exit: Int32, text: String, log: URL) {
        let log = dir.appendingPathComponent(tag + ".txt")
        let result = try await PythonRunner.shared.run(executable: engine, arguments: args, directory: dir, logURL: log,
                                                       extraEnvironment: env)
        return (result.exitCode, PythonRunner.tail(log), log)
    }

    static func sha(_ url: URL) throws -> Data { try Data(contentsOf: url) }

    @MainActor
    static func main() async throws {
        setvbuf(stdout, nil, _IONBF, 0)
        guard CommandLine.arguments.count == 2 else { print("Uso: validador-v5-motor /caminho/runtime/lume-engine"); exit(2) }
        let engine = URL(fileURLWithPath: CommandLine.arguments[1])
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("lume-v5-motor-" + UUID().uuidString)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }
        let original = URL(fileURLWithPath: "examples/Mestre/Manuscrito-modular.docx")
        let document = dir.appendingPathComponent("livro.docx")
        try FileManager.default.copyItem(at: original, to: document)
        let documentBytes = try sha(document)

        // 1. O motor analisa o exemplo (protocolo anterior continua valendo).
        let analysis = try await run(engine, ["revisar", document.path, "--saida", dir.appendingPathComponent("rel").path, "--tempo", "passado"],
                                     tag: "revisar", in: dir)
        require(analysis.exit == 0, "revisar falhou: \(analysis.text.suffix(300))")
        let reportURL = dir.appendingPathComponent("rel/relatorio.json")
        let report = try JSONDecoder().decode(EditorialReport.self, from: Data(contentsOf: reportURL))
        let candidates = report.findings.filter { f in
            let target = f.segments.marked
            return !target.isEmpty && f.text.components(separatedBy: target).count == 2
        }
        require(candidates.count >= 3, "relatório de exemplo sem 3 alertas utilizáveis")
        guard candidates.count >= 3 else { print("\(failures) falha(s): poucos alertas utilizáveis (\(report.findings.count) no total)."); exit(1) }
        let chosen = Array(candidates.prefix(3))
        let ids = chosen.map(\.id)
        let kinds: [ReviewDecision] = [.falsePositive, .style, .error]
        var decisionsObject: [String: String] = [:]
        for (f, d) in zip(chosen, kinds) { decisionsObject[f.id] = d.rawValue }
        let decisionsURL = dir.appendingPathComponent("decisoes.json")
        try JSONSerialization.data(withJSONObject: ["decisions": decisionsObject]).write(to: decisionsURL)
        let decisionsBytes = try sha(decisionsURL)
        let project = dir.appendingPathComponent("projeto")
        let common = ValidatorV5Arguments.common(document: document, report: reportURL, decisions: decisionsURL, project: project, config: nil)

        // 2. Estimativa (sem rede).
        let estimateRun = try await run(engine, try ValidatorV5Arguments.estimate(common: common, ids: ids), tag: "estimativa", in: dir)
        require(estimateRun.exit == 0, "estimativa falhou: \(estimateRun.text.suffix(300))")
        let estimate = try ValidatorV5Protocol.decode(ValidatorV5Estimate.self, .estimate, in: estimateRun.text)
        require(estimate?.accepted == 3 && estimate?.manuscriptVersion == "confere" && estimate?.hasWork == true
                && estimate?.fitsBudget == true && estimate?.secondRoundAuthorized == false, "estimativa do motor")
        require(!FileManager.default.fileExists(atPath: project.path), "estimar não grava nada")

        // 3. Texto exato do pedido.
        let previewRun = try await run(engine, try ValidatorV5Arguments.preview(common: common, ids: ids), tag: "previa", in: dir)
        let preview = try ValidatorV5Protocol.decode(ValidatorV5ExactPreview.self, .preview, in: previewRun.text)
        require(preview != nil && !(preview?.requests.isEmpty ?? true) && (preview?.instructionCharacters ?? 0) > 1000, "prévia do motor")
        let sentText = (preview?.requests.map(\.text) ?? []).joined(separator: "\n")
        for f in chosen { require(sentText.contains(f.text), "a prévia contém o parágrafo do alerta \(f.id)") }
        require(!sentText.contains("sk-"), "prévia sem chave")

        // 4. Execução com respostas simuladas, chave sentinela no ambiente e teto autorizado.
        let sentinel = "sk-teste-NAO-PODE-APARECER-0123456789012345678901"
        func entry(_ f: Finding, exists: String, nature: String, certainty: String, severity: String) -> [String: Any] {
            ["id": f.id, "ocorrencia": 1, "existe": exists, "natureza": nature, "certeza": certainty, "gravidade": severity,
             "justificativa_detector": "correta", "razao_literaria": "nao_se_aplica", "evidencia_suficiente": true,
             "explicacao": "Resposta simulada para o teste local.", "evidencia": exists == "sim" || exists == "nao" ? f.segments.marked : "",
             "evidencia_razao": "", "recomendacao": "", "problema_trecho": "", "problema_explicacao": "",
             "precisa_mais_contexto": false, "paragrafos_solicitados": [Int](), "termos_solicitados": [String](), "relacoes": [Any]()]
        }
        let scripted: [String: Any] = [chosen[0].id: entry(chosen[0], exists: "sim", nature: "objetivo", certainty: "clara", severity: "media"),
                                       chosen[1].id: entry(chosen[1], exists: "nao", nature: "nenhuma", certainty: "nao_se_aplica", severity: "nenhuma"),
                                       chosen[2].id: entry(chosen[2], exists: "nao", nature: "nenhuma", certainty: "nao_se_aplica", severity: "nenhuma")]
        let simulated = dir.appendingPathComponent("simulado.json")
        try JSONSerialization.data(withJSONObject: ["avaliacoes": scripted]).write(to: simulated)
        let environment = OpenAIKey.environment(for: sentinel).merging(["LUME_V5_TRANSPORTE_SIMULADO": simulated.path]) { $1 }
        let runArgs = try ValidatorV5Arguments.run(common: common, ids: ids, budget: 1.0)
        require(!runArgs.joined().contains("sk-"), "argumentos sem chave")
        let first = try await run(engine, runArgs, env: environment, tag: "execucao", in: dir)
        require(first.exit == 0, "execução falhou: \(first.text.suffix(400))")
        let finished = try ValidatorV5Protocol.decode(ValidatorV5Run.self, .finished, in: first.text)
        require(finished?.analysedNow == 3 && finished?.decisionsChanged == false && finished?.summary?.interrupted == false,
                "execução: três itens, decisões intactas")
        require(ValidatorV5Protocol.lastPayload(.progress, in: first.text) != nil, "progresso emitido")
        require(!first.text.contains(sentinel), "a chave não aparece no registro do motor")

        // 5. Resultados no Swift, sem alterar decisões nem manuscrito.
        let resultsRun = try await run(engine, ValidatorV5Arguments.results(common: common), tag: "resultados", in: dir)
        let results = try ValidatorV5Protocol.decode(ValidatorV5Results.self, .results, in: resultsRun.text)
        require(results?.items.count == 3, "três resultados")
        let byID = Dictionary(uniqueKeysWithValues: (results?.items ?? []).map { ($0.id, $0) })
        require(byID[ids[0]]?.result == "contestada" && byID[ids[0]]?.existence.exists == "sim"
                && byID[ids[0]]?.disagreementMeaning?.contains("falso positivo") == true, "falso positivo contestado, com significado")
        require(byID[ids[1]]?.result == "mantida" && byID[ids[1]]?.disagreementMeaning == nil, "estilo mantido")
        require(byID[ids[2]]?.result == "contestada" && byID[ids[2]]?.disagreementMeaning?.contains("não existe") == true,
                "erro confirmado contestado: a IA não vê o problema, sem chamar de erro")
        require((results?.items ?? []).allSatisfy { $0.suggestionApplied == false && $0.isCurrent }, "nada aplicado; resultados válidos")
        let live = Dictionary(uniqueKeysWithValues: zip(ids, kinds))
        require(results?.current(for: live).count == 3, "resultados vigentes para as decisões atuais")

        // 6. Sem execução duplicada: repetir não reenvia nem cobra.
        let again = try await run(engine, runArgs, env: environment, tag: "repeticao", in: dir)
        let repeated = try ValidatorV5Protocol.decode(ValidatorV5Run.self, .finished, in: again.text)
        require(repeated?.analysedNow == 0 && repeated?.summary?.reused == 3 && repeated?.summary?.requests == 0,
                "repetição reaproveita os resultados e não faz pedidos")

        // 7. Teto: insuficiente e acima do máximo são recusados antes de qualquer envio.
        let fresh = dir.appendingPathComponent("projeto-teto")
        let freshCommon = ValidatorV5Arguments.common(document: document, report: reportURL, decisions: decisionsURL, project: fresh, config: nil)
        let low = try await run(engine, ["validar-decisoes-v5"] + freshCommon + ["--ids"] + ids + ["--teto", "0.01", "--tentativas", "1"],
                                env: environment, tag: "teto-baixo", in: dir)
        require(ValidatorV5Protocol.failure(in: low.text)?.code == "teto_insuficiente" && low.exit == 2, "teto insuficiente")
        let high = try await run(engine, ["validar-decisoes-v5"] + freshCommon + ["--ids"] + ids + ["--teto", "6", "--tentativas", "1"],
                                 env: environment, tag: "teto-alto", in: dir)
        require(ValidatorV5Protocol.failure(in: high.text)?.code == "teto_invalido", "teto acima do máximo")
        require(!FileManager.default.fileExists(atPath: fresh.appendingPathComponent("validacoes-v5.json").path), "recusa não grava resultados")

        // 8. Protocolos anteriores intactos: a estimativa do V2 continua saindo com o prefixo antigo.
        let legacy = try await run(engine, ["validar-decisoes-estimar", document.path, "--relatorio", reportURL.path,
                                            "--decisoes", decisionsURL.path, "--projeto", dir.appendingPathComponent("v2").path],
                                   tag: "v2", in: dir)
        require(legacy.text.contains("LUME_ESTIMATIVA_VALIDADOR ") && ValidatorV5Protocol.lastPayload(.estimate, in: legacy.text) == nil,
                "V2 mantém o próprio protocolo")

        // 9. Nada do autor mudou.
        require(try sha(decisionsURL) == decisionsBytes, "arquivo de decisões intacto")
        require(try sha(document) == documentBytes, "manuscrito intacto")

        if failures > 0 { print("\(failures) falha(s)."); exit(1) }
        print("ValidatorV5EngineCheck: tudo certo.")
    }
}
