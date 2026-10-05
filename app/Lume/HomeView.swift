import SwiftUI
import AppKit

/// Início: sem manuscrito, o convite; com manuscrito, a preparação da leitura.
@MainActor
struct HomeView: View {
    @EnvironmentObject private var store: ReviewStore
    @Binding var showSearchSettings: Bool
    @Binding var showKeySheet: Bool
    let openEngine: () -> Void

    var body: some View {
        if store.documentURL == nil {
            StartView(openEngine: openEngine)
        } else {
            PreparationView(showSearchSettings: $showSearchSettings, showKeySheet: $showKeySheet, openEngine: openEngine)
        }
    }

    static var greeting: String {
        switch Calendar.current.component(.hour, from: Date()) {
        case 5..<12: return "Bom dia."
        case 12..<18: return "Boa tarde."
        default: return "Boa noite."
        }
    }

    static var appVersion: String {
        Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "—"
    }
}

/// Aceita um manuscrito arrastado do Finder.
private struct ManuscriptDrop: ViewModifier {
    @EnvironmentObject private var store: ReviewStore
    @Binding var targeted: Bool
    func body(content: Content) -> some View {
        content.onDrop(of: [.fileURL], isTargeted: $targeted) { providers in
            guard !store.isBusy, let provider = providers.first else { return false }
            _ = provider.loadObject(ofClass: URL.self) { url, _ in
                guard let url else { return }
                Task { @MainActor in store.openDocument(url) }
            }
            return true
        }
    }
}

/// Aviso quando não há motor pronto: o Motor é onde se resolve.
private struct EngineMissingNotice: View {
    let openEngine: () -> Void
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: "gearshape").font(.system(size: 15)).foregroundStyle(LumeTheme.amber)
            VStack(alignment: .leading, spacing: 2) {
                Text("Antes de começar, prepare o motor de análise.").font(LumeFont.ui(13, weight: .semibold))
                Text("O FONTE ainda não está disponível nesta instalação.").font(LumeFont.ui(11.5))
                    .foregroundStyle(LumeTheme.secondary)
            }
            Spacer()
            Button("Abrir Motor", action: openEngine).buttonStyle(LumeButtonStyle())
        }.padding(14)
            .background(RoundedRectangle(cornerRadius: LumeRadius.large).fill(LumeTheme.glow.opacity(0.5)))
            .overlay(RoundedRectangle(cornerRadius: LumeRadius.large).strokeBorder(LumeTheme.glowLine.opacity(0.5)))
    }
}

// MARK: - Início vazio

@MainActor
private struct StartView: View {
    @EnvironmentObject private var store: ReviewStore
    let openEngine: () -> Void
    @State private var dropTargeted = false

    var body: some View {
        ScrollView {
            VStack(spacing: 0) {
                LumeMark(size: 64, glowing: true).padding(.top, 48)
                HStack(spacing: 6) {
                    FlameGlyph(size: 11)
                    Text(HomeView.greeting).font(LumeFont.ui(12.5, weight: .medium)).foregroundStyle(LumeTheme.secondary)
                }.padding(.horizontal, 10).padding(.vertical, 4)
                    .background(RoundedRectangle(cornerRadius: LumeRadius.medium).fill(LumeTheme.sunken))
                    .padding(.top, 22)
                Text("Que texto vamos iluminar hoje?").font(LumeFont.display(34, weight: .semibold))
                    .multilineTextAlignment(.center).padding(.top, 14)
                Text("“Uma luz acesa ao lado de quem escreve.”").font(LumeFont.display(17)).italic()
                    .foregroundStyle(LumeTheme.secondary).padding(.top, 8)
                card.padding(.top, 34)
                if !store.pythonExists {
                    EngineMissingNotice(openEngine: openEngine).frame(maxWidth: 640).padding(.top, 16)
                }
                footer.padding(.top, 40).padding(.bottom, 28)
            }.frame(maxWidth: .infinity).padding(.horizontal, 32)
        }.background(LumeTheme.canvas)
            .modifier(ManuscriptDrop(targeted: $dropTargeted))
    }

