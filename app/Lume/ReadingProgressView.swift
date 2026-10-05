import SwiftUI

/// “Lendo com atenção…”: as etapas reais do pipeline (`store.analysisStages`), sem tempo restante
/// nem trecho ao vivo, que o motor não informa.
@MainActor
struct ReadingProgressView: View {
    @EnvironmentObject private var store: ReviewStore
    @State private var breathe = false

    private var documentName: String? { store.documentURL?.deletingPathExtension().lastPathComponent }
    private var running: AnalysisStage? { store.analysisStages.first { $0.state == "running" } }

    var body: some View {
        ScrollView {
            VStack(spacing: 18) {
                VStack(spacing: 0) {
                    ZStack {
                        // A animação vale só para a escala do círculo; com `withAnimation` no `onAppear`,
                        // o layout inicial da tela inteira também entraria na repetição.
                        Circle().fill(LumeTheme.glow).frame(width: 52, height: 52)
                            .scaleEffect(breathe ? 1.06 : 0.94)
                            .animation(.easeInOut(duration: 2.2).repeatForever(autoreverses: true), value: breathe)
                        FlameGlyph(size: 22, color: LumeTheme.amber)
                    }.frame(width: 60, height: 60)
                        .onAppear { breathe = true }
                        .padding(.top, 34)
                    Text("Lendo com atenção…").font(LumeFont.display(30, weight: .semibold)).padding(.top, 16)
                    if let documentName {
                        Text(documentName).font(LumeFont.ui(13)).foregroundStyle(LumeTheme.secondary).padding(.top, 4)
                    }
                    if let stage = running, let done = stage.done, let total = stage.total, total > 0 {
                        progress(stage, done: done, total: total).padding(.top, 24)
                    }
                    stages.padding(.top, 24)
                    HStack {
                        Text("Os pontos de atenção aparecem quando a leitura terminar.")
                            .font(LumeFont.ui(11.5)).foregroundStyle(LumeTheme.secondary)
                        Spacer()
                        Button { store.cancel() } label: { Label("Interromper leitura", systemImage: "xmark") }
                            .buttonStyle(LumeButtonStyle()).disabled(!store.canCancel)
                    }.padding(.top, 22).padding(.bottom, 26)
                }.padding(.horizontal, 32).frame(maxWidth: 660)
                    .background(RoundedRectangle(cornerRadius: LumeRadius.large).fill(LumeTheme.raised))
                    .overlay(RoundedRectangle(cornerRadius: LumeRadius.large).strokeBorder(LumeTheme.line))
                Text(store.embeddedEngine.map { "FONTE \($0.version)" } ?? store.engineDescription)
                    .font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary)
            }.padding(36).frame(maxWidth: .infinity)
        }.background(LumeTheme.canvas)
    }

    private func progress(_ stage: AnalysisStage, done: Int, total: Int) -> some View {
        let fraction = min(1, max(0, Double(done) / Double(total)))
        return VStack(alignment: .leading, spacing: 8) {
            HStack {
                Label(stage.title, systemImage: "book").font(LumeFont.ui(12.5))
                Spacer()
                Text("\(stage.progressText ?? "") (\(Int((fraction * 100).rounded()))%)")
                    .font(LumeFont.ui(12)).monospacedDigit().foregroundStyle(LumeTheme.secondary)
            }
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 2).fill(LumeTheme.sunken)
                    RoundedRectangle(cornerRadius: 2).fill(LumeTheme.candle)
                        .frame(width: max(4, geometry.size.width * fraction))
                }
            }.frame(height: 5)
        }.padding(14)
            .background(RoundedRectangle(cornerRadius: LumeRadius.medium).fill(LumeTheme.surface))
            .accessibilityElement(children: .combine)
            .accessibilityLabel("\(stage.title): \(stage.progressText ?? "")")
    }

    private var stages: some View {
        VStack(alignment: .leading, spacing: 6) {
            Kicker(title: "Etapas sequenciais")
            ForEach(Array(store.analysisStages.enumerated()), id: \.element.id) { index, stage in
                StageRow(index: index + 1, stage: stage)
            }
        }
    }
}

private struct StageRow: View {
    let index: Int
    let stage: AnalysisStage

    private var active: Bool { stage.state == "running" }
    private var quiet: Bool { ["pending", "skipped", "not_implemented"].contains(stage.state) }
    private var symbol: String {
        switch stage.state {
        case "completed": return "checkmark"
        case "running": return "flame"
        case "skipped": return "minus"
        case "failed": return "xmark"
        case "not_implemented": return "minus"
        default: return "hourglass"
        }
    }
    private var label: String {
        switch stage.state {
        case "completed": return "Concluído"
        case "running": return "Em andamento"
        case "skipped": return "Não selecionado"
        case "failed": return "Interrompido"
        case "not_implemented": return "Indisponível"
        default: return "Aguardando"
        }
    }

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: symbol).font(.system(size: 11, weight: .semibold))
                .foregroundStyle(stage.state == "failed" ? LumeTheme.error : (quiet ? LumeTheme.tertiary : LumeTheme.amber))
                .frame(width: 26, height: 26)
                .background(Circle().fill(quiet ? LumeTheme.sunken : LumeTheme.glow))
            VStack(alignment: .leading, spacing: 2) {
                Text("\(index). \(stage.title)").font(LumeFont.ui(13.5, weight: active ? .semibold : .medium))
                    .foregroundStyle(quiet ? LumeTheme.secondary : LumeTheme.ink)
                Text(stage.state == "completed" || active ? stage.statusText : (stage.detail.isEmpty ? label : stage.detail))
                    .font(LumeFont.ui(11.5)).foregroundStyle(LumeTheme.secondary).lineLimit(2).monospacedDigit()
            }
            Spacer(minLength: 8)
            Text(label).font(LumeFont.ui(11, weight: .medium)).foregroundStyle(active ? LumeTheme.amber : LumeTheme.secondary)
                .padding(.horizontal, 7).padding(.vertical, 3)
                .background(RoundedRectangle(cornerRadius: LumeRadius.small).fill(active ? LumeTheme.raised : LumeTheme.sunken))
        }.padding(.horizontal, 12).padding(.vertical, 9)
            .background(RoundedRectangle(cornerRadius: LumeRadius.medium).fill(active ? LumeTheme.glow.opacity(0.55) : LumeTheme.surface))
            .accessibilityElement(children: .combine)
    }
}
