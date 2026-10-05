import Foundation
import CryptoKit

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

/// Verbos da narração que contradizem o tempo escolhido (campo opcional). Só aviso.
struct TenseContradiction: Decodable, Equatable {
    let escolhido: String
    let predominante: String
    let passado: Int
    let presente: Int
}

struct ReportMetadata: Decodable {
    let tempo: String
    let paragrafos: Int
    let versaoFonte: String
    let languagetool: Bool
    let chapters: [ChapterMarker]?
    let stages: [AnalysisStage]?
    let narrativeSummary: NarrativeSummary?
    let tempoContradito: TenseContradiction?
    enum CodingKeys: String, CodingKey {
        case tempo, paragrafos, languagetool, chapters, stages
        case versaoFonte = "versao_fonte"
        case narrativeSummary = "narrative_summary"
        case tempoContradito = "tempo_contradito"
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

/// Alertas que o autor marcou como falso positivo, exportados para estudar e corrigir as regras.
/// Contém trechos do manuscrito: fica fora do repositório.
struct FalsePositiveExport: Encodable {
    struct Entry: Encodable {
        let id: String
        let module: String?
        let layer: String?
        let rule: String?
        let category: String
        let severity: String?
        let priority: String
        let confidence: String?
        let confidenceScore: Double?
        let source: String
        let chapter: String
        let paragraph: Int
        let start: Int
        let end: Int
        let excerpt: String
        let suggestion: String?
        let reason: String
        let text: String
        enum CodingKeys: String, CodingKey {
            case id, module, layer, rule, category, severity, priority, confidence, source, chapter, paragraph
            case start, end, excerpt, suggestion, reason, text
            case confidenceScore = "confidence_score"
        }
        init(_ finding: Finding) {
            id = finding.id; module = finding.module; layer = finding.layer; rule = finding.rule
            category = finding.category; severity = finding.severity; priority = finding.priority
            confidence = finding.confidence; confidenceScore = finding.confidence_score; source = finding.source
            chapter = finding.chapter; paragraph = finding.paragraph; start = finding.start; end = finding.end
            excerpt = finding.segments.marked; suggestion = finding.suggestion; reason = finding.reason; text = finding.text
        }
        /// Grava `null` nos campos ausentes: todas as entradas têm as mesmas chaves.
        func encode(to encoder: Encoder) throws {
            var c = encoder.container(keyedBy: CodingKeys.self)
            try c.encode(id, forKey: .id); try c.encode(module, forKey: .module); try c.encode(layer, forKey: .layer)
            try c.encode(rule, forKey: .rule); try c.encode(category, forKey: .category); try c.encode(severity, forKey: .severity)
            try c.encode(priority, forKey: .priority); try c.encode(confidence, forKey: .confidence)
            try c.encode(confidenceScore, forKey: .confidenceScore); try c.encode(source, forKey: .source)
            try c.encode(chapter, forKey: .chapter); try c.encode(paragraph, forKey: .paragraph)
            try c.encode(start, forKey: .start); try c.encode(end, forKey: .end); try c.encode(excerpt, forKey: .excerpt)
            try c.encode(suggestion, forKey: .suggestion); try c.encode(reason, forKey: .reason); try c.encode(text, forKey: .text)
        }
    }
    let schemaVersion = 1
    let document: String
    let sha256: String
    let engineVersion: String
    let exportedAt: String
    let findings: [Entry]
    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case document, sha256, findings
        case engineVersion = "engine_version"
        case exportedAt = "exported_at"
    }
}

extension FalsePositiveExport {
    /// Os alertas marcados como falso positivo, na ordem do relatório; `nil` quando não há nenhum.
    init?(report: EditorialReport, decisions: [String: ReviewDecision], exportedAt: Date) {
        let findings = report.findings.filter { decisions[$0.id] == .falsePositive }
        guard !findings.isEmpty else { return nil }
        self.init(document: report.document, sha256: report.sha256, engineVersion: report.metadata.versaoFonte,
                  exportedAt: ISO8601DateFormatter().string(from: exportedAt), findings: findings.map(Entry.init))
    }

    func encoded() throws -> Data {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        return try encoder.encode(self)
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

extension Finding {
    /// Identidade do alerta pelo conteúdo: categoria, regra, origem, parágrafo, trecho e evidências.
    /// Sem número de parágrafo nem capítulo, para sobreviver a parágrafos inseridos ou apagados.
    var contentKey: String {
        struct Evidence: Encodable { let text: String; let start: Int; let end: Int; let document: String }
        struct Key: Encodable {
            let category: String; let rule: String?; let source: String
            let text: String; let start: Int; let end: Int; let related: [Evidence]
        }
        let key = Key(category: category, rule: rule, source: source, text: text, start: start, end: end,
                      related: (related ?? []).map { Evidence(text: $0.text, start: $0.start, end: $0.end, document: $0.document) })
        let encoder = JSONEncoder(); encoder.outputFormatting = [.sortedKeys]
        let data = (try? encoder.encode(key)) ?? Data()
        return SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
    }
}

/// Decisões do último relatório salvo de um livro, identificado pelo nome do arquivo.
/// Uma análise nova (outro SHA-256, depois de editar o manuscrito fora do Lume) herda as
/// decisões dos alertas idênticos pelo conteúdo. Nada é herdado por aproximação.
struct BookMemory: Codable {
    let schemaVersion: Int
    let document: String
    let sha256: String
    /// Chave de conteúdo → decisões dos alertas com essa chave, na ordem do relatório.
    let decisions: [String: [String]]
    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case document, sha256, decisions
    }

    init(report: EditorialReport, decisions: [String: ReviewDecision]) {
        schemaVersion = 1; document = report.document; sha256 = report.sha256
        self.decisions = report.findings.reduce(into: [:]) { result, finding in
            result[finding.contentKey, default: []].append((decisions[finding.id] ?? .pending).rawValue)
        }
    }

    /// Nome do livro: sem extensão (.docx e .pages são o mesmo livro), sem maiúsculas, Unicode composto.
    static func bookName(_ document: String) -> String {
        let name = (document as NSString).deletingPathExtension
        return name.precomposedStringWithCanonicalMapping.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)
    }

    static func fileName(_ document: String) -> String {
        String(bookName(document).map { $0.isLetter || $0.isNumber || $0 == "-" || $0 == " " ? $0 : "-" }) + ".json"
    }

    func belongs(to report: EditorialReport) -> Bool {
        Self.bookName(document) == Self.bookName(report.document)
    }

    /// Decisões (exceto Pendente) dos alertas idênticos. Chave repetida só herda, na ordem,
    /// quando a quantidade é a mesma antes e depois; senão é ambígua e fica pendente.
    func inherited(for report: EditorialReport) -> [String: ReviewDecision] {
        let groups = Dictionary(grouping: report.findings, by: \.contentKey)
        var result: [String: ReviewDecision] = [:]
        for (key, findings) in groups {
            guard let previous = decisions[key], previous.count == findings.count else { continue }
            for (finding, raw) in zip(findings, previous) {
                if let value = ReviewDecision(rawValue: raw), value != .pending { result[finding.id] = value }
            }
        }
        return result
    }

    func encoded() throws -> Data {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        return try encoder.encode(self)
    }

    static func decode(_ data: Data) throws -> BookMemory {
        let file = try JSONDecoder().decode(BookMemory.self, from: data)
        guard file.schemaVersion == 1 else { throw FonteError.message("Arquivo do livro com versão desconhecida.") }
        return file
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
