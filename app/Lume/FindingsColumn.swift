import SwiftUI

/// Pontos de atenção: busca, filtros, aviso de tempo contradito e a lista de alertas.
@MainActor
struct FindingsColumn: View {
    @EnvironmentObject private var store: ReviewStore
    @State private var showFilters = false

    private var activeFilters: Int {
        [store.moduleFilter, store.severityFilter, store.layerFilter, store.category, store.decisionFilter]
            .filter { $0 != "Todas" }.count
    }

    private func clearFilters() {
        store.search = ""; store.category = "Todas"; store.decisionFilter = "Todas"
        store.layerFilter = "Todas"; store.moduleFilter = "Todas"; store.severityFilter = "Todas"
    }

    private func move(_ offset: Int) {
        let items = store.filteredFindings
        guard !items.isEmpty else { return }
        let index = items.firstIndex { $0.id == store.selectedID } ?? (offset > 0 ? -1 : items.count)
        let target = min(max(0, index + offset), items.count - 1)
        store.selectedID = items[target].id
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 10) {
                HStack(alignment: .firstTextBaseline) {
                    Text("Pontos de atenção").font(LumeFont.display(19, weight: .semibold))
                    Spacer()
                    Text("\(store.filteredFindings.count)").font(LumeFont.ui(11.5, weight: .semibold)).monospacedDigit()
                        .padding(.horizontal, 6).padding(.vertical, 2)
                        .background(RoundedRectangle(cornerRadius: LumeRadius.small).fill(LumeTheme.glow))
                        .foregroundStyle(LumeTheme.amber)
                        .accessibilityLabel("\(store.filteredFindings.count) alertas nesta seleção")
                }
                HStack(spacing: 6) {
                    SearchField(prompt: "Buscar no texto ou capítulo", text: $store.search)
                    Button { showFilters.toggle() } label: {
                        Image(systemName: activeFilters > 0 ? "line.3.horizontal.decrease.circle.fill" : "line.3.horizontal.decrease.circle")
                            .font(.system(size: 16)).foregroundStyle(activeFilters > 0 ? LumeTheme.accent : LumeTheme.secondary)
                            .overlay(alignment: .topTrailing) {
                                if activeFilters > 0 {
                                    Text("\(activeFilters)").font(.system(size: 8, weight: .bold)).foregroundStyle(LumeTheme.onAccent)
                                        .padding(3).background(Circle().fill(LumeTheme.accent)).offset(x: 5, y: -5)
                                }
                            }
                    }.buttonStyle(.plain).help("Filtros").accessibilityLabel("Filtros, \(activeFilters) ativos")
                        .popover(isPresented: $showFilters, arrowEdge: .bottom) { filters }
                }
                if let contradiction = store.report?.metadata.tempoContradito {
                    TenseNotice(contradiction: contradiction)
                }
            }.padding(14)
            Divider().overlay(LumeTheme.line)
            if store.filteredFindings.isEmpty {
                VStack(spacing: 10) {
                    Image(systemName: store.report == nil ? "book.closed" : "line.3.horizontal.decrease.circle")
                        .font(.system(size: 22, weight: .light))
                    Text(store.report == nil ? "Seus alertas aparecerão aqui." : "Nada nesta seleção.")
                        .font(LumeFont.display(16))
                    if store.report != nil {
                        Button("Limpar filtros", action: clearFilters).buttonStyle(LumeButtonStyle())
                    }
                }.foregroundStyle(LumeTheme.secondary).multilineTextAlignment(.center)
                    .padding(24).frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(spacing: 0) {
                            ForEach(store.filteredFindings) { finding in
                                Button { store.selectedID = finding.id } label: {
                                    FindingCard(finding: finding, decision: store.decision(for: finding),
                                                selected: store.selectedID == finding.id)
                                }.buttonStyle(.plain).id(finding.id)
                                Divider().overlay(LumeTheme.line.opacity(0.6)).padding(.horizontal, 14)
                            }
                        }
                    }.onChange(of: store.selectedID) { id in
                        guard let id else { return }
                        withAnimation(.easeOut(duration: 0.2)) { proxy.scrollTo(id) }
                    }
                }.focusable().modifier(NoFocusRing())
                    .onMoveCommand { direction in
                        if direction == .down { move(1) } else if direction == .up { move(-1) }
                    }
            }
            // Atalhos globais de navegação: ⌘[ e ⌘].
            HStack {
                Button("") { move(-1) }.keyboardShortcut("[", modifiers: .command)
                Button("") { move(1) }.keyboardShortcut("]", modifiers: .command)
            }.frame(width: 0, height: 0).opacity(0).accessibilityHidden(true)
        }.background(LumeTheme.surface)
    }

    private var filters: some View {
        VStack(alignment: .leading, spacing: 12) {
            Kicker(title: "Filtros")
            Form {
                if store.report?.metadata.stages != nil {
                    Picker("Módulo", selection: $store.moduleFilter) {
                        Text("Todos").tag("Todas")
                        ForEach(ReviewModule.allCases) { module in
                            Text("\(module.title) (\(store.report?.findings.filter { $0.module == module.rawValue }.count ?? 0))")
                                .tag(module.rawValue)
                        }
                    }
                    Picker("Classificação", selection: $store.severityFilter) {
                        Text("Todas").tag("Todas")
                        ForEach(FindingSeverity.allCases) { Text($0.title).tag($0.rawValue) }
                    }
                } else {
                    Picker("Camada", selection: $store.layerFilter) {
                        Text("Todas").tag("Todas")
                        Text("Linguística").tag("linguistica")
                        Text("Editorial").tag("editorial")
                    }
                }
                Picker("Categoria", selection: $store.category) {
                    ForEach(store.categories, id: \.self) { Text($0).tag($0) }
                }
                Picker("Avaliação", selection: $store.decisionFilter) {
                    Text("Todas").tag("Todas")
                    ForEach(ReviewDecision.allCases) { Text($0.rawValue).tag($0.rawValue) }
                }
            }.font(LumeFont.ui(12))
            HStack {
                Spacer()
                Button("Limpar filtros", action: clearFilters).buttonStyle(LumeButtonStyle())
            }
        }.padding(18).frame(width: 340)
    }
}

