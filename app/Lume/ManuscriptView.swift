import SwiftUI

/// O manuscrito como papel: o parágrafo do alerta, iluminado, entre os parágrafos próximos que o
/// relatório traz (`context`). O texto é exatamente o devolvido pelo motor; só o fundo do trecho muda.
@MainActor
struct ManuscriptView: View {
    @EnvironmentObject private var store: ReviewStore
    @AppStorage("lumeReadingSize") private var readingSize = 21.0
    let finding: Finding
    /// Com o inspetor recolhido (janela estreita), ele aparece abaixo da página.
    var inspectorBelow = false
    @State private var copiedID: String?

    private var textSize: CGFloat { CGFloat(min(28, max(15, readingSize))) }
    /// Cerca de 65–75 caracteres por linha na serifada, mais as margens da página.
    private var pageWidth: CGFloat { min(820, textSize * 33 + 2 * margin) }
    private let margin: CGFloat = 56

    /// Parágrafos do mesmo capítulo, em ordem, sem repetir o parágrafo do alerta.
    private var paragraphs: [(number: Int, text: String)] {
        var items: [(number: Int, text: String)] = (finding.context ?? [])
            // O título do capítulo já está no cabeçalho da página.
            .filter { $0.document == "atual" && $0.chapter == finding.chapter && $0.paragraph != finding.paragraph
                      && $0.text != finding.chapter }
            .map { ($0.paragraph, $0.text) }
        items.append((finding.paragraph, finding.text))
        var seen = Set<Int>()
        return items.filter { seen.insert($0.number).inserted }.sorted { $0.number < $1.number }
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 14) {
                tools.frame(maxWidth: pageWidth)
                page
                if inspectorBelow {
                    FindingInspector(finding: finding).frame(maxWidth: pageWidth)
                        .background(RoundedRectangle(cornerRadius: LumeRadius.large).fill(LumeTheme.surface))
                        .overlay(RoundedRectangle(cornerRadius: LumeRadius.large).strokeBorder(LumeTheme.line))
                }
            }.padding(.horizontal, 24).padding(.vertical, 18).frame(maxWidth: .infinity)
        }.background(LumeTheme.sunken.opacity(0.55))
    }

    private var tools: some View {
        HStack(spacing: 12) {
            if store.editCount(inParagraph: finding.paragraph) > 0 {
                Label("Este parágrafo já recebeu correções; o texto mostrado é o da análise.", systemImage: "pencil.line")
                    .font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary).lineLimit(1)
            }
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
            Button { readingSize = max(15, readingSize - 1) } label: { Text("A").font(.system(size: 11)) }
                .accessibilityLabel("Diminuir tamanho do texto").disabled(readingSize <= 15)
                .help("Diminuir o texto")
            Button { readingSize = min(28, readingSize + 1) } label: { Text("A").font(.system(size: 15)) }
                .accessibilityLabel("Aumentar tamanho do texto").disabled(readingSize >= 28)
                .help("Aumentar o texto")
        }.buttonStyle(.borderless).foregroundStyle(LumeTheme.secondary)
    }

    private var page: some View {
        VStack(alignment: .leading, spacing: textSize * 0.9) {
            VStack(spacing: 10) {
                Text(finding.chapter.uppercased()).font(LumeFont.ui(10.5, weight: .semibold)).tracking(1.6)
                    .foregroundStyle(LumeTheme.amber).multilineTextAlignment(.center)
                Rectangle().fill(LumeTheme.candle).frame(width: 28, height: 1.5)
            }.frame(maxWidth: .infinity).padding(.bottom, 8)
            ForEach(paragraphs, id: \.number) { item in
                if item.number == finding.paragraph {
                    illuminated
                        .overlay(alignment: .topLeading) { marker.offset(x: -margin + 8) }
                } else {
                    Text(item.text).foregroundStyle(LumeTheme.ink.opacity(0.72))
                        .font(LumeFont.display(textSize)).lineSpacing(textSize * 0.45)
                        .textSelection(.enabled).fixedSize(horizontal: false, vertical: true)
                }
            }
            footer.padding(.top, 14)
        }.padding(.horizontal, margin).padding(.top, 40).padding(.bottom, 28)
            .frame(maxWidth: pageWidth, alignment: .leading)
            .background(RoundedRectangle(cornerRadius: LumeRadius.small).fill(LumeTheme.paper))
            .overlay(RoundedRectangle(cornerRadius: LumeRadius.small).strokeBorder(LumeTheme.line))
            .shadow(color: LumeTheme.nightDeep.opacity(0.05), radius: 3, y: 1)
    }

    /// O trecho recebe luz de vela ao fundo e um traço sob o texto; o texto não muda.
    private var illuminated: some View {
        let parts = finding.segments
        var marked = AttributedString(parts.marked)
        marked.backgroundColor = LumeTheme.glow
        marked.foregroundColor = LumeTheme.ink
        return (Text(parts.before) + Text(marked).underline(true, color: LumeTheme.glowLine) + Text(parts.after))
            .font(LumeFont.display(textSize)).lineSpacing(textSize * 0.45)
            .foregroundStyle(LumeTheme.ink)
            .textSelection(.enabled).fixedSize(horizontal: false, vertical: true)
            .accessibilityLabel(parts.before + parts.marked + parts.after)
            .accessibilityHint("Trecho em destaque: \(parts.marked)")
    }

    private var marker: some View {
        VStack(spacing: 3) {
            FlameGlyph(size: 13)
            Text("§ \(finding.paragraph)").font(LumeFont.ui(9.5, weight: .medium)).foregroundStyle(LumeTheme.amber)
                .fixedSize()
        }.frame(width: 36).padding(.top, 4).accessibilityHidden(true)
    }

    private var footer: some View {
        let ext = store.documentURL?.pathExtension.lowercased()
        let text: String
        let symbol: String
        if store.canEditManuscript {
            text = "Pages · correção controlada, alerta por alerta; uma cópia do original é guardada antes da primeira"
            symbol = "doc.richtext"
        } else if ext == "docx" {
            text = "Word (.docx) · somente leitura: a análise nunca altera o arquivo"
            symbol = "lock.doc"
        } else {
            text = "Relatório aberto sem o manuscrito · somente leitura"
            symbol = "doc.plaintext"
        }
        return VStack(alignment: .leading, spacing: 8) {
            Divider().overlay(LumeTheme.line)
            Label(text, systemImage: symbol).font(LumeFont.ui(10.5)).foregroundStyle(LumeTheme.tertiary)
        }
    }
}
