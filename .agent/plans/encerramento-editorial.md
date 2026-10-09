# Encerramento editorial: poucos alertas, alta confiança, ponto de fim claro

Pedido do autor em 07/10/2026. O plano muda a definição de sucesso do Lume, de “máxima cobertura”
para “interromper o editor só quando há boa razão, e deixar o manuscrito chegar ao fim”.
**Regra durante toda a reestruturação: nenhuma regra nova de detecção.** Ajustes pontuais para
exemplos já discutidos também ficam de fora.

## Objetivo e escopo

Comportamento esperado ao final:

- Cada ocorrência tem um **destino**:
  - `diagnostico`: fora da mesa, serve à melhoria do motor;
  - `informacao`: observação recolhida, sem contar como pendência;
  - `pendencia`: entra na fila e pede decisão.
- Uma pendência pode ser também **impeditiva** (`impeditivo: true`).
- **Revisão concluída:** o editor escolhe **Encerrar revisão** quando nenhum impeditivo está sem
  decisão. O encerramento registra:
  - observações ainda abertas;
  - data;
  - versão do motor;
  - versão da política.

  O estado final se chama “Revisão concluída”, nunca “texto sem erros” ou “revisão perfeita”.
- **A Auditoria final passa a ser controle de qualidade do Lume:**
  - confiança baixa vai para diagnóstico;
  - nada da Auditoria é impeditivo.
- **Métricas:** a métrica principal passa a ser a precisão das pendências, medida pelas decisões
  reais. Os acertos no corpus sintético viram guarda contra regressão, não meta.

Exemplo antes/depois (manuscrito A, relatório de 07/10/2026, 63 ocorrências):

| | Hoje | Depois |
|---|---|---|
| Mesa | 63 pendências, “0 de 63 avaliados” | só as pendências; observações recolhidas |
| Repetição próxima de confiança baixa (17% de erro real) | conta como pendência | vai para informação |
| Encerramento | não existe | “Encerrar revisão” quando os impeditivos estiverem decididos |

Fora do escopo:
- regras novas;
- aumento de cobertura;
- correção de casos individuais;
- mudança do prompt da Auditoria (mudar `VERSAO_PROMPT` reenviaria capítulos e custaria dinheiro);
- calibração estatística formal da confiança;
- uso das decisões de um livro para silenciar alertas de outro.

Critérios de `docs/testing/acceptance-v0.11.md` que continuam valendo:
- preservação do manuscrito;
- contratos Python e Swift com relatórios antigos e atuais;
- comparação antes/depois nos manuscritos A e B.

## Decisões do autor (07/10/2026)

1. **`tratamento` sai da detecção ativa.**
   - Não fica nem como informação.
   - A chave passa a regra retirada, para que configurações salvas com ela continuem abrindo.
   - O registro histórico fica no CHANGELOG e em `dois-planos-e-tratamento.md`.
2. **Uma classe só é impeditiva se cumprir três condições:**
   - **(a)** precisão real **≥ 90%**, com **≥ 20 decisões reais** (sem repetição entre versões do
     mesmo livro);
   - **(b)** natureza **objetiva e determinável**;
   - **(c)** severidade `confirmed_error` ou `probable_error`.

   Precisão alta sozinha nunca torna uma classe impeditiva. Classes editoriais, narrativas, de
   repetição, referência, estilo ou continuidade interpretativa nunca são impeditivas.
3. **É permitido encerrar com observações e pendências não impeditivas abertas,** desde que isso
   seja uma escolha explícita (**Encerrar revisão**) e fique registrado. Nenhum impeditivo pode
   estar sem decisão.

Decisão desta proposta, conservadora, que o autor pode rever:
- O **tempo verbal da narração** é tratado como de natureza **editorial**, não objetiva. A escolha
  do tempo é do autor, e há planos legítimos (comentário do narrador, verdade geral). Por isso não é
  impeditivo, apesar dos 90% medidos.

## Estado atual observado no código

Revisão `05d4123`, branch `organizacao-e-deteccao`, árvore limpa (exceto `sugestoes-de-melhorias.md`).

- `fonte/fonte/contracts.py`, `standardize`/`occurrence`:
  - toda ocorrência recebe `severity` e `confidence_score`;
  - o LanguageTool vira sempre `probable_error`, mesmo com confiança baixa;
  - não há campo de destino.
