import Foundation

/// Confere as ferramentas da mesa de leitura: cópia do contexto e do parágrafo marcado, decisões
/// levadas na reanálise e o plano de limpeza de resíduos.
///
///     swiftc app/Lume/Models.swift tests/DeskToolsCheck.swift -o build/mesa-swift
///     build/mesa-swift
@main
struct DeskToolsCheck {
    static func require(_ condition: Bool, _ message: String) throws {
        if !condition { throw FonteError.message(message) }
    }

    static func json(_ value: String) throws -> String { String(data: try JSONEncoder().encode(value), encoding: .utf8)! }

    static func finding(id: String, paragraph: Int, text: String, start: Int, end: Int,
                        context: [(Int, String, String)] = []) throws -> String {
        let items = try context.map { number, chapter, body in
            let length = body.unicodeScalars.count
            return """
            {"paragraph": \(number), "chapter": \(try json(chapter)), "text": \(try json(body)), "start": 0, "end": \(length), "document": "atual"}
            """
        }
        return """
        {"id": "\(id)", "category": "Ortografia", "priority": "Verificar", "paragraph": \(paragraph),
         "chapter": "Capítulo Um", "text": \(try json(text)), "start": \(start), "end": \(end),
         "reason": "A palavra parece grafada de outro modo.", "source": "regra", "layer": null, "rule": "ortografia",
         "confidence": null, "related": null, "context": [\(items.joined(separator: ","))]}
        """
    }

    static func report(_ sha: Character, document: String = "Livro.pages", _ findings: [String]) throws -> EditorialReport {
        let text = """
        {"schema_version": 1, "document": "\(document)", "sha256": "\(String(repeating: sha, count: 64))",
         "metadata": {"tempo": "passado", "paragrafos": 9, "versao_fonte": "9.9.9", "languagetool": false},
         "warnings": [], "findings": [\(findings.joined(separator: ","))]}
        """
        let decoded = try JSONDecoder().decode(EditorialReport.self, from: Data(text.utf8))
        try decoded.validate()
        return decoded
    }

    static func main() throws {
        try copies()
        try carried()
        try cleanup()
        try cleanupKeepsDecisionHistory()
        print("Mesa de leitura validada: cópias, decisões na reanálise, limpeza de resíduos e histórico de decisões.")
    }

    // MARK: Cópias

    static func copies() throws {
        let body = "🌿 O cafe\u{301} esfriou devagr na mesa."
        let start = body.unicodeScalars.count - " na mesa.".unicodeScalars.count - "devagr".unicodeScalars.count
        let context: [(Int, String, String)] = [
            (6, "Capítulo Um", "Depois da chuva, a rua secou."),
            (4, "Capítulo Um", "Capítulo Um"),           // título: fica só no cabeçalho
            (3, "Capítulo Um", "A porta rangeu."),
            (5, "Capítulo Um", "Duplicado com o alerta."),
            (5, "Capítulo Um", "Duplicado com o alerta."),
            (2, "Capítulo Dois", "Outro capítulo."),     // outro capítulo: fora da página
        ]
        let loaded = try report("a", [try finding(id: "x", paragraph: 5, text: body, start: start, end: start + 6, context: context)])
        let alert = loaded.findings[0]
        try require(alert.segments.marked == "devagr", "Trecho errado: \(alert.segments.marked)")
        try require(alert.pageParagraphs.map(\.number) == [3, 5, 6], "Ordem da página: \(alert.pageParagraphs.map(\.number))")
        try require(alert.pageParagraphs.first { $0.number == 5 }?.text == body, "O parágrafo do alerta vem do próprio alerta.")
        try require(alert.contextText == "Capítulo Um\n\nA porta rangeu.\n\n\(body)\n\nDepois da chuva, a rua secou.",
                    "Contexto copiado: \(alert.contextText)")
        try require(alert.markedParagraphText == "🌿 O cafe\u{301} esfriou *devagr* na mesa.\n\nPor que acendemos esta luz:\nA palavra parece grafada de outro modo.",
                    "Parágrafo marcado: \(alert.markedParagraphText)")

        // Sem contexto: só o título e o parágrafo do alerta.
        let alone = try report("b", [try finding(id: "y", paragraph: 1, text: "Fim.", start: 0, end: 3)]).findings[0]
        try require(alone.contextText == "Capítulo Um\n\nFim.", "Contexto sem vizinhos: \(alone.contextText)")
        try require(alone.markedParagraphText.hasPrefix("*Fim*."), "Destaque no início: \(alone.markedParagraphText)")
    }

    // MARK: Reanálise

