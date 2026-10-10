import Foundation

/// Confere o cálculo das correções (sempre) e, com um documento do Pages como argumento,
/// a gravação real pelo Pages numa cópia descartável.
///
///     swiftc app/Lume/Models.swift app/Lume/ManuscriptEditor.swift tests/EditCheck.swift -o build/edicao-swift
///     build/edicao-swift [copia-descartavel.pages paragrafo inicio fim "texto novo"]
@main
struct EditCheck {
    static func require(_ condition: Bool, _ message: String) throws {
        if !condition { throw FonteError.message(message) }
    }

    static func refused(_ body: () throws -> EditPlan) -> Bool {
        do { _ = try body(); return false } catch { return true }
    }

    static func edit(_ start: Int, _ end: Int, _ before: String, _ after: String) -> AppliedEdit {
        AppliedEdit(finding: "x", paragraph: 1, start: start, end: end, before: before, after: after, date: Date())
    }

    static func main() async throws {
        // Posições em pontos de código: o emoji conta um, o acento combinado conta à parte.
        let text = "🌿 Cafe\u{0301} chegou a noite, e e ficou."
        let scalars = Array(text.unicodeScalars)
        func index(_ word: String) -> Int {
            let target = Array(word.unicodeScalars)
            return (0...(scalars.count - target.count)).first { Array(scalars[$0..<($0 + target.count)]) == target }!
        }
        let a = index("a noite")
        let first = try ManuscriptEditor.plan(text: text, start: a, end: a + 1, replacement: "à", edits: [])
        try require(first.first == a + 1 && first.last == a + 1 && first.replacement == "à", "Posição simples incorreta.")
        try require(first.resultText == text.replacingOccurrences(of: "a noite", with: "à noite"), "Resultado simples incorreto.")
        try require(first.currentText == text, "O texto atual sem correções deve ser o do relatório.")

        // Segunda correção no mesmo parágrafo, depois de uma que mudou o tamanho.
        let longer = edit(a, a + 1, "a", "durante a")
        let repeated = index("e e") + 2
        let second = try ManuscriptEditor.plan(text: text, start: repeated, end: repeated + 2, replacement: "", edits: [longer])
        try require(second.first == repeated + 1 + 8 && second.last == repeated + 2 + 8, "Deslocamento após correção anterior incorreto.")
        try require(second.resultText == "🌿 Cafe\u{0301} chegou durante a noite, e ficou.", "Remoção após correção anterior incorreta.")
        // Uma correção posterior no parágrafo não desloca um trecho anterior.
        let earlier = try ManuscriptEditor.plan(text: text, start: a, end: a + 1, replacement: "à",
                                                edits: [edit(repeated, repeated + 2, "e ", "")])
        try require(earlier.first == a + 1 && earlier.resultText == "🌿 Cafe\u{0301} chegou à noite, e ficou.", "Correção anterior deslocada.")

        // Inserção: o Pages recebe o caractere vizinho junto com o texto novo.
        let comma = index(" chegou")
        let insertion = try ManuscriptEditor.plan(text: text, start: comma, end: comma, replacement: ",", edits: [])
        try require(insertion.first == comma && insertion.last == comma && insertion.replacement == "\u{0301},", "Inserção incorreta.")
        let atStart = try ManuscriptEditor.plan(text: "chegou.", start: 0, end: 0, replacement: "Ela ", edits: [])
        try require(atStart.first == 1 && atStart.last == 1 && atStart.replacement == "Ela c" && atStart.resultText == "Ela chegou.",
                    "Inserção no início incorreta.")

        // Recusas: sobreposição, quebra de linha, texto igual, limites e parágrafo esvaziado.
        try require(refused { try ManuscriptEditor.plan(text: text, start: a, end: a + 7, replacement: "à noite", edits: [longer]) },
                    "Trecho já corrigido deveria ser recusado.")
        try require(refused { try ManuscriptEditor.plan(text: text, start: a, end: a + 1, replacement: "à\nb", edits: []) },
                    "Quebra de linha deveria ser recusada.")
        try require(refused { try ManuscriptEditor.plan(text: text, start: a, end: a + 1, replacement: "a", edits: []) },
                    "Correção igual ao trecho deveria ser recusada.")
        try require(refused { try ManuscriptEditor.plan(text: text, start: 5, end: 999, replacement: "x", edits: []) },
                    "Trecho fora do parágrafo deveria ser recusado.")
        try require(refused { try ManuscriptEditor.plan(text: "Fim.", start: 0, end: 4, replacement: "", edits: []) },
                    "Esvaziar o parágrafo deveria ser recusado.")
        try require(refused { try ManuscriptEditor.plan(text: text, start: a, end: a + 1,
                                                        replacement: String(repeating: "x", count: ManuscriptEditor.limit + 1), edits: []) },
                    "Correção longa demais deveria ser recusada.")
        try require(ManuscriptEditor.currentText(text, edits: [longer, edit(repeated, repeated + 2, "e ", "")])
                        == "🌿 Cafe\u{0301} chegou durante a noite, e ficou.", "Texto atual com duas correções incorreto.")

        // Edição do parágrafo inteiro: só a menor troca contínua vai ao Pages, em posições do relatório.
        let whole = try ManuscriptEditor.paragraphChange(text: text, edits: [],
                                                         newText: "🌿 Cafe\u{0301} chegou à noite, e e ficou.")
        try require(whole.start == a && whole.end == a + 1 && whole.before == "a" && whole.after == "à",
                    "Edição do parágrafo deveria reduzir-se à troca mínima.")
        let rewritten = try ManuscriptEditor.paragraphChange(text: text, edits: [],
                                                             newText: "🌿 Cafe\u{0301} chegou ao anoitecer e ficou.")
        let rewrittenPlan = try ManuscriptEditor.plan(text: text, start: rewritten.start, end: rewritten.end,
                                                      replacement: rewritten.after, edits: [])
        try require(rewrittenPlan.resultText == "🌿 Cafe\u{0301} chegou ao anoitecer e ficou.", "Reescrita do parágrafo incorreta.")
        // Depois de uma correção no parágrafo, a edição parte do texto atual e é traduzida para o relatório.
        let afterEdit = try ManuscriptEditor.paragraphChange(text: text, edits: [longer],
                                                             newText: "🌿 Cafe\u{0301} chegou durante a noite, e ficou.")
        try require(afterEdit.start == repeated && afterEdit.end == repeated + 2 && afterEdit.after == "",
                    "Edição do parágrafo após correção anterior mal traduzida.")
        let afterPlan = try ManuscriptEditor.plan(text: text, start: afterEdit.start, end: afterEdit.end,
                                                  replacement: afterEdit.after, edits: [longer])
        try require(afterPlan.resultText == "🌿 Cafe\u{0301} chegou durante a noite, e ficou.", "Resultado após correção anterior incorreto.")
        // Recusas: mexer numa correção já gravada e parágrafo sem mudança.
        try require((try? ManuscriptEditor.paragraphChange(text: text, edits: [longer],
                                                            newText: "🌿 Cafe\u{0301} chegou durante toda a noite, e e ficou.")) == nil,
                    "Edição sobre correção já gravada deveria ser recusada.")
        try require((try? ManuscriptEditor.paragraphChange(text: text, edits: [], newText: text)) == nil,
                    "Parágrafo sem mudança deveria ser recusado.")

        let log = EditLog(origem: String(repeating: "a", count: 64), atual: String(repeating: "b", count: 64),
                          documento: "Livro.pages", copia: "/tmp/Livro.pages", edits: [longer])
        let encoder = JSONEncoder(); encoder.dateEncodingStrategy = .iso8601
        let decoder = JSONDecoder(); decoder.dateDecodingStrategy = .iso8601
        let object = try JSONSerialization.jsonObject(with: encoder.encode(log)) as? [String: Any]
        try require(object?["schema_version"] as? Int == 1, "Chave JSON do histórico incompatível.")
        try require(try decoder.decode(EditLog.self, from: encoder.encode(log)).edits.first?.after == "durante a", "Histórico não é relido.")
        print("Cálculo das correções validado.")

        try await commitChecks()
        print("Fases da correção, falhas injetadas e reconciliação validadas.")

        guard CommandLine.arguments.count == 7 else { return }
        let document = URL(fileURLWithPath: CommandLine.arguments[1])
        let paragraph = Int(CommandLine.arguments[2])!, start = Int(CommandLine.arguments[3])!, end = Int(CommandLine.arguments[4])!
        let plan = try ManuscriptEditor.plan(text: CommandLine.arguments[6], start: start, end: end,
                                             replacement: CommandLine.arguments[5], edits: [])
        let before = try ManuscriptEditor.sha256(document)
        try await ManuscriptEditor.runPages(document: document, paragraph: paragraph, plan: plan)
        try require(try ManuscriptEditor.sha256(document) != before, "O Pages não gravou a correção.")
        print(plan.resultText)
    }

