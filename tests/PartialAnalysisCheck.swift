import Foundation

/// Confere a análise parcial (LanguageTool pedido e indisponível; estabilização, Fase 6b): o relatório
/// diz o que faltou, a etapa mostra o ausente e o encerramento de uma análise parcial não se confunde
/// com o de uma completa, nem a substitui.
///
///     swiftc app/Lume/Models.swift tests/PartialAnalysisCheck.swift -o build/parcial-swift
///     build/parcial-swift
@main
struct PartialAnalysisCheck {
    static func require(_ condition: Bool, _ message: String) throws {
        if !condition { throw FonteError.message(message) }
    }

    static func report(partial: Bool) throws -> EditorialReport {
        let extra = partial ? """
        , "languagetool_pedido": true, "languagetool_status": "indisponivel",
          "analise_parcial": {"ausente": [{"etapa": "linguistic", "componente": "LanguageTool",
                                           "motivo": "O corretor gramatical embutido não iniciou."}]}
        """ : ""
        let stage = """
        {"module": "linguistic", "title": "Revisão linguística", "state": "completed", "finding_count": 1,
         "coverage": "partial", "detail": "Padrões."\(partial ? #", "ausente": "LanguageTool""# : "")}
        """
        let json = """
        {"schema_version": 1, "document": "Livro.pages", "sha256": "\(String(repeating: "a", count: 64))",
         "metadata": {"tempo": "passado", "paragrafos": 1, "versao_fonte": "9.9.9", "languagetool": \(!partial),
                      "politica_versao": 2, "stages": [\(stage)]\(extra)},
         "warnings": [], "findings": [
           {"id": "f1", "category": "Pontuação duplicada", "priority": "Verificar", "paragraph": 1, "chapter": "Um",
            "text": "Ela parou,, e olhou.", "start": 9, "end": 11, "reason": "Motivo.", "source": "FONTE Linguístico · pontuacao_duplicada",
            "layer": null, "rule": "pontuacao_duplicada", "confidence": "alta", "related": null, "context": null,
            "destino": "informacao", "impeditivo": false}]}
        """
        let decoded = try JSONDecoder().decode(EditorialReport.self, from: Data(json.utf8))
        try decoded.validate()
        return decoded
    }

    static func main() throws {
        let completo = try report(partial: false), parcial = try report(partial: true)
        try require(completo.metadata.analiseParcial == nil, "Relatório completo não pode parecer parcial.")
        try require(parcial.metadata.analiseParcial?.components == ["LanguageTool"], "O componente ausente se perdeu.")
        try require(parcial.metadata.stages?.first?.statusText == "1 ocorrências · sem o LanguageTool (indisponível)",
                    "A etapa precisa mostrar o ausente: \(parcial.metadata.stages?.first?.statusText ?? "")")
        try require(completo.metadata.stages?.first?.statusText == "1 ocorrências · cobertura parcial", "Etapa completa mudou.")

        let tally = ReviewTally(findings: completo.findings, decision: { _ in .pending })
        guard let fechamentoCompleto = ReviewClosure(report: completo, tally: tally),
              let fechamentoParcial = ReviewClosure(report: parcial, tally: tally) else {
            throw FonteError.message("Encerramento deveria ser possível.")
        }
        try require(!fechamentoCompleto.isPartial && fechamentoParcial.missing == ["LanguageTool"], "Registro do alcance errado.")
        // Um não vale para o outro, e os arquivos são diferentes: nada é substituído em silêncio.
        try require(fechamentoCompleto.applies(to: completo) && !fechamentoCompleto.applies(to: parcial),
                    "Encerramento completo não pode valer para análise parcial.")
        try require(fechamentoParcial.applies(to: parcial) && !fechamentoParcial.applies(to: completo),
                    "Encerramento parcial não pode valer para análise completa.")
        try require(ReviewClosure.fileName(completo.sha256) != ReviewClosure.fileName(parcial.sha256, partial: true),
                    "Encerramento parcial substituiria o completo.")
        // JSON: o registro parcial guarda o ausente; o antigo, sem o campo, continua valendo para a completa.
        let lido = try ReviewClosure.decode(fechamentoParcial.encoded())
        try require(lido.missing == ["LanguageTool"], "Ausente não foi gravado no encerramento.")
        let antigo = #"{"schema_version": 1, "document": "Livro.pages", "sha256": "\#(String(repeating: "a", count: 64))", "encerrada_em": "2026-10-01T10:00:00Z", "versao_motor": "9.9.9", "versao_politica": 2, "pendencias_abertas": 0, "observacoes_abertas": 1, "impeditivos_abertos": 0}"#
        let registroAntigo = try ReviewClosure.decode(Data(antigo.utf8))
        try require(registroAntigo.applies(to: completo) && !registroAntigo.applies(to: parcial),
                    "Encerramento antigo deveria valer só para a análise completa.")
        let gravado = String(data: try fechamentoCompleto.encoded(), encoding: .utf8) ?? ""
        try require(!gravado.contains("analise_parcial_sem"), "Encerramento completo não deve gravar o campo.")

        print("Análise parcial validada: relatório, etapa, encerramento separado, registro e compatibilidade.")
    }
}
