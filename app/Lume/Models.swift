import Foundation

enum ReviewModule: String, CaseIterable, Identifiable {
    case linguistic, morphosyntactic, editorial, global_coherence, audit
    var id: String { rawValue }
    var title: String {
        switch self {
        case .linguistic: return "Linguístico"
        case .morphosyntactic: return "Morfossintático"
        case .editorial: return "Contexto curto"
        case .global_coherence: return "Coerência global"
        case .audit: return "Auditoria final"
        }
    }
}

enum FindingSeverity: String, CaseIterable, Identifiable {
    case confirmed_error, probable_error, editorial_attention, possible_inconsistency, author_query
    var id: String { rawValue }
    var title: String {
        switch self {
        case .confirmed_error: return "Erro confirmado"
        case .probable_error: return "Provável erro"
        case .editorial_attention: return "Atenção editorial"
        case .possible_inconsistency: return "Possível inconsistência"
        case .author_query: return "Consulta ao autor"
        }
    }
}

struct AnalysisStage: Decodable, Identifiable {
    let module: String
    let title: String
    let state: String
    let finding_count: Int
    let coverage: String
    let detail: String
    // Andamento dentro da etapa (motores a partir desta versão); ausente nos anteriores.
    var done: Int? = nil
    var total: Int? = nil
    var unit: String? = nil
    var id: String { module }
    /// “420 de 1.274 parágrafos”, com separador de milhar em português.
    var progressText: String? {
        guard let done, let total, total > 0 else { return nil }
        let numero = NumberFormatter()
        numero.locale = Locale(identifier: "pt_BR")
        numero.numberStyle = .decimal
        let feitos = numero.string(from: NSNumber(value: done)) ?? "\(done)"
        let todos = numero.string(from: NSNumber(value: total)) ?? "\(total)"
        return "\(feitos) de \(todos)" + (unit.map { " " + $0 } ?? "")
    }
    var statusText: String {
        switch state {
        case "running": return progressText.map { "Em andamento · " + $0 } ?? "Em andamento"
        case "completed": return "\(finding_count) ocorrências · cobertura parcial"
        case "skipped": return "Não selecionado"
        case "not_implemented": return "Ainda não disponível"
        case "failed": return "Interrompido"
        default: return "Aguardando"
        }
    }
    static var pending: [AnalysisStage] {
        ReviewModule.allCases.map {
            AnalysisStage(module: $0.rawValue, title: $0.title, state: $0 == .audit ? "not_implemented" : "pending",
                          finding_count: 0, coverage: $0 == .audit ? "not_implemented" : "partial", detail: "")
        }
    }
}

struct FindingRange: Decodable {
    let start: Int
    let end: Int
}

enum ReviewDecision: String, CaseIterable, Identifiable {
    case pending = "Pendente"
    case error = "Erro confirmado"
    case style = "Estilo do autor"
    case falsePositive = "Falso positivo"
    case intentional = "Intencional"
    case accepted = "Aceito editorialmente"
    var id: String { rawValue }
}

struct TextEvidence: Decodable {
    let paragraph: Int
    let chapter: String
    let text: String
    let start: Int
    let end: Int
    let document: String
    var valid: Bool { start >= 0 && end >= start && end <= text.unicodeScalars.count }
}

struct Finding: Decodable, Identifiable {
    let id: String
    let category: String
    let priority: String
    let paragraph: Int
    let chapter: String
    let text: String
    let start: Int
    let end: Int
    let reason: String
    let source: String
    let layer: String?
    let rule: String?
    let confidence: String?
    let related: [TextEvidence]?
    let context: [TextEvidence]?
    var module: String? = nil
    var severity: String? = nil
    var confidence_score: Double? = nil
    var range: FindingRange? = nil
    var excerpt: String? = nil
    var suggestion: String? = nil