    static func carried() throws {
        let a = try finding(id: "a", paragraph: 1, text: "Ela sorriu devagr.", start: 11, end: 17)
        let b = try finding(id: "b", paragraph: 2, text: "Choveu a noite intera.", start: 15, end: 21)
        let c = try finding(id: "c", paragraph: 3, text: "Um terceiro trexo.", start: 12, end: 17)
        let first = try report("a", [a, b, c])
        let carry = CarriedDecisions(report: first, decisions: ["a": .falsePositive, "b": .error, "c": .pending], selectedID: "b")
        try require(carry.selectedID == "b" && carry.byID.keys.sorted() == ["a", "b"], "Pendentes não são levados.")

        // Mesmo texto, mesmos IDs: tudo volta; o que o cache já trouxe não é sobrescrito.
        let same = try report("a", [a, b, c])
        try require(carry.merged(into: [:], for: same) == ["a": .falsePositive, "b": .error], "Mesmos IDs devem manter as decisões.")
        try require(carry.merged(into: ["a": .style], for: same) == ["a": .style, "b": .error], "Decisão restaurada não pode ser trocada.")
        try require(carry.merged(into: ["a": .pending], for: same)["a"] == .falsePositive, "Pendente restaurado recebe a decisão anterior.")

        // Parágrafo inserido antes: o ID muda, o conteúdo não; alerta novo fica pendente.
        let shifted = try finding(id: "b2", paragraph: 4, text: "Choveu a noite intera.", start: 15, end: 21)
        let fresh = try finding(id: "n", paragraph: 5, text: "Outro alerta novo.", start: 0, end: 5)
        let moved = try report("b", [a, shifted, fresh])
        try require(carry.merged(into: [:], for: moved) == ["a": .falsePositive, "b2": .error], "Herança pelo conteúdo: \(carry.merged(into: [:], for: moved))")

        // Outro livro não recebe as decisões.
        try require(!carry.belongs(to: try report("c", document: "Outro.pages", [a])), "Outro livro não pode herdar.")
        try require(carry.belongs(to: try report("c", document: "livro.docx", [a])), "Mesmo livro em outro formato herda.")
    }

    // MARK: Limpeza