- `fonte/fonte/pipeline.py`:
  - tudo o que as etapas produzem entra em `findings`, sem filtro;
  - `meta.confidence_semantics = "rule_strength_not_calibrated_probability"`.
- `fonte/fonte/auditoria_ia.py`:
  - o esquema pede `"media"` ou `"baixa"`;
  - `CONFIANCA["baixa"] = ("baixa", .4)` vira ocorrência normal;
  - o estado fica em `Auditoria/<livro>/auditoria.json`.
- `fonte/fonte/settings.py` (`RETIRED_RULES`) e `app/Lume/Models.swift` (`SearchRule.retiredIDs`):
  é o mecanismo de retirada de regras.
- `app/Lume/ReviewStore.swift`:
  - `pendingCount` conta todo alerta sem decisão;
  - `filteredFindings` começa em “Todas”;
  - a correção no Pages grava `.error` (“Erro confirmado”).
- `app/Lume/ContentView.swift`: “Mesa de leitura · X de Y avaliados”.
- `app/Lume/Models.swift`:
  - `ReviewDecision`: Pendente, Erro confirmado, Estilo do autor, Falso positivo, Intencional,
    Aceito editorialmente;
  - `BookMemory`: decisões por livro, por conteúdo.
- Decisões em `~/Library/Application Support/FONTE/Decisoes/<sha256>.json`
  (`{schema_version, document, sha256, decisions: {id: valor}}`).
- `scripts/avaliar_deteccao.py`: o resultado principal é “Total linguística N/M”; alarmes falsos e
  proporção sobre erros anotados vêm em segundo plano.

Medição exploratória das decisões reais (07/10/2026), com 491 decisões únicas:

| Classe · confiança | Decisões | Era erro |
|---|---:|---:|
| Tempo verbal · média | 291 | 90% |
| Diálogo contextual · baixa | 23 | 87% |
| Palavra repetida próxima · baixa | 35 | 17% |
| Estrutura · baixa | 11 | 18% |
| LanguageTool ortografia · alta | 9 | 33% |

Conclusão: o rótulo de confiança não está calibrado e não serve sozinho para decidir o destino.

## Definições

- **Ocorrência:** tudo o que uma etapa detectou e passou pela conferência de trecho.
- **Destino:**
  - `diagnostico`: não vai para `findings`. Fica numa lista própria do relatório, que o app só
    mostra no modo de diagnóstico.
  - `informacao`: aparece recolhida. Não conta e não pede decisão.
  - `pendencia`: entra na fila e conta como pendência.
- **Impeditivo:** pendência que satisfaz a decisão 2 na política vigente.
- **Resolvida:** qualquer decisão diferente de Pendente.
- **Política:** `fonte/fonte/politica.json`, versionada (`versao`), com uma entrada por classe:

  ```json
  {"regra": "...", "confianca": "media", "natureza": "objetiva|editorial",
   "destino": "pendencia", "impeditivo": false,
   "precisao": 0.9, "decisoes": 120, "medido_em": "2026-10-08"}
  ```

  Classe sem medição suficiente:
  - com confiança baixa → `informacao`;
  - nos demais casos → `pendencia` não impeditiva.

  Uma classe nova entra como `informacao` ou `diagnostico`. Ela só sobe com medição em livros reais.

## Arquivos afetados e preservação da arquitetura

| Etapa | Arquivos |
|---|---|
| 1 | `docs/visao.md`, `AGENTS.md`, `docs/arquitetura.md`, `docs/validacao.md`, `README.md` |
| 2 | `scripts/medir_precisao.py` (novo; lê só dados locais e grava em `build/`), `scripts/avaliar_deteccao.py` (resumo com precisão em primeiro lugar) |
| 3 | `fonte/fonte/politica.json` e `fonte/fonte/politica.py` (novos), `contracts.py`, `pipeline.py`, `settings.py`, `grammar.py` (retirar `tratamento`), testes |
| 4 | `fonte/fonte/auditoria_ia.py` (só o encaminhamento; o prompt não muda) |
| 5 | `app/Lume/Models.swift`, `ReviewStore.swift`, `ContentView.swift`, `ManuscriptView.swift`, `tests/ContractCheck.swift`, `tests/ClosureCheck.swift` (novo) |