    // MARK: Fases da correção com falhas injetadas (nenhum Pages, nenhum manuscrito real)

    struct Injected: Error, LocalizedError { let text: String; var errorDescription: String? { text } }

    static func commitChecks() async throws {
        let manager = FileManager.default
        let root = manager.temporaryDirectory.appendingPathComponent("lume-editcheck-" + UUID().uuidString, isDirectory: true)
        try manager.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? manager.removeItem(at: root) }
        let original = Data("manuscrito original".utf8), corrected = Data("manuscrito corrigido".utf8)
        func sha(_ data: Data) -> String { try! ManuscriptEditor.sha256(write(data)) }
        func write(_ data: Data) throws -> URL {
            let url = root.appendingPathComponent(UUID().uuidString); try data.write(to: url); return url
        }
        let expected = sha(original)
        var calls: [String] = []
        struct Scenario {
            var writeFails = false, writeChangesDocument = false, recordFails = false, persistFails = false, restoreFails = false
        }
        func run(_ scenario: Scenario, rescue: URL? = nil) async -> (Result<ManuscriptEditor.Commit, Error>, document: URL, previous: URL, calls: [String]) {
            calls = []
            let document = try! write(original), previous = try! write(original)
            let outcome: Result<ManuscriptEditor.Commit, Error>
            do {
                outcome = .success(try await ManuscriptEditor.commit(
                    document: document, previous: previous, expectedSHA: expected, backup: "/copia/original.pages",
                    write: {
                        calls.append("write")
                        if scenario.writeChangesDocument || !scenario.writeFails { try corrected.write(to: document) }
                        if scenario.writeFails { throw Injected(text: "Pages falhou") }
                    },
                    record: { calls.append("record"); if scenario.recordFails { throw Injected(text: "disco cheio no histórico") } },
                    persist: { calls.append("persist"); if scenario.persistFails { throw Injected(text: "disco cheio nas decisões") } },
                    restore: { target, source in
                        calls.append("restore")
                        if scenario.restoreFails { throw Injected(text: "sem permissão") }
                        _ = try FileManager.default.replaceItemAt(target, withItemAt: source)
                    },
                    preserve: { ManuscriptEditor.preserve($0, in: rescue ?? root.appendingPathComponent("recuperacao", isDirectory: true)) }))
            } catch { outcome = .failure(error) }
            return (outcome, document, previous, calls)
        }
        func failure(_ outcome: Result<ManuscriptEditor.Commit, Error>) -> ManuscriptEditor.EditFailure? {
            if case .failure(let error) = outcome { return error as? ManuscriptEditor.EditFailure }
            return nil
        }

