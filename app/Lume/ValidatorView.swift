import SwiftUI

/// Validar decisões, na própria mesa: a terceira parte ao lado de Pendências e Observações. A confirmação, o
/// andamento e os resultados aparecem aqui, sem janela sobreposta. Nada é enviado antes da confirmação, e a
/// IA só sugere reconsiderar: nenhuma decisão, alerta ou trecho do manuscrito é alterado.
@MainActor
struct ValidationPanel: View {
    @EnvironmentObject private var store: ReviewStore

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                if let estimate = store.validatorEstimate {
                    confirmation(estimate)
                } else if store.isBusy && store.validation == nil {
                    HStack(spacing: 8) { ProgressView().controlSize(.small); Text(store.jobLabel.isEmpty ? "Validando decisões…" : store.jobLabel) }
                        .font(LumeFont.ui(12)).foregroundStyle(LumeTheme.secondary)
                } else if let validation = store.validation {
                    results(validation)
                } else {
                    idle
                }
            }.padding(14).frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    // MARK: Estados

    private var idle: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Segunda leitura das decisões que você já tomou. Ela só sugere reconsiderar, com evidências do texto: nenhuma decisão, alerta ou trecho do manuscrito é alterado.")
                .font(LumeFont.ui(12)).foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
            Text("Antes de enviar qualquer texto, o Lume mostra o que seria enviado, o custo estimado e pede a sua confirmação.")
                .font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
            Button("Validar decisões") { store.requestValidation() }
                .buttonStyle(LumeButtonStyle(kind: .primary)).disabled(!store.canValidateDecisions)
            if !store.canValidateDecisions {
                Text(store.isBusy ? "Aguarde a operação em andamento terminar."
                     : "Marque ao menos uma decisão (erro confirmado, estilo, falso positivo, intencional ou aceito) para validar.")
                    .font(LumeFont.ui(11)).foregroundStyle(LumeTheme.tertiary).fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    /// Confirmação antes de qualquer envio: quantas decisões, modelos, custo e teto da execução.
    private func confirmation(_ estimate: ValidatorEstimate) -> some View {
        let lines = estimate.lines(budget: store.validatorBudget)
        return VStack(alignment: .leading, spacing: 10) {
            Kicker(title: "Recursos com IA · confirmar")
            ForEach(Array(lines.enumerated()), id: \.offset) { index, line in
                let warning = estimate.warns(budget: store.validatorBudget) && index == lines.count - 1
                Text(line).font(LumeFont.ui(12, weight: warning ? .semibold : .regular))
                    .foregroundStyle(warning ? LumeTheme.error : LumeTheme.ink)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if estimate.aAvaliar > 0 {
                Stepper(value: $store.validatorBudget, in: 0.05...20, step: 0.25) {
                    Text(String(format: "Teto de gasto desta execução: US$ %.2f", store.validatorBudget)).font(LumeFont.ui(12))
                }
                Label("Os trechos selecionados e seus parágrafos vizinhos são enviados à API da Anthropic. Pela política atual da API, os dados não são usados para treino por padrão.",
                      systemImage: "hand.raised")
                    .font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
            }
            HStack {
                Spacer()
                Button("Cancelar") { store.cancelValidation() }.buttonStyle(LumeButtonStyle())
                Button(estimate.aAvaliar > 0 ? "Enviar e validar" : "Ver resultados") { store.confirmValidation() }
                    .buttonStyle(LumeButtonStyle(kind: .primary))
            }
        }
    }

    /// Só o que merece reconsiderar, com a evidência. Resultado inconclusivo não aparece como erro.
    private func results(_ validation: DecisionValidation) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline) {
                Kicker(title: "Decisões para reconsiderar")
                Spacer()
                Button("Validar de novo") { store.requestValidation() }
                    .buttonStyle(.borderless).font(LumeFont.ui(11)).disabled(!store.canValidateDecisions)
            }
            Text(coverage(validation)).font(LumeFont.ui(11.5)).foregroundStyle(LumeTheme.secondary)
                .fixedSize(horizontal: false, vertical: true)
            if validation.contested.isEmpty && validation.independent.isEmpty {
                Text("Nenhuma decisão avaliada precisa ser reconsiderada.").font(LumeFont.ui(13)).padding(.vertical, 8)
            }
            ForEach(validation.contested) { card($0, issueOnly: false) }
            if !validation.independent.isEmpty {
                Text("Questões independentes do alerta original").font(LumeFont.ui(12, weight: .semibold)).padding(.top, 6)
                ForEach(validation.independent) { card($0, issueOnly: true) }
            }
        }
    }

    private func coverage(_ validation: DecisionValidation) -> String {
        guard let summary = validation.summary else { return "" }
        var text = "\(summary.avaliadas) de \(summary.elegiveis) decisões avaliadas"
        if summary.reaproveitadas > 0 { text += " (\(summary.reaproveitadas) reaproveitadas sem custo)" }
        if summary.naoAvaliadas > 0 {
            text += "; \(summary.naoAvaliadas) ficaram sem avaliação" + (summary.interrompida ? " porque a execução parou antes do fim" : "")
        }
        return text + String(format: ". Custo: US$ %.4f. Suas decisões não foram alteradas.", summary.custoUsd)
    }

    @ViewBuilder private func card(_ item: ValidatedDecision, issueOnly: Bool) -> some View {
        let finding = store.report?.findings.first { $0.id == item.id }
        VStack(alignment: .leading, spacing: 6) {
            if let finding {
                Text("\(finding.category) · parágrafo \(finding.paragraph) · sua decisão: \(item.decisao)")
                    .font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary)
                let parts = finding.segments
                Text("“\(parts.marked)”").font(LumeFont.ui(13, weight: .semibold))
                Text("Apontado originalmente: \(finding.reason)").font(LumeFont.ui(11))
                    .foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
            }
            if issueOnly, let issue = item.questaoIndependente {
                Text("“\(issue.trecho)”").font(LumeFont.ui(12, weight: .semibold))
                Text(issue.explicacao).font(LumeFont.ui(12)).fixedSize(horizontal: false, vertical: true)
            } else {
                if let text = item.explicacao, !text.isEmpty {
                    Text(text).font(LumeFont.ui(12)).fixedSize(horizontal: false, vertical: true)
                }
                ForEach(item.evidencias ?? [], id: \.self) { quote in
                    Text("Evidência: “\(quote)”").font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary)
                }
                if let advice = item.recomendacao, !advice.isEmpty {
                    Text("Recomendação: \(advice)").font(LumeFont.ui(12, weight: .medium))
                        .fixedSize(horizontal: false, vertical: true)
                }
                if let issue = item.questaoIndependente {
                    Text("Outra questão no trecho: “\(issue.trecho)” — \(issue.explicacao)").font(LumeFont.ui(11))
                        .foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
                }
            }
            HStack {
                Text("Avaliação final: \(item.modeloFinal ?? "—") · suspeita, não erro confirmado")
                    .font(LumeFont.ui(10)).foregroundStyle(LumeTheme.secondary)
                Spacer()
                Button("Ir ao alerta") { store.goToFinding(item.id) }.buttonStyle(LumeButtonStyle(kind: .soft))
                    .accessibilityLabel("Ir ao alerta \(finding?.category ?? "") do parágrafo \(finding?.paragraph ?? 0)")
            }
        }.padding(12).frame(maxWidth: .infinity, alignment: .leading)
            .background(RoundedRectangle(cornerRadius: LumeRadius.medium, style: .continuous)
                .fill(store.selectedID == item.id ? LumeTheme.glow.opacity(0.5) : LumeTheme.surface))
            .overlay(RoundedRectangle(cornerRadius: LumeRadius.medium, style: .continuous).strokeBorder(LumeTheme.line))
            .contentShape(RoundedRectangle(cornerRadius: LumeRadius.medium))
            .onTapGesture { store.selectedID = item.id }       // mostra o alerta na página e no inspetor, sem sair da validação
    }
}