import Combine
import Foundation
import Security

// MARK: Validador V5 — fundação (Fase 2): chave, protocolo, argumentos e resultados
//
// Nada aqui chama a API nem muda uma decisão. Este arquivo só: guarda a chave da OpenAI no Keychain
// (serviço próprio, separado da Anthropic), monta os argumentos do backend sem segredos, interpreta as
// linhas JSON do motor e representa o resultado da IA como dado à parte, nunca como decisão do autor.

// MARK: Chave da OpenAI

/// Armazenamento de um segredo. O Keychain é a implementação real; os testes usam uma em memória.
protocol SecretStore {
    func exists() -> Bool
    func read() -> String?
    func save(_ secret: String) throws
    func delete()
}

/// Um item de senha genérica por serviço, com a conta do usuário do macOS. O backend Python lê pelo
/// serviço (`security find-generic-password -s lume-openai -w`), sem exigir uma conta específica.
struct KeychainSecretStore: SecretStore {
    let service: String
    var account: String = NSUserName()

    /// Consulta só atributos: não lê o segredo nem pede permissão ao abrir o app.
    func exists() -> Bool {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service,
                                    kSecReturnAttributes as String: true, kSecMatchLimit as String: kSecMatchLimitOne]
        return SecItemCopyMatching(query as CFDictionary, nil) == errSecSuccess
    }

    func read() -> String? {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service,
                                    kSecReturnData as String: true, kSecMatchLimit as String: kSecMatchLimitOne]
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess, let data = item as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    func save(_ secret: String) throws {
        delete()
        let item: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service,
                                   kSecAttrAccount as String: account, kSecValueData as String: Data(secret.utf8)]
        let status = SecItemAdd(item as CFDictionary, nil)
        guard status == errSecSuccess else {
            throw FonteError.message("Não foi possível guardar a chave nas Chaves do macOS (código \(status)).")
        }
    }

    func delete() {
        SecItemDelete([kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service] as CFDictionary)
    }
}

/// Chave da OpenAI do Validador V5. Serviço `lume-openai`, o mesmo que o backend Python consulta quando
/// `OPENAI_API_KEY` não está definida. Nunca em UserDefaults, arquivos, relatórios, logs ou argumentos.
enum OpenAIKey {
    static let service = "lume-openai"
    static let environmentVariable = "OPENAI_API_KEY"
    /// Substituível só pelos testes.
    static var store: SecretStore = KeychainSecretStore(service: service)

    enum Problem: Error, Equatable {
        case empty, tooShort, wrongProvider, unexpectedCharacters, notAnOpenAIKey
        var message: String {
            switch self {
            case .empty: return "Cole a chave da API da OpenAI."
            case .tooShort: return "Essa chave parece incompleta. Copie a chave inteira logo após criá-la no painel da OpenAI."
            case .wrongProvider: return "Essa é uma chave da Anthropic. Aqui vai a chave da OpenAI (começa com sk-)."
            case .unexpectedCharacters: return "A chave contém caracteres inesperados. Copie-a de novo, sem espaços nem quebras de linha."
            case .notAnOpenAIKey: return "Essa não parece uma chave da API da OpenAI (começa com sk-)."
            }
        }
    }

    /// Confere só o formato, localmente. Não prova que a chave funciona e nunca repete o valor recebido.
    static func validate(_ raw: String) -> Result<String, Problem> {
        let key = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        if key.isEmpty { return .failure(.empty) }
        if key.hasPrefix("sk-ant-") { return .failure(.wrongProvider) }
        if !key.hasPrefix("sk-") { return .failure(.notAnOpenAIKey) }
        if key.unicodeScalars.contains(where: { !(CharacterSet.alphanumerics.contains($0) || $0 == "-" || $0 == "_") }) {
            return .failure(.unexpectedCharacters)
        }
        if key.count < 40 { return .failure(.tooShort) }
        return .success(key)
    }

    static func exists() -> Bool { store.exists() }
    static func read() -> String? { store.read() }
    static func save(_ raw: String) throws {
        switch validate(raw) {
        case .success(let key): try store.save(key)
        case .failure(let problem): throw FonteError.message(problem.message)
        }
    }
    static func delete() { store.delete() }

    /// Ambiente do processo do motor. É o único caminho da chave até o Python: nunca por argumento.
    static func environment(for key: String) -> [String: String] { [environmentVariable: key] }
}

// MARK: Backend do Validador

/// Qual backend atende “Validar decisões”: V5 (GPT‑6.1 Sol, medium) por padrão; V2 (Claude) como alternativa manual.
/// Nunca há troca automática de provedor: sem a chave do escolhido, o Lume avisa e não envia nada.
enum ValidatorBackend: String, CaseIterable, Identifiable {
    case v5, v2
    static let defaultsKey = "validatorBackend"
    var id: String { rawValue }
    var title: String { self == .v5 ? "GPT‑6.1 Sol (V5)" : "Claude Sonnet (V2)" }

    static func current(_ defaults: UserDefaults = .standard) -> ValidatorBackend {
        defaults.string(forKey: defaultsKey) == ValidatorBackend.v2.rawValue ? .v2 : .v5
    }
}

// MARK: Argumentos do backend (sem segredos)

struct ValidatorV5Arguments {
    static let defaultBudget = 1.0
    static let maxBudget = 5.0
    static let defaultItems = 40
    static let maxItems = 60

    enum Problem: Error, Equatable { case noItems, tooManyItems(Int), invalidBudget }

    /// Posicionais e opções comuns: manuscrito, relatório, decisões (instantâneo), pasta do projeto e configuração.
    static func common(document: URL, report: URL, decisions: URL, project: URL, config: URL?) -> [String] {
        var args = [document.path, "--relatorio", report.path, "--decisoes", decisions.path, "--projeto", project.path]
        if let config { args += ["--config", config.path] }
        return args
    }

