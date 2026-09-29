import SwiftUI
import AppKit

@MainActor
struct ContentView: View {
    @EnvironmentObject private var store: ReviewStore
    @State private var showSetup = false
    @State private var showSearchSettings = false
    @State private var showCoverage = false
    @State private var showKeySheet = false
    @State private var keyText = ""

    var body: some View {
        VStack(spacing: 0) {
            if store.screen == .preparation {
                preparation
            } else {
                reviewDesk
            }
            statusBar
        }
        .tint(LumeTheme.accent)
        .foregroundStyle(LumeTheme.ink)
        .background(LumeTheme.canvas)
        .toolbar {
            ToolbarItemGroup {
                if store.screen == .review {
                    Button { store.showPreparation() } label: {
                        Label("Preparar análise", systemImage: "arrow.left")
                    }.disabled(store.isBusy)
                }
                Button { store.chooseReport() } label: { Label("Abrir relatório", systemImage: "folder") }
                    .disabled(store.isBusy)
                if store.report != nil {
                    Button { store.exportDecisions() } label: { Label("Exportar decisões", systemImage: "square.and.arrow.up") }
                        .disabled(store.isBusy)
                    Menu {
                        Button("Importar decisões…") { store.importDecisions() }
                        Divider()
                        Button("Mostrar relatório no Finder") { store.revealReport() }
                        Button("Abrir relatório HTML") { store.openHTML() }
                    } label: { Label("Mais opções", systemImage: "ellipsis.circle") }
                        .disabled(store.isBusy)
                }
            }
        }
        .sheet(isPresented: $showSearchSettings) {
            SearchSettingsView().environmentObject(store)
        }
        .sheet(isPresented: $showCoverage) {
            VStack(alignment: .leading, spacing: 18) {
                Text("Etapas e alcance da revisão").font(.title2)
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        if let memory = store.report?.metadata.narrativeSummary {
                            VStack(alignment: .leading, spacing: 5) {
                                Text("Memória narrativa").font(.headline)
                                Text("\(memory.scenes) cenas · \(memory.facts) fatos · \(memory.events) eventos")
                                Text("As ocorrências mostram as evidências comparadas. Cenas e fatos completos ficam no relatório JSON.").font(.caption).foregroundStyle(LumeTheme.secondary)
                            }
                        }
                        ForEach(store.report?.metadata.stages ?? []) { stage in
                            VStack(alignment: .leading, spacing: 5) {
                                Text(stage.title + " · " + stage.statusText).font(.headline)
                                Text(stage.detail).font(.callout)
                            }
                        }
                        ForEach(Array((store.report?.warnings ?? []).enumerated()), id: \.offset) { _, warning in
                            Text(warning).font(.caption).foregroundStyle(LumeTheme.secondary)
                        }
                    }.frame(maxWidth: .infinity, alignment: .leading)
                }
                Button("Concluir") { showCoverage = false }.keyboardShortcut(.defaultAction)
            }.padding(26).frame(width: 620, height: 580)
        }
        .sheet(isPresented: $showKeySheet) {
            VStack(alignment: .leading, spacing: 14) {
                Text("Chave da API da Anthropic").font(.title2)
                Text("Crie a chave em console.anthropic.com → API Keys e copie o valor completo logo após criá-la (começa com sk-ant-). Ela fica guardada nas Chaves do macOS, não em arquivos do Lume.")
                    .font(.callout).foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
                SecureField("sk-ant-…", text: $keyText)
                Text("Com a Coerência com IA ligada, os capítulos alterados são enviados à Anthropic. Pela política atual da API, os dados não são usados para treino por padrão e são apagados em até 30 dias.")
                    .font(.caption).foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
                HStack {
                    if store.hasAPIKey {
                        Button("Remover chave", role: .destructive) { store.removeAPIKey(); showKeySheet = false }
                    }
                    Spacer()
                    Button("Cancelar") { keyText = ""; showKeySheet = false }.keyboardShortcut(.cancelAction)
                    Button("Guardar") {
                        store.saveAPIKey(keyText)
                        keyText = ""
                        if store.hasAPIKey && store.errorText == nil { showKeySheet = false }
                    }.keyboardShortcut(.defaultAction).disabled(keyText.isEmpty)
                }
            }.padding(24).frame(width: 520)
        }
        .alert("Enviar à Anthropic?", isPresented: Binding(get: { store.coherenceEstimate != nil },
                                                           set: { if !$0 { store.coherenceEstimate = nil } })) {
            Button("Cancelar", role: .cancel) { store.cancelCoherence() }
            Button("Enviar e analisar") { store.confirmCoherence() }
        } message: {
            Text((store.coherenceEstimate?.summary ?? "") + String(format: "\nTeto desta análise: US$ %.2f.", store.coherenceBudget))
        }
        .alert("Lume", isPresented: Binding(get: { store.errorText != nil && !showSearchSettings }, set: { if !$0 { store.errorText = nil } })) {
            Button("OK", role: .cancel) { store.errorText = nil }
        } message: { Text(store.errorText ?? "") }
    }

    private var documentName: String {
        store.documentURL?.lastPathComponent ?? store.report?.document ?? "Escolha um manuscrito para começar"
    }

    private func card<Content: View>(_ title: String, symbol: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 18) {
            Label(title, systemImage: symbol).font(.system(size: 21, design: .serif))
            content()
        }.padding(26).frame(maxWidth: .infinity, alignment: .topLeading)
            .background(RoundedRectangle(cornerRadius: 16).fill(LumeTheme.paper))
            .overlay(RoundedRectangle(cornerRadius: 16).strokeBorder(LumeTheme.line))
    }

    private var preparation: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 26) {
                    HStack(alignment: .center, spacing: 22) {
                        LumeMark(size: 76)
                        VStack(alignment: .leading, spacing: 7) {
                            Text("lume").font(.system(size: 46, design: .serif)).tracking(-1.5)
                            Text("Prepare uma nova leitura.").font(.system(size: 24, design: .serif))
                            Text("Escolha o manuscrito e o que deseja verificar. Depois, siga para a Mesa de revisão.")
                                .font(.callout).foregroundStyle(LumeTheme.secondary)
                        }
                        Spacer(minLength: 0)
                    }.padding(.vertical, 12)
                    HStack(alignment: .top, spacing: 24) {
                        documentCard
                        analysisCard
                    }.disabled(store.isBusy)
                    if !store.pythonExists {
                        Text("Prepare ou selecione o motor abaixo para habilitar a análise.")
                            .font(.callout).foregroundStyle(LumeTheme.secondary)
                    }
                    engineControls
                }.frame(maxWidth: 1040).padding(36).frame(maxWidth: .infinity)
            }
            Divider()
            preparationActions
        }.background(LumeTheme.canvas)
            .onAppear { showSetup = !store.pythonExists }
    }

    private var preparationActions: some View {
        HStack(spacing: 18) {
            Label("Seu texto, no seu Mac.", systemImage: "lock.shield")
                .font(.caption).foregroundStyle(LumeTheme.secondary)
            Spacer()
            if store.report != nil {
                Button("Retomar relatório aberto") { store.resumeReview() }
                    .buttonStyle(LumeButtonStyle()).disabled(store.isBusy)
            }
            Button { store.analyze() } label: {
                Label("Analisar manuscrito", systemImage: "arrow.right")
            }.buttonStyle(LumeButtonStyle(prominent: true)).disabled(!store.canAnalyze)
        }.frame(maxWidth: 1040).padding(.horizontal, 36).padding(.vertical, 16)
            .frame(maxWidth: .infinity).background(LumeTheme.paper)
    }

    private var documentCard: some View {
        card("1 · Manuscrito", symbol: "doc.text") {
            VStack(alignment: .leading, spacing: 10) {
                Text(store.documentURL?.lastPathComponent ?? "Nenhum manuscrito selecionado")
                    .font(.headline).lineLimit(3).textSelection(.enabled)
                Text("Use um arquivo Word (.docx). No Pages, exporte uma cópia para Word.")
                    .font(.callout).foregroundStyle(LumeTheme.secondary)
                Button(store.documentURL == nil ? "Escolher manuscrito…" : "Trocar manuscrito…") { store.chooseDocument() }
                    .buttonStyle(LumeButtonStyle())
            }
            if store.analysisMode != "linguistica" {
                Divider()
                Text("Comparação com original").font(.headline)
                Text("Opcional: acrescente a versão anterior para procurar possíveis vestígios de cortes.")
                    .font(.callout).foregroundStyle(LumeTheme.secondary)
                if let original = store.originalURL {
                    Text(original.lastPathComponent).font(.callout).lineLimit(3)
                    HStack {
                        Button("Trocar original…") { store.chooseOriginal() }
                        Button("Remover") { store.originalURL = nil }
                    }.buttonStyle(LumeButtonStyle())
                } else {
                    Button("Escolher original…") { store.chooseOriginal() }
                        .buttonStyle(LumeButtonStyle()).disabled(store.documentURL == nil)
                }
            }
        }
    }

    private var analysisCard: some View {
        card("2 · Busca", symbol: "slider.horizontal.3") {
            VStack(alignment: .leading, spacing: 8) {
                Text("Tipo de análise").font(.headline)
                Picker("Tipo de análise", selection: $store.analysisMode) {
                    Text("Linguística").tag("linguistica")
                    Text("Editorial").tag("editorial")
                    Text("Ambas").tag("ambas")
                }.labelsHidden().pickerStyle(.segmented).frame(maxWidth: .infinity)
            }
            VStack(alignment: .leading, spacing: 8) {
                Text("Tempo da narrativa").font(.headline)
                Picker("Tempo da narrativa", selection: $store.tense) {
                    Text("Passado").tag("passado")
                    Text("Presente").tag("presente")
                    Text("Automático").tag("auto")
                }.labelsHidden().pickerStyle(.segmented).frame(maxWidth: .infinity)
            }.disabled(store.analysisMode == "editorial")
            Divider()
            Text("Critérios do manuscrito").font(.headline)
            Text("Escolha as verificações, áreas de busca e marcações usadas no texto.")
                .font(.callout).foregroundStyle(LumeTheme.secondary)
            Button("Configurar busca…") { showSearchSettings = true }
                .buttonStyle(LumeButtonStyle()).disabled(store.documentURL == nil)
            Toggle("Corretor gramatical local", isOn: $store.useLanguageTool)
                .font(.callout).disabled(store.analysisMode == "editorial")
                .help("Ortografia e gramática com o LanguageTool incluído no motor, executado neste Mac, sem internet. Motores sem o corretor embutido exigem um servidor LanguageTool iniciado separadamente na porta 8081.")
            Toggle("Coerência com IA (Claude)", isOn: $store.useCoherenceAI)
                .font(.callout).disabled(store.analysisMode == "linguistica")
                .help("Contradições narrativas analisadas pela API do Claude, no lugar da memória narrativa local. Só os capítulos alterados são enviados à Anthropic; antes do envio, o Lume mostra o custo estimado e pede confirmação.")
            if store.useCoherenceAI {
                VStack(alignment: .leading, spacing: 8) {
                    Picker("Modelo", selection: $store.coherenceModel) {
                        Text("Sonnet 5.5 · recomendado").tag("claude-sonnet-5-5")
                        Text("Opus 5.5 · mais forte, custa o dobro").tag("claude-opus-5-5")
                    }.font(.callout)
                    HStack {
                        Text("Teto por análise (US$)").font(.callout)
                        TextField("1,00", value: $store.coherenceBudget, format: .number.precision(.fractionLength(2)))
                            .frame(width: 70).multilineTextAlignment(.trailing)
                    }
                    HStack {
                        Label(store.hasAPIKey ? "Chave configurada" : "Chave não configurada",
                              systemImage: store.hasAPIKey ? "checkmark.seal" : "exclamationmark.triangle")
                            .font(.caption).foregroundStyle(store.hasAPIKey ? LumeTheme.secondary : Color.orange)
                        Spacer()
                        Button(store.hasAPIKey ? "Trocar chave…" : "Configurar chave…") { showKeySheet = true }
                            .font(.caption)
                    }
                }.padding(.leading, 20).disabled(store.analysisMode == "linguistica")
            }
        }
    }

    private var engineControls: some View {
        DisclosureGroup(isExpanded: $showSetup) {
            VStack(alignment: .leading, spacing: 14) {
                Text(store.engineDescription).font(.callout).foregroundStyle(LumeTheme.secondary)
                if store.embeddedEngine != nil {
                    HStack {
                        Button("Instalar atualização…") { store.importEngine() }
                        Button("Verificar motor") { store.diagnose() }
                        Button("Voltar à versão anterior") { store.rollbackEngine() }
                        Button("Restaurar embutido") { store.resetEngine() }
                    }.buttonStyle(LumeButtonStyle())
                } else {
                    Text(store.backendURL?.lastPathComponent ?? "Selecione a pasta Analisador ou monte o aplicativo completo.")
                        .font(.caption).foregroundStyle(LumeTheme.secondary)
                    HStack {
                        Button("Selecionar pasta…") { store.chooseBackend() }
                        Button("Preparar") { store.install() }.disabled(store.backendURL == nil)
                        Button("Verificar") { store.diagnose() }.disabled(!store.pythonExists)
                    }.buttonStyle(LumeButtonStyle())
                }
            }.padding(.top, 14)
        } label: {
            Label("Motor de análise", systemImage: "gearshape").font(.callout)
        }.padding(20).background(RoundedRectangle(cornerRadius: 12).fill(LumeTheme.paper))
            .disabled(store.isBusy)
    }

    private var reviewDesk: some View {
        VStack(spacing: 0) {
            HStack(spacing: 20) {
                VStack(alignment: .leading, spacing: 5) {
                    Eyebrow(title: "Mesa de revisão")
                    Text(store.isAnalyzing ? documentName : (store.report?.document ?? documentName))
                        .font(.system(size: 20, design: .serif)).lineLimit(1).help(documentName)
                }
                Spacer(minLength: 12)
                if let report = store.report, !store.isAnalyzing, !store.analysisFailed {
                    Button("Etapas e alcance") { showCoverage = true }
                    Text("\(report.findings.count - store.pendingCount) de \(report.findings.count) avaliados")
                        .font(.callout).foregroundStyle(LumeTheme.secondary)
                    if let chapters = report.metadata.chapters {
                        Menu("Capítulos · \(chapters.count)") {
                            if chapters.isEmpty { Text("Nenhum título identificado") }
                            ForEach(Array(chapters.enumerated()), id: \.offset) { _, chapter in
                                Text("§ \(chapter.paragraph) · \(chapter.title)")
                            }
                        }.fixedSize()
                    }
                }
            }.padding(.horizontal, 26).padding(.vertical, 18).background(LumeTheme.paper)
            Divider()
            if store.isAnalyzing {
                analysisProgress
            } else if store.analysisFailed {
                analysisRecovery
            } else {
                HSplitView {
                    findings.frame(minWidth: 300, idealWidth: 340, maxWidth: 430)
                    Group {
                        if let finding = store.selectedFinding {
                            FindingDetail(finding: finding)
                        } else {
                            reviewEmpty
                        }
                    }.frame(minWidth: 500, maxWidth: .infinity, maxHeight: .infinity)
                }
            }
        }.frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var analysisProgress: some View {
        VStack(spacing: 20) {
            ProgressView().controlSize(.large)
            Text("Uma leitura atenta está em andamento.").font(.system(size: 28, design: .serif))
            Text("Os pontos de atenção aparecerão aqui quando a análise terminar.")
                .foregroundStyle(LumeTheme.secondary)
            VStack(alignment: .leading, spacing: 14) {
                ForEach(store.analysisStages) { stage in
                    HStack(spacing: 12) {
                        Image(systemName: stage.state == "completed" ? "checkmark.circle.fill" :
                              (stage.state == "running" ? "circle.inset.filled" : "circle"))
                            .foregroundStyle(LumeTheme.accent)
                        VStack(alignment: .leading, spacing: 3) {
                            Text(stage.title).font(.callout.weight(.medium))
                            Text(stage.statusText).font(.caption).foregroundStyle(LumeTheme.secondary)
                        }
                    }
                }
            }.frame(maxWidth: 440, alignment: .leading)
            Button("Interromper análise") { store.cancel() }.disabled(!store.canCancel)
                .buttonStyle(LumeButtonStyle())
        }.padding(36).frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var analysisRecovery: some View {
        VStack(spacing: 20) {
            Image(systemName: "doc.text.magnifyingglass").font(.largeTitle)
            Text("A análise não foi concluída.").font(.system(size: 28, design: .serif))
            Text(store.status).foregroundStyle(LumeTheme.secondary).multilineTextAlignment(.center)
            HStack {
                Button("Voltar à preparação") { store.showPreparation() }
                if store.report != nil { Button("Retomar relatório anterior") { store.resumeReview() } }
                if store.logURL != nil { Button("Ver registro") { store.openLog() } }
            }.buttonStyle(LumeButtonStyle())
        }.padding(36).frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var reviewEmpty: some View {
        VStack(alignment: .leading, spacing: 22) {
            LumeMark(size: 72)
            Text(store.report?.findings.isEmpty == true ? "Nenhum alerta nesta análise." : "O texto continua sendo do autor.")
                .font(.system(size: 32, design: .serif))
            Text(store.report?.findings.isEmpty == true ? "Confira os critérios usados. A ausência de alertas não garante ausência de erros." : "Selecione um ponto de atenção para ler o contexto e registrar sua avaliação.")
                .font(.callout).foregroundStyle(LumeTheme.secondary)
        }.frame(maxWidth: 480, alignment: .leading).padding(36)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var findings: some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 15) {
                HStack(alignment: .firstTextBaseline) {
                    Text("Pontos de atenção").font(.system(size: 24, design: .serif))
                    Spacer()
                    Text("\(store.filteredFindings.count)").font(.caption.monospacedDigit())
                        .padding(7).background(Capsule().fill(LumeTheme.wash))
                }
                HStack(spacing: 8) {
                    Image(systemName: "magnifyingglass").foregroundStyle(LumeTheme.secondary)
                    TextField("Buscar no texto", text: $store.search).textFieldStyle(.plain)
                        .accessibilityLabel("Buscar no texto ou capítulo")
                }.padding(10).background(RoundedRectangle(cornerRadius: 8).fill(LumeTheme.paper))
                    .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(LumeTheme.line))
                VStack(spacing: 9) {
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
                        ForEach(FindingSeverity.allCases) { severity in
                            Text(severity.title).tag(severity.rawValue)
                        }
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
                }.font(.callout)
            }.padding(20)
            Rectangle().fill(LumeTheme.line).frame(height: 1)
            if store.filteredFindings.isEmpty {
                VStack(spacing: 12) {
                    Image(systemName: store.report == nil ? "text.book.closed" : "line.3.horizontal.decrease.circle").font(.title)
                    Text(store.report == nil ? "Seus alertas aparecerão aqui." : "Nenhum alerta nesta seleção.")
                        .font(.system(size: 17, design: .serif))
                    if store.report != nil {
                        Button("Limpar filtros") { store.search = ""; store.category = "Todas"; store.decisionFilter = "Todas"; store.layerFilter = "Todas"; store.moduleFilter = "Todas"; store.severityFilter = "Todas" }
                            .buttonStyle(LumeButtonStyle())
                    }
                }.foregroundStyle(LumeTheme.secondary).multilineTextAlignment(.center)
                    .padding(24).frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                List(selection: $store.selectedID) {
                    ForEach(store.filteredFindings) { finding in
                        FindingRow(finding: finding, decision: store.decision(for: finding), selected: store.selectedID == finding.id)
                            .tag(finding.id)
                            .listRowSeparator(.hidden)
                            .listRowInsets(EdgeInsets(top: 6, leading: 12, bottom: 6, trailing: 12))
                    }
                }.listStyle(.plain).scrollContentBackground(.hidden)
            }
        }.background(LumeTheme.canvas)
    }

    private var statusBar: some View {
        VStack(spacing: 0) {
            Rectangle().fill(LumeTheme.line).frame(height: 1)
            HStack(spacing: 10) {
                if store.isBusy {
                    ProgressView().controlSize(.small)
                    Text(store.jobLabel)
                    if store.canCancel { Button("Interromper") { store.cancel() } }
                } else {
                    Image(systemName: store.hasUnsavedDecisions ? "exclamationmark.triangle" : "circle.inset.filled")
                        .foregroundStyle(store.hasUnsavedDecisions ? LumeTheme.error : LumeTheme.accent)
                    Text(store.status).lineLimit(2)
                }
                Spacer(minLength: 12)
                if store.logURL != nil { Button("Ver registro") { store.openLog() } }
            }.font(.system(size: 11)).foregroundStyle(LumeTheme.secondary)
                .padding(.horizontal, 18).padding(.vertical, 10)
        }.background(LumeTheme.paper)
    }
}