O que é preservado:
- **Manuscrito e índices:** a política só classifica. Não muda trechos, offsets nem IDs, então as
  decisões antigas continuam valendo.
- **Pipeline:** a política é aplicada depois das etapas, que não se reescrevem.
- **Contrato:** `destino`, `impeditivo`, `politica_versao` e a lista `diagnostico` só se somam aos
  campos atuais.
- **Relatórios antigos (sem `destino`):** o app os lê como `pendencia` não impeditiva. É o
  comportamento de hoje, sem reproduzir heurística no Swift.
- **Decisões antigas:** abrem como antes. “Corrigido” é um valor novo, e os antigos não mudam.
- **Configurações com `tratamento`:** continuam válidas, como regra retirada.
- **Swift:** cuida de contagem, filtros, decisões e encerramento. O Python decide destino e
  impedimento (invariante 3).

## Etapas incrementais

### Etapa 1 — Documentação (definição de sucesso)

Mudanças:
- **`docs/visao.md`:**
  - nova frase central;
  - reescrever “Filosofia de cobertura” (precisão antes de cobertura irrestrita);
  - Auditor como controle de qualidade;
  - falsos negativos passam pela pergunta da classe;
  - destino e encerramento editorial;
  - “Adicionar exceção” sai da lista de decisões propostas.
- **`AGENTS.md`:**
  - a invariante 5 perde a saída “alertar como suspeita” como padrão;
  - princípio novo: antes de qualquer regra, perguntar se a classe é generalizável, relevante e
    detectável com boa precisão (se não for, o erro fica fora da cobertura, e isso é delimitação,
    não fracasso);
  - o corpus deixa de crescer por caso isolado;
  - a regressão de precisão exige justificativa;
  - nenhuma classe nova entra como pendência sem medição.
- **`docs/arquitetura.md`:** seção de destino, impedimento, política e encerramento; novo papel da
  Auditoria.
- **`docs/validacao.md`:** novo protocolo de métricas no topo, mantendo os registros antigos.
- **`README.md`:** descrição da Auditoria e da avaliação.

Encerramento da etapa: revisão por inspeção (caminhos, consistência, diff), sem código.

### Etapa 2 — Medição de precisão a partir das decisões reais

Mudanças:
- `scripts/medir_precisao.py`:
  - lê `Relatorios/*/relatorio.json` e `Decisoes/*.json`;
  - remove a repetição de cada alerta entre versões do mesmo livro;
  - agrega por classe (regra ou categoria × confiança).
- Saída em `build/precisao-<data>/`: só números, sem trechos.
  - Por classe: decisões, % erro, % falso positivo, % estilo, % intencional, % aceito, % corrigido.
  - Ocorrências e pendências por 10 mil palavras.
- `scripts/avaliar_deteccao.py`: o resumo passa a mostrar primeiro a precisão das ocorrências (sobre
  erros anotados ÷ ocorrências fora dos trechos aceitáveis) e alarmes falsos por 10 mil palavras;
  depois, os acertos.

Testes:
- testes do script com decisões fictícias em pasta temporária: remoção de repetições, denominadores,
  ausência de trechos na saída.

Encerramento da etapa: tabela medida registrada aqui, sem trechos, e proposta de `politica.json` v1.

### Etapa 3 — Política e contrato

Mudanças:
- `politica.json` v1 a partir da Etapa 2, aplicando as decisões 1 e 2.
- `politica.py`: `destino(ocorrencia)` e `impeditivo(ocorrencia)`; versão em `meta.politica_versao`.
- `pipeline.py`: aplica a política depois da padronização; `diagnostico` vai para
  `meta.diagnostico` ou para o nível superior do relatório; `findings` fica só com
  `pendencia` e `informacao`.
- `contracts.py`: valida `destino` e `impeditivo`; um impeditivo exige severidade
  `confirmed_error` ou `probable_error`.
- Retirar `tratamento`:
  - remover a regra de `grammar.py` e `GRAMMAR_RULES`;
  - incluir a chave em `RETIRED_RULES` e em `retiredIDs`;
  - os testes de `test_tratamento.py` passam a verificar que a regra é aceita e não tem efeito;
  - o caso do corpus é anotado como fora do escopo.