    static func cleanup() throws {
        let manager = FileManager.default
        let root = manager.temporaryDirectory.resolvingSymlinksInPath()
            .appendingPathComponent("lume-mesa-" + UUID().uuidString, isDirectory: true)
        defer { try? manager.removeItem(at: root) }
        let support = root.appendingPathComponent("FONTE", isDirectory: true)
        let temporary = root.appendingPathComponent("tmp", isDirectory: true)
        func write(_ path: String, _ text: String = "x", in base: URL? = nil, age: TimeInterval = 0) throws -> URL {
            let url = (base ?? support).appendingPathComponent(path)
            try manager.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
            try Data(text.utf8).write(to: url)
            try manager.setAttributes([.modificationDate: Date().addingTimeInterval(-age)], ofItemAtPath: url.path)
            return url
        }
        func header(_ document: String) -> String { #"{"document": "\#(document)", "findings": []}"# }

        _ = try write("Relatorios/livro-velho/relatorio.json", header("Livro.pages"), age: 300)
        _ = try write("Relatorios/livro-meio/relatorio.json", header("livro.docx"), age: 200)
        _ = try write("Relatorios/livro-meio/falsos-positivos.json", "{}")
        _ = try write("Relatorios/livro-novo/relatorio.json", header("Livro.pages"), age: 100)
        let open = try write("Relatorios/aberto/relatorio.json", header("Livro.pages"), age: 900)
        _ = try write("Relatorios/outro/relatorio.json", header("Outro.pages"), age: 900)
        _ = try write("Relatorios/falhou/parcial.txt")
        let currentLog = try write("Registros/atual.txt")
        _ = try write("Registros/velho.txt")
        _ = try write("Configuracoes/job.json")
        _ = try write("Decisoes/aaaa.json")
        _ = try write("Livros/livro.json")
        _ = try write("Copias/aaaa/Livro.pages")
        _ = try write("Edicoes/aaaa.json")
        _ = try write("Coerencia/Livro/cache.json")
        _ = try write("lume-edicao-1/antes.pages", in: temporary)
        _ = try write("outro-app/arquivo", in: temporary)

        let plan = StorageCleanup.plan(support: support, temporary: temporary,
                                       keepReport: open.deletingLastPathComponent(), keepLog: currentLog)
        let removed = Set(plan.removals.map { $0.resolvingSymlinksInPath().path.replacingOccurrences(of: root.path + "/", with: "") })
        let expected: Set<String> = ["FONTE/Relatorios/livro-velho", "FONTE/Relatorios/livro-meio/relatorio.json",
                                     "FONTE/Relatorios/falhou", "FONTE/Registros/velho.txt",
                                     "FONTE/Configuracoes/job.json", "tmp/lume-edicao-1"]
        try require(removed == expected, "Plano de limpeza: \(removed.sorted())")
        try require(plan.reports == 3 && plan.logs == 1 && plan.configurations == 1 && plan.temporaries == 1,
                    "Contagens: \(plan.summary)")
        try require(plan.bytes > 0 && !plan.summary.isEmpty, "Plano sem tamanho ou resumo.")

        let result = plan.apply()
        try require(result.failures == 0 && result.freed > 0, "Limpeza falhou: \(result)")
        for kept in ["FONTE/Relatorios/livro-novo/relatorio.json", "FONTE/Relatorios/aberto/relatorio.json",
                     "FONTE/Relatorios/outro/relatorio.json", "FONTE/Relatorios/livro-meio/falsos-positivos.json",
                     "FONTE/Registros/atual.txt", "FONTE/Decisoes/aaaa.json", "FONTE/Livros/livro.json",
                     "FONTE/Copias/aaaa/Livro.pages", "FONTE/Edicoes/aaaa.json", "FONTE/Coerencia/Livro/cache.json",
                     "tmp/outro-app/arquivo"] {
            try require(manager.fileExists(atPath: root.appendingPathComponent(kept).path), "Não deveria apagar \(kept).")
        }
        for gone in expected {
            try require(!manager.fileExists(atPath: root.appendingPathComponent(gone).path), "Deveria apagar \(gone).")
        }
        let again = StorageCleanup.plan(support: support, temporary: temporary,
                                        keepReport: open.deletingLastPathComponent(), keepLog: currentLog)
        try require(again.isEmpty, "Depois da limpeza não sobra resíduo: \(again.removals)")
    }

    /// Relatório antigo com decisão que o mais recente do livro não tem fica (medição); os demais saem.
    static func cleanupKeepsDecisionHistory() throws {
        let manager = FileManager.default
        let root = manager.temporaryDirectory.resolvingSymlinksInPath()
            .appendingPathComponent("lume-historico-" + UUID().uuidString, isDirectory: true)
        defer { try? manager.removeItem(at: root) }
        let support = root.appendingPathComponent("FONTE", isDirectory: true)
        func write(_ path: String, _ text: String, age: TimeInterval = 0) throws {
            let url = support.appendingPathComponent(path)
            try manager.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
            try Data(text.utf8).write(to: url)
            try manager.setAttributes([.modificationDate: Date().addingTimeInterval(-age)], ofItemAtPath: url.path)
        }
        func report(_ job: String, sha: String, _ ids: [String], age: TimeInterval) throws {
            let findings = ids.map { #"{"id": "\#($0)"}"# }.joined(separator: ", ")
            try write("Relatorios/\(job)/relatorio.json",
                      #"{"document": "Livro.pages", "sha256": "\#(sha)", "findings": [\#(findings)]}"#, age: age)
        }
        func decisions(_ sha: String, _ values: [String: String]) throws {
            let body = values.map { #""\#($0.key)": "\#($0.value)""# }.joined(separator: ", ")
            try write("Decisoes/\(sha).json",
                      #"{"schema_version": 1, "sha256": "\#(sha)", "document": "Livro.pages", "decisions": {\#(body)}}"#)
        }
        // Mais recente (texto editado, outro SHA): "comum" decidido; "sem-marca" ainda aparece, sem decisão.
        try report("novo", sha: "s3", ["comum", "sem-marca"], age: 100)
        try decisions("s3", ["comum": "Erro confirmado"])
        // (1) alerta decidido sumiu do mais recente ("retirado") ou não tem decisão no arquivo dele: fica.
        try report("com-historico", sha: "s2", ["comum", "retirado", "sem-marca"], age: 200)
        try decisions("s2", ["comum": "Erro confirmado", "retirado": "Estilo do autor", "sem-marca": "Falso positivo"])
        // (2) decisões todas representadas (uma pendente; as outras num relatório que já fica): sai.
        try report("representado", sha: "s1", ["comum", "pendente", "retirado"], age: 300)
        try decisions("s1", ["comum": "Erro confirmado", "pendente": "Pendente", "retirado": "Estilo do autor"])
        // (1b) só "sem-marca" decidido, presente no mais recente sem decisão: fica pela mesma razão,
        // salvo quando um relatório mais novo já mantido o carrega (aqui, "com-historico").
        try report("so-sem-marca", sha: "s4", ["sem-marca"], age: 250)
        try decisions("s4", ["sem-marca": "Falso positivo"])
        // (3) sem decisões: sai, como antes.
        try report("sem-decisoes", sha: "s0", ["antigo"], age: 400)

        let plan = StorageCleanup.plan(support: support, temporary: root.appendingPathComponent("tmp"),
                                       keepReport: nil, keepLog: nil)
        let removed = Set(plan.removals.map(\.lastPathComponent))
        try require(removed == ["representado", "so-sem-marca", "sem-decisoes"], "Plano com histórico: \(removed.sorted())")
        try require(plan.preserved == 1 && plan.reports == 3, "Contagens: \(plan.preserved) mantidos, \(plan.reports) apagados.")
        _ = plan.apply()
        for kept in ["Relatorios/novo/relatorio.json", "Relatorios/com-historico/relatorio.json",
                     "Decisoes/s1.json", "Decisoes/s2.json", "Decisoes/s3.json"] {
            try require(manager.fileExists(atPath: support.appendingPathComponent(kept).path), "Não deveria apagar \(kept).")
        }
        // Uma segunda limpeza não apaga o relatório mantido: o resultado é estável.
        let again = StorageCleanup.plan(support: support, temporary: root.appendingPathComponent("tmp"),
                                        keepReport: nil, keepLog: nil)
        try require(again.isEmpty && again.preserved == 1, "Segunda limpeza: \(again.removals)")
    }
}