private struct FindingRow: View {
    let finding: Finding
    let decision: ReviewDecision
    let selected: Bool
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text(finding.category).font(.system(size: 13, weight: .semibold))
                Spacer(minLength: 4)
                Image(systemName: decision.symbol).foregroundStyle(decision.color).help(decision.rawValue)
            }
            Text(finding.text).font(.system(size: 14, design: .serif)).lineSpacing(3).lineLimit(3)
            HStack {
                Text("§ \(finding.paragraph)")
                Text("·")
                Text(decision.rawValue)
            }.font(.system(size: 10)).foregroundStyle(LumeTheme.secondary)
        }.padding(15).frame(maxWidth: .infinity, alignment: .leading)
            .foregroundStyle(LumeTheme.ink)
            .background(RoundedRectangle(cornerRadius: 10).fill(selected ? LumeTheme.wash : LumeTheme.paper))
            .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(selected ? LumeTheme.accent : LumeTheme.line, lineWidth: selected ? 1.5 : 1))
            .accessibilityElement(children: .combine)
    }
}

@MainActor
private struct FindingDetail: View {
    @EnvironmentObject private var store: ReviewStore
    @AppStorage("lumeReadingSize") private var readingSize = 21.0
    let finding: Finding
    private var textSize: CGFloat { CGFloat(min(28, max(17, readingSize))) }
    private var markedParagraph: Text {
        let parts = finding.segments
        return Text(parts.before) + Text(parts.marked).foregroundColor(LumeTheme.copper).bold().underline() + Text(parts.after)
    }
    private var currentIndex: Int? { store.filteredFindings.firstIndex { $0.id == finding.id } }
    private func move(_ offset: Int) {
        guard let index = currentIndex else { return }
        let target = index + offset
        if store.filteredFindings.indices.contains(target) { store.selectedID = store.filteredFindings[target].id }
    }

