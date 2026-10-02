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
}
