# Lume — instruções para agentes de código

## Mapa e leitura inicial

A raiz Git é `Lume/`, organizada no padrão do GitHub:

| Pasta | Conteúdo |
| --- | --- |
| `app/` | Interface SwiftUI (`app/Lume/`) e projeto Xcode (`app/Lume.xcodeproj/`) |
| `fonte/` | Motor FONTE (pacote Python `fonte-revisor`, código em `fonte/fonte/`) |
| `coerencia/` | Motor Coerencia (pacote `coerencia`, embutido no FONTE) |
| `packaging/` | Entrada do motor congelado e pacotes `.lumemotor` |
| `scripts/` | Montagem (`montar-lume.command`), LanguageTool e avaliações |
| `tests/` | Contratos e empacotamento |
| `examples/`, `docs/` | Exemplos de referência e documentação |
| `build/` | Saídas locais, fora do Git |

Comandos são executados a partir da raiz. Não criar pastas paralelas nem reorganizar a
arquitetura para reproduzir exemplos.

Leia os documentos pertinentes antes de alterar código:

- [Visão geral](README.md), [CHANGELOG](CHANGELOG.md) e
  [README do Coerencia](coerencia/README.md).
- [Arquitetura existente](docs/arquitetura.md).
- [Validação e limites](docs/validacao.md).
- [Visão do produto](docs/visao.md), principalmente “Ocorrência, pendência e encerramento” e
  “Precisão antes de cobertura irrestrita”.
- [ExecPlans](.agent/PLANS.md) para mudanças complexas.
- `docs/product/lume-v0.11.md` e `docs/testing/acceptance-v0.11.md` são históricos: a
  memória narrativa heurística que eles descrevem foi removida em 29/09/2026. Os
  comandos de teste e os gates de preservação (manuscrito, contratos) continuam válidos.

Leia também os `AGENTS.md` dos diretórios que serão editados, inclusive quando
iniciar na raiz. Documentos de produto descrevem objetivos; somente código e
evidências da revisão atual demonstram implementação. Resultados históricos não
aprovam um patch novo.

## Invariantes

1. A análise nunca altera o manuscrito. Analisar uma captura de leitura; manter bytes, hash,
   parágrafos, trechos e índices Unicode. Sugestões e decisões ficam em relatórios.
   Única exceção: a correção que o autor pede no app, alerta por alerta, num documento do
   Pages. Ela troca só o trecho destacado (ou, se o autor escolher **Editar parágrafo**, só a
   parte alterada daquele parágrafo), guarda antes uma cópia do arquivo, é conferida
   pelo motor (só aquele parágrafo mudou) e é desfeita se a conferência falhar. Nenhuma
   correção é aplicada automaticamente ou em lote.
2. Preservar o pipeline modular. Etapas posteriores consomem resultados anteriores
   sem reescrevê-los; uma falha interrompe as etapas dependentes.
3. Swift cuida da interface, navegação, decisões, progresso, relatórios, seleção do
   motor e da chave da API. A análise pertence ao Python (FONTE e Coerencia).
4. Nenhuma regra ou instrução de modelo pode depender dos manuscritos reais de referência, de nomes de
   personagens, objetos particulares ou gênero literário. Generalizar cada defeito
   como classe editorial e testar substituições de nomes, objetos e contexto.
5. Na dúvida, não alertar. Evidência fraca não entra na fila do editor: fica como informação,
   diagnóstico do motor ou não é emitida, conforme a política de destino. Não transformar suspeita
   em erro confirmado nem inventar sujeito, falante, tempo ou continuidade.
6. Todo alerta aponta trechos que existem no texto. Trechos citados por um modelo de
   linguagem são conferidos no parágrafo indicado; o que não existir é descartado.
7. Recursos com IA (Coerência e Auditoria final): nada é enviado à API sem ação e
   confirmação do usuário, com os capítulos ou trechos a enviar e o custo estimado; respeitar o teto de gasto; enviar só o que
   mudou; nunca registrar a chave em arquivos, argumentos ou relatórios.
