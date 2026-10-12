import Foundation

/// Fase 2 do Validador V5: chave da OpenAI, argumentos sem segredos, protocolo JSON e resultados da IA como
/// dado separado das decisões. Sem rede, sem API e sem Keychain real (exceto serviços de teste descartáveis).
///
///     swiftc app/Lume/Models.swift app/Lume/ValidatorV5.swift app/Lume/PythonRunner.swift \
///            tests/ValidatorV5Check.swift -o build/validador-v5-swift
///     build/validador-v5-swift            # a partir da raiz do repositório
@main
struct ValidatorV5Check {
    static var failures = 0
    static func require(_ condition: Bool, _ message: String) {
        if !condition { failures += 1; print("FALHOU: " + message) }
    }

    final class MemoryStore: SecretStore {
        var value: String?
        func exists() -> Bool { value != nil }
        func read() -> String? { value }
        func save(_ secret: String) throws { value = secret }
        func delete() { value = nil }
    }

    static func line(_ prefix: ValidatorV5Prefix, _ object: Any) -> String {
        let data = try! JSONSerialization.data(withJSONObject: object, options: [.sortedKeys])
        return prefix.rawValue + String(decoding: data, as: UTF8.self)
    }

    @MainActor
    static func main() async throws {
        let raw = try Data(contentsOf: URL(fileURLWithPath: "tests/fixtures/validador-v5-protocolo.json"))
        let fixtures = try JSONSerialization.jsonObject(with: raw) as! [String: Any]
        let estimateLine = line(.estimate, fixtures["estimate"]!)
        let progressLine = line(.progress, fixtures["progress"]!)
        let finishedLine = line(.finished, fixtures["finished"]!)
        let resultsLine = line(.results, fixtures["results"]!)
        let failureLine = line(.failure, fixtures["failure"]!)

        // 1. Interpretação dos cinco tipos de linha, com os dados do backend real (texto sintético).
        let estimate = try ValidatorV5Protocol.decode(ValidatorV5Estimate.self, .estimate, in: estimateLine)!
        require(estimate.provider == "openai" && estimate.effort == "medium" && estimate.accepted == 5, "estimativa: provedor, esforço, aceitas")
        require(estimate.toSend.count == 5 && estimate.excluded.isEmpty && estimate.reused == 0 && estimate.notLocated == 0, "estimativa: itens")
        require(estimate.fitsBudget && estimate.budgetUsd == 1.0 && estimate.maximumBudgetUsd == 5.0 && estimate.defaultBudgetUsd == 1.0, "estimativa: tetos")
        require(estimate.maximumUsd > estimate.expectedUsd && estimate.minimumBudgetUsd >= estimate.worstRequestUsd, "estimativa: esperado, máximo, mínimo")
        require(!estimate.secondRoundAuthorized && estimate.hasWork && estimate.manuscriptVersion == "confere", "estimativa: segunda rodada e versão")
        require(estimate.verification["versao_confere"] == 5 && !estimate.chapters.isEmpty, "estimativa: verificação e capítulos")
        let progress = try ValidatorV5Protocol.decode(ValidatorV5Progress.self, .progress, in: progressLine)!
        require(progress == ValidatorV5Progress(stage: "avaliacao", done: 3, total: 5), "progresso")
        let run = try ValidatorV5Protocol.decode(ValidatorV5Run.self, .finished, in: finishedLine)!
        require(!run.decisionsChanged && run.analysedNow == 5 && !run.secondRoundAuthorized, "execução: decisões intactas e contagem")
        require(run.pendingContext == 1 && run.summary?.results["contestada"] == 1 && run.summary?.interrupted == false, "execução: pendência e resumo")
        require((run.summary?.costUsd ?? -1) >= 0 && (run.summary?.requests ?? 0) >= 1, "execução: custo e pedidos")
        let results = try ValidatorV5Protocol.decode(ValidatorV5Results.self, .results, in: resultsLine)!
        require(results.items.count == 5 && results.outdated == 0 && results.counts["contestada"] == 1, "resultados: itens e contagem")
        let failure = ValidatorV5Protocol.failure(in: "ruído\n" + failureLine)
        require(failure == ValidatorV5Failure(code: "teto_insuficiente", message: fixtures["failure"].flatMap { ($0 as? [String: String])?["mensagem"] }!), "erro estruturado")

        // 2. IA separada da decisão humana: nada nos resultados aplica ou altera decisão.
        let byParagraph = Dictionary(uniqueKeysWithValues: results.items.map { ($0.paragraph, $0) })
        let contested = byParagraph[10]!
        require(contested.result == "contestada" && contested.previousDecision == "Falso positivo" && contested.existence.exists == "sim"
                && contested.decisionAdequacy == "inadequada", "campos separados: decisão, existência, adequação, resultado")
        require(contested.disagreementMeaning?.contains("existe um problema onde você marcou falso positivo") == true, "significado da contestação")
        require(contested.suggestionApplied == false && contested.notice.contains("não é confirmação humana"), "sugestão nunca aplicada e aviso")
        require(!(contested.resultLabel.lowercased().contains("erro")), "rótulo não chama contestação de erro")
        let inconclusive = byParagraph[56]!
        require(inconclusive.result == "inconclusiva" && inconclusive.existence.exists == "incerto" && inconclusive.disagreementMeaning == nil
                && inconclusive.uncertainties.contains { $0.contains("existe = incerto") }, "inconclusiva mostra incerteza")
        require(byParagraph[56]!.pendingContext?.paragraphs == [9] && byParagraph[56]!.uncertainties.contains { $0.contains("não foi autorizada") }, "pendência de contexto")
        var decisions: [String: ReviewDecision] = [:]
        for item in results.items { decisions[item.id] = ReviewDecision(rawValue: item.currentDecision ?? "") ?? .pending }
        let before = decisions
        let valid = results.current(for: decisions)
        require(valid.count == 5 && decisions == before, "current(for:) só filtra; decisões intactas")
        decisions[contested.id] = .style
        require(results.current(for: decisions).count == 4 && decisions[contested.id] == .style, "decisão mudada: resultado antigo sai de vigência")
        let mirror = Mirror(reflecting: contested)
        require(!mirror.children.contains { $0.value is ReviewDecision }, "o item da IA não carrega ReviewDecision")

        // 3. Protocolos anteriores intactos: prefixos próprios e sem confusão.
        let legacy = ["LUME_PROGRESS {\"etapa\": \"x\"}", "LUME_ESTIMATIVA_VALIDADOR {\"triagem\": \"a\"}",
                      "LUME_VALIDADOR_PROGRESSO {\"etapa\": \"triagem\", \"feitos\": 1, \"total\": 2}",
                      "LUME_VALIDACAO {\"arquivo\": \"/x\", \"resumo\": {}}", "LUME_ESTIMATIVA {\"x\": 1}"]
        let mixed = (legacy + [estimateLine, finishedLine, resultsLine]).joined(separator: "\n")
        require(ValidatorV5Protocol.lastPayload(.finished, in: mixed) != nil, "V5 reconhecido entre linhas antigas")
        require(ValidatorV5Protocol.lastPayload(.progress, in: legacy.joined(separator: "\n")) == nil, "linhas antigas não viram progresso V5")
        require(ValidatorV5Protocol.lastPayload(.failure, in: mixed) == nil && ValidatorV5Protocol.failure(in: mixed) == nil, "sem erro V5 inventado")
        for prefix in ValidatorV5Prefix.allCases {
            require(prefix.rawValue.hasSuffix(" ") && prefix.rawValue.contains("V5"), "prefixo V5 explícito: \(prefix.rawValue)")
        }
        require(!finishedLine.hasPrefix("LUME_VALIDACAO ") && !progressLine.hasPrefix("LUME_VALIDADOR_PROGRESSO ")
                && !estimateLine.hasPrefix("LUME_ESTIMATIVA_VALIDADOR "), "o leitor do V2 (prefixo com espaço) ignora linhas V5")
        require((try? ValidatorV5Protocol.decode(ValidatorV5Run.self, .finished, in: "LUME_VALIDACAO_V5 {truncado")) == nil, "JSON truncado não decodifica")
        require(ValidatorV5Protocol.failure(in: "LUME_VALIDADOR_V5_ERRO {lixo") == nil, "erro ilegível é ignorado, não derruba")

        // 4. Argumentos do backend: sem segredos; piloto com uma tentativa e versão exata.
        let common = ValidatorV5Arguments.common(document: URL(fileURLWithPath: "/m/livro.docx"), report: URL(fileURLWithPath: "/m/r.json"),
                                                 decisions: URL(fileURLWithPath: "/m/d.json"), project: URL(fileURLWithPath: "/m/p"), config: nil)
        let runArgs = try ValidatorV5Arguments.run(common: common, ids: ["b", "a", "b"], budget: 1.0)
        require(runArgs.first == "validar-decisoes-v5" && runArgs.contains("--tentativas") && runArgs[runArgs.firstIndex(of: "--tentativas")! + 1] == "1", "execução: --tentativas 1")
        require(runArgs[runArgs.firstIndex(of: "--ids")! + 1] == "b" && runArgs[runArgs.firstIndex(of: "--ids")! + 2] == "a", "ids únicos na ordem dada")
        for forbidden in ["--permitir-contexto-parcial", "--autorizar-contexto-adicional", "--reanalisar"] {
            require(!runArgs.contains(forbidden), "argumento proibido no piloto: \(forbidden)")
        }
        let withOptions = try ValidatorV5Arguments.run(common: common, ids: ["a", "b"], revalidate: ["b", "zz"], partialContext: true)
        require(withOptions.contains("--permitir-contexto-parcial") && withOptions.contains("--revalidar")
                && withOptions[withOptions.firstIndex(of: "--revalidar")! + 1] == "b" && !withOptions.contains("zz"),
                "opções explícitas: revalidar só os selecionados e contexto parcial")
        require(!withOptions.contains("--reanalisar") && !withOptions.contains("--autorizar-contexto-adicional"), "reanálise e segunda rodada seguem fora")
        let estimateArgs = try ValidatorV5Arguments.estimate(common: common, ids: ["a"], budget: 2.5)
        require(estimateArgs.first == "validar-decisoes-v5-estimar" && !estimateArgs.contains("--tentativas") && estimateArgs.contains("2.50"), "estimativa: argumentos")
        func thrown(_ body: () throws -> [String]) -> ValidatorV5Arguments.Problem? {
            do { _ = try body(); return nil } catch { return error as? ValidatorV5Arguments.Problem }
        }
        require(thrown { try ValidatorV5Arguments.run(common: common, ids: []) } == .noItems, "sem itens")
        require(thrown { try ValidatorV5Arguments.run(common: common, ids: (0..<41).map(String.init)) } == .tooManyItems(41), "itens demais")
        require(thrown { try ValidatorV5Arguments.run(common: common, ids: ["a"], budget: 5.01) } == .invalidBudget, "teto acima do máximo")
        require(thrown { try ValidatorV5Arguments.run(common: common, ids: ["a"], budget: 0) } == .invalidBudget, "teto zero")
        require(thrown { try ValidatorV5Arguments.run(common: common, ids: ["a"], budget: .nan) } == .invalidBudget, "teto NaN")
        let sentinel = "sk-teste-NAO-PODE-APARECER-0123456789012345678901"
        require(!(runArgs + estimateArgs).contains { $0.contains("sk-") || $0.contains(sentinel) }, "nenhuma chave nos argumentos")

        // 5. Chave: ausente, válida e inválida, sem API e sem Keychain real.
        let memory = MemoryStore()
        OpenAIKey.store = memory
        require(!OpenAIKey.exists() && OpenAIKey.read() == nil, "sem chave: o app segue normal")
        for (bad, problem) in [("", OpenAIKey.Problem.empty), ("   \n", .empty), ("sk-ant-api03-" + String(repeating: "x", count: 60), .wrongProvider),
                               ("abc123", .notAnOpenAIKey), ("sk-curta", .tooShort), ("sk-" + String(repeating: "a", count: 30) + " " + String(repeating: "b", count: 30), .unexpectedCharacters)] {
            if case .failure(let found) = OpenAIKey.validate(bad) { require(found == problem, "problema esperado \(problem) para entrada inválida") }
            else { require(false, "entrada inválida aceita") }
            do { try OpenAIKey.save(bad); require(false, "save aceitou chave inválida") }
            catch { require(!error.localizedDescription.contains(bad) || bad.isEmpty || bad.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty, "mensagem repete a chave") }
        }
        require(memory.value == nil, "chave inválida nunca é gravada")
        try OpenAIKey.save("  " + sentinel + "\n")
        require(OpenAIKey.exists() && OpenAIKey.read() == sentinel, "chave válida: guardada sem espaços")
        require(OpenAIKey.environment(for: sentinel) == ["OPENAI_API_KEY": sentinel], "chave só pelo ambiente do processo")
        OpenAIKey.delete()
        require(!OpenAIKey.exists(), "remoção")
        if case .success(let proj) = OpenAIKey.validate("sk-proj-" + String(repeating: "A1_-", count: 20)) { require(proj.hasPrefix("sk-proj-"), "formato sk-proj aceito") }
        else { require(false, "formato sk-proj rejeitado") }

        // 6. Isolamento entre provedores: serviços distintos e itens independentes no Keychain.
        require(OpenAIKey.service == "lume-openai" && OpenAIKey.service != "coerencia-anthropic", "serviços distintos")
        let suffix = UUID().uuidString
        let openAIStore = KeychainSecretStore(service: "lume-openai-teste-" + suffix)
        let anthropicStore = KeychainSecretStore(service: "coerencia-anthropic-teste-" + suffix)
        defer { openAIStore.delete(); anthropicStore.delete() }
        do {
            try openAIStore.save(sentinel)
            require(openAIStore.read() == sentinel && !anthropicStore.exists() && anthropicStore.read() == nil, "Keychain: chave de um provedor não aparece no outro")
            try anthropicStore.save("sk-ant-api03-" + String(repeating: "z", count: 60))
            openAIStore.delete()
            require(!openAIStore.exists() && anthropicStore.exists(), "Keychain: remover a OpenAI preserva a Anthropic")
        } catch {
            print("PENDENTE: Keychain real indisponível neste ambiente (\(error.localizedDescription)); isolamento coberto só por serviços e memória.")
        }

        // 7. Redação em registros e mensagens.
        let log = "Traceback...\nAuthorization: Bearer \(sentinel)\nsk-proj-AAAABBBBCCCCDDDD1111 e texto normal sk-curto"
        let redacted = SecretRedactor.redact(log, secrets: [sentinel])
        require(!redacted.contains(sentinel) && !redacted.contains("sk-proj-AAAA") && redacted.contains("texto normal sk-curto"), "redação de chaves")
        let tmp = FileManager.default.temporaryDirectory.appendingPathComponent("lume-v5-" + suffix + ".txt")
        try Data(log.utf8).write(to: tmp)
        defer { try? FileManager.default.removeItem(at: tmp) }
        require(!PythonRunner.safeTail(tmp).contains("sk-proj-AAAA") && PythonRunner.tail(tmp).contains("sk-proj-AAAA"), "safeTail redige; tail original intacto")

        // 7b. Linhas de protocolo maiores que 32 KB (40 resultados) precisam ser lidas inteiras.
        let big = FileManager.default.temporaryDirectory.appendingPathComponent("lume-v5-grande-" + UUID().uuidString + ".txt")
        defer { try? FileManager.default.removeItem(at: big) }
        let bigResults = line(.results, fixtures["results"]!)
        var items = (fixtures["results"] as! [String: Any])["itens"] as! [[String: Any]]
        while items.count < 60 { items += items.prefix(5).map { $0 } }
        var oversized = fixtures["results"] as! [String: Any]; oversized["itens"] = items
        let oversizedLine = line(.results, oversized)
        try Data((oversizedLine + "\n").utf8).write(to: big)
        require(oversizedLine.utf8.count > 32_768, "linha de teste maior que 32 KB")
        require(ValidatorV5Protocol.lastPayload(.results, in: PythonRunner.tail(big)) == nil, "tail perde a linha grande (motivo do defeito)")
        let whole = try ValidatorV5Protocol.decode(ValidatorV5Results.self, .results, in: PythonRunner.text(big))
        require(whole?.items.count == items.count, "text lê a linha inteira")
        _ = bigResults

        // 8. Backend: V5 por padrão; V2 só por escolha explícita; valor desconhecido volta ao padrão.
        let defaults = UserDefaults(suiteName: "lume-v5-teste-" + suffix)!
        defer { defaults.removePersistentDomain(forName: "lume-v5-teste-" + suffix) }
        require(ValidatorBackend.current(defaults) == .v5, "padrão: V5")
        defaults.set("qualquer", forKey: ValidatorBackend.defaultsKey)
        require(ValidatorBackend.current(defaults) == .v5, "valor desconhecido: V5")
        defaults.set(ValidatorBackend.v2.rawValue, forKey: ValidatorBackend.defaultsKey)
        require(ValidatorBackend.current(defaults) == .v2, "V2 como alternativa manual")

        // 9. Lotes sucessivos de até 40, sempre com nova confirmação.
        let many = (0..<100).map { "id\($0)" }
        let plan = ValidatorV5Batching.plan(many + ["id0", "id1"])
        require(plan.next.count == 40 && plan.remaining == 60 && plan.batches == 3 && plan.next.first == "id0", "100 decisões: 3 lotes de até 40")
        require(ValidatorV5Batching.plan(Array(many.prefix(40))).batches == 1 && ValidatorV5Batching.plan([]).next.isEmpty, "40 cabem em um lote; vazio não gera lote")
        require(ValidatorV5Batching.plan(many, limit: 500).next.count == ValidatorV5Arguments.maxItems, "limite do backend respeitado")

        // 10. Classificação A–F a partir do diagnóstico completo.
        let base = ((fixtures["results"] as! [String: Any])["itens"] as! [[String: Any]])[0]
        func make(_ result: String, exists: String, nature: String = "objetivo", certainty: String = "clara", adequacy: String,
                  decision: String = "Falso positivo", evidence: Bool = true, situation: String = "valida",
                  current: Bool = true) -> ValidatorV5Item {
            var o = base
            o["resultado"] = result; o["adequacao_da_decisao_segundo_a_ia"] = adequacy
            o["decisao_humana_anterior"] = decision; o["decisao_humana_atual"] = decision
            o["existencia_segundo_a_ia"] = ["existe": exists, "natureza": nature, "certeza": certainty, "gravidade": "media", "rotulo": "x"]
            o["evidencias_verificadas"] = evidence ? [["papel": "problema_tecnico", "paragrafo": 1, "trecho": "x"]] : [[String: Any]]()
            o["situacao"] = situation; o["vale_para_o_texto_e_decisao_atuais"] = current
            return try! JSONDecoder().decode(ValidatorV5Item.self, from: JSONSerialization.data(withJSONObject: o))
        }
        func kind(_ item: ValidatorV5Item?, live: ReviewDecision? = nil) -> DecisionAssessment {
            ValidatorV5Assessment.classify(item, liveDecision: live ?? item.flatMap { ReviewDecision(rawValue: $0.previousDecision ?? "") })
        }
        require(kind(nil) == .notAnalyzed, "sem resultado: ainda não analisada")
        require(kind(make("mantida", exists: "nao", nature: "nenhuma", certainty: "nao_se_aplica", adequacy: "adequada")) == .probablyCorrect,
                "A: falso positivo sem problema, com evidência")
        require(kind(make("apontamento_inadequado", exists: "nao", nature: "nenhuma", certainty: "nao_se_aplica", adequacy: "adequada",
                          decision: "Falso positivo")) == .probablyCorrect, "ausência de problema num alerta já rejeitado nunca é possível erro")
        require(kind(make("mantida", exists: "sim", adequacy: "adequada", decision: "Erro confirmado")) == .probablyCorrect, "A: erro confirmado sustentado")
        require(kind(make("mantida", exists: "nao", adequacy: "adequada", evidence: false)) == .inconclusive, "sem evidência verificada: inconclusiva")
        require(kind(make("mantida", exists: "incerto", adequacy: "adequada")) == .inconclusive, "existência incerta: inconclusiva")
        require(kind(make("mantida", exists: "sim", adequacy: "inadequada")) == .inconclusive, "resultado contraditório: inconclusiva")
        require(kind(make("contestada", exists: "sim", adequacy: "inadequada", decision: "Falso positivo")) == .possibleError,
                "B: a IA vê desvio objetivo e claro que o autor rejeitou")
        require(kind(make("contestada", exists: "nao", nature: "nenhuma", certainty: "nao_se_aplica", adequacy: "inadequada",
                          decision: "Erro confirmado")) == .possibleError, "B: a IA não vê o erro que o autor confirmou")
        require(kind(make("contestada", exists: "sim", nature: "interpretativo", certainty: "discutivel", adequacy: "inadequada",
                          decision: "Estilo do autor")) == .reviewRecommended, "C: discordância interpretativa não afirma erro")
        require(kind(make("contestada", exists: "sim", adequacy: "inadequada", evidence: false)) == .inconclusive, "contestação sem evidência: inconclusiva")
        require(kind(make("revisao_recomendada", exists: "sim", nature: "interpretativo", certainty: "discutivel", adequacy: "indeterminada",
                          decision: "Estilo do autor")) == .reviewRecommended, "C: revisão recomendada")
        require(kind(make("inconclusiva", exists: "incerto", nature: "interpretativo", certainty: "discutivel", adequacy: "indeterminada")) == .inconclusive, "D")
        let fresh = make("mantida", exists: "nao", adequacy: "adequada")
        require(kind(fresh, live: .style) == .outdated, "F: a decisão mudou depois da análise")
        require(kind(make("mantida", exists: "nao", adequacy: "adequada", situation: "desatualizada_conteudo", current: false)) == .outdated,
                "F: o texto mudou")
        require(kind(make("mantida", exists: "nao", adequacy: "adequada", situation: "desatualizada_configuracao", current: false)) == .outdated,
                "F: a configuração mudou")
        for a in DecisionAssessment.allCases {
            let text = ValidatorV5Assessment.explanation(a, item: fresh).lowercased() + a.title.lowercased()
            require(!text.contains("você acertou") && !text.contains("você errou") && !text.contains("erro confirmado"), "linguagem neutra: \(a)")
        }
        require(Set(DecisionAssessment.allCases.map(\.title)).count == 6 && DecisionAssessment.notAnalyzed.needsRun && DecisionAssessment.outdated.needsRun
                && !DecisionAssessment.probablyCorrect.needsRun, "seis categorias; só E e F pedem execução")

        try await flows(fixtures: fixtures)
        wording(fixtures: fixtures)

        if failures > 0 { print("\(failures) falha(s)."); exit(1) }
        print("ValidatorV5Check: tudo certo.")
    }

