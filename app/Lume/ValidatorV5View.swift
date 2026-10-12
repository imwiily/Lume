import SwiftUI

// MARK: Avaliação da IA sobre as decisões (V5 por padrão)
//
// A IA aparece sempre como parecer, à parte da decisão do autor. Nenhum botão aqui altera decisão, relatório ou
// manuscrito, e nenhum texto diz que o autor "acertou" ou "errou": são pareceres que podem estar equivocados.

extension DecisionAssessment {
    var color: Color {
        switch self {
        case .probablyCorrect: return LumeTheme.accent
        case .possibleError: return LumeTheme.amber
        case .reviewRecommended: return LumeTheme.secondary
        case .inconclusive, .notAnalyzed, .outdated: return LumeTheme.tertiary
        }
    }
}

/// Selo discreto da avaliação, para a linha do alerta.
struct AssessmentBadge: View {
    let assessment: DecisionAssessment
    var body: some View {
        Label(assessment.short, systemImage: assessment.symbol)
            .font(LumeFont.ui(10)).foregroundStyle(assessment.color)
            .labelStyle(.titleAndIcon).lineLimit(1)
            .accessibilityLabel("Avaliação da IA: \(assessment.title)")
    }
}

/// Justificativa completa: diagnóstico, evidências, grau de certeza, recomendação e modelo.
struct SecondOpinionCard: View {
    let item: ValidatorV5Item
    let liveDecision: ReviewDecision?

