import Foundation

// MARK: Contrapropostas e fundamentações do autor
//
// Registro do próprio autor sobre um apontamento, ao lado do parecer da IA. Fica em
// Application Support/FONTE/Manifestacoes/<livro>.json, fora do cache do Validador: limpar o Validador
// não apaga nada daqui. Nunca altera decisão, relatório nem manuscrito e nunca é enviado a serviço algum.

struct EditorialNote: Codable, Identifiable, Equatable {
    enum Kind: String, Codable, CaseIterable, Identifiable {
        case counterproposal = "contraproposta"
        case rationale = "fundamentacao"
        var id: String { rawValue }
        /// Rótulo do campo no cartão de avaliação.
        var fieldTitle: String { self == .counterproposal ? "Minha contraproposta" : "Minha fundamentação" }
        var plural: String { self == .counterproposal ? "Contrapropostas" : "Fundamentações" }
    }

    /// ID do apontamento (um registro por apontamento).
    var id: String
    var kind: Kind
    /// Texto exatamente como o autor o salvou.
    var text: String
    var createdAt: Date
    var updatedAt: Date
    // Instantâneo do momento em que o autor salvou, para a exportação não depender de cache nem do relatório aberto.
    var book: String
    var manuscriptSHA: String
    var chapter: String
    var paragraph: Int
    var category: String
    var paragraphText: String
    var start: Int
    var end: Int
    var humanDecision: String
    var assessment: String
    var assessmentTitle: String
    var aiResultLabel: String?
    var aiDiagnosis: String?
    var aiExplanation: String?
    var aiSuggestion: String?
    var aiModel: String?
}

/// Situação do registro frente ao relatório, ao manuscrito e à avaliação atuais.
enum EditorialNoteState: Equatable {
    case current
    case assessmentChanged(from: String, to: String)
    case decisionChanged(from: String, to: String)
    case manuscriptChanged(paragraphIntact: Bool)
    case notLocated

    var isCurrent: Bool { self == .current }

    var message: String {
        switch self {
        case .current: return "Vigente: mesma versão do manuscrito e mesma avaliação da IA."
        case .assessmentChanged(let from, let to):
            return "Desatualizado: a avaliação da IA mudou desde o registro (era “\(from)”, agora “\(to)”)."
        case .decisionChanged(let from, let to):
            return "Desatualizado: a sua decisão mudou desde o registro (era “\(from)”, agora “\(to)”)."
        case .manuscriptChanged(let intact):
            return intact ? "Desatualizado: o manuscrito é de outra versão da registrada; o parágrafo continua igual."
                : "Desatualizado: o manuscrito é de outra versão da registrada e o parágrafo mudou."
        case .notLocated:
            return "Desatualizado: o apontamento não foi localizado no relatório aberto."
        }
    }

    /// Só leva ao apontamento quando ele é o mesmo parágrafo registrado.
    var canNavigate: Bool {
        switch self {
        case .current, .assessmentChanged, .decisionChanged: return true
        case .manuscriptChanged(let intact): return intact
        case .notLocated: return false
        }
    }

    /// Estado de `note` diante do que está aberto agora; `findingText == nil` quando o apontamento não existe.
    static func of(_ note: EditorialNote, reportSHA: String, findingText: String?, assessment: String?,
                   assessmentTitle: String?, decision: String?) -> EditorialNoteState {
        guard let findingText else { return .notLocated }
        if reportSHA != note.manuscriptSHA { return .manuscriptChanged(paragraphIntact: findingText == note.paragraphText) }
        if let assessment, assessment != note.assessment {
            return .assessmentChanged(from: note.assessmentTitle, to: assessmentTitle ?? assessment)
        }
        if let decision, decision != note.humanDecision { return .decisionChanged(from: note.humanDecision, to: decision) }
        return .current
    }
}

/// Arquivo por livro. Gravação atômica; arquivo ilegível é posto de lado, nunca sobrescrito.
enum EditorialNoteFile {
    private struct Container: Codable { var version = 1; var notes: [EditorialNote] }

    private static var encoder: JSONEncoder {
        let e = JSONEncoder(); e.dateEncodingStrategy = .iso8601
        e.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        return e
    }

