import SwiftUI
import AppKit
import UniformTypeIdentifiers

@MainActor
struct ContentView: View {
    @EnvironmentObject private var store: ReviewStore
    @State private var showEngine = false
    @State private var showSearchSettings = false
    @State private var showCoverage = false
    @State private var showKeySheet = false

    var body: some View {
        // Padrão do Mac: a barra lateral sobe até os botões da janela e o título,
        // o subtítulo e as ações ficam numa única barra de ferramentas nativa.
        NavigationSplitView {
            NightRail(showEngine: $showEngine)
                .navigationSplitViewColumnWidth(min: 88, ideal: 88, max: 88)
                .modifier(HideSidebarToggle())
        } detail: {
            VStack(spacing: 0) {
                if store.screen == .preparation {
                    HomeView(showSearchSettings: $showSearchSettings, showKeySheet: $showKeySheet)
                } else {
                    ReadingDesk()
                }
                StatusLine()
            }
            .background(LumeTheme.canvas)
            .navigationTitle(windowTitle)
            .navigationSubtitle(windowSubtitle)
            .toolbar { toolbarContent }
            .toolbarBackground(LumeTheme.paper, for: .windowToolbar)
            .toolbarBackground(.visible, for: .windowToolbar)
        }
        .navigationSplitViewStyle(.prominentDetail)
        .tint(LumeTheme.accent)
        .foregroundStyle(LumeTheme.ink)
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

    private var documentName: String {
        let name = store.isAnalyzing ? (store.documentURL?.lastPathComponent ?? store.report?.document)
                                     : (store.report?.document ?? store.documentURL?.lastPathComponent)
        return ReviewStore.manuscriptExtensions.reduce(name ?? "Lume") {
            $0.replacingOccurrences(of: "." + $1, with: "", options: [.caseInsensitive, .anchored, .backwards])
        }
    }

    private var windowTitle: String {
        store.screen == .preparation ? "Nova leitura" : documentName
    }

    private var windowSubtitle: String {
        if store.screen == .preparation {
            return store.documentURL.map { $0.deletingPathExtension().lastPathComponent } ?? "Nenhum manuscrito escolhido"
        }
        if store.isAnalyzing { return "Lendo agora…" }
        if store.analysisFailed { return "Leitura interrompida" }
        guard let report = store.report else { return "Mesa de leitura" }
        let total = report.findings.count
        return "Mesa de leitura · \(total - store.pendingCount) de \(total) avaliados"
    }

    @ToolbarContentBuilder
    private var toolbarContent: some ToolbarContent {
        if store.screen == .review, let report = store.report, !store.isAnalyzing, !store.analysisFailed {
            ToolbarItemGroup(placement: .primaryAction) {
                if let chapters = report.metadata.chapters {
                    Menu {
                        if chapters.isEmpty { Text("Nenhum título identificado") }
                        ForEach(Array(chapters.enumerated()), id: \.offset) { _, chapter in
                            Text("§ \(chapter.paragraph) · \(chapter.title)")
                        }
                    } label: { Label("Capítulos", systemImage: "list.bullet") }
                        .help("Capítulos identificados (\(chapters.count))")
                }
                Button { showCoverage = true } label: { Label("Etapas e alcance", systemImage: "chart.bar.doc.horizontal") }
                    .help("Etapas e alcance da leitura")
            }
        }
        ToolbarItemGroup(placement: .primaryAction) {
            Button { store.chooseReport() } label: { Label("Abrir relatório", systemImage: "folder") }
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
}

private struct HideSidebarToggle: ViewModifier {
    func body(content: Content) -> some View {
        if #available(macOS 14, *) {
            content.toolbar(removing: .sidebarToggle)
        } else {
            content
        }
    }
}

// MARK: - Trilho noturno

@MainActor
private struct NightRail: View {
    @EnvironmentObject private var store: ReviewStore
    @Binding var showEngine: Bool

    private func item(_ title: String, symbol: String, active: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(spacing: 5) {
                Image(systemName: symbol).font(.system(size: 17, weight: .regular))
                    .frame(width: 42, height: 34)
                    .background(RoundedRectangle(cornerRadius: 11, style: .continuous)
                        .fill(active ? LumeTheme.candle.opacity(0.18) : .clear))
                Text(title).font(LumeFont.ui(10, weight: .medium))
            }.foregroundStyle(active ? LumeTheme.candle : LumeTheme.linen.opacity(0.72))
                .frame(maxWidth: .infinity).contentShape(Rectangle())
        }.buttonStyle(.plain)
            .accessibilityLabel(title).accessibilityAddTraits(active ? .isSelected : [])
    }

    var body: some View {
        VStack(spacing: 18) {
            LumeMark(size: 40, glowing: store.isAnalyzing).padding(.top, 6)
                .help("Lume")
            item("Início", symbol: "sun.horizon", active: store.screen == .preparation) { store.showPreparation() }
                .disabled(store.isBusy)
            item("Leitura", symbol: "book", active: store.screen == .review) { store.resumeReview() }
                .disabled(store.isBusy || store.report == nil)
            Spacer()
            if store.logURL != nil {
                item("Registro", symbol: "text.alignleft", active: false) { store.openLog() }
            }
            item("Motor", symbol: "gearshape", active: showEngine) { showEngine.toggle() }
                .popover(isPresented: $showEngine, arrowEdge: .trailing) {
                    EngineControls().environmentObject(store).padding(22).frame(width: 380)
                        .background(LumeTheme.paper)
                }
                .padding(.bottom, 16)
        }.frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(LinearGradient(colors: [LumeTheme.night, LumeTheme.nightDeep], startPoint: .top, endPoint: .bottom)
                .ignoresSafeArea())
    }
}

@MainActor
private struct EngineControls: View {
    @EnvironmentObject private var store: ReviewStore
    @Environment(\.openWindow) private var openWindow
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Kicker(title: "Motor de análise")
            Text(store.engineDescription).font(LumeFont.display(18))
            Text("O FONTE lê o manuscrito neste Mac. Atualizações do motor não mexem nos seus relatórios.")
                .font(LumeFont.ui(12)).foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
            if store.embeddedEngine != nil {
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Button("Instalar atualização…") { store.importEngine() }
                        Button("Verificar motor") { store.diagnose() }
                    }
                    HStack {
                        Button("Voltar à versão anterior") { store.rollbackEngine() }
                        Button("Restaurar embutido") { store.resetEngine() }
                    }
                }.buttonStyle(LumeButtonStyle())
            } else {
                Text(store.backendURL?.lastPathComponent ?? "Selecione a pasta fonte ou monte o aplicativo completo.")
                    .font(LumeFont.ui(12)).foregroundStyle(LumeTheme.secondary)
                HStack {
                    Button("Selecionar pasta…") { store.chooseBackend() }
                    Button("Preparar") { store.install() }.disabled(store.backendURL == nil)
                    Button("Verificar") { store.diagnose() }.disabled(!store.pythonExists)
                }.buttonStyle(LumeButtonStyle())
            }
            Button("Sobre o Lume e licenças…") { openWindow(id: "sobre") }
                .buttonStyle(.link).font(LumeFont.ui(12))
        }.disabled(store.isBusy).foregroundStyle(LumeTheme.ink)
    }
}

// MARK: - Início

@MainActor
private struct HomeView: View {
    @EnvironmentObject private var store: ReviewStore
    @Binding var showSearchSettings: Bool
    @Binding var showKeySheet: Bool
    @State private var dropTargeted = false

