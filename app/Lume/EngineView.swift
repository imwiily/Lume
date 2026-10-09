import SwiftUI
import AppKit

/// Motor: administra o FONTE. Mostra a versão carregada e as ações reais; nada editorial aqui.
@MainActor
struct EngineView: View {
    @EnvironmentObject private var store: ReviewStore
    @Environment(\.openWindow) private var openWindow

    private var origin: String {
        guard let engine = store.embeddedEngine else { return "Instalação externa de desenvolvimento" }
        return engine.updated ? "Atualização instalada" : "Motor embutido"
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Motor de análise").font(LumeFont.display(26, weight: .semibold))
                    Text("O FONTE lê o manuscrito neste Mac. Atualizações do motor não mexem nos seus relatórios nem nas suas decisões.")
                        .font(LumeFont.ui(13)).foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
                }
                Panel(padding: 20) {
                    VStack(alignment: .leading, spacing: 16) {
                        HStack(alignment: .center, spacing: 14) {
                            Image(systemName: "terminal").font(.system(size: 20))
                                .frame(width: 46, height: 46)
                                .background(RoundedRectangle(cornerRadius: LumeRadius.medium).fill(LumeTheme.sunken))
                            VStack(alignment: .leading, spacing: 4) {
                                HStack(spacing: 10) {
                                    Text(store.embeddedEngine.map { "FONTE \($0.version)" } ?? "FONTE")
                                        .font(LumeFont.display(22, weight: .semibold))
                                    HStack(spacing: 5) {
                                        Circle().fill(store.pythonExists ? LumeTheme.glowLine : LumeTheme.tertiary).frame(width: 6, height: 6)
                                        Text(store.pythonExists ? origin : "Motor não preparado")
                                    }.font(LumeFont.ui(11, weight: .medium)).foregroundStyle(LumeTheme.amber)
                                        .padding(.horizontal, 7).padding(.vertical, 3)
                                        .background(RoundedRectangle(cornerRadius: LumeRadius.small).fill(LumeTheme.glow.opacity(0.6)))
                                }
                                Text(store.engineDescription).font(LumeFont.ui(12)).foregroundStyle(LumeTheme.secondary)
                            }
                        }
                        Divider().overlay(LumeTheme.line)
                        if store.embeddedEngine != nil {
                            HStack(spacing: 8) {
                                Button { store.diagnose() } label: { Label("Verificar motor", systemImage: "stethoscope") }
                                Button { store.importEngine() } label: { Label("Instalar atualização…", systemImage: "square.and.arrow.down") }
                                Button { store.rollbackEngine() } label: { Label("Voltar à versão anterior", systemImage: "clock.arrow.circlepath") }
                                Spacer()
                                Button { store.resetEngine() } label: { Label("Restaurar embutido", systemImage: "arrow.counterclockwise") }
                            }.buttonStyle(LumeButtonStyle())
                        } else {
                            VStack(alignment: .leading, spacing: 10) {
                                Text(store.backendURL?.path ?? "Selecione a pasta fonte ou monte o aplicativo completo.")
                                    .font(LumeFont.ui(12)).foregroundStyle(LumeTheme.secondary).textSelection(.enabled)
                                HStack(spacing: 8) {
                                    Button("Selecionar pasta…") { store.chooseBackend() }
                                    Button("Preparar") { store.install() }.disabled(store.backendURL == nil)
                                    Button("Verificar") { store.diagnose() }.disabled(!store.pythonExists)
                                }.buttonStyle(LumeButtonStyle())
                            }
                        }
                    }
                }.disabled(store.isBusy)
                Panel(padding: 20) {
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Localização").font(LumeFont.ui(13, weight: .semibold))
                        if let engine = store.embeddedEngine {
                            HStack {
                                Text(engine.root.path).font(.system(size: 11, design: .monospaced))
                                    .foregroundStyle(LumeTheme.secondary).textSelection(.enabled).lineLimit(2).truncationMode(.middle)
                                Spacer()
                                Button("Mostrar no Finder") { NSWorkspace.shared.activateFileViewerSelecting([engine.root]) }
                                    .buttonStyle(LumeButtonStyle(kind: .soft))
                            }
                        } else {
                            Text("Fontes de desenvolvimento em uso; sem motor empacotado.").font(LumeFont.ui(12))
                                .foregroundStyle(LumeTheme.secondary)
                        }
                        Text("O resultado de Verificar motor aparece na linha de estado; os detalhes ficam em Registro.")
                            .font(LumeFont.ui(11.5)).foregroundStyle(LumeTheme.secondary)
                    }
                }
                Panel(padding: 20) {
                    HStack(alignment: .center, spacing: 14) {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Armazenamento").font(LumeFont.ui(13, weight: .semibold))
                            Text("Cada análise guarda um relatório, um registro e uma configuração, com texto do manuscrito. A limpeza apaga os de leituras antigas e mantém o relatório aberto, o mais recente de cada livro, suas decisões e as cópias de segurança. Também ficam os relatórios antigos com decisões que o mais recente não tem, porque só eles permitem medir essas decisões; eles guardam trechos do manuscrito.")
                                .font(LumeFont.ui(11.5)).foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
                        }
                        Spacer(minLength: 8)
                        Button { store.cleanStorage() } label: { Label("Limpar resíduos…", systemImage: "trash") }
                            .buttonStyle(LumeButtonStyle()).disabled(store.isBusy)
                            .help("Mostra o espaço a liberar e pede confirmação antes de apagar")
                    }
                }
                HStack {
                    Label("A análise do FONTE roda neste Mac.", systemImage: "lock").font(LumeFont.ui(11.5))
                        .foregroundStyle(LumeTheme.secondary)
                    Spacer()
                    Button("Sobre o Lume e licenças…") { openWindow(id: "sobre") }.buttonStyle(LumeButtonStyle(kind: .plain))
                        .font(LumeFont.ui(12))
                }
            }.frame(maxWidth: 860).padding(36).frame(maxWidth: .infinity)
        }.background(LumeTheme.canvas)
    }
}

