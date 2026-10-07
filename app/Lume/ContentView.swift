import SwiftUI
import AppKit
import UniformTypeIdentifiers

/// Telas que pertencem só à interface; Início e Leitura continuam decididas pelo `ReviewStore`.
enum LumeSection { case main, log, engine }

/// Janela do Lume: barra com a marca e a navegação, a tela atual e a linha de estado.
@MainActor
struct ContentView: View {
    @EnvironmentObject private var store: ReviewStore
    @State private var section: LumeSection
    @State private var showSearchSettings = false
    @State private var showCoverage = false
    @State private var showKeySheet = false
    @AppStorage("lumeInspectorVisible") private var inspectorVisible = true

    init(section: LumeSection = .main) { _section = State(initialValue: section) }

    var body: some View {
        VStack(spacing: 0) {
            content.frame(maxWidth: .infinity, maxHeight: .infinity)
            StatusLine()
        }
        .background(LumeTheme.canvas)
        .navigationTitle(windowTitle)
        .navigationSubtitle(windowSubtitle)
        .toolbar { toolbarContent }
        .toolbarBackground(LumeTheme.surface, for: .windowToolbar)
        .toolbarBackground(.visible, for: .windowToolbar)
        .tint(LumeTheme.accent)
        .foregroundStyle(LumeTheme.ink)
        .onChange(of: store.isAnalyzing) { analyzing in
            if analyzing { section = .main }
        }
        .sheet(isPresented: $showSearchSettings) { SearchSettingsView().environmentObject(store) }
        .sheet(isPresented: $showCoverage) { CoverageSheet().environmentObject(store) }
        .sheet(isPresented: $showKeySheet) { KeySheet().environmentObject(store) }
        .alert("Enviar à Anthropic?", isPresented: Binding(get: { store.aiEstimate != nil },
                                                           set: { if !$0 { store.aiEstimate = nil } })) {
            Button("Cancelar", role: .cancel) { store.cancelAI() }
            Button("Enviar e analisar") { store.confirmAI() }
        } message: {
            Text(store.aiEstimate?.summary ?? "")
        }
        .alert("Lume", isPresented: Binding(get: { store.errorText != nil && !showSearchSettings && !showKeySheet },
                                            set: { if !$0 { store.errorText = nil } })) {
            Button("OK", role: .cancel) { store.errorText = nil }
        } message: { Text(store.errorText ?? "") }
    }

    @ViewBuilder private var content: some View {
        switch section {
        case .log: LogView()
        case .engine: EngineView()
        case .main:
            if store.screen == .preparation {
                HomeView(showSearchSettings: $showSearchSettings, showKeySheet: $showKeySheet,
                         openEngine: { section = .engine })
            } else {
                ReadingDeskView()
            }
        }
    }

    private var onDesk: Bool {
        section == .main && store.screen == .review && store.report != nil && !store.isAnalyzing && !store.analysisFailed
    }

    // MARK: Título

    private var documentName: String {
        let name = store.isAnalyzing ? (store.documentURL?.lastPathComponent ?? store.report?.document)
                                     : (store.report?.document ?? store.documentURL?.lastPathComponent)
        return ReviewStore.manuscriptExtensions.reduce(name ?? "Lume") {
            $0.replacingOccurrences(of: "." + $1, with: "", options: [.caseInsensitive, .anchored, .backwards])
        }
    }

    private var windowTitle: String {
        switch section {
        case .log: return "Registro"
        case .engine: return "Motor"
        case .main: return store.screen == .preparation ? "Nova leitura" : documentName
        }
    }

    private var windowSubtitle: String {
        switch section {
        case .log: return store.logURL?.lastPathComponent ?? "Nenhuma operação nesta sessão"
        case .engine: return store.engineDescription
        case .main: break
        }
        if store.screen == .preparation {
            return store.documentURL.map { $0.deletingPathExtension().lastPathComponent } ?? "Nenhum manuscrito escolhido"
        }
        if store.isAnalyzing { return "Lendo agora…" }
        if store.analysisFailed { return "Leitura interrompida" }
        guard let report = store.report else { return "Mesa de leitura" }
        let total = report.findings.count
        return "Mesa de leitura · \(total - store.pendingCount) de \(total) avaliados"
    }

