import Foundation

@main
struct ContractCheck {
    static func require(_ condition: Bool, _ message: String) throws {
        if !condition { throw FonteError.message(message) }
    }

    static func main() async throws {
        guard CommandLine.arguments.count == 3 else {
            throw FonteError.message("Uso: fonte-contract relatorio.json /caminho/.venv/bin/python")
        }
        let reportURL = URL(fileURLWithPath: CommandLine.arguments[1])
        let report = try JSONDecoder().decode(EditorialReport.self, from: Data(contentsOf: reportURL))
        try report.validate()
        try require(!report.findings.isEmpty, "O exemplo deveria conter alertas.")
        for finding in report.findings {
            let parts = finding.segments
            try require(parts.before + parts.marked + parts.after == finding.text, "O destaque alterou o texto.")
        }
        let text = "🌿 Cafe\u{0301} observa."
        let finding = Finding(id: "unicode", category: "Teste", priority: "baixa", paragraph: 1,
                              chapter: "Teste", text: text, start: 8, end: 15, reason: "Teste", source: "Teste",
                              layer: nil, rule: nil, confidence: nil, related: nil, context: nil)
        try require(finding.segments.marked == "observa", "Offsets Python/Swift divergentes.")
        let file = DecisionFile(schemaVersion: 1, sha256: report.sha256, document: report.document,
                                decisions: [report.findings[0].id: ReviewDecision.falsePositive.rawValue])
        let encoded = try JSONEncoder().encode(file)
        let object = try JSONSerialization.jsonObject(with: encoded) as? [String: Any]
        try require(object?["schema_version"] as? Int == 1, "Chave JSON incompatível.")
        let restored = try JSONDecoder().decode(DecisionFile.self, from: encoded)
        try require(restored.decisions == file.decisions, "Decisões divergentes.")

        var settings = SearchSettings()
        settings.repetitionScopes = ["narracao"]
        settings.rules["tempo_verbal"] = false
        settings.chapterTitles = ["Capítulo um", "A floresta"]
        let settingsData = try settings.encoded()
        let settingsJSON = try JSONSerialization.jsonObject(with: settingsData) as? [String: Any]
        try require(settingsJSON?["word_distance"] as? Int == 8, "Chave de configuração incompatível.")
        let decodedSettings = try SearchSettings.decode(settingsData)
        try require(decodedSettings.chapterTitles == settings.chapterTitles && decodedSettings.repetitionScopes == ["narracao"], "Configuração não preservada.")

        // Migração das configurações completas v0.6, inclusive ‘desativar todas’.
        var oldSettings = settings
        oldSettings.rules = oldSettings.rules.filter { !SearchRule.newIDs.contains($0.key) }
        oldSettings.rules = oldSettings.rules.mapValues { _ in false }
        let migrated = try SearchSettings.decode(oldSettings.encoded())
        try require(migrated.rules.count == SearchRule.all.count && !migrated.rules.values.contains(true),
                    "A migração reativou regras desativadas.")

        if let stages = report.metadata.stages {
            try require(stages.map(\.module) == ReviewModule.allCases.map(\.rawValue), "Ordem de módulos divergente.")
            // Até o FONTE 1.3.1 a auditoria vinha como `not_implemented`; esses relatórios continuam válidos.
            let audit = stages.last
            try require(["not_implemented", "skipped", "completed", "failed"].contains(audit?.state ?? ""), "Estado da auditoria desconhecido.")
            let audited = report.findings.filter { $0.module == "audit" }.count
            try require(audit?.state == "completed" ? audited == audit?.finding_count : audited == 0,
                        "Ocorrências da auditoria sem a etapa concluída.")
            try require(report.findings.allSatisfy { $0.module != nil && $0.severity != nil && $0.range != nil },
                        "Ocorrências sem contrato modular.")
        }
        // O mesmo leitor deve continuar aceitando os relatórios anteriores.
        var legacy = try JSONSerialization.jsonObject(with: Data(contentsOf: reportURL)) as! [String: Any]
        var legacyMetadata = legacy["metadata"] as! [String: Any]
        legacyMetadata.removeValue(forKey: "stages"); legacy["metadata"] = legacyMetadata
        legacy["findings"] = (legacy["findings"] as! [[String: Any]]).map { row in
            row.filter { !["module", "severity", "confidence_score", "range", "excerpt", "suggestion"].contains($0.key) }
        }
        let oldReport = try JSONDecoder().decode(EditorialReport.self, from: JSONSerialization.data(withJSONObject: legacy))
        try oldReport.validate()
        try require(oldReport.findings.count == report.findings.count, "Leitura legada alterou os alertas.")
        try require(oldReport.metadata.tempoContradito == nil, "Aviso de tempo inventado num relatório sem ele.")

        // Tempo escolhido contrariado pela narração (campo opcional).
        var contradicted = try JSONSerialization.jsonObject(with: Data(contentsOf: reportURL)) as! [String: Any]
        var contradictedMetadata = contradicted["metadata"] as! [String: Any]
        contradictedMetadata["tempo_contradito"] = ["escolhido": "passado", "predominante": "presente", "passado": 35, "presente": 412]
        contradicted["metadata"] = contradictedMetadata
        let withNotice = try JSONDecoder().decode(EditorialReport.self, from: JSONSerialization.data(withJSONObject: contradicted))
        try require(withNotice.metadata.tempoContradito == TenseContradiction(escolhido: "passado", predominante: "presente", passado: 35, presente: 412),
                    "Aviso de tempo escolhido não lido.")

        // Estimativa da auditoria como o motor imprime (campos a mais são ignorados).
        let line = #"{"modelo": "claude-opus-5-5", "esforco": "medium", "trechos": 5, "a_enviar": 2, "reaproveitados": 3, "titulos_a_enviar": ["Capítulo 2", "Capítulo 4"], "caracteres": 9000, "custo_estimado_usd": 0.12, "custo_minimo_usd": 0.06, "custo_maximo_usd": 0.24, "calibracao": "provisoria"}"#
        let audit = try JSONDecoder().decode(AuditEstimate.self, from: Data(line.utf8))
        var combined = AIEstimate(coherence: nil, audit: audit, coherenceBudget: 1, auditBudget: 0.5)
        try require(combined.summary.contains("2 de 5 trechos") && combined.summary.contains("Teto: US$ 0.50")
                    && !combined.summary.contains("Coerência"), "Estimativa da auditoria mal lida.")
        combined.audit = try JSONDecoder().decode(AuditEstimate.self, from: Data(line.replacingOccurrences(of: #""a_enviar": 2"#, with: #""a_enviar": 0"#).utf8))
        try require(combined.summary.contains("não há custo"), "Auditoria sem envio deveria dizer que não há custo.")

        let temporary = FileManager.default.temporaryDirectory.appendingPathComponent("FONTE contrato \(UUID().uuidString)")
        try FileManager.default.createDirectory(at: temporary, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: temporary) }
        let argument = "Livro d'Água $(literal) 🌿"
        let log = temporary.appendingPathComponent("registro.txt")
        let result = try await PythonRunner.shared.run(
            executable: URL(fileURLWithPath: CommandLine.arguments[2]),
            arguments: ["-c", "import sys; print(sys.argv[1])", argument],
            directory: temporary, logURL: log)
        try require(result.exitCode == 0 && !result.cancelled, "Falha no processo Python.")
        try require(PythonRunner.tail(log).trimmingCharacters(in: .whitespacesAndNewlines) == argument,
                    "O argumento não chegou intacto ao Python.")
        print("Contrato Swift validado: JSON, decisões, Unicode e execução Python.")
    }
}
