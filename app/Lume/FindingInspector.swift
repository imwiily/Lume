import SwiftUI

/// Inspetor editorial: o que o Lume encontrou, por quê, o que sugere, o que o editor pode fazer no
/// arquivo (Pages) e a decisão, que é sempre humana. Confiança é indício heurístico, não probabilidade.
@MainActor
struct FindingInspector: View {
    @EnvironmentObject private var store: ReviewStore
    let finding: Finding
    @State private var correction = ""
    /// Editar parágrafo: opção do autor para trocar o parágrafo todo em vez do trecho destacado.
    @State private var editingParagraph = false
    @State private var paragraphDraft = ""

    private var severity: FindingSeverity? { finding.severity.flatMap(FindingSeverity.init(rawValue:)) }
    private var currentIndex: Int? { store.filteredFindings.firstIndex { $0.id == finding.id } }

    /// O destino dado pela política: o que este alerta pede do editor.
    private var destinationNote: (text: String, symbol: String)? {
        if finding.isBlocking { return ("Impeditivo: decida antes de encerrar a revisão.", "lock.fill") }
        if finding.destination == .informacao {
            return ("Observação: não pede decisão nem impede o encerramento. Decida só se quiser.", "eye")
        }
        return nil
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            header
            reasonSection
            if let suggestion = finding.suggestion { suggestionView(suggestion) }
            if let related = finding.related, !related.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    Kicker(title: "Evidências relacionadas")
                    ForEach(Array(related.enumerated()), id: \.offset) { _, evidence in evidenceView(evidence) }
                }
            }
            manuscriptActions
            if let conflict = store.decisionConflicts[finding.id] { conflictNote(conflict) }
            decisionSection
            details
            Text("Lume encontra. Lume explica. **O editor decide.**")
                .font(LumeFont.ui(11)).foregroundStyle(LumeTheme.tertiary).frame(maxWidth: .infinity, alignment: .center)
                .padding(.top, 4)
        }.padding(18).frame(maxWidth: .infinity, alignment: .leading)
            .task(id: finding.id) {
                correction = finding.suggestion ?? finding.segments.marked
                editingParagraph = false
            }
    }

    // MARK: Classificação

    private var header: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                SeverityTag(severity: severity)
                Text(finding.moduleTitle).font(LumeFont.ui(10.5)).foregroundStyle(LumeTheme.secondary).lineLimit(1)
                Spacer(minLength: 4)
                if let index = currentIndex {
                    Text("\(index + 1) de \(store.filteredFindings.count)").font(LumeFont.ui(10.5)).monospacedDigit()
                        .foregroundStyle(LumeTheme.secondary)
                }
                Button { move(-1) } label: { Image(systemName: "chevron.up") }
                    .help("Alerta anterior (⌘[)").accessibilityLabel("Alerta anterior")
                    .disabled(currentIndex == nil || currentIndex == 0)
                Button { move(1) } label: { Image(systemName: "chevron.down") }
                    .help("Próximo alerta (⌘])").accessibilityLabel("Próximo alerta")
                    .disabled(currentIndex == nil || currentIndex == store.filteredFindings.count - 1)
            }.buttonStyle(.borderless)
            Text(finding.category).font(LumeFont.display(20, weight: .semibold)).fixedSize(horizontal: false, vertical: true)
            if let note = destinationNote {
                Label(note.text, systemImage: note.symbol).font(LumeFont.ui(11))
                    .foregroundStyle(finding.isBlocking ? LumeTheme.error : LumeTheme.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Text("\(finding.chapter) · § \(finding.paragraph)").font(LumeFont.ui(11.5)).foregroundStyle(LumeTheme.secondary)
                .textSelection(.enabled)
            Text("“\(finding.segments.marked)”").font(LumeFont.display(15)).italic()
                .padding(.horizontal, 10).padding(.vertical, 7).frame(maxWidth: .infinity, alignment: .leading)
                .background(RoundedRectangle(cornerRadius: LumeRadius.medium).fill(LumeTheme.glow.opacity(0.6)))
                .overlay(alignment: .leading) { Rectangle().fill(LumeTheme.glowLine).frame(width: 2) }
                .textSelection(.enabled)
                .accessibilityLabel("Trecho: \(finding.segments.marked)")
        }
    }

    private var reasonSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Kicker(title: "Por que acendemos esta luz", color: LumeTheme.amber, flame: true)
            Text(finding.reason).font(LumeFont.ui(13)).lineSpacing(3).textSelection(.enabled)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func suggestionView(_ suggestion: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Kicker(title: "Sugestão")
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(finding.segments.marked).strikethrough(color: LumeTheme.rose).foregroundStyle(LumeTheme.secondary)
                Image(systemName: "arrow.right").font(.system(size: 10)).foregroundStyle(LumeTheme.secondary)
                Text(suggestion.isEmpty ? "remover o trecho" : suggestion).italic(suggestion.isEmpty).fontWeight(.semibold)
            }.font(LumeFont.display(15)).textSelection(.enabled)
                .padding(.horizontal, 10).padding(.vertical, 7).frame(maxWidth: .infinity, alignment: .leading)
                .background(RoundedRectangle(cornerRadius: LumeRadius.medium).fill(LumeTheme.raised))
                .overlay(RoundedRectangle(cornerRadius: LumeRadius.medium).strokeBorder(LumeTheme.line))
                .accessibilityElement(children: .combine)
                .accessibilityLabel(suggestion.isEmpty ? "Sugestão: remover o trecho destacado."
                                    : "Sugestão para o trecho destacado: \(suggestion)")
        }
    }

    private func evidenceView(_ evidence: TextEvidence) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text("\(evidence.document == "original" ? "Original" : "Manuscrito atual") · \(evidence.chapter) · § \(evidence.paragraph)")
                .font(LumeFont.ui(10.5)).foregroundStyle(LumeTheme.secondary)
            Text(evidence.text).font(LumeFont.display(13.5)).lineSpacing(3).textSelection(.enabled)
                .fixedSize(horizontal: false, vertical: true)
        }.padding(10).frame(maxWidth: .infinity, alignment: .leading)
            .background(RoundedRectangle(cornerRadius: LumeRadius.medium).fill(LumeTheme.raised))
            .overlay(RoundedRectangle(cornerRadius: LumeRadius.medium).strokeBorder(LumeTheme.line))
    }

    // MARK: Ações no manuscrito (Pages)

    @ViewBuilder private var manuscriptActions: some View {
        if store.canEditManuscript {
            VStack(alignment: .leading, spacing: 8) {
                Kicker(title: "Ações no manuscrito (Pages)")
                correctionView
            }
        } else {
            Label(store.documentURL?.pathExtension.lowercased() == "docx"
                  ? "Documento Word: somente leitura. Registre a avaliação abaixo."
                  : "Somente leitura: abra o manuscrito .pages no Lume para corrigir no arquivo.",
                  systemImage: "lock")
                .font(LumeFont.ui(11.5)).foregroundStyle(LumeTheme.secondary)
        }
    }

    /// Correção do trecho destacado, gravada no documento do Pages a pedido do autor.
    @ViewBuilder private var correctionView: some View {
        if let edit = store.appliedEdit(for: finding) {
            VStack(alignment: .leading, spacing: 6) {
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Image(systemName: "checkmark.circle.fill").foregroundStyle(LumeTheme.sage)
                    Text(edit.before.isEmpty ? "inserção" : edit.before).strikethrough(!edit.before.isEmpty, color: LumeTheme.rose)
                        .foregroundStyle(LumeTheme.secondary)
                    Image(systemName: "arrow.right").font(.system(size: 10)).foregroundStyle(LumeTheme.secondary)
                    Text(edit.after.isEmpty ? "trecho removido" : edit.after).italic(edit.after.isEmpty).fontWeight(.semibold)
                    Spacer(minLength: 4)
                    Button { store.revealBackup() } label: { Image(systemName: "clock.arrow.circlepath") }
                        .buttonStyle(.borderless).help("Mostrar a cópia anterior às correções")
                        .accessibilityLabel("Mostrar a cópia anterior às correções")
                }.font(LumeFont.display(14)).textSelection(.enabled)
                Text("Gravado no arquivo; analise novamente para ver o manuscrito atualizado.")
                    .font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary)
            }
        } else if editingParagraph {
            VStack(alignment: .leading, spacing: 8) {
                TextField("Parágrafo", text: $paragraphDraft, axis: .vertical)
                    .textFieldStyle(.roundedBorder).font(LumeFont.display(14)).lineLimit(3...12)
                    .accessibilityLabel("Texto do parágrafo inteiro")
                Text("Só o que você mudar é gravado; o restante do parágrafo e a formatação ficam como estão.")
                    .font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
                HStack(spacing: 8) {
                    Button { editingParagraph = false } label: { Label("Editar só o trecho", systemImage: "text.cursor") }
                        .buttonStyle(LumeButtonStyle(kind: .soft))
                        .help("Volta a trocar apenas o trecho destacado")
                    Spacer(minLength: 4)
                    Button { store.applyParagraphEdit(paragraphDraft, for: finding) } label: {
                        Label("Gravar parágrafo", systemImage: "pencil.line")
                    }.buttonStyle(LumeButtonStyle(kind: .primary))
                        .disabled(store.isBusy || paragraphDraft == store.currentParagraph(for: finding))
                        .help("Grava no arquivo do Pages a parte do parágrafo que você alterou. Uma cópia do original é guardada antes da primeira correção.")
                }
            }
        } else {
            VStack(alignment: .leading, spacing: 8) {
                TextField("Texto que substitui o trecho destacado (vazio remove o trecho)", text: $correction)
                    .textFieldStyle(.roundedBorder).font(LumeFont.display(14))
                    .accessibilityLabel("Correção para o trecho destacado")
                HStack(spacing: 8) {
                    Button { store.applyCorrection(correction, for: finding) } label: {
                        Label("Corrigir no manuscrito", systemImage: "pencil.line")
                    }.buttonStyle(LumeButtonStyle(kind: .primary)).disabled(!canCorrect)
                        .help("Troca só o trecho destacado, no próprio arquivo do Pages. Uma cópia do original é guardada antes da primeira correção.")
                    Button {
                        paragraphDraft = store.currentParagraph(for: finding)
                        editingParagraph = true
                    } label: { Label("Editar parágrafo", systemImage: "text.alignleft") }
                        .buttonStyle(LumeButtonStyle())
                        .help("Abre o parágrafo inteiro para edição, em vez de só o trecho destacado")
                }
                if store.editCount(inParagraph: finding.paragraph) > 0 {
                    Text("Este parágrafo já recebeu correções; o texto da página é o da análise. A troca vale só para o trecho destacado.")
                        .font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
                }
            }
        }
    }
    private var canCorrect: Bool { !store.isBusy && correction != finding.segments.marked }

    // MARK: Decisão editorial

    private var decisionSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Kicker(title: "Decisão editorial")
                Spacer()
                Text("Sua avaliação").font(LumeFont.ui(10.5)).foregroundStyle(LumeTheme.amber)
            }
            LazyVGrid(columns: [GridItem(.flexible(), spacing: 6), GridItem(.flexible(), spacing: 6)], spacing: 6) {
                ForEach(ReviewDecision.allCases) { decision in
                    DecisionChip(decision: decision, selected: store.decision(for: finding) == decision) {
                        store.setDecision(decision, for: finding)
                    }
                }
            }.disabled(store.isBusy)
            HStack {
                Text("⌘1–⌘7 escolhem a decisão.").font(LumeFont.ui(10.5)).foregroundStyle(LumeTheme.tertiary)
                Spacer()
                Button { confirm() } label: { Label("Confirmar", systemImage: "checkmark") }
                    .buttonStyle(LumeButtonStyle())
                    .disabled(store.decision(for: finding) == .pending)
                    .help("Confirma a sua avaliação e passa para o próximo alerta")
            }
        }
    }

    /// O motor juntou neste alerta ocorrências equivalentes que tinham decisões diferentes. O Lume não
    /// escolhe entre elas; a divergência fica registrada mesmo depois da sua decisão.
    private func conflictNote(_ entries: [String]) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Label("Decisões anteriores divergentes", systemImage: "exclamationmark.triangle")
                .font(LumeFont.ui(12, weight: .semibold)).foregroundStyle(LumeTheme.amber)
            Text("Este alerta reúne o mesmo fenômeno apontado antes por outra fonte, e as decisões tomadas não coincidem. "
                 + "Nenhuma foi escolhida automaticamente.")
                .font(LumeFont.ui(11.5)).foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
            ForEach(entries, id: \.self) { entry in
                Text("• \(entry)").font(LumeFont.ui(11.5)).textSelection(.enabled).fixedSize(horizontal: false, vertical: true)
            }
        }.padding(10).frame(maxWidth: .infinity, alignment: .leading)
            .background(RoundedRectangle(cornerRadius: LumeRadius.medium).stroke(LumeTheme.amber.opacity(0.5)))
    }

    // MARK: Detalhes

    private var details: some View {
        VStack(alignment: .leading, spacing: 8) {
            DisclosureGroup("Detalhes técnicos") {
                VStack(alignment: .leading, spacing: 4) {
                    if let confidence = finding.confidence {
                        Text("Força do indício: \(confidence). É um indício heurístico, não uma probabilidade; a classificação é automática e depende da sua decisão.")
                    }
                    Text("Etapa: \(finding.moduleTitle) · Classificação: \(finding.severityTitle)")
                    if let rule = finding.rule { Text("Regra: \(rule)") }
                    if let detectores = finding.detectores, detectores.count > 1 {
                        Text("Também apontado por: \(detectores.dropFirst().joined(separator: ", "))")
                    }
                    Text("Prioridade: \(finding.priority)")
                    Text("Origem: \(finding.source)")
                }.font(LumeFont.ui(11)).frame(maxWidth: .infinity, alignment: .leading).padding(.top, 6)
                    .textSelection(.enabled).fixedSize(horizontal: false, vertical: true)
            }
            if let report = store.report, !report.warnings.isEmpty {
                DisclosureGroup("Sobre esta análise · \(report.warnings.count) avisos") {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(Array(report.warnings.enumerated()), id: \.offset) { _, warning in
                            Text(warning).font(LumeFont.ui(11)).lineSpacing(2).fixedSize(horizontal: false, vertical: true)
                        }
                        Text("As avaliações registradas não treinam o analisador automaticamente.").font(LumeFont.ui(11))
                    }.padding(.top, 6)
                }
            }
        }.font(LumeFont.ui(11.5)).foregroundStyle(LumeTheme.secondary)
    }

    private func move(_ offset: Int) {
        guard let index = currentIndex else { return }
        let target = index + offset
        if store.filteredFindings.indices.contains(target) { store.selectedID = store.filteredFindings[target].id }
    }

    /// A decisão já foi salva ao ser escolhida; confirmar passa ao alerta seguinte da lista.
    /// Usa a ordem do relatório para seguir em frente mesmo quando o filtro esconde o alerta atual.
    private func confirm() {
        let all = store.report?.findings ?? []
        guard let position = all.firstIndex(where: { $0.id == finding.id }) else { return }
        let visible = Set(store.filteredFindings.map(\.id))
        if let next = all[(position + 1)...].first(where: { visible.contains($0.id) }) {
            store.selectedID = next.id
        } else {
            store.status = "Este era o último alerta da lista."
        }
    }
}

