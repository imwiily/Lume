# ExecPlan — Auditor Final com a API do Claude

Iniciado em 05/10/2026. Plano vivo; nenhuma etapa implementada.

## Objetivo e escopo

Implementar a quinta etapa do pipeline (`audit`, “Auditoria final”), prevista em
`docs/visao.md`: depois das quatro etapas, um modelo do Claude relê o manuscrito,
capítulo por capítulo, junto com os alertas já emitidos, e procura **somente problemas
novos** que as regras deixaram passar. O resultado também mede as etapas: muitos achados
novos indicam etapas fracas.

Comportamento observável esperado:

- Antes: a etapa aparece como “Ainda não disponível” e o relatório avisa “Auditoria editorial
  independente ainda não implementada”.
- Depois, com a opção ligada e o envio confirmado: a etapa roda, os achados novos aparecem
  na lista com o módulo “Auditoria final” e `rule=auditoria_ia`, e o relatório resume quantos
  capítulos foram enviados, quanto custou e quantos achados foram descartados (trecho
  inexistente, repetição de alerta existente, fora do escopo).
- Exemplo: um capítulo tem “Os documentos que ela trouxe estava na mesa”, e nenhuma regra
  apontou a concordância. O auditor devolve o parágrafo, o trecho exato “estava”, a categoria
  `concordancia` e a explicação. O trecho é conferido no parágrafo e vira um alerta de atenção
  editorial com confiança média.

Opcional e **desligado por padrão**, como a Coerência com IA.

Fora do escopo:

- Contradições narrativas entre capítulos. Ficam com a Coerência com IA, e o auditor não as
  procura.
- Interpretação literária, inferência psicológica, gosto, estilo e reescrita do texto
  (AGENTS.md, “Fora do escopo atual”).
- Correção automática. O auditor só cria alertas, e a correção continua sendo pedida alerta a
  alerta, como hoje.
- Mudar o número de versão, montar ou publicar a release. A 2.0 é decidida depois da medição
  (Etapa 7).
- Modelo local (Ollama) para o auditor.

Critérios de `docs/testing/acceptance-v0.11.md` comprovados: os gates de preservação
(manuscrito intacto, contratos Python e Swift, leitura de relatórios antigos). A memória
narrativa heurística descrita ali foi removida e não se aplica.

## Decisões do autor (05/10/2026)

O auditor vem desligado por padrão porque custa dinheiro.

1. **Modelo padrão:** `claude-opus-5-5` (US$ 4 de entrada / US$ 20 de saída por milhão de
   tokens; cache a US$ 0,20). O seletor do app oferece os mesmos modelos da Coerência.
2. **Teto padrão por análise:** US$ 1,00, separado do teto da Coerência.
3. **Confirmação:** uma única folha antes de enviar, com os capítulos e o custo estimado de
   cada recurso ligado (Coerência e Auditoria), e um botão que confirma os dois.
4. **Classificação:** os achados nunca são `confirmed_error`. Ficam como
   `editorial_attention`, e só a categoria de continuidade local fica como
   `possible_inconsistency`. A confiança é `média` ou `baixa`, nunca `alta`.
5. **Falha da API:** erro da API (conexão, limite de uso, recusa, teto) marca a etapa como
   `failed`, com aviso, e mantém o relatório das quatro etapas anteriores.
6. **Manuscritos A e B:** não são enviados à API por enquanto. A parte da Etapa 7 que roda o
   auditor neles fica pendente até nova autorização. As comparações de A e B sem a auditoria
   (alertas das quatro etapas idênticos) continuam valendo, porque não enviam nada.

## Estado atual observado no código

Revisão `290f439` (Lume 1.4.1 / FONTE 1.3.1). Na criação deste plano, a árvore tinha
alterações não commitadas de outra tarefa: frases reescritas, falsos positivos ao lado do
relatório e aviso de tempo contradito. Elas devem ser commitadas antes da Etapa 1.

- `fonte/fonte/pipeline.py`:
  - `STAGES` termina em `("audit", "Auditoria final")`.
  - O job da auditoria é `(False, None, "Auditor editorial independente ainda não
    implementado…")`.
  - Etapa desligada: `emit("not_implemented" if module == "audit" else "skipped")`.
  - O aviso fixo da linha ~222 anuncia a auditoria como não implementada.
  - A lista `findings` acumula os resultados das etapas anteriores e está disponível no
    fecho de `run`.
  - `standardize(..., rejected=[])` descarta ocorrências inválidas uma a uma.