/// A narração contradiz o tempo escolhido: os alertas de tempo verbal tratam a própria narração
/// como desvio. Só informa; a nova análise é escolha do autor.
struct TenseNotice: View {
    let contradiction: TenseContradiction

    var body: some View {
        let other = contradiction.predominante, chosen = contradiction.escolhido
        let found = other == "presente" ? contradiction.presente : contradiction.passado
        let rest = other == "presente" ? contradiction.passado : contradiction.presente
        HStack(alignment: .top, spacing: 9) {
            FlameGlyph(size: 13, color: LumeTheme.amber).padding(.top, 1)
            VStack(alignment: .leading, spacing: 3) {
                Text("A narração parece estar no \(other)").font(LumeFont.ui(12, weight: .semibold))
                Text("Esta análise usou o \(chosen), mas a narração tem \(found) verbos no \(other) e \(rest) no \(chosen). Se o livro é narrado no \(other), escolha \(other.capitalized) e analise de novo: os alertas de tempo verbal desta lista tratam a própria narração como desvio.")
                    .font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }.padding(10).frame(maxWidth: .infinity, alignment: .leading)
            .background(RoundedRectangle(cornerRadius: LumeRadius.medium).fill(LumeTheme.glow.opacity(0.55)))
            .overlay(alignment: .leading) {
                Rectangle().fill(LumeTheme.glowLine).frame(width: 2)
                    .clipShape(RoundedRectangle(cornerRadius: 1))
            }
            .accessibilityElement(children: .combine)
    }
}

/// A lista recebe foco para navegar com ↑ ↓; o anel azul de foco do sistema não é desenhado.
struct NoFocusRing: ViewModifier {
    func body(content: Content) -> some View {
        if #available(macOS 14.0, *) { content.focusEffectDisabled() } else { content }
    }
}

private struct FindingCard: View {
    let finding: Finding
    let decision: ReviewDecision
    let selected: Bool

    private var severity: FindingSeverity? { finding.severity.flatMap(FindingSeverity.init(rawValue:)) }

    /// Janela de leitura em volta do trecho: até 40 caracteres antes e 70 depois, só para exibição.
    /// O texto vem dos segmentos em pontos de código; nada é alterado no relatório.
    private var excerpt: Text {
        let parts = finding.segments
        let before = parts.before.count > 40 ? "…" + String(parts.before.suffix(40)) : parts.before
        let after = parts.after.count > 70 ? String(parts.after.prefix(70)) + "…" : parts.after
        var marked = AttributedString(parts.marked)
        marked.backgroundColor = LumeTheme.glow
        return Text(before) + Text(marked).fontWeight(.semibold) + Text(after)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .center) {
                SeverityTag(severity: severity)
                Spacer(minLength: 4)
                Text("\(finding.chapter) · § \(finding.paragraph)").font(LumeFont.ui(10.5)).foregroundStyle(LumeTheme.secondary)
                    .lineLimit(1).truncationMode(.head)
            }
            Text(finding.category).font(LumeFont.ui(13, weight: .semibold)).lineLimit(2)
            excerpt.font(LumeFont.display(13)).foregroundStyle(LumeTheme.ink.opacity(0.85)).lineLimit(2)
            HStack(spacing: 5) {
                Image(systemName: decision.symbol).font(.system(size: 10))
                Text(decision == .pending ? "Pendente de decisão" : decision.rawValue)
                if finding.module == ReviewModule.audit.rawValue {
                    Text("·")
                    Text("Auditoria final")
                }
            }.font(LumeFont.ui(10.5, weight: .medium)).foregroundStyle(decision == .pending ? LumeTheme.secondary : decision.color)
        }.padding(.horizontal, 14).padding(.vertical, 11).frame(maxWidth: .infinity, alignment: .leading)
            .background(selected ? LumeTheme.raised : Color.clear)
            .overlay(alignment: .leading) {
                if selected { Rectangle().fill(LumeTheme.accent).frame(width: 3) }
            }
            .contentShape(Rectangle())
            .accessibilityElement(children: .combine)
            .accessibilityAddTraits(selected ? .isSelected : [])
    }
}
