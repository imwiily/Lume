# Lume — instruções para Codex

## Mapa e leitura inicial

A raiz Git é `Lume/`; o produto está em `LumeMac/`. O pacote Python se chama
`fonte-revisor`, mas sua pasta real é `LumeMac/Analisador/`. A interface SwiftUI
fica em `LumeMac/Lume/`. Não criar pastas paralelas `fonte-revisor/` ou
`lume-swift/` nem reorganizar a arquitetura para reproduzir exemplos de prompts.

Leia os documentos pertinentes antes de alterar código:

- [Produto e objetivo v0.11](docs/product/lume-v0.11.md).
- [Critérios e comandos de aceitação](docs/testing/acceptance-v0.11.md).
- [Arquitetura existente](LumeMac/Documentacao/ARQUITETURA.md).
- [Validação histórica e limites](LumeMac/Documentacao/VALIDACAO.md).
- [Visão do produto](LumeMac/Documentacao/VISAO.md) e [README](LumeMac/README.md).
- [ExecPlans](.agent/PLANS.md) para mudanças complexas.

Leia também os `AGENTS.md` dos diretórios que serão editados, inclusive quando
iniciar na raiz. Eles complementam estas regras para motor, interface e testes.
Documentos de produto descrevem objetivos; somente código e evidências da revisão
atual demonstram implementação. Resultados históricos não aprovam um patch novo.

## Invariantes

1. O manuscrito é imutável. Analisar uma captura de leitura; manter bytes, hash,
   parágrafos, trechos e índices Unicode. Sugestões e decisões ficam em relatórios.
2. Preservar o pipeline modular. Etapas posteriores consomem resultados anteriores
   sem reescrevê-los; uma falha interrompe as etapas dependentes.
3. Swift cuida da interface, navegação, decisões, progresso, relatórios e seleção
   do motor. A análise linguística, semântica e narrativa pertence ao Python.
4. Nenhuma regra pode depender de Hikari, Echoes, nomes de personagens, objetos
   particulares ou gênero literário. Generalizar cada defeito como classe editorial
   e testar substituições de nomes, objetos e contexto.
5. Preferir `unresolved` quando faltar evidência. Não inventar sujeito, falante,
   destinatário, identidade, tempo ou continuidade para aumentar cobertura.
6. Reutilizar `semantic_roles` confiáveis: AGENT, PATIENT, OBJECT, RECIPIENT,
   LOCATION, SOURCE, DESTINATION, INSTRUMENT e HOLDER. Não reextrair sujeito e
   objeto arbitrariamente quando o evento já fornece esses papéis.
7. A confiança deve propagar entidade → referência → evento → fato, incluindo
   papéis e nível de inferência. Não aumentar artificialmente a confiança nem
   transformar fatos fracos em memória ou alertas fortes.
8. Distinguir evento, candidato a fato, fato local e persistente. Todo fato mantém
   origem, evidência, escopo, polaridade, confiança e validade. Histórico preserva
   transições; estado atual deriva desse histórico.
9. Participantes e objetos locais ou não resolvidos não viram identidades canônicas
   automaticamente. A passagem entre cenas exige evidência de identidade e validade.
10. Preservar contratos JSON e leitura de relatórios/decisões antigos. Não confundir
    confiança heurística com probabilidade, volume de fatos com precisão ou
    ausência de exceções com correção semântica.

## Forma de trabalhar

- Conferir estado Git, instruções aplicáveis, implementação e testes antes de editar.
  Preservar trabalho local de outras tarefas; não limpar, reverter ou incluir suas
  alterações por conveniência.
- Delimitar uma mudança verificável. Para funcionalidades complexas, schema,
  fact bank, refactors ou alterações entre módulos, manter um ExecPlan conforme
  `.agent/PLANS.md`, da investigação à validação.
- Para correções/funcionalidades semânticas, escrever primeiro o caso esperado,
  demonstrar a falha relevante e implementar a menor correção genérica. Incluir
  positivos, negativos e ambiguidades. Não enfraquecer ou remover testes para passar.
- Não editar manuscritos, resultados esperados ou relatórios de referência para
  esconder regressões. Uma mudança legítima de expectativa precisa de justificativa.
- Para código funcional, executar testes afetados, suíte do analisador, regressões
  e contratos pertinentes conforme `docs/testing/acceptance-v0.11.md`. Mudanças
  narrativas/globais exigem corpus sintético, Echoes e Hikari antes do fechamento.
- Para documentação apenas, conferir caminhos, referências, comandos por inspeção,
  consistência e diff. Não é necessário montar o app ou reanalisar manuscritos.
- Não declarar concluída uma alteração funcional com falha ou regressão conhecida.
  Se faltar corpus, dependência ou execução, registrar o gate como pendente, o motivo
  e o que falta; não apresentar ausência de validação como aprovação.
- Ao terminar, informar arquivos alterados, testes realmente executados, resultados,
  métricas comparáveis antes/depois e limitações. Revisar o diff final separadamente
  da implementação. Isso não implementa o módulo Auditor Final.

## Limites desta etapa

A v0.11 prioriza promoção seletiva de eventos para memória útil. Auditor Final,
interpretação literária, causalidade complexa, inferência psicológica, regras
profundas de gênero e reescrita automática ficam fora do escopo.

O guia de [AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
descreve as instruções por diretório; o padrão de
[ExecPlans](https://developers.openai.com/cookbook/articles/codex_exec_plans)
orienta os planos locais. `.agent/PLANS.md` é referenciado explicitamente aqui.