    private var greeting: String {
        switch Calendar.current.component(.hour, from: Date()) {
        case 5..<12: return "Bom dia."
        case 12..<18: return "Boa tarde."
        default: return "Boa noite."
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 30) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text(greeting).font(LumeFont.display(40)).tracking(-0.5)
                        Text(store.documentURL == nil ? "Que texto vamos iluminar hoje?" : "Tudo pronto para uma leitura atenta.")
                            .font(LumeFont.display(22)).foregroundStyle(LumeTheme.secondary)
                    }.padding(.top, 8)
                    manuscript
                    if !store.pythonExists {
                        Sheet(fill: LumeTheme.wash) {
                            VStack(alignment: .leading, spacing: 10) {
                                Label("Antes de começar, prepare o motor de análise.", systemImage: "gearshape")
                                    .font(LumeFont.ui(14, weight: .semibold))
                                EngineControls()
                            }
                        }
                    }
                    readingMode
                    HStack(alignment: .top, spacing: 20) {
                        languageSheet
                        storySheet
                    }.disabled(store.isBusy)
                    AuditSheet(showKeySheet: $showKeySheet).disabled(store.isBusy)
                }.frame(maxWidth: 940).padding(.horizontal, 40).padding(.vertical, 34)
                    .frame(maxWidth: .infinity)
            }
            actions
        }.background(LumeTheme.canvas)
    }

    private var manuscript: some View {
        Button { store.chooseDocument() } label: {
            HStack(spacing: 22) {
                ZStack {
                    RoundedRectangle(cornerRadius: 10, style: .continuous).fill(LumeTheme.canvas)
                        .frame(width: 58, height: 74)
                        .shadow(color: LumeTheme.night.opacity(0.12), radius: 8, y: 4)
                    VStack(spacing: 5) {
                        ForEach(0..<4) { i in Capsule().fill(LumeTheme.line).frame(width: i == 3 ? 20 : 34, height: 3) }
                    }
                    FlameGlyph(size: 18).offset(x: 22, y: -30)
                }
                VStack(alignment: .leading, spacing: 6) {
                    if let url = store.documentURL {
                        Kicker(title: "Manuscrito")
                        Text(url.deletingPathExtension().lastPathComponent).font(LumeFont.display(24)).lineLimit(2)
                        Text("Clique ou arraste outro manuscrito para trocar. O arquivo original nunca é alterado.")
                            .font(LumeFont.ui(12)).foregroundStyle(LumeTheme.secondary)
                    } else {
                        Text("Traga seu manuscrito").font(LumeFont.display(24))
                        Text("Arraste um arquivo Word (.docx) ou Pages (.pages) até aqui, ou clique para escolher.")
                            .font(LumeFont.ui(13)).foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
                    }
                }
                Spacer(minLength: 0)
                Image(systemName: store.documentURL == nil ? "plus.circle" : "arrow.triangle.2.circlepath")
                    .font(.system(size: 22, weight: .light)).foregroundStyle(LumeTheme.accent)
            }.padding(26).frame(maxWidth: .infinity, alignment: .leading)
                .background(RoundedRectangle(cornerRadius: 24, style: .continuous)
                    .fill(dropTargeted ? LumeTheme.wash : LumeTheme.paper))
                .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous)
                    .strokeBorder(dropTargeted ? LumeTheme.accent : LumeTheme.line,
                                  style: StrokeStyle(lineWidth: dropTargeted ? 2 : 1.2, dash: store.documentURL == nil ? [7, 6] : [])))
                .contentShape(RoundedRectangle(cornerRadius: 24))
        }.buttonStyle(.plain).disabled(store.isBusy)
            .accessibilityLabel(store.documentURL == nil ? "Escolher manuscrito" : "Trocar manuscrito")
            .onDrop(of: [.fileURL], isTargeted: $dropTargeted) { providers in
                guard let provider = providers.first else { return false }
                _ = provider.loadObject(ofClass: URL.self) { url, _ in
                    guard let url else { return }
                    Task { @MainActor in store.openDocument(url) }
                }
                return true
            }
    }

    private func modeCard(_ tag: String, title: String, detail: String, symbol: String) -> some View {
        let selected = store.analysisMode == tag
        return Button { store.analysisMode = tag } label: {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Image(systemName: symbol).font(.system(size: 18)).frame(width: 24, height: 24)
                        .foregroundStyle(selected ? LumeTheme.accent : LumeTheme.secondary)
                    Spacer()
                    Image(systemName: selected ? "largecircle.fill.circle" : "circle")
                        .foregroundStyle(selected ? LumeTheme.accent : LumeTheme.line)
                }
                Text(title).font(LumeFont.display(19))
                Text(detail).font(LumeFont.ui(12)).foregroundStyle(LumeTheme.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: 0)
            }.padding(18).frame(maxWidth: .infinity, minHeight: 138, alignment: .topLeading)
                .background(RoundedRectangle(cornerRadius: 18, style: .continuous).fill(selected ? LumeTheme.wash : LumeTheme.paper))
                .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .strokeBorder(selected ? LumeTheme.accent : LumeTheme.line, lineWidth: selected ? 1.6 : 1))
                .contentShape(RoundedRectangle(cornerRadius: 18))
        }.buttonStyle(.plain)
            .accessibilityLabel(title + ". " + detail).accessibilityAddTraits(selected ? .isSelected : [])
    }

    private var readingMode: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .firstTextBaseline) {
                Text("Como você quer ler?").font(LumeFont.display(24))
                Spacer()
                Button { showSearchSettings = true } label: { Label("Ajustar o que procurar…", systemImage: "slider.horizontal.3") }
                    .buttonStyle(LumeButtonStyle(kind: .soft)).disabled(store.documentURL == nil)
            }
            HStack(spacing: 14) {
                modeCard("linguistica", title: "A língua", detail: "Ortografia, gramática, pontuação e tempo verbal.", symbol: "textformat")
                modeCard("editorial", title: "A história", detail: "Repetições, continuidade e contradições entre cenas.", symbol: "book.pages")
                modeCard("ambas", title: "Leitura completa", detail: "A língua e a história, numa só passada.", symbol: "sparkles")
            }.disabled(store.isBusy)
        }
    }

    private func pill(_ title: String, tag: String) -> some View {
        let selected = store.tense == tag
        return Button { store.tense = tag } label: {
            Text(title).font(LumeFont.ui(12, weight: .medium)).padding(.horizontal, 14).padding(.vertical, 7)
                .foregroundStyle(selected ? LumeTheme.linen : LumeTheme.ink)
                .background(Capsule().fill(selected ? LumeTheme.night : LumeTheme.canvas))
                .overlay(Capsule().strokeBorder(selected ? .clear : LumeTheme.line))
        }.buttonStyle(.plain).accessibilityAddTraits(selected ? .isSelected : [])
    }

    private var languageSheet: some View {
        let off = store.analysisMode == "editorial"
        return Sheet {
            VStack(alignment: .leading, spacing: 16) {
                Kicker(title: "A língua")
                VStack(alignment: .leading, spacing: 8) {
                    Text("Em que tempo o livro é narrado?").font(LumeFont.ui(14, weight: .semibold))
                    HStack(spacing: 8) { pill("Passado", tag: "passado"); pill("Presente", tag: "presente") }
                    Text("Um tempo diferente do texto gera muitos alertas falsos de tempo verbal.")
                        .font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
                }
                Divider().overlay(LumeTheme.line)
                Toggle(isOn: $store.useLanguageTool) {
                    VStack(alignment: .leading, spacing: 3) {
                        Text("Corretor gramatical local").font(LumeFont.ui(14, weight: .semibold))
                        Text("LanguageTool neste Mac, sem internet.").font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary)
                    }
                }.toggleStyle(.switch)
                    .help("Ortografia e gramática com o LanguageTool incluído no motor, executado neste Mac, sem internet. Motores sem o corretor embutido exigem um servidor LanguageTool iniciado separadamente na porta 8081.")
            }
        }.disabled(off).opacity(off ? 0.5 : 1)
    }

    private var storySheet: some View {
        let off = store.analysisMode == "linguistica"
        return Sheet {
            VStack(alignment: .leading, spacing: 16) {
                Kicker(title: "A história")
                Toggle(isOn: $store.useCoherenceAI) {
                    VStack(alignment: .leading, spacing: 3) {
                        Text("Coerência com IA (Claude)").font(LumeFont.ui(14, weight: .semibold))
                        Text("Contradições entre cenas. Só capítulos alterados são enviados, com custo mostrado antes.")
                            .font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
                    }
                }.toggleStyle(.switch)
                    .help("Contradições narrativas analisadas pela API do Claude. Só os capítulos alterados são enviados à Anthropic; antes do envio, o Lume mostra o custo estimado e pede confirmação.")
                if store.useCoherenceAI {
                    VStack(alignment: .leading, spacing: 10) {
                        Picker("Modelo", selection: $store.coherenceModel) {
                            Text("Sonnet 5.5 · recomendado").tag("claude-sonnet-5-5")
                            Text("Opus 5.5 · mais forte, custa o dobro").tag("claude-opus-5-5")
                        }.font(LumeFont.ui(12))
                        HStack {
                            Text("Teto por análise (US$)").font(LumeFont.ui(12))
                            Spacer()
                            TextField("1,00", value: $store.coherenceBudget, format: .number.precision(.fractionLength(2)))
                                .frame(width: 70).multilineTextAlignment(.trailing)
                        }
                        HStack {
                            Label(store.hasAPIKey ? "Chave guardada nas Chaves do macOS" : "Chave ainda não configurada",
                                  systemImage: store.hasAPIKey ? "key" : "exclamationmark.triangle")
                                .font(LumeFont.ui(11)).foregroundStyle(store.hasAPIKey ? LumeTheme.secondary : LumeTheme.rose)
                            Spacer()
                            Button(store.hasAPIKey ? "Trocar…" : "Configurar…") { showKeySheet = true }
                                .buttonStyle(LumeButtonStyle(kind: .soft))
                        }
                    }.padding(14).background(RoundedRectangle(cornerRadius: 14).fill(LumeTheme.canvas))
                }
                Divider().overlay(LumeTheme.line)
                VStack(alignment: .leading, spacing: 8) {
                    Text("Comparar com uma versão anterior").font(LumeFont.ui(14, weight: .semibold))
                    Text("Opcional: procura vestígios de cortes.").font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary)
                    if let original = store.originalURL {
                        HStack {
                            Label(original.lastPathComponent, systemImage: "doc.on.doc").font(LumeFont.ui(12)).lineLimit(2)
                            Spacer()
                            Button("Trocar…") { store.chooseOriginal() }
                            Button("Remover") { store.originalURL = nil }
                        }.buttonStyle(LumeButtonStyle())
                    } else {
                        Button("Escolher original…") { store.chooseOriginal() }
                            .buttonStyle(LumeButtonStyle()).disabled(store.documentURL == nil)
                    }
                }
            }
        }.disabled(off).opacity(off ? 0.5 : 1)
    }

    private var actions: some View {
        HStack(spacing: 16) {
            Label("Seu texto, no seu Mac.", systemImage: "lock")
                .font(LumeFont.ui(12)).foregroundStyle(LumeTheme.secondary)
            Spacer()
            if store.report != nil {
                Button("Retomar relatório aberto") { store.resumeReview() }
                    .buttonStyle(LumeButtonStyle()).disabled(store.isBusy)
            }
            Button { store.analyze() } label: {
                HStack(spacing: 8) { Text("Começar a leitura"); Image(systemName: "arrow.right") }
            }.buttonStyle(LumeButtonStyle(kind: .primary)).disabled(!store.canAnalyze)
                .keyboardShortcut(.return, modifiers: .command)
        }.padding(.horizontal, 40).padding(.vertical, 16)
            .background(LumeTheme.paper.shadow(.drop(color: LumeTheme.night.opacity(0.06), radius: 8, y: -2)))
    }
}