/// Registro: o arquivo de registro da última operação desta sessão, só para leitura.
@MainActor
struct LogView: View {
    @EnvironmentObject private var store: ReviewStore
    @State private var text = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .bottom) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Registro").font(LumeFont.display(26, weight: .semibold))
                    Text(store.logURL == nil ? "Nenhuma operação nesta sessão ainda."
                                             : "Saída do motor na última operação: análise, estimativa, verificação ou correção.")
                        .font(LumeFont.ui(13)).foregroundStyle(LumeTheme.secondary)
                }
                Spacer()
                if let url = store.logURL {
                    Button("Mostrar no Finder") { NSWorkspace.shared.activateFileViewerSelecting([url]) }
                        .buttonStyle(LumeButtonStyle())
                    Button("Abrir no editor") { store.openLog() }.buttonStyle(LumeButtonStyle())
                }
            }
            if let url = store.logURL {
                Text(url.path).font(.system(size: 11, design: .monospaced)).foregroundStyle(LumeTheme.tertiary)
                    .textSelection(.enabled).lineLimit(1).truncationMode(.middle)
                ScrollView {
                    Text(text.isEmpty ? "O registro está vazio." : text)
                        .font(.system(size: 11.5, design: .monospaced)).lineSpacing(2)
                        .textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading).padding(14)
                }.background(RoundedRectangle(cornerRadius: LumeRadius.large).fill(LumeTheme.raised))
                    .overlay(RoundedRectangle(cornerRadius: LumeRadius.large).strokeBorder(LumeTheme.line))
            } else {
                Panel {
                    Text("O registro aparece aqui depois de analisar, estimar o custo, verificar o motor ou corrigir um trecho.")
                        .font(LumeFont.ui(12.5)).foregroundStyle(LumeTheme.secondary)
                }
                Spacer()
            }
        }.padding(36).frame(maxWidth: 980, maxHeight: .infinity, alignment: .topLeading)
            .frame(maxWidth: .infinity).background(LumeTheme.canvas)
            .task(id: store.logURL) {
                // Atualiza enquanto o motor escreve; para quando a tela sai.
                while !Task.isCancelled {
                    if let url = store.logURL { text = PythonRunner.tail(url) } else { text = "" }
                    guard store.isBusy else { break }
                    try? await Task.sleep(nanoseconds: 1_000_000_000)
                }
            }
    }
}

// MARK: - Folhas