    var moduleTitle: String { module.flatMap(ReviewModule.init(rawValue:))?.title ?? "Relatório anterior" }
    var severityTitle: String { severity.flatMap(FindingSeverity.init(rawValue:))?.title ?? "Sem classificação" }
    var validContract: Bool {
        (module == nil || ReviewModule(rawValue: module ?? "") != nil)
            && (severity == nil || FindingSeverity(rawValue: severity ?? "") != nil)
            && (confidence_score.map { $0.isFinite && (0...1).contains($0) } ?? true)
            && (range.map { $0.start >= 0 && $0.end >= $0.start && $0.end - $0.start == end - start } ?? true)
            && (excerpt.map { $0 == segments.marked } ?? true)
    }

    // Os offsets do Python contam pontos de código, não grafemas Swift ou UTF-16.
    var segments: (before: String, marked: String, after: String) {
        let scalars = Array(text.unicodeScalars)
        let lower = min(max(0, start), scalars.count)
        let upper = min(max(lower, end), scalars.count)
        func string(_ range: Range<Int>) -> String {
            scalars[range].map { String($0) }.joined()
        }
        return (string(0..<lower), string(lower..<upper), string(upper..<scalars.count))
    }
}

struct NarrativeSummary: Decodable {
    let scenes: Int
    let facts: Int
    let characters: Int
    let objects: Int
    let events: Int
}

struct ReportMetadata: Decodable {
    let tempo: String
    let paragrafos: Int
    let versaoFonte: String
    let languagetool: Bool
    let chapters: [ChapterMarker]?
    let stages: [AnalysisStage]?
    let narrativeSummary: NarrativeSummary?
    enum CodingKeys: String, CodingKey {
        case tempo, paragrafos, languagetool, chapters, stages
        case versaoFonte = "versao_fonte"
        case narrativeSummary = "narrative_summary"
    }
}

struct EditorialReport: Decodable {
    let schemaVersion: Int
    let document: String
    let sha256: String
    let metadata: ReportMetadata
    let warnings: [String]
    let findings: [Finding]
    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case document, sha256, metadata, warnings, findings
    }

    func validate() throws {
        guard schemaVersion == 1,
              sha256.count == 64,
              sha256.allSatisfy({ "0123456789abcdef".contains($0) }),
              Set(findings.map(\.id)).count == findings.count,
              findings.allSatisfy({ $0.start >= 0 && $0.end >= $0.start
                  && $0.end <= $0.text.unicodeScalars.count && $0.validContract
                  && ($0.related ?? []).allSatisfy({ $0.valid })
                  && ($0.context ?? []).allSatisfy({ $0.valid }) }) else {
            throw FonteError.message("O relatório tem versão, identificadores ou posições inválidas.")
        }
    }
}

struct DecisionFile: Codable {
    let schemaVersion: Int
    let sha256: String
    let document: String
    let decisions: [String: String]
    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case sha256, document, decisions
    }
}

enum FonteError: LocalizedError {
    case message(String)
    var errorDescription: String? {
        switch self { case .message(let message): return message }
    }
}

struct ChapterMarker: Decodable {
    let paragraph: Int
    let title: String
}

