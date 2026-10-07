import SwiftUI
import AppKit

/// Identidade “Nocturne & Candlelight”: o manuscrito é papel, o Lume é instrumento, a atenção é luz.
/// Noite de ameixa para a estrutura, linho e papel para as superfícies, vela só para a atenção.
/// Todas as cores de texto passam no contraste AA sobre as superfícies do mesmo modo.
enum LumeTheme {
    // Cores de marca, iguais nos dois modos.
    static let night = Color(hex: 0x2A1F3D)
    static let nightDeep = Color(hex: 0x1B1428)
    static let candle = Color(hex: 0xF2C46D)
    static let linen = Color(hex: 0xF7F1EA)
    static let paperWhite = Color(hex: 0xFFFCF7)
    static let blush = Color(hex: 0xE7A493)
    /// Páginas do livro no símbolo.
    static let bookPage = Color(hex: 0xECE4DC)

    // Superfícies: janela, painéis, cartões em relevo, página do manuscrito e campos.
    static let canvas = adaptive(0xF7F1EA, 0x17121F)
    static let surface = adaptive(0xFBF7F1, 0x1F1829)
    static let raised = adaptive(0xFFFCF7, 0x272033)
    static let paper = adaptive(0xFFFCF7, 0x221B2C)
    static let sunken = adaptive(0xF0E8DF, 0x2C2438)
    static let line = adaptive(0xE6DCD1, 0x372D44)
    static let lineStrong = adaptive(0xCFC4B8, 0x4E4362)

    // Texto.
    static let ink = adaptive(0x221A2E, 0xF4EDE4)
    static let secondary = adaptive(0x5E5468, 0xB9ADC4)
    static let tertiary = adaptive(0x7D7286, 0x968AA2)

    // Ação: a noite conduz a interface; no escuro, um lilás claro.
    static let accent = adaptive(0x2A1F3D, 0xD9CCEE)
    static let onAccent = adaptive(0xF7F1EA, 0x1B1428)
    /// Fundo discreto de item selecionado ou realçado.
    static let wash = adaptive(0xEFE7F3, 0x30263F)

    // Atenção: a luz da vela sobre o trecho, nunca como cor de erro.
    static let glow = adaptive(0xFCEBC6, 0x4A3A22)
    static let glowLine = adaptive(0xD9A441, 0xF2C46D)
    /// Texto na cor da vela com contraste suficiente sobre superfícies claras.
    static let amber = adaptive(0x7A5410, 0xF2C46D)

    // Sentido editorial: sempre acompanhado de ícone e texto.
    static let error = adaptive(0xA8323F, 0xF49AA4)
    static let rose = adaptive(0xA24E3E, 0xF0A898)
    static let style = adaptive(0x3F55A0, 0xAFC0F5)
    static let sage = adaptive(0x3A7257, 0x9ED2B5)

    static func adaptive(_ light: UInt, _ dark: UInt) -> Color {
        Color(NSColor(name: nil) { appearance in
            let value = appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua ? dark : light
            return NSColor(srgbRed: Double((value >> 16) & 255) / 255,
                           green: Double((value >> 8) & 255) / 255,
                           blue: Double(value & 255) / 255, alpha: 1)
        })
    }
}

/// Raios pequenos e precisos: estrutura de ferramenta, não de cartão de site.
enum LumeRadius {
    static let small: CGFloat = 4
    static let medium: CGFloat = 6
    static let large: CGFloat = 8
}

/// New York (serifada do sistema) para manuscrito, capítulos e voz literária; SF Pro para a interface.
enum LumeFont {
    static func display(_ size: CGFloat, weight: Font.Weight = .regular) -> Font {
        .system(size: size, weight: weight, design: .serif)
    }
    static func ui(_ size: CGFloat, weight: Font.Weight = .regular) -> Font {
        .system(size: size, weight: weight)
    }
}

extension Color {
    init(hex: UInt) {
        self.init(.sRGB, red: Double((hex >> 16) & 255) / 255,
                  green: Double((hex >> 8) & 255) / 255, blue: Double(hex & 255) / 255, opacity: 1)
    }
}

// MARK: - Marca

/// Símbolo: uma chama sobre um livro aberto — a luz que acompanha a leitura.
struct LumeMark: View {
    var size: CGFloat = 48
    var glowing = false
    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: size * 0.22, style: .continuous)
                .fill(LinearGradient(colors: [LumeTheme.night, LumeTheme.nightDeep], startPoint: .top, endPoint: .bottom))
            if glowing {
                Circle().fill(RadialGradient(colors: [LumeTheme.candle.opacity(0.32), .clear],
                                             center: .center, startRadius: 0, endRadius: size * 0.3))
                    .frame(width: size * 0.6, height: size * 0.6).offset(y: -size * 0.08)
            }
            BookPages().fill(LumeTheme.bookPage)
                .frame(width: size * 0.48, height: size * 0.18).offset(y: size * 0.13)
            Teardrop().fill(LumeTheme.candle)
                .frame(width: size * 0.15, height: size * 0.27).offset(y: -size * 0.065)
            Teardrop().fill(LumeTheme.paperWhite)
                .frame(width: size * 0.053, height: size * 0.095).offset(y: -size * 0.02)
        }.frame(width: size, height: size).accessibilityHidden(true)
    }
}