/// Uma das decisões de `ReviewDecision`, com atalho ⌘1–⌘7.
struct DecisionChip: View {
    let decision: ReviewDecision
    let selected: Bool
    let action: () -> Void

    private var fill: Color {
        guard selected else { return LumeTheme.raised }
        return decision == .pending ? LumeTheme.glow.opacity(0.7) : decision.color.opacity(0.12)
    }
    private var border: Color {
        guard selected else { return LumeTheme.line }
        return decision == .pending ? LumeTheme.glowLine : decision.color
    }
    private var symbol: String { selected && decision != .pending ? decision.symbol + ".fill" : decision.symbol }

    private var label: some View {
        HStack(spacing: 6) {
            Image(systemName: symbol).font(.system(size: 11)).foregroundStyle(decision.color)
            Text(decision.rawValue).font(LumeFont.ui(11.5, weight: selected ? .semibold : .regular))
                .foregroundStyle(LumeTheme.ink).lineLimit(1).minimumScaleFactor(0.85)
            Spacer(minLength: 0)
        }.padding(.horizontal, 9).frame(maxWidth: .infinity, minHeight: 30)
    }

    var body: some View {
        let shape = RoundedRectangle(cornerRadius: LumeRadius.medium)
        return Button(action: action) {
            label.background(shape.fill(fill))
                .overlay(shape.strokeBorder(border, lineWidth: selected ? 1.5 : 1))
                .contentShape(shape)
        }.buttonStyle(.plain).keyboardShortcut(decision.shortcut, modifiers: .command)
            .help(decision.explanation + " (⌘" + String(decision.shortcut.character) + ")")
            .accessibilityLabel(decision.rawValue + (selected ? ", selecionado" : "") + ". " + decision.explanation)
    }
}
