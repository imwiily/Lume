import SwiftUI
import AppKit

enum LumeTheme {
    static let forest = Color(hex: 0x173E36)
    static let cream = Color(hex: 0xF4EFE5)
    static let gold = Color(hex: 0xDCB58B)
    static let railMuted = Color(hex: 0xC1D1C8)
    static let canvas = adaptive(0xF4EFE5, 0x17221F)
    static let paper = adaptive(0xFFFCF6, 0x202E29)
    static let ink = adaptive(0x233D34, 0xF4EFE5)
    static let secondary = adaptive(0x5D695F, 0xB7C4BC)
    static let line = adaptive(0xDDDCD0, 0x405148)
    static let wash = adaptive(0xE8EDE4, 0x30473D)
    static let accent = adaptive(0x245548, 0xA9CEB7)
    static let copper = adaptive(0x97512F, 0xE5AD82)
    static let error = adaptive(0xA0443D, 0xF1A69A)
    static let style = adaptive(0x44617B, 0xA8C6DF)

    private static func adaptive(_ light: UInt, _ dark: UInt) -> Color {
        Color(NSColor(name: nil) { appearance in
            let value = appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua ? dark : light
            return NSColor(srgbRed: Double((value >> 16) & 255) / 255,
                           green: Double((value >> 8) & 255) / 255,
                           blue: Double(value & 255) / 255, alpha: 1)
        })
    }
}

extension Color {
    init(hex: UInt) {
        self.init(.sRGB, red: Double((hex >> 16) & 255) / 255,
                  green: Double((hex >> 8) & 255) / 255, blue: Double(hex & 255) / 255, opacity: 1)
    }
}

struct LumeMark: View {
    var size: CGFloat = 48
    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: size * 0.24).fill(LumeTheme.forest)
            BookGlyph().stroke(LumeTheme.cream, style: StrokeStyle(lineWidth: size * 0.045, lineCap: .round, lineJoin: .round))
            Circle().fill(LumeTheme.gold).frame(width: size * 0.115, height: size * 0.115)
                .offset(y: -size * 0.27)
        }.frame(width: size, height: size).accessibilityHidden(true)
    }
}

private struct BookGlyph: Shape {
    func path(in rect: CGRect) -> Path {
        func p(_ x: CGFloat, _ y: CGFloat) -> CGPoint { CGPoint(x: rect.minX + rect.width * x, y: rect.minY + rect.height * y) }
        var path = Path()
        path.move(to: p(0.5, 0.43))
        path.addCurve(to: p(0.24, 0.34), control1: p(0.41, 0.35), control2: p(0.32, 0.33))
        path.addLine(to: p(0.24, 0.67))
        path.addCurve(to: p(0.5, 0.77), control1: p(0.34, 0.67), control2: p(0.43, 0.70))
        path.addCurve(to: p(0.76, 0.67), control1: p(0.57, 0.70), control2: p(0.66, 0.67))
        path.addLine(to: p(0.76, 0.34))
        path.addCurve(to: p(0.5, 0.43), control1: p(0.68, 0.33), control2: p(0.59, 0.35))
        path.addLine(to: p(0.5, 0.77))
        return path
    }
}

struct LumeButtonStyle: ButtonStyle {
    var prominent = false
    var onDark = false
    @Environment(\.isEnabled) private var enabled
    func makeBody(configuration: Configuration) -> some View {
        configuration.label.font(.system(size: 13, weight: .medium))
            .padding(.horizontal, 13).padding(.vertical, 10)
            .foregroundStyle(prominent ? (onDark ? LumeTheme.forest : LumeTheme.cream) : (onDark ? LumeTheme.cream : LumeTheme.ink))
            .background(RoundedRectangle(cornerRadius: 9).fill(prominent ? (onDark ? LumeTheme.gold : LumeTheme.forest) : (onDark ? Color.white.opacity(0.08) : LumeTheme.paper)))
            .overlay(RoundedRectangle(cornerRadius: 9).strokeBorder(onDark ? Color.white.opacity(0.15) : LumeTheme.line, lineWidth: prominent ? 0 : 1))
            .opacity(enabled ? (configuration.isPressed ? 0.75 : 1) : 0.4)
    }
}

struct Eyebrow: View {
    let title: String
    var color: Color = LumeTheme.secondary
    var body: some View {
        Text(title.uppercased()).font(.system(size: 10, weight: .semibold)).tracking(1.7).foregroundStyle(color)
    }
}

extension ReviewDecision {
    var symbol: String {
        switch self {
        case .pending: return "circle.dotted"
        case .error: return "exclamationmark.circle"
        case .style: return "pencil.line"
        case .falsePositive: return "checkmark.seal"
        case .intentional: return "quote.bubble"
        case .accepted: return "checkmark.circle"
        }
    }
    var color: Color {
        switch self {
        case .pending: return LumeTheme.secondary
        case .error: return LumeTheme.error
        case .style: return LumeTheme.style
        case .falsePositive: return LumeTheme.accent
        case .intentional: return LumeTheme.style
        case .accepted: return LumeTheme.accent
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
}
