# ExecPlan — Validador de Decisões

Branch `feature/validador-decisoes`, a partir de `hotfix/lume-1.8.1` (`470814c`, 10/10/2026).
Segunda leitura crítica, opcional e manual, das decisões que o autor já tomou. Nunca altera
decisão, relatório nem manuscrito.

## Objetivo e escopo

Na Mesa de Revisão, a ação **Validar decisões** reavalia decisões elegíveis com Haiku 5.5
(triagem) e Sonnet 5.5 (reavaliação) e mostra só as que merecem reconsideração, com evidência.
Fora do pedido: mudar a decisão, o relatório, o FONTE/Coerência/Auditoria, o motor de correção do
Pages, preços fixos novos, orçamento global entre execuções (ver “Divergência”).

## Estado atual observado (inspeção em 10/10/2026)

- **Decisões** (`app/Lume/Models.swift:81`): `ReviewDecision` com rawValues `Pendente`,
  `Erro confirmado`, `Estilo do autor`, `Falso positivo`, `Intencional`, `Aceito editorialmente`,
  `Corrigido`. Persistidas por `ReviewStore.autosave` em `decisionURL(for:)` como `DecisionFile`
  (`schema_version`, `sha256`, `document`, `decisions: {id: rawValue}`, `conflitos`) e na memória
  do livro (`BookMemory`). O ID do alerta é derivado de parágrafo, texto e posição pelo FONTE.
- **Alertas** vivem em `relatorio.json` → `findings[]` (`id`, `category`, `paragraph`, `text` =
  parágrafo inteiro, `start`/`end` em pontos de código, `reason`, `source`, `rule`, `layer`).
  A Auditoria IA (`rule=auditoria_ia`) e a Coerência (`rule=coerencia_ia`) entram nesse mesmo
  campo — não há registro à parte. Ocorrências absorvidas ficam em `absorvidos`.
- **Leitura do manuscrito**: `fonte.reader.read_manuscript(path, settings)` → `Block(number, text,
  chapter, heading…)`; já usada por `auditoria-estimar`. Sem tokens de IA.
- **Cliente da API**: `coerencia.modelo.Claude` (`json()` com esquema estrito, cache do prompt
  de sistema, repetição só de falhas não cobradas, conta o pior caso antes de enviar),
  `Orcamento` (teto por execução, `TetoAtingido`), `criar_modelo`, `PRECOS`/`tarifa`.
  `claude-haiku-5-5` já tem preço (faixa mais cara, conservadora) e, por não estar em `ATUAIS`,
  usa `messages.create` sem `effort`/`fallbacks`.
- **Padrão de recurso com IA**: `auditoria_ia.py` (estimar sem rede → confirmar → executar com
  teto → registro por chave de conteúdo em `<projeto>/auditoria.json`, escrita atômica →
  conferência dos trechos devolvidos). A chave segue por `ANTHROPIC_API_KEY` no ambiente do
  processo (Swift lê nas Chaves do macOS). Linhas de protocolo: `LUME_ESTIMATIVA_*`, `LUME_PROGRESS`.
- **Testes**: baseline antes de editar — FONTE 503 OK, Coerencia 44 OK, contratos `tests/` OK.
  Dublê de modelo: `ModeloFalso` em `fonte/tests/test_auditoria_ia.py`.

### Divergência com o pedido

O pedido fala em “limite global existente”. Na versão estável só existe **teto por execução**
(`--auditoria-teto`, `Orcamento`). O `OrcamentoGlobal` está só na branch experimental
`experiment/haiku-5.5`, não integrada. Decisão: usar o teto por execução existente; o global
fica como próximo passo, a decidir pelo autor.

## Decisões arquiteturais

1. **Python faz tudo que é análise** (invariante 3): `fonte/fonte/validador_decisoes.py`; Swift só
   confirma, executa e exibe. Subcomandos novos da CLI existente: `validar-decisoes-estimar` e
   `validar-decisoes`. Nenhum módulo existente muda de comportamento.
2. **Entrada**: manuscrito atual + `relatorio.json` + arquivo de decisões (`DecisionFile`) — o Swift
   já os tem. Elegíveis: `Erro confirmado`, `Estilo do autor`, `Falso positivo`, `Intencional`,
   `Aceito editorialmente`. `Pendente`, `Corrigido` e valores desconhecidos nunca entram.
3. **Integridade antes do envio**: o alerta só é avaliado se o parágrafo atual for idêntico ao
   `text` do relatório (mesmo número, ou único parágrafo idêntico em outro lugar). Senão vira
   `trecho_alterado`/`nao_localizado` e nada é enviado; sem aproximação.
4. **Contexto adaptativo**: Haiku recebe ±1 parágrafo; se pedir mais, o Lume (não o modelo)
   busca localmente, no capítulo, parágrafos que contenham os termos pedidos, até um teto de
   caracteres. Sonnet recebe ±3 mais o que foi recuperado.
5. **Híbrido coordenado pelo Lume**: Haiku → (`contestar`, `incerto`, `precisa_contexto` +
   amostra determinística de `manter`) → Sonnet com a evidência original, não o resumo. Modo
   `sonnet_direto` para o experimento. Sem limiares de confiança numéricos.
