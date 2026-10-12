import SwiftUI
import AppKit
import UniformTypeIdentifiers

// MARK: Contrapropostas e fundamentações: armazenamento na mesa e telas

extension ReviewStore {
    private var notesURL: URL? {
        guard let report else { return nil }
        return try? supportDirectory("Manifestacoes").appendingPathComponent(BookMemory.fileName(report.document))
    }

    func reloadEditorialNotes() {
        guard let url = notesURL else { editorialNotes = []; return }
        do { editorialNotes = try EditorialNoteFile.load(url) }
        catch {
            editorialNotes = []
            errorText = "O arquivo de contrapropostas estava ilegível e foi posto de lado (não apagado): \(error.localizedDescription)"
        }
    }

    func note(for id: String) -> EditorialNote? { editorialNotes.first { $0.id == id } }

    /// Campo a oferecer: o do registro existente ou o que a avaliação atual pede; `nil` nos demais casos.
    func noteKind(for finding: Finding) -> EditorialNote.Kind? {
        if let existing = note(for: finding.id) { return existing.kind }
        switch assessment(for: finding) {
        case .possibleError, .reviewRecommended: return .counterproposal
        case .inconclusive: return .rationale
        default: return nil
        }
    }

    /// Salva (ou edita) o registro. Atualiza o instantâneo do apontamento e da avaliação, mas nunca toca decisão,
    /// relatório, manuscrito nem cache da IA. Retorna `false` se não conseguiu gravar.
    @discardableResult
    func saveEditorialNote(for finding: Finding, kind: EditorialNote.Kind, text: String) -> Bool {
        guard let report, let url = notesURL, !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return false }
        let kept = note(for: finding.id)
        // Registro de outro parágrafo ou sem apontamento correspondente: só o texto muda; o instantâneo fica como estava.
        if var old = kept, !editorialNoteState(old).canNavigate {
            old.text = text; old.updatedAt = Date()
            return persist(editorialNotes.map { $0.id == old.id ? old : $0 }, to: url)
        }
        let item = secondOpinionItem(for: finding.id)
        let assessed = assessment(for: finding)
        let record = EditorialNote(
            id: finding.id, kind: kept?.kind ?? kind, text: text, createdAt: kept?.createdAt ?? Date(), updatedAt: Date(),
            book: report.document, manuscriptSHA: report.sha256, chapter: finding.chapter, paragraph: finding.paragraph,
            category: finding.category, paragraphText: finding.text, start: finding.start, end: finding.end,
            humanDecision: decision(for: finding).rawValue,
            assessment: (assessed ?? .notAnalyzed).rawValue, assessmentTitle: (assessed ?? .notAnalyzed).title,
            aiResultLabel: item?.resultLabel, aiDiagnosis: item.map { ValidatorV5Wording.existence($0.existence) },
            aiExplanation: item?.explanation, aiSuggestion: item?.suggestion, aiModel: item?.model)
        var next = editorialNotes.filter { $0.id != record.id } + [record]
        next.sort { ($0.paragraph, $0.start, $0.id) < ($1.paragraph, $1.start, $1.id) }
        return persist(next, to: url)
    }

    private func persist(_ next: [EditorialNote], to url: URL) -> Bool {
        do { try EditorialNoteFile.save(next, to: url) }
        catch { errorText = "Não foi possível salvar a manifestação: \(error.localizedDescription)"; return false }
        editorialNotes = next
        return true
    }

    func deleteEditorialNote(_ id: String) {
        guard let url = notesURL else { return }
        let next = editorialNotes.filter { $0.id != id }
        do { try EditorialNoteFile.save(next, to: url) }
        catch { errorText = "Não foi possível excluir a manifestação: \(error.localizedDescription)"; return }
        editorialNotes = next
    }

    func editorialNoteState(_ note: EditorialNote) -> EditorialNoteState {
        let finding = report?.findings.first { $0.id == note.id }
        let assessed = finding.flatMap { assessment(for: $0) } ?? (finding == nil ? nil : .notAnalyzed)
        return EditorialNoteState.of(note, reportSHA: report?.sha256 ?? "", findingText: finding?.text,
                                     assessment: assessed?.rawValue, assessmentTitle: assessed?.title,
                                     decision: finding.map { decision(for: $0).rawValue })
    }

    /// Salva um .md escolhido no painel padrão do macOS. Nada é enviado a nenhum serviço.
    func exportEditorialNotes(ids: Set<String>) {
        let chosen = editorialNotes.filter { ids.contains($0.id) }
        guard !chosen.isEmpty else { return }
        let panel = NSSavePanel()
        panel.allowedContentTypes = [UTType(filenameExtension: "md") ?? .plainText]
        let book = report.map { BookMemory.bookName($0.document) } ?? "livro"
        panel.nameFieldStringValue = "pendencias-editoriais-\(book).md"
        guard panel.runModal() == .OK, let url = panel.url else { return }
        let states = Dictionary(uniqueKeysWithValues: chosen.map { ($0.id, editorialNoteState($0)) })
        do {
            try EditorialNoteExport.markdown(chosen, states: states).write(to: url, atomically: true, encoding: .utf8)
            status = "\(chosen.count) registro(s) exportado(s) para \(url.lastPathComponent)."
        } catch { errorText = error.localizedDescription }
    }

    func confirmDeleteEditorialNote(_ id: String) {
        let alert = NSAlert()
        alert.messageText = "Excluir este registro?"
        alert.informativeText = "O texto que você escreveu será apagado. A decisão e o manuscrito não mudam."
        alert.alertStyle = .warning
        alert.addButton(withTitle: "Excluir"); alert.addButton(withTitle: "Cancelar")
        if alert.runModal() == .alertFirstButtonReturn { deleteEditorialNote(id) }
    }
}