        // 1. Tudo certo: documento corrigido, histórico e decisões gravados, sem restauração.
        var r = await run(Scenario())
        try require((try? r.0.get()) == .recorded && r.calls == ["write", "record", "persist"], "Caminho feliz incorreto.")
        try require(try Data(contentsOf: r.document) == corrected, "Documento deveria ficar corrigido.")

        // 2. P2: falha só nas decisões depois do histórico: o manuscrito NÃO volta; só aviso.
        r = await run(Scenario(persistFails: true))
        try require((try? r.0.get()) == .decisionsUnsaved("disco cheio nas decisões"), "Falha de decisões deveria ser só aviso.")
        try require(!r.calls.contains("restore") && r.calls == ["write", "record", "persist"], "Não pode restaurar por falha de decisões.")
        try require(try Data(contentsOf: r.document) == corrected, "O documento corrigido tem de permanecer.")

        // 3. Falha ao gravar o histórico: o arquivo anterior é restaurado e as decisões não são tocadas.
        r = await run(Scenario(recordFails: true))
        try require(failure(r.0)?.recovery == .restored && r.calls == ["write", "record", "restore"], "Falha do histórico deveria restaurar.")
        try require(try Data(contentsOf: r.document) == original, "O documento deveria voltar ao original.")

        // 4. Falha do Pages sem mudar o arquivo: nada a restaurar.
        r = await run(Scenario(writeFails: true))
        try require(failure(r.0)?.recovery == .untouched && !r.calls.contains("restore"), "Arquivo intacto não pede restauração.")