6. **Custo**: estimativa local, conservadora, com reserva para o Sonnet; teto por execução;
   Haiku só gasta teto − reserva; parar por teto deixa o resultado parcial e dito.
7. **Resultados à parte**: `<projeto>/validacao-decisoes.json`, chaveado por ID do alerta, com
   impressão digital (versão do prompt, modelo, decisão, texto, contexto). Mudou algo → reavalia.
8. **Privacidade**: só trechos necessários; nada do manuscrito em log; texto do manuscrito entra
   entre marcadores como dado.

## Arquivos

- `fonte/fonte/validador_decisoes.py` (novo) · `fonte/fonte/cli.py` (2 subcomandos)
- `fonte/tests/test_validador_decisoes.py` (novo)
- `app/Lume/ValidatorView.swift` (novo) · `ReviewStore.swift`, `ReadingDeskView.swift`,
  `Models.swift`, `project.pbxproj` (integração mínima)
- `docs/arquitetura.md`, `CHANGELOG.md` ao final

## Progresso

- [x] Fase 1 — diagnóstico, branch e baseline
- [x] Fase 2 — núcleo Python + testes (32 testes, sem API)
- [x] Fase 3 — integração Swift (build, `ValidatorCheck`, contratos)
- [x] Fase 4 — regressão: FONTE 535 OK, Coerencia 44 OK, `tests/` 53 OK, contratos Swift OK
- [ ] Pendente: inspeção visual nativa das duas folhas; execução real autorizada (texto curto) e
      comparação Haiku→Sonnet × Sonnet direto; motor congelado não foi remontado.

Achados da própria revisão corrigidos: sanitização destruía os marcadores `<<<TEXTO`; o modelo
registrado agora é o que respondeu (retomada automática); teto mínimo informado.

## Homologação técnica (10/10/2026, sem chamadas pagas)

- Manuscrito real de referência (relatório de 79 alertas, SHA `d75a…`): 71 elegíveis, 8 `Corrigido` excluídos, 71/71 localizados
  no documento do relatório; com parágrafos inseridos/apagados, 71/71 relocalizados por texto.
- O documento vivo está no iCloud Pages (bloqueado ao processo por TCC): a simulação usou a cópia de
  `Copias/` com o mesmo SHA. Reexecutar com o arquivo atual antes do teste pago.
- Estimativa no manuscrito de referência (híbrido): US$ 0,29 estimado, US$ 0,76 máximo, teto mínimo US$ 0,68.
- Corrigidos: tokens e pedidos na estimativa; custo mínimo do modo direto; trilha da amostragem
  (taxa, sorteio, selecionado, discordâncias); resumo da confirmação (separação, aviso, pedidos).
- Risco aberto: decisão sobre alerta cujo parágrafo foi editado por outra correção fica
  `trecho_alterado` (1 de 71 no manuscrito de referência); critério mantido por precisão.

## Correção de precisão (prompt v2, 11/10/2026)

Causa: apontamento do detector tratado como fato (`reason` inclui o tempo declarado em `--tempo`), lista
de exceções do detector usada como critério fechado, decisões sem definição, alvo ambíguo e rótulo A/B
livre. Alternativas implementadas: A (hipótese), C (significado das decisões), D (alvo inequívoco), E
(classificação estruturada) e as conferências da G (evidência x ocorrência, contradição entre itens).
Fora: B (neutralizar o `reason`) e F (teto para categorias editoriais). FONTE não alterado; falha de
anterioridade registrada em `.agent/plans/anterioridade-perfeito-aspectual.md`.

## Semântica de `Estilo do autor` e `Intencional` (11/10/2026)

Verificado: não havia regra que as tornasse incoerentes quando o apontamento procede (o código delegava
ao modelo), mas o contrato tinha três falhas: `procede` misturava validade técnica com legitimidade
(“sem admitir leitura legítima”); o prompt não citava oralidade, caracterização ou voz do narrador como
razões legítimas; e a contestação se “provava” só com o próprio alvo.
Correção: `procede` passa a ser só validade técnica; `justificativa_editorial` (presente, ausente,
incerta, nao_se_aplica) com `evidencia_estilistica`; `decisao_coerente` deixa de ser declarada pelo
modelo e é derivada pelo significado da categoria; contestar uma preservação exige `evidencia_contexto`
específica, no texto enviado e fora do alvo; o registro do alvo (diálogo, pensamento, narração) é
informado ao modelo. Intenção indeterminada é inconclusiva (`intencao_indeterminada`).
Experimento comparativo V2: pasta de projeto nova, referência V1 preservada e somente leitura; a chave
de reaproveitamento inclui `VERSAO_PROMPT`, então nada da V1 é reutilizado.

## Experimento de isolamento do Haiku (preparado em 11/10/2026, não executado)

Oito contestações da V1 que o Haiku encerrou na V2 sem o Sonnet (IDs em `iso/ids8.json` no diretório do
experimento): Sonnet V2 direto (`--modo sonnet_direto`) sobre um arquivo de decisões filtrado, pasta de
projeto nova, referência V1 e resultados V2 intactos. 3 pedidos; estimado ~US$ 0,10; teto mínimo do
`Orcamento` US$ 0,66 (pior caso de um pedido ~US$ 0,60); teto proposto US$ 0,75.