- `fonte/fonte/contracts.py`: `MODULES` já inclui `audit`.
- `fonte/fonte/coerencia_ia.py`: modelo de adaptador a seguir. Ele:
  - converte blocos em parágrafos do Coerencia;
  - roda um `Projeto` incremental numa pasta do app;
  - devolve ocorrências v1 com `finding()`, IDs estáveis e avisos com o custo.
- `coerencia/coerencia/modelo.py`, classe `Claude`:
  - SDK `anthropic`, `messages.create` com saída estruturada
    (`output_config.format`, `estrito()`);
  - prompt de sistema em cache (`cache_control`) e `effort`;
  - `fallbacks="default"` com o beta `server-side-fallback-2026-07-01`;
  - tratamento de `refusal` e `max_tokens`;
  - custo por chamada (`PRECOS`) e `Orcamento` (teto antes de cada chamada);
  - chave por `ANTHROPIC_API_KEY` ou pelas Chaves do macOS (serviço `coerencia-anthropic`).
- `coerencia/coerencia/projeto.py`: `capitulos()` divide os capítulos e calcula um hash por
  capítulo. `Projeto.estimar()` estima o custo localmente, sem chamar a API, com calibração
  por caractere e por cena e uma faixa de mínimo e máximo.
- CLI (`fonte/fonte/cli.py`): `revisar … --coerencia-ia --coerencia-projeto --coerencia-modelo
  --coerencia-teto --coerencia-esforco` e `coerencia-estimar`.
- App:
  - `ReviewStore.swift`: `useCoherenceAI`, `coherenceModel`, `coherenceBudget`, o fluxo
    `.estimate` → `CoherenceEstimate` → `confirmCoherence()` → `.analyze`, e
    `coherenceProject` em Application Support.
  - `Models.swift`: o estágio inicial de `audit` é `not_implemented`.
- Contratos que hoje **exigem** a auditoria não implementada:
  - `tests/ContractCheck.swift:54`;
  - `packaging/lume_engine.py:46` (autoteste do motor);
  - `app/Lume/Models.swift:66`;
  - `docs/arquitetura.md:98`.
- Testes existentes: não há nenhum do auditor. A Coerência é testada com modelo simulado
  (`coerencia/tests`, `fonte/tests` com `Mock`). Nenhum teste chama a API.

Lacunas: não há medição das etapas contra um auditor, nem corpus com erros que as regras
não pegam, além dos 3 linguísticos que faltam em `desenvolvimento`/`validacao`.

## Arquivos afetados e preservação da arquitetura

| Caminho | Responsabilidade |
| --- | --- |
| `fonte/fonte/auditoria_ia.py` (novo) | Prompt, esquema, envio por capítulo, conferência dos trechos, descarte, conversão em ocorrências v1, projeto incremental |
| `fonte/fonte/pipeline.py` | Job real da etapa `audit`, recebendo uma cópia imutável dos alertas anteriores; estados `skipped`/`completed`/`failed`; aviso condicional |
| `fonte/fonte/cli.py` | `--auditoria-ia --auditoria-projeto --auditoria-modelo --auditoria-teto --auditoria-esforco` e `auditoria-estimar` |
| `coerencia/coerencia/modelo.py` | Reuso do cliente `Claude`, sem cópia; no máximo um parâmetro novo (ex.: `max_tokens`) |
| `packaging/lume_engine.py` | Autoteste aceita a auditoria desligada (`skipped`) |
| `app/Lume/Models.swift`, `ReviewStore.swift`, `ContentView.swift` | Opção, modelo, teto, estimativa conjunta, confirmação, progresso; estágio inicial `pending` |
| `tests/ContractCheck.swift` | Relatório novo com a auditoria `skipped` ou `completed`; relatório antigo com `not_implemented` continua lido |
| `fonte/tests/test_auditoria_ia.py` (novo) | Testes com modelo simulado |
| `docs/arquitetura.md`, `docs/validacao.md`, `README.md`, `CHANGELOG.md` | Contrato, limites, custo, evidências |

Como cada garantia é preservada:

- **Manuscrito:** o auditor lê só a captura (`Manuscript.capture`) e nunca escreve.
- **Pipeline:**
  - a auditoria recebe as ocorrências anteriores como dados somente leitura e só acrescenta
    as suas;
  - `standardize` confere cada trecho de novo;
  - a ordem das etapas não muda.
