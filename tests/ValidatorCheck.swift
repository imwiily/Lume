import Foundation

/// Confere o que o app aceita do Validador de decisões: a linha `LUME_VALIDACAO` e o registro do
/// projeto. Só vale a avaliação de um alerta que continua no relatório e cuja decisão não mudou;
/// só `contestada` entra em “reconsiderar”; questão independente aparece à parte; inconclusivo e
/// não avaliado nunca viram contestação.
///
///     swiftc app/Lume/Models.swift tests/ValidatorCheck.swift -o build/validador-swift
///     build/validador-swift
@main
struct ValidatorCheck {
    static func require(_ condition: Bool, _ message: String) throws {
        if !condition { throw FonteError.message(message) }
    }

    static func finding(_ id: String) -> String {
        """
        {"id": "\(id)", "category": "Crase", "priority": "Verificar", "paragraph": 1, "chapter": "Capítulo Um",
         "text": "Ela foi a feira.", "start": 8, "end": 15, "reason": "Explicação.", "source": "regra", "layer": null,
         "rule": "crase", "confidence": "média", "related": null, "context": null,
         "module": "linguistic", "severity": "probable_error"}
        """
    }

    static func item(_ id: String, _ decisao: String, _ estado: String, issue: Bool = false) -> String {
        let questao = issue ? "{\"trecho\": \"a feira\", \"explicacao\": \"Falta crase.\"}" : "null"
        return "\"\(id)\": {\"id\": \"\(id)\", \"decisao\": \"\(decisao)\", \"estado\": \"\(estado)\", \"chave\": \"x\", "
            + "\"classe\": \"A\", \"modelo_final\": \"claude-sonnet-5-5\", \"explicacao\": \"Porque sim.\", "
            + "\"evidencias\": [\"foi a feira\"], \"recomendacao\": \"Reconsiderar.\", \"questao_independente\": \(questao), "
            + "\"triagem\": {\"veredito\": \"contestar\", \"motivo\": \"m\", \"termos_contexto\": []}}"
    }

    static func main() throws {
        let ids = ["a1", "a2", "a3", "a4", "a5", "a6"]
        let json = """
        {"schema_version": 1, "document": "livro.pages", "sha256": "\(String(repeating: "a", count: 64))",
         "metadata": {"tempo": "passado", "paragrafos": 1, "versao_fonte": "1.8.1", "languagetool": false, "diagnostico": []},
         "warnings": [], "findings": [\(ids.map(finding).joined(separator: ","))]}
        """
        let report = try JSONDecoder().decode(EditorialReport.self, from: Data(json.utf8))
        let decisions: [String: ReviewDecision] = ["a1": .style, "a2": .falsePositive, "a3": .intentional,
                                                   "a4": .accepted, "a5": .error]
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("lume-validador-" + UUID().uuidString)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }
        let file = dir.appendingPathComponent("validacao-decisoes.json")
        let body = [item("a1", "Estilo do autor", "contestada"),
                    item("a2", "Falso positivo", "inconclusiva"),
                    item("a3", "Intencional", "apontamento_inadequado", issue: true),
                    item("a4", "Erro confirmado", "contestada"),      // a decisão mudou depois da avaliação
                    item("a5", "Erro confirmado", "nao_avaliada"),
                    item("zz", "Estilo do autor", "contestada")]      // alerta que não está mais no relatório
        try Data("{\"versao\": 1, \"prompt\": 1, \"meta\": {}, \"itens\": {\(body.joined(separator: ","))}}".utf8).write(to: file)
        let line = """
        {"arquivo": "\(file.path)", "resumo": {"modo": "hibrido", "elegiveis": 5, "avaliadas": 3, "nao_avaliadas": 2,
         "contestadas": 1, "reaproveitadas": 0, "interrompida": true, "custo_usd": 0.0123, "modelos": {}}}
        """
        let result = try DecisionValidation.load(line: Data(line.utf8), report: report, decisions: decisions)
        try require(result.contested.map(\.id) == ["a1"], "Só a contestação de decisão ainda vigente deve aparecer: \(result.contested.map(\.id)).")
        try require(result.independent.map(\.id) == ["a3"], "A questão independente deve aparecer à parte.")
        try require(result.unevaluated == 2 && result.summary?.interrompida == true, "O resumo parcial deve ser preservado.")
        try require(result.contested.first?.evidencias == ["foi a feira"], "A evidência deve chegar ao app.")
        try require(!result.contested.contains { $0.estado != "contestada" }, "Inconclusivo nunca é contestação.")
        print("Contrato do Validador de decisões: OK")
    }
}