    private var card: some View {
        VStack(spacing: 0) {
            Rectangle().fill(LinearGradient(colors: [.clear, LumeTheme.candle.opacity(0.8), .clear],
                                            startPoint: .leading, endPoint: .trailing)).frame(height: 2)
            VStack(spacing: 14) {
                ZStack(alignment: .topTrailing) {
                    Image(systemName: "doc.text").font(.system(size: 22, weight: .light))
                        .frame(width: 54, height: 54)
                        .background(Circle().fill(LumeTheme.sunken))
                    FlameGlyph(size: 12).offset(x: 4, y: -4)
                }.padding(.top, 28)
                VStack(spacing: 5) {
                    Text("Traga seu manuscrito").font(LumeFont.ui(17, weight: .semibold))
                    Text("Arraste o arquivo para esta mesa ou escolha no Finder.")
                        .font(LumeFont.ui(13)).foregroundStyle(LumeTheme.secondary)
                }
                HStack(spacing: 10) {
                    Button { store.chooseDocument() } label: { Label("Escolher manuscrito", systemImage: "folder") }
                        .buttonStyle(LumeButtonStyle(kind: .primary)).keyboardShortcut("o", modifiers: .command)
                    Button { store.chooseReport() } label: { Label("Abrir relatório", systemImage: "doc.plaintext") }
                        .buttonStyle(LumeButtonStyle())
                }.disabled(store.isBusy).padding(.top, 6)
                Divider().overlay(LumeTheme.line).padding(.top, 14)
                VStack(spacing: 7) {
                    HStack(spacing: 8) {
                        Kicker(title: "Formatos", color: LumeTheme.amber)
                        Text("Word (.docx) e Pages (.pages)").font(LumeFont.ui(12))
                    }
                    Label("As análises do FONTE acontecem neste Mac.", systemImage: "lock")
                        .font(LumeFont.ui(12)).foregroundStyle(LumeTheme.ink)
                    Text("A Coerência e a Auditoria final com IA são opcionais e só enviam trechos à Anthropic depois da sua confirmação.")
                        .font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary).multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                }.padding(.top, 4).padding(.bottom, 26)
            }.padding(.horizontal, 36)
        }.frame(maxWidth: 640)
            .background(RoundedRectangle(cornerRadius: LumeRadius.large).fill(dropTargeted ? LumeTheme.wash : LumeTheme.raised))
            .overlay(RoundedRectangle(cornerRadius: LumeRadius.large)
                .strokeBorder(dropTargeted ? LumeTheme.accent : LumeTheme.line, lineWidth: dropTargeted ? 1.5 : 1))
            .clipShape(RoundedRectangle(cornerRadius: LumeRadius.large))
    }

    private var footer: some View {
        HStack(spacing: 8) {
            Circle().fill(store.pythonExists ? LumeTheme.glowLine : LumeTheme.tertiary).frame(width: 6, height: 6)
            Text(store.embeddedEngine.map { "FONTE \($0.version)" } ?? store.engineDescription)
            Text("·")
            Text("Análise local neste Mac")
            Text("·")
            Text("Versão \(HomeView.appVersion)")
        }.font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary)
    }
}

// MARK: - Preparação

@MainActor
private struct PreparationView: View {
    @EnvironmentObject private var store: ReviewStore
    @Binding var showSearchSettings: Bool
    @Binding var showKeySheet: Bool
    let openEngine: () -> Void
    @State private var dropTargeted = false