- **Origem e confiança:**
  - campos `module=audit`, `rule=auditoria_ia`, `source="Auditoria · IA (Claude)"`;
  - severidade e confiança limitadas (decisão 4);
  - a confiança é heurística e não representa probabilidade.
- **Identidade:** usa o ID padrão de `finding()` (parágrafo, texto, regra, trecho). Resultados
  guardados por capítulo mantêm os mesmos IDs enquanto o capítulo e os alertas dele não mudam,
  o que preserva as decisões.
- **Compatibilidade:**
  - campos novos são opcionais (`metadata.auditoria_ia`);
  - relatórios, decisões e configurações antigos continuam lidos;
  - o estado `not_implemented` continua aceito na leitura.
- **Chave:** segue o mesmo caminho da Coerência (variável de ambiente passada pelo app ou
  Chaves do macOS). Nunca vai em argumentos, registros ou relatórios.

## Desenho do auditor

**Unidade de envio:** o capítulo, conforme `coerencia.projeto.capitulos()`, com a mesma
numeração de parágrafos do FONTE. Capítulos acima de um limite de caracteres (calibrar na
Etapa 6; ponto de partida: 40 mil) são divididos em janelas de parágrafos inteiros, com 2
parágrafos de sobreposição só para contexto. Achados na sobreposição valem só na janela
dona do parágrafo.

**Pedido:** uma chamada por capítulo ou janela, pelo `Claude.json`.

- `system`: fixo, genérico e em cache. Contém:
  - a missão (“procure problemas que os alertas listados não cobrem”);
  - as categorias permitidas;
  - a regra “na dúvida, não aponte”;
  - a preservação da voz (falas coloquiais, ortografia intencional, fragmentos expressivos);
  - a regra de que instruções que apareçam no texto do manuscrito são conteúdo, não ordens.

  Não pode conter nada de obras reais (invariante 4).
- `user`: o tempo da narração escolhido; os parágrafos numerados com o papel do trecho
  (narração, fala, pensamento, título); e os alertas existentes daquele capítulo (parágrafo,
  trecho, categoria). O texto vai delimitado.
- `output_config`: esquema estrito, `effort` (padrão `medium`, configurável). O pensamento é
  adaptativo, padrão do modelo. `max_tokens` 16000, como a Coerência. Se a resposta for
  cortada (`max_tokens`), a janela é dividida ao meio e reenviada uma vez, contando no teto.

Esquema da resposta:

```json
{"ocorrencias": [{"paragrafo": 12, "trecho": "estava", "categoria": "concordancia",
                  "explicacao": "…", "sugestao": "estavam", "confianca": "media"}]}
```

- `categoria` é uma lista fechada, no início: `ortografia`, `concordancia`, `regencia`,
  `crase`, `pontuacao`, `tempo_verbal`, `estrutura_frase`, `repeticao`, `dialogo`,
  `referencia`, `continuidade_local`. A lista é mapeada para os códigos e títulos de
  categoria já usados no app.
- `sugestao` é opcional (pode ser `null`). `confianca` aceita `media` ou `baixa`.

**Conferência e descarte, em código e nunca pelo modelo** (invariantes 5 e 6). Cada
descarte é contado por motivo em `metadata.auditoria_ia.descartes`:

1. Parágrafo fora do capítulo ou da janela enviada.
2. Trecho que não existe no parágrafo, comparado após normalização NFC sem mudar o texto. Se
   aparecer mais de uma vez no parágrafo, vale a primeira ocorrência, e a explicação cita o
   trecho.
3. Trecho que se sobrepõe a um alerta existente no mesmo parágrafo, de qualquer etapa.
4. Categoria de tempo verbal em fala ou pensamento fora de `tense_scopes`; categorias
   desligadas na configuração da busca.
5. Repetição dentro da própria resposta (mesmo parágrafo e trecho).

**Projeto incremental:**

- Pasta `~/Library/Application Support/FONTE/Auditoria/<livro>/`, como a da Coerência.
- Para cada capítulo ou janela, guarda o hash de: texto, alertas anteriores daquele trecho,
  modelo, esforço, versão do prompt e configuração relevante. A resposta bruta já conferida
  também é guardada.
- Trecho com o mesmo hash não é reenviado: os achados guardados são reaproveitados
  (invariante 7, “enviar só o que mudou”).
- Ao atingir o teto, o que já foi auditado fica salvo, e o restante entra na próxima análise.

**Estimativa** (`auditoria-estimar`): local, sem rede, como `Projeto.estimar`.