    private static func selection(_ ids: [String], limit: Int) throws -> [String] {
        let unique = Array(NSOrderedSet(array: ids).compactMap { $0 as? String })
        guard !unique.isEmpty else { throw Problem.noItems }
        guard unique.count <= min(limit, maxItems) else { throw Problem.tooManyItems(unique.count) }
        return unique
    }

    private static func budgetText(_ budget: Double) throws -> String {
        guard budget.isFinite, budget > 0, budget <= maxBudget else { throw Problem.invalidBudget }
        return String(format: "%.2f", locale: Locale(identifier: "en_US_POSIX"), budget)
    }

    /// Opções que só entram quando pedidas: `--revalidar` (resultados desatualizados, só os listados) e
    /// `--permitir-contexto-parcial` (manuscrito editado depois da análise, com o contexto registrado conferido).
    private static func extras(revalidate: [String], partialContext: Bool, ids: [String]) -> [String] {
        var out: [String] = []
        let wanted = revalidate.filter(ids.contains)
        if !wanted.isEmpty { out += ["--revalidar"] + wanted }
        if partialContext { out += ["--permitir-contexto-parcial"] }
        return out
    }

    static func estimate(common: [String], ids: [String], budget: Double = defaultBudget, limit: Int = defaultItems,
                         revalidate: [String] = [], partialContext: Bool = false) throws -> [String] {
        ["validar-decisoes-v5-estimar"] + common + ["--ids"] + (try selection(ids, limit: limit))
            + ["--max-itens", String(limit), "--teto", try budgetText(budget)]
            + extras(revalidate: revalidate, partialContext: partialContext, ids: ids)
    }

    /// Execução do piloto: uma tentativa por requisição, versão exata do manuscrito (sem contexto parcial) e
    /// sem segunda rodada de contexto nem reanálise. Estas opções não existem aqui de propósito.
    static func run(common: [String], ids: [String], budget: Double = defaultBudget, limit: Int = defaultItems,
                    revalidate: [String] = [], partialContext: Bool = false) throws -> [String] {
        ["validar-decisoes-v5"] + common + ["--ids"] + (try selection(ids, limit: limit))
            + ["--max-itens", String(limit), "--teto", try budgetText(budget), "--tentativas", "1"]
            + extras(revalidate: revalidate, partialContext: partialContext, ids: ids)
    }

    /// Texto exato do pedido, calculado localmente (sem rede) pelo mesmo caminho do envio.
    static func preview(common: [String], ids: [String], budget: Double = defaultBudget, limit: Int = defaultItems,
                        revalidate: [String] = [], partialContext: Bool = false) throws -> [String] {
        ["validar-decisoes-v5-previa"] + common + ["--ids"] + (try selection(ids, limit: limit))
            + ["--max-itens", String(limit), "--teto", try budgetText(budget)]
            + extras(revalidate: revalidate, partialContext: partialContext, ids: ids)
    }

    static func results(common: [String], ids: [String] = []) -> [String] {
        ["validar-decisoes-v5-resultados"] + common + (ids.isEmpty ? [] : ["--ids"] + ids)
    }
}

// MARK: Protocolo de linhas do motor

enum ValidatorV5Prefix: String, CaseIterable {
    case estimate = "LUME_ESTIMATIVA_VALIDADOR_V5 "
    case progress = "LUME_VALIDADOR_V5_PROGRESSO "
    case finished = "LUME_VALIDACAO_V5 "
    case results = "LUME_RESULTADOS_V5 "
    case failure = "LUME_VALIDADOR_V5_ERRO "
    case preview = "LUME_PREVIA_VALIDADOR_V5 "
}

struct ValidatorV5Excluded: Decodable, Equatable {
    let id: String
    let reason: String
    enum CodingKeys: String, CodingKey { case id, reason = "motivo" }
}

struct ValidatorV5Sent: Decodable, Equatable {
    let id: String
    let paragraph: Int
    let category: String
    enum CodingKeys: String, CodingKey { case id, paragraph = "paragrafo", category = "categoria" }
}

struct ValidatorV5Estimate: Decodable {
    let provider: String
    let model: String
    let effort: String
    let storage: String
    let selected: Int
    let accepted: Int
    let excluded: [ValidatorV5Excluded]
    let manuscriptVersion: String
    let verification: [String: Int]
    let toSend: [ValidatorV5Sent]
    let chapters: [String]
    let reused: Int
    let notLocated: Int
    let requests: Int
    let expectedUsd: Double
    let maximumUsd: Double
    let worstRequestUsd: Double
    let minimumBudgetUsd: Double
    let budgetUsd: Double
    let defaultBudgetUsd: Double
    let maximumBudgetUsd: Double
    let fitsBudget: Bool
    let secondRoundAuthorized: Bool
    let secondRoundExtraUsd: Double
    let priceSource: String?
    let notice: String

