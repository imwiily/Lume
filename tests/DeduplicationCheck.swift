import Foundation

/// Confere a memória editorial com ocorrências absorvidas (estabilização, Fase 6b): o alerta principal
/// herda pela própria identidade e, depois, pelas identidades que o motor juntou a ele; decisões
/// divergentes viram conflito registrado, nunca uma escolha automática.
///
///     swiftc app/Lume/Models.swift tests/DeduplicationCheck.swift -o build/deduplicacao-swift
///     build/deduplicacao-swift
@main
struct DeduplicationCheck {
    static func require(_ condition: Bool, _ message: String) throws {
        if !condition { throw FonteError.message(message) }
    }

    static let text = "Ele começou à mexer na caixa."

    struct Alert {
        var id: String
        var start: Int
        var end: Int
        var category: String
        var rule: String?
        var source: String
        var absorbed: [Alert] = []

        func json(absorbedFields: Bool) -> String {
            let rule = self.rule.map { "\"\($0)\"" } ?? "null"
            let extra = absorbed.isEmpty || !absorbedFields ? "" : """
            , "detectores": ["\(source)", \(absorbed.map { "\"\($0.source)\"" }.joined(separator: ","))],
              "absorvidos": [\(absorbed.map { """
                {"id": "\($0.id)", "rule": \($0.rule.map { "\"\($0)\"" } ?? "null"), "classe": "languagetool:gramatica",
                 "category": "\($0.category)", "source": "\($0.source)", "paragraph": 1, "start": \($0.start), "end": \($0.end)}
                """ }.joined(separator: ","))]
            """
            return """
            {"id": "\(id)", "category": "\(category)", "priority": "Verificar", "paragraph": 1, "chapter": "Um",
             "text": "\(DeduplicationCheck.text)", "start": \(start), "end": \(end), "reason": "Motivo.", "source": "\(source)",
             "layer": null, "rule": \(rule), "confidence": null, "related": null, "context": null\(extra)}
            """
        }
    }

    static func report(_ sha: Character, _ alerts: [Alert], absorbedFields: Bool = true) throws -> EditorialReport {
        let json = """
        {"schema_version": 1, "document": "Livro.pages", "sha256": "\(String(repeating: sha, count: 64))",
         "metadata": {"tempo": "passado", "paragrafos": 1, "versao_fonte": "9.9.9", "languagetool": true},
         "warnings": [], "findings": [\(alerts.map { $0.json(absorbedFields: absorbedFields) }.joined(separator: ","))]}
        """
        let decoded = try JSONDecoder().decode(EditorialReport.self, from: Data(json.utf8))
        try decoded.validate()
        return decoded
    }

    // O mesmo fenômeno de crase, visto pelas duas fontes.
    static let fonte = Alert(id: "f1", start: 12, end: 19, category: "Crase indevida", rule: "crase",
                             source: "FONTE Morfossintático · crase")
    static let lt = Alert(id: "l1", start: 4, end: 19, category: "Ortografia e gramática", rule: "languagetool",
                          source: "LanguageTool local · CRASE_CONFUSION")
    static let lt2 = Alert(id: "l2", start: 12, end: 19, category: "Ortografia e gramática", rule: "languagetool",
                           source: "LanguageTool local · CRASE_CONFUSION_2")