8. Preservar contratos JSON e leitura de relatórios, decisões e configurações antigos
   (inclusive chaves de regras retiradas). Não confundir confiança heurística com
   probabilidade nem ausência de exceções com correção.
9. O manuscrito precisa poder chegar ao fim. O critério de sucesso é a precisão das pendências e
   um encerramento claro (“Revisão concluída”), não a ausência de alertas nem a cobertura máxima.
   Só é impeditiva a classe com precisão real ≥ 90% em ≥ 20 decisões, natureza objetiva e
   severidade de erro; classes editoriais, narrativas, de repetição, referência, estilo ou
   continuidade nunca são impeditivas. Plano: `.agent/plans/encerramento-editorial.md`.

## Forma de trabalhar

- Conferir estado Git, instruções aplicáveis, implementação e testes antes de editar.
  Preservar trabalho local de outras tarefas; não limpar, reverter ou incluir suas
  alterações por conveniência.
- Delimitar uma mudança verificável. Para funcionalidades complexas, contratos,
  refactors ou alterações entre módulos, manter um ExecPlan conforme `.agent/PLANS.md`.
- O repositório é público. Nunca versionar trechos, nomes de personagens ou adaptações
  próximas de manuscritos reais (em testes, corpus, exemplos, documentos, imagens ou
  mensagens de commit). Relatórios reais servem só para descobrir a classe do problema;
  o caso de teste é escrito do zero, com outras palavras e outros nomes.
- Um falso negativo encontrado depois **não** pede uma regra automaticamente. Antes de qualquer
  regra ou detector novo, responder: a classe é generalizável, relevante e detectável com boa
  precisão? Se não, o erro fica fora da cobertura automática, e isso é delimitação, não fracasso.
  Não criar regra a partir de um caso isolado.
- Uma classe nova entra como informação ou diagnóstico e só vira pendência com precisão medida em
  livros reais (`scripts/medir_precisao.py`, quando existir).
- Para correções de detecção aprovadas por essa pergunta, escrever primeiro o caso esperado,
  demonstrar a falha e implementar a menor correção genérica, com positivos, negativos e
  ambiguidades. O corpus de `fonte/tests/corpus/deteccao/` recebe classes, não cada caso
  isolado, e é medido com `scripts/avaliar_deteccao.py`. Não enfraquecer ou remover testes
  para passar.
- Falso positivo vale tanto quanto falso negativo: uma mudança que baixa a precisão das
  pendências é regressão e precisa de justificativa, como a perda de acertos.
- Não editar manuscritos, resultados esperados ou relatórios de referência para
  esconder regressões. Uma mudança legítima de expectativa precisa de justificativa.
- Para código funcional, executar testes afetados, suítes do FONTE e do Coerencia,
  testes de integração e contratos Python/Swift (comandos nos READMEs). Mudanças que
  alteram alertas exigem comparação antes/depois nos manuscritos reais de referência (A e B).
- Chamadas reais à API custam dinheiro do usuário: testar com modelo simulado e só
  usar a API com autorização, em textos curtos, informando o custo.
- Para documentação apenas, conferir caminhos, referências, comandos por inspeção,
  consistência e diff.
- Não declarar concluída uma alteração funcional com falha ou regressão conhecida.
  Se faltar corpus, dependência ou execução, registrar a pendência e o motivo.
- Ao terminar, informar arquivos alterados, testes realmente executados, resultados,
  métricas comparáveis antes/depois (alertas e pendências, não só acertos) e limitações.
  Revisar o diff final separadamente da implementação.

## Fora do escopo atual

Interpretação literária, inferência psicológica, regras profundas de gênero, reescrita
automática do texto e a busca de “zero alertas” ou cobertura total. A Auditoria final com IA fica nas categorias fechadas de
`fonte/fonte/auditoria_ia.py`; ampliá-las é uma mudança de escopo.