    enum CodingKeys: String, CodingKey {
        case provider = "provedor", model = "modelo", effort = "esforco", storage = "armazenamento_pelo_provedor"
        case selected = "selecionadas", accepted = "aceitas", excluded = "excluidos"
        case manuscriptVersion = "versao_manuscrito", verification = "verificacao", toSend = "a_enviar"
        case chapters = "capitulos_a_enviar", reused = "reutilizadas_sem_custo", notLocated = "nao_localizadas"
        case requests = "pedidos_primeira_rodada", expectedUsd = "custo_esperado_usd", maximumUsd = "custo_maximo_usd"
        case worstRequestUsd = "pior_pedido_usd", minimumBudgetUsd = "teto_minimo_usd", budgetUsd = "teto_usd"
        case defaultBudgetUsd = "teto_padrao_usd", maximumBudgetUsd = "teto_maximo_usd", fitsBudget = "cabe_no_teto"
        case secondRound = "segunda_rodada", priceSource = "fonte_dos_precos", notice = "aviso"
    }
    private struct SecondRound: Decodable {
        let authorized: Bool
        let extraUsd: Double
        enum CodingKeys: String, CodingKey { case authorized = "autorizada", extraUsd = "custo_maximo_adicional_usd" }
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        provider = try c.decode(String.self, forKey: .provider); model = try c.decode(String.self, forKey: .model)
        effort = try c.decode(String.self, forKey: .effort); storage = try c.decode(String.self, forKey: .storage)
        selected = try c.decode(Int.self, forKey: .selected); accepted = try c.decode(Int.self, forKey: .accepted)
        excluded = try c.decode([ValidatorV5Excluded].self, forKey: .excluded)
        manuscriptVersion = try c.decode(String.self, forKey: .manuscriptVersion)
        verification = try c.decode([String: Int].self, forKey: .verification)
        toSend = try c.decode([ValidatorV5Sent].self, forKey: .toSend)
        chapters = try c.decode([String].self, forKey: .chapters)
        reused = try c.decode(Int.self, forKey: .reused); notLocated = try c.decode(Int.self, forKey: .notLocated)
        requests = try c.decode(Int.self, forKey: .requests)
        expectedUsd = try c.decode(Double.self, forKey: .expectedUsd); maximumUsd = try c.decode(Double.self, forKey: .maximumUsd)
        worstRequestUsd = try c.decode(Double.self, forKey: .worstRequestUsd)
        minimumBudgetUsd = try c.decode(Double.self, forKey: .minimumBudgetUsd)
        budgetUsd = try c.decode(Double.self, forKey: .budgetUsd)
        defaultBudgetUsd = try c.decode(Double.self, forKey: .defaultBudgetUsd)
        maximumBudgetUsd = try c.decode(Double.self, forKey: .maximumBudgetUsd)
        fitsBudget = try c.decode(Bool.self, forKey: .fitsBudget)
        let second = try c.decode(SecondRound.self, forKey: .secondRound)
        secondRoundAuthorized = second.authorized; secondRoundExtraUsd = second.extraUsd
        priceSource = try c.decodeIfPresent(String.self, forKey: .priceSource)
        notice = try c.decode(String.self, forKey: .notice)
    }

    /// Há algo a enviar (e portanto custo e confirmação). Com zero, nada é enviado.
    var hasWork: Bool { !toSend.isEmpty }
}

/// O que o backend enviaria, por requisição, tal como montado (`LUME_PREVIA_VALIDADOR_V5`).
struct ValidatorV5ExactPreview: Decodable {
    struct Request: Decodable {
        let ids: [String]
        let characters: Int
        let text: String
        enum CodingKeys: String, CodingKey { case ids = "itens", characters = "caracteres", text = "texto" }
    }
    let requests: [Request]
    let instructionCharacters: Int
    let secondRoundAuthorized: Bool
    let note: String
    enum CodingKeys: String, CodingKey {
        case requests = "pedidos", instructionCharacters = "instrucoes_caracteres"
        case secondRoundAuthorized = "segunda_rodada_autorizada", note = "observacao"
    }
}

struct ValidatorV5Progress: Decodable, Equatable {
    let stage: String
    let done: Int
    let total: Int
    enum CodingKeys: String, CodingKey { case stage = "etapa", done = "feitos", total }
}

struct ValidatorV5Failure: Decodable, Equatable {
    let code: String
    let message: String
    enum CodingKeys: String, CodingKey { case code = "codigo", message = "mensagem" }
}

struct ValidatorV5RunSummary: Decodable {
    let analysed: Int
    let reused: Int
    let outdated: Int
    let notLocated: Int
    let withoutAnswer: Int
    let interrupted: Bool
    let interruptionReason: String
    let results: [String: Int]
    let requests: Int
    let inputTokens: Int
    let cachedTokens: Int
    let outputTokens: Int
    let reasoningTokens: Int
    let costUsd: Double
    let budgetUsd: Double
    enum CodingKeys: String, CodingKey {
        case analysed = "analisadas_agora", reused = "reutilizadas_sem_custo", outdated = "desatualizadas"
        case notLocated = "nao_localizadas", withoutAnswer = "sem_resposta", interrupted = "interrompida"
        case interruptionReason = "motivo_interrupcao", results = "resultados", requests = "pedidos"
        case inputTokens = "tokens_entrada", cachedTokens = "tokens_cache", outputTokens = "tokens_saida"
        case reasoningTokens = "tokens_raciocinio", costUsd = "custo_usd", budgetUsd = "teto_usd"
    }
}