- Devolve os capítulos a enviar, os caracteres e o custo estimado com faixa.
- Não pode usar `count_tokens`, porque isso enviaria o texto à Anthropic antes da
  confirmação.
- A calibração inicial vem das chamadas reais da Etapa 5 e é registrada no código com a data.

**Progresso:** `LUME_PROGRESS` com `done`/`total`/`unit="capítulos"`, pelo `avancar` já
usado na Coerência.

**Metadados:** `metadata.auditoria_ia` registra:

- modelo e esforço;
- capítulos totais, enviados e reaproveitados;
- custo em US$;
- achados novos por categoria;
- descartes por motivo;
- se a rodada foi interrompida pelo teto.

A medição prevista na visão (“Módulos: 182 / Auditor: 27 novos”) sai daí.

## Etapas incrementais

### Etapa 0 — Decisões e base

- **Comportamento:** nenhum.
- **Trabalho:** registrar neste plano as respostas às seis decisões e commitar as alterações
  locais anteriores.
- **Encerramento:** decisões anotadas; `git status` limpo, exceto
  `sugestoes-de-melhorias.md`.

### Etapa 1 — Contrato e esqueleto da etapa

- **Comportamento:** com a auditoria desligada, a etapa sai `skipped` (não mais
  `not_implemented`) e o aviso fixo desaparece. Com um auditor simulado, a etapa roda depois
  das outras quatro e recebe os alertas delas.
- **Testes primeiro** (falham antes):
  - estado `skipped`;
  - aviso ausente;
  - o auditor simulado recebe exatamente os alertas anteriores e não consegue alterá-los
    (cópia);
  - relatório antigo com `not_implemented` continua lido no Swift (`ContractCheck`) e no
    Python;
  - autoteste do motor ajustado.
- **Mudança:** `pipeline.py`, `Models.swift`, `ContractCheck.swift`, `lume_engine.py`,
  `docs/arquitetura.md`.
- **Encerramento:** as suítes do FONTE, de integração e do Coerencia e o contrato Swift
  passam. A comparação de alertas em A e B fica idêntica, porque nenhuma regra muda.

### Etapa 2 — Núcleo do auditor com modelo simulado

- **Comportamento:** `auditoria_ia.auditar(blocks, anteriores, cliente, …)` devolve
  ocorrências v1 conferidas.
- **Testes** (modelo simulado que devolve JSON fixo):
  - positivos: trecho existente vira alerta com módulo, regra, severidade, confiança e
    intervalo corretos;
  - negativos (cada motivo de descarte), cada um com contagem;
  - ambiguidade: trecho repetido no parágrafo;
  - Unicode: emoji e acentos combinados, com offsets em pontos de código;
  - substituição de nomes e objetos nos textos de teste (invariante 4);
  - o prompt montado não contém regras de obras e inclui os alertas existentes do capítulo;
  - resposta cortada leva à divisão da janela;
  - `refusal` vira aviso e o capítulo fica para depois, sem quebrar a etapa.
- **Encerramento:** testes novos passam, e as suítes continuam verdes.

### Etapa 3 — Projeto incremental, teto e estimativa

- **Comportamento:**
  - a segunda análise sem mudanças não chama o cliente e devolve os mesmos IDs;
  - mudar um capítulo ou um alerta dele reenvia só aquele trecho;
  - o teto interrompe antes da próxima chamada, e a próxima análise continua de onde parou;
  - `auditoria-estimar` não abre conexão (o teste falha se o cliente for criado).
- **Testes:** os quatro comportamentos acima, mais a chave ausente dos argumentos, do
  registro e do relatório.
- **Mudança:** `auditoria_ia.py` e `cli.py`.
- **Encerramento:** testes passam; o comando de estimativa roda em A e B localmente, sem
  rede, e o resultado é anotado neste plano.

### Etapa 4 — App

- **Comportamento:**
  - opção “Auditoria final com IA (Claude)”, desligada por padrão, com modelo, teto e
    esforço, na mesma seção da Coerência;
  - a estimativa conjunta aparece numa folha antes de qualquer envio, conforme a decisão 3 (uma folha para os dois recursos);
  - progresso por capítulos;
  - os alertas da auditoria aparecem filtráveis pelo módulo;
  - os avisos de custo ficam em “Sobre esta análise”.
- **Testes:** contrato Swift com `metadata.auditoria_ia` presente e ausente; build
  `xcodebuild`.
- **Inspeção visual nativa** obrigatória: folha de confirmação, progresso e alerta da
  auditoria. A compilação sozinha não basta.
