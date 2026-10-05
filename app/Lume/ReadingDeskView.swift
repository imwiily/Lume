import SwiftUI

/// Mesa de leitura: Pontos de atenção | Manuscrito | Inspetor editorial.
/// O manuscrito tem prioridade de espaço: numa janela estreita, o inspetor recolhe e passa para
/// baixo da página, sem esconder nenhuma ação.
@MainActor
struct ReadingDeskView: View {
    @EnvironmentObject private var store: ReviewStore
    @AppStorage("lumeInspectorVisible") private var inspectorVisible = true
    /// Largura a partir da qual cabem lista, página confortável e inspetor lado a lado.
    static let inspectorMinimumWidth: CGFloat = 1180

    var body: some View {
        Group {
            if store.isAnalyzing {
                ReadingProgressView()
            } else if store.analysisFailed {
                recovery
            } else {
                GeometryReader { geometry in
                    let showsInspector = inspectorVisible && geometry.size.width >= Self.inspectorMinimumWidth
                    HSplitView {
                        FindingsColumn().frame(minWidth: 260, idealWidth: 310, maxWidth: 400)
                        Group {
                            if let finding = store.selectedFinding {
                                ManuscriptView(finding: finding, inspectorBelow: !showsInspector)
                            } else {
                                restingPage
                            }
                        }.frame(minWidth: 440, maxWidth: .infinity, maxHeight: .infinity)
                        if showsInspector {
                            ScrollView {
                                if let finding = store.selectedFinding {
                                    FindingInspector(finding: finding)
                                } else {
                                    inspectorPlaceholder
                                }
                            }.frame(minWidth: 300, idealWidth: 350, maxWidth: 440, maxHeight: .infinity)
                                .background(LumeTheme.surface)
                        }
                    }
                }
            }
        }.frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var recovery: some View {
        VStack(spacing: 16) {
            Image(systemName: "moon.stars").font(.system(size: 36, weight: .light)).foregroundStyle(LumeTheme.amber)
            Text("A leitura foi interrompida.").font(LumeFont.display(28, weight: .semibold))
            Text(store.status).font(LumeFont.ui(13)).foregroundStyle(LumeTheme.secondary)
                .multilineTextAlignment(.center).frame(maxWidth: 520)
            HStack {
                Button("Voltar ao início") { store.showPreparation() }
                if store.report != nil { Button("Retomar relatório anterior") { store.resumeReview() } }
                if store.logURL != nil { Button("Ver registro") { store.openLog() } }
            }.buttonStyle(LumeButtonStyle())
        }.padding(40).frame(maxWidth: .infinity, maxHeight: .infinity).background(LumeTheme.canvas)
    }

    private var restingPage: some View {
        let none = store.report?.findings.isEmpty == true
        return VStack(alignment: .leading, spacing: 18) {
            LumeMark(size: 52)
            Text(none ? "Nenhum alerta nesta leitura." : "Cada alerta é uma pergunta,\nnão uma sentença.")
                .font(LumeFont.display(28, weight: .semibold)).lineSpacing(3)
            Text(none ? "Confira os critérios usados em Etapas e alcance. A ausência de alertas não garante ausência de erros."
                      : "O texto continua sendo seu. Escolha um ponto de atenção à esquerda para lê-lo na página e registrar sua avaliação.")
                .font(LumeFont.ui(13.5)).foregroundStyle(LumeTheme.secondary).lineSpacing(3)
            Text("Lume encontra. Lume explica. O editor decide.").font(LumeFont.display(14)).italic()
                .foregroundStyle(LumeTheme.amber)
        }.frame(maxWidth: 460, alignment: .leading).padding(40)
            .frame(maxWidth: .infinity, maxHeight: .infinity).background(LumeTheme.sunken.opacity(0.55))
    }

    private var inspectorPlaceholder: some View {
        VStack(alignment: .leading, spacing: 8) {
            Kicker(title: "Inspetor editorial")
            Text("Escolha um ponto de atenção para ver o que o Lume encontrou, por que acendeu a luz e registrar a sua decisão.")
                .font(LumeFont.ui(12.5)).foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
        }.padding(18).frame(maxWidth: .infinity, alignment: .leading)
    }
}

/// Linha de estado da janela: andamento, mensagens e as ações de registro e falsos positivos.
@MainActor
struct StatusLine: View {
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
            .padding(.horizontal, 16).padding(.vertical, 7)
            .background(LumeTheme.surface)
            .overlay(alignment: .top) { Rectangle().fill(LumeTheme.line).frame(height: 1) }
    }
}