/// Só a chama, para usos pequenos (marcadores de atenção, progresso).
struct FlameGlyph: View {
    var size: CGFloat = 16
    var color: Color = LumeTheme.candle
    var body: some View {
        Teardrop().fill(color).frame(width: size * 0.56, height: size).accessibilityHidden(true)
    }
}

/// Gota de chama: ponta em cima, base redonda.
struct Teardrop: Shape {
    func path(in rect: CGRect) -> Path {
        let w = rect.width, h = rect.height
        let center = CGPoint(x: rect.minX + w / 2, y: rect.maxY - w / 2)
        var path = Path()
        path.move(to: CGPoint(x: rect.midX, y: rect.minY))
        path.addQuadCurve(to: CGPoint(x: rect.maxX, y: center.y), control: CGPoint(x: rect.minX + w * 0.98, y: rect.minY + h * 0.4))
        path.addArc(center: center, radius: w / 2, startAngle: .degrees(0), endAngle: .degrees(180), clockwise: false)
        path.addQuadCurve(to: CGPoint(x: rect.midX, y: rect.minY), control: CGPoint(x: rect.minX + w * 0.02, y: rect.minY + h * 0.4))
        path.closeSubpath()
        return path
    }
}

/// Livro aberto em duas páginas cheias, separadas pela lombada.
struct BookPages: Shape {
    func path(in rect: CGRect) -> Path {
        func p(_ x: CGFloat, _ y: CGFloat) -> CGPoint { CGPoint(x: rect.minX + rect.width * x, y: rect.minY + rect.height * y) }
        var path = Path()
        for side in [false, true] {
            // Página esquerda em coordenadas próprias; a direita é o espelho.
            func q(_ x: CGFloat, _ y: CGFloat) -> CGPoint { side ? p(1 - x, y) : p(x, y) }
            path.move(to: q(0, 0.13))
            path.addQuadCurve(to: q(0.488, 0.07), control: q(0.25, -0.06))
            path.addLine(to: q(0.488, 1))
            path.addQuadCurve(to: q(0, 0.97), control: q(0.25, 0.78))
            path.closeSubpath()
        }
        return path
    }
}

// MARK: - Componentes

/// Botões retangulares de cantos discretos.
/// `.primary`: ação principal (noite). `.secondary`: ação comum. `.soft`: ação de apoio. `.plain`: texto.
struct LumeButtonStyle: ButtonStyle {
    enum Kind { case primary, secondary, soft, plain }
    var kind: Kind = .secondary
    @Environment(\.isEnabled) private var enabled
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(LumeFont.ui(13, weight: kind == .primary ? .semibold : .medium))
            .padding(.horizontal, kind == .plain ? 2 : (kind == .primary ? 16 : 12))
            .padding(.vertical, kind == .plain ? 2 : (kind == .primary ? 8 : 6))
            .foregroundStyle(foreground)
            .background(RoundedRectangle(cornerRadius: LumeRadius.medium, style: .continuous).fill(background))
            .overlay(RoundedRectangle(cornerRadius: LumeRadius.medium, style: .continuous)
                .strokeBorder(kind == .secondary ? LumeTheme.lineStrong.opacity(0.7) : .clear))
            .opacity(enabled ? (configuration.isPressed ? 0.8 : 1) : 0.45)
            .contentShape(RoundedRectangle(cornerRadius: LumeRadius.medium))
    }
    private var foreground: Color {
        switch kind {
        case .primary: return LumeTheme.onAccent
        case .plain: return LumeTheme.accent
        default: return LumeTheme.ink
        }
    }
    private var background: Color {
        switch kind {
        case .primary: return LumeTheme.accent
        case .secondary: return LumeTheme.raised
        case .soft: return LumeTheme.sunken
        case .plain: return .clear
        }
    }
}

/// Painel de instrumento: superfície plana, contorno fino, sem sombra.
struct Panel<Content: View>: View {
    var padding: CGFloat = 18
    var fill: Color = LumeTheme.surface
    @ViewBuilder var content: Content
    var body: some View {
        content.padding(padding).frame(maxWidth: .infinity, alignment: .topLeading)
            .background(RoundedRectangle(cornerRadius: LumeRadius.large, style: .continuous).fill(fill))
            .overlay(RoundedRectangle(cornerRadius: LumeRadius.large, style: .continuous).strokeBorder(LumeTheme.line))
    }
}

