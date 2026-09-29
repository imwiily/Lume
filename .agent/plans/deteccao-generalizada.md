# ExecPlan — detecção generalizada: avaliação cega e corretor gramatical embutido

Iniciado em 29/09/2026. Plano vivo; atualizar progresso, descobertas e evidências.

## Objetivo e escopo

O usuário relatou que textos novos com erros propositais não são detectados. Uma
medição inicial confirmou: num texto inédito com 23 erros anotados, o motor atual
encontrou 3 erros reais sem LanguageTool (mais 2 coincidências por outra regra) e
11 com um LanguageTool local iniciado manualmente, além de 6 falsos positivos.
Nenhuma das 4 contradições narrativas foi encontrada.

Esta tarefa entrega duas coisas:

1. **Avaliação cega de detecção.** Corpus anotado de textos sintéticos inéditos,
   dividido em `desenvolvimento` (pode orientar correções) e `validacao` (nunca
   usado para ajustar regras), e um script que gera DOCX, executa o motor e mede
   cobertura por categoria e alarmes falsos, com denominadores explícitos.
2. **Corretor gramatical embutido.** LanguageTool local passa a ser encontrado e
   iniciado pelo próprio motor (servidor só em 127.0.0.1, sem nuvem), com Java
   próprio no pacote do motor. Erros objetivos dentro de falas passam a ser
   revistos, sem formalizar a voz dos personagens. Regras FONTE complementares
   cobrem lacunas de classes gerais (crase, há/a, por que interrogativo, vocativo).

Exemplo antes/depois (texto de desenvolvimento): “— Voce viu o Paulo?” não gera
alerta hoje porque a fala é mascarada; depois, “Voce” deve ser apontado.
“— Você viu? — perguntou ela.” não deve gerar alerta de maiúscula em “perguntou”.

Fora do escopo: IA/LLM para memória narrativa (decisão adiada pelo usuário),
melhoria de extração de fatos, Auditor Final, mudança de schema do relatório.
As contradições narrativas entram no corpus apenas como linha de base.

Gates afetados de `docs/testing/acceptance-v0.11.md`: A01 (manuscrito imutável),
A11 (contratos compatíveis), A12 (regressão), A13 (corpus real — ver pendências),
A14 (fechamento). A02–A10 não são alvo; devem continuar sem regressão.

## Estado atual observado no código

- Revisão Git `24f73a8` com muitas alterações locais não commitadas de outras
  etapas (motor 0.9.5). Preservar; não incluir nem reverter.
- `fonte/linguistic.py`: ~20 padrões regex (pontuação duplicada, espaço, quê,
  vocativo restrito a nome + você/proibição, maiúscula após pergunta, “além de disso”).
  Padrões sintáticos só na narração; mecânicos também em falas.
- `fonte/languagetool.py`: cliente HTTP para servidor externo em 127.0.0.1:porta.
  Envia `narrative_masks` (falas, aspas e itálicos trocados por espaços), o que
  esconde erros das falas e produz falsos “frase sem maiúscula” em incisos
  (“— … — perguntou ela”). Resultado sem `rule`, `suggestion` nem `category_code`
  específicos; `contracts.standardize` força `probable_error`.
- `fonte/cli.py`: `--languagetool` (store_true) + `--porta-lt 8081`. Sem a flag,
  aviso de que ortografia/concordância/regência dependem do LanguageTool.
- Swift `ReviewStore.useLanguageTool = false`; `ContentView` mostra “Corretor
  gramatical local” com ajuda “iniciado separadamente na porta 8081”.
- `Scripts/build_engine.py` congela o motor com PyInstaller em `.lumemotor`
  (`runtime/`, `manifest.json` com inventário). Nada de Java/LanguageTool.
- Ambiente: Mac M3 16 GB, OpenJDK 25 via Homebrew, LanguageTool 6.6 baixado só
  no scratchpad da sessão para a medição inicial.
- Testes: 326 do analisador e 17 de pacotes aprovados antes das mudanças.
  `test_fonte.py`/`test_pipeline.py` cobrem o cliente LanguageTool com servidor
  simulado (conferir antes de alterar).