struct ValidatorV5Run: Decodable {
    let excluded: [ValidatorV5Excluded]
    let manuscriptVersion: String
    let verification: [String: Int]
    /// O backend afirma que nenhuma decisão foi alterada; o app nunca grava decisões a partir desta resposta.
    let decisionsChanged: Bool
    let secondRoundAuthorized: Bool
    let pendingContext: Int
    let reanalysed: [String]
    let analysedNow: Int
    let message: String?
    let notices: [String]
    let summary: ValidatorV5RunSummary?
    enum CodingKeys: String, CodingKey {
        case excluded = "excluidos", manuscriptVersion = "versao_manuscrito", verification = "verificacao"
        case decisionsChanged = "decisoes_alteradas", secondRoundAuthorized = "segunda_rodada_autorizada"
        case pendingContext = "pendencias_de_contexto", reanalysed = "reanalisados", analysedNow = "analisadas_agora"
        case message = "mensagem", notices = "avisos", summary = "v5"
    }
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        excluded = try c.decode([ValidatorV5Excluded].self, forKey: .excluded)
        manuscriptVersion = try c.decode(String.self, forKey: .manuscriptVersion)
        verification = try c.decode([String: Int].self, forKey: .verification)
        decisionsChanged = try c.decode(Bool.self, forKey: .decisionsChanged)
        secondRoundAuthorized = try c.decode(Bool.self, forKey: .secondRoundAuthorized)
        pendingContext = try c.decode(Int.self, forKey: .pendingContext)
        reanalysed = try c.decodeIfPresent([String].self, forKey: .reanalysed) ?? []
        analysedNow = try c.decode(Int.self, forKey: .analysedNow)
        message = try c.decodeIfPresent(String.self, forKey: .message)
        notices = try c.decodeIfPresent([String].self, forKey: .notices) ?? []
        summary = try c.decodeIfPresent(ValidatorV5RunSummary.self, forKey: .summary)
    }
}

// MARK: Resultados da IA (dado à parte das decisões humanas)

struct ValidatorV5Existence: Decodable, Equatable {
    let exists: String?
    let nature: String?
    let certainty: String?
    let severity: String?
    let label: String
    enum CodingKeys: String, CodingKey {
        case exists = "existe", nature = "natureza", certainty = "certeza", severity = "gravidade", label = "rotulo"
    }
}

struct ValidatorV5Evidence: Decodable, Equatable {
    let role: String?
    let paragraph: Int?
    let excerpt: String?
    enum CodingKeys: String, CodingKey { case role = "papel", paragraph = "paragrafo", excerpt = "trecho" }
}

struct ValidatorV5Discarded: Decodable, Equatable {
    let role: String?
    let reason: String?
    enum CodingKeys: String, CodingKey { case role = "papel", reason = "motivo" }
}

struct ValidatorV5Issue: Decodable, Equatable {
    let excerpt: String
    let explanation: String
    enum CodingKeys: String, CodingKey { case excerpt = "trecho", explanation = "explicacao" }
}

struct ValidatorV5ContextRequest: Decodable, Equatable {
    let paragraphs: [Int]
    let terms: [String]
    enum CodingKeys: String, CodingKey { case paragraphs = "paragrafos", terms = "termos" }
}

/// Um resultado da IA sobre uma decisão. É informação: não carrega nenhuma operação que mude a decisão.
struct ValidatorV5Item: Decodable, Identifiable {
    let id: String
    let paragraph: Int
    let category: String
    let excerpt: String?
    /// valida, desatualizada_conteudo, desatualizada_configuracao, nao_localizada, decisao_ausente_ou_nao_elegivel.
    let situation: String
    let isCurrent: Bool
    let previousDecision: String?
    let currentDecision: String?
    let existence: ValidatorV5Existence
    /// adequada, inadequada ou indeterminada, segundo a IA.
    let decisionAdequacy: String?
    /// mantida, contestada, revisao_recomendada, apontamento_inadequado ou inconclusiva.
    let result: String?
    let resultLabel: String
    let disagreementMeaning: String?
    let reviewPriority: String?
    let explanation: String
    let evidence: [ValidatorV5Evidence]
    let discardedEvidence: [ValidatorV5Discarded]
    let uncertainties: [String]
    let independentIssue: ValidatorV5Issue?
    let suggestion: String?
    let suggestionApplied: Bool
    let versionCheck: String?
    let pendingContext: ValidatorV5ContextRequest?
    let model: String?
    let notice: String

    enum CodingKeys: String, CodingKey {
        case id, paragraph = "paragrafo", category = "categoria", excerpt = "trecho", situation = "situacao"
        case isCurrent = "vale_para_o_texto_e_decisao_atuais", previousDecision = "decisao_humana_anterior"
        case currentDecision = "decisao_humana_atual", existence = "existencia_segundo_a_ia"
        case decisionAdequacy = "adequacao_da_decisao_segundo_a_ia", result = "resultado"
        case resultLabel = "rotulo_do_resultado", disagreementMeaning = "significado_da_discordancia"
        case reviewPriority = "prioridade_da_revisao", explanation = "explicacao_da_ia"
        case evidence = "evidencias_verificadas", discardedEvidence = "evidencias_descartadas"
        case uncertainties = "incertezas_e_limitacoes", independentIssue = "questao_independente"
        case suggestion = "sugestao_da_ia", suggestionApplied = "sugestao_aplicada_ao_manuscrito"
        case versionCheck = "verificacao_da_versao", pendingContext = "pendencia_de_contexto"
        case model = "modelo", notice = "aviso"
    }
}

struct ValidatorV5Results: Decodable {
    let items: [ValidatorV5Item]
    let counts: [String: Int]
    let outdated: Int
    let readNotice: String?
    enum CodingKeys: String, CodingKey {
        case items = "itens", counts = "contagem", outdated = "desatualizadas", readNotice = "aviso_de_leitura"
    }

    /// Itens cujo resultado ainda vale para a decisão registrada agora. Só filtra: não altera nada.
    func current(for decisions: [String: ReviewDecision]) -> [ValidatorV5Item] {
        items.filter { $0.isCurrent && decisions[$0.id]?.rawValue == $0.currentDecision }
    }
}

enum ValidatorV5Event {
    case estimate(ValidatorV5Estimate)
    case progress(ValidatorV5Progress)
    case finished(ValidatorV5Run)
    case results(ValidatorV5Results)
    case failure(ValidatorV5Failure)
}