    // MARK: Barra

    @ToolbarContentBuilder
    private var toolbarContent: some ToolbarContent {
        ToolbarItem(placement: .navigation) {
            HStack(spacing: 12) {
                HStack(spacing: 7) {
                    LumeMark(size: 22, glowing: store.isAnalyzing)
                    Text("Lume").font(LumeFont.ui(14, weight: .semibold))
                }.help("Lume")
                navigation
            }
        }
        if onDesk, let report = store.report {
            ToolbarItemGroup(placement: .primaryAction) {
                if let chapters = report.metadata.chapters {
                    Menu {
                        if chapters.isEmpty { Text("Nenhum título identificado") }
                        ForEach(Array(chapters.enumerated()), id: \.offset) { _, chapter in
                            let findings = report.findings.filter { $0.chapter == chapter.title }
                            Button("§ \(chapter.paragraph) · \(chapter.title) — \(findings.count) alertas") {
                                if let first = findings.first { store.selectedID = first.id }
                            }.disabled(findings.isEmpty)
                        }
                    } label: { Label("Capítulos", systemImage: "book.closed") }
                        .help("Capítulos identificados (\(chapters.count)): leva ao primeiro alerta do capítulo")
                }
                Button { store.reanalyze() } label: { Label("Reanalisar", systemImage: "arrow.clockwise") }
                    .help("Analisar a obra de novo com as mesmas opções, mantendo as decisões já marcadas")
                    .disabled(!store.canReanalyze)
                Button { showCoverage = true } label: { Label("Etapas e alcance", systemImage: "slider.horizontal.3") }
                    .help("Etapas e alcance da leitura")
                Button { inspectorVisible.toggle() } label: { Label("Inspetor", systemImage: "sidebar.right") }
                    .help(inspectorVisible ? "Recolher o inspetor para baixo da página" : "Mostrar o inspetor ao lado da página")
            }
        }
        ToolbarItemGroup(placement: .primaryAction) {
            Button { store.chooseReport() } label: { Label("Abrir relatório", systemImage: "doc.plaintext") }
                .help("Abrir um relatório JSON salvo").disabled(store.isBusy)
            if store.report != nil {
                Button { store.exportDecisions() } label: { Label("Exportar decisões", systemImage: "square.and.arrow.up") }
                    .help("Exportar suas avaliações").disabled(store.isBusy)
                Menu {
                    Button("Importar decisões…") { store.importDecisions() }
                    Divider()
                    Button("Mostrar relatório no Finder") { store.revealReport() }
                } label: { Label("Mais opções", systemImage: "ellipsis.circle") }
                    .help("Mais opções").disabled(store.isBusy)
            }
        }
    }

    /// Navegação principal, no lugar do antigo trilho lateral.
    private var navigation: some View {
        HStack(spacing: 2) {
            navItem("Início", active: section == .main && store.screen == .preparation) {
                section = .main; store.showPreparation()
            }.disabled(store.isBusy)
            navItem("Leitura", active: section == .main && store.screen == .review) {
                section = .main
                if !store.isAnalyzing { store.resumeReview() }
            }.disabled(!store.isAnalyzing && (store.isBusy || store.report == nil))
            navItem("Registro", active: section == .log) { section = .log }
            navItem("Motor", active: section == .engine) { section = .engine }
        }.padding(2)
            .background(RoundedRectangle(cornerRadius: LumeRadius.medium + 1).fill(LumeTheme.sunken))
    }

    private func navItem(_ title: String, active: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title).font(LumeFont.ui(12, weight: active ? .semibold : .regular))
                .foregroundStyle(active ? LumeTheme.onAccent : LumeTheme.ink)
                .padding(.horizontal, 11).padding(.vertical, 4)
                .background(RoundedRectangle(cornerRadius: LumeRadius.medium).fill(active ? LumeTheme.accent : .clear))
                .contentShape(Rectangle())
        }.buttonStyle(.plain).accessibilityAddTraits(active ? .isSelected : [])
    }
}