Testes:
- uma classe com 95% e natureza editorial não é impeditiva;
- uma classe com 89% e natureza objetiva não é impeditiva;
- uma classe com 95% e 19 decisões não é impeditiva;
- uma classe sem medição e de confiança baixa vai para informação;
- relatório antigo sem `destino` passa pelo contrato;
- IDs inalterados;
- configuração com `tratamento: true` é aceita e não gera alerta.

Encerramento da etapa: comparação antes/depois em A, B, C e no texto de terceiros, por destino.
Os mesmos IDs devem aparecer; só os destinos mudam.

### Etapa 4 — Auditoria final

Mudanças:
- Confiança baixa → `diagnostico`.
- Confiança média em ortografia, concordância, crase ou regência → `pendencia`, nunca impeditiva.
- Demais categorias → `informacao`.
- O prompt e `VERSAO_PROMPT` **não mudam**: nada é reenviado e não há custo.
- Métrica da Auditoria: achados promovidos e quantos deles foram confirmados como erro real (pela
  Etapa 2).

Testes: com modelo simulado, nenhuma chamada à API.

### Etapa 5 — App

Mudanças:
- `Finding`: `destino` e `impeditivo` opcionais.
- Contagens: “N pendências · M impeditivas”, no lugar de “X de Y avaliados”.
- Filtro inicial “Pendências”.
- Observações numa seção recolhida; diagnóstico só no modo de diagnóstico.
- Decisão nova **Corrigido**, gravada pela correção no Pages, no lugar de “Erro confirmado”.
- **Encerrar revisão:**
  - habilitado só com zero impeditivos sem decisão;
  - grava `Encerramentos/<sha256>.json` com observações e pendências abertas, data, versão do
    motor e versão da política;
  - mostra o selo “Revisão concluída”.
- Uma reanálise do mesmo texto com a mesma política mantém o encerramento.
- Texto ou política novos mostram o encerramento anterior como histórico.
- Limpar resíduos preserva `Encerramentos/`.

Testes:
- `ClosureCheck.swift`:
  - impeditivo pendente bloqueia o encerramento;
  - observações abertas não bloqueiam;
  - registro com os quatro campos;
  - relatório antigo funciona.
- `ContractCheck.swift` com relatório antigo e novo.
- Build.
- **Inspeção visual nativa pelo autor** (exigida para mudanças visuais).

## Testes, critérios de aceitação e riscos

Critérios de aceitação:
- Nenhuma regra nova.
- IDs e decisões preservados.
- Relatórios e configurações antigos abrem.
- Nenhum impeditivo fora da decisão 2.
- O encerramento é impossível com impeditivo pendente.
- Os textos dizem “Revisão concluída”, nunca “sem erros”.

Riscos e mitigação:

| Risco | Mitigação |
|---|---|
| Dados de decisão de um único autor e poucos livros, com classes de n pequeno | Mínimo de 20 decisões; classe sem dados não é impeditiva |
| “Erro confirmado” hoje mistura correção feita com erro reconhecido | “Corrigido” separa daqui em diante; a medição soma os dois como erro real |
| Política desatualizada | Versão no relatório e no encerramento; nova medição a cada release |
| Esconder erro real em `informacao` | Continua visível ao abrir a seção; a precisão da classe justifica o rebaixamento |

## Comandos e evidências

Na raiz Git:

```sh
fonte/.venv/bin/python scripts/medir_precisao.py --saida build/precisao-<data>   # Etapa 2
(cd fonte && .venv/bin/python -m unittest discover -s tests)
PYTHONPATH=fonte fonte/.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
PYTHONPATH=fonte fonte/.venv/bin/python tests/check_python_contract.py
(cd coerencia && ../fonte/.venv/bin/python -m unittest discover -s tests)
fonte/.venv/bin/python scripts/avaliar_deteccao.py --conjunto todos --saida build/avaliacao-<data>
```

As verificações Swift seguem os cabeçalhos de `tests/*.swift`. A comparação nos manuscritos usa
cópias no scratchpad, nunca os originais.

## Progresso, descobertas e decisões

