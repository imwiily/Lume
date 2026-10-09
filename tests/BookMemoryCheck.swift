import Foundation

/// Confere a herança de decisões entre análises do mesmo livro (pelo nome do arquivo).
///
///     swiftc app/Lume/Models.swift tests/BookMemoryCheck.swift -o build/livro-swift
///     build/livro-swift
@main
struct BookMemoryCheck {
    static func require(_ condition: Bool, _ message: String) throws {
        if !condition { throw FonteError.message(message) }
    }

    struct Alert {
        var id: String
        var paragraph: Int
        var text: String
        var start: Int
        var end: Int
        var category = "Ortografia"
        var rule: String? = "ortografia"
        var related = "null"
    }

    static func report(_ sha: Character, document: String = "Livro.pages", _ alerts: [Alert]) throws -> EditorialReport {
        let findings = try alerts.map { alert -> String in
            let text = String(data: try JSONEncoder().encode(alert.text), encoding: .utf8)!
            let rule = alert.rule.map { "\"\($0)\"" } ?? "null"
            return """
            {"id": "\(alert.id)", "category": "\(alert.category)", "priority": "Verificar", "paragraph": \(alert.paragraph),
             "chapter": "Capítulo \(alert.paragraph)", "text": \(text), "start": \(alert.start), "end": \(alert.end),
             "reason": "Motivo.", "source": "regra", "layer": null, "rule": \(rule), "confidence": null,
             "related": \(alert.related), "context": null}
            """
        }
        let json = """
        {"schema_version": 1, "document": "\(document)", "sha256": "\(String(repeating: sha, count: 64))",
         "metadata": {"tempo": "passado", "paragrafos": 9, "versao_fonte": "9.9.9", "languagetool": false},
         "warnings": [], "findings": [\(findings.joined(separator: ","))]}
        """
        let decoded = try JSONDecoder().decode(EditorialReport.self, from: Data(json.utf8))
        try decoded.validate()
        return decoded
    }

    static let a = Alert(id: "a1", paragraph: 1, text: "🌿 Cafe\u{301} estava frio.", start: 2, end: 7)
    static let b = Alert(id: "b1", paragraph: 2, text: "Ela sorriu devagr.", start: 11, end: 17)
    static let c = Alert(id: "c1", paragraph: 3, text: "Choveu a noite intera.", start: 15, end: 21, category: "Repetição", rule: nil)