    private func evidenceView(_ evidence: TextEvidence) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("\(evidence.document == "original" ? "Original" : "Manuscrito atual") · \(evidence.chapter) · § \(evidence.paragraph)")
                .font(.caption).foregroundStyle(LumeTheme.secondary)
            Text(evidence.text).font(.system(size: 16, design: .serif)).lineSpacing(5)
                .textSelection(.enabled)
        }.padding(14).frame(maxWidth: .infinity, alignment: .leading)
            .background(RoundedRectangle(cornerRadius: 10).fill(LumeTheme.paper))
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 26) {
                HStack {
                    Eyebrow(title: "Leitura em contexto")
                    Spacer()
                    if let index = currentIndex {
                        Text("\(index + 1) / \(store.filteredFindings.count)").font(.caption.monospacedDigit()).foregroundStyle(LumeTheme.secondary)
                    }
                    Button { move(-1) } label: { Image(systemName: "chevron.left") }
                        .help("Alerta anterior").accessibilityLabel("Alerta anterior").disabled(currentIndex == nil || currentIndex == 0)
                    Button { move(1) } label: { Image(systemName: "chevron.right") }
                        .help("Próximo alerta").accessibilityLabel("Próximo alerta").disabled(currentIndex == nil || currentIndex == store.filteredFindings.count - 1)
                }
                VStack(alignment: .leading, spacing: 10) {
                    Text(finding.category).font(.system(size: 34, weight: .regular, design: .serif))
                    Text(finding.moduleTitle + " · " + finding.severityTitle)
                        .font(.callout.weight(.medium)).foregroundStyle(LumeTheme.accent)
                    Text("\(finding.chapter)  ·  Parágrafo \(finding.paragraph)")
                        .font(.callout).foregroundStyle(LumeTheme.secondary).textSelection(.enabled)
                }
                VStack(alignment: .leading, spacing: 20) {
                    HStack {
                        Eyebrow(title: "Trecho original")
                        Spacer()
                        Button { readingSize = max(17, readingSize - 1) } label: { Text("A−") }
                            .accessibilityLabel("Diminuir tamanho do texto").disabled(readingSize <= 17)
                        Button { readingSize = min(28, readingSize + 1) } label: { Text("A+") }
                            .accessibilityLabel("Aumentar tamanho do texto").disabled(readingSize >= 28)
                    }.buttonStyle(.borderless)
                    markedParagraph.font(.system(size: textSize, design: .serif)).lineSpacing(8)
                        .textSelection(.enabled).fixedSize(horizontal: false, vertical: true)
                    HStack {
                        Rectangle().fill(LumeTheme.copper).frame(width: 18, height: 2)
                        Text("Trecho sinalizado para sua avaliação").font(.system(size: 10)).foregroundStyle(LumeTheme.secondary)
                    }
                }.padding(26).frame(maxWidth: .infinity, alignment: .leading)
                    .background(RoundedRectangle(cornerRadius: 14).fill(LumeTheme.paper))
                    .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(LumeTheme.line))
                VStack(alignment: .leading, spacing: 12) {
                    Label("Por que chamou atenção", systemImage: "text.magnifyingglass").font(.system(size: 14, weight: .semibold))
                    Text(finding.reason).font(.system(size: 14)).lineSpacing(5).textSelection(.enabled)
                    if let suggestion = finding.suggestion {
                        Text(suggestion.isEmpty ? "Sugestão: remover o trecho destacado." : "Sugestão para o trecho destacado: “\(suggestion)”")
                            .font(.callout).textSelection(.enabled)
                    }
                    DisclosureGroup("Detalhes da análise") {
                        Text("Prioridade: \(finding.priority)\nOrigem: \(finding.source)")
                            .font(.caption).frame(maxWidth: .infinity, alignment: .leading).padding(.top, 6)
                    }.font(.caption).foregroundStyle(LumeTheme.secondary)
                }
                if let confidence = finding.confidence {
                    Text("Força do indício: \(confidence). Classificação automática, sujeita à decisão editorial.")
                        .font(.caption).foregroundStyle(LumeTheme.secondary)
                }
                if let related = finding.related, !related.isEmpty {
                    VStack(alignment: .leading, spacing: 14) {
                        Eyebrow(title: "Trechos relacionados")
                        ForEach(Array(related.enumerated()), id: \.offset) { _, evidence in
                            evidenceView(evidence)
                        }
                    }
                }
                if let context = finding.context, !context.isEmpty {
                    DisclosureGroup("Ver contexto próximo") {
                        VStack(alignment: .leading, spacing: 14) {
                            ForEach(Array(context.enumerated()), id: \.offset) { _, evidence in
                                evidenceView(evidence)
                            }
                        }.padding(.top, 12)
                    }
                }
                Rectangle().fill(LumeTheme.line).frame(height: 1)
                VStack(alignment: .leading, spacing: 14) {
                    HStack {
                        Text("Como você avalia este trecho?").font(.system(size: 21, design: .serif))
                        Spacer()
                    }
                    LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                        ForEach(ReviewDecision.allCases) { decision in
                            DecisionButton(decision: decision, selected: store.decision(for: finding) == decision) {
                                store.setDecision(decision, for: finding)
                            }
                        }
                    }.disabled(store.isBusy)
                    Text("Sua avaliação fica salva neste Mac. Exporte as decisões para compartilhar o feedback.")
                        .font(.caption).foregroundStyle(LumeTheme.secondary).lineSpacing(3)
                }
                Button { store.copyParagraph(finding) } label: {
                    Label("Copiar parágrafo para localizar no original", systemImage: "doc.on.doc")
                }.buttonStyle(LumeButtonStyle())
                if let report = store.report, !report.warnings.isEmpty {
                    DisclosureGroup("Sobre esta análise · \(report.warnings.count) avisos") {
                        VStack(alignment: .leading, spacing: 10) {
                            ForEach(Array(report.warnings.enumerated()), id: \.offset) { _, warning in
                                Text(warning).font(.caption).lineSpacing(3)
                            }
                            Text("As avaliações registradas não treinam o analisador automaticamente.").font(.caption)
                        }.padding(.top, 10)
                    }.font(.caption).foregroundStyle(LumeTheme.secondary)
                }
            }.padding(32).frame(maxWidth: 820, alignment: .leading)
                .frame(maxWidth: .infinity, alignment: .center)
        }.background(LumeTheme.canvas)
    }
}