    // MARK: Fase 3 — fluxo, autorização, revalidação, cancelamento, parciais, invalidação e linguagem

    @MainActor
    final class FakeBackend {
        var estimates: [ValidatorV5Estimate] = []      // respostas sucessivas de `estimate`
        var estimateError: Error?
        var outcome: ValidatorV5Coordinator.Outcome = .finished
        var runError: Error?
        var stored: ValidatorV5Results
        var progressEvents: [ValidatorV5Progress] = []
        var estimateCalls = 0, runCalls = 0, resultCalls = 0, cancelCalls = 0
        var runIDs: [[String]] = []
        var resultIDs: [[String]] = []
        init(results: ValidatorV5Results) { stored = results }

        func backend() -> ValidatorV5Coordinator.Backend {
            .init(estimate: { [unowned self] _, _ in
                    estimateCalls += 1
                    if let e = estimateError { throw e }
                    return estimates[min(estimateCalls - 1, estimates.count - 1)]
                  },
                  run: { [unowned self] ids, _, progress in
                    runCalls += 1; runIDs.append(ids)
                    if let e = runError { throw e }
                    for event in progressEvents { progress(event) }
                    return outcome
                  },
                  results: { [unowned self] ids in resultCalls += 1; resultIDs.append(ids); return stored },
                  cancel: { [unowned self] in cancelCalls += 1 })
        }
    }

