import SwiftUI
import AppKit

/// Componente de terceiros listado em `licencas/indice.json` do motor.
struct LicenseComponent: Decodable, Identifiable, Hashable {
    let nome: String
    let versao: String
    let licenca: String
    let uso: String
    let arquivos: [String]
    var id: String { nome }
}

private struct LicenseIndex: Decodable {
    let schema: Int
    let componentes: [LicenseComponent]
}

/// “Sobre o Lume”: versões, créditos e as licenças de tudo que segue no motor.
@MainActor
struct SobreView: View {
    @EnvironmentObject private var store: ReviewStore
    @State private var selectedID: String?
    @State private var search = ""

    private var appVersion: String {
        let info = Bundle.main.infoDictionary
        let version = info?["CFBundleShortVersionString"] as? String ?? "—"
        let build = info?["CFBundleVersion"] as? String ?? "—"
        return "Versão \(version) (\(build))"
    }
    private var root: URL? { store.embeddedEngine?.root }
    private var components: [LicenseComponent] {
        guard let root, let data = try? Data(contentsOf: root.appendingPathComponent("licencas/indice.json")),
              let index = try? JSONDecoder().decode(LicenseIndex.self, from: data) else { return [] }
        return index.componentes
    }
    private var filtered: [LicenseComponent] {
        search.isEmpty ? components : components.filter {
            ($0.nome + " " + $0.licenca + " " + $0.uso).localizedCaseInsensitiveContains(search)
        }
    }

    /// Só lê arquivos dentro do motor; caminhos do índice são relativos à sua raiz.
    private func fileURL(_ relative: String) -> URL? {
        guard let root else { return nil }
        let url = root.appendingPathComponent(relative).standardizedFileURL
        return url.path.hasPrefix(root.standardizedFileURL.path + "/") ? url : nil
    }
    private func licenseText(_ component: LicenseComponent) -> String {
        component.arquivos.compactMap { relative -> String? in
            guard let url = fileURL(relative),
                  let text = (try? String(contentsOf: url, encoding: .utf8)) ?? (try? String(contentsOf: url, encoding: .isoLatin1))
            else { return nil }
            return component.arquivos.count > 1 ? "── \(url.lastPathComponent) ──\n\n" + text : text
        }.joined(separator: "\n\n")
    }

    var body: some View {
        HStack(spacing: 0) {
            identity
            VStack(alignment: .leading, spacing: 0) {
                if components.isEmpty {
                    missing
                } else {
                    HSplitView {
                        list.frame(minWidth: 230, idealWidth: 250, maxWidth: 300)
                        detail.frame(minWidth: 360, maxWidth: .infinity)
                    }
                }
            }.background(LumeTheme.canvas)
        }
        .ignoresSafeArea(.container, edges: .top)
        .frame(minWidth: 860, minHeight: 560)
        .foregroundStyle(LumeTheme.ink).tint(LumeTheme.accent)
        .onAppear { if selectedID == nil { selectedID = components.first?.id } }
    }

    private var identity: some View {
        VStack(alignment: .leading, spacing: 14) {
            LumeMark(size: 76, glowing: true).padding(.top, 58)
            Text("Lume").font(LumeFont.display(36, weight: .semibold)).foregroundStyle(LumeTheme.linen)
            VStack(alignment: .leading, spacing: 4) {
                Text(appVersion)
                if let engine = store.embeddedEngine { Text("Motor FONTE \(engine.version)") }
            }.font(LumeFont.ui(12)).foregroundStyle(LumeTheme.linen.opacity(0.75))
            Text("Uma luz acesa ao lado de quem escreve.")
                .font(LumeFont.display(16)).italic().foregroundStyle(LumeTheme.candle)
                .fixedSize(horizontal: false, vertical: true).padding(.top, 6)
            Spacer()
            Text("O manuscrito é papel. O Lume é instrumento. A atenção é luz.")
                .font(LumeFont.display(13)).italic().foregroundStyle(LumeTheme.linen.opacity(0.85))
                .fixedSize(horizontal: false, vertical: true)
            Text("O manuscrito é lido neste Mac e a análise nunca o altera. Só os trechos que você autorizar seguem para a Coerência ou a Auditoria final com IA.")
                .font(LumeFont.ui(11)).foregroundStyle(LumeTheme.linen.opacity(0.7))
                .fixedSize(horizontal: false, vertical: true)
            Text("O Lume é software livre sob a licença MIT. Os componentes ao lado seguem suas próprias licenças.")
                .font(LumeFont.ui(11)).foregroundStyle(LumeTheme.linen.opacity(0.7))
                .fixedSize(horizontal: false, vertical: true).padding(.bottom, 26)
        }.padding(.horizontal, 26).frame(width: 260).frame(maxHeight: .infinity, alignment: .top)
            .background(LinearGradient(colors: [LumeTheme.night, LumeTheme.nightDeep], startPoint: .top, endPoint: .bottom)
                .ignoresSafeArea())
    }