    static func main() throws {
        let first = try report("a", [a, b, c])
        let decided: [String: ReviewDecision] = ["a1": .falsePositive, "b1": .error, "c1": .style]
        let memory = BookMemory(report: first, decisions: decided)

        // Mesmo texto, arquivo salvo de novo (outro SHA): tudo volta.
        let resaved = try report("b", [a, b, c])
        try require(memory.inherited(for: resaved) == decided, "Mesmo texto com outro SHA deveria herdar todas as decisões.")

        // Parágrafo 2 editado pelo autor: o alerta dele fica pendente; os outros voltam.
        var edited = b; edited.id = "b2"; edited.text = "Ela sorriu bem devagr."; edited.start = 15; edited.end = 21
        let afterEdit = memory.inherited(for: try report("c", [a, edited, c]))
        try require(afterEdit == ["a1": .falsePositive, "c1": .style], "Alerta de parágrafo editado não pode herdar decisão: \(afterEdit)")

        // Parágrafo inserido antes: números e IDs mudam, conteúdo não.
        var shiftedB = b; shiftedB.id = "b3"; shiftedB.paragraph = 5
        var shiftedC = c; shiftedC.id = "c3"; shiftedC.paragraph = 6
        let afterInsert = memory.inherited(for: try report("d", [a, shiftedB, shiftedC]))
        try require(afterInsert == ["a1": .falsePositive, "b3": .error, "c3": .style], "Inserir parágrafo não deveria zerar decisões: \(afterInsert)")

        // Mesmo trecho com outra regra, ou evidência relacionada diferente: não herda.
        var otherRule = a; otherRule.id = "a4"; otherRule.rule = "acentuacao"
        var related = c; related.id = "c4"
        related.related = #"[{"paragraph": 1, "chapter": "Um", "text": "Outro texto.", "start": 0, "end": 5, "document": "atual"}]"#
        try require(memory.inherited(for: try report("e", [otherRule, related])).isEmpty, "Regra ou evidência diferente não pode herdar.")

        // Pendentes não são herdados; decisões desconhecidas são ignoradas.
        let partial = BookMemory(report: first, decisions: ["a1": .pending, "b1": .accepted])
        try require(partial.inherited(for: resaved) == ["b1": .accepted], "Só decisões diferentes de Pendente devem ser herdadas.")

        // Parágrafos idênticos com o mesmo alerta: herda na ordem só se a quantidade for a mesma.
        var twin1 = b; twin1.id = "t1"; twin1.paragraph = 7
        var twin2 = b; twin2.id = "t2"; twin2.paragraph = 8
        let twins = BookMemory(report: try report("f", [twin1, twin2]), decisions: ["t1": .error, "t2": .intentional])
        var moved1 = twin1; moved1.id = "m1"; moved1.paragraph = 9
        var moved2 = twin2; moved2.id = "m2"; moved2.paragraph = 10
        try require(twins.inherited(for: try report("1", [moved1, moved2])) == ["m1": .error, "m2": .intentional],
                    "Repetições na mesma quantidade devem herdar na ordem.")
        try require(twins.inherited(for: try report("2", [moved1])).isEmpty,
                    "Repetição com quantidade diferente é ambígua e não pode herdar.")

        // Nome do livro: sem extensão, sem diferenciar maiúsculas e composição Unicode.
        try require(BookMemory.bookName("Livro Azul.docx") == BookMemory.bookName("livro azul.pages"), "Extensão e maiúsculas não mudam o livro.")
        try require(BookMemory.bookName("Cafe\u{301}.pages") == BookMemory.bookName("Café.pages"), "Acento composto e decomposto são o mesmo nome.")
        try require(BookMemory.bookName("Livro Azul.pages") != BookMemory.bookName("Livro Azul 2.pages"), "Nomes diferentes são livros diferentes.")
        try require(memory.belongs(to: try report("3", document: "LIVRO.docx", [a])), "Mesmo nome deveria pertencer ao livro.")
        try require(!memory.belongs(to: try report("4", document: "Outro.pages", [a])), "Outro nome não pertence ao livro.")
        let fileName = BookMemory.fileName("Livro/Azul: 1?.pages")
        try require(!fileName.contains("/") && !fileName.contains(":") && fileName.hasSuffix(".json"), "Nome de arquivo inseguro: \(fileName)")

        // JSON: ida e volta; versão desconhecida é recusada.
        let data = try memory.encoded()
        let decoded = try BookMemory.decode(data)
        try require(decoded.inherited(for: resaved) == decided, "O livro gravado deveria herdar o mesmo que o original.")
        let future = String(decoding: data, as: UTF8.self).replacingOccurrences(of: "\"schema_version\" : 1", with: "\"schema_version\" : 2")
        try require((try? BookMemory.decode(Data(future.utf8))) == nil, "Versão desconhecida do livro deveria ser recusada.")

        // Estabilização de 07/10/2026: alertas que passaram a trazer `rule` (tempo verbal, estrutura…)
        // herdam da memória gravada antes, quando a regra ainda vinha vazia. Só esses: outra regra no
        // mesmo trecho não herda pela chave antiga.
        let tense = Alert(id: "t1", paragraph: 4, text: "Ela abre a porta e saiu.", start: 4, end: 8,
                          category: "Tempo verbal", rule: nil)
        let oldMemory = BookMemory(report: try report("d", [tense]), decisions: ["t1": .intentional])
        var tenseNow = tense; tenseNow.rule = "tempo_verbal"
        try require(oldMemory.inherited(for: try report("e", [tenseNow])) == ["t1": .intentional],
                    "Memória antiga deveria valer para o alerta que só ganhou a regra.")
        var spelling = tense; spelling.rule = "ortografia"
        try require(oldMemory.inherited(for: try report("f", [spelling])).isEmpty,
                    "Uma regra que já existia não pode herdar pela chave sem regra.")
        try require(BookMemory(report: try report("1", [tenseNow]), decisions: ["t1": .error])
                        .inherited(for: try report("2", [tenseNow])) == ["t1": .error],
                    "Memória nova continua valendo pela chave com regra.")

        // Configuração salva antes de existir ‘residuo_edicao’: herda o valor de ‘estrutura’.
        func settings(_ rules: [String: Bool]) throws -> SearchSettings {
            var all = Dictionary(uniqueKeysWithValues: SearchRule.all.map { ($0.id, true) })
            all.removeValue(forKey: "residuo_edicao")
            for (key, value) in rules { all[key] = value }
            var saved = SearchSettings()
            saved.rules = all
            return try SearchSettings.decode(try saved.encoded())
        }
        try require(try settings(["estrutura": false]).rules["residuo_edicao"] == false,
                    "Sem a chave nova, o resíduo de edição deve seguir ‘estrutura’ desligada.")
        try require(try settings([:]).rules["residuo_edicao"] == true, "Com ‘estrutura’ ligada, o resíduo fica ligado.")
        try require(try settings(["estrutura": false, "residuo_edicao": true]).rules["residuo_edicao"] == true,
                    "Valor salvo da chave nova prevalece.")

        print("Decisões por livro validadas: mesmo texto, edição, inserção, repetições, pendentes, nome, JSON, chave antiga sem regra e herança de residuo_edicao.")
    }
}