    static func decodeEstimate(_ object: [String: Any]) throws -> ValidatorV5Estimate {
        try JSONDecoder().decode(ValidatorV5Estimate.self, from: JSONSerialization.data(withJSONObject: object))
    }

    @MainActor
    static func flows(fixtures: [String: Any]) async throws {
        let base = fixtures["estimate"] as! [String: Any]
        let estimate = try decodeEstimate(base)
        let resultsData = try JSONSerialization.data(withJSONObject: fixtures["results"]!)
        let results = try JSONDecoder().decode(ValidatorV5Results.self, from: resultsData)
        let ids = estimate.toSend.map(\.id)
        let eligible = Set(ids)
        let sentinel = "sk-teste-NAO-PODE-APARECER-0123456789012345678901"

        // Seleção explícita: nada vazio, nada fora do elegível, nada acima do limite, teto no intervalo.
        do {
            let fake = FakeBackend(results: results); fake.estimates = [estimate]
            let c = ValidatorV5Coordinator(backend: fake.backend())
            await c.requestEstimate(ids: [], eligible: eligible, budget: 1)
            require(c.phase == .failed && fake.estimateCalls == 0 && c.failure != nil, "seleção vazia é recusada sem backend")
            await c.requestEstimate(ids: ids + (0..<40).map { "x\($0)" }, eligible: eligible.union((0..<40).map { "x\($0)" }), budget: 1)
            require(c.phase == .failed && fake.estimateCalls == 0, "acima do limite é recusado")
            await c.requestEstimate(ids: ids + ["intruso"], eligible: eligible, budget: 1)
            require(c.phase == .failed && fake.estimateCalls == 0, "item sem decisão elegível é recusado")
            await c.requestEstimate(ids: ids, eligible: eligible, budget: 5.01)
            require(c.phase == .failed && fake.estimateCalls == 0, "teto acima do máximo é recusado")
            await c.requestEstimate(ids: ids, eligible: eligible, budget: 1)
            require(c.phase == .awaitingAuthorization && c.estimate != nil && fake.estimateCalls == 1, "estimativa pedida só depois de passar nas regras")
            require(fake.runCalls == 0, "estimar nunca executa")
        }

        // Fluxo normal: autorização, revalidação, progresso, execução, resultados; nova execução exige nova autorização.
        do {
            let fake = FakeBackend(results: results); fake.estimates = [estimate, estimate]
            fake.progressEvents = [ValidatorV5Progress(stage: "avaliacao", done: 2, total: 5), ValidatorV5Progress(stage: "avaliacao", done: 5, total: 5)]
            let c = ValidatorV5Coordinator(backend: fake.backend(), secrets: { [sentinel] })
            var seen: [Int] = []
            await c.requestEstimate(ids: ids, eligible: eligible, budget: 1)
            await c.confirm(authorized: false)
            require(fake.runCalls == 0 && c.phase == .awaitingAuthorization, "sem autorização marcada nada é enviado")
            await c.confirm(authorized: true) { seen.append($0.done) }
            require(fake.estimateCalls == 2, "a estimativa é refeita imediatamente antes de enviar")
            require(fake.runCalls == 1 && fake.runIDs == [ids] && c.phase == .finished && seen == [2, 5], "execução única com progresso")
            require(c.results?.items.count == 5 && !c.partial && c.estimate == nil, "resultados completos e estimativa limpa")
            require(fake.resultIDs.last == [], "depois da execução, relê todos os resultados do projeto (não só o lote)")
            await c.confirm(authorized: true)
            require(fake.runCalls == 1, "a autorização não persiste para outra execução")
        }

        // Mudança relevante entre a estimativa mostrada e a execução: nova confirmação, nada enviado.
        do {
            var changed = base
            changed["a_enviar"] = Array((base["a_enviar"] as! [[String: Any]]).prefix(3))
            changed["custo_maximo_usd"] = (base["custo_maximo_usd"] as! Double) + 1.0
            let fresh = try decodeEstimate(changed)
            require(!estimate.isEquivalent(to: fresh) && estimate.isEquivalent(to: estimate), "equivalência de estimativas")
            let fake = FakeBackend(results: results); fake.estimates = [estimate, fresh, fresh]
            let c = ValidatorV5Coordinator(backend: fake.backend())
            await c.requestEstimate(ids: ids, eligible: eligible, budget: 1)
            await c.confirm(authorized: true)
            require(fake.runCalls == 0 && c.phase == .awaitingAuthorization && c.estimate?.toSend.count == 3 && c.notice != nil,
                    "estimativa mudou: não envia e pede nova confirmação")
            await c.confirm(authorized: true)
            require(fake.runCalls == 1 && c.phase == .finished, "com a estimativa nova confirmada, executa")
        }

        // Cancelamento antes do envio e durante a execução (resultados parciais preservados).
        do {
            let fake = FakeBackend(results: results); fake.estimates = [estimate, estimate]
            let c = ValidatorV5Coordinator(backend: fake.backend())
            await c.requestEstimate(ids: ids, eligible: eligible, budget: 1)
            c.cancelBeforeSend()
            require(c.phase == .idle && c.estimate == nil && fake.runCalls == 0 && c.notice?.contains("antes de enviar") == true, "cancelar antes de enviar")
            let partialResults = ValidatorV5Results(items: Array(results.items.prefix(2)), counts: [:], outdated: 0, readNotice: nil)
            fake.stored = partialResults; fake.outcome = .cancelled
            await c.requestEstimate(ids: ids, eligible: eligible, budget: 1)
            await c.confirm(authorized: true)
            require(c.phase == .cancelled && c.partial && c.results?.items.count == 2, "cancelamento durante a execução guarda o parcial")
            c.cancelRunning()
            require(fake.cancelCalls == 0, "cancelar sem execução em andamento não faz nada")
        }

        // Falhas recuperáveis, com chave redigida, e resultados parciais mantidos.
        do {
            struct Boom: LocalizedError { let text: String; var errorDescription: String? { text } }
            let boom = Boom(text: "Falha ao falar com a API (Bearer \(sentinel)).")
            let fake = FakeBackend(results: results); fake.estimates = [estimate, estimate]
            fake.estimateError = boom
            let c = ValidatorV5Coordinator(backend: fake.backend(), secrets: { [sentinel] })
            await c.requestEstimate(ids: ids, eligible: eligible, budget: 1)
            require(c.phase == .failed && !(c.failure ?? "").contains(sentinel) && (c.failure ?? "").contains("[chave oculta]"), "erro da estimativa sem chave")
            fake.estimateError = nil
            await c.requestEstimate(ids: ids, eligible: eligible, budget: 1)
            require(c.phase == .awaitingAuthorization, "depois de uma falha, dá para tentar de novo")
            fake.outcome = .failed(ValidatorV5Failure(code: "chave_ausente", message: "Chave \(sentinel) recusada."))
            await c.confirm(authorized: true)
            require(c.phase == .failed && c.partial && c.results != nil && !(c.failure ?? "").contains(sentinel), "falha na execução: parcial guardado e chave redigida")
            let fake2 = FakeBackend(results: results); fake2.estimates = [estimate, estimate]; fake2.runError = boom
            let c2 = ValidatorV5Coordinator(backend: fake2.backend(), secrets: { [sentinel] })
            await c2.requestEstimate(ids: ids, eligible: eligible, budget: 1)
            await c2.confirm(authorized: true)
            require(c2.phase == .failed && !(c2.failure ?? "").contains(sentinel), "exceção na execução: chave redigida")
        }

        // Invalidação por texto ou decisão; a decisão humana nunca é tocada.
        do {
            var decisions: [String: ReviewDecision] = [:]
            for item in results.items { decisions[item.id] = ReviewDecision(rawValue: item.previousDecision ?? "") ?? .pending }
            let item = results.items[0]
            require(ValidatorV5Wording.staleness(item, decisions: decisions) == nil, "resultado válido não tem desatualização")
            var live = decisions
            live[item.id] = live[item.id] == .style ? .error : .style
            require(ValidatorV5Wording.staleness(item, decisions: live) == .decision, "decisão mudou: resultado desatualizado")
            var edited = fixtures["results"] as! [String: Any]
            var items = edited["itens"] as! [[String: Any]]
            items[0]["situacao"] = "desatualizada_conteudo"; items[0]["vale_para_o_texto_e_decisao_atuais"] = false
            edited["itens"] = items
            let stale = try JSONDecoder().decode(ValidatorV5Results.self, from: JSONSerialization.data(withJSONObject: edited))
            require(ValidatorV5Wording.staleness(stale.items[0], decisions: decisions) == .text, "texto mudou: resultado desatualizado")
            require(stale.current(for: decisions).count == 4, "itens desatualizados saem de vigência")
            require(decisions == decisions.mapValues { $0 }, "decisões intactas")
        }
    }

