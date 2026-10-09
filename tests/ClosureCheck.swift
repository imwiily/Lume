import Foundation

/// Confere a mesa em três partes (pendências, observações, impeditivos) e o encerramento da revisão:
/// impeditivo sem decisão bloqueia; pendências comuns e observações abertas não bloqueiam e ficam
/// registradas; relatório antigo, sem destino, é tudo pendência; o registro vale só para o mesmo
/// texto e a mesma política.
///
///     swiftc app/Lume/Models.swift tests/ClosureCheck.swift -o build/encerramento-swift
///     build/encerramento-swift
@main
struct ClosureCheck {
    static func require(_ condition: Bool, _ message: String) throws {
        if !condition { throw FonteError.message(message) }
    }

    static func finding(_ id: String, destino: String?, impeditivo: Bool?, severity: String = "probable_error") -> String {
        let extra = [destino.map { "\"destino\": \"\($0)\"" }, impeditivo.map { "\"impeditivo\": \($0)" }]
            .compactMap { $0 }.map { ", " + $0 }.joined()
        return """
        {"id": "\(id)", "category": "Crase", "priority": "Verificar", "paragraph": 1, "chapter": "Capítulo Um",
         "text": "Ela foi a feira.", "start": 8, "end": 15, "reason": "Explicação.", "source": "regra", "layer": null,
         "rule": "crase", "confidence": "média", "related": null, "context": null,
         "module": "linguistic", "severity": "\(severity)"\(extra)}
        """
    }

    static func report(_ findings: [String], policy: Int?, sha: String = String(repeating: "a", count: 64)) throws -> EditorialReport {
        let policyField = policy.map { ", \"politica_versao\": \($0)" } ?? ""
        let json = """
        {"schema_version": 1, "document": "livro.pages", "sha256": "\(sha)",
         "metadata": {"tempo": "passado", "paragrafos": 1, "versao_fonte": "1.4.0", "languagetool": false\(policyField),
                      "diagnostico": []},
         "warnings": [], "findings": [\(findings.joined(separator: ","))]}
        """
        let decoded = try JSONDecoder().decode(EditorialReport.self, from: Data(json.utf8))
        try decoded.validate()
        return decoded
    }

    static func main() throws {
        let current = try report([finding("p1", destino: "pendencia", impeditivo: false),
                                  finding("b1", destino: "pendencia", impeditivo: true),
                                  finding("o1", destino: "informacao", impeditivo: false, severity: "editorial_attention")],
                                 policy: 2)
        var decisions: [String: ReviewDecision] = [:]
        func tally() -> ReviewTally { ReviewTally(findings: current.findings) { decisions[$0.id] ?? .pending } }

        var counts = tally()
        try require((counts.pending, counts.blocking, counts.observations) == (2, 1, 1), "Contagem por destino errada.")
        try require(!counts.canClose, "Impeditivo sem decisão deveria bloquear o encerramento.")
        try require(ReviewClosure(report: current, tally: counts) == nil, "Encerramento registrado com impeditivo aberto.")

        decisions["b1"] = .falsePositive
        counts = tally()
        try require(counts.canClose, "Com o impeditivo decidido, o encerramento deveria estar disponível.")
        try require((counts.pendingOpen, counts.observationsOpen) == (1, 1), "Abertos contados errado.")
        let date = Date(timeIntervalSince1970: 1_791_000_000)
        guard let record = ReviewClosure(report: current, tally: counts, date: date) else {
            throw FonteError.message("Encerramento não foi criado.")
        }
        try require(record.openPendencies == 1 && record.openObservations == 1 && record.openBlocking == 0,
                    "O registro deve guardar o que ficou aberto.")
        try require(record.engineVersion == "1.4.0" && record.policyVersion == 2, "Versões do motor e da política ausentes.")

        let decoded = try ReviewClosure.decode(record.encoded())
        try require(decoded == record, "O registro não sobrevive à gravação.")
        let text = String(decoding: try record.encoded(), as: UTF8.self)
        for key in ["encerrada_em", "versao_motor", "versao_politica", "pendencias_abertas", "observacoes_abertas"] {
            try require(text.contains("\"\(key)\""), "Campo \(key) ausente no JSON.")
        }
        try require(record.applies(to: current), "O encerramento deveria valer para o mesmo texto e política.")
        try require(!record.applies(to: try report([], policy: 3)), "Política nova não pode herdar o encerramento.")
        try require(!record.applies(to: try report([], policy: 2, sha: String(repeating: "b", count: 64))),
                    "Texto novo não pode herdar o encerramento.")

        // Relatório antigo: sem destino nem política, tudo é pendência comum e nada bloqueia.
        let old = try report([finding("x1", destino: nil, impeditivo: nil)], policy: nil)
        let oldCounts = ReviewTally(findings: old.findings) { _ in .pending }
        try require((oldCounts.pending, oldCounts.blocking, oldCounts.observations) == (1, 0, 0) && oldCounts.canClose,
                    "Relatório antigo deveria ser só pendências, sem impeditivos.")
        try require(ReviewClosure(report: old, tally: oldCounts)?.policyVersion == nil, "Relatório antigo sem política.")

        // Contrato: impeditivo só em pendência; destino desconhecido é recusado.
        for bad in [finding("z1", destino: "informacao", impeditivo: true), finding("z2", destino: "outro", impeditivo: false)] {
            if (try? report([bad], policy: 2)) != nil { throw FonteError.message("Destino inválido aceito.") }
        }
        // Decisão nova sem mudar os atalhos antigos.
        try require(ReviewDecision.allCases.last == .corrected && ReviewDecision(rawValue: "Corrigido") == .corrected,
                    "“Corrigido” deve ser o último caso.")

        print("Encerramento validado: destinos, impeditivos, registro, versões, relatório antigo e contrato.")
    }
}