- **Encerramento:** build sem erros e inspeção registrada.

### Etapa 5 — Ponta a ponta com a API, em texto curto

- **Requer autorização e custo informado:** alguns centavos.
- **Comportamento:** um texto sintético de 2 capítulos (escrito do zero, com erros
  plantados e controles) passa pelo motor com a API real.
- **Evidências registradas:**
  - custo por chamada;
  - tokens de entrada, saída e cache (`cache_read_input_tokens` > 0 na segunda chamada);
  - achados, descartes e tempo.
- **Uso dos números:** calibram a estimativa da Etapa 3.
- **Encerramento:** sem erro de contrato. Os trechos citados existem, e a segunda rodada
  não chama a API.

### Etapa 6 — Medição no corpus

- **Requer autorização;** custo estimado antes de rodar.
- **Corpus:** `fonte/tests/corpus/deteccao/` ganha a categoria `auditoria` em
  `scripts/avaliar_deteccao.py`. A medição separa:
  1. erros anotados que as regras perdem e o auditor encontra;
  2. achados em trechos aceitáveis;
  3. alarmes falsos;
  4. achados que repetem alertas, que devem dar zero depois do descarte.
- **Textos novos:** escritos do zero, com classes que as regras não cobrem (concordância
  distante, regência rara, continuidade local dentro da cena) e controles de voz (fala
  coloquial, fragmentos intencionais).
- **Ajuste do prompt:** só com o conjunto `desenvolvimento`. A `validacao` é medida uma vez,
  no fim, sem retoque posterior.
- **Encerramento:** números registrados em `docs/validacao.md`, com denominadores. Sem meta
  de precisão prometida; a decisão sobre a 2.0 usa esses números.

### Etapa 7 — Manuscritos reais, documentação e montagem

- **Rodar o auditor em A e B está suspenso pela decisão 6.** Até nova autorização, esta etapa faz só a documentação, a montagem e a comparação de A e B sem a auditoria.
- **Execução, quando autorizada:** cópias de A e B no scratchpad, com a configuração usada pelo autor, rodadas
  com a auditoria ligada.
- **Registro:**
  - os alertas das quatro etapas antes e depois (devem ficar idênticos);
  - os achados novos do auditor;
  - os descartes;
  - o custo;
  - a segunda rodada, sem custo.
- **Revisão:** os achados de A e B são revistos pelo autor no app, com as decisões; os
  falsos positivos alimentam o prompt pelo fluxo de `lume-fluxo-relatorios`, sempre como
  classe genérica.
- **Documentação:** `README.md`, `docs/arquitetura.md`, `CHANGELOG.md` e
  `docs/validacao.md`.
- **Montagem:** `scripts/montar-lume.command` (regressões, contratos Swift, diagnóstico do
  motor com o auditor embutido).
- **Encerramento:** montagem aprovada e varredura de coincidências com A e B antes de
  qualquer push. A release fica à parte, por decisão do autor.

## Testes, critérios de aceitação e riscos

| Risco | Controle | Teste |
| --- | --- | --- |
| Trecho inventado pelo modelo | Conferência no parágrafo, descarte contado | Etapa 2, negativos 1–2 |
| Repetir alerta existente com outro recorte | Descarte por sobreposição no parágrafo | Etapa 2, negativo 3 |
| Apagar ou alterar alertas anteriores | Cópia somente leitura; contagem das quatro etapas igual antes e depois | Etapas 1 e 7 |
| Suspeita apresentada como erro | Severidade e confiança limitadas (decisão 4) | Etapa 2, positivos |
| Corrigir a voz do autor (falas, coloquialismo) | Prompt, filtro por papel do trecho, controles no corpus | Etapas 2 e 6 |
| Regra ou prompt dependente de obra real | Prompt genérico revisado; textos de teste novos; varredura de coincidências | Etapas 2, 6 e 7 |
| Gasto acima do esperado | Estimativa local, confirmação, teto antes de cada chamada, reaproveitamento | Etapa 3 |
| Envio sem consentimento | Nada sai sem a confirmação do app ou a opção explícita no terminal; a estimativa não usa rede | Etapa 3 |
| Chave exposta | Variável de ambiente ou Chaves do macOS; ausente de argumentos, registro e relatório | Etapa 3 |
| Resultados diferentes a cada rodada | Achados guardados por hash; IDs estáveis | Etapa 3 |
| Falha da API derrubando a análise | Etapa `failed` com aviso; relatório mantido (decisão 5) | Etapas 1–2 |
| Instruções embutidas no texto do manuscrito | Texto delimitado, regra explícita no sistema, saída por esquema estrito | Etapa 2 |
| Relatório antigo ilegível | `not_implemented` aceito; campos novos opcionais | Etapa 1 |