        // 5. Falha da conferência depois de o Pages salvar: restaura.
        r = await run(Scenario(writeFails: true, writeChangesDocument: true))
        try require(failure(r.0)?.recovery == .restored && r.calls == ["write", "restore"], "Arquivo alterado deveria ser restaurado.")
        try require(try Data(contentsOf: r.document) == original, "Restauração incorreta.")

        // 6. P3: a restauração falha; a cópia anterior é preservada, com caminho e permissão corretos.
        let rescue = root.appendingPathComponent("recuperacao-p3", isDirectory: true)
        r = await run(Scenario(recordFails: true, restoreFails: true), rescue: rescue)
        guard let broken = failure(r.0), case .restoreFailed(let kept) = broken.recovery else {
            throw FonteError.message("Falha de restauração deveria informar a cópia preservada.")
        }
        try require(try Data(contentsOf: URL(fileURLWithPath: kept)) == original, "A cópia preservada deve ser a anterior à correção.")
        try require(kept.hasPrefix(rescue.path) && !manager.fileExists(atPath: r.previous.path), "A cópia deve sair da pasta temporária.")
        let folderMode = (try manager.attributesOfItem(atPath: URL(fileURLWithPath: kept).deletingLastPathComponent().path)[.posixPermissions] as? NSNumber)?.intValue
        let fileMode = (try manager.attributesOfItem(atPath: kept)[.posixPermissions] as? NSNumber)?.intValue
        try require(folderMode == 0o700 && fileMode == 0o600, "A cópia preservada deve ser só do usuário.")
        let message = broken.localizedDescription
        try require(message.contains(kept) && message.contains("/copia/original.pages") && message.contains("disco cheio no histórico"),
                    "A mensagem deve trazer a causa e os dois caminhos.")
        try require(try Data(contentsOf: r.document) == corrected, "Sem restauração, o documento segue como está (copia preservada).")

        // 7. Se nem mover a cópia for possível, ela continua no lugar original (e a pasta de trabalho é mantida).
        let blocked = root.appendingPathComponent("arquivo-no-lugar-da-pasta"); try Data().write(to: blocked)
        r = await run(Scenario(recordFails: true, restoreFails: true), rescue: blocked)
        guard let stuck = failure(r.0), case .restoreFailed(let still) = stuck.recovery else {
            throw FonteError.message("Falha ao mover deveria manter a cópia no lugar.")
        }
        try require(still == r.previous.path && manager.fileExists(atPath: still), "A cópia deve continuar onde estava.")

        // 8. Reabertura: histórico gravado, decisão não salva → “Corrigido”; decisões já tomadas ficam.
        let edits = [edit(0, 1, "a", "à"), AppliedEdit(finding: "y", paragraph: 2, start: 0, end: 1, before: "a", after: "b", date: Date()),
                     AppliedEdit(finding: "ausente", paragraph: 3, start: 0, end: 1, before: "a", after: "b", date: Date())]
        let before: [String: ReviewDecision] = ["y": .accepted, "z": .falsePositive]
        let merged = ManuscriptEditor.reconcile(before, with: edits, ids: ["x", "y", "z"])
        try require(merged.decisions["x"] == .corrected && merged.changed == 1, "Correção sem decisão deveria virar Corrigido.")
        try require(merged.decisions["y"] == .accepted && merged.decisions["z"] == .falsePositive, "Decisões existentes devem ser preservadas.")
        try require(merged.decisions["ausente"] == nil, "Alerta fora do relatório não entra nas decisões.")
        let again = ManuscriptEditor.reconcile(merged.decisions, with: edits, ids: ["x", "y", "z"])
        try require(again.changed == 0 && again.decisions == merged.decisions, "A reconciliação deve ser idempotente.")
        let withError = ManuscriptEditor.reconcile(["x": .error], with: [edit(0, 1, "a", "à")], ids: ["x"])
        try require(withError.decisions["x"] == .corrected, "‘Erro confirmado’ corrigido no manuscrito vira Corrigido.")
    }
}