    @MainActor
    static func wording(fixtures: [String: Any]) {
        let estimate = try! JSONDecoder().decode(ValidatorV5Estimate.self,
                                                 from: JSONSerialization.data(withJSONObject: fixtures["estimate"]!))
        let lines = ValidatorV5Wording.estimateLines(estimate, budget: 1.0).joined(separator: "\n")
        for needle in ["OpenAI", "gpt-6.1-sol", "teto autorizado: US$ 1.00", "Segunda rodada de contexto: não autorizada",
                       "verificável", "pior caso"] {
            require(lines.contains(needle), "linhas da estimativa mencionam: \(needle)")
        }
        require(!lines.contains("sk-") && !lines.contains("/Users/"), "estimativa sem segredos nem caminhos")
        var excluded = fixtures["estimate"] as! [String: Any]
        excluded["excluidos"] = [["id": "a", "motivo": "versao_do_manuscrito_diferente"]]
        excluded["a_enviar"] = [Any]()
        excluded["fits"] = true
        let none = try! JSONDecoder().decode(ValidatorV5Estimate.self, from: JSONSerialization.data(withJSONObject: excluded))
        let text = ValidatorV5Wording.estimateLines(none, budget: 1.0).joined(separator: "\n")
        require(text.contains("versão exata do relatório") && text.contains("Nada será enviado e não há custo"), "versão incompatível e nada a enviar")
        for kind in [ValidatorV5Wording.Kind.held, .contested, .review, .inadequate, .inconclusive, .unknown] {
            let title = kind.title.lowercased()
            require(!title.contains("erro confirmado") && !title.contains("é um erro"), "rótulo não chama o resultado da IA de erro: \(kind)")
        }
        // Pré-visualização: só dados locais, trecho marcado e contexto do relatório.
        let findingJSON = """
        {"id": "f1", "category": "Crase", "priority": "Verificar", "paragraph": 7, "chapter": "Capítulo Um",
         "text": "Ela foi a feira.", "start": 8, "end": 15, "reason": "Falta crase.", "source": "regra", "layer": null,
         "rule": "crase", "confidence": "média", "related": null,
         "context": [{"paragraph": 6, "chapter": "Capítulo Um", "text": "Antes disso.", "start": 0, "end": 12, "document": "d"},
                     {"paragraph": 7, "chapter": "Capítulo Um", "text": "Ela foi a feira.", "start": 8, "end": 15, "document": "d"}],
         "module": "linguistic", "severity": "probable_error"}
        """
        let finding = try! JSONDecoder().decode(Finding.self, from: Data(findingJSON.utf8))
        var one = fixtures["estimate"] as! [String: Any]
        one["a_enviar"] = [["id": "f1", "paragrafo": 7, "categoria": "Crase"]]
        let est = try! JSONDecoder().decode(ValidatorV5Estimate.self, from: JSONSerialization.data(withJSONObject: one))
        let entries = ValidatorV5Preview.entries(for: est, findings: [finding], decisions: ["f1": .style])
        require(entries.count == 1 && entries[0].marked == "Ela foi ⟦a feira⟧." && entries[0].decision == "Estilo do autor"
                && entries[0].context == ["§ 6: Antes disso."] && entries[0].detectorHypothesis == "Falta crase.", "pré-visualização do envio")
        require(!entries.map { $0.marked + $0.heading + $0.detectorHypothesis }.joined().contains("sk-"), "pré-visualização sem segredos")
    }
}