    static func load(_ url: URL) throws -> [EditorialNote] {
        guard FileManager.default.fileExists(atPath: url.path) else { return [] }
        let decoder = JSONDecoder(); decoder.dateDecodingStrategy = .iso8601
        do { return try decoder.decode(Container.self, from: Data(contentsOf: url)).notes }
        catch {
            let aside = url.deletingPathExtension().appendingPathExtension("ilegivel-\(Int(Date().timeIntervalSince1970)).json")
            try? FileManager.default.moveItem(at: url, to: aside)
            throw error
        }
    }

    static func save(_ notes: [EditorialNote], to url: URL) throws {
        try encoder.encode(Container(notes: notes)).write(to: url, options: .atomic)
    }
}

enum EditorialNoteExport {
    /// Parágrafo inteiro, com a ocorrência em negrito. Os offsets contam pontos de código, como no motor.
    static func highlighted(_ note: EditorialNote) -> String {
        let scalars = Array(note.paragraphText.unicodeScalars)
        let lower = min(max(0, note.start), scalars.count), upper = min(max(lower, note.end), scalars.count)
        func s(_ r: Range<Int>) -> String { String(String.UnicodeScalarView(scalars[r])) }
        let marked = s(lower..<upper)
        return marked.isEmpty ? s(0..<scalars.count) : s(0..<lower) + "**" + marked + "**" + s(upper..<scalars.count)
    }

    private static func quote(_ text: String) -> String {
        text.split(separator: "\n", omittingEmptySubsequences: false).map { "> " + $0 }.joined(separator: "\n")
    }

    /// `states` traz a situação atual de cada registro; ausente conta como não localizado.
    static func markdown(_ notes: [EditorialNote], states: [String: EditorialNoteState], generatedAt: Date = Date()) -> String {
        let formatter = ISO8601DateFormatter()
        var out = ["# Pendências editoriais", "",
                   "Gerado pelo Lume em \(formatter.string(from: generatedAt)). \(notes.count) registro(s). "
                   + "Os textos “Minha contraproposta” e “Minha fundamentação” são do autor, sem alterações; "
                   + "o diagnóstico da IA é um parecer e pode estar equivocado. Nada aqui altera o manuscrito.", ""]
        let ordered = notes.sorted { ($0.book, $0.paragraph, $0.start, $0.id) < ($1.book, $1.paragraph, $1.start, $1.id) }
        for (index, note) in ordered.enumerated() {
            let state = states[note.id] ?? .notLocated
            let none = "Não registrado."
            out += ["---", "", "## \(index + 1). \(note.kind.fieldTitle) · \(note.category)", "",
                    "- **Obra:** \(note.book)",
                    "- **Capítulo:** \(note.chapter.isEmpty ? "não informado" : note.chapter)",
                    "- **Parágrafo:** \(note.paragraph)",
                    "- **Apontamento:** `\(note.id)` · \(note.category)",
                    "- **Decisão editorial humana:** \(note.humanDecision)",
                    "- **Classificação da avaliação:** \(note.assessmentTitle)",
                    "- **Situação do registro:** \(state.message)",
                    "- **Versão do manuscrito registrada:** `\(note.manuscriptSHA)`",
                    "- **Registrado em:** \(formatter.string(from: note.createdAt)) · **editado em:** \(formatter.string(from: note.updatedAt))",
                    "", "### Parágrafo original (ocorrência em negrito)", "", quote(highlighted(note)), "",
                    "### Avaliação da IA", "",
                    "- **Resultado:** \(note.aiResultLabel ?? none)",
                    "- **Diagnóstico:** \(note.aiDiagnosis ?? none)",
                    "- **Modelo:** \(note.aiModel ?? none)", "",
                    "**Justificativa da IA:**", "", note.aiExplanation.map(quote) ?? none, ""]
            if let suggestion = note.aiSuggestion, !suggestion.isEmpty {
                out += ["**Recomendação da IA (nada foi aplicado):**", "", quote(suggestion), ""]
            }
            out += ["### \(note.kind.fieldTitle)", "", quote(note.text), ""]
        }
        return out.joined(separator: "\n")
    }
}