/// Última leitura com o Claude, depois das regras; vale para os três modos.
struct AuditSheet: View {
    @EnvironmentObject private var store: ReviewStore
    @Binding var showKeySheet: Bool

    var body: some View {
        Sheet {
            VStack(alignment: .leading, spacing: 16) {
                Kicker(title: "Auditoria final")
                Toggle(isOn: $store.useAuditAI) {
                    VStack(alignment: .leading, spacing: 3) {
                        Text("Auditoria final com IA (Claude)").font(LumeFont.ui(14, weight: .semibold))
                        Text("Uma última leitura procura o que as regras deixaram passar. Custa dinheiro: só trechos novos ou alterados são enviados, com o custo mostrado antes.")
                            .font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
                    }
                }.toggleStyle(.switch)
                    .help("Depois das outras etapas, o Claude relê cada capítulo com os alertas já encontrados e aponta só problemas novos, como suspeitas para você avaliar. Antes do envio, o Lume mostra o custo estimado e pede confirmação.")
                if store.useAuditAI {
                    HStack(alignment: .center, spacing: 18) {
                        Picker("Modelo", selection: $store.auditModel) {
                            Text("Opus 5.5 · recomendado").tag("claude-opus-5-5")
                            Text("Sonnet 5.5 · custa a metade").tag("claude-sonnet-5-5")
                        }.font(LumeFont.ui(12)).frame(maxWidth: 300)
                        HStack {
                            Text("Teto por análise (US$)").font(LumeFont.ui(12))
                            TextField("1,00", value: $store.auditBudget, format: .number.precision(.fractionLength(2)))
                                .frame(width: 70).multilineTextAlignment(.trailing)
                        }
                        Spacer()
                        Label(store.hasAPIKey ? "Chave guardada" : "Chave ainda não configurada",
                              systemImage: store.hasAPIKey ? "key" : "exclamationmark.triangle")
                            .font(LumeFont.ui(11)).foregroundStyle(store.hasAPIKey ? LumeTheme.secondary : LumeTheme.rose)
                        Button(store.hasAPIKey ? "Trocar…" : "Configurar…") { showKeySheet = true }
                            .buttonStyle(LumeButtonStyle(kind: .soft))
                    }.padding(14).background(RoundedRectangle(cornerRadius: 14).fill(LumeTheme.canvas))
                }
            }
        }
    }
}

// MARK: - Mesa de leitura

@MainActor
private struct ReadingDesk: View {
    @EnvironmentObject private var store: ReviewStore