- [x] 07/10: diagnóstico e proposta aprovados; decisões do autor registradas acima.
- [x] Etapa 1 — documentação (07/10). `docs/visao.md`: frase central, “Ocorrência, pendência e
  encerramento”, “Revisão concluída”, Auditor como controle de qualidade, falsos negativos com a
  pergunta da classe, “Precisão antes de cobertura irrestrita”, decisões sem “Adicionar exceção”.
  `AGENTS.md`: invariante 5 sem a saída “alertar como suspeita”, invariante 9 (encerramento e
  critério de impeditivo), pergunta da classe antes de qualquer regra, classe nova entra como
  informação, regressão de precisão. `docs/arquitetura.md`: seção de destino e encerramento “em
  implantação” e papel da Auditoria. `docs/validacao.md`: protocolo de métricas no topo. `README.md`:
  Auditoria e avaliação. As listas de regras ainda citam `tratamento` até a Etapa 3.
- [x] Etapa 2 — medição de precisão (07/10).
  - `scripts/medir_precisao.py` e `tests/test_medir_precisao.py`: remoção de repetições entre
    versões, desfechos, limiar, LanguageTool separado em ortografia e gramática, saída sem trechos
    nem nomes.
  - `scripts/avaliar_deteccao.py`: precisão e alarmes falsos por 10 mil palavras no topo do resumo.
  - Medição real (`build/precisao-20261007/`): 650 decisões únicas, 6 livros, precisão total 79%.
  - Corpus `todos`: precisão das ocorrências 88%, alarmes falsos por 10 mil palavras 22,6,
    linguística 66/85 (sem mudança de detecção).

  | Classe · confiança | Decisões | Erro real | Natureza proposta |
  |---|---:|---:|---|
  | narrative_tense · média | 408 | 91% | editorial |
  | palavra_proxima · baixa | 43 | 23% | editorial |
  | dialogo_contextual · baixa | 32 | 91% | editorial |
  | languagetool:gramatica · média | 30 | 60% | objetiva |
  | sentence_structure · média | 18 | 39% | editorial |
  | languagetool:ortografia · alta | 13 | 31% | objetiva |
  | pontuacao_duplicada · alta | 12 | 92% | objetiva |
  | sentence_structure · baixa | 10 | 10% | editorial |
  | narrative_tense · baixa | 8 | 0% | editorial |

  **Descoberta:** com as regras do autor, **nenhuma classe é impeditiva hoje**. As duas que passam
  do limiar numérico são editoriais. A objetiva mais próxima (pontuação duplicada, 92%) tem só 12
  decisões. Com a política v1, “Encerrar revisão” nunca é bloqueado até que uma classe objetiva
  acumule ≥ 20 decisões com ≥ 90%.

  Proposta de política v1, a confirmar com o autor antes da Etapa 3:
  - **Natureza objetiva:** crase, homófonos, concordância, pontuação duplicada, espaçamento,
    construção inválida, quê tônico, acentuação contextual, vírgula em “que, não” e LanguageTool
    (ortografia e gramática). Todas as demais são editoriais.
  - **Destino `informacao`:**
    - classe medida (≥ 20 decisões) com precisão < 50%: hoje, `palavra_proxima` baixa (23%);
    - classe sem medição e de confiança baixa: `sentence_structure` baixa (10% em 10),
      `narrative_tense` baixa (0% em 8), `gerundismo`, `incomplete_subordinate_clause`,
      `coerencia_temporal` baixa e as demais de confiança baixa.
  - **Exceção pelos dados:** `dialogo_contextual` baixa (91% em 32) fica `pendencia`, porque o
    rótulo baixo não corresponde ao resultado medido.
  - **Destino `pendencia`, não impeditiva:** todas as demais.
  - **Atenção sem mudança de destino:** `languagetool:ortografia` alta (31% em 13) e
    `sentence_structure` média (39% em 18) continuam pendência por falta de 20 decisões; ficam
    marcadas para a próxima medição.