/// Rótulo de seção em versalete; a chama aparece só quando o rótulo fala de atenção.
struct Kicker: View {
    let title: String
    var color: Color = LumeTheme.secondary
    var flame = false
    var body: some View {
        HStack(spacing: 6) {
            if flame { FlameGlyph(size: 10) }
            Text(title.uppercased()).font(LumeFont.ui(10.5, weight: .semibold)).tracking(0.8).foregroundStyle(color)
        }.accessibilityElement(children: .combine)
    }
}

/// Etiqueta da classificação automática: ícone, texto e cor, nunca só cor.
struct SeverityTag: View {
    let severity: FindingSeverity?
    var fallback = "Sem classificação"
    var body: some View {
        let color = severity?.color ?? LumeTheme.secondary
        HStack(spacing: 4) {
            Image(systemName: severity?.symbol ?? "circle").font(.system(size: 9, weight: .semibold))
            Text((severity?.title ?? fallback).uppercased()).font(LumeFont.ui(9.5, weight: .semibold)).tracking(0.5)
        }.foregroundStyle(color).padding(.horizontal, 6).padding(.vertical, 3)
            .background(RoundedRectangle(cornerRadius: LumeRadius.small).fill(color.opacity(0.12)))
            .accessibilityElement(children: .combine)
    }
}

/// Campo de busca retangular, no padrão dos painéis.
struct SearchField: View {
    let prompt: String
    @Binding var text: String
    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: "magnifyingglass").font(.system(size: 11)).foregroundStyle(LumeTheme.tertiary)
            TextField(prompt, text: $text).textFieldStyle(.plain).font(LumeFont.ui(12.5))
            if !text.isEmpty {
                Button { text = "" } label: { Image(systemName: "xmark.circle.fill") }
                    .buttonStyle(.plain).foregroundStyle(LumeTheme.tertiary).accessibilityLabel("Limpar busca")
            }
        }.padding(.horizontal, 9).padding(.vertical, 6)
            .background(RoundedRectangle(cornerRadius: LumeRadius.medium).fill(LumeTheme.raised))
            .overlay(RoundedRectangle(cornerRadius: LumeRadius.medium).strokeBorder(LumeTheme.line))
    }
}

/// Linha de opção com título, explicação e um controle à direita.
struct OptionRow<Accessory: View>: View {
    let title: String
    var detail: String? = nil
    @ViewBuilder var accessory: Accessory
    var body: some View {
        HStack(alignment: .center, spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(LumeFont.ui(13, weight: .medium))
                if let detail {
                    Text(detail).font(LumeFont.ui(11.5)).foregroundStyle(LumeTheme.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            Spacer(minLength: 8)
            accessory
        }
    }
}

extension ReviewDecision {
    var symbol: String {
        switch self {
        case .pending: return "circle.dotted"
        case .error: return "exclamationmark.circle"
        case .style: return "paintbrush.pointed"
        case .falsePositive: return "checkmark.seal"
        case .intentional: return "heart"
        case .accepted: return "checkmark.circle"
        case .corrected: return "pencil.circle"
        }
    }
    var color: Color {
        switch self {
        case .pending: return LumeTheme.secondary
        case .error: return LumeTheme.error
        case .style: return LumeTheme.style
        case .falsePositive: return LumeTheme.sage
        case .intentional: return LumeTheme.amber
        case .accepted: return LumeTheme.sage
        case .corrected: return LumeTheme.sage
        }
    }
    var explanation: String {
        switch self {
        case .pending: return "Voltar a este trecho depois"
        case .error: return "Há uma correção a fazer"
        case .style: return "Preservar a escolha narrativa"
        case .falsePositive: return "O alerta não se aplica"
        case .intentional: return "Escolha deliberada do autor"
        case .accepted: return "Avaliado e mantido na edição"
        case .corrected: return "A correção já foi feita"
        }
    }
    var shortcut: KeyEquivalent {
        KeyEquivalent(Character(String((ReviewDecision.allCases.firstIndex(of: self) ?? 0) + 1)))
    }
}

extension FindingSeverity {
    var color: Color {
        switch self {
        case .confirmed_error: return LumeTheme.error
        case .probable_error: return LumeTheme.rose
        case .editorial_attention: return LumeTheme.amber
        case .possible_inconsistency: return LumeTheme.style
        case .author_query: return LumeTheme.secondary
        }
    }
    var symbol: String {
        switch self {
        case .confirmed_error: return "xmark.octagon"
        case .probable_error: return "exclamationmark.circle"
        case .editorial_attention: return "lightbulb"
        case .possible_inconsistency: return "arrow.triangle.branch"
        case .author_query: return "questionmark.bubble"
        }
    }
}