    private var stale: ValidatorV5Wording.Staleness? {
        ValidatorV5Wording.staleness(item, decisions: liveDecision.map { [item.id: $0] } ?? [:])
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if let stale {
                Label(stale.message, systemImage: "exclamationmark.triangle").font(LumeFont.ui(11))
                    .foregroundStyle(LumeTheme.amber).fixedSize(horizontal: false, vertical: true)
            }
            Group {
                row("Sua decisão", item.previousDecision ?? "—")
                row("A IA vê problema no trecho?", ValidatorV5Wording.existence(item.existence))
                let degree = ValidatorV5Wording.degree(item.existence)
                if !degree.isEmpty { row("Grau de certeza", degree.joined(separator: " · ")) }
                row("Decisão frente ao diagnóstico", ValidatorV5Wording.adequacy(item.decisionAdequacy))
                if let meaning = item.disagreementMeaning { row("O que a discordância significa", meaning) }
            }.opacity(stale == nil ? 1 : 0.6)
            VStack(alignment: .leading, spacing: 1) {
                Text("Por que a IA concorda ou discorda").font(LumeFont.ui(10)).foregroundStyle(LumeTheme.tertiary)
                Text(item.explanation).font(LumeFont.ui(12)).fixedSize(horizontal: false, vertical: true)
            }.opacity(stale == nil ? 1 : 0.6)
            if item.evidence.isEmpty {
                Text("Evidências verificadas: nenhuma registrada para este resultado.").font(LumeFont.ui(11))
                    .foregroundStyle(LumeTheme.secondary)
            } else {
                VStack(alignment: .leading, spacing: 3) {
                    Text("Evidências verificadas no texto").font(LumeFont.ui(11, weight: .semibold))
                    ForEach(Array(item.evidence.enumerated()), id: \.offset) { _, e in
                        Text("§ \(e.paragraph.map(String.init) ?? "—"): “\(e.excerpt ?? "")”").font(LumeFont.ui(11))
                            .foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
            if !item.uncertainties.isEmpty {
                VStack(alignment: .leading, spacing: 3) {
                    Text("Incertezas e limitações").font(LumeFont.ui(11, weight: .semibold))
                    ForEach(item.uncertainties, id: \.self) { line in
                        Label(line, systemImage: "questionmark.circle").font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
            if let issue = item.independentIssue {
                Text("Outra questão no trecho: “\(issue.excerpt)” — \(issue.explanation)").font(LumeFont.ui(11))
                    .foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
            }
            if let suggestion = item.suggestion, !suggestion.isEmpty {
                row("Recomendação da IA (nada é aplicado ao manuscrito)", suggestion)
            }
            if let request = item.pendingContext {
                Label("O modelo pediu mais contexto (parágrafos \(request.paragraphs.map(String.init).joined(separator: ", "))). "
                      + "A segunda rodada está desativada; este parecer considera só o contexto enviado.",
                      systemImage: "text.badge.plus").font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Text("Avaliado por \(item.model ?? "modelo não registrado"). Parecer da IA: pode estar equivocado e não altera a sua decisão.")
                .font(LumeFont.ui(10)).foregroundStyle(LumeTheme.tertiary).fixedSize(horizontal: false, vertical: true)
        }.padding(12).frame(maxWidth: .infinity, alignment: .leading)
            .background(RoundedRectangle(cornerRadius: LumeRadius.medium, style: .continuous).fill(LumeTheme.surface))
            .overlay(RoundedRectangle(cornerRadius: LumeRadius.medium, style: .continuous).strokeBorder(LumeTheme.line))
    }

    private func row(_ title: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 1) {
            Text(title).font(LumeFont.ui(10)).foregroundStyle(LumeTheme.tertiary)
            Text(value).font(LumeFont.ui(12)).fixedSize(horizontal: false, vertical: true)
        }
    }
}

/// Inspetor: a avaliação logo acima da decisão editorial, com a justificativa sob demanda.
@MainActor
struct AssessmentSection: View {
    @EnvironmentObject private var store: ReviewStore
    let finding: Finding
    @State private var showDetails = false

    var body: some View {
        if let assessment = store.assessment(for: finding) {
            let item = store.secondOpinionItem(for: finding.id)
            let live = store.decision(for: finding)
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Kicker(title: "Avaliação da IA")
                    Spacer()
                    Text(item?.model ?? store.validatorBackend.title).font(LumeFont.ui(10.5)).foregroundStyle(LumeTheme.tertiary)
                }
                Label(assessment.title, systemImage: assessment.symbol).font(LumeFont.ui(13, weight: .semibold))
                    .foregroundStyle(assessment == .possibleError ? LumeTheme.amber : LumeTheme.ink)
                Text(ValidatorV5Assessment.explanation(assessment, item: item, liveDecision: live))
                    .font(LumeFont.ui(11.5)).foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
                if let item, assessment != .notAnalyzed {
                    DisclosureGroup("Justificativa, evidências e recomendação", isExpanded: $showDetails) {
                        SecondOpinionCard(item: item, liveDecision: live).padding(.top, 6)
                    }.font(LumeFont.ui(11.5, weight: .semibold))
                }
                if assessment.needsRun && store.validatorBackend == .v5 {
                    HStack {
                        Spacer()
                        Button("Validar esta decisão") { store.requestSecondOpinion(ids: [finding.id]) }
                            .buttonStyle(LumeButtonStyle(kind: .soft)).disabled(store.isBusy)
                            .help("Calcula o custo e pede a sua confirmação antes de enviar qualquer texto")
                    }
                }
            }
        }
    }
}

/// Validar decisões na mesa: V5 (padrão) ou V2 (alternativa manual). Sem troca automática de provedor.
@MainActor
struct ValidationHost: View {
    @EnvironmentObject private var store: ReviewStore
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Picker("Validador", selection: $store.validatorBackend) {
                ForEach(ValidatorBackend.allCases) { Text($0.title).tag($0) }
            }.pickerStyle(.segmented).labelsHidden().padding(.horizontal, 14).padding(.top, 10)
                .disabled(store.isBusy)
                .help("O GPT‑6.1 Sol (V5) é o padrão; o Claude (V2) fica como alternativa manual. O Lume nunca troca sozinho.")
            if store.validatorBackend == .v5 { ValidatorV5Panel() } else { ValidationPanel() }
        }
    }
}

@MainActor
struct ValidatorV5Panel: View {
    @EnvironmentObject private var store: ReviewStore
    @State private var authorized = false
    @State private var showPreview = false