    var body: some View {
        VStack(spacing: 0) {
            if store.isAnalyzing {
                ReadingInProgress()
            } else if store.analysisFailed {
                recovery
            } else {
                HSplitView {
                    FindingsColumn().frame(minWidth: 300, idealWidth: 350, maxWidth: 440)
                    Group {
                        if let finding = store.selectedFinding {
                            ReadingPage(finding: finding)
                        } else {
                            restingPage
                        }
                    }.frame(minWidth: 520, maxWidth: .infinity, maxHeight: .infinity)
                }
            }
        }.frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var recovery: some View {
        VStack(spacing: 18) {
            Image(systemName: "moon.stars").font(.system(size: 40, weight: .light)).foregroundStyle(LumeTheme.accent)
            Text("A leitura foi interrompida.").font(LumeFont.display(30))
            Text(store.status).font(LumeFont.ui(13)).foregroundStyle(LumeTheme.secondary)
                .multilineTextAlignment(.center).frame(maxWidth: 520)
            HStack {
                Button("Voltar ao início") { store.showPreparation() }
                if store.report != nil { Button("Retomar relatório anterior") { store.resumeReview() } }
                if store.logURL != nil { Button("Ver registro") { store.openLog() } }
            }.buttonStyle(LumeButtonStyle())
        }.padding(40).frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var restingPage: some View {
        let none = store.report?.findings.isEmpty == true
        return VStack(alignment: .leading, spacing: 20) {
            LumeMark(size: 64)
            Text(none ? "Nenhum alerta nesta leitura." : "Cada alerta é uma pergunta,\nnão uma sentença.")
                .font(LumeFont.display(32)).lineSpacing(4)
            Text(none ? "Confira os critérios usados. A ausência de alertas não garante ausência de erros."
                      : "O texto continua sendo seu. Escolha um ponto de atenção à esquerda para lê-lo em contexto e registrar sua avaliação.")
                .font(LumeFont.ui(14)).foregroundStyle(LumeTheme.secondary).lineSpacing(3)
        }.frame(maxWidth: 480, alignment: .leading).padding(40)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

@MainActor
private struct ReadingInProgress: View {
    @EnvironmentObject private var store: ReviewStore
    @State private var breathe = false

    var body: some View {
        ScrollView {
            VStack(spacing: 22) {
                ZStack {
                    Circle().fill(RadialGradient(colors: [LumeTheme.candle.opacity(0.35), .clear], center: .center,
                                                 startRadius: 0, endRadius: 90))
                        .frame(width: 180, height: 180).scaleEffect(breathe ? 1.08 : 0.9)
                    LumeMark(size: 84, glowing: true)
                }.onAppear {
                    withAnimation(.easeInOut(duration: 2.2).repeatForever(autoreverses: true)) { breathe = true }
                }
                Text("Lendo com atenção…").font(LumeFont.display(32))
                Text("Os pontos de atenção aparecem aqui quando a leitura terminar.")
                    .font(LumeFont.ui(13)).foregroundStyle(LumeTheme.secondary)
                VStack(alignment: .leading, spacing: 0) {
                    ForEach(Array(store.analysisStages.enumerated()), id: \.element.id) { index, stage in
                        HStack(alignment: .top, spacing: 14) {
                            VStack(spacing: 0) {
                                ZStack {
                                    Circle().fill(stage.state == "completed" ? LumeTheme.candle :
                                                    (stage.state == "running" ? LumeTheme.candle.opacity(0.35) : .clear))
                                    Circle().strokeBorder(stage.state == "pending" || stage.state == "skipped" ? LumeTheme.line : LumeTheme.candle, lineWidth: 1.5)
                                    if stage.state == "completed" {
                                        Image(systemName: "checkmark").font(.system(size: 9, weight: .bold)).foregroundStyle(LumeTheme.night)
                                    }
                                }.frame(width: 18, height: 18)
                                if index < store.analysisStages.count - 1 {
                                    Rectangle().fill(LumeTheme.line).frame(width: 1.5, height: 30)
                                }
                            }
                            VStack(alignment: .leading, spacing: 3) {
                                Text(stage.title).font(LumeFont.ui(14, weight: stage.state == "running" ? .semibold : .regular))
                                Text(stage.statusText).font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary).monospacedDigit()
                            }
                        }.accessibilityElement(children: .combine)
                    }
                }.padding(24).frame(maxWidth: 460, alignment: .leading)
                    .background(RoundedRectangle(cornerRadius: 20, style: .continuous).fill(LumeTheme.paper))
                Button("Interromper leitura") { store.cancel() }.disabled(!store.canCancel)
                    .buttonStyle(LumeButtonStyle())
            }.padding(40).frame(maxWidth: .infinity)
        }
    }
}

// MARK: - Coluna de alertas

@MainActor
private struct FindingsColumn: View {
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
            VStack(alignment: .leading, spacing: 12) {
                HStack(alignment: .firstTextBaseline) {
                    Text("Pontos de atenção").font(LumeFont.display(21))
                    Spacer()
                    Text("\(store.filteredFindings.count)").font(LumeFont.ui(12, weight: .semibold)).monospacedDigit()
                        .padding(.horizontal, 9).padding(.vertical, 3)
                        .background(Capsule().fill(LumeTheme.wash)).foregroundStyle(LumeTheme.accent)
                }
                HStack(spacing: 8) {
                    HStack(spacing: 7) {
                        Image(systemName: "magnifyingglass").foregroundStyle(LumeTheme.secondary)
                        TextField("Buscar no texto ou capítulo", text: $store.search).textFieldStyle(.plain)
                            .font(LumeFont.ui(13))
                    }.padding(.horizontal, 12).padding(.vertical, 8)
                        .background(Capsule().fill(LumeTheme.paper))
                        .overlay(Capsule().strokeBorder(LumeTheme.line))
                    Button { showFilters.toggle() } label: {
                        Image(systemName: activeFilters > 0 ? "line.3.horizontal.decrease.circle.fill" : "line.3.horizontal.decrease.circle")
                            .font(.system(size: 18)).foregroundStyle(activeFilters > 0 ? LumeTheme.accent : LumeTheme.secondary)
                            .overlay(alignment: .topTrailing) {
                                if activeFilters > 0 {
                                    Text("\(activeFilters)").font(.system(size: 8, weight: .bold)).foregroundStyle(LumeTheme.linen)
                                        .padding(3).background(Circle().fill(LumeTheme.rose)).offset(x: 5, y: -5)
                                }
                            }
                    }.buttonStyle(.plain).help("Filtros").accessibilityLabel("Filtros, \(activeFilters) ativos")
                        .popover(isPresented: $showFilters, arrowEdge: .bottom) { filters }
                }
                if let contradiction = store.report?.metadata.tempoContradito {
                    TenseNotice(contradiction: contradiction)
                }
            }.padding(18)
            Rectangle().fill(LumeTheme.line).frame(height: 1)
            if store.filteredFindings.isEmpty {
                VStack(spacing: 12) {
                    Image(systemName: store.report == nil ? "book.closed" : "line.3.horizontal.decrease.circle")
                        .font(.system(size: 26, weight: .light))
                    Text(store.report == nil ? "Seus alertas aparecerão aqui." : "Nada nesta seleção.")
                        .font(LumeFont.display(17))
                    if store.report != nil {
                        Button("Limpar filtros", action: clearFilters).buttonStyle(LumeButtonStyle())
                    }
                }.foregroundStyle(LumeTheme.secondary).multilineTextAlignment(.center)
                    .padding(24).frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(spacing: 8) {
                            ForEach(store.filteredFindings) { finding in
                                Button { store.selectedID = finding.id } label: {
                                    FindingCard(finding: finding, decision: store.decision(for: finding),
                                                selected: store.selectedID == finding.id)
                                }.buttonStyle(.plain).id(finding.id)
                            }
                        }.padding(12)
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
        }.background(LumeTheme.canvas)
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
        }.padding(20).frame(width: 340)
    }
}

/// A narração contradiz o tempo escolhido: os alertas de tempo verbal tratam a própria narração
/// como desvio. Só informa; a nova análise é escolha do autor.
private struct TenseNotice: View {
    let contradiction: TenseContradiction

    var body: some View {
        let other = contradiction.predominante, chosen = contradiction.escolhido
        let found = other == "presente" ? contradiction.presente : contradiction.passado
        let rest = other == "presente" ? contradiction.passado : contradiction.presente
        HStack(alignment: .top, spacing: 9) {
            Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(LumeTheme.amber)
            VStack(alignment: .leading, spacing: 3) {
                Text("A narração parece estar no \(other)").font(LumeFont.ui(12, weight: .semibold))
                Text("Esta análise usou o \(chosen), mas a narração tem \(found) verbos no \(other) e \(rest) no \(chosen). Se o livro é narrado no \(other), escolha \(other.capitalized) e analise de novo: os alertas de tempo verbal desta lista tratam a própria narração como desvio.")
                    .font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }.padding(10).frame(maxWidth: .infinity, alignment: .leading)
            .background(RoundedRectangle(cornerRadius: 10).fill(LumeTheme.wash))
            .accessibilityElement(children: .combine)
    }
}

/// A lista recebe foco para navegar com ↑ ↓; o anel azul de foco do sistema não é desenhado.
private struct NoFocusRing: ViewModifier {
    func body(content: Content) -> some View {
        if #available(macOS 14.0, *) { content.focusEffectDisabled() } else { content }
    }
}

private struct FindingCard: View {
    let finding: Finding
    let decision: ReviewDecision
    let selected: Bool

    private var severity: FindingSeverity? { finding.severity.flatMap(FindingSeverity.init(rawValue:)) }
    private var excerpt: Text {
        let parts = finding.segments
        return Text(parts.before) + Text(parts.marked).bold().foregroundColor(LumeTheme.rose) + Text(parts.after)
    }