/// Editor do registro: usado no cartão do inspetor e na lista das Pendências Editoriais.
@MainActor
struct EditorialNoteEditor: View {
    @EnvironmentObject private var store: ReviewStore
    let finding: Finding
    let kind: EditorialNote.Kind
    @State private var draft = ""
    @State private var editing = false

    var body: some View {
        let note = store.note(for: finding.id)
        let isEditing = note == nil || editing
        VStack(alignment: .leading, spacing: 8) {
            if let note, !isEditing {
                Text(note.text).font(LumeFont.ui(12)).textSelection(.enabled).fixedSize(horizontal: false, vertical: true)
                    .padding(8).frame(maxWidth: .infinity, alignment: .leading)
                    .background(RoundedRectangle(cornerRadius: LumeRadius.small).fill(LumeTheme.raised.opacity(0.5)))
                let state = store.editorialNoteState(note)
                if !state.isCurrent {
                    Label(state.message, systemImage: "exclamationmark.triangle").font(LumeFont.ui(11)).foregroundStyle(LumeTheme.amber)
                        .fixedSize(horizontal: false, vertical: true)
                }
                HStack {
                    Spacer()
                    Button("Excluir") { store.confirmDeleteEditorialNote(finding.id) }.buttonStyle(LumeButtonStyle())
                    Button("Editar") { draft = note.text; editing = true }.buttonStyle(LumeButtonStyle(kind: .soft))
                }
            } else {
                TextEditor(text: $draft).font(LumeFont.ui(12)).frame(minHeight: 96)
                    .scrollContentBackground(.hidden).padding(6)
                    .background(RoundedRectangle(cornerRadius: LumeRadius.small).fill(LumeTheme.raised.opacity(0.5)))
                    .overlay(RoundedRectangle(cornerRadius: LumeRadius.small).strokeBorder(LumeTheme.line))
                HStack {
                    Spacer()
                    if editing { Button("Cancelar") { editing = false }.buttonStyle(LumeButtonStyle()) }
                    Button("Salvar") { if store.saveEditorialNote(for: finding, kind: kind, text: draft) { editing = false } }
                        .buttonStyle(LumeButtonStyle(kind: .primary))
                        .disabled(draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || draft == note?.text)
                }
            }
        }
    }
}

/// Inspetor: logo abaixo da avaliação da IA, quando ela pede uma manifestação do autor.
@MainActor
struct EditorialNoteSection: View {
    @EnvironmentObject private var store: ReviewStore
    let finding: Finding

    var body: some View {
        if let kind = store.noteKind(for: finding) {
            VStack(alignment: .leading, spacing: 8) {
                Kicker(title: kind.fieldTitle)
                Text(kind == .counterproposal
                     ? "Por que você discorda do diagnóstico ou considera a decisão defensável."
                     : "Sua leitura do trecho, as razões da decisão e o contexto que importa.")
                    .font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary)
                EditorialNoteEditor(finding: finding, kind: kind)
                Text("Fica só neste Mac. Não altera a sua decisão nem o manuscrito e não aciona a IA.")
                    .font(LumeFont.ui(10)).foregroundStyle(LumeTheme.tertiary)
            }.id(finding.id)
        }
    }
}