struct SearchRule: Identifiable {
    let id: String
    let title: String
    static let newIDs: Set<String> = ["construcao_invalida", "pontuacao_duplicada", "espacamento", "virgula_que_nao", "que_tonico_interrogativo", "coerencia_temporal", "acentuacao_contextual", "vocativo", "capitalizacao_contextual", "dialogo_contextual", "referente_contextual", "gerundismo",
                                          "crase", "homofonos", "concordancia", "regencia", "virgula_sujeito_verbo"]
    /// Regras da memória narrativa heurística, removida do motor: configurações antigas que as
    /// mencionam continuam abrindo, e essas chaves são descartadas.
    static let retiredIDs: Set<String> = ["memoria_narrativa", "conflito_habilidade", "conflito_objeto",
                                          "conflito_cronologia", "coerencia_generica"]
    static let all: [SearchRule] = [
        .init(id: "construcao_invalida", title: "Construções inválidas conhecidas"),
        .init(id: "pontuacao_duplicada", title: "Pontuação duplicada"),
        .init(id: "espacamento", title: "Espaçamento no texto"),
        .init(id: "virgula_que_nao", title: "Vírgula em ‘que, não’"),
        .init(id: "que_tonico_interrogativo", title: "Acento em quê no fim da pergunta"),
        .init(id: "vocativo", title: "Possíveis vocativos sem vírgula"),
        .init(id: "capitalizacao_contextual", title: "Maiúscula após pergunta ou exclamação"),
        .init(id: "coerencia_temporal", title: "Relações temporais entre orações"),
        .init(id: "acentuacao_contextual", title: "Acentuação verbal no contexto passado"),
        .init(id: "crase", title: "Crase ausente ou indevida"),
        .init(id: "homofonos", title: "Por que, há/a, onde/aonde, mal/mau, mas/mais"),
        .init(id: "concordancia", title: "Concordância verbal e nominal · narração"),
        .init(id: "regencia", title: "Regência na norma culta · atenção editorial"),
        .init(id: "virgula_sujeito_verbo", title: "Vírgula entre sujeito e verbo · narração"),
        .init(id: "tempo_verbal", title: "Mudanças de tempo verbal"),
        .init(id: "estrutura", title: "Estrutura da frase · narração"),
        .init(id: "pontuacao_dialogo", title: "Ligação entre fala e narração"),
        .init(id: "dialogo_contextual", title: "Ações e retomadas de fala por travessão"),
        .init(id: "referente_contextual", title: "Objeto após enumeração · contexto curto"),
        .init(id: "gerundismo", title: "Perífrases verbais · atenção editorial"),
        .init(id: "palavra_consecutiva", title: "Palavras repetidas consecutivamente"),
        .init(id: "palavra_proxima", title: "Palavras repetidas próximas"),
        .init(id: "frase_duplicada", title: "Frases repetidas"),
        .init(id: "variacao_nome", title: "Variações de nomes"),
        .init(id: "duracao_suspensao", title: "Duração de suspensão ou afastamento"),
        .init(id: "adiamento_amanha", title: "Adiamento para amanhã"),
        .init(id: "referente_proximidade", title: "Referências de proximidade pouco claras"),
        .init(id: "pronome_apos_corte", title: "Pronomes após cortes · exige original")
    ]
}

struct SearchSettings: Codable {
    var schemaVersion = 1
    var rules = Dictionary(uniqueKeysWithValues: SearchRule.all.map { ($0.id, true) })
    var tenseScopes = ["narracao"]
    var repetitionScopes = ["narracao", "dialogo", "pensamento"]
    var wordDistance = 8
    var repetitionBoundary = "trecho"
    var duplicateAcrossParagraphs = true
    var duplicateSimilarity = 1.0
    var dialogueDashes = true
    var quotesRole = "dialogo"
    var italicThoughts = true
    var ignoredNames: [String] = []
    var chapterTitles: [String] = []
    var chapterStyles: [String] = []
    var chapterAuto = true

    func encoded() throws -> Data {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        return try encoder.encode(self)
    }
    static func decode(_ data: Data) throws -> SearchSettings {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        var result = try decoder.decode(SearchSettings.self, from: data)
        for key in SearchRule.retiredIDs { result.rules.removeValue(forKey: key) }
        let scopes = Set(["narracao", "dialogo", "pensamento"])
        let known = Set(SearchRule.all.map(\.id))
        let legacy = known.subtracting(SearchRule.newIDs)
        guard result.schemaVersion == 1,
              legacy.isSubset(of: Set(result.rules.keys)),
              Set(result.rules.keys).isSubset(of: known),
              Set(result.tenseScopes).isSubset(of: scopes),
              Set(result.repetitionScopes).isSubset(of: scopes),
              (2...40).contains(result.wordDistance),
              ["trecho", "frase"].contains(result.repetitionBoundary),
              (0.8...1.0).contains(result.duplicateSimilarity),
              scopes.contains(result.quotesRole),
              [result.ignoredNames, result.chapterTitles, result.chapterStyles].allSatisfy({
                  $0.count <= 500 && $0.allSatisfy({ !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && $0.count <= 200 })
              }) else { throw FonteError.message("Configuração de busca inválida ou incompatível.") }
        let allDisabled = !result.rules.values.contains(true)
        for key in SearchRule.newIDs where result.rules[key] == nil {
            result.rules[key] = !allDisabled
        }
        return result
    }
}
