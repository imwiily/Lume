import SwiftUI
import AppKit

/// Ajustar o que procurar: as verificações de `SearchRule.all`, onde procurar e como o texto está
/// marcado. Edita `store.searchSettings` sem mudar o seu formato.
@MainActor
struct SearchSettingsView: View {
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
        var detail: String {
            switch self {
            case .checks: return "O que procurar"
            case .areas: return "Onde procurar"
            case .structure: return "Como o texto está marcado"
            }
        }
    }
    @State private var section: Section = .checks
    private var panelHeight: CGFloat {
        min(680, max(460, (NSScreen.main?.visibleFrame.height ?? 840) - 180))
    }
    @State private var titlesText = ""
    @State private var stylesText = ""
    @State private var namesText = ""
    private let scopes = [("narracao", "Narração"), ("dialogo", "Falas"), ("pensamento", "Pensamentos marcados")]
    private var activeRules: Int { SearchRule.all.filter { store.searchSettings.rules[$0.id] ?? false }.count }

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
    private func heading(_ title: String) -> some View { Text(title).font(LumeFont.display(21, weight: .semibold)) }
    private func subheading(_ title: String) -> some View { Text(title).font(LumeFont.ui(13, weight: .semibold)) }
    private func note(_ text: String) -> some View {
        Text(text).font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
    }
    private func editor(_ text: Binding<String>, height: CGFloat) -> some View {
        TextEditor(text: text).font(LumeFont.ui(12)).scrollContentBackground(.hidden).padding(6).frame(height: height)
            .background(RoundedRectangle(cornerRadius: LumeRadius.medium).fill(LumeTheme.raised))
            .overlay(RoundedRectangle(cornerRadius: LumeRadius.medium).strokeBorder(LumeTheme.line))
    }
    private func group<Content: View>(@ViewBuilder _ content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 10) { content() }
            .padding(14).frame(maxWidth: .infinity, alignment: .leading)
            .background(RoundedRectangle(cornerRadius: LumeRadius.medium).fill(LumeTheme.raised))
            .overlay(RoundedRectangle(cornerRadius: LumeRadius.medium).strokeBorder(LumeTheme.line))
    }

    private var checks: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline) {
                heading("O que procurar")
                Spacer()
                Text("\(activeRules) de \(SearchRule.all.count) ativas").font(LumeFont.ui(11.5)).monospacedDigit()
                    .foregroundStyle(LumeTheme.secondary)
            }
            note("Cada verificação pode ser ativada separadamente. O modo de leitura (língua, história ou completa) continua limitando quais camadas serão executadas.")
            group {
                ForEach(SearchRule.all) { rule in
                    Toggle(rule.title, isOn: Binding(get: { store.searchSettings.rules[rule.id] ?? false },
                                                     set: { store.searchSettings.rules[rule.id] = $0 }))
                        .font(LumeFont.ui(13))
                }
            }
            HStack {
                Button("Ativar todas") { for rule in SearchRule.all { store.searchSettings.rules[rule.id] = true } }
                Button("Desativar todas") { for rule in SearchRule.all { store.searchSettings.rules[rule.id] = false } }
            }.buttonStyle(LumeButtonStyle(kind: .soft))
        }
    }
    private var areas: some View {
        VStack(alignment: .leading, spacing: 12) {
            heading("Onde procurar")
            group {
                subheading("Palavras dobradas e frases repetidas")
                ForEach(scopes, id: \.0) { key, label in Toggle(label, isOn: scopeBinding(key, tense: false)) }
                Toggle("Comparar frases também entre parágrafos próximos", isOn: $store.searchSettings.duplicateAcrossParagraphs)
                Picker("Frases repetidas", selection: $store.searchSettings.duplicateSimilarity) {
                    Text("Mesmas palavras").tag(1.0)
                    Text("Sequências semelhantes").tag(0.85)
                }.pickerStyle(.menu)
                note("A comparação ignora maiúsculas e pontuação. Sequências semelhantes tornam a busca mais sensível.")
                note("A busca não cruza de uma fala para um inciso narrativo ao comparar palavras. Frases entre parágrafos podem pertencer a personagens diferentes; o motor ainda não identifica o falante.")
            }
            group {
                subheading("Mudanças de tempo verbal")
                ForEach(scopes, id: \.0) { key, label in Toggle(label, isOn: scopeBinding(key, tense: true)) }
                note("Estrutura e pontuação são verificadas na narração. Variações de nomes usam o documento inteiro. O corretor gramatical local mantém suas próprias proteções.")
            }
        }.font(LumeFont.ui(13))
    }
    private var structure: some View {
        VStack(alignment: .leading, spacing: 12) {
            heading("Como o texto está marcado")
            group {
                Toggle("Travessão inicial marca diálogo", isOn: $store.searchSettings.dialogueDashes)
                Picker("Trechos entre aspas representam", selection: $store.searchSettings.quotesRole) {
                    Text("Falas").tag("dialogo")
                    Text("Pensamentos").tag("pensamento")
                    Text("Manter como narração").tag("narracao")
                }.pickerStyle(.menu)
                Toggle("Itálico marca pensamento", isOn: $store.searchSettings.italicThoughts)
                note("Essas opções descrevem a marcação, não interpretam o sentido. Itálico pode ter outras funções. Pensamentos sem marcas continuam classificados como narração.")
            }
            group {
                subheading("Capítulos")
                Toggle("Reconhecer títulos e numeração automaticamente", isOn: $store.searchSettings.chapterAuto)
                note("Reconhece ‘Capítulo um’, ‘Capítulo 1’ e ‘Capítulo I’, estilos de título e níveis de estrutura. Para uma divisão própria, desative o automático e cadastre os títulos exatos abaixo.")
                Text("Títulos exatos · um por linha")
                editor($titlesText, height: 85).onChange(of: titlesText) { store.searchSettings.chapterTitles = lines($0) }
                Text("Estilos de parágrafo adicionais · um por linha")
                editor($stylesText, height: 65).onChange(of: stylesText) { store.searchSettings.chapterStyles = lines($0) }
                Text("Nomes aceitos · nomes e termos da obra (espécies, lugares, poderes) que não geram alerta de grafia nem de variação; o plural vale junto · um por linha")
                editor($namesText, height: 65).onChange(of: namesText) { store.searchSettings.ignoredNames = lines($0) }
            }
        }.font(LumeFont.ui(13))
    }

    private var sidebar: some View {
        VStack(alignment: .leading, spacing: 4) {
            Kicker(title: "Ajustar o que procurar").padding(.horizontal, 10).padding(.bottom, 6)
            ForEach(Section.allCases) { item in
                let selected = section == item
                Button { section = item } label: {
                    HStack(spacing: 9) {
                        Image(systemName: item.symbol).frame(width: 16).foregroundStyle(selected ? LumeTheme.amber : LumeTheme.secondary)
                        VStack(alignment: .leading, spacing: 1) {
                            Text(item.rawValue).font(LumeFont.ui(12.5, weight: selected ? .semibold : .regular))
                            Text(item.detail).font(LumeFont.ui(10.5)).foregroundStyle(LumeTheme.secondary)
                        }
                        Spacer(minLength: 0)
                    }.padding(.horizontal, 10).padding(.vertical, 7)
                        .background(RoundedRectangle(cornerRadius: LumeRadius.medium).fill(selected ? LumeTheme.raised : .clear))
                        .overlay(alignment: .leading) {
                            if selected { Rectangle().fill(LumeTheme.accent).frame(width: 2).padding(.vertical, 6) }
                        }
                        .contentShape(Rectangle())
                }.buttonStyle(.plain)
                    .accessibilityLabel(item.rawValue).accessibilityAddTraits(selected ? .isSelected : [])
            }
            Spacer()
            Text(store.documentURL?.lastPathComponent ?? "Próxima leitura").font(LumeFont.ui(11))
                .foregroundStyle(LumeTheme.secondary).lineLimit(2).truncationMode(.middle).padding(.horizontal, 10)
        }.padding(.vertical, 18).padding(.horizontal, 10).frame(width: 210).frame(maxHeight: .infinity)
            .background(LumeTheme.surface)
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 0) {
                sidebar
                Divider().overlay(LumeTheme.line)
                ScrollView {
                    VStack(alignment: .leading, spacing: 0) {
                        switch section {
                        case .checks: checks
                        case .areas: areas
                        case .structure: structure
                        }
                    }.frame(maxWidth: .infinity, alignment: .leading).padding(22)
                }.id(section).frame(maxWidth: .infinity, maxHeight: .infinity)
            }
            Divider().overlay(LumeTheme.line)
            VStack(alignment: .leading, spacing: 10) {
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
            }.padding(.horizontal, 20).padding(.vertical, 14).background(LumeTheme.surface)
        }.frame(width: 780, height: panelHeight)
            .background(LumeTheme.canvas).foregroundStyle(LumeTheme.ink).tint(LumeTheme.accent)
            .onAppear { refreshText() }
            .onDisappear { store.saveSearchSettings() }
    }
}