    private var coordinator: ValidatorV5Coordinator { store.secondOpinion }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                if coordinator.estimate != nil || coordinator.phase == .revalidating {
                    confirmation
                } else if store.isBusy {
                    HStack(spacing: 8) { ProgressView().controlSize(.small); Text(store.jobLabel.isEmpty ? "Validando decisões…" : store.jobLabel) }
                        .font(LumeFont.ui(12)).foregroundStyle(LumeTheme.secondary)
                    if store.canCancel { Button("Interromper") { store.cancel() }.buttonStyle(LumeButtonStyle()) }
                } else {
                    overview
                }
            }.padding(14).frame(maxWidth: .infinity, alignment: .leading)
        }.task { store.refreshSecondOpinion() }
    }

    // MARK: Resumo e lote

    private var overview: some View {
        let counts = store.assessmentCounts
        let total = store.assessments.count
        let pending = store.validationPending
        let plan = ValidatorV5Batching.plan(pending.map(\.id))
        let scope = store.validationScope
        return VStack(alignment: .leading, spacing: 12) {
            Text(total == 0
                 ? "Nenhuma decisão elegível ainda (erro confirmado, estilo, falso positivo, intencional ou aceito)."
                 : "\(total) decisões registradas. A avaliação da IA é um parecer: pode estar equivocada e nunca altera as suas decisões.")
                .font(LumeFont.ui(11.5)).foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
            VStack(spacing: 2) {
                ForEach(DecisionAssessment.allCases) { category in
                    Button { store.assessmentFilter = store.assessmentFilter == category ? nil : category } label: {
                        HStack {
                            Image(systemName: category.symbol).foregroundStyle(category.color).frame(width: 18)
                            Text(category.title).font(LumeFont.ui(12.5))
                            Spacer()
                            Text("\(counts[category] ?? 0)").font(LumeFont.ui(12, weight: .semibold)).monospacedDigit()
                        }.padding(.horizontal, 8).padding(.vertical, 5)
                            .background(RoundedRectangle(cornerRadius: LumeRadius.small)
                                .fill(store.assessmentFilter == category ? LumeTheme.glow.opacity(0.7) : Color.clear))
                    }.buttonStyle(.plain)
                }
            }
            if store.assessmentFilter != nil {
                Button("Mostrar todas") { store.assessmentFilter = nil }.buttonStyle(.borderless).font(LumeFont.ui(11))
            }
            Divider().overlay(LumeTheme.line)
            actions(pendingCount: pending.count, plan: plan, scopeCount: scope.count)
            Divider().overlay(LumeTheme.line)
            list(scope)
        }
    }

    private func actions(pendingCount: Int, plan: (next: [String], remaining: Int, batches: Int), scopeCount: Int) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("\(scopeCount) decisões no filtro atual · \(pendingCount) a analisar (não analisadas ou desatualizadas)")
                .font(LumeFont.ui(11.5)).foregroundStyle(LumeTheme.secondary)
            if !store.hasOpenAIKey {
                Label("Falta a chave da OpenAI. O Lume não troca de provedor sozinho.", systemImage: "key")
                    .font(LumeFont.ui(11.5)).foregroundStyle(LumeTheme.amber)
                Button("Configurar chave da OpenAI") { store.requestKeySheet = true }.buttonStyle(LumeButtonStyle())
            } else if pendingCount == 0 {
                Text(scopeCount == 0 ? "Nada no filtro atual." : "Todas as decisões do filtro atual já têm validação atual.")
                    .font(LumeFont.ui(11.5))
            } else {
                Toggle(isOn: $store.acceptEditedManuscript) {
                    Text("Aceitar manuscrito editado depois da análise").font(LumeFont.ui(11.5))
                }.toggleStyle(.checkbox)
                    .help("Cada decisão só é enviada se o parágrafo e o contexto registrado no relatório continuarem iguais no texto atual")
                Text("Sem isso, qualquer edição do arquivo (inclusive correções feitas pelo Lume) impede o envio. Com isso, itens cujo parágrafo ou vizinhos mudaram continuam de fora.")
                    .font(LumeFont.ui(10)).foregroundStyle(LumeTheme.tertiary).fixedSize(horizontal: false, vertical: true)
                Stepper(value: $store.secondOpinionBudget, in: 0.25...ValidatorV5Arguments.maxBudget, step: 0.25) {
                    Text(String(format: "Teto desta execução: US$ %.2f (máx. US$ %.2f)", store.secondOpinionBudget,
                                ValidatorV5Arguments.maxBudget)).font(LumeFont.ui(11.5))
                }
                Button(plan.batches > 1 ? "Validar \(plan.next.count) decisões (lote 1 de \(plan.batches))" : "Validar \(plan.next.count) decisões") {
                    store.requestSecondOpinion(ids: plan.next)
                }.buttonStyle(LumeButtonStyle(kind: .primary)).disabled(store.isBusy || !store.secondOpinionAvailable)
                Text(plan.remaining > 0
                     ? "Até \(ValidatorV5Arguments.defaultItems) por execução. Depois de cada lote, \(plan.remaining) continuam à espera e pedem nova confirmação."
                     : "O Lume calcula o custo e pede a sua confirmação antes de enviar qualquer texto.")
                    .font(LumeFont.ui(10.5)).foregroundStyle(LumeTheme.tertiary).fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    private func list(_ scope: [Finding]) -> some View {
        let shown = scope.filter { store.assessmentFilter == nil || store.assessments[$0.id] == store.assessmentFilter }
        return VStack(alignment: .leading, spacing: 6) {
            Text(store.assessmentFilter.map { "\($0.title) (\(shown.count))" } ?? "Decisões no filtro atual (\(shown.count))")
                .font(LumeFont.ui(12, weight: .semibold))
            ForEach(shown) { finding in
                let assessment = store.assessments[finding.id] ?? .notAnalyzed
                Button { store.selectedID = finding.id } label: {
                    VStack(alignment: .leading, spacing: 3) {
                        Text("\(finding.category) · § \(finding.paragraph) · \(store.decision(for: finding).rawValue)")
                            .font(LumeFont.ui(10.5)).foregroundStyle(LumeTheme.secondary)
                        Text("“\(finding.segments.marked)”").font(LumeFont.ui(12.5, weight: .semibold)).lineLimit(1)
                        AssessmentBadge(assessment: assessment)
                    }.padding(8).frame(maxWidth: .infinity, alignment: .leading)
                        .background(RoundedRectangle(cornerRadius: LumeRadius.small)
                            .fill(store.selectedID == finding.id ? LumeTheme.glow.opacity(0.6) : LumeTheme.raised.opacity(0.5)))
                }.buttonStyle(.plain)
            }
        }
    }

    // MARK: Confirmação (no lugar da janela)

    private var confirmation: some View {
        VStack(alignment: .leading, spacing: 10) {
            Kicker(title: "Validar decisões · confirmar")
            if let notice = coordinator.notice {
                Label(notice, systemImage: "exclamationmark.triangle").font(LumeFont.ui(12, weight: .semibold))
                    .foregroundStyle(LumeTheme.amber).fixedSize(horizontal: false, vertical: true)
            }
            if let estimate = coordinator.estimate {
                ForEach(Array(ValidatorV5Wording.estimateLines(estimate, budget: store.secondOpinionBudget).enumerated()), id: \.offset) { _, line in
                    Text(line).font(LumeFont.ui(12)).fixedSize(horizontal: false, vertical: true)
                }
                if estimate.hasWork {
                    DisclosureGroup("Ver o que será enviado", isExpanded: $showPreview) { previewContent(estimate) }
                        .font(LumeFont.ui(12, weight: .semibold))
                        .onChange(of: showPreview) { _, open in if open { store.loadSecondOpinionPreview() } }
                    Toggle(isOn: $authorized) {
                        Text("Autorizo o envio destes \(estimate.toSend.count) trecho(s) do manuscrito à OpenAI, só nesta execução.")
                            .font(LumeFont.ui(12)).fixedSize(horizontal: false, vertical: true)
                    }.toggleStyle(.checkbox)
                    Label("A resposta é um parecer: nenhuma decisão, alerta ou trecho do manuscrito é alterado.", systemImage: "hand.raised")
                        .font(LumeFont.ui(11)).foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
                }
            }
            if coordinator.phase == .revalidating {
                HStack { ProgressView().controlSize(.small); Text("Conferindo de novo seleção, versão e custo antes de enviar…").font(LumeFont.ui(11.5)) }
            }
            HStack {
                Spacer()
                Button("Cancelar") { store.cancelSecondOpinion() }.buttonStyle(LumeButtonStyle())
                Button((coordinator.estimate?.hasWork ?? false) ? "Enviar e validar" : "Fechar") {
                    if coordinator.estimate?.hasWork ?? false { store.confirmSecondOpinion(authorized: authorized) }
                    else { store.cancelSecondOpinion() }
                }.buttonStyle(LumeButtonStyle(kind: .primary))
                    .disabled((coordinator.estimate?.hasWork ?? false) && (!authorized || !(coordinator.estimate?.fitsBudget ?? false)
                                                                            || coordinator.phase != .awaitingAuthorization))
            }
        }.id(signature(coordinator.estimate))      // nova estimativa, nova confirmação: a caixa volta desmarcada
    }

    private func signature(_ estimate: ValidatorV5Estimate?) -> String {
        guard let e = estimate else { return "none" }
        return e.toSend.map(\.id).joined(separator: ",") + String(format: "|%.4f|%.2f", e.maximumUsd, e.budgetUsd)
    }

    /// Texto exato do pedido, quando o backend o devolve; senão, a prévia parcial, identificada como tal.
    @ViewBuilder private func previewContent(_ estimate: ValidatorV5Estimate) -> some View {
        if let exact = store.secondOpinionExactPreview {
            VStack(alignment: .leading, spacing: 8) {
                Text("Texto exato do pedido ao modelo: \(exact.requests.count) requisição(ões). As instruções fixas do Validador "
                     + "(\(exact.instructionCharacters) caracteres, sem o manuscrito) acompanham cada uma.")
                    .font(LumeFont.ui(10.5)).foregroundStyle(LumeTheme.secondary).fixedSize(horizontal: false, vertical: true)
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 10) {
                        ForEach(Array(exact.requests.enumerated()), id: \.offset) { index, request in
                            VStack(alignment: .leading, spacing: 3) {
                                Text("Requisição \(index + 1) · \(request.ids.count) item(ns) · \(request.characters) caracteres")
                                    .font(LumeFont.ui(10.5, weight: .semibold)).foregroundStyle(LumeTheme.secondary)
                                Text(request.text).font(.system(size: 10.5, design: .monospaced)).textSelection(.enabled)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                        }
                    }
                }.frame(height: 200)
            }.padding(.top, 4)
        } else if store.secondOpinionPreviewLoading {
            HStack { ProgressView().controlSize(.small); Text("Montando o texto exato do pedido…").font(LumeFont.ui(11)) }
        } else {
            if store.secondOpinionPreviewFailed {
                Label("Não foi possível obter o texto exato; abaixo, uma prévia parcial.", systemImage: "exclamationmark.triangle")
                    .font(LumeFont.ui(11)).foregroundStyle(LumeTheme.amber)
            }
            let entries = ValidatorV5Preview.entries(for: estimate, findings: store.report?.findings ?? [], decisions: store.decisions)
            VStack(alignment: .leading, spacing: 8) {
                Text(ValidatorV5Preview.note).font(LumeFont.ui(10)).foregroundStyle(LumeTheme.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                ForEach(entries, id: \.id) { entry in
                    VStack(alignment: .leading, spacing: 3) {
                        Text(entry.heading).font(LumeFont.ui(10.5, weight: .semibold)).foregroundStyle(LumeTheme.secondary)
                        Text(entry.marked).font(LumeFont.ui(11.5)).fixedSize(horizontal: false, vertical: true)
                    }
                }
            }.padding(.top, 4)
        }
    }
}
