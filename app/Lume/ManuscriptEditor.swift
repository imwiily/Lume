import Foundation
import CryptoKit

/// Uma correção gravada no manuscrito a pedido do autor. Posições em pontos de código
/// Unicode, relativas ao parágrafo como estava no relatório.
struct AppliedEdit: Codable, Equatable {
    let finding: String
    let paragraph: Int
    let start: Int
    let end: Int
    let before: String
    let after: String
    let date: Date
}

/// Histórico das correções de um relatório: liga o arquivo analisado ao arquivo atual.
struct EditLog: Codable {
    var schemaVersion = 1
    /// SHA-256 do manuscrito analisado (o do relatório).
    let origem: String
    /// SHA-256 do manuscrito depois da última correção.
    var atual: String
    let documento: String
    /// Cópia do manuscrito feita antes da primeira correção.
    let copia: String
    var edits: [AppliedEdit] = []

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case origem, atual, documento, copia, edits
    }
}

/// O que pedir ao Pages: posições iniciando em 1, inclusivas, no parágrafo atual.
struct EditPlan: Equatable {
    let first: Int
    let last: Int
    let replacement: String
    let currentText: String
    let resultText: String
}

enum ManuscriptEditor {
    static let limit = 500

    static func sha256(_ url: URL) throws -> String {
        SHA256.hash(data: try Data(contentsOf: url)).map { String(format: "%02x", $0) }.joined()
    }

    private static func string(_ scalars: ArraySlice<Unicode.Scalar>) -> String {
        var view = String.UnicodeScalarView()
        view.append(contentsOf: scalars)
        return String(view)
    }

    /// Texto atual do parágrafo: o do relatório com as correções já gravadas.
    static func currentText(_ original: String, edits: [AppliedEdit]) -> String {
        var scalars = Array(original.unicodeScalars)
        for edit in edits.sorted(by: { $0.start > $1.start }) where edit.start >= 0 && edit.end <= scalars.count && edit.start <= edit.end {
            scalars.replaceSubrange(edit.start..<edit.end, with: Array(edit.after.unicodeScalars))
        }
        return string(scalars[...])
    }

    /// Edição do parágrafo inteiro pedida pelo autor: reduz o texto novo à menor troca
    /// contínua em relação ao parágrafo atual (o resto, com a formatação, fica intocado) e
    /// devolve essa troca em posições do relatório. Uma troca que toca correção já gravada é recusada.
    static func paragraphChange(text: String, edits: [AppliedEdit], newText: String) throws -> (start: Int, end: Int, before: String, after: String) {
        let original = Array(text.unicodeScalars)
        let current = Array(currentText(text, edits: edits).unicodeScalars)
        let new = Array(newText.unicodeScalars)
        guard current != new else { throw FonteError.message("O parágrafo não foi alterado.") }
        var prefix = 0
        while prefix < min(current.count, new.count), current[prefix] == new[prefix] { prefix += 1 }
        var suffix = 0
        while suffix < min(current.count, new.count) - prefix,
              current[current.count - 1 - suffix] == new[new.count - 1 - suffix] { suffix += 1 }
        let lower = prefix, upper = current.count - suffix
        var shift = 0
        for edit in edits.sorted(by: { $0.start < $1.start }) {
            let editLower = edit.start + shift, editUpper = editLower + edit.after.unicodeScalars.count
            if max(lower, editLower) < min(upper, editUpper) || (lower == upper && editLower < lower && lower < editUpper) {
                throw FonteError.message("A edição mexe num trecho já alterado por outra correção. Analise o manuscrito novamente para continuar neste ponto.")
            }
            if editUpper <= lower { shift += edit.after.unicodeScalars.count - (edit.end - edit.start) }
        }
        let start = lower - shift, end = upper - shift
        guard start >= 0, end >= start, end <= original.count else {
            throw FonteError.message("A edição não cabe no parágrafo do relatório.")
        }
        return (start, end, string(original[start..<end]), string(new[lower..<(new.count - suffix)]))
    }

    /// Traduz o trecho do relatório para o parágrafo atual. `edits` são as correções já
    /// gravadas neste parágrafo; um trecho que toca uma delas é recusado.
    static func plan(text: String, start: Int, end: Int, replacement: String, edits: [AppliedEdit]) throws -> EditPlan {
        let original = Array(text.unicodeScalars)
        guard start >= 0, end >= start, end <= original.count else {
            throw FonteError.message("O trecho deste alerta não cabe no parágrafo.")
        }
        guard end - start <= limit, replacement.unicodeScalars.count <= limit else {
            throw FonteError.message("Trecho ou correção com mais de \(limit) caracteres: edite este ponto diretamente no Pages.")
        }
        guard !replacement.unicodeScalars.contains(where: { $0.value < 0x20 || $0.value == 0x2028 || $0.value == 0x2029 || $0.value == 0xFFFC }) else {
            throw FonteError.message("A correção não pode conter quebras de linha nem caracteres de controle.")
        }
        guard replacement.unicodeScalars.elementsEqual(original[start..<end]) == false else {
            throw FonteError.message("A correção é igual ao trecho atual.")
        }
        for edit in edits where max(start, edit.start) < min(end, edit.end) || start == edit.start || end == edit.end
            || (start == end && edit.start < start && start < edit.end) {
            throw FonteError.message("Este trecho já foi alterado por outra correção. Analise o manuscrito novamente para continuar neste ponto.")
        }
        let shift = edits.filter { $0.end <= start }.reduce(0) {
            $0 + $1.after.unicodeScalars.count - ($1.end - $1.start)
        }
        let current = Array(currentText(text, edits: edits).unicodeScalars)
        var lower = start + shift, upper = end + shift
        var new = Array(replacement.unicodeScalars)
        guard lower >= 0, upper <= current.count, !current.isEmpty else {
            throw FonteError.message("O trecho deste alerta não cabe no parágrafo atual.")
        }
        // O Pages precisa de ao menos um caractere para receber o texto novo.
        if lower == upper {
            if lower > 0 { lower -= 1; new.insert(current[lower], at: 0) }
            else { new.append(current[upper]); upper += 1 }
        }
        var result = current
        result.replaceSubrange(lower..<upper, with: new)
        guard !string(result[...]).trimmingCharacters(in: .whitespaces).isEmpty else {
            throw FonteError.message("A correção deixaria o parágrafo vazio: faça essa alteração diretamente no Pages.")
        }
        return EditPlan(first: lower + 1, last: upper, replacement: string(new[...]),
                        currentText: string(current[...]), resultText: string(result[...]))
    }