    var body: some View {
        HStack(alignment: .top, spacing: 11) {
            Circle().fill(severity?.color ?? LumeTheme.secondary).frame(width: 7, height: 7).padding(.top, 5)
            VStack(alignment: .leading, spacing: 7) {
                HStack(alignment: .firstTextBaseline) {
                    Text(finding.category).font(LumeFont.ui(12, weight: .semibold))
                    Spacer(minLength: 4)
                    Image(systemName: decision.symbol).font(.system(size: 12)).foregroundStyle(decision.color)
                }
                excerpt.font(LumeFont.display(13.5)).lineSpacing(2).lineLimit(3)
                    .foregroundStyle(LumeTheme.ink.opacity(0.9))
                Text("§ \(finding.paragraph) · \(decision.rawValue)")
                    .font(LumeFont.ui(10)).foregroundStyle(LumeTheme.secondary)
            }
        }.padding(13).frame(maxWidth: .infinity, alignment: .leading)
            .background(RoundedRectangle(cornerRadius: 14, style: .continuous).fill(selected ? LumeTheme.wash : LumeTheme.paper))
            .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous)
                .strokeBorder(selected ? LumeTheme.accent : LumeTheme.line.opacity(0.7), lineWidth: selected ? 1.5 : 1))
            .contentShape(RoundedRectangle(cornerRadius: 14))
            .accessibilityElement(children: .combine)
            .accessibilityAddTraits(selected ? .isSelected : [])
    }
}

// MARK: - Página de leitura

@MainActor
private struct ReadingPage: View {
    @EnvironmentObject private var store: ReviewStore
    @AppStorage("lumeReadingSize") private var readingSize = 21.0
    let finding: Finding
    @State private var correction = ""
    @State private var copiedID: String?
    /// Editar parágrafo: opção do autor para trocar o parágrafo todo em vez do trecho destacado.
    @State private var editingParagraph = false
    @State private var paragraphDraft = ""

    private var textSize: CGFloat { CGFloat(min(28, max(17, readingSize))) }