    private var list: some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 10) {
                Kicker(title: "Componentes de terceiros · \(components.count)")
                SearchField(prompt: "Buscar", text: $search)
            }.padding(16).padding(.top, 28)
            ScrollView {
                LazyVStack(spacing: 2) {
                    ForEach(filtered) { component in
                        let selected = component.id == selectedID
                        Button { selectedID = component.id } label: {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(component.nome).font(LumeFont.ui(13, weight: .medium)).foregroundStyle(LumeTheme.ink)
                                Text(component.licenca).font(LumeFont.ui(10)).foregroundStyle(LumeTheme.secondary).lineLimit(1)
                            }.padding(.horizontal, 12).padding(.vertical, 7)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .background(RoundedRectangle(cornerRadius: LumeRadius.medium)
                                    .fill(selected ? LumeTheme.raised : .clear))
                                .overlay(alignment: .leading) {
                                    if selected { Rectangle().fill(LumeTheme.accent).frame(width: 2).padding(.vertical, 6) }
                                }
                                .contentShape(Rectangle())
                        }.buttonStyle(.plain)
                            .accessibilityLabel(component.nome + ", " + component.licenca)
                            .accessibilityAddTraits(selected ? .isSelected : [])
                    }
                }.padding(.horizontal, 10).padding(.bottom, 12)
            }
        }
    }

    @ViewBuilder
    private var detail: some View {
        if let component = components.first(where: { $0.id == selectedID }) {
            VStack(alignment: .leading, spacing: 14) {
                VStack(alignment: .leading, spacing: 6) {
                    Kicker(title: component.uso).padding(.top, 28)
                    HStack(alignment: .firstTextBaseline) {
                        Text(component.nome).font(LumeFont.display(24, weight: .semibold))
                        if !component.versao.isEmpty {
                            Text(component.versao).font(LumeFont.ui(12)).foregroundStyle(LumeTheme.secondary)
                        }
                    }
                    HStack {
                        Text(component.licenca).font(LumeFont.ui(12, weight: .semibold)).foregroundStyle(LumeTheme.accent)
                        Spacer()
                        if let first = component.arquivos.first.flatMap(fileURL) {
                            Button("Mostrar no Finder") { NSWorkspace.shared.activateFileViewerSelecting([first]) }
                                .buttonStyle(LumeButtonStyle(kind: .soft)).lineLimit(1).fixedSize()
                        }
                    }
                }
                ScrollView {
                    Text(licenseText(component).isEmpty ? "Texto de licença não encontrado no motor." : licenseText(component))
                        .font(.system(size: 11, design: .monospaced)).lineSpacing(2)
                        .textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading).padding(16)
                }.background(RoundedRectangle(cornerRadius: LumeRadius.large).fill(LumeTheme.raised))
                    .overlay(RoundedRectangle(cornerRadius: LumeRadius.large).strokeBorder(LumeTheme.line))
            }.padding(22)
        } else {
            Text("Escolha um componente para ler a licença.").font(LumeFont.ui(13)).foregroundStyle(LumeTheme.secondary)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }

    private var missing: some View {
        VStack(alignment: .leading, spacing: 10) {
            Kicker(title: "Licenças")
            Text("Este motor não traz o índice de licenças.").font(LumeFont.display(22, weight: .semibold))
            Text("As licenças acompanham o motor embutido no app montado com scripts/montar-lume.command. Instalações de desenvolvimento e motores anteriores à versão 1.0 não incluem o índice.")
                .font(LumeFont.ui(13)).foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
        }.padding(32).frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
    }
}

/// Substitui o item “Sobre” padrão do menu do app.
struct SobreCommands: Commands {
    @Environment(\.openWindow) private var openWindow
    var body: some Commands {
        CommandGroup(replacing: .appInfo) {
            Button("Sobre o Lume") { openWindow(id: "sobre") }
        }
    }
}