    /// Troca um caractere de cada vez: o Pages trata um intervalo como lista e repetiria o
    /// texto novo em cada posição. O texto novo herda a formatação do primeiro caractere.
    static let script = """
    -- Textos chegam como códigos Unicode: passados como texto, o osascript decompõe os
    -- acentos (“á” viraria “a” + acento combinado) e o resultado não seria o pedido.
    on texto(codigos)
        if codigos is "" then return ""
        set AppleScript's text item delimiters to ","
        set partes to text items of codigos
        set AppleScript's text item delimiters to ""
        set lista to {}
        repeat with parte in partes
            set end of lista to (parte as integer)
        end repeat
        return character id lista
    end texto

    on run argv
        set docPath to item 1 of argv
        set n to (item 2 of argv) as integer
        set a to (item 3 of argv) as integer
        set b to (item 4 of argv) as integer
        set novo to texto(item 5 of argv)
        set esperado to texto(item 6 of argv)
        -- A referência é criada fora do bloco do Pages: só assim o app, que roda isolado,
        -- recebe permissão para abrir o arquivo no lugar (senão abre uma cópia sem título).
        set arquivo to (POSIX file docPath) as alias
        set alvo to POSIX path of arquivo
        tell application id "com.apple.Pages"
            set aberto to false
            repeat with x in documents
                try
                    if (POSIX path of ((file of x) as alias)) is alvo then set aberto to true
                end try
            end repeat
            set d to open arquivo
            if d is missing value then error "LUME_NAO_ABRIU"
            try
                if (POSIX path of ((file of d) as alias)) is not alvo then error "LUME_NAO_ABRIU"
                if aberto and (modified of d) then error "LUME_MODIFICADO"
                tell d
                    considering case, diacriticals, hyphens, punctuation and white space
                        if ((paragraph n of body text) as text) is not esperado then error "LUME_DIFERENTE"
                    end considering
                    repeat with k from b to (a + 1) by -1
                        set character k of paragraph n of body text to ""
                    end repeat
                    set character a of paragraph n of body text to novo
                end tell
                save d
            on error m
                if not aberto then close d saving no
                error m
            end try
            if not aberto then close d saving no
        end tell
    end run
    """

    /// Executa a troca no Pages. Roda fora da fila principal; lança a mensagem para o autor.
    static func runPages(document: URL, paragraph: Int, plan: EditPlan) async throws {
        // Dentro do parágrafo o Pages usa U+2028 onde o relatório mostra quebra de linha.
        let expected = plan.currentText.replacingOccurrences(of: "\n", with: "\u{2028}")
        func codes(_ text: String) -> String { text.unicodeScalars.map { String($0.value) }.joined(separator: ",") }
        let arguments = ["-e", script, document.path, String(paragraph), String(plan.first), String(plan.last),
                         codes(plan.replacement), codes(expected)]
        let (status, output): (Int32, String) = try await withCheckedThrowingContinuation { continuation in
            DispatchQueue.global(qos: .userInitiated).async {
                do {
                    let task = Process()
                    task.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
                    task.arguments = arguments
                    let pipe = Pipe()
                    task.standardError = pipe
                    task.standardOutput = FileHandle.nullDevice
                    task.standardInput = FileHandle.nullDevice
                    try task.run()
                    let data = pipe.fileHandleForReading.readDataToEndOfFile()
                    task.waitUntilExit()
                    continuation.resume(returning: (task.terminationStatus, String(decoding: data, as: UTF8.self)))
                } catch { continuation.resume(throwing: error) }
            }
        }
        guard status != 0 else { return }
        if output.contains("LUME_MODIFICADO") {
            throw FonteError.message("O documento está aberto no Pages com alterações não salvas. Salve ou feche o documento e tente de novo.")
        }
        if output.contains("LUME_NAO_ABRIU") {
            throw FonteError.message("O Pages não conseguiu abrir este arquivo para edição. Feche no Pages qualquer janela sem título que tenha surgido, sem salvar. Nada foi alterado.")
        }
        if output.contains("LUME_DIFERENTE") {
            throw FonteError.message("O parágrafo no Pages não corresponde ao do relatório (pode haver imagem, tabela ou nota ancorada nele). Nada foi alterado; corrija este ponto diretamente no Pages.")
        }
        if output.contains("-1743") {
            throw FonteError.message("O Lume não tem permissão para controlar o Pages. Autorize em Ajustes do Sistema → Privacidade e Segurança → Automação.")
        }
        if output.contains("-1728") || output.contains("-2700") || output.contains("-1708") {
            throw FonteError.message("O Pages não concluiu a correção. Se o documento estiver aberto, feche-o sem salvar.\n\n\(output.suffix(400))")
        }
        throw FonteError.message("Não foi possível usar o Pages para gravar a correção. Confira se o Pages está instalado.\n\n\(output.suffix(400))")
    }
}
