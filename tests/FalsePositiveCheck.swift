import Foundation

/// Confere o arquivo de “Extrair falsos positivos” sem abrir o painel de salvar.
///
///     swiftc app/Lume/Models.swift tests/FalsePositiveCheck.swift -o build/falsos-positivos-swift
///     build/falsos-positivos-swift
@main
struct FalsePositiveCheck {
    static func require(_ condition: Bool, _ message: String) throws {
        if !condition { throw FonteError.message(message) }
    }

    /// Relatório sintético: um alerta modular com emoji e acento combinado antes do trecho,
    /// um alerta de relatório antigo (sem módulo, severidade nem sugestão) e um terceiro alerta.
    static let report = """
    {"schema_version": 1, "document": "teste.docx", "sha256": "\(String(repeating: "a", count: 64))",
     "metadata": {"tempo": "passado", "paragrafos": 3, "versao_fonte": "9.9.9", "languagetool": false},
     "warnings": [],
     "findings": [
      {"id": "f1", "category": "Tempo verbal", "priority": "alta", "paragraph": 2, "chapter": "Um",
       "text": "🌿 Cafe\\u0301 observa a rua.", "start": 8, "end": 15, "reason": "Presente na narração.",
       "source": "regra", "layer": "linguistica", "rule": "coerencia_temporal", "confidence": "média",
       "related": null, "context": null, "module": "morphosyntactic", "severity": "probable_error",
       "confidence_score": 0.7, "excerpt": "observa", "suggestion": "observava"},
      {"id": "f2", "category": "Repetição", "priority": "baixa", "paragraph": 3, "chapter": "Dois",
       "text": "Era era tarde.", "start": 0, "end": 7, "reason": "Palavra repetida.",
       "source": "regra", "layer": null, "rule": null, "confidence": null, "related": null, "context": null},
      {"id": "f3", "category": "Pontuação", "priority": "média", "paragraph": 1, "chapter": "Um",
       "text": "Fim..", "start": 3, "end": 5, "reason": "Ponto duplicado.",
       "source": "regra", "layer": null, "rule": "pontuacao_duplicada", "confidence": null,
       "related": null, "context": null}
     ]}
    """

    static func main() throws {
        let report = try JSONDecoder().decode(EditorialReport.self, from: Data(Self.report.utf8))
        let date = Date(timeIntervalSince1970: 1_790_000_000)

        // Sem falsos positivos não há arquivo.
        try require(FalsePositiveExport(report: report, decisions: [:], exportedAt: date) == nil,
                    "Relatório sem decisões não deveria gerar arquivo.")
        try require(FalsePositiveExport(report: report, decisions: ["f1": .error, "f2": .style, "f3": .accepted],
                                        exportedAt: date) == nil,
                    "Outras decisões não são falsos positivos.")

        // Só os falsos positivos, na ordem do relatório (não na do dicionário de decisões).
        let decisions: [String: ReviewDecision] = ["f3": .falsePositive, "f2": .intentional, "f1": .falsePositive,
                                                   "inexistente": .falsePositive]
        guard let export = FalsePositiveExport(report: report, decisions: decisions, exportedAt: date) else {
            throw FonteError.message("Os falsos positivos não foram extraídos.")
        }
        try require(export.findings.map(\.id) == ["f1", "f3"], "Seleção ou ordem dos falsos positivos incorreta.")

        // O JSON gravado: chaves estáveis, trecho pelos índices Python e campos de relatório antigo nulos.
        let object = try JSONSerialization.jsonObject(with: export.encoded()) as? [String: Any]
        try require(object?["schema_version"] as? Int == 1, "Versão do arquivo ausente.")
        try require(object?["document"] as? String == "teste.docx" && object?["sha256"] as? String == report.sha256,
                    "Documento ou hash ausente.")
        try require(object?["engine_version"] as? String == "9.9.9", "Versão do motor ausente.")
        try require(object?["exported_at"] as? String == ISO8601DateFormatter().string(from: date), "Data da extração incorreta.")
        let entries = object?["findings"] as? [[String: Any]] ?? []
        try require(entries.count == 2, "Quantidade de entradas incorreta.")
        let first = entries[0], second = entries[1]
        try require(first["excerpt"] as? String == "observa", "Trecho fora dos índices em pontos de código.")
        try require(first["text"] as? String == "🌿 Cafe\u{0301} observa a rua.", "Parágrafo alterado na extração.")
        try require(first["rule"] as? String == "coerencia_temporal" && first["module"] as? String == "morphosyntactic"
                    && first["severity"] as? String == "probable_error" && first["suggestion"] as? String == "observava"
                    && first["confidence_score"] as? Double == 0.7 && first["paragraph"] as? Int == 2
                    && first["chapter"] as? String == "Um" && first["reason"] as? String == "Presente na narração.",
                    "Campos do alerta modular incompletos.")
        try require(first["start"] as? Int == 8 && first["end"] as? Int == 15, "Posição do trecho incorreta.")
        try require(second["excerpt"] as? String == "..", "Trecho do relatório antigo incorreto.")
        try require(second["module"] is NSNull && second["severity"] is NSNull && second["suggestion"] is NSNull,
                    "Campos ausentes devem ficar nulos, não inventados.")
        try require(Set(first.keys) == Set(second.keys), "Entradas com chaves diferentes.")

        print("Extração de falsos positivos validada: seleção, ordem, Unicode, campos antigos e chaves JSON.")
    }
}