    /// Correção do trecho destacado, gravada no documento do Pages a pedido do autor.
    @ViewBuilder private var correctionView: some View {
        if let edit = store.appliedEdit(for: finding) {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Image(systemName: "checkmark.circle.fill").foregroundStyle(LumeTheme.sage)
                Text(edit.before.isEmpty ? "inserção" : edit.before).strikethrough(!edit.before.isEmpty, color: LumeTheme.rose)
                    .foregroundStyle(LumeTheme.secondary)
                Image(systemName: "arrow.right").font(.system(size: 11)).foregroundStyle(LumeTheme.secondary)
                Text(edit.after.isEmpty ? "trecho removido" : edit.after).italic(edit.after.isEmpty).bold()
                Text("Gravado no arquivo; analise novamente para ver o manuscrito atualizado.")
                    .font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary).lineLimit(1)
                Spacer(minLength: 4)
                Button { store.revealBackup() } label: { Image(systemName: "clock.arrow.circlepath") }
                    .buttonStyle(.borderless).help("Mostrar a cópia anterior às correções")
                    .accessibilityLabel("Mostrar a cópia anterior às correções")
            }.font(LumeFont.display(15)).textSelection(.enabled)
        } else if editingParagraph {
            VStack(alignment: .leading, spacing: 6) {
                TextField("Parágrafo", text: $paragraphDraft, axis: .vertical)
                    .textFieldStyle(.roundedBorder).font(LumeFont.display(16)).lineLimit(3...12)
                    .accessibilityLabel("Texto do parágrafo inteiro")
                HStack(spacing: 10) {
                    Button { editingParagraph = false } label: { Label("Editar só o trecho", systemImage: "text.cursor") }
                        .buttonStyle(.borderless).font(LumeFont.ui(11))
                        .help("Volta a trocar apenas o trecho destacado")
                    Text("Só o que você mudar é gravado; o restante do parágrafo e a formatação ficam como estão.")
                        .font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary)
                    Spacer(minLength: 4)
                    Button { store.applyParagraphEdit(paragraphDraft, for: finding) } label: {
                        Label("Gravar parágrafo", systemImage: "pencil.line")
                    }.buttonStyle(LumeButtonStyle())
                        .disabled(store.isBusy || paragraphDraft == store.currentParagraph(for: finding))
                        .help("Grava no arquivo do Pages a parte do parágrafo que você alterou. Uma cópia do original é guardada antes da primeira correção.")
                }
            }
        } else {
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 10) {
                    TextField("Texto que substitui o trecho destacado (vazio remove o trecho)", text: $correction)
                        .textFieldStyle(.roundedBorder).font(LumeFont.display(16))
                        .accessibilityLabel("Correção para o trecho destacado")
                    Button { store.applyCorrection(correction, for: finding) } label: {
                        Label("Corrigir", systemImage: "pencil.line")
                    }.buttonStyle(LumeButtonStyle()).disabled(!canCorrect)
                        .help("Troca só o trecho destacado, no próprio arquivo do Pages. Uma cópia do original é guardada antes da primeira correção.")
                    Button {
                        paragraphDraft = store.currentParagraph(for: finding)
                        editingParagraph = true
                    } label: { Label("Editar parágrafo", systemImage: "text.alignleft") }
                        .buttonStyle(LumeButtonStyle())
                        .help("Abre o parágrafo inteiro para edição, em vez de só o trecho destacado")
                }
                if store.editCount(inParagraph: finding.paragraph) > 0 {
                    Text("Este parágrafo já recebeu correções; o texto acima é o da análise. A troca vale só para o trecho destacado.")
                        .font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary)
                }
            }
        }
    }
    private var canCorrect: Bool { !store.isBusy && correction != finding.segments.marked }

    /// Correção, avaliação e confirmação logo abaixo da explicação do alerta.
    private var actionPanel: some View {
        VStack(alignment: .leading, spacing: 10) {
            if store.canEditManuscript { correctionView }
            HStack(spacing: 10) {
                ViewThatFits(in: .horizontal) {
                    HStack(spacing: 6) { decisionChips }
                    LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 6), count: 3), spacing: 6) { decisionChips }
                }.disabled(store.isBusy)
                Button { confirm() } label: { Label("Confirmar", systemImage: "checkmark") }
                    .buttonStyle(LumeButtonStyle())
                    .disabled(store.decision(for: finding) == .pending)
                    .help("Confirma a sua avaliação e passa para o próximo alerta")
            }
        }.padding(14).frame(maxWidth: .infinity, alignment: .leading)
            .background(RoundedRectangle(cornerRadius: 16, style: .continuous).fill(LumeTheme.wash.opacity(0.6)))
            .task(id: finding.id) {
                correction = finding.suggestion ?? finding.segments.marked
                editingParagraph = false
            }
    }

    @ViewBuilder private var decisionChips: some View {
        ForEach(ReviewDecision.allCases) { decision in
            DecisionChip(decision: decision, selected: store.decision(for: finding) == decision) {
                store.setDecision(decision, for: finding)
            }
        }
    }
    private var severity: FindingSeverity? { finding.severity.flatMap(FindingSeverity.init(rawValue:)) }
    private var currentIndex: Int? { store.filteredFindings.firstIndex { $0.id == finding.id } }
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

    /// O trecho sinalizado recebe uma luz suave ao fundo; o texto não é alterado.
    private var illuminated: Text {
        let parts = finding.segments
        var marked = AttributedString(parts.marked)
        marked.backgroundColor = LumeTheme.glow
        marked.foregroundColor = LumeTheme.ink
        return Text(parts.before) + Text(marked).underline(color: LumeTheme.rose) + Text(parts.after)
    }

    private func evidenceView(_ evidence: TextEvidence) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("\(evidence.document == "original" ? "Original" : "Manuscrito atual") · \(evidence.chapter) · § \(evidence.paragraph)")
                .font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary)
            Text(evidence.text).font(LumeFont.display(15)).lineSpacing(5).textSelection(.enabled)
        }.padding(16).frame(maxWidth: .infinity, alignment: .leading)
            .background(RoundedRectangle(cornerRadius: 14, style: .continuous).fill(LumeTheme.canvas))
    }

    var body: some View {
        VStack(spacing: 0) {
            header.padding(.horizontal, 24).padding(.top, 16).padding(.bottom, 12)
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    page
                    marginNote
                    actionPanel
                    if let related = finding.related, !related.isEmpty {
                        VStack(alignment: .leading, spacing: 10) {
                            Kicker(title: "Trechos relacionados")
                            ForEach(Array(related.enumerated()), id: \.offset) { _, evidence in evidenceView(evidence) }
                        }
                    }
                    if let context = finding.context, !context.isEmpty {
                        DisclosureGroup("Ver contexto próximo") {
                            VStack(alignment: .leading, spacing: 12) {
                                ForEach(Array(context.enumerated()), id: \.offset) { _, evidence in evidenceView(evidence) }
                            }.padding(.top, 12)
                        }.font(LumeFont.ui(12))
                    }
                    if let report = store.report, !report.warnings.isEmpty {
                        DisclosureGroup("Sobre esta análise · \(report.warnings.count) avisos") {
                            VStack(alignment: .leading, spacing: 10) {
                                ForEach(Array(report.warnings.enumerated()), id: \.offset) { _, warning in
                                    Text(warning).font(LumeFont.ui(11)).lineSpacing(3)
                                }
                                Text("As avaliações registradas não treinam o analisador automaticamente.").font(LumeFont.ui(11))
                            }.padding(.top, 10)
                        }.font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary)
                    }
                }.padding(.horizontal, 24).padding(.bottom, 18).frame(maxWidth: 860, alignment: .leading)
                    .frame(maxWidth: .infinity, alignment: .center)
            }
        }.background(LumeTheme.canvas)
    }

    /// Cabeçalho em duas linhas curtas: classificação e navegação; categoria e local.
    private var header: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 10) {
                Label(finding.moduleTitle + " · " + finding.severityTitle, systemImage: "circle.fill")
                    .labelStyle(DotLabel(color: severity?.color ?? LumeTheme.secondary))
                    .font(LumeFont.ui(11, weight: .medium))
                Spacer()
                if let index = currentIndex {
                    Text("\(index + 1) de \(store.filteredFindings.count)").font(LumeFont.ui(11)).monospacedDigit()
                        .foregroundStyle(LumeTheme.secondary)
                }
                Button { move(-1) } label: { Image(systemName: "chevron.up") }
                    .help("Alerta anterior (⌘[)").accessibilityLabel("Alerta anterior")
                    .disabled(currentIndex == nil || currentIndex == 0)
                Button { move(1) } label: { Image(systemName: "chevron.down") }
                    .help("Próximo alerta (⌘])").accessibilityLabel("Próximo alerta")
                    .disabled(currentIndex == nil || currentIndex == store.filteredFindings.count - 1)
            }.buttonStyle(.borderless)
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                Text(finding.category).font(LumeFont.display(22)).lineLimit(2)
                Text("\(finding.chapter) · parágrafo \(finding.paragraph)")
                    .font(LumeFont.ui(12)).foregroundStyle(LumeTheme.secondary).textSelection(.enabled).lineLimit(1)
            }
        }.frame(maxWidth: 860, alignment: .leading).frame(maxWidth: .infinity, alignment: .center)
    }

    /// A página.
    private var page: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 10) {
                Kicker(title: "No seu texto")
                Spacer()
                Button {
                    store.copyParagraph(finding)
                    let id = finding.id
                    withAnimation(.easeOut(duration: 0.15)) { copiedID = id }
                    Task {
                        try? await Task.sleep(nanoseconds: 1_500_000_000)
                        if copiedID == id { withAnimation(.easeIn(duration: 0.3)) { copiedID = nil } }
                    }
                } label: {
                    if copiedID == finding.id {
                        Label("Copiado", systemImage: "checkmark").foregroundStyle(LumeTheme.sage)
                            .font(LumeFont.ui(11, weight: .semibold))
                    } else {
                        Image(systemName: "doc.on.doc")
                    }
                }.help("Copiar parágrafo para localizar no original")
                    .accessibilityLabel("Copiar parágrafo para localizar no original")
                Button { readingSize = max(17, readingSize - 1) } label: { Text("A").font(.system(size: 11)) }
                    .accessibilityLabel("Diminuir tamanho do texto").disabled(readingSize <= 17)
                Button { readingSize = min(28, readingSize + 1) } label: { Text("A").font(.system(size: 16)) }
                    .accessibilityLabel("Aumentar tamanho do texto").disabled(readingSize >= 28)
            }.buttonStyle(.borderless)
            illuminated.font(LumeFont.display(textSize)).lineSpacing(textSize * 0.35)
                .textSelection(.enabled).fixedSize(horizontal: false, vertical: true)
        }.padding(.horizontal, 26).padding(.vertical, 18).frame(maxWidth: .infinity, alignment: .leading)
            .background(RoundedRectangle(cornerRadius: 18, style: .continuous).fill(LumeTheme.paper)
                .shadow(color: LumeTheme.night.opacity(0.08), radius: 14, y: 6))
    }

    /// Nota de margem: o motivo do alerta. A sugestão já vem no campo de correção;
    /// a caixa "trecho → sugestão" só aparece quando o documento não pode ser corrigido pelo app.
    private var marginNote: some View {
        HStack(alignment: .top, spacing: 14) {
            RoundedRectangle(cornerRadius: 2).fill(LinearGradient(colors: [LumeTheme.candle, LumeTheme.blush],
                                                                   startPoint: .top, endPoint: .bottom))
                .frame(width: 3)
            VStack(alignment: .leading, spacing: 8) {
                Text(finding.reason).font(LumeFont.ui(13.5)).lineSpacing(4).textSelection(.enabled)
                    .fixedSize(horizontal: false, vertical: true)
                if let suggestion = finding.suggestion, !store.canEditManuscript {
                    HStack(alignment: .firstTextBaseline, spacing: 8) {
                        Text(finding.segments.marked).strikethrough(color: LumeTheme.rose)
                            .foregroundStyle(LumeTheme.secondary)
                        Image(systemName: "arrow.right").font(.system(size: 11)).foregroundStyle(LumeTheme.secondary)
                        Text(suggestion.isEmpty ? "remover o trecho" : suggestion)
                            .italic(suggestion.isEmpty).foregroundStyle(LumeTheme.accent).bold()
                    }.font(LumeFont.display(15)).textSelection(.enabled)
                        .padding(.horizontal, 12).padding(.vertical, 8)
                        .background(RoundedRectangle(cornerRadius: 10).fill(LumeTheme.wash))
                        .accessibilityElement(children: .combine)
                        .accessibilityLabel(suggestion.isEmpty ? "Sugestão: remover o trecho destacado."
                                            : "Sugestão para o trecho destacado: \(suggestion)")
                }
                DisclosureGroup("Detalhes da análise") {
                    VStack(alignment: .leading, spacing: 4) {
                        if let confidence = finding.confidence {
                            Text("Força do indício: \(confidence). Classificação automática, sujeita à sua decisão.")
                        }
                        Text("Prioridade: \(finding.priority)\nOrigem: \(finding.source)")
                    }.font(LumeFont.ui(11)).frame(maxWidth: .infinity, alignment: .leading).padding(.top, 6)
                        .textSelection(.enabled)
                }.font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary)
            }
        }.fixedSize(horizontal: false, vertical: true)
    }
}

private struct DotLabel: LabelStyle {
    let color: Color
    func makeBody(configuration: Configuration) -> some View {
        HStack(spacing: 7) {
            Circle().fill(color).frame(width: 8, height: 8)
            configuration.title.foregroundStyle(color)
        }
    }
}