enum ValidatorV5Protocol {
    /// Última linha do texto com o prefixo, sem o prefixo. Linhas de outros protocolos são ignoradas.
    static func lastPayload(_ prefix: ValidatorV5Prefix, in text: String) -> Data? {
        guard let line = text.split(separator: "\n", omittingEmptySubsequences: true)
            .last(where: { $0.hasPrefix(prefix.rawValue) }) else { return nil }
        return Data(line.dropFirst(prefix.rawValue.count).utf8)
    }

    static func decode<T: Decodable>(_ type: T.Type, _ prefix: ValidatorV5Prefix, in text: String) throws -> T? {
        guard let data = lastPayload(prefix, in: text) else { return nil }
        return try JSONDecoder().decode(type, from: data)
    }

    /// Falha estruturada do backend, se houver; tem precedência sobre qualquer outra resposta.
    static func failure(in text: String) -> ValidatorV5Failure? {
        (try? decode(ValidatorV5Failure.self, .failure, in: text)) ?? nil
    }
}

// MARK: Linguagem da apresentação (Fase 3)

/// Textos e classificações da segunda opinião. Tudo vem de campos já devolvidos pelo backend; nada é inferido
/// nem inventado, e nenhuma frase chama a discordância da IA de “erro confirmado”.
enum ValidatorV5Wording {
    /// Como a IA classificou o resultado, em termos da mesa.
    enum Kind: String {
        case held, contested, review, inadequate, inconclusive, unknown
        var title: String {
            switch self {
            case .held: return "A IA não vê motivo para reconsiderar"
            case .contested: return "A IA discorda da decisão registrada"
            case .review: return "A IA reconhece o desvio; a escolha é sua"
            case .inadequate: return "A IA considera que o apontamento não se sustenta"
            case .inconclusive: return "Sem conclusão segura da IA"
            case .unknown: return "Resultado da IA"
            }
        }
        var symbol: String {
            switch self {
            case .held: return "checkmark.circle"
            case .contested: return "arrow.triangle.2.circlepath"
            case .review: return "eye"
            case .inadequate: return "minus.circle"
            case .inconclusive: return "questionmark.circle"
            case .unknown: return "circle"
            }
        }
    }

    static func kind(_ item: ValidatorV5Item) -> Kind {
        switch item.result {
        case "mantida": return .held
        case "contestada": return .contested
        case "revisao_recomendada": return .review
        case "apontamento_inadequado": return .inadequate
        case "inconclusiva": return .inconclusive
        default: return .unknown
        }
    }

    enum Staleness: Equatable {
        case text, decision, notLocated
        var message: String {
            switch self {
            case .text: return "Resultado desatualizado: o texto ou o contexto mudou desde a análise. Ele não vale mais para este trecho."
            case .decision: return "Resultado desatualizado: a sua decisão mudou depois da análise. Ele não vale mais."
            case .notLocated: return "Resultado desatualizado: o trecho não foi localizado com segurança no manuscrito atual."
            }
        }
    }

    /// Por que o resultado deixou de valer, se deixou. A decisão atual do app prevalece sobre a do arquivo.
    static func staleness(_ item: ValidatorV5Item, decisions: [String: ReviewDecision]) -> Staleness? {
        if let live = decisions[item.id], live.rawValue != item.previousDecision { return .decision }
        if item.situation == "nao_localizada" { return .notLocated }
        if item.situation == "valida" && item.isCurrent { return nil }
        if item.situation == "decisao_ausente_ou_nao_elegivel" { return .decision }
        return .text
    }

    static func existence(_ e: ValidatorV5Existence) -> String {
        switch e.exists {
        case "sim": return "Segundo a IA, há um desvio neste trecho."
        case "nao": return "Segundo a IA, não há desvio neste trecho."
        case "incerto": return "A IA não conseguiu estabelecer se há um desvio neste trecho."
        default: return "Informação insuficiente sobre a existência do desvio."
        }
    }

    static func degree(_ e: ValidatorV5Existence) -> [String] {
        var out: [String] = []
        switch e.nature {
        case "objetivo": out.append("natureza objetiva (resposta única na norma)")
        case "interpretativo": out.append("natureza interpretativa (depende de leitura)")
        default: break
        }
        switch e.certainty {
        case "clara": out.append("certeza clara no texto enviado")
        case "discutivel": out.append("certeza discutível: admite outra leitura razoável")
        default: break
        }
        switch e.severity {
        case "alta": out.append("gravidade alta")
        case "media": out.append("gravidade média")
        case "baixa": out.append("gravidade baixa")
        default: break
        }
        return out
    }

    static func adequacy(_ value: String?) -> String {
        switch value {
        case "adequada": return "A decisão registrada é compatível com o diagnóstico da IA."
        case "inadequada": return "A decisão registrada diverge do diagnóstico da IA."
        case "indeterminada": return "O diagnóstico da IA não basta para avaliar a decisão registrada."
        default: return "Informação insuficiente para avaliar a decisão registrada."
        }
    }

    static func exclusion(_ reason: String) -> String {
        switch reason {
        case "versao_do_manuscrito_diferente": return "o manuscrito aberto não é a versão exata do relatório"
        case "contexto_nao_verificavel": return "o contexto do relatório não pôde ser verificado"
        case "decisao_nao_elegivel": return "a decisão não é elegível (pendente ou já corrigida)"
        case "id_fora_do_relatorio": return "o alerta não está mais no relatório"
        default: return reason
        }
    }