/// Mesa › Pendências Editoriais: todos os registros do livro aberto.
@MainActor
struct EditorialNotesPanel: View {
    @EnvironmentObject private var store: ReviewStore
    @State private var filter: EditorialNote.Kind?
    @State private var selected: Set<String> = []
    @State private var expanded: String?

    private var shown: [EditorialNote] { store.editorialNotes.filter { filter == nil || $0.kind == filter } }

    var body: some View {
        let items = shown
        ScrollView {
            VStack(alignment: .leading, spacing: 10) {
                Text("Contrapropostas e fundamentações que você escreveu sobre as avaliações da IA. Ficam guardadas à parte do cache do Validador.")
                    .font(LumeFont.ui(11.5)).foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
                Picker("Tipo", selection: $filter) {
                    Text("Todos · \(store.editorialNotes.count)").tag(EditorialNote.Kind?.none)
                    ForEach(EditorialNote.Kind.allCases) { kind in
                        Text("\(kind.plural) · \(store.editorialNotes.filter { $0.kind == kind }.count)").tag(EditorialNote.Kind?.some(kind))
                    }
                }.pickerStyle(.menu).labelsHidden()
                HStack {
                    Button("Selecionar todos") { selected.formUnion(items.map(\.id)) }.buttonStyle(.borderless)
                    Button("Limpar seleção") { selected.subtract(items.map(\.id)) }.buttonStyle(.borderless)
                    Spacer()
                    Button("Exportar \(selected.intersection(items.map(\.id)).count) (.md)") {
                        store.exportEditorialNotes(ids: selected.intersection(items.map(\.id)))
                    }.buttonStyle(LumeButtonStyle(kind: .primary)).disabled(selected.intersection(items.map(\.id)).isEmpty)
                }.font(LumeFont.ui(11))
                Divider().overlay(LumeTheme.line)
                if items.isEmpty {
                    Text("Nenhum registro ainda. Eles aparecem aqui quando você escreve “Minha contraproposta” ou “Minha fundamentação” no inspetor de um apontamento.")
                        .font(LumeFont.ui(12)).foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
                }
                ForEach(items) { note in row(note) }
            }.padding(14).frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private func row(_ note: EditorialNote) -> some View {
        let state = store.editorialNoteState(note)
        let finding = store.report?.findings.first { $0.id == note.id }
        return VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .top, spacing: 8) {
                Toggle("", isOn: Binding(get: { selected.contains(note.id) },
                                         set: { if $0 { selected.insert(note.id) } else { selected.remove(note.id) } }))
                    .toggleStyle(.checkbox).labelsHidden().accessibilityLabel("Selecionar para exportar")
                VStack(alignment: .leading, spacing: 3) {
                    Text("\(note.kind.fieldTitle) · § \(note.paragraph) · \(note.category)")
                        .font(LumeFont.ui(10.5)).foregroundStyle(LumeTheme.secondary)
                    Text(note.text).font(LumeFont.ui(12)).lineLimit(expanded == note.id ? nil : 3)
                        .fixedSize(horizontal: false, vertical: true)
                    if !state.isCurrent {
                        Label(state.message, systemImage: "exclamationmark.triangle").font(LumeFont.ui(10.5))
                            .foregroundStyle(LumeTheme.amber).fixedSize(horizontal: false, vertical: true)
                    }
                    HStack {
                        Button(expanded == note.id ? "Recolher" : "Ver e editar") { expanded = expanded == note.id ? nil : note.id }
                        if state.canNavigate { Button("Ir ao apontamento") { store.goToFinding(note.id) } }
                        Button("Excluir") { store.confirmDeleteEditorialNote(note.id) }
                    }.buttonStyle(.borderless).font(LumeFont.ui(11))
                    if expanded == note.id {
                        if let finding { EditorialNoteEditor(finding: finding, kind: note.kind).padding(.top, 4) }
                        else { Text("O apontamento não está no relatório aberto; o registro só pode ser exportado ou excluído.")
                            .font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary) }
                    }
                }
            }
        }.padding(8).frame(maxWidth: .infinity, alignment: .leading)
            .background(RoundedRectangle(cornerRadius: LumeRadius.small).fill(LumeTheme.raised.opacity(0.5)))
    }
}