    private var activeRules: Int { SearchRule.all.filter { store.searchSettings.rules[$0.id] ?? false }.count }
    private var sendsToAI: Bool { store.coherenceActive || store.auditActive }

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 26) {
                    header
                    if !store.pythonExists { EngineMissingNotice(openEngine: openEngine) }
                    modes
                    HStack(alignment: .top, spacing: 16) {
                        LanguagePanel()
                        StoryPanel(showKeySheet: $showKeySheet)
                    }
                    AuditPanel(showKeySheet: $showKeySheet)
                }.disabled(store.isBusy)
                    .frame(maxWidth: 1040).padding(.horizontal, 36).padding(.vertical, 30)
                    .frame(maxWidth: .infinity)
            }
            actions
        }.background(LumeTheme.canvas)
    }

    private var header: some View {
        HStack(alignment: .top, spacing: 24) {
            VStack(alignment: .leading, spacing: 6) {
                Text(HomeView.greeting).font(LumeFont.display(34, weight: .semibold))
                Text("Tudo pronto para uma leitura atenta.").font(LumeFont.display(19)).foregroundStyle(LumeTheme.secondary)
            }
            Spacer(minLength: 16)
            manuscriptCard.frame(maxWidth: 400)
        }
    }

    private var manuscriptCard: some View {
        Button { store.chooseDocument() } label: {
            HStack(spacing: 14) {
                Image(systemName: "doc.text").font(.system(size: 20, weight: .light))
                    .frame(width: 42, height: 42)
                    .background(RoundedRectangle(cornerRadius: LumeRadius.medium).fill(LumeTheme.sunken))
                VStack(alignment: .leading, spacing: 3) {
                    if let url = store.documentURL {
                        Text(url.lastPathComponent).font(LumeFont.ui(13.5, weight: .semibold)).lineLimit(1)
                            .truncationMode(.middle)
                    }
                    Text("Clique ou arraste outro manuscrito para trocar. O arquivo nunca é alterado pela análise.")
                        .font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
                }
                Spacer(minLength: 4)
                Image(systemName: "arrow.left.arrow.right").foregroundStyle(LumeTheme.secondary)
            }.padding(12)
                .background(RoundedRectangle(cornerRadius: LumeRadius.large).fill(dropTargeted ? LumeTheme.wash : LumeTheme.raised))
                .overlay(RoundedRectangle(cornerRadius: LumeRadius.large)
                    .strokeBorder(dropTargeted ? LumeTheme.accent : LumeTheme.line))
                .contentShape(RoundedRectangle(cornerRadius: LumeRadius.large))
        }.buttonStyle(.plain).accessibilityLabel("Trocar manuscrito")
            .modifier(ManuscriptDrop(targeted: $dropTargeted))
    }

    private var modes: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline) {
                Text("Como você quer ler?").font(LumeFont.display(22, weight: .semibold))
                Spacer()
                Button { showSearchSettings = true } label: {
                    HStack(spacing: 6) {
                        Image(systemName: "slider.horizontal.3")
                        Text("Ajustar o que procurar…")
                        Text("\(activeRules) de \(SearchRule.all.count)").font(LumeFont.ui(11)).monospacedDigit()
                            .foregroundStyle(LumeTheme.secondary)
                    }
                }.buttonStyle(LumeButtonStyle(kind: .soft))
                    .help("Verificações ativas, áreas e marcação do texto para a próxima leitura")
            }
            HStack(spacing: 12) {
                ModeCard(tag: "linguistica", title: "A língua", symbol: "textformat",
                         detail: "Ortografia, gramática, pontuação e tempo verbal.",
                         note: "Etapas linguística e morfossintática")
                ModeCard(tag: "editorial", title: "A história", symbol: "book",
                         detail: "Repetições, continuidade e Coerência com IA quando ligada.",
                         note: "Etapas de contexto curto e coerência global")
                ModeCard(tag: "ambas", title: "Leitura completa", symbol: "text.magnifyingglass",
                         detail: "A língua e a história, numa só passada.",
                         note: "Todas as etapas")
            }
        }
    }

    private var actions: some View {
        HStack(spacing: 14) {
            Image(systemName: "lock").foregroundStyle(LumeTheme.amber)
                .frame(width: 30, height: 30).background(Circle().fill(LumeTheme.glow.opacity(0.6)))
            VStack(alignment: .leading, spacing: 1) {
                Text("Seu texto, no seu Mac.").font(LumeFont.ui(13, weight: .semibold))
                Text(sendsToAI ? "Só os trechos que você confirmar seguem para a Anthropic."
                               : "O FONTE lê o manuscrito neste Mac e não o altera.")
                    .font(LumeFont.ui(11.5)).foregroundStyle(LumeTheme.secondary)
            }
            Spacer()
            if store.report != nil {
                Button("Retomar relatório aberto") { store.resumeReview() }
                    .buttonStyle(LumeButtonStyle()).disabled(store.isBusy)
            }
            Button { store.analyze() } label: {
                HStack(spacing: 8) { Text("Começar a leitura"); Image(systemName: "arrow.right") }
            }.buttonStyle(LumeButtonStyle(kind: .primary)).disabled(!store.canAnalyze)
                .keyboardShortcut(.return, modifiers: .command)
        }.padding(.horizontal, 36).padding(.vertical, 14)
            .background(LumeTheme.surface)
            .overlay(alignment: .top) { Rectangle().fill(LumeTheme.line).frame(height: 1) }
    }
}

/// Um dos três modos de leitura; a lógica dos modos continua no `ReviewStore` (`analysisMode`).
@MainActor
private struct ModeCard: View {
    @EnvironmentObject private var store: ReviewStore
    let tag: String
    let title: String
    let symbol: String
    let detail: String
    let note: String