    static func main() throws {
        var principal = fonte; principal.absorbed = [lt]

        // Herança direta: sem o LT, o FONTE aparecia sozinho com o mesmo ID; com o LT, o principal é ele.
        let semLT = try report("a", [fonte])
        let memory = BookMemory(report: semLT, decisions: ["f1": .falsePositive])
        let comLT = try report("b", [principal])
        try require(memory.inheritance(for: comLT) == InheritedDecisions(decisions: ["f1": .falsePositive]),
                    "Herança direta do principal falhou.")

        // Herança pela absorvida: antes da 6b o LT aparecia sozinho e tinha a decisão.
        let antes = try report("c", [lt], absorbedFields: false)
        let fromLT = BookMemory(report: antes, decisions: ["l1": .error]).inheritance(for: comLT)
        try require(fromLT == InheritedDecisions(decisions: ["f1": .error]), "Herança pela ocorrência absorvida falhou: \(fromLT)")

        // Memória antiga, gravada quando o LT ainda saía sem `rule`: a chave antiga também vale.
        var semRegra = lt; semRegra.rule = nil
        let antiga = BookMemory(report: try report("d", [semRegra], absorbedFields: false), decisions: ["l1": .accepted])
        try require(antiga.inheritance(for: comLT).decisions == ["f1": .accepted], "Chave antiga da absorvida não foi consultada.")

        // Decisões compatíveis das duas absorvidas: herda.
        var dois = fonte; dois.absorbed = [lt, lt2]
        let ambos = try report("e", [lt, lt2], absorbedFields: false)
        let compat = BookMemory(report: ambos, decisions: ["l1": .error, "l2": .error]).inheritance(for: try report("f", [dois]))
        try require(compat == InheritedDecisions(decisions: ["f1": .error]), "Decisões compatíveis deveriam ser herdadas.")

        // Incompatíveis: nada é escolhido; o conflito fica registrado.
        let incompat = BookMemory(report: ambos, decisions: ["l1": .error, "l2": .falsePositive])
            .inheritance(for: try report("f", [dois]))
        try require(incompat.decisions.isEmpty && incompat.conflicts["f1"]?.count == 2,
                    "Decisões incompatíveis não podem ser escolhidas: \(incompat)")

        // Decisão direta e absorvida diferente: a direta fica; a divergência histórica aparece.
        let mista = try report("1", [fonte, lt], absorbedFields: false)
        let direta = BookMemory(report: mista, decisions: ["f1": .style, "l1": .error]).inheritance(for: comLT)
        try require(direta.decisions == ["f1": .style], "A decisão direta não pode ser sobrescrita.")
        try require(direta.conflicts["f1"] == ["Estilo do autor — este alerta", "Erro confirmado — LanguageTool local · CRASE_CONFUSION"],
                    "A divergência histórica precisa ficar visível: \(direta.conflicts)")

        // O conflito registrado sobrevive a uma nova análise (memória do livro) e ao JSON.
        let gravada = BookMemory(report: comLT, decisions: ["f1": .style], conflicts: direta.conflicts)
        let lida = try BookMemory.decode(gravada.encoded())
        try require(lida.inheritance(for: try report("2", [principal])).conflicts["f1"] == direta.conflicts["f1"],
                    "Conflito registrado se perdeu na memória do livro.")

        // Fenômenos diferentes no mesmo trecho: cada um com a sua identidade; nada passa de um ao outro.
        let outro = Alert(id: "o1", start: 12, end: 19, category: "Ortografia e gramática", rule: "languagetool",
                          source: "LanguageTool local · CONTRACOES_OBRIGATORIAS")
        let separados = try report("3", [fonte, outro])
        let semTransferencia = BookMemory(report: separados, decisions: ["o1": .error]).inheritance(for: try report("4", [fonte, outro]))
        try require(semTransferencia == InheritedDecisions(decisions: ["o1": .error]), "Decisão passou para outro fenômeno.")

        // Reanálise do mesmo manuscrito: pelo ID da absorvida.
        let carry = CarriedDecisions(report: antes, decisions: ["l1": .intentional], selectedID: nil)
        let reanalise = carry.merge(into: [:], for: comLT)
        try require(reanalise.decisions == ["f1": .intentional], "Reanálise não consultou a identidade absorvida: \(reanalise)")
        let conflitoNaReanalise = CarriedDecisions(report: mista, decisions: ["f1": .style, "l1": .error], selectedID: nil)
            .merge(into: [:], for: comLT)
        try require(conflitoNaReanalise.decisions == ["f1": .style] && conflitoNaReanalise.conflicts["f1"] != nil,
                    "Reanálise escondeu a divergência: \(conflitoNaReanalise)")

        // Relatório antigo e arquivos antigos: sem os campos novos, tudo como antes.
        let velho = try report("5", [fonte, lt], absorbedFields: false)
        try require(velho.findings.allSatisfy { $0.absorvidos == nil && $0.detectores == nil }, "Relatório antigo ganhou campos.")
        try require(BookMemory(report: velho, decisions: ["l1": .error]).inheritance(for: velho)
                    == InheritedDecisions(decisions: ["l1": .error]), "Relatório antigo mudou de herança.")
        let arquivo = #"{"schema_version": 1, "sha256": "x", "document": "Livro.pages", "decisions": {"f1": "Falso positivo"}}"#
        let decisoes = try JSONDecoder().decode(DecisionFile.self, from: Data(arquivo.utf8))
        try require(decisoes.conflicts == nil, "Arquivo de decisões antigo deveria ser lido sem conflitos.")
        let livro = #"{"schema_version": 1, "sha256": "x", "document": "Livro.pages", "decisions": {}}"#
        try require(try BookMemory.decode(Data(livro.utf8)).conflicts == nil, "Memória antiga deveria ser lida.")
        let semConflito = String(data: try BookMemory(report: velho, decisions: [:]).encoded(), encoding: .utf8) ?? ""
        try require(!semConflito.contains("conflitos"), "Memória sem conflitos não deve gravar o campo.")

        print("Deduplicação validada: herança direta e por absorvida, chave antiga, compatíveis, incompatíveis, decisão direta divergente, persistência, fenômenos diferentes, reanálise e arquivos antigos.")
    }
}