    /// Linhas da confirmação: o que seria enviado, para quem e quanto custa. Sem texto do manuscrito.
    static func estimateLines(_ e: ValidatorV5Estimate, budget: Double) -> [String] {
        var lines = ["\(e.selected) apontamento(s) selecionado(s); \(e.accepted) verificável(is) com a versão atual do manuscrito."]
        if e.reused > 0 { lines.append("\(e.reused) já têm resultado válido para o mesmo texto e decisão: reaproveitados, sem custo.") }
        if e.notLocated > 0 { lines.append("\(e.notLocated) não foram localizados com segurança no manuscrito atual e não serão enviados.") }
        if !e.excluded.isEmpty {
            let reasons = Dictionary(grouping: e.excluded, by: { $0.reason }).sorted { $0.key < $1.key }
                .map { "\($0.value.count) — \(exclusion($0.key))" }
            lines.append("Fora do envio: " + reasons.joined(separator: "; ") + ".")
        }
        guard e.hasWork else { return lines + ["Nada será enviado e não há custo."] }
        if let partial = e.verification["contexto_parcial"], partial > 0 {
            lines.append("\(partial) verificados só pelo contexto registrado no relatório: o manuscrito foi editado depois da análise.")
        }
        let chapters = e.chapters.prefix(5).joined(separator: ", ") + (e.chapters.count > 5 ? "…" : "")
        lines.append("Serão enviados \(e.toSend.count) trecho(s), com os parágrafos vizinhos, de: \(chapters).")
        lines.append("Provedor: OpenAI · modelo \(e.model) · esforço \(e.effort). \(e.storage).")
        lines.append(String(format: "Custo esperado: US$ %.2f · pior caso: US$ %.2f (maior pedido: US$ %.2f) · teto autorizado: US$ %.2f.",
                            e.expectedUsd, e.maximumUsd, e.worstRequestUsd, budget))
        if !e.fitsBudget {
            lines.append(String(format: "Atenção: o teto não cobre o pior caso de um pedido (mínimo US$ %.2f). Nada será enviado com este teto.", e.minimumBudgetUsd))
        }
        lines.append(e.secondRoundAuthorized ? "Segunda rodada de contexto: autorizada."
                     : "Segunda rodada de contexto: não autorizada; se o modelo pedir mais contexto, só será registrado.")
        return lines
    }
}

extension ValidatorV5Estimate {
    /// Dois cálculos são equivalentes se mandariam o mesmo e custariam o mesmo (centavos). Usado para exigir nova
    /// confirmação quando algo relevante muda entre a estimativa mostrada e a execução.
    func isEquivalent(to other: ValidatorV5Estimate) -> Bool {
        func cents(_ v: Double) -> Int { Int((v * 100).rounded()) }
        return provider == other.provider && model == other.model && effort == other.effort
            && manuscriptVersion == other.manuscriptVersion
            && toSend.map(\.id) == other.toSend.map(\.id)
            && Set(excluded.map { $0.id + ":" + $0.reason }) == Set(other.excluded.map { $0.id + ":" + $0.reason })
            && reused == other.reused && notLocated == other.notLocated && requests == other.requests
            && cents(maximumUsd) == cents(other.maximumUsd) && cents(budgetUsd) == cents(other.budgetUsd)
            && fitsBudget == other.fitsBudget && secondRoundAuthorized == other.secondRoundAuthorized
    }
}

// MARK: Pré-visualização do que seria enviado

/// O que sai do Mac para cada item: o parágrafo do alerta com o trecho marcado, a hipótese do detector, a
/// decisão do revisor e o contexto registrado no relatório. Montado só com dados locais; nenhum segredo entra.
/// O envio real usa até três parágrafos de cada lado do manuscrito atual (versão conferida por SHA).
struct ValidatorV5Preview {
    struct Entry: Equatable {
        let id: String
        let heading: String
        let marked: String
        let detectorHypothesis: String
        let decision: String
        let context: [String]
    }
    static let note = "Prévia PARCIAL, montada com o relatório (parágrafo do alerta, hipótese, decisão e o contexto registrado). "
        + "O pedido real pode incluir mais contexto: até três parágrafos vizinhos de cada lado, do manuscrito atual. "
        + "Esta prévia não é o texto exato transmitido."

    static func entries(for estimate: ValidatorV5Estimate, findings: [Finding], decisions: [String: ReviewDecision]) -> [Entry] {
        let byID = Dictionary(uniqueKeysWithValues: findings.map { ($0.id, $0) })
        return estimate.toSend.compactMap { sent in
            guard let f = byID[sent.id] else { return nil }
            let parts = f.segments
            return Entry(id: f.id, heading: "\(f.chapter) · § \(f.paragraph) · \(f.category)",
                         marked: parts.before + "⟦" + parts.marked + "⟧" + parts.after,
                         detectorHypothesis: f.reason, decision: decisions[f.id]?.rawValue ?? "—",
                         context: (f.context ?? []).filter { $0.paragraph != f.paragraph }.map { "§ \($0.paragraph): " + $0.text })
        }
    }
}

// MARK: Coordenação do fluxo (sem SwiftUI, testável com um backend simulado)

enum ValidatorV5Phase: Equatable {
    case idle, estimating, awaitingAuthorization, revalidating, running, finished, cancelled, failed
}

/// Conduz seleção → estimativa → autorização → revalidação → execução. Nunca grava decisões nem manuscrito;
/// só guarda o resultado da IA como dado à parte. O backend real (processo do motor) é injetado.
@MainActor
final class ValidatorV5Coordinator: ObservableObject {
    struct Backend {
        var estimate: (_ ids: [String], _ budget: Double) async throws -> ValidatorV5Estimate
        /// Executa; chama `progress` a cada avanço. Devolve como terminou.
        var run: (_ ids: [String], _ budget: Double, _ progress: @escaping (ValidatorV5Progress) -> Void) async throws -> Outcome
        var results: (_ ids: [String]) async throws -> ValidatorV5Results
        var cancel: () -> Void
    }
    enum Outcome { case finished, cancelled, failed(ValidatorV5Failure) }

