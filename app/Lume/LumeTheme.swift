import SwiftUI
import AppKit

/// Identidade “Luz de leitura”: noite de ameixa, luz de vela e papel de linho.
/// Guia completo em docs/identidade/README.md. Todas as cores de texto passam no
/// contraste AA sobre as superfícies do mesmo modo (claro ou escuro).
enum LumeTheme {
    // Cores de marca, iguais nos dois modos.
    static let night = Color(hex: 0x2A1F3D)
    static let nightDeep = Color(hex: 0x1B1428)
    static let candle = Color(hex: 0xF2C46D)
    static let linen = Color(hex: 0xF7F1EA)
    static let blush = Color(hex: 0xE7A493)

    // Superfícies.
    static let canvas = adaptive(0xF7F1EA, 0x18131F)
    static let paper = adaptive(0xFFFCF7, 0x221B2D)
    static let wash = adaptive(0xEEE7F4, 0x2E2540)
    static let line = adaptive(0xE6DCD2, 0x3A3047)

    // Texto e ação.
    static let ink = adaptive(0x2B2238, 0xF4EDE4)
    static let secondary = adaptive(0x6A5F74, 0xB8ACC2)
    static let accent = adaptive(0x5B3F8C, 0xCDB8F2)
    static let rose = adaptive(0xA24E3E, 0xF0A898)
    static let amber = adaptive(0x8A5A12, 0xF2C46D)

    // Sentido editorial: sempre acompanhado de ícone e texto.
    static let error = adaptive(0xA8323F, 0xF49AA4)
    static let style = adaptive(0x3F55A0, 0xAFC0F5)
    static let sage = adaptive(0x3A7257, 0x9ED2B5)

    /// Fundo suave do trecho sinalizado: a “luz” sobre a página.
    static let glow = adaptive(0xF8DCCF, 0x5A3A3A)

    static func adaptive(_ light: UInt, _ dark: UInt) -> Color {
        Color(NSColor(name: nil) { appearance in
            let value = appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua ? dark : light
            return NSColor(srgbRed: Double((value >> 16) & 255) / 255,
                           green: Double((value >> 8) & 255) / 255,
                           blue: Double(value & 255) / 255, alpha: 1)
        })
    }
}

/// Serifada (New York) para voz e leitura; arredondada (SF Rounded) para a interface.
enum LumeFont {
    static func display(_ size: CGFloat, weight: Font.Weight = .regular) -> Font {
        .system(size: size, weight: weight, design: .serif)
    }
    static func ui(_ size: CGFloat, weight: Font.Weight = .regular) -> Font {
        .system(size: size, weight: weight, design: .rounded)
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
            RoundedRectangle(cornerRadius: size * 0.27, style: .continuous)
                .fill(LinearGradient(colors: [LumeTheme.night, LumeTheme.nightDeep], startPoint: .top, endPoint: .bottom))
            Circle().fill(RadialGradient(colors: [LumeTheme.candle.opacity(glowing ? 0.55 : 0.38), .clear],
                                         center: .center, startRadius: 0, endRadius: size * 0.36))
                .frame(width: size * 0.8, height: size * 0.8).offset(y: -size * 0.1)
            OpenBook().stroke(LumeTheme.linen, style: StrokeStyle(lineWidth: size * 0.05, lineCap: .round, lineJoin: .round))
            Flame().fill(LinearGradient(colors: [LumeTheme.candle, LumeTheme.blush], startPoint: .top, endPoint: .bottom))
                .frame(width: size * 0.15, height: size * 0.25).offset(y: -size * 0.1)
        }.frame(width: size, height: size).accessibilityHidden(true)
    }
}

/// Apenas a chama, para usos pequenos sobre texto (progresso, marcadores).
struct FlameGlyph: View {
    var size: CGFloat = 16
    var body: some View {
        Flame().fill(LinearGradient(colors: [LumeTheme.candle, LumeTheme.blush], startPoint: .top, endPoint: .bottom))
            .frame(width: size * 0.6, height: size).accessibilityHidden(true)
    }
}