Para distinguir falha de ambiente:

- sem chave, sem rede ou sem o pacote `coerencia`, a mensagem diz isso e a etapa não roda;
- testes simulados nunca dependem de rede;
- se faltar o LanguageTool nas comparações, isso é registrado como pendência e não é
  confundido com resultado do auditor.

## Comandos e evidências

Executar a partir da raiz.

```bash
(cd fonte && .venv/bin/python -m unittest discover -s tests)
PYTHONPATH=fonte fonte/.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
(cd coerencia && ../fonte/.venv/bin/python -m unittest discover -s tests)
swiftc app/Lume/Models.swift app/Lume/PythonRunner.swift tests/ContractCheck.swift -o build/<saida>/contrato-swift
build/<saida>/contrato-swift examples/Mestre/relatorio.json fonte/.venv/bin/python
fonte/.venv/bin/python scripts/avaliar_deteccao.py --conjunto desenvolvimento --languagetool --saida build/<saida>
# Estimativa local, sem rede:
cd fonte && .venv/bin/python -m fonte auditoria-estimar <copia.pages> --auditoria-projeto <pasta>
# Com API, só com autorização:
cd fonte && .venv/bin/python -m fonte revisar <copia.pages> --saida <nova> --tempo passado \
  --auditoria-ia --auditoria-projeto <pasta> --auditoria-modelo <modelo> --auditoria-teto <US$>
```

- Saídas e logs ficam em `build/<tarefa>/` ou no scratchpad. Manuscritos reais nunca entram
  em fixtures versionadas.
- Para cada rodada com API: modelo, esforço, versão do prompt, hash do manuscrito, custo e
  tokens.

## Progresso, descobertas e decisões

- [x] Etapa 0 — decisões e base (05/10; commits `e39844a` e `72f5fec`)
- [x] Etapa 1 — contrato e esqueleto (05/10)
- [ ] Etapa 2 — núcleo com modelo simulado
- [ ] Etapa 3 — incremental, teto e estimativa
- [ ] Etapa 4 — app
- [ ] Etapa 5 — ponta a ponta com a API (autorização)
- [ ] Etapa 6 — medição no corpus (autorização)
- [ ] Etapa 7 — manuscritos, documentação e montagem (autorização)

05/10/2026: plano criado a partir do código em `290f439` mais as alterações locais da
tarefa anterior. O cliente `Claude` da Coerência cobre saída estruturada, cache, recusa e
teto. O auditor o reaproveita em vez de criar outro cliente.

05/10/2026, Etapa 1:

- `pipeline.run(..., auditoria=None)` chama `fonte.auditoria_ia.auditar(blocks, cópia dos
  alertas, avancar, **opções)`. O módulo ainda é um esqueleto que recusa rodar; o núcleo vem
  na Etapa 2.
- A etapa desligada sai `skipped`, com cobertura `partial`. O aviso “Auditoria editorial
  independente ainda não implementada” saiu; ficou só a ressalva de que etapa concluída não
  significa cobertura completa.
- Decisão 5 implementada: exceção comum na auditoria marca a etapa como `failed`, remove o
  que ela tinha acrescentado e mantém o relatório. `KeyboardInterrupt` e afins continuam
  interrompendo a análise.
- Expectativas mudadas de propósito: `test_pipeline.py` (2 lugares), `ContractCheck.swift`,
  `packaging/lume_engine.py` e `Models.swift` (estágio inicial `pending`). O contrato Swift
  continua aceitando `not_implemented` de relatórios antigos.

## Validação realizada e resultado final

Etapa 1 (05/10/2026):

- 312 testes do analisador (5 novos em `test_auditoria_ia.py`; 4 falhavam antes da mudança),
  25 dos pacotes e do contrato Python e 24 do Coerencia aprovados.
- Contrato Swift aprovado com o relatório antigo (`examples/Mestre`, `not_implemented`) e com
  um relatório novo (`skipped`). Autoteste do motor (`--lume-probe`) saudável. `xcodebuild`
  Debug sem erros.
- Manuscritos A e B com Passado e LanguageTool, sem a auditoria (nada enviado): A 45 → 45,
  B 17 → 17, mesmos identificadores.
- Nenhuma chamada à API.