- [x] Etapa 3 — política, contrato e retirada de `tratamento` (07/10).
  - Ajustes do autor à política v1:
    - o limiar de observação é um critério de não-interrupção, não de qualidade;
    - `confidence` é evidência auxiliar e os dados prevalecem;
    - pendência não afirma que a regra é confiável;
    - o LanguageTool de ortografia (31% em 13) continua pendência até ter amostra.
  - Código:
    - `fonte/fonte/data/politica.json` (v1, princípios escritos no arquivo);
    - `fonte/fonte/politica.py`;
    - `contracts.check_destination`;
    - a pipeline aplica a política no fim (`metadata.politica_versao`, `destinos`, `impeditivos`,
      `diagnostico`);
    - a CLI informa pendências, impeditivas e observações.
  - A exceção do diálogo contextual sai sozinha da regra “com 20 decisões, os dados decidem”, sem
    entrada especial.
  - `tratamento`:
    - removida de `grammar.py`;
    - em `RETIRED_RULES` e `retiredIDs`;
    - `test_tratamento.py` agora confere que a chave é aceita sem efeito;
    - a anotação do corpus foi retirada, com nota.
  - Testes: `fonte/tests/test_politica.py` (10). FONTE 415, pacotes 35, Coerencia 25, contrato
    Python, contrato Swift (relatório novo e `examples/Mestre` antigo), mesa, falsos positivos,
    decisões por livro, build Debug.
  - Manuscritos, mesmos IDs antes e depois:

    | Texto | Pendências | Observações | Impeditivos |
    |---|---:|---:|---:|
    | A | 37 | 26 | 0 |
    | B | 2 | 13 | 0 |
    | C | 18 | 11 | 0 |
    | Texto de terceiros | 13 | 26 | 0 |

    Observações: repetição próxima, tempo verbal baixo, estrutura baixa, gerundismo e subordinada
    isolada.
  - Corpus `todos`:
    - precisão das pendências 97% (alarmes falsos na fila por 10 mil palavras 5,0);
    - precisão de todas as ocorrências 88% (22,6);
    - linguística 65/84 (era 66/85; sai a anotação de `tratamento`);
    - 63 dos 65 erros encontrados ficam na fila; 2 só como observação (subordinada isolada e um
      acento, classes de confiança baixa sem medição).
  - `examples/` mantidos sem destino, como relatórios antigos de compatibilidade.
- [x] Etapa 4 — Auditoria (07/10). Política v2, com a seção `auditoria`:
  - confiança baixa vai sempre para `diagnostico`;
  - as categorias experimentais começam em `diagnostico`;
  - ortografia, concordância, crase e regência começam como `informacao`;
  - a promoção a pendência depende só de medição (mesma regra das demais classes);
  - `impeditivo` nunca vem da Auditoria por conta própria;
  - a classe da Auditoria é `audit_<categoria>` (em `politica.classe` e no script de medição);
  - o prompt e `VERSAO_PROMPT` não mudaram; nenhuma chamada à API.

  A avaliação do corpus mede a Auditoria incluindo o diagnóstico (contagem `diagnostico`), sem
  contá-lo como ocorrência mostrada. O dado de teste `audit_agreement`, que não existe como
  categoria, passou a `audit_concordancia`.
- [x] Etapa 5 — app (07/10). Falta a inspeção visual pelo autor.
  - `Finding.destino/impeditivo`, `FindingDestination`, `ReviewTally`, `ReviewClosure` e
    `ReportMetadata.politicaVersao/diagnostico`.
  - Decisão “Corrigido” (último caso, ⌘7), gravada pela correção no Pages.
  - Mesa com `DeskSection` (Pendências padrão, Observações) e `ClosureStrip` (impeditivos e
    encerramento). Cartões de observação discretos; impeditivos primeiro, com etiqueta.
  - Inspetor com a nota do destino; `DiagnosticPanel` em Etapas e alcance.
  - O título da janela e o menu de capítulos contam pendências.
  - Encerramentos em `Encerramentos/<sha256>.json`; Limpar resíduos não os toca.
  - `tests/ClosureCheck.swift` novo; a montagem roda também `DeskToolsCheck` e `ClosureCheck`.
  - Evidências: montagem `build/20261007-180710-05B33731/`, com contrato Swift, decisões por livro,
    mesa, encerramento, falsos positivos e correção validados. FONTE 417, pacotes 37, contrato
    Python, Coerencia 25. O motor congelado lê a política (B: 2 pendências, 13 observações).
  - Pendente: inspeção visual nativa e uso real pelo autor.

## Validação realizada e resultado final

(preencher ao fim de cada etapa)