@MainActor
struct CoverageSheet: View {
    @EnvironmentObject private var store: ReviewStore
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 4) {
                Kicker(title: "Etapas e alcance")
                Text("O que esta leitura cobriu").font(LumeFont.display(24, weight: .semibold))
            }
            ScrollView {
                VStack(alignment: .leading, spacing: 10) {
                    if let partial = store.report?.metadata.analiseParcial {
                        PartialNotice(partial: partial)
                    }
                    if let memory = store.report?.metadata.narrativeSummary {
                        Panel(padding: 14) {
                            VStack(alignment: .leading, spacing: 4) {
                                Text("Memória narrativa").font(LumeFont.ui(13, weight: .semibold))
                                Text("\(memory.scenes) cenas · \(memory.facts) fatos · \(memory.events) eventos").font(LumeFont.ui(12.5))
                                Text("As ocorrências mostram as evidências comparadas. Cenas e fatos completos ficam no relatório JSON.")
                                    .font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary)
                            }
                        }
                    }
                    ForEach(store.report?.metadata.stages ?? []) { stage in
                        Panel(padding: 14) {
                            VStack(alignment: .leading, spacing: 4) {
                                HStack {
                                    Text(stage.title).font(LumeFont.ui(13, weight: .semibold))
                                    Spacer()
                                    Text(stage.statusText).font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary)
                                }
                                Text(stage.detail).font(LumeFont.ui(12)).foregroundStyle(LumeTheme.ink.opacity(0.85))
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                        }
                    }
                    if let report = store.report {
                        DiagnosticPanel(report: report)
                    }
                    ForEach(Array((store.report?.warnings ?? []).enumerated()), id: \.offset) { _, warning in
                        Text(warning).font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }.frame(maxWidth: .infinity, alignment: .leading)
            }
            HStack { Spacer(); Button("Concluir") { dismiss() }.buttonStyle(LumeButtonStyle(kind: .primary)).keyboardShortcut(.defaultAction) }
        }.padding(24).frame(width: 640, height: 600).background(LumeTheme.canvas)
            .foregroundStyle(LumeTheme.ink).tint(LumeTheme.accent)
    }
}

@MainActor
struct KeySheet: View {
    @EnvironmentObject private var store: ReviewStore
    @Environment(\.dismiss) private var dismiss
    @State private var keyText = ""
    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 14) {
                LumeMark(size: 40)
                VStack(alignment: .leading, spacing: 2) {
                    Kicker(title: "Recursos com IA")
                    Text("Chave da API da Anthropic").font(LumeFont.display(22, weight: .semibold))
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
        }.padding(24).frame(width: 540).background(LumeTheme.canvas)
            .foregroundStyle(LumeTheme.ink).tint(LumeTheme.accent)
    }
}

/// Diagnóstico do motor: achados fora da mesa (Auditoria de confiança baixa, categorias
/// experimentais). Ficam aqui, em Etapas e alcance, só para consulta; não pedem decisão.
struct DiagnosticPanel: View {
    let report: EditorialReport
    @State private var expanded = false

    var body: some View {
        let items = report.metadata.diagnostico ?? []
        Panel(padding: 14) {
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text("Diagnóstico do motor").font(LumeFont.ui(13, weight: .semibold))
                    Spacer()
                    Text(report.metadata.politicaVersao.map { "Política v\($0)" } ?? "Relatório anterior à política")
                        .font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary)
                }
                Text(items.isEmpty
                     ? "Nenhum achado ficou só no diagnóstico nesta leitura."
                     : "\(items.count) achado(s) com evidência fraca ou em fase experimental ficaram fora da mesa. Servem para medir e melhorar o Lume; não pedem decisão nem impedem o encerramento.")
                    .font(LumeFont.ui(12)).foregroundStyle(LumeTheme.ink.opacity(0.85)).fixedSize(horizontal: false, vertical: true)
                if !items.isEmpty {
                    DisclosureGroup(isExpanded: $expanded) {
                        VStack(alignment: .leading, spacing: 6) {
                            ForEach(items) { item in
                                VStack(alignment: .leading, spacing: 1) {
                                    Text("\(item.category) · \(item.chapter) · § \(item.paragraph)").font(LumeFont.ui(11, weight: .semibold))
                                    Text(item.segments.marked).font(LumeFont.display(12)).foregroundStyle(LumeTheme.secondary)
                                }
                            }
                        }.padding(.top, 4)
                    } label: {
                        Text("Ver achados").font(LumeFont.ui(11.5))
                    }
                }
            }
        }
    }
}
