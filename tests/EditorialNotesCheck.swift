import Foundation

/// Contrapropostas e fundamentações: persistência, preservação após limpeza, exportação e desatualização.
/// Sem rede, sem API e sem Keychain.
///
///     swiftc app/Lume/Models.swift app/Lume/EditorialNotes.swift tests/EditorialNotesCheck.swift \
///            -o build/notas-editoriais-swift
///     build/notas-editoriais-swift          # a partir da raiz do repositório
@main
struct EditorialNotesCheck {
    static var failures = 0
    static func require(_ condition: Bool, _ message: String) {
        if !condition { failures += 1; print("FALHOU: " + message) }
    }

    static func note(_ id: String = "a1", kind: EditorialNote.Kind = .counterproposal, text: String,
                     sha: String = String(repeating: "a", count: 64)) -> EditorialNote {
        EditorialNote(id: id, kind: kind, text: text, createdAt: Date(timeIntervalSince1970: 1_000), updatedAt: Date(timeIntervalSince1970: 2_000),
                      book: "Livro Exemplo.pages", manuscriptSHA: sha, chapter: "Capítulo 2", paragraph: 14, category: "Concordância",
                      paragraphText: "Os vizinhos chegou tarde. 🙂 Depois todos saíram.", start: 4, end: 16,
                      humanDecision: "Erro confirmado", assessment: "possibleError", assessmentTitle: "Possível erro na decisão",
                      aiResultLabel: "Decisão contestada", aiDiagnosis: "Segundo a IA, há um desvio neste trecho.",
                      aiExplanation: "O verbo está no singular.\nO sujeito é plural.", aiSuggestion: nil, aiModel: "gpt-test")
    }

    static func main() throws {
        let manager = FileManager.default
        let support = manager.temporaryDirectory.appendingPathComponent("lume-notas-\(UUID().uuidString)", isDirectory: true)
        defer { try? manager.removeItem(at: support) }
        let folder = support.appendingPathComponent("Manifestacoes", isDirectory: true)
        try manager.createDirectory(at: folder, withIntermediateDirectories: true)
        let file = folder.appendingPathComponent(BookMemory.fileName("Livro Exemplo.pages"))

        // 1. Persistência e recuperação: o texto volta byte a byte (espaços, quebras, emoji, aspas).
        let exact = "  Discordo: “eles” chegou.\n\n  Segunda linha com 🙂 e espaços finais   "
        try EditorialNoteFile.save([note(text: exact), note("b2", kind: .rationale, text: "Fundamentação")], to: file)
        let back = try EditorialNoteFile.load(file)
        require(back.count == 2, "recarregou 2 registros")
        require(back.first { $0.id == "a1" }?.text == exact, "texto idêntico ao salvo")
        require(back.first { $0.id == "b2" }?.kind == .rationale, "tipo preservado")
        require(back.first?.createdAt == Date(timeIntervalSince1970: 1_000), "data preservada")
        require(try EditorialNoteFile.load(folder.appendingPathComponent("nada.json")).isEmpty, "arquivo ausente = vazio")

        // 2. Limpeza do Validador e dos resíduos não toca nos registros.
        let validator = support.appendingPathComponent("Validador/livro-exemplo", isDirectory: true)
        try manager.createDirectory(at: validator, withIntermediateDirectories: true)
        try Data("{}".utf8).write(to: validator.appendingPathComponent("validacoes-v5.json"))
        try manager.removeItem(at: validator.deletingLastPathComponent())          // redefinição do cache da IA
        let plan = StorageCleanup.plan(support: support, temporary: support.appendingPathComponent("tmp"), keepReport: nil, keepLog: nil)
        _ = plan.apply()
        require(manager.fileExists(atPath: file.path), "arquivo de manifestações sobrevive às limpezas")
        require(try EditorialNoteFile.load(file).first { $0.id == "a1" }?.text == exact, "texto intacto após limpezas")

        // 3. Arquivo ilegível é posto de lado, não sobrescrito.
        let broken = folder.appendingPathComponent("quebrado.json")
        try Data("{ não é json".utf8).write(to: broken)
        require((try? EditorialNoteFile.load(broken)) == nil, "arquivo ilegível falha")
        require(!manager.fileExists(atPath: broken.path), "ilegível movido")
        require((try? manager.contentsOfDirectory(atPath: folder.path))?.contains { $0.hasPrefix("quebrado.ilegivel-") } == true,
                "cópia do ilegível preservada")

        // 4. Exportação: parágrafo integral, ocorrência destacada, textos sem alteração.
        let n = note(text: exact)
        require(EditorialNoteExport.highlighted(n) == "Os v**izinhos cheg**ou tarde. 🙂 Depois todos saíram.",
                "ocorrência destacada por pontos de código: \(EditorialNoteExport.highlighted(n))")
        let md = EditorialNoteExport.markdown([n], states: ["a1": .current], generatedAt: Date(timeIntervalSince1970: 0))
        for needle in ["Livro Exemplo.pages", "Capítulo 2", "**Parágrafo:** 14", "`a1` · Concordância", "Erro confirmado",
                       "Possível erro na decisão", "O verbo está no singular.", "> O sujeito é plural.",
                       "> " + "  Discordo: “eles” chegou.", "> " + "  Segunda linha com 🙂 e espaços finais   ",
                       String(repeating: "a", count: 64), "Vigente"] {
            require(md.contains(needle), "exportação contém: \(needle)")
        }
        require(md.contains("### Minha contraproposta"), "título do campo")

        // 5. Desatualização: versão diferente nunca associa em silêncio a outro parágrafo.
        let sha = n.manuscriptSHA, other = String(repeating: "b", count: 64)
        func state(_ s: String, _ text: String?, _ a: String? = "possibleError", _ d: String? = "Erro confirmado") -> EditorialNoteState {
            .of(n, reportSHA: s, findingText: text, assessment: a, assessmentTitle: "Atual", decision: d)
        }
        require(state(sha, n.paragraphText) == .current, "vigente")
        require(state(sha, n.paragraphText, "outdated") == .assessmentChanged(from: "Possível erro na decisão", to: "Atual"), "avaliação mudou")
        require(state(sha, n.paragraphText, "possibleError", "Estilo") == .decisionChanged(from: "Erro confirmado", to: "Estilo"), "decisão mudou")
        require(state(other, n.paragraphText) == .manuscriptChanged(paragraphIntact: true), "outra versão, mesmo parágrafo")
        require(state(other, "Outro texto.") == .manuscriptChanged(paragraphIntact: false), "outra versão, parágrafo mudou")
        require(!state(other, "Outro texto.").canNavigate && !state(sha, nil).canNavigate, "sem navegação para parágrafo diferente")
        require(state(sha, nil) == .notLocated, "não localizado")
        let stale = EditorialNoteExport.markdown([n], states: ["a1": state(other, "Outro texto.")])
        require(stale.contains("Desatualizado") && stale.contains("o parágrafo mudou"), "exportação marca desatualizado")
        require(stale.contains("Depois todos saíram.") && !stale.contains("Outro texto."), "exportação usa o parágrafo registrado, não o atual")

        print(failures == 0 ? "OK: manifestações editoriais" : "\(failures) falha(s)")
        exit(failures == 0 ? 0 : 1)
    }
}