## Arquivos afetados e preservação da arquitetura

| Caminho | Mudança |
| --- | --- |
| `LumeMac/Analisador/tests/corpus/deteccao/*.json` | Corpus anotado (novo) |
| `LumeMac/Scripts/avaliar_deteccao.py` | Avaliação cega (novo) |
| `LumeMac/Tests/test_detection_benchmark.py` | Integridade do corpus e do placar (novo) |
| `LumeMac/Analisador/fonte/languagetool.py` | Localizar/iniciar servidor; falas; filtros; campos do contrato |
| `LumeMac/Analisador/fonte/linguistic.py` | Regras genéricas complementares |
| `LumeMac/Analisador/fonte/settings.py` | Novas chaves de regra (padrão ligado; configs antigas preservadas) |
| `LumeMac/Analisador/fonte/cli.py`, `pipeline.py` | Resolução embutido/externo; avisos |
| `LumeMac/Scripts/preparar_languagetool.py` | Baixa LT fixado por SHA-256, poda idiomas, gera JRE mínimo (novo) |
| `LumeMac/Scripts/build_engine.py`, `Montar-Lume.command` | Copiar LT+JRE ao pacote e testar |
| `LumeMac/Lume/ReviewStore.swift`, `ContentView.swift` | Ligado por padrão; texto de ajuda |

Preservação: o manuscrito continua só lido; offsets seguem pontos de código
(conversão UTF-16 do LT mantida); o LT roda na etapa Linguística existente, sem
nova etapa; relatórios v1 mantêm campos; `--languagetool`/`--porta-lt` mantêm o
significado para servidor externo quando não houver LT embutido. Uma configuração
antiga com todas as regras desligadas não reativa as regras novas (mesmo mecanismo
de `NEW_RULES` já usado em `settings.validate`; conferir).

Questão de compatibilidade Swift ↔ motor: o app só passa `--languagetool` quando o
toggle está ligado; o CLI sem a flag continua sem LT. Assim, um motor antigo
selecionado não recebe argumentos desconhecidos. Com o toggle ligado por padrão,
um motor antigo sem servidor externo falha com a mensagem existente — registrar.

## Etapas incrementais

1. Corpus + script + teste de integridade. Medir linha de base (sem LT; com LT
   externo atual). Encerramento: tabela por categoria salva em `LumeMac/Saida/`.
2. LanguageTool: enviar texto de falas; filtrar maiúscula em incisos de diálogo,
   regras de estilo/registro e sobreposição com regras FONTE; preencher `rule`,
   `category_code`, `suggestion`, severidade por categoria LT. Testes com servidor
   simulado. Encerramento: falsos positivos de incisos zerados no desenvolvimento.
3. Regras FONTE complementares, cada uma com positivos, negativos e ambíguos.
4. Ciclo de vida: localizar Java/LT (variável de ambiente, pacote do motor,
   pasta de desenvolvimento), iniciar em porta livre de 127.0.0.1, aguardar,
   encerrar sempre. Testes com processo simulado.
5. Empacotamento: script de preparação; `build_engine.py` inclui `languagetool/`;
   probe verifica. Swift: ligado por padrão.
6. Validação: suítes, contratos, avaliação `validacao` (uma vez, sem ajuste
   posterior), revisão do diff.

## Testes, critérios de aceitação e riscos

- Cobertura linguística no conjunto `validacao` deve subir em relação à linha de
  base medida antes das mudanças; alarmes falsos nos textos de controle devem ser
  relatados, não escondidos. Nenhuma meta percentual fixada depois de ver números.
- Riscos: falsos positivos em falas coloquiais (controles “Tá”, “pra”, “Me faz”);
  LT indisponível no ambiente de teste (testes simulados + execução real marcada);
  tamanho do pacote (LT+JRE); tempo de inicialização do Java.
- Corpus sintético é escrito pelo mesmo agente que implementa; não é avaliação
  independente. O usuário deve acrescentar textos próprios para medir de verdade.

## Comandos e evidências

- Avaliação: em `LumeMac/`, `Analisador/.venv/bin/python Scripts/avaliar_deteccao.py
  --conjunto desenvolvimento --saida Saida/<nova>` (ver `--help`).