private struct DecisionChip: View {
    let decision: ReviewDecision
    let selected: Bool
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            HStack(spacing: 5) {
                Image(systemName: selected && decision != .pending ? decision.symbol + ".fill" : decision.symbol)
                    .font(.system(size: 12)).foregroundStyle(decision.color)
                Text(decision.rawValue).font(LumeFont.ui(11.5, weight: selected ? .semibold : .regular))
                    .foregroundStyle(LumeTheme.ink).lineLimit(1).fixedSize()
            }.padding(.horizontal, 9).frame(maxWidth: .infinity, minHeight: 28)
                .background(Capsule().fill(selected ? LumeTheme.wash : LumeTheme.canvas))
                .overlay(Capsule().strokeBorder(selected ? decision.color : LumeTheme.line, lineWidth: selected ? 1.5 : 1))
                .contentShape(Capsule())
        }.buttonStyle(.plain).keyboardShortcut(decision.shortcut, modifiers: .command)
            .help(decision.explanation + " (⌘" + String(decision.shortcut.character) + ")")
            .accessibilityLabel(decision.rawValue + (selected ? ", selecionado" : "") + ". " + decision.explanation)
    }
}

// MARK: - Linha de estado

@MainActor
private struct StatusLine: View {
    @EnvironmentObject private var store: ReviewStore
    var body: some View {
        HStack(spacing: 10) {
            if store.isBusy {
                ProgressView().controlSize(.small)
                Text(store.jobLabel)
                if store.canCancel { Button("Interromper") { store.cancel() }.buttonStyle(.borderless) }
            } else {
                Image(systemName: store.hasUnsavedDecisions ? "exclamationmark.triangle" : "sparkle")
                    .foregroundStyle(store.hasUnsavedDecisions ? LumeTheme.error : LumeTheme.amber)
                Text(store.status).lineLimit(2)
            }
            Spacer(minLength: 12)
            if store.logURL != nil { Button("Ver registro") { store.openLog() }.buttonStyle(.borderless) }
            if store.report != nil {
                Button("Extrair falsos positivos") { store.exportFalsePositives() }.buttonStyle(.borderless)
                    .disabled(store.isBusy || store.falsePositiveCount == 0)
                    .help("Salva em JSON, ao lado do relatório, os alertas marcados como falso positivo, para analisar e corrigir as regras")
                if store.falsePositivesURL != nil {
                    Button("Mostrar no Finder") { store.revealFalsePositives() }.buttonStyle(.borderless)
                        .help("Mostra o arquivo de falsos positivos no Finder")
                }
            }
        }.font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary)
            .padding(.horizontal, 18).padding(.vertical, 9)
            .background(LumeTheme.paper)
            .overlay(alignment: .top) { Rectangle().fill(LumeTheme.line).frame(height: 1) }
    }
}

// MARK: - Folhas

@MainActor
private struct CoverageSheet: View {
    @EnvironmentObject private var store: ReviewStore
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Kicker(title: "Etapas e alcance")
            Text("O que esta leitura cobriu").font(LumeFont.display(28))
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    if let memory = store.report?.metadata.narrativeSummary {
                        Sheet(padding: 16) {
                            VStack(alignment: .leading, spacing: 5) {
                                Text("Memória narrativa").font(LumeFont.ui(14, weight: .semibold))
                                Text("\(memory.scenes) cenas · \(memory.facts) fatos · \(memory.events) eventos").font(LumeFont.ui(13))
                                Text("As ocorrências mostram as evidências comparadas. Cenas e fatos completos ficam no relatório JSON.")
                                    .font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary)
                            }
                        }
                    }
                    ForEach(store.report?.metadata.stages ?? []) { stage in
                        Sheet(padding: 16) {
                            VStack(alignment: .leading, spacing: 5) {
                                HStack {
                                    Text(stage.title).font(LumeFont.ui(14, weight: .semibold))
                                    Spacer()
                                    Text(stage.statusText).font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary)
                                }
                                Text(stage.detail).font(LumeFont.ui(12)).foregroundStyle(LumeTheme.ink.opacity(0.85))
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                        }
                    }
                    ForEach(Array((store.report?.warnings ?? []).enumerated()), id: \.offset) { _, warning in
                        Text(warning).font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary)
                    }
                }.frame(maxWidth: .infinity, alignment: .leading)
            }
            HStack { Spacer(); Button("Concluir") { dismiss() }.buttonStyle(LumeButtonStyle(kind: .primary)).keyboardShortcut(.defaultAction) }
        }.padding(28).frame(width: 640, height: 600).background(LumeTheme.canvas)
            .foregroundStyle(LumeTheme.ink).tint(LumeTheme.accent)
    }
}

@MainActor
private struct KeySheet: View {
    @EnvironmentObject private var store: ReviewStore
    @Environment(\.dismiss) private var dismiss
    @State private var keyText = ""
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(spacing: 14) {
                LumeMark(size: 44)
                VStack(alignment: .leading, spacing: 2) {
                    Kicker(title: "Recursos com IA")
                    Text("Chave da API da Anthropic").font(LumeFont.display(24))
                }
            }
            Text("Crie a chave em console.anthropic.com → API Keys e copie o valor completo logo após criá-la (começa com sk-ant-). Ela fica guardada nas Chaves do macOS, não em arquivos do Lume.")
                .font(LumeFont.ui(12)).foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
            SecureField("sk-ant-…", text: $keyText).textFieldStyle(.roundedBorder)
            if let error = store.errorText {
                Text(error).font(LumeFont.ui(11)).foregroundStyle(LumeTheme.error).fixedSize(horizontal: false, vertical: true)
            }
            Label("Com a Coerência ou a Auditoria final com IA ligadas, os capítulos ou trechos novos e alterados são enviados à Anthropic, sempre depois da sua confirmação. Pela política atual da API, os dados não são usados para treino por padrão e são apagados em até 30 dias.",
                  systemImage: "hand.raised")
                .font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
            HStack {
                if store.hasAPIKey {
                    Button("Remover chave", role: .destructive) { store.removeAPIKey(); dismiss() }
                        .buttonStyle(LumeButtonStyle())
                }
                Spacer()
                Button("Cancelar") { keyText = ""; store.errorText = nil; dismiss() }
                    .buttonStyle(LumeButtonStyle()).keyboardShortcut(.cancelAction)
                Button("Guardar") {
                    store.saveAPIKey(keyText)
                    keyText = ""
                    if store.hasAPIKey && store.errorText == nil { dismiss() }
                }.buttonStyle(LumeButtonStyle(kind: .primary)).keyboardShortcut(.defaultAction).disabled(keyText.isEmpty)
            }
        }.padding(28).frame(width: 540).background(LumeTheme.canvas)
            .foregroundStyle(LumeTheme.ink).tint(LumeTheme.accent)
    }
}

@MainActor
private struct SearchSettingsView: View {
    @EnvironmentObject private var store: ReviewStore
    @Environment(\.dismiss) private var dismiss
    private enum Section: String, CaseIterable, Identifiable {
        case checks = "Verificações"
        case areas = "Áreas e critérios"
        case structure = "Estrutura"
        var id: String { rawValue }
        var symbol: String {
            switch self {
            case .checks: return "checklist"
            case .areas: return "scope"
            case .structure: return "text.quote"
            }
        }
    }
    @State private var section: Section = .checks
    private var panelHeight: CGFloat {
        min(680, max(440, (NSScreen.main?.visibleFrame.height ?? 840) - 180))
    }
    @State private var titlesText = ""
    @State private var stylesText = ""
    @State private var namesText = ""
    private let scopes = [("narracao", "Narração"), ("dialogo", "Falas"), ("pensamento", "Pensamentos marcados")]