    @Published private(set) var phase: ValidatorV5Phase = .idle
    @Published private(set) var estimate: ValidatorV5Estimate?
    @Published private(set) var progress: ValidatorV5Progress?
    @Published private(set) var results: ValidatorV5Results?
    /// Resultados que ficaram de uma execução interrompida ou com falha: continuam válidos.
    @Published private(set) var partial = false
    @Published private(set) var notice: String?
    @Published private(set) var failure: String?
    @Published private(set) var recoverable = true

    private let backend: Backend
    private var ids: [String] = []
    private var budget = ValidatorV5Arguments.defaultBudget
    private var secrets: () -> [String]

    init(backend: Backend, secrets: @escaping () -> [String] = { [] }) {
        self.backend = backend
        self.secrets = secrets
    }

    var isWorking: Bool { [.estimating, .revalidating, .running].contains(phase) }

    /// Seleção explícita: só IDs que o autor marcou, elegíveis agora, sem repetição e dentro do limite.
    func requestEstimate(ids selected: [String], eligible: Set<String>, budget: Double) async {
        guard !isWorking else { return }
        let unique = Array(NSOrderedSet(array: selected).compactMap { $0 as? String })
        failure = nil; notice = nil
        guard !unique.isEmpty else { return fail("Nenhum apontamento foi selecionado.") }
        guard unique.count <= ValidatorV5Arguments.defaultItems else {
            return fail("Selecione no máximo \(ValidatorV5Arguments.defaultItems) apontamentos por execução.")
        }
        guard unique.allSatisfy(eligible.contains) else { return fail("Há apontamentos sem decisão elegível na seleção.") }
        guard budget > 0, budget <= ValidatorV5Arguments.maxBudget else {
            return fail(String(format: "O teto deve ficar entre US$ 0,01 e US$ %.2f.", ValidatorV5Arguments.maxBudget))
        }
        phase = .estimating
        do {
            let found = try await backend.estimate(unique, budget)
            ids = unique; self.budget = budget
            estimate = found
            phase = .awaitingAuthorization
        } catch {
            estimate = nil
            fail(error.localizedDescription)
        }
    }

    func cancelBeforeSend() {
        guard phase == .awaitingAuthorization else { return }
        estimate = nil; phase = .idle
        notice = "Segunda opinião cancelada antes de enviar qualquer texto."
    }

    /// `authorized` vale só para esta chamada. Antes de enviar, o backend recalcula: se a estimativa mudou
    /// (itens, versão, custo, teto), nada é enviado e uma nova confirmação é exigida.
    func confirm(authorized: Bool, onProgress: @escaping (ValidatorV5Progress) -> Void = { _ in }) async {
        guard authorized, phase == .awaitingAuthorization, let shown = estimate else { return }
        guard shown.hasWork, shown.fitsBudget else { return fail("O teto não cobre o envio. Ajuste o teto e calcule de novo.", keepEstimate: true) }
        phase = .revalidating
        do {
            let fresh = try await backend.estimate(ids, budget)
            guard fresh.isEquivalent(to: shown) else {
                estimate = fresh
                phase = .awaitingAuthorization
                notice = "A estimativa mudou desde que foi mostrada (texto, decisões, versão ou custo). Confira e confirme de novo."
                return
            }
        } catch {
            phase = .awaitingAuthorization
            return fail(error.localizedDescription, keepEstimate: true)
        }
        phase = .running
        progress = nil
        estimate = nil
        do {
            let outcome = try await backend.run(ids, budget) { [weak self] value in
                self?.progress = value
                onProgress(value)
            }
            switch outcome {
            case .finished:
                await load(partial: false)
                phase = .finished
            case .cancelled:
                await load(partial: true)
                phase = .cancelled
                notice = "Segunda opinião interrompida. O que já foi avaliado ficou guardado e não é cobrado de novo."
            case .failed(let problem):
                await load(partial: true)
                recoverable = true
                failure = SecretRedactor.redact(problem.message, secrets: secrets())
                phase = .failed
            }
        } catch {
            await load(partial: true)
            failure = SecretRedactor.redact(error.localizedDescription, secrets: secrets())
            phase = .failed
        }
    }

    /// Pede o cancelamento do processo em andamento.
    func cancelRunning() {
        guard phase == .running else { return }
        backend.cancel()
    }

    /// Relê os resultados gravados (por exemplo, depois de editar o manuscrito). Sem rede.
    func refresh(ids selected: [String] = []) async {
        guard !isWorking else { return }
        if let loaded = try? await backend.results(selected) { results = loaded }
    }

    func reset() {
        guard !isWorking else { return }
        phase = .idle; estimate = nil; progress = nil; failure = nil; notice = nil
    }

#if DEBUG
    fileprivate func debugApply(_ phase: ValidatorV5Phase, _ estimate: ValidatorV5Estimate?, _ results: ValidatorV5Results?,
                                _ partial: Bool, _ notice: String?, _ failure: String?) {
        self.phase = phase; self.estimate = estimate; self.results = results
        self.partial = partial; self.notice = notice; self.failure = failure
    }
#endif

    /// Relê TODOS os resultados gravados do projeto (lista vazia = sem filtro): o lote que acabou de rodar é só
    /// uma parte, e a mesa precisa continuar vendo as validações anteriores.
    private func load(partial isPartial: Bool) async {
        if let loaded = try? await backend.results([]) {
            results = loaded
            partial = isPartial
        }
    }

    private func fail(_ message: String, keepEstimate: Bool = false) {
        failure = SecretRedactor.redact(message, secrets: secrets())
        recoverable = true
        if !keepEstimate { phase = .failed } else if phase != .awaitingAuthorization { phase = .failed }
    }
}