    var body: some View {
        let selected = store.analysisMode == tag
        Button { store.analysisMode = tag } label: {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Image(systemName: symbol).font(.system(size: 15)).foregroundStyle(selected ? LumeTheme.amber : LumeTheme.secondary)
                    Text(title).font(LumeFont.ui(14, weight: .semibold))
                    Spacer()
                    Image(systemName: selected ? "largecircle.fill.circle" : "circle")
                        .foregroundStyle(selected ? LumeTheme.accent : LumeTheme.lineStrong)
                }
                Text(detail).font(LumeFont.ui(12.5)).foregroundStyle(LumeTheme.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: 0)
                Text(note).font(LumeFont.ui(11)).foregroundStyle(LumeTheme.tertiary)
            }.padding(14).frame(maxWidth: .infinity, minHeight: 124, alignment: .topLeading)
                .background(RoundedRectangle(cornerRadius: LumeRadius.large).fill(selected ? LumeTheme.raised : LumeTheme.surface))
                .overlay(RoundedRectangle(cornerRadius: LumeRadius.large)
                    .strokeBorder(selected ? LumeTheme.accent : LumeTheme.line, lineWidth: selected ? 1.5 : 1))
                .contentShape(RoundedRectangle(cornerRadius: LumeRadius.large))
        }.buttonStyle(.plain)
            .accessibilityLabel(title + ". " + detail).accessibilityAddTraits(selected ? .isSelected : [])
    }
}

/// Cabeçalho comum dos painéis de preparação.
private struct PanelHeader: View {
    let title: String
    let symbol: String
    var tag: String? = nil
    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: symbol).font(.system(size: 14)).foregroundStyle(LumeTheme.amber)
            Text(title).font(LumeFont.ui(14, weight: .semibold))
            Spacer()
            if let tag {
                Text(tag).font(LumeFont.ui(10.5, weight: .medium)).foregroundStyle(LumeTheme.secondary)
                    .padding(.horizontal, 6).padding(.vertical, 2)
                    .background(RoundedRectangle(cornerRadius: LumeRadius.small).fill(LumeTheme.sunken))
            }
        }
    }
}

/// Bloco interno dos painéis.
private struct Inset<Content: View>: View {
    @ViewBuilder var content: Content
    var body: some View {
        content.padding(12).frame(maxWidth: .infinity, alignment: .leading)
            .background(RoundedRectangle(cornerRadius: LumeRadius.medium).fill(LumeTheme.raised))
            .overlay(RoundedRectangle(cornerRadius: LumeRadius.medium).strokeBorder(LumeTheme.line))
    }
}

/// Estado da chave da Anthropic, compartilhada pela Coerência e pela Auditoria.
@MainActor
private struct KeyStatusRow: View {
    @EnvironmentObject private var store: ReviewStore
    @Binding var showKeySheet: Bool
    var body: some View {
        HStack(spacing: 8) {
            Label(store.hasAPIKey ? "Chave guardada nas Chaves do macOS" : "Chave ainda não configurada",
                  systemImage: store.hasAPIKey ? "key" : "exclamationmark.triangle")
                .font(LumeFont.ui(11.5)).foregroundStyle(store.hasAPIKey ? LumeTheme.secondary : LumeTheme.rose)
            Spacer()
            Button(store.hasAPIKey ? "Trocar…" : "Configurar…") { showKeySheet = true }
                .buttonStyle(LumeButtonStyle(kind: .soft))
        }
    }
}

/// Teto em dólares por análise.
private struct BudgetField: View {
    @Binding var value: Double
    var body: some View {
        HStack(spacing: 6) {
            Text("Teto por análise").font(LumeFont.ui(12))
            Spacer()
            Text("US$").font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary)
            TextField("1,00", value: $value, format: .number.precision(.fractionLength(2)))
                .textFieldStyle(.roundedBorder).frame(width: 70).multilineTextAlignment(.trailing)
        }
    }
}

@MainActor
private struct LanguagePanel: View {
    @EnvironmentObject private var store: ReviewStore
    var body: some View {
        let off = store.analysisMode == "editorial"
        Panel {
            VStack(alignment: .leading, spacing: 12) {
                PanelHeader(title: "A língua", symbol: "textformat")
                Inset {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Em que tempo o livro é narrado?").font(LumeFont.ui(13, weight: .medium))
                        Text("Um tempo diferente do texto gera muitos alertas falsos de tempo verbal.")
                            .font(LumeFont.ui(11.5)).foregroundStyle(LumeTheme.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                        Picker("Tempo da narração", selection: $store.tense) {
                            Text("Passado").tag("passado")
                            Text("Presente").tag("presente")
                        }.pickerStyle(.segmented).labelsHidden()
                    }
                }
                Inset {
                    OptionRow(title: "Corretor gramatical local", detail: "LanguageTool neste Mac, sem internet.") {
                        Toggle("Corretor gramatical local", isOn: $store.useLanguageTool).toggleStyle(.switch).labelsHidden()
                    }
                }.help("Ortografia e gramática com o LanguageTool incluído no motor, executado neste Mac, sem internet. Motores sem o corretor embutido exigem um servidor LanguageTool iniciado separadamente na porta 8081.")
            }
        }.disabled(off).opacity(off ? 0.5 : 1)
    }
}