private struct DecisionButton: View {
    let decision: ReviewDecision
    let selected: Bool
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            HStack(alignment: .top, spacing: 10) {
                Image(systemName: selected ? "checkmark.circle.fill" : decision.symbol)
                    .font(.system(size: 17)).foregroundStyle(decision.color).frame(width: 20)
                VStack(alignment: .leading, spacing: 5) {
                    Text(decision.rawValue).font(.system(size: 12, weight: .semibold)).foregroundStyle(LumeTheme.ink)
                    Text(decision.explanation).font(.system(size: 10)).foregroundStyle(LumeTheme.secondary)
                }
                Spacer(minLength: 0)
            }.padding(13).frame(maxWidth: .infinity, minHeight: 70, alignment: .leading)
                .background(RoundedRectangle(cornerRadius: 10).fill(selected ? LumeTheme.wash : LumeTheme.paper))
                .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(selected ? decision.color : LumeTheme.line, lineWidth: selected ? 2 : 1))
                .contentShape(RoundedRectangle(cornerRadius: 10))
        }.buttonStyle(.plain)
            .accessibilityLabel(decision.rawValue + (selected ? ", selecionado" : "") + ". " + decision.explanation)
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
    }
    @State private var section: Section = .checks
    private var panelHeight: CGFloat {
        min(660, max(440, (NSScreen.main?.visibleFrame.height ?? 840) - 180))
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
    private var checks: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("O que procurar").font(.title2)
            Text("Cada verificação pode ser ativada separadamente. O modo Linguística / Editorial / Ambas continua limitando quais camadas serão executadas.").font(.callout).foregroundStyle(.secondary)
            ForEach(SearchRule.all) { rule in
                Toggle(rule.title, isOn: Binding(get: { store.searchSettings.rules[rule.id] ?? false }, set: { store.searchSettings.rules[rule.id] = $0 }))
            }
            HStack {
                Button("Ativar todas") { for rule in SearchRule.all { store.searchSettings.rules[rule.id] = true } }
                Button("Desativar todas") { for rule in SearchRule.all { store.searchSettings.rules[rule.id] = false } }
            }
        }
    }
    private var areas: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Onde procurar").font(.title2)
            Text("Repetições de palavras e frases").font(.headline)
            ForEach(scopes, id: \.0) { key, label in Toggle(label, isOn: scopeBinding(key, tense: false)) }
            Stepper("Distância máxima: \(store.searchSettings.wordDistance) palavras", value: $store.searchSettings.wordDistance, in: 2...40)
            VStack(alignment: .leading, spacing: 6) {
                Text("Limite para palavras")
                Picker("Limite para palavras", selection: $store.searchSettings.repetitionBoundary) {
                    Text("Mesmo trecho").tag("trecho")
                    Text("Mesma frase").tag("frase")
                }.labelsHidden().pickerStyle(.menu).frame(maxWidth: .infinity, minHeight: 28)
            }
            Toggle("Comparar frases também entre parágrafos próximos", isOn: $store.searchSettings.duplicateAcrossParagraphs)
            VStack(alignment: .leading, spacing: 6) {
                Text("Frases repetidas")
                Picker("Frases repetidas", selection: $store.searchSettings.duplicateSimilarity) {
                    Text("Mesmas palavras").tag(1.0)
                    Text("Sequências semelhantes").tag(0.85)
                }.labelsHidden().pickerStyle(.menu).frame(maxWidth: .infinity, minHeight: 28)
                Text("A comparação ignora maiúsculas e pontuação. Sequências semelhantes tornam a busca mais sensível.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Text("A busca não cruza de uma fala para um inciso narrativo ao comparar palavras. Frases entre parágrafos podem pertencer a personagens diferentes; o motor ainda não identifica o falante.").font(.caption).foregroundStyle(.secondary)
            Divider()
            Text("Mudanças de tempo verbal").font(.headline)
            ForEach(scopes, id: \.0) { key, label in Toggle(label, isOn: scopeBinding(key, tense: true)) }
            Text("Estrutura e pontuação são verificadas na narração. Continuidade e referências usam o contexto; variações de nomes usam o documento inteiro. O corretor gramatical local mantém suas próprias proteções.").font(.caption).foregroundStyle(.secondary)
        }
    }
    private var structure: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Como o texto está marcado").font(.title2)
            Toggle("Travessão inicial marca diálogo", isOn: $store.searchSettings.dialogueDashes)
            VStack(alignment: .leading, spacing: 6) {
                Text("Trechos entre aspas representam")
                Picker("Trechos entre aspas representam", selection: $store.searchSettings.quotesRole) {
                    Text("Falas").tag("dialogo")
                    Text("Pensamentos").tag("pensamento")
                    Text("Manter como narração").tag("narracao")
                }.labelsHidden().pickerStyle(.menu).frame(maxWidth: .infinity, minHeight: 28)
            }
            Toggle("Itálico marca pensamento", isOn: $store.searchSettings.italicThoughts)
            Text("Essas opções descrevem a marcação, não interpretam o sentido. Itálico pode ter outras funções. Pensamentos sem marcas continuam classificados como narração.").font(.caption).foregroundStyle(.secondary)
            Divider()
            Text("Capítulos").font(.headline)
            Toggle("Reconhecer títulos e numeração automaticamente", isOn: $store.searchSettings.chapterAuto)
            Text("Reconhece ‘Capítulo um’, ‘Capítulo 1’ e ‘Capítulo I’, estilos de título e níveis de estrutura. Para uma divisão própria, desative o automático e cadastre os títulos exatos abaixo.").font(.caption).foregroundStyle(.secondary)
            Text("Títulos exatos · um por linha")
            TextEditor(text: $titlesText).onChange(of: titlesText) { store.searchSettings.chapterTitles = lines($0) }.frame(height: 85).border(Color.secondary.opacity(0.3))
            Text("Estilos de parágrafo adicionais · um por linha")
            TextEditor(text: $stylesText).onChange(of: stylesText) { store.searchSettings.chapterStyles = lines($0) }.frame(height: 65).border(Color.secondary.opacity(0.3))
            Text("Nomes aceitos que não devem gerar alerta de variação · um por linha")
            TextEditor(text: $namesText).onChange(of: namesText) { store.searchSettings.ignoredNames = lines($0) }.frame(height: 65).border(Color.secondary.opacity(0.3))
        }
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Configurar busca").font(.largeTitle)
            Text(store.documentURL?.lastPathComponent ?? "Configuração para a próxima análise").font(.callout).foregroundStyle(.secondary)
            HStack(spacing: 8) {
                ForEach(Section.allCases) { item in
                    Button { section = item } label: {
                        Text(item.rawValue).font(.system(size: 13, weight: .semibold))
                            .lineLimit(1).frame(maxWidth: .infinity, minHeight: 38)
                            .foregroundStyle(section == item ? LumeTheme.cream : LumeTheme.ink)
                            .background(RoundedRectangle(cornerRadius: 8).fill(section == item ? LumeTheme.forest : LumeTheme.wash))
                            .contentShape(Rectangle())
                    }.buttonStyle(.plain)
                        .accessibilityLabel(item.rawValue)
                        .accessibilityAddTraits(section == item ? .isSelected : [])
                }
            }.frame(maxWidth: .infinity)
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    switch section {
                    case .checks: checks
                    case .areas: areas
                    case .structure: structure
                    }
                }.frame(maxWidth: .infinity, alignment: .leading).padding(16)
            }.id(section).frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(RoundedRectangle(cornerRadius: 10).fill(LumeTheme.paper))
            if let error = store.errorText {
                Text(error).font(.caption).foregroundStyle(LumeTheme.error).lineLimit(3)
                Button("Fechar aviso") { store.errorText = nil }.font(.caption)
            }
            Text("As mudanças valem na próxima análise. A configuração é salva para o caminho deste documento; exporte para reutilizar em outro arquivo.").font(.caption).foregroundStyle(.secondary)
            HStack {
                Button("Importar…") { store.importSearchSettings(); refreshText() }
                Button("Exportar…") { store.exportSearchSettings() }
                Button("Restaurar padrão") { store.searchSettings = SearchSettings(); refreshText() }
                Spacer()
                Button("Concluir") { store.saveSearchSettings(); dismiss() }.keyboardShortcut(.defaultAction)
            }
        }.padding(24).frame(width: 720, height: panelHeight)
            .background(LumeTheme.canvas).foregroundStyle(LumeTheme.ink).tint(LumeTheme.accent)
            .onAppear { refreshText() }
            .onDisappear { store.saveSearchSettings() }
    }
}