#if DEBUG
// Apenas para inspeção visual (LUME_SNAPSHOT): coloca o fluxo em estados fixos, sem backend e sem rede.
extension ValidatorV5Coordinator {
    func debugShow(phase: ValidatorV5Phase, estimate: ValidatorV5Estimate? = nil, results: ValidatorV5Results? = nil,
                   partial: Bool = false, notice: String? = nil, failure: String? = nil) {
        debugApply(phase, estimate, results, partial, notice, failure)
    }
}
#endif

// MARK: Avaliação editorial da decisão (A–F), derivada do diagnóstico completo da V5

/// Como a decisão humana aparece à luz do parecer da IA. É apresentação: não altera diagnóstico nem decisão, e
/// nenhuma categoria afirma que o autor "acertou" ou "errou": são pareceres da IA e podem estar equivocados.
enum DecisionAssessment: String, CaseIterable, Identifiable {
    case probablyCorrect, possibleError, reviewRecommended, inconclusive, notAnalyzed, outdated
    var id: String { rawValue }

    var title: String {
        switch self {
        case .probablyCorrect: return "Decisão provavelmente correta"
        case .possibleError: return "Possível erro na decisão"
        case .reviewRecommended: return "Revisão editorial recomendada"
        case .inconclusive: return "Análise inconclusiva"
        case .notAnalyzed: return "Ainda não analisada"
        case .outdated: return "Análise desatualizada"
        }
    }
    /// Versão curta para a linha do alerta.
    var short: String {
        switch self {
        case .probablyCorrect: return "IA: provavelmente correta"
        case .possibleError: return "IA: possível erro"
        case .reviewRecommended: return "IA: revisar"
        case .inconclusive: return "IA: inconclusiva"
        case .notAnalyzed: return "IA: não analisada"
        case .outdated: return "IA: desatualizada"
        }
    }
    var symbol: String {
        switch self {
        case .probablyCorrect: return "checkmark.circle"
        case .possibleError: return "exclamationmark.circle"
        case .reviewRecommended: return "eye"
        case .inconclusive: return "questionmark.circle"
        case .notAnalyzed: return "circle.dashed"
        case .outdated: return "clock.badge.exclamationmark"
        }
    }
    /// Só `notAnalyzed` e `outdated` pedem uma nova execução para ficarem em dia.
    var needsRun: Bool { self == .notAnalyzed || self == .outdated }
}

enum ValidatorV5Assessment {
    /// Classifica olhando o diagnóstico inteiro (resultado, existência, natureza, certeza, adequação e evidências),
    /// não só o rótulo do resultado. Em dúvida ou contradição, é inconclusiva; ausência de problema num alerta que o
    /// autor já rejeitou nunca vira "possível erro".
    static func classify(_ item: ValidatorV5Item?, liveDecision: ReviewDecision?) -> DecisionAssessment {
        guard let item else { return .notAnalyzed }
        if let live = liveDecision, live.rawValue != item.previousDecision { return .outdated }
        guard item.isCurrent, item.situation == "valida" else { return .outdated }
        let exists = item.existence.exists
        let supported = !item.evidence.isEmpty
        switch item.result {
        case "mantida", "apontamento_inadequado":
            // Sustenta a decisão só com adequação declarada, existência definida e evidência verificada.
            return item.decisionAdequacy == "adequada" && exists != "incerto" && supported ? .probablyCorrect : .inconclusive
        case "contestada":
            guard item.decisionAdequacy == "inadequada", exists == "sim" || exists == "nao", supported else { return .inconclusive }
            // Desvio objetivo e claro, ou a IA não vê o problema que o autor reconheceu: contradiz a decisão.
            if exists == "nao" || (item.existence.nature == "objetivo" && item.existence.certainty == "clara") {
                return .possibleError
            }
            return .reviewRecommended           // existe, mas é interpretativo ou discutível: sem afirmar erro
        case "revisao_recomendada":
            return exists == "sim" ? .reviewRecommended : .inconclusive
        default:
            return .inconclusive
        }
    }

    /// Frase curta do parecer, sem "você acertou/errou".
    static func explanation(_ assessment: DecisionAssessment, item: ValidatorV5Item?, liveDecision: ReviewDecision? = nil) -> String {
        switch assessment {
        case .probablyCorrect:
            return item?.existence.exists == "nao"
                ? "Parecer da IA: ela também não vê desvio neste trecho; a sua decisão parece compatível com o texto."
                : "Parecer da IA: a sua decisão parece compatível com o texto e com as evidências verificadas."
        case .possibleError:
            return item?.disagreementMeaning ?? "Parecer da IA: há evidências que contradizem a sua decisão."
        case .reviewRecommended:
            return "Parecer da IA: a decisão pode ser defensável, mas há uma questão que merece reconsideração. A IA não afirma erro."
        case .inconclusive:
            return "A IA não teve evidência ou certeza suficiente para julgar esta decisão."
        case .notAnalyzed:
            return "Esta decisão foi registrada, mas ainda não tem validação atual."
        case .outdated:
            if let item { return ValidatorV5Wording.staleness(item, decisions: liveDecision.map { [item.id: $0] } ?? [:])?.message
                ?? "O texto, a decisão ou a configuração mudou desde a análise." }
            return "O texto, a decisão ou a configuração mudou desde a análise."
        }
    }
}

/// Lotes sucessivos: até `limit` itens por execução, cada um com a sua confirmação.
enum ValidatorV5Batching {
    static func plan(_ ids: [String], limit: Int = ValidatorV5Arguments.defaultItems) -> (next: [String], remaining: Int, batches: Int) {
        let unique = Array(NSOrderedSet(array: ids).compactMap { $0 as? String })
        let size = max(1, min(limit, ValidatorV5Arguments.maxItems))
        let next = Array(unique.prefix(size))
        return (next, unique.count - next.count, (unique.count + size - 1) / size)
    }
}