struct OpenBook: Shape {
    func path(in rect: CGRect) -> Path {
        func p(_ x: CGFloat, _ y: CGFloat) -> CGPoint { CGPoint(x: rect.minX + rect.width * x, y: rect.minY + rect.height * y) }
        var path = Path()
        path.move(to: p(0.2, 0.58))
        path.addQuadCurve(to: p(0.5, 0.68), control: p(0.36, 0.54))
        path.addQuadCurve(to: p(0.8, 0.58), control: p(0.64, 0.54))
        path.move(to: p(0.2, 0.69))
        path.addQuadCurve(to: p(0.5, 0.79), control: p(0.36, 0.65))
        path.addQuadCurve(to: p(0.8, 0.69), control: p(0.64, 0.65))
        return path
    }
}

struct Flame: Shape {
    func path(in rect: CGRect) -> Path {
        func p(_ x: CGFloat, _ y: CGFloat) -> CGPoint { CGPoint(x: rect.minX + rect.width * x, y: rect.minY + rect.height * y) }
        var path = Path()
        path.move(to: p(0.5, 0))
        path.addCurve(to: p(0.5, 1), control1: p(0.78, 0.3), control2: p(1.08, 0.98))
        path.addCurve(to: p(0.5, 0), control1: p(-0.08, 0.98), control2: p(0.22, 0.3))
        path.closeSubpath()
        return path
    }
}

// MARK: - Componentes

/// Botões em cápsula. `.primary` é a luz (vela sobre ameixa); `.quiet` é contorno.
struct LumeButtonStyle: ButtonStyle {
    enum Kind { case primary, quiet, soft }
    var kind: Kind = .quiet
    @Environment(\.isEnabled) private var enabled
    func makeBody(configuration: Configuration) -> some View {
        configuration.label.font(LumeFont.ui(13, weight: kind == .primary ? .semibold : .medium))
            .padding(.horizontal, kind == .primary ? 20 : 14).padding(.vertical, kind == .primary ? 11 : 8)
            .foregroundStyle(kind == .primary ? LumeTheme.night : (kind == .soft ? LumeTheme.accent : LumeTheme.ink))
            .background(Capsule().fill(kind == .primary ? LumeTheme.candle : (kind == .soft ? LumeTheme.wash : LumeTheme.paper)))
            .overlay(Capsule().strokeBorder(kind == .quiet ? LumeTheme.line : .clear))
            .shadow(color: kind == .primary && enabled ? LumeTheme.candle.opacity(0.45) : .clear, radius: 10, y: 3)
            .scaleEffect(configuration.isPressed ? 0.97 : 1)
            .opacity(enabled ? 1 : 0.45)
            .contentShape(Capsule())
    }
}

/// Superfície de papel com cantos suaves.
struct Sheet<Content: View>: View {
    var padding: CGFloat = 22
    var fill: Color = LumeTheme.paper
    @ViewBuilder var content: Content
    var body: some View {
        content.padding(padding).frame(maxWidth: .infinity, alignment: .topLeading)
            .background(RoundedRectangle(cornerRadius: 20, style: .continuous).fill(fill))
            .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).strokeBorder(LumeTheme.line.opacity(0.8)))
    }
}

/// Rótulo pequeno em versalete, precedido de uma chama.
struct Kicker: View {
    let title: String
    var color: Color = LumeTheme.secondary
    var body: some View {
        HStack(spacing: 6) {
            FlameGlyph(size: 10)
            Text(title.uppercased()).font(LumeFont.ui(10, weight: .semibold)).tracking(1.4).foregroundStyle(color)
        }
    }
}

/// Anel de progresso das avaliações.
struct LightRing: View {
    let value: Double
    var size: CGFloat = 38
    var body: some View {
        ZStack {
            Circle().stroke(LumeTheme.line, lineWidth: 4)
            Circle().trim(from: 0, to: max(0.001, min(1, value)))
                .stroke(LinearGradient(colors: [LumeTheme.candle, LumeTheme.blush], startPoint: .top, endPoint: .bottom),
                        style: StrokeStyle(lineWidth: 4, lineCap: .round))
                .rotationEffect(.degrees(-90))
        }.frame(width: size, height: size).accessibilityHidden(true)
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
        }
    }
    var shortcut: KeyEquivalent {
        KeyEquivalent(Character(String((ReviewDecision.allCases.firstIndex(of: self) ?? 0) + 1)))
    }
}

extension FindingSeverity {
    var color: Color {
        switch self {
        case .confirmed_error, .probable_error: return LumeTheme.error
        case .editorial_attention: return LumeTheme.rose
        case .possible_inconsistency: return LumeTheme.amber
        case .author_query: return LumeTheme.style
        }
    }
}