    private func scopeBinding(_ key: String, tense: Bool) -> Binding<Bool> {
        Binding(get: {
            (tense ? store.searchSettings.tenseScopes : store.searchSettings.repetitionScopes).contains(key)
        }, set: { enabled in
            var values = tense ? store.searchSettings.tenseScopes : store.searchSettings.repetitionScopes
            values.removeAll { $0 == key }
            if enabled { values.append(key) }
            if tense { store.searchSettings.tenseScopes = values }
            else { store.searchSettings.repetitionScopes = values }
        })
    }
    private func lines(_ text: String) -> [String] {
        text.components(separatedBy: .newlines).map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }
    }
    private func refreshText() {
        titlesText = store.searchSettings.chapterTitles.joined(separator: "\n")
        stylesText = store.searchSettings.chapterStyles.joined(separator: "\n")
        namesText = store.searchSettings.ignoredNames.joined(separator: "\n")
    }
    private func heading(_ title: String) -> some View { Text(title).font(LumeFont.display(22)) }
    private func subheading(_ title: String) -> some View { Text(title).font(LumeFont.ui(14, weight: .semibold)) }
    private func note(_ text: String) -> some View {
        Text(text).font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
    }
    private func editor(_ text: Binding<String>, height: CGFloat) -> some View {
        TextEditor(text: text).font(LumeFont.ui(12)).scrollContentBackground(.hidden).padding(6).frame(height: height)
            .background(RoundedRectangle(cornerRadius: 10).fill(LumeTheme.canvas))
            .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(LumeTheme.line))
    }

    private var checks: some View {
        VStack(alignment: .leading, spacing: 12) {
            heading("O que procurar")
            note("Cada verificação pode ser ativada separadamente. O modo de leitura (língua, história ou completa) continua limitando quais camadas serão executadas.")
            ForEach(SearchRule.all) { rule in
                Toggle(rule.title, isOn: Binding(get: { store.searchSettings.rules[rule.id] ?? false }, set: { store.searchSettings.rules[rule.id] = $0 }))
                    .font(LumeFont.ui(13))
            }
            HStack {
                Button("Ativar todas") { for rule in SearchRule.all { store.searchSettings.rules[rule.id] = true } }
                Button("Desativar todas") { for rule in SearchRule.all { store.searchSettings.rules[rule.id] = false } }
            }.buttonStyle(LumeButtonStyle())
        }
    }
    private var areas: some View {
        VStack(alignment: .leading, spacing: 14) {
            heading("Onde procurar")
            subheading("Repetições de palavras e frases")
            ForEach(scopes, id: \.0) { key, label in Toggle(label, isOn: scopeBinding(key, tense: false)) }
            Stepper("Distância máxima: \(store.searchSettings.wordDistance) palavras", value: $store.searchSettings.wordDistance, in: 2...40)
            Picker("Limite para palavras", selection: $store.searchSettings.repetitionBoundary) {
                Text("Mesmo trecho").tag("trecho")
                Text("Mesma frase").tag("frase")
            }.pickerStyle(.menu)
            Toggle("Comparar frases também entre parágrafos próximos", isOn: $store.searchSettings.duplicateAcrossParagraphs)
            Picker("Frases repetidas", selection: $store.searchSettings.duplicateSimilarity) {
                Text("Mesmas palavras").tag(1.0)
                Text("Sequências semelhantes").tag(0.85)
            }.pickerStyle(.menu)
            note("A comparação ignora maiúsculas e pontuação. Sequências semelhantes tornam a busca mais sensível.")
            note("A busca não cruza de uma fala para um inciso narrativo ao comparar palavras. Frases entre parágrafos podem pertencer a personagens diferentes; o motor ainda não identifica o falante.")
            Divider()
            subheading("Mudanças de tempo verbal")
            ForEach(scopes, id: \.0) { key, label in Toggle(label, isOn: scopeBinding(key, tense: true)) }
            note("Estrutura e pontuação são verificadas na narração. Continuidade e referências usam o contexto; variações de nomes usam o documento inteiro. O corretor gramatical local mantém suas próprias proteções.")
        }.font(LumeFont.ui(13))
    }
    private var structure: some View {
        VStack(alignment: .leading, spacing: 14) {
            heading("Como o texto está marcado")
            Toggle("Travessão inicial marca diálogo", isOn: $store.searchSettings.dialogueDashes)
            Picker("Trechos entre aspas representam", selection: $store.searchSettings.quotesRole) {
                Text("Falas").tag("dialogo")
                Text("Pensamentos").tag("pensamento")
                Text("Manter como narração").tag("narracao")
            }.pickerStyle(.menu)
            Toggle("Itálico marca pensamento", isOn: $store.searchSettings.italicThoughts)
            note("Essas opções descrevem a marcação, não interpretam o sentido. Itálico pode ter outras funções. Pensamentos sem marcas continuam classificados como narração.")
            Divider()
            subheading("Capítulos")
            Toggle("Reconhecer títulos e numeração automaticamente", isOn: $store.searchSettings.chapterAuto)
            note("Reconhece ‘Capítulo um’, ‘Capítulo 1’ e ‘Capítulo I’, estilos de título e níveis de estrutura. Para uma divisão própria, desative o automático e cadastre os títulos exatos abaixo.")
            Text("Títulos exatos · um por linha")
            editor($titlesText, height: 85).onChange(of: titlesText) { store.searchSettings.chapterTitles = lines($0) }
            Text("Estilos de parágrafo adicionais · um por linha")
            editor($stylesText, height: 65).onChange(of: stylesText) { store.searchSettings.chapterStyles = lines($0) }
            Text("Nomes aceitos que não devem gerar alerta de variação · um por linha")
            editor($namesText, height: 65).onChange(of: namesText) { store.searchSettings.ignoredNames = lines($0) }
        }.font(LumeFont.ui(13))
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 4) {
                Kicker(title: "Ajustar o que procurar")
                Text(store.documentURL?.deletingPathExtension().lastPathComponent ?? "Próxima leitura").font(LumeFont.display(26))
            }
            HStack(spacing: 8) {
                ForEach(Section.allCases) { item in
                    Button { section = item } label: {
                        Label(item.rawValue, systemImage: item.symbol).font(LumeFont.ui(12, weight: .semibold))
                            .lineLimit(1).frame(maxWidth: .infinity, minHeight: 34)
                            .foregroundStyle(section == item ? LumeTheme.linen : LumeTheme.ink)
                            .background(Capsule().fill(section == item ? LumeTheme.night : LumeTheme.paper))
                            .overlay(Capsule().strokeBorder(section == item ? .clear : LumeTheme.line))
                            .contentShape(Capsule())
                    }.buttonStyle(.plain)
                        .accessibilityLabel(item.rawValue)
                        .accessibilityAddTraits(section == item ? .isSelected : [])
                }
            }
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    switch section {
                    case .checks: checks
                    case .areas: areas
                    case .structure: structure
                    }
                }.frame(maxWidth: .infinity, alignment: .leading).padding(20)
            }.id(section).frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(RoundedRectangle(cornerRadius: 18, style: .continuous).fill(LumeTheme.paper))
            if let error = store.errorText {
                HStack {
                    Text(error).font(LumeFont.ui(11)).foregroundStyle(LumeTheme.error).lineLimit(3)
                    Button("Fechar aviso") { store.errorText = nil }.buttonStyle(.borderless).font(LumeFont.ui(11))
                }
            }
            note("As mudanças valem na próxima análise. A configuração é salva para o caminho deste documento; exporte para reutilizar em outro arquivo.")
            HStack {
                Button("Importar…") { store.importSearchSettings(); refreshText() }
                Button("Exportar…") { store.exportSearchSettings() }
                Button("Restaurar padrão") { store.searchSettings = SearchSettings(); refreshText() }
                Spacer()
                Button("Concluir") { store.saveSearchSettings(); dismiss() }
                    .buttonStyle(LumeButtonStyle(kind: .primary)).keyboardShortcut(.defaultAction)
            }.buttonStyle(LumeButtonStyle())
        }.padding(26).frame(width: 740, height: panelHeight)
            .background(LumeTheme.canvas).foregroundStyle(LumeTheme.ink).tint(LumeTheme.accent)
            .onAppear { refreshText() }
            .onDisappear { store.saveSearchSettings() }
    }
}