- Suítes: comandos de `docs/testing/acceptance-v0.11.md`.

## Progresso, descobertas e decisões

- [x] 29/09 Medição exploratória no scratchpad (3/23 sem LT; 11/23 com LT; 0/4 narrativa).
- [x] Etapa 1 — corpus (4 textos por conjunto, 1 de controle cada), `Scripts/avaliar_deteccao.py`,
  `Tests/test_detection_benchmark.py`. Linha de base em `Saida/deteccao-generalizada/base-*`.
- [x] Etapa 2 — `languagetool.py`: falas enviadas; filtros de inciso, nomes, estilo/registro, itálico;
  sugestão e confiança; sobreposição com FONTE omitida. `tests/test_languagetool.py`.
- [x] Etapa 3 — `grammar.py` (crase, homófonos, concordância, regência, vírgula sujeito–verbo),
  vocativo após resposta/cumprimento, interrogativos fora do vocativo antigo, ‘há’ de abertura e
  adjetivo posposto no tempo verbal. `tests/test_grammar.py`.
- [x] Etapa 4 — ciclo de vida do servidor embutido (porta livre em 127.0.0.1, registro em arquivo,
  encerramento garantido); CLI `--languagetool`/`--porta-lt`; `languagetool_origem`.
- [x] Etapa 5 — `Scripts/preparar_languagetool.py`, `build_engine.py`, `Montar-Lume.command`,
  probe `grammar_checker`; Swift: corretor ligado por padrão e cinco regras na configuração.
- [x] Etapa 6 — validação (abaixo).

Decisões:
- Regência “chegar em/na” é anotada como erro de norma culta, mas o alerta é
  `editorial_attention`; colocação pronominal e coloquialismos em falas são aceitáveis.
- A CLI continua sem corretor por padrão; o app envia `--languagetool` (toggle ligado).
  Assim um motor antigo não recebe argumento desconhecido; sem servidor externo, ele falha
  com a mensagem existente e o usuário pode desligar a opção.
- LanguageTool: o registro de idiomas não pode ser podado (detector de idioma) e o português
  usa o dicionário de inglês; só dados grandes de outros idiomas saem. Paridade com o LT
  completo verificada no corpus.
- Número de versão do motor/app não foi alterado (decisão de entrega do usuário).

Descobertas:
- Placar inicial casava trechos curtos dentro de palavras (“a a” em “tinha acontecido”);
  corrigido com limite de palavra e teste de ambiguidade; linhas de base recontadas.
- Revisão manual no corpus real revelou 6 alarmes (concordância por erro de análise,
  vírgula em vocativos de falas marcadas por hífen) e a supressão de um verbo real pela
  correção de adjetivo posposto; corrigidos com reproduções genéricas antes da rodada final.
- As versões de Echoes/Hikari com os hashes antigos não existem mais no disco.

## Validação realizada e resultado final

Registro completo em `LumeMac/Documentacao/VALIDACAO.md` (seção “Detecção generalizada”).

- `validacao`: 5/20 → 19/20 erros linguísticos (padrão do app antes → depois), alarmes 5 → 6;
  contradições 0/4 antes e depois. `desenvolvimento`: 34/35 (orientou as regras; não é medida).
- 364 testes do analisador, 25 de integração, contratos Python e Swift, build Release: aprovados.
- Motor congelado com corretor: validado após relocação, paridade exata com fontes no corpus;
  app empacotado e assinado (`Saida/deteccao-generalizada/Pacote/`).
- Echoes/Hikari (versões atuais): hash/índice preservados, nenhuma ocorrência anterior perdida,
  19 novas revistas manualmente como corretas.

Gates: A01 aprovado (hash/índice); A11 aprovado (contratos; campo aditivo `languagetool_origem`);
A12 aprovado (suítes); A13 aprovado com ressalva (versões atuais dos manuscritos, baseline 0.9.5
congelado); A14 pendente — DOM do HTML (jsdom ausente), inspeção visual nativa e avaliação
independente. Fechamento da v0.11 continua fora desta tarefa.