@MainActor
private struct StoryPanel: View {
    @EnvironmentObject private var store: ReviewStore
    @Binding var showKeySheet: Bool
    var body: some View {
        let off = store.analysisMode == "linguistica"
        Panel {
            VStack(alignment: .leading, spacing: 12) {
                PanelHeader(title: "A história", symbol: "book", tag: "IA opcional")
                Inset {
                    VStack(alignment: .leading, spacing: 10) {
                        OptionRow(title: "Coerência com IA (Claude)",
                                  detail: "Contradições entre cenas. Só capítulos alterados são enviados, com custo mostrado antes.") {
                            Toggle("Coerência com IA", isOn: $store.useCoherenceAI).toggleStyle(.switch).labelsHidden()
                        }.help("Contradições narrativas analisadas pela API do Claude. Só os capítulos alterados são enviados à Anthropic; antes do envio, o Lume mostra o custo estimado e pede confirmação.")
                        if store.useCoherenceAI {
                            Divider().overlay(LumeTheme.line)
                            Picker("Modelo", selection: $store.coherenceModel) {
                                Text("Sonnet 5.5 · recomendado").tag("claude-sonnet-5-5")
                                Text("Opus 5.5 · custa o dobro").tag("claude-opus-5-5")
                            }.pickerStyle(.segmented).font(LumeFont.ui(12))
                            BudgetField(value: $store.coherenceBudget)
                            KeyStatusRow(showKeySheet: $showKeySheet)
                        }
                    }
                }
                Inset {
                    VStack(alignment: .leading, spacing: 8) {
                        OptionRow(title: "Comparar com uma versão anterior", detail: "Opcional: procura vestígios de cortes.") {
                            if store.originalURL == nil {
                                Button("Escolher original…") { store.chooseOriginal() }
                                    .buttonStyle(LumeButtonStyle(kind: .soft)).disabled(store.documentURL == nil)
                            }
                        }
                        if let original = store.originalURL {
                            HStack {
                                Label(original.lastPathComponent, systemImage: "doc.on.doc").font(LumeFont.ui(12)).lineLimit(1)
                                    .truncationMode(.middle)
                                Spacer()
                                Button("Trocar…") { store.chooseOriginal() }
                                Button("Remover") { store.originalURL = nil }
                            }.buttonStyle(LumeButtonStyle(kind: .soft))
                        }
                    }
                }
            }
        }.disabled(off).opacity(off ? 0.5 : 1)
    }
}

/// Auditoria final com IA: vale para os três modos; desligada por padrão porque custa dinheiro.
@MainActor
struct AuditPanel: View {
    @EnvironmentObject private var store: ReviewStore
    @Binding var showKeySheet: Bool
    var body: some View {
        Panel {
            VStack(alignment: .leading, spacing: 12) {
                PanelHeader(title: "Auditoria final", symbol: "text.magnifyingglass", tag: "Opcional · custa dinheiro")
                Inset {
                    VStack(alignment: .leading, spacing: 10) {
                        OptionRow(title: "Auditoria final com IA (Claude)",
                                  detail: "Uma última leitura procura o que as regras deixaram passar. Só trechos novos ou alterados são enviados, com o custo mostrado antes.") {
                            Toggle("Auditoria final com IA", isOn: $store.useAuditAI).toggleStyle(.switch).labelsHidden()
                        }.help("Depois das outras etapas, o Claude relê cada capítulo com os alertas já encontrados e aponta só problemas novos, como suspeitas para você avaliar. Antes do envio, o Lume mostra o custo estimado e pede confirmação.")
                        if store.useAuditAI {
                            Divider().overlay(LumeTheme.line)
                            Picker("Modelo", selection: $store.auditModel) {
                                Text("Opus 5.5 · recomendado").tag("claude-opus-5-5")
                                Text("Sonnet 5.5 · custa a metade").tag("claude-sonnet-5-5")
                            }.pickerStyle(.segmented).font(LumeFont.ui(12)).frame(maxWidth: 520, alignment: .leading)
                            BudgetField(value: $store.auditBudget).frame(maxWidth: 520)
                            KeyStatusRow(showKeySheet: $showKeySheet)
                            Text("Antes do envio, o Lume mostra o custo estimado e pede sua confirmação.")
                                .font(LumeFont.ui(11)).italic().foregroundStyle(LumeTheme.secondary)
                        }
                    }
                }
            }
        }
    }
}
