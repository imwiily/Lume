# Estabilização final do FONTE

Pedido do autor (07/10/2026). Branch `fonte-estabilizacao-final`, criada a partir do marco
estável `9f0f6d801b14aad62e25d9722588b787e0694c59` (`organizacao-e-deteccao`, não alterada).
Objetivo: responder se tudo o que o FONTE se propõe a detectar está bem definido, é
generalizável, coerente e confiável. **Detectar menos coisas com mais consistência.**

Restrições:
- não mexer em Mesa, encerramento, destinos ou critérios da Política;
- a Auditoria continua como controle de qualidade;
- nenhuma regra nova a partir de caso isolado;
- preservar IDs, relatórios e decisões;
- nenhuma chamada à API.

## Progresso

- [x] Etapa 1 — inventário (07/10, sem alterar código).
- [x] Etapa 2 — auditoria arquitetural (07/10, sem alterar código).
- [x] Etapa 3 — plano de estabilização (07/10; aprovado pelo autor com as decisões D1–D8).
- [x] Fase 0 — linha de base e comparação (07/10).
- [x] Fase 1 — identidade, regra e classe (07/10; aprovada pelo autor).
- [x] Fase 2a — núcleo verbal, sem mudança de comportamento (07/10; aprovada pelo autor).
- [x] Preparação da Fase 2b: evidência independente congelada e protocolo (07/10; commit `b935ebf`).
- [x] Fase 2b — reconhecimento verbal (08/10; commit `184ffbc`).
- [x] Fase 3 — núcleo de tempo e modo, só consolidação (08/10; commit `e0159ca`).
- [x] Fase 4 — segmentação entre fala e narração, só consolidação (08/10; commit `f01bd9e`).
- [x] Fase 5 — verbos de fala, pensamento e percepção, só consolidação (08/10; commit `30549b0`).
- [x] Fase 6a — deduplicação centralizada, sem mudança de comportamento (08/10; commit `02888c9`).
- [x] Fase 6b — deduplicação por família com preservação das decisões (08/10; commit `50860e4`).
- [x] Fase 6b — categoria original do LanguageTool (08/10; commit `1ef184d`).
- [x] Fase 6b — LanguageTool indisponível: análise parcial (08/10; commit `c5339e1`).
- [x] Fase 7a — parecer definitivo das regras e plano de implementação (08/10; commit `3218e49`;
  aprovada pelo autor; nenhuma regra alterada).
- [x] Fase 7b — implementação (08–09/10; commits `5f40df7` a `061fb6f`, registro em `4882ab1`).
  Aprovada pelo autor em 09/10.
- [x] `imperfeito` (problema 1 da Fase 3): corrigido na Fase 7b, grupo 5 (`5303db5`); aprovado junto
  com a Fase 7b.
- [x] Fase 8 — auditoria cruzada, validação final e preparação do FONTE 1.5.0 (09/10). Veredicto:
  apto. Aguarda a aprovação final do autor; sem tag, release ou push.

## Fontes de evidência usadas

| Fonte | Conteúdo | Limites |
|---|---|---|
| Decisões reais (`build/precisao-20261007/`) | 650 decisões únicas, 6 livros, 1 autor | Classes com n < 20 não têm precisão medida |
| Quatro textos reais analisados hoje, sem LanguageTool | A, B e C (do autor) e um texto de terceiros | A e B já revisados: poucos erros restantes |
| Corpus `todos` por classe, sem LanguageTool | 4.084 palavras | Escrito junto com as regras: quase todas as classes dão 100%, o que mede pouco |
| Uso real | 58 de 58 relatórios rodaram com LanguageTool | — |

“Disparos A/B/C/X” abaixo é a contagem nos quatro textos.

## Etapa 1 — Inventário

Legenda:
- **Natureza:** O = objetiva; E = editorial; R = registro ou estilo.
- **Destino:** destino segundo a política v2.
- **Impl.:** G = estrutural ou geral; H = heurística com listas ou regex estreitas; X = nasceu de
  um exemplo isolado.

### Etapa Linguística (`linguistic.py`, `editorial/repetition.py`, `languagetool.py`)

| ID (regra) | Função | O que detecta | Evidência | Conf. | Sev. | Destino | Decisões (prec.) | Disparos A/B/C/X | Nat. | Impl. |
|---|---|---|---|---|---|---|---|---|---|---|
| `construcao_invalida` | `linguistic.RULES` | só “além de disso” | 1 regex | alta | confirmed | pendência | 1 (100%) | 0/0/0/0 | O | X |
| `pontuacao_duplicada` | `linguistic.RULES` | `,,` `;;` `..` | regex | alta | confirmed/probable | pendência | 12 (92%) | 0 | O | G |
| `espacamento` | `linguistic.RULES` | espaço duplo; espaço antes de `,;` | regex | alta | probable | pendência | 1 | 0 | O | G |
| `virgula_que_nao` | `linguistic.RULES` | “que, não” | regex com 3 exceções | média | probable | pendência | 1 | 0 | O? | X |
| `que_tonico_interrogativo` | `linguistic.RULES` | “que?” → “quê?” | regex | alta | probable | pendência | 4 (100%) | 0 | O | G |
| `capitalizacao_contextual` | `linguistic.RULES` | pronome minúsculo depois de `?` ou `!` | regex com lista de pronomes | média | probable | pendência | 0 | 0 | O? | H |
| `vocativo` | `linguistic.vocatives` | nome inicial + aposto + verbo; nome + “você”/“não faça”; “Sim/Oi + nome” | 3 regex + léxico | média | probable | pendência | 0 | 0 | O? | H |
| `palavra_consecutiva` | `editorial/repetition.analyze` | “o o”, palavra dobrada | regex + léxico | média | — | pendência | 1 (0%) | 0 | O | G |
| (LanguageTool) `languagetool:ortografia` | `languagetool.check` | grafia | LT + filtros de nomes e itálico | alta (forçada) | probable (forçada) | pendência | 13 (31%) | — | O | G (externa) |
| (LanguageTool) `languagetool:gramatica` | `languagetool.check` | concordância, crase, pontuação etc. | LT + 12 filtros pontuais | média (forçada) | probable (forçada) | pendência | 30 (60%) | — | O | G (externa) |

### Etapa Morfossintática

| ID | Função | O que detecta | Evidência | Conf. | Sev. | Destino | Decisões (prec.) | Disparos A/B/C/X | Nat. | Impl. |
|---|---|---|---|---|---|---|---|---|---|---|
| `tempo_verbal` (category_code `narrative_tense`, sem `rule`) | `analysis.analyze` | verbo fora do tempo escolhido, um a um | léxico (`indicative_tense`) + modelo + `legitimate_present`, `present_function`, `past_plane`, `narrator_frame`, `lista_ou_rotulo` | média/baixa | (sem severity → editorial_attention) | pendência (média); observação (baixa) | média 408 (91%); baixa 8 (0%) | 12/0/6/16 | E | G + camadas de exceções |
| `estrutura` (`sentence_structure`) | `analysis.analyze` | frase sem verbo finito; fragmento incompleto | modelo + `verbo_finito_possivel` + segunda leitura + `classificar_fragmento`, `fragmento_deliberado`, `elipse_de_complemento`, `para_verbal`, `fragmento_suspenso` | média/baixa | — | pendência / observação | média 18 (39%); baixa 10 (10%) | 0/1/4/1 | E | H (pilha de exceções) |
| `estrutura` (`incomplete_subordinate_clause`) | `analysis.analyze` | subordinada sem principal | `abertura_subordinada` + árvore | baixa | — | observação | 1 | 0/0/1/0 | E | H |
| `estrutura` (Resíduo de edição, `editorial_review`, sem `rule`) | `analysis.analyze` | dois auxiliares finitos seguidos | árvore (aux) | média | — | pendência | 2 (50%) | 0 | O | G |
| `coerencia_temporal` (10 subtipos) | `temporal.relations/conditionals/modality/sequence/surface_coordination` | tempos incompatíveis entre orações e na sequência narrativa | árvore + `form`/`event_tense` + estado local + listas (`STATIVE`, `TIME_SHIFTS`…) | alta/média/baixa | probable/attention | pendência / observação | alta 12 (100%); média 14 (57%); baixa 2 | ver subtipos | E | G + H |
| ├ `conditional_tense_mismatch`, `conditional_future` | `conditionals`, `relations` | “se … iria … irá” | árvore + terminação | | probable | | | 0 | | G |
| ├ `modal_mood_mismatch` | `modality` | “talvez” + indicativo | advérbio + modo | | attention | | | 1/0/0/0 | | H |
| ├ `simultaneous_present`, `ambiguous_simultaneity`, `coordinated_past_present` | `relations` (geração antiga) | presente ligado a passado | árvore | | | | | 0 | | G |
| └ `coordinated_tense_mismatch`, `past_present_past`, `same_subject_narrative_shift`, `local_narrative_tense_shift` | `sequence`, `surface_coordination` (geração nova) | desvio na sequência narrativa | eventos + estado | | probable | | | 9/0/0/2 | | G |
| `acentuacao_contextual` | `temporal.accents` | “caiam” → “caíam” no passado | léxico (hiato) + raiz + sujeito | média | probable | pendência | 2 (50%) | 0 | O | G |
| `crase` (6 subclasses) | `grammar.crase` | locuções fixas; “às vezes”; horas; “à” + verbo/masculino; dativo feminino; locução prepositiva | regex + listas (`DATIVE`, `COMMON_GENDER`, `LOCUTIONS`) + árvore | alta/média | probable | pendência | 0 próprias | 0/1/0/0 | O | G (fixas) / H (dativo) |
| `homofonos` (7 subclasses) | `grammar.homophones` | por que/porque; mas/mais; mal/mau; há/a; onde/aonde; debaixo/em cima | regex + listas de exceções | alta/média | probable | pendência | 0 | 0 | O | H (exceções acumuladas em há/a, mais) |
| `concordancia` (5 subclasses) | `grammar.agreement`, `elided_subject_plural` | haver impessoal; sujeito × verbo; um/nenhum; atração; nominal; sujeito oculto + predicativo plural | árvore (`nsubj`, `Number`) + guardas | média | probable | pendência | 5 (100%) | 0/0/1/0 | O | G + H |
| `regencia` (3) | `grammar.regency` | “chegar em”; “ajudou ela”; “pedir para que” | árvore + listas | média | attention | pendência | 4 (75%) | 1/0/0/0 | **R** | X |
| `virgula_sujeito_verbo` (2) | `grammar.subject_comma`, `relative_subject_comma` | vírgula isolada entre sujeito e verbo | árvore + forma | média | probable | pendência | 2 (50%) | 0/0/1/0 | O | G + H |
| `correlacao_tempos` | `grammar.correlation` | subordinada no imperfeito do subjuntivo + principal no presente | lista de conectores + terminação | média | probable/attention | pendência | 7 (86%) | 0/0/5/0 | E | H |
| `frase_cortada` (3) | `grammar.truncated` | frase que termina em preposição ou em “cada”; parágrafo sem ponto final; “Que” maiúsculo depois de reticências | listas + regex | média | probable/attention | pendência | 3 (100%) | 19/1/3/1 | O / E | H; X (“cada”, “Que”) |
| `locucoes` (2) | `grammar.locutions` | “ao invés de”; “embora” + nome | regex | média | attention/probable | pendência | 2 (100%) | 0/0/2/0 | R / O | X |

### Etapa Editorial (contexto curto)

| ID | Função | O que detecta | Evidência | Conf. | Sev. | Destino | Decisões (prec.) | Disparos A/B/C/X | Nat. | Impl. |
|---|---|---|---|---|---|---|---|---|---|---|
| `pontuacao_dialogo` (`dialogue_punctuation`, sem `rule`) | `analysis.analyze` | aspas + vírgula + verbo que não é de fala | fechamento de aspas (`narrative_masks`) + lista `SPEECH` | média | — | pendência | 9 (78%) | 0 | E | H |
| `dialogo_contextual` (2) | `editorial/context.analyze` | ação depois do travessão sem pontuação; fala retomada com maiúscula | segmentação + verbo de fala | baixa (rótulo) | attention | pendência (dados) | 32 (91%) | 0 | O? / E | G + lista de fala |
| `referente_contextual` | `editorial/context.analyze` | só a palavra “o objeto” depois de enumeração | literal “objeto” | baixa | author_query | observação | 0 | 0 | E | **X** |
| `gerundismo` | `editorial/context.analyze` | “vou estar fazendo” | regex | baixa | attention | observação | 1 (0%) | 1/0/0/0 | **R** (a mensagem diz “não é erro”) | H |
| `palavra_proxima` | `editorial/repetition.analyze` | mesma palavra a ≤ 8 palavras | contagem + exceções expressivas | baixa | attention | observação | 43 (23%) | 19/12/4/15 | **R** | H |
| `frase_duplicada` | `editorial/repetition.analyze` | frase repetida | igualdade ou semelhança | alta/baixa | attention | pendência / observação | 0 | 0 | E | G |
| `referente_proximidade` | `editorial/references.analyze` | só “Eles/Elas + estavam/estão/ficaram + tão/muito/bem + perto” sem plural antes | 1 regex | baixa | author_query | observação | 0 | 0 | E | **X** |
| `pronome_apos_corte` | `editorial/references.edit_scars` | pronome perto de trecho cortado em relação ao original | diff de palavras (exige `--original`) | baixa | author_query | observação | 0 | 0 | E | H |

### Etapa Coerência global

| ID | Função | O que detecta | Evidência | Conf. | Sev. | Destino | Decisões | Disparos | Nat. | Impl. |
|---|---|---|---|---|---|---|---|---|---|---|
| `variacao_nome` (2) | `editorial/entities.analyze`, `capitalization` | nomes a uma letra de distância; o mesmo termo com e sem maiúscula | léxico + distância | média | attention | pendência | 2 (0%, intencionais) | 0/0/2/4 | E | G |
| `duracao_suspensao` | `editorial/chronology` | “suspenso por N dias” × “amanhã e os N dias seguintes” | 2 regex | alta | possible_inconsistency | pendência | 0 | 0 | E | **X** |
| `adiamento_amanha` | `editorial/chronology` | “adiado para amanhã” × “mais N dias” | 2 regex | média | possible_inconsistency | pendência | 0 | 0 | E | **X** |
| `coerencia_ia` | `coerencia_ia.py` (Coerencia) | contradições narrativas | IA + trechos conferidos | média/alta | possible_inconsistency | pendência | 0 | — | E | (IA) |
| `auditoria_ia` | `auditoria_ia.py` | QA, 11 categorias | IA | média/baixa | attention/possible | diagnóstico / observação | 0 | — | — | (IA) |

**Total:** 30 regras configuráveis ativas, mais 2 classes do LanguageTool e 2 recursos com IA. Dentro
delas há cerca de 45 subclasses com mensagem própria.

## Etapa 2 — Auditoria arquitetural

### A. Regras frágeis
- **Nascidas de um único exemplo (X):**
  - `construcao_invalida` (um regex: “além de disso”);
  - `referente_proximidade` (uma frase-modelo);
  - `referente_contextual` (a palavra literal “objeto”);
  - `duracao_suspensao` e `adiamento_amanha` (prazos de uma cena específica);
  - `frase_cortada` nas partes “cada” e “Que” depois de reticências;
  - `locucoes` na parte “embora + nome”;
  - `virgula_que_nao`.

  Nenhuma disparou nos quatro textos reais. Juntas somam 1 decisão real.
- **Exceções acumuladas:**
  - **`homofonos`, parte há/a:** listas de verbos e palavras que impedem o alerta (“daqui”,
    “faltava”, “chegar”, “voltar”…).
  - **`homofonos`, parte mas/mais:** lista de palavras seguintes.
  - **`estrutura`:** seis funções de exceção encadeadas e uma segunda leitura. A precisão real é
    de 39% (média) e 10% (baixa).
  - **`tempo_verbal`:** `legitimate_present` com listas (`STATIVE`, verbos de fala, “há + tempo”,
    “quer que”, “poder confirmar”), mais `present_function`, `past_plane` e `narrator_frame`. Elas
    funcionam (91% em 408), mas cada caso real virou mais uma lista.
- **Regex sem estrutura:**
  - `capitalizacao_contextual`, `vocativo` (três padrões) e `gerundismo`;
  - `chronology`.
- **Segmentação frágil:** `pontuacao_dialogo` depende de `narrative_masks`, uma segunda
  implementação de fala e narração, diferente de `segments.classify` (ver C).

### B. Sobreposição
1. **Tempo verbal: quatro detectores para o mesmo verbo.**
   - Os detectores são `tempo_verbal` (desvio do tempo escolhido), `coerencia_temporal` (duas
     gerações de relações), `correlacao_tempos` e, na Auditoria, `tempo_verbal`.
   - Existem dois mecanismos de remoção de duplicatas para conter isso: em
     `pipeline.morphosyntactic` e em `temporal.PRECEDENCE`.
   - A geração antiga (`simultaneous_present`, `ambiguous_simultaneity`, `coordinated_past_present`,
     `conditional_future`) só sobrevive onde a nova não aponta, e não disparou em nenhum texto real.
   - Os fenômenos são legítimos e diferentes: desvio global, relação entre orações, correlação do
     subjuntivo. A análise base, porém, deveria ser uma só.
2. **Palavra dobrada: três implementações.**
   - `editorial/repetition` (ativa), um ramo morto em `analysis.analyze` e a regra
     `PORTUGUESE_WORD_REPEAT_RULE` do LanguageTool.
   - A Auditoria também tem a categoria `repeticao`.
3. **Pontuação de diálogo: duas regras para a mesma classe** (ação narrativa depois da fala).
   - `pontuacao_dialogo` cobre falas com aspas; `dialogo_contextual`, falas com travessão.
   - São listas de verbos de fala e segmentações diferentes.
4. **Espaços e pontuação** (`espacamento`, `pontuacao_duplicada`, `capitalizacao_contextual`)
   repetem regras do LanguageTool, que é mais amplo.
5. **Crase, homófonos e concordância:** as regras próprias convivem com as equivalentes do LT, e a
   pipeline só esconde a própria quando o LT apontou o mesmo trecho.

### C. Componentes compartilhados com problema (corrigir na base, não nas regras)
1. **“Verbo finito”: sete definições.**
   - `lexicon.finite`, `lexicon.model_finite`, `analysis.verbo_finito_possivel` + `posicao_de_verbo`,
     `temporal.form`, `temporal.event_tense`, `grammar.verbal`, `grammar.present_main.only_finite`.
   - Além delas, o teste direto de `"Fin"` em `grammar.agreement` e `subject_comma`.
   - Regras diferentes discordam sobre o mesmo token. Os casos “Corri… entro” e “Olho” vêm daí:
     o modelo marca a primeira palavra como nome, e cada regra se recupera (ou não) do seu jeito.
2. **Tempo de um verbo: três classificadores.**
   - `lexicon.indicative_tense` (usado por `tempo_verbal`), `temporal.form` e `temporal.event_tense`.
3. **Fala e narração: duas segmentações.**
   - `segments.classify` (corrigida em 07/10 para fala por linha) e `analysis.narrative_masks`, que
     ainda tem a lógica antiga e só alimenta os fechamentos de aspas de `pontuacao_dialogo`.
4. **Verbos de fala: quatro listas.**
   - `analysis.SPEECH`, `IRREGULARES_DE_FALA`, `forma_de_fala` e `grammar.COMPLEMENT_VERBS`.
   - Elas aparecem em `dialogo_contextual`, `pontuacao_dialogo`, `virgula_sujeito_verbo`,
     `regencia`, `frase_cortada` e `tempo_verbal`.
5. **Identificador da regra ausente.**
   - Os alertas de `analysis.py` (tempo verbal, estrutura, resíduo de edição, pontuação de diálogo)
     não têm `rule`. A política e a medição os reconhecem pelo `category_code`, e o resíduo de
     edição aparece como `editorial_review`, um código genérico.
   - Desligar `estrutura` desliga também o resíduo de edição, que é outra classe.
6. **Código morto:** o ramo `palavra_consecutiva` e as máscaras de `narrative_masks` (sobrescritas
   por `masks_override`) em `analysis.analyze`.

### D. Regras específicas demais (as 5 perguntas)

| Regra | Classe real? | Generalizável? | Ocorre em textos diferentes? | Detecção confiável? | Ferramenta melhor? | Proposta |
|---|---|---|---|---|---|---|
| `construcao_invalida` | sim (locução deformada) | não, como está (1 padrão) | não (0 disparos) | sim no padrão | LT tem regras de locução | retirar ou generalizar com uma lista curada de locuções deformadas |
| `referente_proximidade` | sim (referência) | não | não | não | IA | retirar |
| `referente_contextual` | sim | não (palavra literal) | não | não | IA | retirar |
| `duracao_suspensao`, `adiamento_amanha` | sim (continuidade de prazos) | não | não | não | Coerência com IA | retirar |
| `frase_cortada`: “cada”, “Que” | parcialmente | não | não | sim no padrão | — | retirar essas duas partes |
| `locucoes`: “embora + nome” | sim | estreita | não | média | — | simplificar ou retirar |
| `virgula_que_nao` | sim (vírgula indevida) | estreita | não | média | — | retirar ou fundir num futuro detector de vírgula |
| `regencia` (3 casos) | é registro, não erro | — | raro | sim | — | retirar (conflita com “não sugerir estilo”) |
| `gerundismo` | é estilo | — | raro | — | — | retirar (a própria mensagem diz “não é erro”) |
| `palavra_proxima` | é estilo | — | muito | 23% | — | retirar (o princípio “nunca sugerir limpeza de repetição” já exclui; hoje é observação) |
| `locucoes`: “ao invés de” | prescrição discutível | — | raro | média | — | retirar ou manter só como observação |

### E. Mensagens mais fortes que a evidência
- **LanguageTool:** `contracts.occurrence` força `probable_error` em todo alerta do LT, inclusive
  nos de confiança baixa. A ortografia do LT aparece como “alta”, mas acertou 31% em 13 decisões.
- **`concordancia` e `crase` (dativo):** afirmam quem faz ou recebe a ação (“Quem faz a ação é
  X”), mas isso vem do analisador sintático. Deveriam dizer “parece”.
- **Pontuação final ausente:** “O parágrafo termina sem ponto.” como `probable_error` .8. Linhas
  de título, epígrafe, verso e lista são legítimas (A tem 19 disparos sem decisão).
- **`capitalizacao_contextual` e `vocativo`:** `probable_error` .85 sem nenhuma medição.
- **Confiança “alta”:** `pontuacao_duplicada`, `espacamento` e `que_tonico` declaram 0,9 ou mais
  sem medição suficiente (exceto `pontuacao_duplicada`, 92% em 12).
- **Na direção oposta, rótulo fraco demais:** `dialogo_contextual` aparece como “baixa”, mas acertou
  91% em 32 decisões. A política já corrige isso pelo dado.

### F. LanguageTool
- **Uso real:** ligado em 58 de 58 análises. Na prática, é sempre a primeira fonte de ortografia e
  gramática geral.
- **Precedência invertida entre etapas:**
  - na etapa linguística, a regra própria vence (o alerta do LT no mesmo trecho é descartado);
  - na morfossintática, o LT vence (a regra gramatical própria é pulada no trecho do LT).
- **Duplicação sem ganho:** `espacamento`, `pontuacao_duplicada` (em parte), `palavra_consecutiva`
  e `capitalizacao_contextual` repetem regras do LT.
- **O que o FONTE acrescenta e o LT não tem:**
  - tempo verbal da narração e coerência temporal;
  - correlação de tempos;
  - estrutura de diálogo;
  - crase dativa e com horas;
  - “haver” impessoal com contexto;
  - vírgula entre sujeito e verbo com relativa;
  - acentuação contextual no passado;
  - variação de nomes da obra.
- **Recomendação:** tratar o LT só como fonte de ocorrência. O contrato deixaria de forçar
  severidade e confiança, e a política e os dados decidiriam o peso de cada classe do LT
  (`languagetool:ortografia` e `:gramatica` já são classes medidas).

### Resumo da Etapa 2

1. **Regras saudáveis** (classe real, implementação estrutural, evidência boa ou objetiva):
   - `pontuacao_duplicada` (92% em 12), `que_tonico_interrogativo` e `acentuacao_contextual`;
   - `concordancia` (exceto as mensagens);
   - `crase` nas locuções fixas, nas horas e em “à” + verbo/masculino;
   - `tempo_verbal` (91% em 408) e a geração nova de `coerencia_temporal` (100% em 12, alta);
   - `dialogo_contextual` (91% em 32), `frase_duplicada` e `variacao_nome`;
   - `correlacao_tempos` (86% em 7) e o resíduo de edição.
2. **Precisam de refatoração:**
   - `estrutura` (pilha de exceções; 39% e 10%);
   - `tempo_verbal` e `coerencia_temporal` (análise base comum, ver C1–C2);
   - `pontuacao_dialogo` e `dialogo_contextual` (uma segmentação e uma lista de fala);
   - `homofonos` nas partes há/a e mas/mais;
   - `frase_cortada` na parte de pontuação final ausente (títulos, versos, epígrafes).
3. **Redundantes:**
   - o ramo `palavra_consecutiva` de `analysis.py` (morto) e as máscaras de `narrative_masks`;
   - a geração antiga de relações temporais;
   - `espacamento` e `capitalizacao_contextual` diante do LanguageTool.
4. **Frágeis (H):**
   - `vocativo`, `capitalizacao_contextual` e `virgula_que_nao`;
   - `homofonos` nas partes com exceções;
   - `crase` no dativo;
   - `locucoes`;
   - `correlacao_tempos` na parte “se”.
5. **Candidatas à retirada:**
   - nascidas de exemplo isolado: `construcao_invalida` (ou generalizar), `referente_proximidade`,
     `referente_contextual`, `duracao_suspensao`, `adiamento_amanha`, as partes “cada” e “Que” de
     `frase_cortada` e a parte “embora + nome” de `locucoes`;
   - estilo ou registro, em conflito com “não sugerir estilo”: `gerundismo`, `palavra_proxima`,
     `regencia` e “ao invés de”.
6. **Componentes compartilhados a melhorar:**
   - verbo finito único (C1);
   - classificador de tempo único (C2);
   - segmentação de fala única (C3);
   - lista de verbos de fala única (C4);
   - `rule` explícito em todos os alertas (C5).
7. **Conflitos com o LanguageTool:**
   - precedência invertida entre etapas;
   - severidade e confiança forçadas no contrato;
   - duplicação em espaços, pontuação e palavra dobrada.
8. **Riscos de regressão:**
   - **IDs:** a chave inclui categoria e origem (`source`), então mudar a categoria ou a origem de
     um alerta muda o ID. As retiradas não afetam IDs de outras regras.
   - **Política:** a medição é por classe; renomear ou unificar classes zera a medição (precisa de
     um mapa de classes antigas).
   - **Verbo finito:** é a mudança de maior alcance. Pode alterar tempo verbal, estrutura,
     concordância e vírgula ao mesmo tempo, então exige comparação antes/depois por classe em A, B,
     C, no texto de terceiros e no corpus.
   - **Corpus:** ele foi escrito junto com as regras (quase tudo dá 100%) e não detecta queda de
     precisão real. A métrica principal precisa vir das decisões reais.
   - **Configurações salvas:** regras retiradas entram em `RETIRED_RULES` e `retiredIDs`.

**Erros fora da cobertura vistos nesta auditoria** (registrados, sem regra nova):
- 1ª pessoa no início de frase sem sujeito (“Olho”, “Corri… entro”);
- mistura de tu e você entre falas;
- palavra estrangeira sem itálico.

Todos dependem de componentes base (C1) ou de atribuição de falante. Nenhum tem dados que
justifiquem uma regra própria.


## Etapa 3 — Plano de estabilização

Ordem pedida pelo autor:
1. núcleo linguístico;
2. reavaliação das regras;
3. sobreposição;
4. LanguageTool;
5. dados e compatibilidade (transversal);
6. evidência independente (transversal).

Nenhuma regra nova. Cada fase vira um commit próprio na branch `fonte-estabilizacao-final`. A
**reversão** de qualquer fase é `git revert` desse commit: nenhuma fase muda formato de arquivo de
forma incompatível, todos os campos novos só se somam, e a Política v2 não muda.

### Fatos de compatibilidade que guiam o plano
- **ID do alerta:** `sha256(parágrafo:categoria:origem:início:fim:texto)`. Não inclui `rule`,
  severidade, confiança nem mensagem. Mudar **categoria** ou **origem** (`source`) muda o ID; mudar
  o resto não.
- **Memória do livro** (`BookMemory.contentKey`, Swift): usa categoria, **`rule`**, origem, trecho e
  evidências.
  - Acrescentar `rule` a alertas que hoje saem sem ele **quebraria em silêncio** a herança de
    decisões entre versões do livro.
  - Exige migração (Fase 1).
- **Política e medição:** `politica.classe()` usa `rule` primeiro e `category_code` depois.
  Acrescentar `rule="tempo_verbal"` mudaria a classe estatística de `narrative_tense` para
  `tempo_verbal` e perderia as 408 decisões medidas. Exige uma classe estatística estável (Fase 1).

### Quatro tipos de evidência (Prioridade 6)

| Tipo | O que prova | Ferramenta | Basta para dizer que a regra é “saudável”? |
|---|---|---|---|
| 1. Funcionamento | o código faz o que diz | testes unitários | não |
| 2. Regressão | nada mudou sem querer | relatório antes/depois por ID, destino e classe em A, B, C, texto de terceiros e corpus; script novo de comparação (ferramenta, não regra) | não |
| 3. Generalização | a regra se comporta em texto que não vimos | textos independentes (ver decisão D7): alertas e alarmes por 10 mil palavras | parcialmente |
| 4. Decisões reais | precisão editorial | `scripts/medir_precisao.py` | sim, com n ≥ 20 |

Uma regra só é declarada saudável com evidência dos tipos 3 e 4. Sem n ≥ 20, o estado dela é
“sem evidência suficiente”, nunca “saudável”.

### Análise semântica das definições de verbo finito (base da Fase 2)
Não são sete versões da mesma pergunta. São **três perguntas diferentes**, mais um ingrediente:

| Definição | Pergunta que responde | Quem usa | Por que funciona ali |
|---|---|---|---|
| `lexicon.model_finite` | o modelo diz que é finito? | ingrediente das outras | — |
| `lexicon.finite` | **é certamente verbo finito?** (modelo + léxico + filtros nominais) | tempo verbal, estrutura (primeira leitura), correlação, frase cortada, vírgula com relativa | alertar *sobre* um verbo exige certeza |
| `temporal.form` | idem, já com o **tempo** (passado, presente, condicional, ambíguo) | coerência temporal | idem |
| `analysis.verbo_finito_possivel` + `posicao_de_verbo` | **pode ser verbo finito?** (basta uma fonte com apoio) | estrutura (“sem verbo”) | alertar a *ausência* de verbo exige abster-se na dúvida |
| `temporal.event_tense` | qual o tempo deste **evento**, recuperando erros do modelo pelo léxico e pela sintaxe? | sequência narrativa (âncoras) | recuperação, sem alerta direto |
| `grammar.verbal` | há **forma verbal** aqui? (modelo ou léxico só-verbo, sem posição) | guardas de homófonos (“porque”, “mais”) e de lema | guarda negativa: “não alertar se houver verbo antes” |
| `grammar.present_main.only_finite` | o léxico só conhece como verbo? | correlação (verbo principal) | recuperação pontual |
| teste direto de `"Fin"` | o modelo diz finito? (sem léxico) | concordância, vírgula sujeito–verbo | precisa do número e da pessoa do modelo |

**Consequência:** a unificação certa é **um núcleo com três políticas nomeadas e explícitas**, não
uma função só:
- `finito_certo`, para alertar sobre um verbo;
- `finito_possivel`, para se abster de afirmar ausência de verbo;
- `forma_verbal`, para guardas.

Além delas, **um** classificador de tempo, com modo estrito (alvo de alerta) e modo de recuperação
(âncora). Cada uso atual é ligado à política que corresponde ao que ele já faz.

### Fases

#### Fase 0 — Linha de base e ferramenta de comparação (sem mudança de comportamento)
- **Arquivos:** `scripts/comparar_relatorios.py` (novo; compara por ID, destino e classe) e testes
  dele.
- **Problema:** hoje as comparações são feitas à mão. Sem uma linha de base fixa, mudanças do
  núcleo não são verificáveis.
- **O que deve permanecer:** tudo; não há mudança no motor.
- **Testes:** os da própria ferramenta.
- **Evidências fixadas:** linha de base em `build/` (fora do Git) para A, B, C, texto de terceiros
  e corpus, com e sem LanguageTool; precisão por classe nas decisões reais; textos independentes
  (D7).
- **Risco:** nenhum.
- **Aprovação:** linha de base registrada no plano, com hashes dos textos e versão.

#### Fase 1 — Identificador explícito e classe estatística estável (C5)
- **Arquivos:** `analysis.py`, `politica.py`, `scripts/medir_precisao.py`, `contracts.py`,
  `app/Lume/Models.swift` (`contentKey`) e testes.
- **Problema:**
  - tempo verbal, estrutura, resíduo de edição e pontuação de diálogo saem sem `rule`;
  - o resíduo de edição é desligado junto com `estrutura`;
  - a classe estatística é deduzida de forma frágil.
- **Mudança:**
  1. Todo alerta passa a ter `rule` (`tempo_verbal`, `estrutura`, `residuo_edicao`,
     `pontuacao_dialogo`).
  2. Campo novo `classe` emitido pelo motor: a chave estatística. Ela fica **idêntica à de hoje**
     (`narrative_tense`, `sentence_structure`, `incomplete_subordinate_clause`,
     `editorial_review` etc.). Política e medição passam a ler `classe`, e relatórios antigos usam
     a dedução atual.
  3. Compatibilidade do `contentKey`: alertas cujo `rule` foi acrescentado nesta fase geram também
     a chave antiga (sem `rule`), e a herança aceita as duas.
  4. Configuração própria para o resíduo de edição (D2).
- **O que deve permanecer:** IDs e destinos 100% iguais; herança de decisões de memórias antigas.
- **Testes:**
  - funcionamento (todo alerta tem `rule` e `classe`);
  - regressão (IDs e destinos iguais nos cinco conjuntos);
  - Swift: memória antiga continua herdando;
  - configuração antiga com `estrutura: false` mantém o resíduo desligado (D2).
- **Risco:** baixo. **Precisão:** neutra.
- **Aprovação:** zero diferenças de ID e destino; `BookMemoryCheck` com memória antiga verde.

#### Fase 2 — Núcleo do verbo finito (C1)
- **Arquivos:** `fonte/fonte/verbo.py` (novo núcleo), `lexicon.py`, `analysis.py`, `temporal.py`,
  `grammar.py` e testes.
- **2a, refatoração sem mudança:**
  - as três políticas nomeadas reproduzem **exatamente** as definições atuais;
  - os chamadores passam a usar o núcleo;
  - `verbo_finito_possivel`, `verbal` e `only_finite` viram aliases e depois somem.
- **2b, alinhamento de divergências, uma por vez:**
  - exemplo: concordância e vírgula usam `"Fin"` cru e passariam a `finito_certo`, mantendo o
    número e a pessoa do modelo;
  - cada divergência é uma mudança separada, medida por classe.
- **O que deve permanecer:** 2a, saída idêntica; 2b, nenhuma classe medida perde precisão.
- **Testes:**
  - regressão byte a byte (2a);
  - testes de contrato das três políticas, com casos em que discordam de propósito (homógrafo
    nome/verbo, verbo ligado como complemento, 1ª pessoa sem sujeito);
  - generalização (2b).
- **Risco:** **alto** em 2b; atinge tempo verbal, estrutura, concordância e vírgula.
- **Precisão:** esperada maior na estrutura (39% → ?) e neutra no tempo verbal.
- **Aprovação 2b:**
  - nenhuma classe com n ≥ 20 cai de precisão (recalculada com os alertas que continuam);
  - alarmes por 10 mil palavras nos textos independentes não sobem;
  - toda mudança de alerta em A, B, C e texto de terceiros é listada e justificada.
- **Reversão:** 2a e 2b em commits separados.

#### Fase 3 — Classificador de tempo único (C2)
- **Arquivos:** `verbo.py`, `lexicon.indicative_tense`, `temporal.form` e `event_tense`,
  `grammar.correlation`.
- **Mudança:** os três classificadores viram `tempo(token, modo)`, com modo `estrito` (alvo de
  alerta) e `recuperacao` (âncora). Mesmo esquema da Fase 2: 3a idêntica, 3b alinhada e medida.
- **O que deve permanecer:** tempo verbal com média ≥ 91% (408 decisões); coerência temporal alta.
- **Risco:** médio-alto.
- **Aprovação e reversão:** como na Fase 2.

#### Fase 4 — Segmentação única de fala e narração (C3)
- **Arquivos:** `analysis.py` (`narrative_masks`, `pontuacao_dialogo`), `segments.py`.
- **Mudança:** os fechamentos de aspas usados por `pontuacao_dialogo` passam a vir de
  `segments.classify`. A lógica duplicada de `narrative_masks` sai.
- **O que deve permanecer:** os alertas de pontuação de diálogo nos textos com aspas. As diferenças
  esperadas vêm só da fala por linha, a correção de 07/10.
- **Testes:**
  - equivalência nos conjuntos;
  - aspas que atravessam parágrafos;
  - aspas de destaque;
  - fala no meio do parágrafo.
- **Risco:** médio (aspas desbalanceadas). **Aprovação:** toda diferença explicada.

#### Fase 5 — Léxico único de elocução (C4)
- **Arquivos:** `analysis.py` (`SPEECH`, `forma_de_fala`, `IRREGULARES_DE_FALA`), `grammar.py`
  (`COMPLEMENT_VERBS`), `editorial/context.py`.
- **Mudança:** um módulo com os verbos de fala (lemas, formas e irregulares).
  `COMPLEMENT_VERBS` (verbos que pedem “que”) é outro conceito: fica no mesmo módulo, como lista
  separada.
- **O que deve permanecer:** diálogo contextual com 91%.
- **Testes:** cada regra usuária, antes e depois.
- **Risco:** médio. Unir listas amplia ou reduz o que cada regra reconhece; medir por regra.

#### Fase 6 — Deduplicação central e LanguageTool (P3, P4)
- **Arquivos:** `pipeline.py`, `contracts.py`, `languagetool.py`, `temporal.py` e testes.
- **Mudança:**
  1. Um passo único de deduplicação depois de todas as etapas, com uma tabela de **famílias de
     fenômeno** (tempo, crase, concordância, ortografia, pontuação, diálogo, repetição…). Ele
     substitui o filtro do LT na etapa linguística, o pulo de trechos do LT na gramática e a
     remoção de duplicatas de tempo verbal da pipeline. O `PRECEDENCE` interno de `temporal` fica:
     é o mesmo detector.
  2. **Mesmo trecho e mesma família:** a regra específica vence a genérica; a precedência entre
     FONTE e LT segue a decisão D3. Fenômenos diferentes no mesmo trecho continuam separados.
  3. **O alerta descartado não some sem rastro:** ele fica registrado no vencedor (`absorvidos`:
     IDs). O app herda para o vencedor a decisão já tomada sobre um absorvido.
  4. **LanguageTool como fonte de ocorrências:** sem severidade nem confiança forçadas (D4). A
     política decide o peso pelos dados das classes do LT.
  5. **Geração antiga de relações temporais**
     (`simultaneous_present`, `ambiguous_simultaneity`, `coordinated_past_present`,
     `conditional_future`): retirada se a Fase 0 confirmar zero contribuição única e zero decisões.
     `conditional_tense_mismatch` fica.
  6. **Palavra dobrada:** sai o ramo morto de `analysis.py`; `repetition` fica, e o LT entra na
     deduplicação.
  7. **Diálogo:** as classes de aspas e de travessão ficam separadas (estatística e IDs), com
     segmentação e léxico comuns (Fases 4 e 5).
- **O que deve permanecer:**
  - o FONTE funciona igual sem o LT;
  - nenhuma capacidade própria confiável é removida por existir no LT.
- **Testes:**
  - deduplicação por família;
  - absorção com herança de decisão (Swift);
  - análise com e sem LT;
  - Política v2 sobre o resultado.
- **Risco:** médio. Os IDs mudam nos trechos em que o vencedor muda; a absorção preserva as
  decisões.

#### Fase 7 — Reavaliação das regras (P2): veredictos individuais
Tipos usados na tabela:
- (a) objetiva e confiável, mesmo rara;
- (b) específica demais;
- (c) redundante;
- (d) estilística ou de registro;
- (e) sem evidência suficiente;
- (f) estruturalmente equivocada.

| Regra ou parte | Tipo | Veredicto proposto | Justificativa |
|---|---|---|---|
| `construcao_invalida` (“além de disso”) | a | **manter** | erro objetivo, nunca correto, custo zero; rara não é motivo de retirada |
| `referente_proximidade` | b + f | **retirar** | ausência de plural em 3 parágrafos não prova ambiguidade; correferência está fora do escopo do FONTE (é da IA) |
| `referente_contextual` (“o objeto”) | b + f | **retirar** | depende de uma palavra literal; ambiguidade exige semântica |
| `duracao_suspensao`, `adiamento_amanha` | b | **retirar** | vocabulário de uma cena; continuidade de prazos é da Coerência com IA |
| `frase_cortada`: termina em preposição ou contração | a | **manter** | classe fechada, objetiva |
| `frase_cortada`: “cada” depois de verbo | a, mas estreita | **reformular**: entra na mesma lista fechada de palavras que pedem continuação, sem caso especial | mesma classe da preposição final |
| `frase_cortada`: “Que” maiúsculo depois de reticências | a (norma: a frase continua → minúscula) | **manter** | 1 caso real, correto; custo baixo |
| `frase_cortada`: pontuação final ausente | a, frágil | **reformular** depois da D6 | títulos, versos e epígrafes; 19 casos em A sem decisão |
| `locucoes`: “embora” + nome | a | **manter** | conjunção sem oração é erro objetivo; a guarda exige ausência de verbo |
| `locucoes`: “ao invés de” | d | **retirar** | distinção prescritiva; no PB contemporâneo é amplamente aceito como “em vez de” |
| `virgula_que_nao` | a, frágil | **reformular**: não alertar quando outra vírgula fecha um inciso logo adiante (“que, não sei como, …”) | erro real (vírgula solta), com uma falha estrutural identificável |
| `regencia`: “chegar em” | d (registro) | **retirar** | PB contemporâneo, prosa e diálogo; a própria mensagem admite o uso |
| `regencia`: “pedir para que” | d | **retirar** | idem |
| `regencia`: pronome reto como objeto (“ajudou ela”) | desvio da norma-padrão, comum no PB falado | **manter só na narração**, como atenção editorial, com mensagem de norma-padrão e não de erro (D5) | o narrador costuma seguir a norma; falas já estão fora |
| `gerundismo` | d | **retirar** | a mensagem já diz “não é erro” |
| `palavra_proxima` | d (23% em 43) | **retirar** (D5) | repetição é estilo; o Lume não sugere limpeza de repetição |
| `capitalizacao_contextual` | a, sem dados | **manter** | o FONTE precisa funcionar sem o LT; regra objetiva e barata |
| `vocativo` | a, frágil, sem dados | **manter**; revisar os 3 padrões só na Fase 2 | 0 decisões; sem base para retirar ou manter como saudável |
| `espacamento`, `pontuacao_duplicada`, `que_tonico` | a | **manter** | objetivas; necessárias sem o LT |
| `homofonos` (há/a, mas/mais) | a, com exceções acumuladas | **refatorar** guardas pelo núcleo (`forma_verbal`), sem novas listas | as listas são guardas de “há verbo”, função que o núcleo cobre |
| `crase` dativa | a, heurística | **manter** e moderar a mensagem (“parece”) | depende da árvore |
| `concordancia` | a | **manter** e moderar a mensagem | o sujeito vem do analisador |
| `estrutura` (fragmento) | e (39% / 10%) | **reavaliar depois da Fase 2**; se continuar abaixo de 50% com n ≥ 20, a Política já a mantém como observação (sem mudar a Política) | a causa principal é o verbo finito |
| `pontuacao_dialogo`, `dialogo_contextual` | a / e | **manter**, com componentes comuns | 91% e 78% |
| `pronome_apos_corte` | e | **manter** como está (exige `--original`; observação) | sem custo; sem dados |
| `correlacao_tempos`, `acentuacao_contextual`, `frase_duplicada`, `variacao_nome`, resíduo de edição, `tempo_verbal`, `coerencia_temporal` | a / e | **manter** | medidas ou objetivas |

Mensagens a moderar (sem mudar a detecção):
- concordância e crase dativa: “parece”;
- pontuação final ausente;
- confiança declarada sem dados.

A severidade do LT é tratada na Fase 6.

As retiradas vão para `RETIRED_RULES` e `retiredIDs`, ou viram subpartes retiradas. Os alertas
antigos dessas regras continuam legíveis.

#### Fase 8 — Auditoria cruzada e baseline final (Etapas 6–7 do pedido)
- **Revisar:** exceções introduzidas, lógica duplicada, testes de exemplo único e mensagens versus
  confiança.
- **Comparar:** antes e depois em todos os quatro tipos de evidência.
- **Proposta de versão:** FONTE 1.5.0 — baseline estável de detecção linguística.

### Limitações aceitas deliberadamente (não serão cobertas)
- Correferência e ambiguidade de referentes; continuidade e prazos entre cenas (Coerência com IA,
  opcional).
- Atribuição de falante, e com ela a mistura de “tu” e “você” entre falas.
- 1ª pessoa no início de frase sem sujeito que o modelo lê como nome (“Olho…”, “Corri…”). Depende
  do modelo; o núcleo só garante que nenhuma regra afirme o contrário.
- Palavra estrangeira sem itálico (o LT só baixa a confiança).
- Palavras válidas trocadas (“só”/“sobre”, “inferno”/“interno”).
- Registro, estilo, ritmo e repetição expressiva.
- Ortografia geral sem o LanguageTool.
- Vírgulas em geral (só as classes já existentes).

### Decisões que precisam da autorização do autor
- **D1.** Classe estatística: campo `classe` emitido pelo motor, com as chaves de hoje, em vez de
  renomear e migrar as medições. *Recomendado.*
- **D2.** Resíduo de edição com configuração própria (`residuo_edicao`). Em configurações antigas,
  herda o valor de `estrutura`.
- **D3.** Precedência no mesmo trecho e na mesma família:
  - **(a)** a regra específica do FONTE vence o LT, e o alerta do LT fica como absorvido, com a
    decisão herdada (*recomendado*: mensagem mais clara, classe medida, e o FONTE igual sem o LT);
  - **(b)** o LT vence o FONTE.

  Hoje as duas coisas acontecem, dependendo da etapa.
- **D4.** Severidade do LT pela categoria do próprio LT:
  - ortografia e gramática → provável erro;
  - pontuação, maiúsculas e tipografia → atenção editorial.

  A confiança do LT fica no máximo “média”, e os filtros continuam podendo baixá-la. Com isso, a
  ortografia do LT só poderia ser impeditiva se a Política medir 90% ou mais.
- **D5.** Confirmar estes veredictos: retirar `palavra_proxima` (hoje observação) e manter o
  pronome reto como objeto só na narração.
- **D6.** Pontuação final ausente: você decide no app os 19 casos de A, para dar dados antes da
  reformulação.
- **D7.** Evidência independente, à escolha:
  - **(a)** baixar textos literários brasileiros em domínio público, com grafia atualizada, como
    corpus de alarmes falsos (prosa editada profissionalmente: quase todo alerta é suspeito). Usa
    a internet e não envolve a API. Os textos ficariam fora do Git.
  - **(b)** textos que você fornecer;
  - **(c)** os dois.
- **D8.** Ordem e marcos de parada: proponho parar para sua revisão depois das Fases 1, 2b, 6 e 7.

### Decisões do autor sobre a Etapa 3 (07/10/2026)
- **D1 — aprovada.** Os nomes atuais das classes estatísticas ficam. Três coisas distintas:
  - **identidade persistente:** o ID, que não muda;
  - **identificação da regra:** `rule`;
  - **classe estatística:** `classe`.

  `rule` não pode alterar IDs nem impedir a herança de decisões.
- **D2 — aprovada.** `residuo_edicao` com configuração própria. Configurações antigas herdam o
  valor de `estrutura`, sem nenhuma mudança silenciosa nas preferências salvas (Python e Swift).
- **D3 — aprovada com ressalva.**
  - Opção A como estratégia inicial, **sem precedência absoluta**: classe por classe, a escolha é
    reavaliada se a regra própria tiver desempenho inferior ao do LT.
  - A deduplicação preserva a origem das duas detecções.
  - **Coincidência de trecho não prova equivalência.** Só se deduplica quando o fenômeno é
    comprovadamente o mesmo.
  - Nunca transferir decisão para um fenômeno apenas parecido.
- **D4 — reformular.** Separar quatro coisas:
  - a categoria informada pelo LT;
  - a severidade atribuída pelo FONTE;
  - a confiança;
  - o destino (Política v2, intacta).

  A correspondência entre categoria e severidade tem de ser conservadora, sem tratar a categoria
  do LT como prova de erro, e o impacto deve ser medido antes de aprovar. Fica para a Fase 6, com
  uma nova proposta.
- **D5 — aprovada com correção.**
  - Retirar `palavra_proxima`; `palavra_consecutiva` (palavra dobrada) **fica**.
  - Pronome reto como objeto: só na narração, mas **narração não é registro formal**. Respeitar
    narradores coloquiais, sobretudo em 1ª pessoa. O alerta é uma possível questão de norma-padrão,
    sem afirmar erro nem recomendar correção incompatível com a voz. Avaliar se há contexto para
    emitir com segurança.
- **D6 — aprovada.** O autor decide no app os 19 casos de pontuação final ausente em A. Até lá, a
  regra não muda.
- **D7 — opção C.**
  - Textos de domínio público, quando adequados, e textos do autor.
  - Variedade: 1ª e 3ª pessoa, passado e presente, diálogos, registros.
  - Textos antigos não servem de referência automática para a norma contemporânea.
  - Tudo fora do Git, respeitando direitos autorais.
  - Conjuntos de **desenvolvimento** e de **validação** separados; regras nunca são ajustadas
    pelo de validação.
- **D8 — aprovada.** Paradas depois das Fases 1, 2b, 6 e 7. Uma fase por commit, **com registro das
  dependências entre fases**: um `git revert` isolado não é seguro depois que fases seguintes
  dependem do código revertido.
- **Condições adicionais:**
  - o núcleo verbal preserva as **três perguntas** (certamente verbo, pode ser verbo, há forma
    verbal) e nunca vira uma função binária única;
  - regras raras (“embora” + nome, “Que” depois de reticências) ficam só se detectarem um fenômeno
    delimitado, e não um padrão superficial; serão reavaliadas na Fase 7 com contraexemplos
    corretos;
  - os percentuais (91% etc.) vêm sempre com o tamanho da amostra; não são garantia estatística.

### Dependências entre fases
- Fase 1 ← nenhuma.
- Fase 2a ← Fase 1 (`rule` e `classe`). Fase 2b ← 2a.
- Fase 3 ← Fase 2 (núcleo verbal).
- Fase 4 ← nenhuma de código, mas a comparação usa a Fase 0.
- Fase 5 ← Fase 4 (pontuação de diálogo).
- Fase 6 ← Fases 1, 4 e 5 (famílias, `rule` e `classe`).
- Fase 7 ← Fases 2–6.
- Reverter a Fase N exige reverter antes as fases que dependem dela, ou adaptá-las.


## Execução

### Fase 0 — linha de base (07/10/2026)
- **Motor:** os fontes em `9f0f6d8`, sem mudança de código.
- **Saída:** `build/baseline-9f0f6d8/` (fora do Git).
- **Textos** (cópias no scratchpad; início do SHA-256):

  | Texto | SHA-256 | Tempo |
  |---|---|---|
  | A | `16eb0bc91c878ff2` | passado |
  | B | `c2dd6f65b969344b` | passado |
  | C | `b8118757c5eb5af2` | presente |
  | texto de terceiros | `be79dc79ace25db9` | passado |

  Cada um foi analisado com e sem LanguageTool.
- **Alertas:**

  | Texto | Sem LT | Com LT | Pendências | Observações |
  |---|---:|---:|---:|---:|
  | A | 63 | 63 | 37 | 26 |
  | B | 15 | 18 | 2 | 13 |
  | C | 29 | 31 | 18 | 11 |
  | texto de terceiros | 39 | 50 | 13 | 26 |

  Pendências e observações contadas sem LT. Nenhum impeditivo.
- **Corpus `todos`** (relatórios guardados): precisão das pendências 97%, linguística 65/84.
- **Decisões reais:** 650 únicas, precisão total 79%.
- **Ferramentas:** `scripts/comparar_relatorios.py` (+4 testes, que importam a classe de
  `fonte.politica`) e `avaliar_deteccao.py --guardar-relatorios`.
- **Pendente:** os textos independentes (D7) ainda não foram reunidos. Vão ser montados antes da
  Fase 2b, com os textos do autor e textos de domínio público, separados em desenvolvimento e
  validação. A Fase 1 exige identidade, e não precisão, então não depende deles.

### Fase 1 — identidade, regra e classe (07/10/2026)
- **Código:**
  - `analysis.REGRA_POR_CATEGORIA` grava `rule` e o `category_code` de antes;
  - o LanguageTool grava `rule="languagetool"` e `category_code="grammar"`;
  - `politica.classe` lê o campo `classe` primeiro; para `REGRAS_SEM_CLASSE_PROPRIA`, usa o
    `category_code` de antes; `aplicar` grava `classe`;
  - `contracts.check_destination` exige `rule` e `classe`;
  - `medir_precisao.py` e `comparar_relatorios.py` usam `fonte.politica.classe`.
- **`residuo_edicao`:**
  - em `settings.RULES`;
  - sem a chave, herda `estrutura`;
  - pipeline e `search` passam a regra adiante;
  - `analysis` usa a chave própria;
  - no Swift: `SearchRule.all` e `newIDs`; `SearchSettings.decode` herda `estrutura`.
- **Memória do livro:** `Finding.legacyContentKey` dá a chave sem regra só para
  `rulesAddedLater`; `BookMemory.inherited` usa essa chave para os alertas que a nova não casou.
- **Evidência de regressão** (`build/fase1/comparacao/`):
  - 29 conjuntos (8 relatórios dos textos reais e 21 do corpus) **idênticos** em IDs, destino,
    impedimento, classe, severidade e confiança;
  - a única diferença é descritiva (`rule`);
  - o `category_code` também ficou igual.
- **Evidência de herança** com as memórias reais dos livros (verificação avulsa fora do Git):

  | Relatório | Decisões herdadas antes | Depois | Sem a chave antiga |
  |---|---:|---:|---:|
  | A | 28 | 28 (iguais) | 21 |
  | A com LT | 28 | 28 (iguais) | — |
  | C | 15 | 15 (iguais) | 7 |
  | C com LT | 17 | 17 (iguais) | — |

- **Testes:**
  - FONTE 421 (novos: `test_identidade_e_classes.py`, com 4 testes);
  - pacotes 41, contrato Python, Coerencia 25;
  - Swift: contrato (relatório novo e antigo), decisões por livro (chave antiga, regra que já
    existia não herda, herança de `residuo_edicao`), mesa, falsos positivos, encerramento,
    correção;
  - build Debug.
  - Mudança de expectativa: `test_politica` monta alertas com `rule` e `classe`, porque o contrato
    passou a exigi-los, e ganhou dois casos inválidos.
- **Limitação conhecida:** um motor externo anterior a esta versão recusa uma configuração que traga
  `residuo_edicao`. É o mesmo comportamento de quando entraram as regras gramaticais; o app usa o
  motor embutido da mesma versão.


### Fase 2a — núcleo de identificação verbal (07/10/2026)

**Núcleo novo, `fonte/fonte/verbo.py`.** Os corpos foram movidos por cópia exata e renomeados:

| Operação | Origem | Pergunta |
|---|---|---|
| `certamente_verbo` | `lexicon.finite` | identificação positiva |
| `pode_ser_verbo` + `posicao_de_verbo` | `analysis.verbo_finito_possivel` | identificação conservadora |
| `ha_forma_verbal` | `grammar.verbal` | verificação de presença |

Ingredientes:
- `model_finite`: leitura do modelo, com `Fin` ou modo;
- `conjugado_pelo_modelo`: só `Fin`, novo nome para as verificações diretas que existiam;
- `so_verbo_no_lexico`: unifica dois `only_finite`;
- `nominal_context`, `after_article`, `NOMINAL_DETERMINERS`, `TOTALIZERS`;
- `RELATIVOS`: uma definição só, importada por `analysis`.

`indicative_tense` mudou para o núcleo, por depender da identificação; o tempo será unificado na
Fase 3. `lexicon.py` fica só com os dados do léxico.

**Ligação de cada uso** (a semântica anterior é a regra):
- **`certamente_verbo`:** todos os usos de `finite` em `analysis` (estrutura, elipse, subordinada,
  pontuação de diálogo, resíduo), em `grammar` (vírgula com relativa, frase cortada, “Que” depois
  de reticências, “embora”) e em `temporal` (`form`, sujeito, coordenação, `sole_verb`,
  `event_tense`).
- **`pode_ser_verbo`:** estrutura (“sem verbo”), `aspas_de_destaque` e `fecha_oracao_dependente`
  (guarda do resíduo de edição).
- **`ha_forma_verbal`:** guardas de homófonos (“porque”, “mais”).
- **`conjugado_pelo_modelo`:** concordância (laço principal e verbo anterior na oração), pronome reto
  como objeto, vírgula entre sujeito e verbo, `present_main`.
- **`model_finite`:** `form`, `indicative_tense`, tempo verbal (passado só no léxico) e diálogo
  contextual (primeiro verbo pelo modelo).

**Combinações próprias mantidas como estavam** (não cabem limpas numa das três operações; ficam
documentadas para a Fase 2b):
- `grammar.relative_subject_comma`: `certamente_verbo(v) or (léxico finito and etiqueta verbal)`.
- `grammar.locutions` (“embora”): `certamente_verbo(t) or etiqueta verbal`.
- `grammar.present_main.only_finite`: `so_verbo_no_lexico(t)` e etiqueta não nominal.
- `temporal.event_tense`: verifica `"Fin" not in verb_form` dentro da recuperação de tempo
  (classificação de tempo, Fase 3).
- `pronome reto como objeto`: `token.pos_ == "VERB" and conjugado_pelo_modelo(token)` (sem AUX,
  como antes).

**Comportamentos estranhos vistos na sondagem, não corrigidos** (candidatos à Fase 2b, a medir):
- “começa” em “Uma nova era começa.” não passa em `certamente_verbo`, embora seja verbo;
- “coceira” passa em `ha_forma_verbal` por uma entrada do léxico.

**Testes:**
- `fonte/tests/test_verbo.py` (6), de caracterização:
  - o certo implica o possível;
  - o possível sem o certo, na posição do verbo;
  - a presença sem certeza;
  - as três concordam nos verbos claros;
  - definição única, com os módulos usando o núcleo.
- Quatro testes antigos só trocaram o caminho de importação (`fonte.lexicon.finite` →
  `fonte.verbo.certamente_verbo`; `nominal_context`). Nenhuma expectativa mudou.

**Evidências:**
- 29 conjuntos idênticos a `9f0f6d8` (código 0) e **byte a byte iguais à Fase 1**, inclusive
  mensagens e sugestões;
- herança real igual (A 28, A com LT 28, C 15, C com LT 17);
- FONTE 427, pacotes 41, contrato Python, Coerencia 25;
- Swift: contrato (relatório novo e antigo), decisões por livro, mesa, falsos positivos,
  encerramento;
- build Debug.


### Preparação da Fase 2b — evidência independente e protocolo (07/10/2026)

**Material.** Fica fora do Git, em `~/Lume-evidencia/`, com `MANIFESTO.md` e
`CONGELAMENTO-SHA256.txt`.
- **Fontes:** domínio público, Project Gutenberg, com autores diferentes em cada conjunto.

  | Conjunto | Obras | Narração |
  |---|---|---|
  | desenvolvimento | Machado de Assis, *Dom Casmurro* e *Memórias Póstumas*; Lima Barreto, *Policarpo Quaresma* | 1ª pessoa e comentário no presente; 3ª pessoa com diálogos |
  | validação | José de Alencar, *Cinco minutos*; Aluísio Azevedo, *O Cortiço* | 1ª pessoa epistolar; 3ª pessoa com fala popular |

- **Grafia:** as edições estão na grafia original; nenhuma edição atualizada estava acessível.
  - Critério, sem alterar os textos: só frases em que toda palavra minúscula existe no léxico
    contemporâneo do FONTE.
  - A grafia histórica nunca é tratada como erro.
- **Amostra:** `scripts/amostrar_verbos.py`, com a semente `fase2b`; 25 formas por estrato e por
  conjunto (150 + 150). Estratos: homógrafo nome/verbo, infinitivo ou futuro do subjuntivo, início
  de frase, discordância entre operações, controle verbal, controle não verbal.
- **Anotação cega,** com justificativa por item:

  | Conjunto | Finitos | Não finitos | Não verbais | Ambíguos |
  |---|---:|---:|---:|---:|
  | desenvolvimento | 48 | 32 | 70 | 1 |
  | validação | 53 | 41 | 56 | 3 |

  - `finito`: inclui o imperativo e o subjuntivo;
  - `nao_finito`: infinitivo, gerúndio ou particípio verbal;
  - `nao_verbal`.
- **Frases construídas:** 20, só no desenvolvimento, marcadas como tal (`desenvolvimento-construido.json`).
  Trazem os exemplos do autor (segura, causa, coceira, começa, cantar) e ambiguidades genuínas
  (vira, Leve, Grito).
- A, B, C e o texto de terceiros continuam como regressão histórica, **não** como validação.

**Ferramentas** (no repositório, sem efeito no motor):
- `scripts/amostrar_verbos.py`;
- `scripts/avaliar_verbo.py`, que mede as três operações e as três situações dos finitos e recusa
  listar erros da validação;
- `tests/test_evidencia_verbo.py` (4). O teste da recusa achou um defeito no avaliador (anotação
  vazia não acionava o bloqueio), já corrigido.

**Linha de base** (motor `7407ab5`; ambíguos fora das métricas):

| Métrica | Desenvolvimento (textos publicados) | Desenvolvimento + construídos | Validação (agregado) |
|---|---|---|---|
| `certamente_verbo`: precisão | 0,978 (n = 45; 1 falso positivo) | 0,980 (n = 49) | 0,979 (n = 47; 1 falso positivo) |
| `certamente_verbo`: cobertura dos finitos | 0,917 (n = 48) | 0,828 (n = 58) | 0,885 (n = 52) |
| `pode_ser_verbo`: cobertura dos finitos | 0,958 | 0,931 | 0,962 |
| `pode_ser_verbo`: taxa em não verbais | 0,101 (n = 69) | 0,133 | 0,109 (n = 55) |
| `ha_forma_verbal`: cobertura dos finitos | 0,958 | 0,897 | 0,904 |
| `ha_forma_verbal`: taxa em não verbais | 0,145 | 0,160 | 0,091 |
| Finitos: confirmados / não confirmados / modelo errou a classe | 44 / 3 / 1 | 48 / 5 / 5 | 46 / 2 / 4 |

O invariante “certo implica possível” vale nos dois conjuntos.

**Critérios de aprovação de cada mudança da Fase 2b.** Com n ≈ 50, um item vale cerca de 2 pontos
percentuais, então os critérios são em itens, não em porcentagem.

1. **Validação** (agregada, no máximo 3 consultas, cada uma registrada aqui):
   - `certamente_verbo`: nenhum falso positivo novo (≤ 1); a cobertura pode subir.
   - `pode_ser_verbo`: nenhum finito perdido (cobertura ≥ 0,962); a taxa em não verbais não sobe
     mais de 1 item.
   - `ha_forma_verbal`: taxa em não verbais ≤ 0,091 e cobertura ≥ 0,904.
   - O invariante “certo implica possível” continua valendo.
2. **Desenvolvimento:** a mudança corrige uma classe de erro com mais de um item. Exceção por frase
   é proibida.
3. **Regressão** (`comparar_relatorios.py`, 29 conjuntos):
   - toda mudança de alerta é listada e justificada pela classe corrigida;
   - nenhuma classe com n ≥ 20 decisões reais perde precisão (alerta decidido como erro que some
     conta como perda; alerta decidido como falso positivo ou estilo que some conta como ganho);
   - IDs dos alertas que continuam ficam iguais, e a herança real de decisões não cai.
4. **Ambíguos:** nenhuma mudança é justificada por item ambíguo.
5. **Reversão:** commit próprio por mudança, com as dependências registradas.

**Primeiras divergências** (só desenvolvimento; registradas, nada corrigido):
- **`ha_forma_verbal` confia na etiqueta do modelo.** No desenvolvimento, 14,5% dos não verbais
  passam como “há forma verbal”: substantivos, interjeições e pronomes que o modelo marcou como
  VERB (“vida”, “prima”, “romance”, “chorão”, “Oh”, “Tu”, “perdão”, “coitadinha”, “Eis”, “era”
  em “Uma nova era”, “coceira”). Como é uma guarda, o erro deixa as regras **mais caladas**, e não
  mais barulhentas. O custo são alertas perdidos (homófonos).
- **`certamente_verbo` com falso positivo:** “*Vão* temor!” (adjetivo, que o modelo leu como AUX).
  Um em 45.
- **`certamente_verbo` não confirma verbos reais:** “Basta”, “vale (a pena)”, “Preciso” (o modelo
  leu como nome próprio no início de citação), “alcançar” (futuro do subjuntivo) e, nos
  construídos, “segura”, “causa”, “começa”, “cantar”, “Canto”, “Olho”.
  - **Ausência de confirmação, e não confirmação de ausência:** ainda assim é ela que sustenta os
    alertas de tempo verbal.
  - **Três situações:** “segura” e “causa” têm a classe errada no modelo (ADJ); “Canto” e “Olho”
    também (NOUN); “começa”, “Basta” e “vale” estão como VERB no modelo, mas os filtros do núcleo
    não confirmam (causa a investigar na 2b).
- **`pode_ser_verbo` descarta finitos:** futuro do subjuntivo igual ao infinitivo (“alcançar”,
  “cantar”), porque o léxico também marca a forma como não finita; e a 1ª pessoa no início de
  frase lida como nome (“Preciso”, “Canto”). Aqui o erro custa caro: a estrutura poderia dizer
  “sem verbo”.
- **Consistência:** a validação mostra o mesmo padrão em números agregados (precisão 0,979;
  4 finitos com a classe errada pelo modelo).


### Fase 2b — reconhecimento verbal (08/10/2026)

Só `fonte/fonte/verbo.py` mudou no motor. As três operações continuam separadas. Cada mudança
corresponde a uma classe estrutural, verificada numa varredura de todas as 12.687 palavras dos
textos de desenvolvimento, e não só na amostra anotada. A varredura achou falsos positivos que a
amostra não mostrava, e eles foram corrigidos antes de qualquer consulta à validação.

**Mudanças:**

1. **`pode_ser_verbo` (recuperar verbos reais):**
   - `abre_oracao`: forma com leitura finita no léxico, núcleo de oração aberta por subordinante ou
     relativo (futuro do subjuntivo igual ao infinitivo: “quando ele cantar”, “o que a alcançar”).
     Pode saltar sujeito, negação, advérbio e clítico, mesmo com etiqueta errada. Não vale depois
     de preposição, nem para nome com determinante logo antes, nem com o “que” determinante de um
     nome (“Que posto queres?”), nem para palavras gramaticais.
   - `abre_frase`: forma com maiúscula abrindo a frase ou uma fala ou citação (depois de «, “, —
     ou :), seguida do que costuma seguir um verbo: objeto, pronome, subordinante ou infinitivo.
     Verbo conjugado logo depois faz da forma o sujeito (“Quaresma disse”); preposição, adjetivo
     ou advérbio fazem dela um nome (“Passo a passo”, “Morro abaixo”). Palavra com clítico
     (“falar-lhe”) conta como palavra.
2. **`certamente_verbo` (confirmação positiva, mantendo a precisão):**
   - `nominal_context`:
     - preposição regida pela forma sempre prova nome ou infinitivo (“no vão da porta”);
     - artigo e cópula só provam se o léxico admite leitura nominal ou não finita, ou se a cópula
       é ela mesma certamente verbo (“estava vazia”); a falsa cópula de “Uma nova era começa”
       não veta;
     - forma dependente sem sujeito que governa objeto ou oração é verbo, se o léxico não admite
       leitura não finita (“e vale a pena”; não “crime achar dinheiro”).
   - Sem confirmação do modelo:
     - nome do modelo precedido de determinante não é confirmado só pelo léxico (“A vida é
       longa”: lacuna nominal do léxico; 76 casos assim no desenvolvimento);
     - exceto clítico depois de palavra que o atrai (“não a sentia”).
   - Evidência forte, mesmo com etiqueta nominal do modelo:
     - `rege_infinitivo`: forma não gramatical seguida de infinitivo de verdade (minúsculo, por
       morfologia ou terminação -r); não depois de cópula, artigo ou preposição (“Venho explicar”;
       não “É preciso sair”);
     - `entre_sujeito_e_complemento`: forma do presente, minúscula, entre determinante + nome e um
       complemento que começa por determinante ou nome, concordando em número (“A garra segura o
       menino”, “O braço causa coceira”); sem determinante no complemento, a forma que concorda
       como adjetivo é adjetivo posposto (“a tarde inteira sozinha”).
3. **`ha_forma_verbal` (reconhecimento excessivo):** o léxico veta a palavra que ele conhece e
   nunca como finita (“Oh”, “perdão”, “romance”). É o mesmo veto da confirmação positiva.

**Alcance nas 12.687 palavras do desenvolvimento** (motor `7407ab5` → candidato):
- **`certamente_verbo`:**
  - +16, todos verbos reais, conferidos um a um;
  - −76: nomes que o léxico só conhece como verbo e cerca de 3 verbos que o modelo leu como nome
    depois de determinante, que passam a não confirmados.
- **`pode_ser_verbo`:** +18, sobretudo futuros do subjuntivo e infinitivos depois de subordinante.
- **`ha_forma_verbal`:** −36, nomes, interjeições e alguns infinitivos e gerúndios com clítico,
  que não são formas conjugadas.

**Métricas** (desenvolvimento só com textos publicados; a validação na consulta 1):

| Métrica | Desenvolvimento antes | Desenvolvimento depois | Validação antes | Validação depois |
|---|---|---|---|---|
| `certamente_verbo`: precisão (falsos positivos) | 0,978 (1) | 0,978 (1) | 0,979 (1) | 0,979 (1) |
| `certamente_verbo`: cobertura | 0,917 | 0,938 | 0,885 | 0,904 |
| `pode_ser_verbo`: cobertura | 0,958 | **1,000** | 0,962 | **0,981** |
| `pode_ser_verbo`: taxa em não verbais | 0,101 | 0,101 | 0,109 | 0,109 |
| `ha_forma_verbal`: cobertura | 0,958 | 0,958 | 0,904 | 0,904 |
| `ha_forma_verbal`: taxa em não verbais | 0,145 | **0,043** | 0,091 | **0,018** |
| Finitos: confirmados / não confirmados / classe errada no modelo | 44 / 3 / 1 | 45 / 2 / 1 | 46 / 2 / 4 | 47 / 2 / 3 |

O invariante “certo implica possível” vale. Com os 20 construídos, a cobertura de
`certamente_verbo` no desenvolvimento vai de 0,828 para 0,897.

**Consultas à validação:**
- **Consulta 1 (08/10):** só agregada, depois de a candidata estar definida pelo desenvolvimento.
  O hash da validação foi conferido antes (igual ao congelado). Todos os critérios atendidos.
  Nenhum ajuste depois dela.
- Restam 2 consultas.

**Regressão:**
- 29 conjuntos **idênticos** a `9f0f6d8` (IDs, destinos, classes, severidades, confianças). Nenhum
  alerta criado, eliminado ou alterado.
- Uma candidata intermediária criava 1 alerta de tempo verbal em predicativo (“estava vazia”, num
  texto de controle e no texto de terceiros). A causa foi identificada (cópula verdadeira) e
  corrigida antes da validação.
- Herança real igual (A 28, A com LT 28, C 15, C com LT 17).
- Corpus: precisão das pendências 97%, linguística 65/84, como antes.

**Testes:**
- FONTE 432:
  - `test_verbo.py`: os dois testes de caracterização da 2a foram atualizados, com justificativa
    (“segura” e “causa” confirmados; futuro do subjuntivo possível);
  - nova classe `VerbClassTests`, com 5 testes de classe e contraexemplos.
- Pacotes 45, contrato Python, Coerencia 25.
- Swift: contrato, decisões por livro, mesa, falsos positivos, encerramento.

**Limitações que permanecem:**
- Lacunas do léxico:
  - “Vão temor!”: o adjetivo “vão” não está no léxico, então segue como falso positivo de
    `certamente_verbo`;
  - “vida”: segue em `ha_forma_verbal`, porque o léxico só a conhece como verbo.
- `certamente_verbo` não confirma:
  - “Preciso falar-lhe” (o infinitivo com clítico foi lido como forma conjugada);
  - “Basta fechal-o” (grafia antiga);
  - “Canto” e “Olho” no início de frase.

  Os quatro ficam como “pode ser verbo”, de propósito.
- `pode_ser_verbo` aceita alguns infinitivos depois de “que” e subordinantes (“prevenir que
  curar”). É a direção conservadora: só faz a estrutura se abster.
- **Critério anterior `sole_verb`:** frase nominal sem nenhum verbo (“Grito no corredor.”, “Olho
  por olho.”) já era “pode ser verbo” e continua assim.
- Cerca de 3 verbos que o modelo lê como nome depois de determinante não clítico (“outras *dormia*”)
  perderam a confirmação. Ficam como possíveis.


### Fase 3 — núcleo de tempo e modo, sem mudança de comportamento (08/10/2026)

**Implementações antigas e responsabilidades:**

| Antes | Onde | Responsabilidade |
|---|---|---|
| `form` | `temporal` | classificação estrita (modelo + léxico, indicativo exigido; condicional, futuro, ambíguo) |
| `indicative_tense` | `verbo` | classificação estrita da narração (“passado”/“presente”); passado só pelo léxico |
| `event_tense` | `temporal` | recuperação de eventos (léxico, sintaxe, lema, 1ª do plural ambígua) |
| `sole_verb`, `verbal_para` | `temporal` | recuperação: verbo único da frase; “para” verbal |
| recuperação embutida em `analyze` | `analysis` | passado só no léxico na narração no presente |
| `imperfect`, `pluperfect` | `temporal` | morfologia: imperfeito; locução ter/haver + particípio |
| `imperfect_subjunctive` | `grammar` | modo: imperfeito do subjuntivo sem leitura no indicativo |
| `CONDITIONAL_ENDING`, `CONDITIONAL`, expressão dentro de `form` | `temporal`, `grammar` | terminação do condicional (três cópias) |
| `IMPERFECT_SUBJUNCTIVE` | `temporal`, `grammar` | terminação do imperfeito do subjuntivo (duas cópias) |
| `clause_tense` | `temporal` | tempo da principal de uma condicional (específico da relação; continua em `temporal`) |

**Arquitetura consolidada:** `fonte/fonte/tempo.py`, que depende só de `lexicon` e `verbo`.

| Responsabilidade | Onde fica |
|---|---|
| Morfologia | `TERMINACAO_CONDICIONAL`, `TERMINACAO_IMPERFEITO_SUBJUNTIVO`, `IMPERFECT_ENDING`, `IRREGULAR_IMPERFECT`, `imperfeito`, `mais_que_perfeito_composto` |
| Modo | `imperfeito_do_subjuntivo`; o modo do modelo é lido nas classificações |
| Forma finita ou não finita | `verbo.py` (Fase 2) |
| Classificação estrita | `tempo_estrito` e `tempo_narrativo` |
| Recuperação | `tempo_recuperado`, `passado_so_no_lexico`, `para_como_verbo`, `verbo_unico_da_frase` |
| Relação temporal entre orações e plano narrativo | continuam em `temporal.py` (`relations`, `conditionals`, `modality`, `sequence`, `past_plane`, `legitimate_present`, `narrator_frame`), consumindo o núcleo |

`verbo.pode_ser_verbo` importa `verbo_unico_da_frase` do núcleo de tempo. `DEPOIS_DE_PARAR`
passou para o núcleo.

**Diferenças semânticas preservadas (intencionais):**
- **`tempo_estrito` × `tempo_narrativo`:** a narrativa aceita o passado só pelo léxico, sem o
  indicativo do modelo. Há 97 casos assim no desenvolvimento (“Conheci-o”, “Era” no início).
  Ela exige o indicativo do modelo para o presente (separa o imperativo).
- **Imperfeito do subjuntivo em dois sentidos,** com a terminação compartilhada:
  - na correlação (`imperfeito_do_subjuntivo`), sem leitura no indicativo (“disse” não conta);
  - nas condicionais de `temporal`, a terminação + léxico finito, sem esse filtro, como antes.
- **A recuperação nunca é alvo de alerta sozinha.** A 1ª do plural ambígua vira passado só como
  âncora (“Passamos”: ambígua na estrita).

**Evidências:**
- **29 conjuntos:** idênticos a `9f0f6d8` (código 0) e iguais à Fase 2b **byte a byte** em
  alertas, mensagens, sugestões, metadados e avisos.
- **Equivalência palavra a palavra:** os dez classificadores (estrito, recuperado, verbo único,
  “para”, imperfeito, mais-que-perfeito, narrativo, imperfeito do subjuntivo, passado só no léxico
  e `clause_tense`) dão o mesmo resultado em `184ffbc` e na Fase 3 nas 12.687 palavras do
  desenvolvimento.
- **Herança real igual:** A 28 e 28; C 15 e 17.
- **Validação reservada:** não consultada (refatoração sem mudança de comportamento; restam 2
  consultas).

**Testes:**
- **FONTE 444:** novo `test_tempo.py`, com 12 testes:
  - estrito × recuperação × narrativo;
  - homógrafos presente/perfeito;
  - condicional e subjuntivo;
  - morfologia;
  - limitações registradas;
  - definição única.
- **Testes antigos:** dois trocaram só o caminho de importação (`form` e `sole_verb`).
- Pacotes 45, contrato Python, Coerencia 25.
- Swift: contrato, decisões por livro, mesa, falsos positivos, encerramento.
- **Uma falha de importação** (`IRREGULAR_IMPERFECT` em `temporal`) apareceu numa verificação de
  nomes não definidos e foi corrigida antes dos testes. Ela só se manifestaria na sugestão do
  imperfeito.

**Problemas encontrados que exigiriam mudança de comportamento** (registrados em
`LimitacoesRegistradas`; não corrigidos):
1. `imperfeito` dá positivo para **todo** futuro do pretérito, e não só para “-ríamos”: “faria”,
   “viajaria” e “construiríamos” terminam em “-ia”/“-íamos” (`IMPERFECT_ENDING`). Também dá positivo
   para o imperfeito do subjuntivo (“fosse”, “cantasse”), pela etiqueta `Tense=Imp` do modelo.
   - **Contrato real:** “qualquer imperfeito, de qualquer modo, e também o condicional por
     engano”, e não “imperfeito do indicativo”.
   - **Quem o usa:** `past_plane` (narração no presente) e a sugestão. `modal_imperfect` usa a
     mesma terminação, então “deveria” e “poderia” também passam.
   - **Verificação de 08/10:** o relatório ao autor da Fase 3 descreveu por engano “construíamos”
     (que é imperfeito do indicativo, corretamente classificado) como condicional. Os testes e
     este plano usam a forma certa, “construiríamos”.
   - Correção comportamental pendente.
2. `tempo_recuperado` ignora o modo do modelo. Subjuntivo e imperativo (“Fale com ela”, “Vamos
   embora”) saem “presente”, e um nome próprio também (“Quaresma”, pelo verbo único da frase).
   Isso pode servir de âncora indevida na sequência narrativa.
3. A política narrativa aceita o passado pelo léxico mesmo quando o modelo lê subjuntivo, desde
   que o léxico só tenha o passado. Os 97 casos do desenvolvimento são passados reais; o risco não
   foi medido.

**Limitações da Fase 2b, mantidas:**
- falso positivo residual de “Vão temor!”;
- verbos lidos como nome depois de determinante não clítico (“outras dormia”);
- permissividade de `pode_ser_verbo` com alguns infinitivos depois de “que”;
- frases nominais sem verbo, já aceitas pelo critério do verbo único;
- ambiguidades morfológicas sem decisão segura (“vira”, 1ª do plural, “-íamos”).

**Avaliação de risco** para o tempo verbal (408 decisões, 91%) e a correlação temporal:
- **Nesta fase:** nenhum, pela equivalência integral.
- **Numa mudança futura:**
  - o problema 2 (recuperação ignorando o modo) é o de maior alcance, porque alimenta a
    sequência narrativa;
  - o problema 1 afeta só a narração no presente (`past_plane`) e a sugestão do imperfeito.
- Qualquer mudança nesses pontos exige a mesma rotina da Fase 2b: varredura ampla, critérios na
  validação e comparação dos 29 conjuntos.


### Fase 4 — segmentação entre fala e narração, sem mudança de comportamento (08/10/2026)

**Verificação preliminar (pedida pelo autor).** Houve erro de descrição no relatório da Fase 3:
“construíamos” é imperfeito do indicativo e está classificado corretamente; o condicional é
“construiríamos”, a forma usada nos testes e no plano. Houve também erro real no componente,
maior do que o descrito: `imperfeito` dá positivo para todo futuro do pretérito (“faria”,
“viajaria”) e para o imperfeito do subjuntivo. O contrato real e a correção pendente estão no
problema 1 da Fase 3, acima.

**Inventário dos segmentadores:**

| Mecanismo | O que decide | Quem usa |
|---|---|---|
| `segments.classify` | papel de cada caractere: travessão e hífen por linha, aspas com papel configurável, itálico como pensamento, título | linguística, gramática, temporal, contexto (diálogo), repetição, Auditoria, máscaras da pipeline (`search`) |
| `analysis.narrative_masks` | leitura antiga: aspas sempre fala, travessão só no início do parágrafo, itálico oculto | `analysis.analyze` chamado direto (testes); na pipeline, só os fechamentos de aspas (pontuação de diálogo) e os avisos de aspas |
| `temporal.SPEECH_OPENING` | parágrafo que abre com travessão ou hífen **seguido de espaço** sai da sequência narrativa | `temporal.events` |
| “texto anterior termina em travessão” | inciso de fala | `grammar` (pronome reto como objeto), `languagetool` (maiúscula depois de inciso) |
| caractere vizinho é travessão | começo e retomada de inciso | `editorial/context` (diálogo contextual) |
| tabela de aspas em `analysis` | aspas de destaque | pontuação de diálogo |

**Representação compartilhada** (`fonte/fonte/segments.py`):
- o papel de cada caractere na posição original (`narracao`, `dialogo`, `pensamento`,
  `separador`, `titulo`), com `spans` para os trechos;
- `percorrer_aspas(blocks, repete_abertura)`: estado das aspas entre parágrafos, fechamentos e
  avisos;
- `marcar_travessoes(text, roles, por_linha, hifen)`;
- `abre_fala(texto, exige_espaco)` e `termina_em_travessao(prefixo)`;
- `TRAVESSOES`, `ABRE_ASPAS` e `FECHA_ASPAS` como constantes únicas.

O núcleo não julga a pontuação. `classify` e `narrative_masks` são montados com essas peças.

**Diferenças preservadas, com os comportamentos contraditórios encontrados.** Nenhuma foi escolhida
como certa; cada uma está em `tests/test_segmentacao.py::DiferencasPreservadas`.
1. **Hífen de diálogo** (“- Vamos - disse”): fala em `classify`, narração em `narrative_masks`.
2. **Fala que começa numa linha do meio do parágrafo:** só `classify`, por causa da correção de
   07/10 (`por_linha`).
3. **Aspas com `quotes_role = narracao`:** `classify` as trata como narração, mas os fechamentos
   de `narrative_masks`, usados pela pontuação de diálogo, continuam tratando-as como fala.
4. **Aspa que reabre a mesma fala no início de um parágrafo, sem fechar** (aspas retas): a fala
   continua em `narrative_masks` (`repete_abertura`); em `classify`, a aspa fecha a fala anterior.
5. **Abertura de fala:** `classify` aceita “—Vamos” sem espaço; `temporal.events` só tira da
   sequência o parágrafo com o sinal **seguido de espaço** (`abre_fala(exige_espaco=True)`).
   Num parágrafo “—Fala — disse ela”, o inciso entra na sequência narrativa; com espaço, não.
6. **Itálico:** em `classify`, vira pensamento conforme `italic_thoughts`; em `narrative_masks`,
   é ocultado conforme `protect_italics` (opção `--incluir-italico`). São configurações
   diferentes.
7. **Inciso:** `grammar` e `languagetool` olham o texto anterior até o travessão (ignorando
   espaços); `context` olha o caractere vizinho do trecho. Na prática, são equivalentes.

**Código duplicado removido:**
- três tabelas de aspas e duas máquinas de estado de aspas viraram uma;
- dois laços de travessão viraram um, com modos;
- `SPEECH_OPENING` e três testes de travessão escritos à mão passaram a usar o núcleo.

**Evidências:**
- **Fotografia caractere a caractere** de `classify` (5 configurações) e `narrative_masks` (com e
  sem itálico): desenvolvimento, corpus, A, B, C, texto de terceiros e 18 casos-limite, num total
  de 189 combinações, **idênticas** antes e depois.
- **29 conjuntos:** idênticos a `9f0f6d8` (código 0) e iguais à Fase 3 em alertas, metadados e
  avisos.
- **Herança real igual:** A 28 e 28; C 15 e 17.
- **Validação reservada:** não consultada.

**Testes:**
- FONTE 459: novo `test_segmentacao.py`, com 15 testes:
  - travessão, aspas e papel das aspas;
  - inciso, ação depois de fala, narração antes e depois, duas falas;
  - quebra de linha, hífen de diálogo, palavra composta;
  - pensamento em itálico, travessões desligados;
  - peças compartilhadas e diferenças preservadas.
- Pacotes 45, contrato Python, Coerencia 25.
- Swift: contrato, decisões por livro, mesa, falsos positivos, encerramento.

**Riscos para a Fase 5** (verbos de elocução):
- As listas de verbos de fala alimentam o diálogo contextual (91% em 32 decisões), a pontuação de
  diálogo (78% em 9), a vírgula entre sujeito e verbo, o pronome reto como objeto, a frase cortada
  (`complement_verb`) e listas temporais (`REPORTING`, `NARRATOR_THAT`). Unir listas muda o que
  cada regra reconhece; é preciso medir regra por regra.
- A pontuação de diálogo depende dos fechamentos da leitura antiga (`narrative_masks`, diferenças
  3 e 4). Mudar a lista de fala sem mexer na segmentação mantém essa dependência; unificar a
  segmentação de verdade seria mudança de comportamento, fora da Fase 5.
- **Sobreposição de sentidos:** “dizer” é de fala; “sentir” e “achar” são de complemento
  (`COMPLEMENT_VERBS`). A Fase 5 não pode misturá-los.

### Fase 5 — verbos de fala, pensamento e percepção, sem mudança de comportamento (08/10/2026)

**Inventário das listas** (antes da Fase 5):

| Lista | Onde | Reconhece por | Verbos | Quem usa | Efeito |
|---|---|---|---|---|---|
| `SPEECH` + `IRREGULARES_DE_FALA` | `analysis` | lema do modelo **ou** forma (radical ≥ 3 letras + terminação; 11 formas de dizer/pedir) | 63 | pontuação de diálogo (verbo depois de aspas e vírgula), diálogo contextual (ação depois da fala e retomada depois do inciso), pronome reto como objeto, vírgula sujeito-verbo (inciso), crase do LanguageTool | o verbo da lista **suprime** o alerta, exceto na retomada do diálogo contextual, em que é condição |
| `forma_de_fala` | `analysis` | só a forma | os mesmos | diálogo contextual (palavra logo após o travessão), crase do LanguageTool | idem |
| `verb_de_fala_form` | `grammar` | lema ou forma, com a forma contada duas vezes | os mesmos | vírgula sujeito-verbo (duas verificações) | suprime |
| `COMPLEMENT_VERBS` + `complement_verb` | `grammar` | forma (inciso **ou** radical destes) | 17 + os do inciso | frase cortada (“Que” maiúsculo depois de reticências) | **condição** do alerta |
| `REPORTING` | `temporal` | só lema | 18 | condicional sem hipótese (discurso indireto fica de fora), função do presente (verdade geral) | suprime |
| `NARRATOR_THAT` | `temporal` | forma da 1ª pessoa do singular + “que” | 16 | comentário do narrador (presente legítimo) | suprime |
| `NARRATOR_TELLS` | `temporal` | “vou” + verbo | 11 | comentário do narrador | suprime |
| lista em linha de “poder” + infinitivo | `temporal` | só lema | 5 | presente legítimo (“posso garantir”) | suprime |
| `DATIVE` | `grammar` | lema | 31 | crase dativa | não é lista de fala: verbos com objeto indireto; fica fora |
| `STATE`, `STATIVE` | `temporal` | lema | — | estado mental e estados | não é lista de fala; fica fora |

**Diferenças entre as listas** (todas preservadas): o inciso aceita pensamento e verbos que só são
fala pelo contexto; os que pedem “que” somam crença e percepção ao inciso; o relato tem
conhecimento e percepção, mas não “perguntar” nem os modos de dizer (“murmurar”); o comentário
do narrador é de formas, não de lemas; o reconhecimento pela forma só existe no inciso e nos que
pedem “que”.

**Categorias** (do verbo, não do uso), em `elocucao.CATEGORIAS`, a única fonte:
- **elocução** (55 verbos): dizer, perguntar, prometer, jurar, contar, narrar, atestar…;
- **pensamento** (18): pensar, refletir, lembrar, achar, saber, crer, supor, querer…;
- **percepção** (5): sentir, perceber, ouvir, notar, observar;
- **só pelo contexto** (11): continuar, completar, interromper, terminar, brincar, chamar, ler,
  cantar, começar, mostrar, apresentar.
Admitir oração com “que” não é categoria: é o perfil `PEDEM_QUE`.

**Perfis preservados** (cada um igual à lista antiga): `INCISO` (+ `INCISO_IRREGULARES`),
`PEDEM_QUE`, `RELATO`, `COMENTARIO_DO_NARRADOR` (lema → forma da 1ª pessoa), `NARRADOR_ANUNCIA`,
`ATESTA`. Nenhum perfil é definido pela união de outros nem por categoria: mudar isso muda o que
as regras reconhecem.

**Código duplicado removido:**
- o reconhecimento por radical + terminação existia duas vezes (`forma_de_fala` e
  `complement_verb`, com `len(v) > 4` no lugar de radical ≥ 3): agora é `pelo_radical`;
- `verb_de_fala_form` somava a forma escrita a `verbo_de_fala`, que já a olha em minúsculas;
  `casefold` de `lower` é igual a `casefold` em todo o Unicode, então a soma era redundante;
- `TERMINACOES` passou de `analysis` para o núcleo (o tempo verbal também usa);
- listas em linha do `temporal` passaram a vir dos perfis.

**Inconsistências linguísticas encontradas (sem correção, mudariam alertas):**
1. **Reconhecimento pela forma sem léxico:** pelo radical, 1.178 formas passam como verbo do
   inciso e 1.466 como verbo que pede “que”; 52 e 67 delas também são nome ou adjetivo (“grito”,
   “chama”, “canto”, “fala”, “completa”), e há formas de outro verbo com o mesmo radical
   (“sentou”, de sentar, passa como “sentir”; “contem”, de conter, como “contar”). No inciso
   isso só suprime alertas; na frase cortada é condição do alerta.
2. **Formas que o radical não alcança:** mais-que-perfeito (“dissera”, “falara”), condicional
   (“diria”), imperfeito do subjuntivo (“dissesse”), futuro do subjuntivo (“disser”), “dirão”.
   Só o lema do modelo as reconhece. “ler” tem radical curto e também depende do lema.
3. **Mecanismos diferentes:** o inciso aceita a forma quando o lema falha; o relato, o comentário
   e “poder” + infinitivo só aceitam o lema.
4. **Percepção pela metade:** `PEDEM_QUE` tem “sentir” e “perceber”, mas não “notar”, “ver” nem
   “ouvir”, que também pedem “que”; o inciso tem “observar” e não os outros.
5. **Ambiguidades de sentido:** “esperar” (ter esperança ou aguardar) e “chamar”, “terminar”,
   “continuar” só são fala no inciso.

**Evidências:**
- **Fotografia por palavra**, antes e depois, **idêntica**: as funções de forma em todas as
  857.387 formas do léxico (minúsculas, inicial e caixa alta) e, em 223.624 palavras em contexto
  (desenvolvimento, corpus e textos públicos), o verbo de fala, o relato pelo lema, o comentário
  do narrador, o presente legítimo e a função do presente.
- **Testes por consumidor** (`PorConsumidor`): passam no código antigo (`f01bd9e`, com as funções
  antigas no lugar das novas) e no novo.
- **29 conjuntos:** idênticos a `9f0f6d8` (código 0; controle negativo dá 1) e iguais à Fase 4 em
  alertas, metadados e avisos. Por isso não mudam o diálogo contextual (91% em 32 decisões), a
  pontuação de diálogo, os incisos, a vírgula sujeito-verbo, o pronome reto, a frase cortada nem
  o tempo verbal.
- **Herança real igual:** A 28 e 28; C 15 e 17.
- **Validação reservada:** não consultada.

**Testes:** FONTE 470 (novo `test_elocucao.py`, 11 testes: listas antigas, categorias por perfil,
inciso por lema e por forma com elocução, pensamento, percepção, verbos que pedem “que” e ações,
radical curto, frase cortada, relato, comentário e anúncio do narrador, fonte única). Pacotes 45,
contrato Python, Coerencia 25; Swift: contrato, decisões por livro, mesa, falsos positivos,
encerramento e correções; build do app.

**Pendência mantida:** o defeito de `imperfeito` (problema 1 da Fase 3) continua sem correção:
confunde o futuro do pretérito (“faria”) com o imperfeito do indicativo (“fazia”) e não separa o
imperfeito do subjuntivo. Fica para uma fase controlada com mudança de comportamento.

**Riscos para a Fase 6** (deduplicação FONTE × LanguageTool):
- A crase do LanguageTool é suprimida pela forma do inciso (`forma_de_fala`); a deduplicação
  muda a ordem e a origem dos alertas, e a supressão precisa continuar antes dela.
- A deduplicação compara trechos e IDs; o ID não inclui a regra, mas a herança no app inclui.
  Mudar a origem de um alerta pode perder decisões herdadas (`legacyContentKey`).
- A maiúscula depois de inciso do LanguageTool usa `termina_em_travessao`; a do FONTE usa o
  caractere vizinho. Deduplicar exige saber qual é a leitura de cada um.

### Fase 6a — deduplicação centralizada, sem mudança de comportamento (08/10/2026)

**Dois fenômenos separados.** *Supressão linguística*: a regra decide que a evidência não basta
(fica na regra). *Deduplicação*: duas fontes apontam o mesmo trecho e só uma ocorrência aparece
(agora em `fonte/fonte/deduplicacao.py`).

**Mecanismos de deduplicação** (descartes medidos nos textos A, B, C e X, com e sem LT):

| Mecanismo (onde estava → agora) | Classes | Critério de equivalência | Prevalece | IDs e decisões | Estatística | Descartes reais |
|---|---|---|---|---|---|---|
| LT sob regra linguística (`pipeline.linguistic` → `languagetool_sob_regras_linguisticas`) | LT × espaçamento, pontuação duplicada, maiúscula, construção inválida, vocativo, “que” tônico, palavra dobrada | um caractere em comum no parágrafo, **qualquer fenômeno** | FONTE | o LT descartado nunca chega ao relatório: não tem ID nem decisão | a classe do LT perde a amostra | 0 |
| Gramática sob LT (`grammar.analyze(skip=…)` → `gramatica_sob_languagetool`) | crase, homófonos, concordância, regência, vírgula, correlação, frase cortada, locuções × qualquer alerta do LT | um caractere em comum, **qualquer fenômeno** | LT | o alerta do FONTE existe sem o LT e some com ele: ID e chave de conteúdo mudam conforme o LT está ligado | a classe do FONTE perde a amostra quando o LT está ligado | 1 (B com LT: crase × `CRASE_CONFUSION`, mesmo trecho e mesma correção) |
| Relação que repete o tempo verbal (`pipeline.morphosyntactic` → `relacao_que_repete_tempo_verbal`) | coerência temporal × tempo verbal | o outro verbo da relação tem exatamente o trecho do alerta de tempo verbal e o verbo apontado está no tempo da narração | tempo verbal | nenhum | — | 0 |
| Tempo verbal sob relação (`pipeline.morphosyntactic` → `tempo_verbal_sob_relacao`) | tempo verbal × coerência temporal | o alerta de tempo verbal está contido no trecho da relação | relação | nenhum | `narrative_tense` perde a amostra | 2 (A, com e sem LT) |
| Mesmo ID entre etapas (`pipeline.run` → `mesmo_id`) | todas | ID igual e resultado idêntico (resultado diferente interrompe) | o primeiro | nenhum | — | 0 |
| Auditoria sobre alertas anteriores (`auditoria_ia`, agora com `sobrepoe`) | Auditoria × todas | um caractere em comum | etapas anteriores | o descarte fica contado em `alerta_existente` | — | não medido (sem API) |

**Precedências internas de um mesmo detector** (ficam no detector):
- `temporal.PRECEDENCE`: no mesmo trecho, vence a relação mais específica; as relações antigas só
  ficam onde nenhuma da lista apontou. Descartes reais: 0.
- `grammar`: no mesmo trecho exato, vence a primeira regra na ordem de `CHECKS`. Descartes reais: 0.
- Auditoria (`repetido`) e repetição: um alerta por trecho dentro do próprio detector.

**Supressões linguísticas (inalteradas, não são deduplicação):**
- **LT:** categorias e tipos ignorados (estilo, registro, regionalismo); 2 regras ignoradas; e
  filtros por regra:
  - espaço depois de reticências;
  - maiúscula depois de vírgula em vocativo ou dois-pontos;
  - auxiliar com gerúndio;
  - “todos” + particípio;
  - parônimo antes de gerúndio;
  - vírgula em locução e “além de” integrado;
  - palavra repetida em onomatopeia;
  - grafia de interjeição, palavra cortada, nome ou itálico;
  - crase depois de verbo de fala;
  - maiúscula depois de travessão.

  Também reduz a confiança de palavra recorrente e de sugestão distante.
- **FONTE:** escopo de cada regra (`SCOPES`), listas e rótulos, e os filtros de cada regra.
- **Não são remoção:** o destino `diagnostico` da Política (fica no relatório) e o descarte de
  trecho inexistente (`ocorrencias_descartadas`, validação).

**Código obsoleto:**
- **Removido:** o parâmetro `skip` de `grammar.analyze`. O filtro passou para depois da regra, o
  que é equivalente: um trecho igual a um descartado também tocaria o mesmo alerta do LT.
- **Mantido, porque não é morto:**
  - a geração antiga de relações temporais (`conditional_future`, `simultaneous_present`,
    `ambiguous_simultaneity`, `coordinated_past_present`). Não apareceu nos 29 conjuntos, mas
    `test_temporal`, `test_diagnostic`, o relatório de referência `examples/Temporal` e a
    verificação do motor empacotado (`packaging/lume_engine.py`, `conditional_future`) a exigem.
    Retirá-la mudaria resultados.
  - o ramo de palavra dobrada em `analysis.analyze`. A pipeline não o usa, mas a chamada direta
    (sem `enabled_rules`) usa, e `test_fonte` o exige.

**Evidências:**
- **29 conjuntos:** idênticos a `9f0f6d8` (código 0) e iguais à Fase 5 em alertas, mensagens,
  metadados e avisos.
- **Herança real igual:** A 28 e 28; C 15 e 17.
- **Testes:**
  - FONTE 483: novo `test_deduplicacao.py`, com 13 testes que cobrem intervalos, o critério atual
    de cada mecanismo, limitações registradas, LT ligado no mesmo trecho e em outro, LT desligado,
    LT indisponível e fonte única;
  - pacotes 45, contrato Python, Coerencia 25;
  - Swift: contrato, decisões por livro, mesa, falsos positivos, encerramento e correções;
  - build do app.

**Constatações:**
1. Hoje a coincidência de trecho basta: nenhum mecanismo entre fontes compara o fenômeno.
2. A precedência é invertida entre etapas: na linguística vence o FONTE; na morfossintática, o LT.
3. Com o LT ligado, um alerta próprio do FONTE some e outro do LT aparece no lugar. As decisões
   tomadas numa leitura sem o LT não passam para a leitura com o LT, e vice-versa.
4. Nos relatórios finais, quase não há sobreposição visível: só repetição próxima × tempo verbal
   (fenômenos diferentes, mantidos separados) e repetição × repetição (o mesmo detector).
5. O LT indisponível, quando pedido, interrompe a análise sem relatório. Com o LT desligado, o
   FONTE funciona sozinho.

### Fase 6b — levantamento e estratégia (aguarda aprovação; nada executado)

**Duplicatas reais encontradas:**
- **Crase × `CRASE_CONFUSION`** (B com LT, 1 caso):
  - mesmo trecho, mesma correção (tirar o acento antes de verbo), mesmo fenômeno;
  - hoje vence o LT.
- **Tempo verbal × relação temporal** (A, 2 casos):
  - o mesmo desvio de tempo do mesmo verbo; a relação explica melhor;
  - mecanismo interno do FONTE, já correto.
- **Outras sobreposições LT × FONTE:** nenhuma nos 4 textos. Elas só existem hoje como risco (os
  dois mecanismos descartam qualquer fenômeno no trecho).

**Proposta:**
1. **Equivalência por família, explícita e pequena.** Só são duplicatas as regras do LT e do FONTE
   da mesma família, no mesmo trecho (ou um contido no outro), com correção compatível ou sem
   correção:
   - crase;
   - pontuação duplicada;
   - espaçamento;
   - maiúscula no início de frase;
   - palavra dobrada.

   Fora disso, os dois alertas ficam. Isso muda o comportamento: fenômenos diferentes no mesmo
   trecho voltariam a aparecer, embora nos 4 textos não haja nenhum.
2. **Ocorrência principal por família:** o FONTE, nas famílias em que a regra própria é específica
   e funciona igual sem o LT. Argumento central: o ID fica o mesmo com e sem o LT. No LT, a crase
   cai em `languagetool:gramatica` (60% em 30 decisões, misturando todos os fenômenos do LT); não há
   medida específica de crase de nenhum dos lados. Sem família definida, nenhuma precedência.
3. **Identidade e decisões:**
   - o principal guarda seu ID e passa a levar `detectores` (as fontes que o apontaram) e
     `absorvidos`, com ID, regra, classe, origem, categoria e trecho de cada ocorrência
     representada (campo novo e opcional; relatórios antigos não têm);
   - no app, depois da chave de conteúdo e da chave antiga, o alerta sem decisão herda a decisão de
     um absorvido, pela chave de conteúdo dele;
   - se os absorvidos tiverem decisões diferentes, nada é herdado e o alerta mostra que há decisões
     divergentes, para escolha explícita;
   - não há transferência entre famílias diferentes.
4. **Métricas:**
   - a classe do principal não muda (crase continua crase);
   - o absorvido não soma amostra à própria classe nem à do principal, e o registro de detectores
     permite medir depois;
   - recalibração possível, registrada à parte: `languagetool:gramatica` mistura fenômenos e pode
     conter casos de crase.
5. **LT: categoria, confiança e severidade:**
   - gravar a categoria e o tipo originais (`languagetool: {regra, categoria, tipo}`);
   - classe e confiança como estão, para não perder as medições;
   - **severidade sem mudança nesta fase.** Hoje todo alerta do LT sai “provável erro”, inclusive
     espaçamento e parênteses sem par. Rebaixar para “atenção editorial” muda rótulo, cor e filtro
     no app. Não muda destino, IDs nem herança. Impedimento: nenhuma classe do LT atinge o limiar
     hoje, mas a mudança impediria a ortografia do LT de ser impeditiva no futuro, porque a regra
     exige severidade de erro. Precisa de aprovação separada.
6. **LT indisponível:** manter a interrupção explícita, ou seguir só com o FONTE e um aviso. É
   decisão do autor.

### Fase 6b — execução, parte 1: deduplicação (08/10/2026)

**Decisões do autor:**
- **D1:** famílias aprovadas, com equivalência de fenômeno **e** de correção; sem precedência
  universal; na dúvida, os dois alertas ficam.
- **D2:** `detectores` e `absorvidos`, herança pela identidade principal e depois pelas absorvidas;
  conflito registrado e mostrado, nunca escolhido.
- **D3:** só os campos originais do LanguageTool; severidade, confiança, classe e destino iguais.
- **D4:** o FONTE segue sem o LanguageTool indisponível, com a análise marcada como parcial.

**Implementação:**
- `deduplicacao.consolidar`, depois de todas as etapas e antes da política. Saem os dois filtros
  por sobreposição (LT sob regra linguística, gramática sob LT).
- Famílias (`FAMILIAS`) com as regras do FONTE e os IDs do LanguageTool 6.6, conferidos no servidor
  embutido com frases de teste:

  | Família | FONTE | LanguageTool | Principal |
  |---|---|---|---|
  | crase | `crase` | `CRASE_CONFUSION`, `CRASE_CONFUSION_2`, `ERROS_DE_CRASE_MARCOAGPINTO`, `SAIR_AS_RUAS` | FONTE |
  | pontuação duplicada | `pontuacao_duplicada` | `DOUBLE_PUNCTUATION`, `DOUBLE_PUNCTUATION_XML` | FONTE |
  | espaçamento | `espacamento` | `ESPACO_DUPLO`, `WHITESPACE_RULE`, `SPACE_BEFORE_PUNCTUATION`, `SPACE_BEFORE_PUNCTUATION2`, `COMMA_PARENTHESIS_WHITESPACE` | FONTE |
  | maiúscula inicial | `capitalizacao_contextual` | `UPPERCASE_SENTENCE_START` | FONTE |
  | palavra duplicada | `palavra_consecutiva` | `PORTUGUESE_WORD_REPEAT_RULE`, `WORD_REPEAT_RULE` | FONTE |

- **Equivalência:**
  - mesma família, trecho em comum e o mesmo texto corrigido do parágrafo;
  - a palavra dobrada do FONTE, sem sugestão, tem correção implícita (ficar com uma palavra);
  - “Dois pontos finais” (pode ser reticências) não tem correção comparável e nunca se junta.
- **Precedência por família, com motivo registrado no código:** em todas, o FONTE mantém a mesma
  identidade com e sem o LanguageTool. Não há medida específica de crase de nenhum dos lados
  (`languagetool:gramatica` mistura fenômenos).
- **Fenômenos diferentes no mesmo trecho ficam separados.** Exemplo conferido no servidor: em
  “a a”, o LT propõe “à” (contração) e o FONTE aponta palavra dobrada.
- **App:** campos opcionais `detectores` e `absorvidos` (validados: mesmo parágrafo e dentro do
  texto). A herança segue esta ordem:
  1. a identidade própria (ID e conteúdo, inclusive a chave antiga);
  2. as absorvidas pelo ID (reanálise e edições pelo Lume);
  3. as absorvidas pela chave de conteúdo (memória do livro).

  Decisões divergentes não são escolhidas: viram conflito (`conflitos`, no arquivo de decisões e
  na memória do livro), mostrado no inspetor, contado no status e lembrado no diálogo de
  encerramento. A decisão própria nunca é sobrescrita. Os critérios de encerramento não mudam.

**Diferenças nos 29 conjuntos** (contra a Fase 6a e a linha de base): **uma**, em B com o
LanguageTool.

| Campo | Antes | Depois |
|---|---|---|
| Ocorrência anterior | `f90940b991a9fb77`, LanguageTool `CRASE_CONFUSION`, classe `languagetool:gramatica`, pendência, provável erro, confiança média | absorvida em `absorvidos` (ID, regra, classe, origem e trecho preservados) |
| Ocorrência principal | — (a crase do FONTE caía sob o LT) | `b59c213854d4c288`, `crase`, classe `crase`, pendência, provável erro, confiança alta: o mesmo ID, com os mesmos campos, de B sem LT |
| Equivalência | — | família crase, mesmo trecho, a mesma correção (tirar o acento antes de verbo) |
| Decisões | nenhuma salva para os dois IDs | herança simulada nos relatórios reais: decisão no LT antigo → principal (livro e reanálise); decisão própria preservada com conflito registrado |
| Métricas | uma amostra possível para `languagetool:gramatica` | para `crase`; destinos iguais (4 pendências, 14 observações) |

Metadados: `deduplicacao` (1 absorvida). As contagens por etapa descontam a absorvida
(linguística 4 → 3); a morfossintática ganha a crase (2 → 3).
Os outros 28 conjuntos ficam idênticos. Herança real igual: A 28 e 28; C 15 e 17.

**Testes:**
- FONTE 487 (`test_deduplicacao.py`, 17 testes):
  - equivalência: crase e espaço com trechos parciais, palavra dobrada;
  - mesmo trecho com outro fenômeno, outra correção, sem correção, sem caractere comum;
  - consolidação com identidade, classe e registro;
  - pipeline com LT simulado: mesmo fenômeno, outro fenômeno no mesmo trecho, mesma identidade com
    e sem o LT.
- Pacotes 45, contrato Python, Coerencia 25.
- Swift: as 6 verificações anteriores e a nova `DeduplicationCheck`, que cobre:
  - herança direta e por absorvida, inclusive pela chave antiga;
  - decisões compatíveis, incompatíveis e direta divergente;
  - persistência do conflito;
  - fenômenos diferentes, reanálise e arquivos antigos.
- Build do app.

**Pendências registradas:**
- A severidade automática “provável erro” do LT (D3) será revista em fase própria.
- A relação temporal que absorve o tempo verbal (Fase 6a) ainda não registra `absorvidos`. É
  FONTE × FONTE, e o alerta absorvido nunca apareceu, então não há decisão a perder.

### Fase 6b — execução, parte 2: categoria original do LanguageTool (08/10/2026)

- **Mudança:** cada alerta do LT leva `languagetool: {regra, categoria, tipo}`, como o servidor
  informou; a ocorrência absorvida também o guarda. Severidade, confiança, classe e destino não
  mudam.
- **Diferenças nos 29 conjuntos:** só o campo novo, em 16 alertas do LT (B 3, C 2, X 11) e no
  absorvido de B. Mais nada. Herança igual: A 28 e 28; C 15 e 17.
- **Para a revisão futura da severidade (D3, sem mudança agora).** Nos relatórios atuais, todo
  alerta do LT é “provável erro”:

  | Tipo | Categoria do LT | Alertas | Classe | Confiança | Destino |
  |---|---|---|---|---|---|
  | `misspelling` | `TYPOS` | 9 | `languagetool:ortografia` | baixa | informação |
  | `typographical` | `TYPOGRAPHY`, `PUNCTUATION` | 4 | `languagetool:gramatica` | média | pendência |
  | `uncategorized` | `PUNCTUATION`, `MISC` | 2 | `languagetool:gramatica` | média | pendência |
  | `grammar` | `GRAMMAR` | 1 | `languagetool:gramatica` | média | pendência |

  - Seis dos sete alertas de `languagetool:gramatica` são tipografia, pontuação ou sem categoria.
    A classe mistura fenômenos, e a medição dela (60% em 30 decisões) também.
  - A ortografia é reconhecida por dois critérios diferentes: a confiança usa o tipo
    (`misspelling`/`TYPOS`); a classe usa o nome da regra (`MORFOLOGIK`/`SPELLING`). Hoje coincidem.
- **Testes:** FONTE 488 (`CategoriaOriginalTests`: o campo existe; severidade, confiança e classe
  ficam iguais depois do contrato e da política).

### Fase 6b — execução, parte 3: LanguageTool indisponível (08/10/2026)

**Antes:** com o corretor pedido e fora do ar (embutido que não inicia, servidor externo que não
responde ou que cai no meio), a análise parava sem relatório.

**Agora (D4):**
- **Motor:**
  - o FONTE segue sem o corretor. `LanguageToolIndisponivel` (subclasse de `ValueError`) separa a
    indisponibilidade dos erros de configuração; porta inválida continua sendo erro;
  - nenhum alerta do corretor entra, nem os de parágrafos anteriores à falha;
  - `metadata.analise_parcial.ausente` (etapa, componente, motivo), `languagetool_status:
    "indisponivel"` e `ausente` na etapa linguística;
  - aviso “Análise parcial: …”, que diz o que não foi verificado.
- **CLI:**
  - a falha ao iniciar o embutido é passada à pipeline (`languagetool_falha`);
  - os metadados dizem `languagetool: false`, `languagetool_pedido: true` e origem nula;
  - a última linha diz “INDISPONÍVEL — análise parcial”; o código de saída é 0.
- **App:**
  - aviso de análise parcial na mesa e em Etapas e alcance;
  - a etapa mostra “sem o LanguageTool (indisponível)”;
  - o título leva “(análise parcial)”;
  - o diálogo de encerramento avisa.
- **Encerramento:**
  - o de uma análise parcial vai para um registro próprio (`<sha256>-parcial.json`, com
    `analise_parcial_sem`) e só vale para análise com o mesmo alcance;
  - um encerramento completo anterior não é tocado nem passa a valer para a parcial;
  - registros antigos, sem o campo, valem só para a análise completa;
  - os critérios de encerramento não mudam.

**Campos só na falha:** relatórios completos não ganham nenhum campo. Os 29 conjuntos são
**idênticos** aos da parte 2, e a herança real é igual à linha de base (A 28 e 28; C 15 e 17), com o
código Swift atual.

**Teste real, sem simulação:**
- CLI sobre o texto X com `--languagetool --porta-lt 9` (sem servidor);
- código de saída 0, relatório parcial com motivo, e os mesmos 39 alertas da análise sem o LT;
- o contrato Swift lê o relatório.

**Testes:**
- FONTE 493: `test_languagetool_indisponivel.py`, com 6 testes:
  - servidor fora do ar;
  - queda depois de alguns parágrafos;
  - falha ao iniciar;
  - servidor funcionando, sem marca de parcial;
  - porta inválida;
  - CLI com o embutido que não inicia.

  O teste da 6a que fixava a interrupção saiu (mudança aprovada).
- Pacotes 45, contrato Python, Coerencia 25.
- Swift: as 7 verificações e a nova `PartialAnalysisCheck`, que cobre o relatório, a etapa, o
  encerramento separado, o registro e a compatibilidade.
- Build do app.

### Fase 7a — parecer definitivo das regras (08/10/2026; nenhuma regra alterada)

**Pergunta central:** o fenômeno é relevante, generalizável e detectável com precisão suficiente?

#### Evidências, em quatro categorias separadas
1. **Funcionamento** (corpus de desenvolvimento, 3.978 palavras, escrito junto com as regras):
   - 97% de precisão nas pendências, 0 alarmes falsos na fila;
   - 9 alarmes fora da fila (6 de tempo verbal, 2 de repetição, 1 de estrutura);
   - mede o funcionamento, não o uso real.
2. **Regressão:** os 29 conjuntos da Fase 6b (`build/fase6b3`) são a nova linha de comparação.
3. **Generalização em textos independentes:** os 3 romances de desenvolvimento do
   `~/Lume-evidencia`, com cerca de 202 mil palavras de prosa editada; a validação ficou intocada.
   - **Método:** FONTE sem o LanguageTool; contagem por regra e leitura de amostras.
   - **Confusores, que limitam a leitura:**
     - grafia anterior a 1943 (“della”, “póde”, “sahir”): desorganiza o modelo e o léxico e infla
       concordância, crase dativa, variação de nome, homófonos e acentuação;
     - falas com “--”, que a segmentação não reconhece: falas analisadas como narração, o que infla
       tempo verbal e coerência temporal;
     - narrador do século XIX que comenta no presente.
   - **Uso:** só para **classes de alarme falso** que não dependem desses confusores. Não serve
     como medida de precisão.
4. **Decisões reais:** `medir_precisao.py`, com 650 decisões únicas em 6 livros. São as mesmas da
   Política v2; não houve decisões novas. Com menos de 20 decisões, o número é só indicação.

Disparos reais = relatórios de A, B, C e X da Fase 6b (com o LT). “Indep.” = os 3 romances.
Núcleos: V verbo, T tempo, S segmentação, E elocução, D deduplicação, L léxico, M modelo spaCy.

#### Veredictos individuais

| Regra (subtipos) | Fenômeno | Nat. | Implementação · núcleos | Decisões (precisão) | Disparos A/B/C/X | Indep. (amostra) | Alarmes falsos conhecidos | Risco de FN | Sobreposição FONTE · LT | Custo | Destino v2 | Veredicto |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `tempo_verbal` | verbo fora do tempo da narração | E | geral + exceções · V T S E M | 416 (90%); média 408 (91%), baixa 8 (0%) | 12/0/6/16 | inflado pelos confusores | comentário do narrador, verdade geral | médio | coerência temporal (dedup interna) · nenhuma | alto (exceções) | pendência (média), observação (baixa) | **Manter** |
| `estrutura`: fragmento | frase sem verbo finito | E | pilha de exceções · V M | 28 (29%); média 18 (39%), baixa 10 (10%) | 0/1/4/1 | 9 a 48 por livro; suspensões e elipses de fala | fragmento deliberado, elipse de diálogo, verbo não reconhecido | baixo | — · — | alto | pendência (média), observação (baixa) | **Restringir** |
| `estrutura`: subordinada sem principal | “Quando as luzes se apagam.” | E | árvore · V M | 1 (100%) | 0/0/1/0 | 0 a 2 | — | — | — · — | baixo | observação | **Manter** |
| `residuo_edicao` | dois auxiliares finitos seguidos | O | árvore · M | 2 (50%) | 0 | 1 | — | — | — · — | baixo | pendência | **Manter** |
| `pontuacao_dialogo` | aspas + vírgula + verbo que não é de fala | E | fechamentos da leitura antiga · S E V | 9 (78%) | 0 | 9 (0/5) | título entre aspas com mais de 3 palavras; “disse-me”; `quotes_role = narracao` ignorado | médio | `dialogo_contextual` (travessão) · — | médio | pendência | **Refatorar** |
| `dialogo_contextual` (ação depois da fala; retomada) | pontuação do inciso de travessão | O/E | segmentação + perfil de fala · S E M | 32 (91%) | 0 | 0 (“--” não é travessão) | — | médio | — · — | médio | pendência | **Manter** |
| `palavra_consecutiva` | palavra dobrada | O | regex + léxico | 1 (0%, estilo) | 0 | 30: 15 “-a a” depois de ênclise, 4 “se se”, 1 abreviatura | ênclise + preposição “a”; “se se”; abreviaturas | baixo | — · família palavra duplicada (D) | baixo | pendência | **Restringir** |
| `palavra_proxima` | repetição a até 8 palavras | R | contagem | 43 (23%; 33 de estilo) | 19/12/4/15 | cerca de 1.000 | repetição expressiva | — | — · — | baixo | observação | **Retirar** (D5) |
| `frase_duplicada` | frase repetida | E | igualdade/semelhança | 0 | 0 | 0 | — | — | — · — | baixo | pendência/observação | **Manter** |
| `variacao_nome` (nome a uma letra; grafia oscilante) | o mesmo nome escrito de dois jeitos | E | distância + léxico · L | 2 (0%, ambas intencionais) | 0/0/2/4 | 220 (com a grafia antiga) | verbo com ênclise tratado como termo composto (“disse-me”); grafia fora do léxico | baixo | — · — | baixo | pendência | **Restringir** (ênclise) e **sem evidência** de precisão |
| `duracao_suspensao`, `adiamento_amanha` | prazos de uma cena | E | 2 regex (exemplo isolado) | 0 | 0 | 0 | — | alto | Coerência com IA · — | baixo | pendência | **Retirar** |
| `referente_proximidade` | “Eles … tão perto” sem plural antes | E | 1 regex (exemplo isolado) | 0 | 0 | 0 | — | — | IA · — | baixo | observação | **Retirar** |
| `referente_contextual` | só “o objeto” depois de enumeração | E | palavra literal | 0 | 0 | 0 | — | — | IA · — | baixo | observação | **Retirar** |
| `pronome_apos_corte` | pronome perto de trecho cortado | E | diff com `--original` | 0 | não executado | não executado | — | — | — · — | baixo | observação | **Sem evidência** (fica como está) |
| `construcao_invalida` | “além de disso” | O | 1 regex | 1 (100%) | 0 | 0 | — | — | — · LT (locuções) | mínimo | pendência | **Manter** |
| `pontuacao_duplicada` (`,,` `;;` · “Dois pontos finais”) | sinal repetido | O | regex | 12 (92%), **todas** em “Dois pontos finais” | 0 | 5 | — | baixo | — · família (D) | mínimo | pendência | **Manter** |
| `espacamento` | espaço duplo; antes de `,;` | O | regex | 1 (100%) | 0 | 0 | — | — | — · família (D) | mínimo | pendência | **Manter** |
| `virgula_que_nao` | “que, não” | O | regex + 3 exceções | 1 (100%) | 0 | 2 (0/2) | conectivo conclusivo (“pelo que, não…”, “assim que, não…”) | — | — · — | baixo | pendência | **Restringir** |
| `que_tonico_interrogativo` | “que?” → “quê?” | O | regex | 4 (100%) | 0 | 26 (4/4 pela norma atual) | — | — | — · — | mínimo | pendência | **Manter** |
| `coerencia_temporal`: geração nova (4) e condicional | tempos incompatíveis entre orações e na sequência | E | árvore + eventos · V T M | alta 12 (100%); subtipos novos 16 (94%) | 11 em A; 2 em X | inflado pelos confusores | — | médio | `tempo_verbal` (D interna) · — | alto | pendência | **Manter** |
| `coerencia_temporal`: `coordinated_past_present` (geração antiga) | presente coordenado a passado | E | árvore · T M | 7 (29%: 2 erros, 4 FP) | 0 | 61 | comentário do narrador, pergunta, verdade geral | — | geração nova · — | médio | pendência | **Desativar** |
| `coerencia_temporal`: `ambiguous_simultaneity`, `conditional_future`, `simultaneous_present` (geração antiga) | “enquanto” e hipótese | E | árvore · T M | 4 (100%) | 0 | 0 a 3 | — | — | — · — | baixo | pendência | **Manter** |
| `acentuacao_contextual` | “caiam” → “caíam” no passado | O | léxico + raiz + sujeito · L T | 2 (50%) | 0 | 3 (3/3, grafia antiga) | — | — | — · LT (ortografia) | baixo | pendência | **Manter** |
| `vocativo` | chamamento sem vírgula | O | 3 regex + léxico | 0 | 0 | 4 (1/4) | verbo no início da pergunta + “você” (“Quer você…?”) | — | — · — | médio | pendência | **Restringir** |
| `capitalizacao_contextual` | pronome minúsculo depois de `?` ou `!` | O | regex | 0 | 0 | 6 (≈0/4) | depois de interjeição ou vocativo exclamativo (“Ah! tu…”), aceito pela norma | — | — · família maiúscula (D) | baixo | pendência | **Restringir** |
| `gerundismo` | “vou estar fazendo” | R | regex | 1 (0%, estilo) | 1/0/0/0 | 0 | — (a mensagem diz que não é erro) | — | — · — | baixo | observação | **Retirar** |
| `crase`: locução fixa, horas, “à” + verbo/masculino | crase objetiva | O | regex + léxico · V | 0 próprias; 1 em B (agora principal) | 0/1/0/0 | 3 em locução | — | médio | — · família crase (D) | baixo | pendência | **Manter** |
| `crase`: “Crase ausente” (dativo) | objeto indireto feminino | O | árvore + lista `DATIVE` · M | 0 | 0 | 13 (1/6) | objeto direto lido como indireto (“contou ao filho a história”); verbo fora do léxico | médio | — · — | médio | pendência | **Restringir** |
| `homofonos` (por que/porque, há/a, mas/mais, mal/mau, onde/aonde, locuções) | grafia de homófonos | O | regex + listas de exceção | 0 | 0 | 55 (por que/porque e “embaixo” corretos pela norma atual; há/a só falha com a grafia antiga) | — | médio | — · LT (`POR_QUE_PORQUE`) | médio (listas) | pendência | **Manter** (manutenção sem mudança) |
| `concordancia`: verbal, haver impessoal, sujeito oculto | concordância | O | árvore + guardas · V M | 5 (100%, verbal, 2 livros) | 0/0/1/0 | 160 (≈2/12, grafia antiga) | sujeito escolhido pelo modelo | médio | — · LT (concordância) | médio | pendência | **Manter** (mensagem com “parece”) |
| `concordancia`: nominal | adjetivo × nome | O | árvore · M | 0 | 0 | 23 (0/4) | linhas de sumário; cor composta (“azul ferrete”) | — | — · LT | baixo | pendência | **Sem evidência**; restringir as duas classes |
| `regencia`: pronome reto como objeto | “ajudou ela” | norma-padrão | árvore + perfil de fala · E M | 2 (100%) | 0 | 0 | — | — | — · — | baixo | pendência | **Restringir**: atenção editorial, sem afirmar erro (D5) |
| `regencia`: “chegar em”, “pedir para que” | regência coloquial | R | árvore + listas | 2 (50%: 1 erro, 1 estilo; 16 marcações brutas de estilo) | 1/0/0/0 | 1 | uso brasileiro aceito | — | — · — | baixo | pendência | **Retirar** |
| `virgula_sujeito_verbo` | vírgula entre sujeito e verbo | O | árvore + forma · V E M | 2 (50%) | 0/0/1/0 | 58 (≈4/6) | infinitivo coordenado; gerúndio em inciso | médio | — · — | médio | pendência | **Sem evidência** (fica como está) |
| `correlacao_tempos` | imperfeito do subjuntivo + principal no presente | E | conectores + terminação · T | 7 (86%, 1 livro) | 0/0/5/0 | 36 (0 a 2/4) | principal impessoal ou genérica (“é possível que…”, “o que se chama”) | — | — · — | médio | pendência | **Sem evidência**; anotar a classe impessoal |
| `frase_cortada`: preposição final | frase termina em preposição | O | lista fechada | 1 (100%) | 0 | 3 (0/3, todas com “...”) | interrupção deliberada com “...” (o “…” já é aceito) | — | — · — | baixo | pendência | **Refatorar** (“...” igual a “…”) |
| `frase_cortada`: “cada” depois de verbo | “conta cada.” | O | caso especial | 0 | 0 | 0 | — | — | — · — | baixo | pendência | **Manter** (sem mudança agora) |
| `frase_cortada`: “Que” depois de reticências | “prometi… Que voltaria” | O | perfil `PEDEM_QUE` · E | 1 (100%) | 0/0/1/0 | 0 | radical de outro verbo (“sentou”) pode disparar | — | — · — | baixo | pendência | **Manter** |
| `frase_cortada`: pontuação final ausente | parágrafo sem ponto | O | regex + `lista_ou_rotulo` | 1 (100%) | **19 sem decisão**/1/1/1 | 18 (sumário, verso, título) | título, sumário, verso, epígrafe | — | — · — | baixo | pendência | **Sem evidência** (aguarda a D6) |
| `locucoes`: “embora” + nome | conjunção sem oração | O | regex | 1 (100%) | 0/0/1/0 | 0 | — | — | — · — | baixo | pendência | **Manter** |
| `locucoes`: “ao invés de” | “ao invés de” = “ao contrário de” | norma-padrão | regex | 1 (100%) | 0/0/1/0 | 0 | uso contemporâneo amplo | — | — · LT (estilo, desligado) | baixo | pendência | **Sem evidência** (fica; a decisão real foi “erro”) |

Contagem:
- 32 chaves configuráveis. O inventário falava em 30; contando à parte `residuo_edicao` e as
  subpartes, são 41 linhas.
- **Manter:** 18. **Restringir:** 8. **Refatorar:** 2. **Desativar:** 1. **Retirar:** 6 (7 regras;
  as duas de prazo estão numa linha). **Sem evidência:** 6.
- `variacao_nome` está contada em Restringir.

#### Questões prioritárias

**1. `imperfeito`:**
- **Quem usa:** um único consumidor, `temporal.past_plane`. Ele decide se um passado numa narração
  no presente é anterior (sem alerta) ou incerto (observação).
- **Por que o defeito está latente:** `past_plane` só é consultado quando `tempo_narrativo` (ou
  `passado_so_no_lexico`) já disse “passado”, e o condicional e o imperfeito do subjuntivo dão
  `None` ali. Verificado com “faria”, “viajaria”, “fosse”, “tivesse” e “cantasse”.
- **Nos textos reais:**
  - **C (narrado no presente):** dois casos chegam lá, e os dois são imperfeitos legítimos
    (“queria”, “ia”). Nenhum alerta muda.
  - **A, B e X:** narrados no passado; não usam `past_plane`.
- **Defeito inverso:** a terminação do condicional (`-ria`) também pega imperfeitos de verbos em
  `-er` (“queria”), resolvidos hoje pelo léxico.
- **Correção proposta:**
  - `imperfeito` passa a excluir o condicional (terminação + léxico sem leitura de passado, a
    mesma regra de `tempo_estrito`) e o imperfeito do subjuntivo (`imperfeito_do_subjuntivo` e
    `Mood=Sub`);
  - os testes de `LimitacoesRegistradas` mudam de propósito;
  - impacto esperado: nenhum alerta nos 29 conjuntos (conferir);
  - risco: “queria”/“ia” lidos pelo modelo como condicional, protegidos pelo léxico.

**2. Verbos de fala** (por consumidor):

| Consumidor | Uso do perfil | Erro do radical (aceitar a mais) | Erro de cobertura (formas que faltam) |
|---|---|---|---|
| pontuação de diálogo | suprime | conservador (perde alerta) | **gera alarme falso** (“disse-me”, “dissera”) |
| diálogo contextual, ação depois da fala | suprime | conservador | gera alarme falso (mesmas formas) |
| diálogo contextual, retomada | condição | **gera alerta** (substantivo logo depois do travessão: “Grito…”) | perde alerta |
| pronome reto, vírgula sujeito-verbo, crase do LT | suprimem | conservador | gera alarme falso |
| frase cortada, “Que” | condição | **gera alerta** (“sentou… Que”, “contem… Que”) | perde alerta |

- **Alcance nos textos reais:** nenhuma palavra só nominal é aceita pelo radical em A, B, C ou X;
  “disse-me” e “dissera” não aparecem (a ênclise é rara no PB atual); só há um “dissesse”, em A.
- **Nos textos independentes:** a ênclise é frequente e gera alarmes falsos.
- **Proposta (fase comportamental):** reconhecer as formas irregulares com ênclise e no
  mais-que-perfeito, e conferir o léxico nos dois consumidores que geram alerta. **Não** ampliar
  categorias nem unir perfis.

**3. Segmentação** (as 7 divergências da Fase 4):
- **Afeta precisão:** só a 3 (`quotes_role = narracao` ignorado pela pontuação de diálogo, que
  continua tratando aspas como fala). Ocorre só para quem configura aspas como narração.
- **Aceitáveis:** 1, 2, 5, 6 e 7. A leitura antiga só decide os fechamentos de aspas; o hífen de
  diálogo de X é lido pela atual. A divergência 4 (aspa que reabre) não aparece nos textos reais.
- **Nova limitação:** “--” como travessão não é reconhecido por nenhuma das leituras.
  - Ausente nos textos reais; comum em texto digitado sem conversão.
  - Fica **fora do escopo** da Fase 7, registrada para a segmentação.

**4. Pontuação final ausente:**
- Nenhuma reformulação até as decisões da D6. Os 19 casos de A não são usados como confirmados.
- Os textos independentes mostram classes de alarme falso **sem** usar A: linhas de sumário,
  verso, título de capítulo não marcado.
- Depois da D6, medir as candidatas (linha curta em maiúsculas, linha sem verbo finito do núcleo,
  bloco de sumário) contra as decisões.

**5. Registro:**
- **Erro objetivo:** palavra dobrada, crase de locução, “que” tônico, concordância.
- **Desvio da norma-padrão comum no PB:** pronome reto como objeto, “ao invés de”. Ficam como
  atenção editorial, sem dizer que é erro. Pronome reto só na narração (já é).
- **Escolha de registro:** “chegar em”, “pedir para que”, gerundismo. **Retirar.**
- **Estilo:** repetição próxima. **Retirar** (D5; 77% das decisões são “estilo”).

**6. Regras de exemplo isolado:**
- **Retirar:** `referente_proximidade`, `referente_contextual`, `duracao_suspensao`,
  `adiamento_amanha`. Literais, sem disparos nem decisões; o fenômeno é da Coerência com IA.
- **Manter:** `construcao_invalida`, “embora” + nome, “Que” depois de reticências. Objetivas, com
  decisões reais corretas e custo mínimo.
- **Restringir:** `virgula_que_nao`, pela classe dos conectivos conclusivos, sem condição literal.

#### LanguageTool (proposta; nada alterado)
- **Diagnóstico:**
  - `languagetool:gramatica` (60% em 30) mistura gramática, tipografia, pontuação e sem categoria.
    Seis dos sete alertas atuais não são gramática.
  - Nas decisões, o desempenho por regra varia:
    - `SPACE_AFTER_PUNCTUATION` 4/6;
    - `VERB_COMMA_CONJUNCTION` 1/5;
    - `AUXILIARY_VERB_INFINITIVE` 0/2;
    - concordâncias 3/3.
  - Severidade forçada em “provável erro”.
- **Estratégia em três passos, com aprovação separada:**
  1. **Medir sem mudar** (pronto para executar):
     - redistribuir as decisões históricas por categoria do LT. O ID da regra está na origem, e a
       categoria de cada regra se obtém do próprio LT 6.6;
     - relatório numérico por categoria;
     - nada muda nos relatórios nem na Política.
  2. **Classe interpretada, versionada:**
     - para relatórios novos, `languagetool:ortografia` (`misspelling`), `languagetool:gramatica`
       (`grammar`), `languagetool:tipografia` (`typographical`, `whitespace`, `PUNCTUATION`) e
       `languagetool:outros` (`uncategorized`, `MISC`);
     - relatórios antigos continuam com a classe deduzida de sempre;
     - as medições novas vêm do passo 1, decisão por decisão, sem somar classes;
     - exige a Política v3. Os IDs não mudam (a classe não entra no ID), e as decisões e a herança
       também não (a chave de conteúdo não usa classe).
  3. **Severidade pela interpretação:**
     - tipografia e outros → “atenção editorial”;
     - ortografia e gramática continuam “provável erro” só se a medição da nova classe sustentar;
       senão, “atenção editorial”;
     - efeito: rótulo, cor e filtro no app;
     - sem efeito em IDs, decisões e destino (o destino não usa a severidade);
     - o impedimento exige severidade de erro: rebaixar impede o LT de ser impeditivo no futuro.
       Isso fica explícito na aprovação.

#### Pendências funcionais registradas (sem mudar a interface)
1. **Conflitos:** resolução explícita de decisões históricas conflitantes, com uma ação para
   marcar o conflito como resolvido. Hoje o registro é cumulativo.
2. **Código de saída da CLI** na análise parcial: hoje é 0. Propor um código próprio e tratá-lo no
   app, que precisa continuar abrindo o relatório.
3. **Encerramento completo × parcial:** já separados por registro. Falta mostrar no app quando
   existe um encerramento completo para o mesmo texto enquanto se olha uma análise parcial, e
   vice-versa.

#### Plano de implementação da Fase 7b (por prioridade)

**P1 — alto impacto em alarmes falsos**

| # | Problema | Solução | Risco | Impacto esperado | Evidência | Testes | Decisões anteriores |
|---|---|---|---|---|---|---|---|
| 1 | `palavra_consecutiva` alerta “-a a” e “se se” | não alertar quando a primeira palavra é pronome ligado por hífen ao verbo (ênclise) e a segunda é preposição; nem em “se se” (conjunção + pronome) | baixo (“a a” sem hífen continua) | os 30 disparos independentes caem para cerca de 10; 0 nos reais | 15 + 4 de 30 | positivos “o o”, “para para”; negativos de ênclise, “se se”, abreviatura | IDs iguais nos que ficam |
| 2 | `coordinated_past_present` (2 de 7) | não emitir mais (a função fica para os testes de caracterização) | baixo: nenhum disparo real hoje | média de `coerencia_temporal` mais limpa | 7 decisões; 61 independentes | testes atuais desse subtipo mudam de propósito | decisões antigas ficam nos relatórios antigos |
| 3 | `frase_cortada` alerta preposição antes de “...” | tratar “...” como “…” | mínimo | 3 a menos nos independentes | 3/3 | “de...” e “de…” iguais | — |
| 4 | “Crase ausente” (dativo) | só alertar quando o verbo está no léxico como verbo, o complemento tem `dep_ = obl/iobj` confirmado e não há outro objeto direto feminino; senão, nada | médio (perde verdadeiros) | 1/6 nos independentes | corpus 8/9 | corpus atual mais negativos de objeto direto | — |
| 5 | `estrutura` (fragmento) com 39% e 10% | rebaixar o fragmento para confiança baixa (vira observação pela Política atual, sem mudar a Política) | baixo | menos interrupções; a classe `sentence_structure\|baixa` continua sendo medida | 28 decisões | destino conferido | os IDs não mudam (a confiança não entra no ID) |

**P2 — erros estruturais de classificação**
- **`imperfeito`:** como na questão 1; nenhum alerta deve mudar.
- **Perfil de fala:**
  - formas irregulares com ênclise (“disse-me”) e no mais-que-perfeito (“dissera”);
  - conferência no léxico nos dois consumidores que geram alerta (retomada e “Que”);
  - sem ampliar categorias;
  - evidência: amostras independentes e testes de cada consumidor.
- **`pontuacao_dialogo`:**
  - respeitar `quotes_role = narracao`;
  - não tratar como fala aspas de título com mais de 3 palavras depois de um nome e antes da
    vírgula, só com evidência estrutural.

**P3 — regras redundantes ou de exemplo isolado (retirar)**
- **Quais:** `referente_proximidade`, `referente_contextual`, `duracao_suspensao`,
  `adiamento_amanha`.
- **Como:** vão para `RETIRED_RULES`, com o app aceitando as chaves.
- **Compatibilidade:** relatórios antigos continuam legíveis e as decisões ficam.

**P4 — regras estilísticas ou de registro**
- **Retirar:** `palavra_proxima`, `gerundismo`, `regencia` “chegar em” e `regencia` “pedir para
  que”. As duas de regência viram subpartes retiradas, e `regencia` fica com o pronome reto.
- **Pronome reto:** mensagem de norma-padrão, sem afirmar erro.
- **Configurações antigas:** aceitas.

**P5 — regras frágeis (restringir)**
- `vocativo`: não aceitar como nome um verbo do léxico em início de pergunta.
- `capitalizacao_contextual`: não alertar depois de interjeição (“Ah!”, “Oh!”) nem de vocativo
  exclamativo.
- `virgula_que_nao`: não alertar com conectivo conclusivo antes (“pelo que”, “de modo que”,
  “assim que”).
- `concordancia` nominal: excluir linhas de sumário e cor composta.
- `variacao_nome`: verbo com ênclise conferido no léxico.

Cada uma precisa de positivos, negativos e substituição de nomes. Uma regra com 0 decisões não
passa a ser considerada saudável por ter sido restringida.

**P6 — manutenção sem mudar comportamento:**
- listas de exceção de há/a e mas/mais nos núcleos;
- mensagens com “parece” em concordância e crase;
- a relação temporal registra `absorvidos` ao absorver o tempo verbal.

**Fora do escopo (permanece):**
- “--” como travessão; atribuição de falante; correferência;
- palavras válidas trocadas; ortografia sem o LanguageTool;
- pontuação final ausente até a D6;
- a classe e a severidade do LT até a decisão separada;
- o modelo de linguagem maior.

**Comparação obrigatória na Fase 7b:**
- **29 conjuntos**, com a justificativa de cada diferença;
- **textos independentes** antes e depois, por classe de alarme falso;
- **herança real**, que precisa ficar igual;
- **corpus de desenvolvimento** sem perder nenhum verdadeiro que não seja explicado.

**Regras recomendadas sem nenhuma alteração:**
- `tempo_verbal`;
- `dialogo_contextual`;
- `estrutura` (subordinada sem principal);
- `residuo_edicao`;
- `frase_duplicada`;
- `construcao_invalida`;
- `pontuacao_duplicada`;
- `espacamento`;
- `que_tonico_interrogativo`;
- `coerencia_temporal` (geração nova e os 3 subtipos antigos de bom desempenho);
- `acentuacao_contextual`;
- `crase` (locuções, horas, “à” + verbo/masculino);
- `homofonos` (comportamento);
- `concordancia` verbal (comportamento);
- `frase_cortada` (“cada” e “Que”);
- `locucoes` (as duas partes);
- `virgula_sujeito_verbo`;
- `correlacao_tempos`;
- `pronome_apos_corte`.

### Fase 7b — implementação (08–09/10/2026)

**Método:**
- **Um commit por grupo.** Cada um foi gerado numa cópia congelada (`git worktree`): 29 conjuntos
  e os 3 textos independentes de desenvolvimento, comparados com o grupo anterior
  (`build/f7b/<grupo>`).
- **Linha de base `build/f7b/base`:** idêntica à Fase 6b.
- **Herança real** conferida com o código Swift atual.
- **Testes:** os novos testes de cada grupo falham no código anterior.

| # | Commit | Mudança | 29 conjuntos | Textos independentes |
|---|---|---|---|---|
| 1 | `5f40df7` | Palavra dobrada: ênclise + artigo/preposição homógrafos, “se” conjunção + “se” pronome com verbo, abreviatura | iguais | −19 alarmes |
| 2 | `f1695ca` | `coordinated_past_present` desativada (`temporal.DESATIVADAS`; a implementação fica) | sem mudança de alertas; o metadado `temporal_relations` perde a relação | −61 pendências da relação; nos mesmos verbos volta o tempo verbal genérico (+20 pendências, +41 observações) |
| 3 | `a8bed43` | “...” igual a “…” na frase cortada | iguais | −3 |
| 4 | `649ec41` | Crase dativa: destinatário já expresso; pronome preposicionado | iguais | −1 |
| 5 | `5303db5` | `modo_do_imperfeito`: indicativo, condicional, subjuntivo, ambíguo, pelo léxico e pelo modelo | iguais | iguais |
| 6 | `cee60b3` | Verbos de fala: ênclise (“disse-me”), mais-que-perfeito (“dissera”); radical conferido com o lema do modelo onde o verbo de fala é condição do alerta | iguais | −1 |
| 7 | `d74cb3b` | Pontuação de diálogo não roda com aspas como narração | iguais | iguais |
| 8 | `a85f5d8` | Retiradas: repetição próxima, gerundismo, prazos, referentes literais; regências coloquiais | ver abaixo | −1.024 observações de repetição; −1 de regência |
| 9 | `477eeb3` | Frágeis: vocativo, maiúscula depois de interjeição, “que, não” conclusivo, cor composta, ênclise na grafia oscilante | iguais | −16 |
| 10 | `061fb6f` | Mensagens de concordância e crase dativa com “parece”; `medir_precisao.py --languagetool` | ver abaixo | — |

**Manuscritos reais, com o LT, antes → depois** (pendências/observações):
- A 37/26 → 36/6;
- B 4/14 → 4/2;
- C 19/12 → 19/8;
- X 17/33 → 17/18.

Na fila sai uma única pendência: a “chegar em” de A. As outras saídas são observações: 50 de
repetição próxima e 1 de gerundismo. O texto mudou nos 29 conjuntos em três pontos: os avisos da
etapa editorial (descreviam regras retiradas), o metadado `temporal_relations` e as mensagens do
grupo 10.

**Textos independentes, antes → depois:** 2.457/3.483 → 2.373/2.500 (pendências/observações). A
maior parte do volume que resta vem dos confusores da Fase 7a (grafia antiga, “--”, narrador
oitocentista).

**Corpus de desenvolvimento:**
- precisão das pendências 97% → 97%;
- alarmes falsos de 22,6 → 17,6 por 10 mil palavras;
- precisão de todas as ocorrências 88% → 90%;
- cobertura de regência 7/10 → 2/10: os 5 casos anotados eram “chegar em” e “pedir para que”, que
  deixaram de ser tratados como erro por decisão aprovada. As anotações não foram alteradas; a
  perda fica registrada aqui.

**IDs e decisões:**
- **IDs:** nenhum alerta que continua mudou de ID.
- **Herança real:** A passa de 28 para 7; C, de 15 e 17 para 11 e 13.
  - As 25 decisões que deixam de ser herdadas (21 em A, 4 em C) são todas de alertas retirados
    (repetição próxima 23, “chegar em” 1, gerundismo 1), todas “Estilo do autor”.
  - As demais são idênticas.
  - Os arquivos de decisões por relatório (`Decisoes/<sha>.json`) continuam intactos e entram em
    `medir_precisao.py`.

**Testes alterados, com motivo:**
- Saíram os testes que exercitavam regras retiradas (prazos, adiamento, repetição próxima,
  referentes, gerundismo, “chegar em”, “pedir para que”). No lugar, testes de que as chaves são
  aceitas e não produzem alertas.
- Os testes que usavam a repetição próxima como exemplo de outra coisa (aspas, itálico,
  travessões, ordem das etapas, identidade por evidência, janela de contexto, IDs antigos) passaram
  a usar a palavra dobrada, a frase repetida ou o diálogo contextual. `test_legacy_ids_preserved`
  passou a exigir que haja alerta: sem isso, passaria por vacuidade.
- `LimitacoesRegistradas` de `test_tempo` (imperfeito) virou teste da correção.
- “dissera” mudou de negativo para positivo em `test_elocucao`.
- Os testes da relação desativada usam `desativadas=()` para continuar caracterizando a
  implementação.

**Descartados, com justificativa:**
- **Rebaixar a confiança do fragmento de estrutura:** não feito (decisão do autor). Fica a
  limitação de 39% e 10%, com a Política v2 como está.
- **Aspas de título** na pontuação de diálogo: não há critério estrutural seguro; a evidência é só
  dos textos independentes.
- **Pontuação final ausente:** aguarda a D6.
- **“ao invés de”:** sem mudança, pendente de evidência.
- **Listas de há/a e mas/mais nos núcleos:** risco sem alarme falso demonstrado em texto atual.
- **`absorvidos` na relação temporal:** o alerta genérico absorvido nunca chegou a um relatório;
  não há decisão a preservar.
- **Ramo de palavra dobrada de `analysis.analyze`** (só na chamada direta): não recebeu as
  distinções do grupo 1. Fica para a auditoria da Fase 8.

**Limitações que ficam:**
- crase dativa com o modelo errando o objeto;
- concordância verbal dependente do sujeito escolhido pelo modelo;
- correlação de tempos com principal impessoal;
- vírgula sujeito-verbo sem decisões suficientes;
- “--” como travessão;
- radical do perfil de fala nos usos que só suprimem (conservador);
- nomes próprios homógrafos de verbo em pergunta com vocativo (“Lia você vem?”), que agora não
  são apontados;
- interjeição seguida de vocativo exclamativo (“Pobre Ana! tu…”), ainda apontada.

**Critérios restantes para a Fase 8:**
- auditoria cruzada das exceções e da duplicação que sobrou (inclusive o ramo de palavra dobrada
  de `analysis`);
- medição final nas quatro categorias de evidência;
- decisão separada sobre classe e severidade do LT (Política v3);
- D6 (pontuação final ausente);
- as pendências funcionais da Fase 7a (resolução de conflitos, código de saída parcial,
  encerramento completo × parcial);
- versão do baseline.

### Fase 8 — auditoria cruzada e validação final (09/10/2026)

**Pergunta:** existe algum defeito relevante, demonstrado e não resolvido que impeça considerar o
FONTE uma base estável? Nenhuma regra, exceção ou detector mudou nesta fase.

**Método:**
- motor nos fontes do HEAD (`ff92811`; o código do motor é o mesmo de `061fb6f`);
- saídas em `build/f8/` (fora do Git): `final/` (29 conjuntos e os 3 textos independentes de
  desenvolvimento), `precisao/`, `testes/` e `testes-1.5.0/`;
- os `.docx` dos textos independentes foram refeitos dos `.txt` congelados (parágrafos por linha em
  branco, espaços colapsados) e conferidos: os três relatórios são idênticos aos de `build/f7b/g10`;
- a validação do `~/Lume-evidencia` não foi usada: as **duas consultas reservadas** da validação
  verbal continuam disponíveis.

#### Auditoria cruzada

| # | Achado | Evidência | Classe |
|---|---|---|---|
| 1 | Ramo de palavra dobrada em `analysis.analyze` sem as distinções do grupo 1 da 7b | Só roda sem `enabled_rules` (chamada direta). `search.linguistic` sempre passa listas sem `palavra_consecutiva`; a pipeline usa `editorial/repetition`. Chamadores diretos: testes (`test_fonte`, `test_lexical_review`, `test_clitic_feedback`) e a sonda de saúde do motor (`packaging/lume_engine.py`), que só confere o tempo verbal. Nenhum relatório passa por ele. | B: divergência sem efeito funcional; não removido (`test_repeat_narrative_only` depende dele, e a remoção não traz ganho ao usuário) |
| 2 | Texto da etapa morfossintática diz “quatro relações temporais locais”; uma está desativada | `pipeline.py`, descrição da etapa | B: descritivo; mudá-lo altera o texto dos 29 conjuntos |
| 3 | `contracts.occurrence` ainda dá severidade a `duracao_suspensao`, `adiamento_amanha` e `referente_proximidade` | Essas regras não emitem mais; o ramo não é alcançado | B: inerte |
| 4 | `politica.json` mantém `palavra_proxima\|baixa` e `gerundismo\|baixa` | Necessário para classificar relatórios antigos; Política v2 intacta | Correto |
| 5 | Listas de regras Swift × Python | 26 regras ativas iguais nos dois lados; `retiredIDs` = `RETIRED_RULES` (12) | Sem divergência |
| 6 | Checagens diretas de morfologia fora dos núcleos (`VerbForm` Inf/Ger/Part, `Mood`) | Não são “verbo finito” nem classificação de tempo; ficam nas relações, como registrado na Fase 3 | Sem divergência |
| 7 | `scripts/montar-lume.command` não compilava nem rodava `DeduplicationCheck` e `PartialAnalysisCheck` | As duas verificações das Fases 6b ficavam fora da montagem | Corrigido: só a montagem, sem efeito no motor |
| 8 | Cópia antiga e não editável do FONTE 1.4.0 no `site-packages` da `.venv` | Um script fora de `fonte/` importa essa cópia (aconteceu numa sonda desta fase). Testes, `avaliar_deteccao`, `medir_precisao`, contrato e a pipeline usam os fontes; a montagem reinstala `./fonte` antes de congelar | B: só do ambiente de desenvolvimento |
| 9 | Problemas 2 e 3 da Fase 3 (recuperação ignora o modo; passado só pelo léxico sob subjuntivo) | Registrados em `LimitacoesRegistradas` | B |

#### Preservação das decisões

- **IDs:** contra `9f0f6d8`, nenhum alerta que continua mudou de ID ou de destino. Saíram 105 nos
  8 conjuntos reais: 100 de repetição próxima, 2 de gerundismo, 2 de “chegar em” (A e A com LT) e 1
  do LT absorvido pela crase do FONTE (B com LT). Entrou 1 (essa crase).
- **Herança real** (código Swift atual, memórias reais dos livros):

  | Relatório | 9f0f6d8 | Fase 6b | Final |
  |---|---:|---:|---:|
  | A / A com LT | 28 / 28 | 28 / 28 | 7 / 7 |
  | C / C com LT | 15 / 17 | 15 / 17 | 11 / 13 |

  As 25 que saem (A 21, C 4) são todas de regras retiradas: repetição próxima 23, gerundismo 1,
  “chegar em” 1. As que ficam são as mesmas, pelo mesmo ID.
- **Relatórios e arquivos antigos:** os 58 relatórios, 31 arquivos de decisões e 3 memórias de livro
  da pasta do app abrem e validam com o modelo Swift atual. Nada foi gravado nessa pasta.
- **Próximo salvamento da memória editorial** (simulado com o código Swift, sem gravar):
  - `Decisoes/<sha>.json` mantém **todas** as entradas: `loadReport` restaura o arquivo sem filtrar
    pelos IDs do relatório novo, e `autosave` grava o dicionário inteiro. No livro A: 30 entradas,
    23 de alertas que não estão no relatório novo, todas preservadas.
  - `Livros/<livro>.json` é refeito só com os alertas do relatório aberto: no livro A, 30 → 7
    decisões. É o comportamento de sempre (memória do último relatório). Sem efeito funcional: as
    regras retiradas não emitem mais, e a memória do livro nunca é a única cópia de uma decisão.
  - Conflitos de alertas que não estão no relatório novo saem do arquivo de decisões no próximo
    salvamento (`decisionConflicts` filtrado pelos IDs). Hoje não há nenhum conflito nos dados reais.
- **Medição histórica:** `medir_precisao.py` cruza cada relatório guardado com o arquivo de decisões
  do mesmo SHA. As 650 decisões continuam medidas, inclusive as das regras retiradas (repetição
  próxima 43, gerundismo 1).
- **Onde o histórico pode se perder:** a decisão só tem sentido (regra, classe, trecho) junto do
  relatório que a gerou. “Limpar resíduos” apaga os relatórios antigos (fica o mais recente de cada
  livro); depois disso, as decisões de alertas que não existem no relatório mantido deixam de ser
  medidas. É uma ação explícita, com resumo antes, e anterior à estabilização; mas o diálogo não
  avisa da perda de medição. Já existem 3 arquivos de decisões sem relatório (53 decisões fora da
  medição), de antes desta fase.
  - **Menor solução proposta (não implementada; aguarda aprovação):** em `StorageCleanup.plan`,
    manter também a pasta de um relatório antigo quando o arquivo de decisões do mesmo SHA tiver
    decisão (não pendente) para um ID que existe nesse relatório e não existe no relatório mantido
    do livro. Cerca de 10 linhas em `Models.swift`.
  - **Testes propostos** em `DeskToolsCheck`: (1) relatório antigo com alerta decidido que sumiu do
    mais recente → fica; (2) relatório antigo cujas decisões estão todas no mais recente → sai;
    (3) relatório antigo sem decisões → sai, como hoje.

#### Validação final

1. **Funcionamento** (corpus de desenvolvimento, 21 textos, 3.978 palavras, sem o LT; escrito junto
   com as regras, não mede uso real): idêntico ao da Fase 7b.

   | Métrica | 9f0f6d8 | Fase 6b | Final |
   |---|---:|---:|---:|
   | Precisão das pendências | 96,9% | 96,9% | 96,7% |
   | Alarmes falsos nas pendências por 10 mil palavras | 5,0 | 5,0 | 5,0 |
   | Precisão de todas as ocorrências | 88% | 88% | 89,6% |
   | Alarmes falsos por 10 mil palavras (todas) | 22,6 | 22,6 | 17,6 |
   | Ocorrências | 81 | 81 | 73 |
   | Cobertura linguística | 65/84 | 65/84 | 60/84 |

   A única classe com cobertura diferente é regência, 7/10 → 2/10: os 5 casos anotados eram “chegar
   em” e “pedir para que”, retirados por decisão aprovada. Narrativa 0/14 (contradição e
   continuidade são da Coerência com IA).
2. **Regressão:** os 29 conjuntos são **idênticos** aos da Fase 7b (8 reais com e sem o LT; 21 do
   corpus).

   | Texto (palavras) | 9f0f6d8 | Fase 6b | Final | Pendências por 10 mil | Observações por 10 mil |
   |---|---|---|---|---:|---:|
   | A (13.810) | 37/26 | 37/26 | 36/6 | 26,1 | 4,3 |
   | B (2.509) | 2/13 | 2/13 | 2/1 | 8,0 | 4,0 |
   | C (3.129) | 18/11 | 18/11 | 18/7 | 57,5 | 22,4 |
   | X (6.338) | 13/26 | 13/26 | 13/11 | 20,5 | 17,4 |
   | A com LT | 37/26 | 37/26 | 36/6 | 26,1 | 4,3 |
   | B com LT | 4/14 | 4/14 | 4/2 | 15,9 | 8,0 |
   | C com LT | 19/12 | 19/12 | 19/8 | 60,7 | 25,6 |
   | X com LT | 17/33 | 17/33 | 17/18 | 26,8 | 28,4 |

   Pendências/observações. Nenhum impeditivo em nenhum conjunto. Das 36 pendências de A, 19 são de
   pontuação final ausente, sem decisão (D6).
3. **Generalização** (3 romances de desenvolvimento, 193.194 palavras, sem o LT): idênticos aos da
   Fase 7b. Fase 6b → final: pendências 2.457 → 2.373 (127,2 → 122,8 por 10 mil), observações 3.483 →
   2.500 (180,3 → 129,4). Por regra: repetição próxima −1.024, coerência temporal −61 (com +61 de
   tempo verbal genérico nos mesmos verbos), palavra dobrada −19, variação de nome −10, frase cortada
   −3, maiúscula −3, vocativo −2; nenhuma regra subiu fora dessa troca. O volume que resta vem dos
   confusores da Fase 7a (grafia anterior a 1943, “--” como travessão, narrador oitocentista). Sem
   anotação, não há falsos positivos por 10 mil nem precisão aqui, e esses textos não servem para
   afirmar confiabilidade no português brasileiro contemporâneo.
4. **Decisões reais** (`build/f8/precisao/`): as mesmas 650 decisões únicas de 6 livros e 1 autor;
   nenhuma decisão nova desde 07/10. Precisão total 79%.
   - pelo destino atual da Política v2: **pendências 497/582 = 85,4%**; observações 4/22 = 18,2%;
     regras retiradas 11/46 = 23,9% (fora das classes ativas); ativas no total 501/604 = 82,9%;
   - por classe (n ≥ 20): `narrative_tense` média 91% (408); `dialogo_contextual` baixa 91% (32);
     `languagetool:gramatica` média 60% (30). Abaixo de 20 decisões, só indicação: estrutura média
     39% (18) e baixa 10% (10); coerência temporal média 57% (14) e alta 100% (12); pontuação
     duplicada 92% (12); ortografia do LT 33% (12); pontuação de diálogo 78% (9); as demais com
     1 a 7 decisões;
   - nos alertas que o motor final emite: C com LT tem 19 pendências decididas (12 erro confirmado,
     4 intencional, 3 aceito; 0 falso positivo) e 8 observações (3 falso positivo, 3 intencional,
     2 erro); A com LT tem 34 de 36 pendências sem decisão;
   - os percentuais vêm de um autor e de decisões tomadas sobre versões anteriores do motor; não são
     garantia estatística.

#### Classificação dos problemas restantes

- **A — impeditivos:** nenhum demonstrado.
- **B — limitações aceitas nesta versão:**
  - o histórico de decisões depende de guardar o relatório (“Limpar resíduos”; solução proposta
    acima, aguardando aprovação);
  - memória do livro só com o último relatório; conflitos de alertas que sumiram saem no próximo
    salvamento (0 hoje);
  - ramo de palavra dobrada de `analysis.analyze` (só chamada direta);
  - texto da etapa (“quatro relações”), severidade inerte em `contracts.py`, cópia antiga na
    `.venv`;
  - estrutura (fragmento) com 39% e 10% em menos de 20 decisões, mantida pela Política v2 por
    decisão do autor;
  - `languagetool:gramatica` com 60% em 30 e categorias misturadas (Política v3, separada);
  - pontuação final ausente **sem validação** (19 decisões pendentes); não é declarada confiável;
  - as limitações da Fase 7b (crase dativa e concordância dependentes do modelo, correlação com
    principal impessoal, vírgula sujeito-verbo sem decisões, “--” como travessão, radical do
    perfil de fala nos usos que só suprimem, “Lia você vem?”, “Pobre Ana! tu…”) e os problemas 2
    e 3 da Fase 3.
- **C — melhorias futuras:** Política v3 do LT; “--” como travessão; acentuação (1/8) e ortografia
  sem o LT; validação da pontuação final depois da D6; textos contemporâneos anotados para
  generalização; aspas de título na pontuação de diálogo.

#### Questões separadas da estabilização (nenhuma impede o núcleo)

| Questão | Onde está | Impeditivo do FONTE? |
|---|---|---|
| Categorias e severidades do LT | Política v3 e app | Não: o LT é opcional; classe, severidade e destino atuais estão documentados e não mudam IDs |
| 19 decisões de pontuação final ausente | decisões do autor no app | Não: a regra fica sem validação, como pendência |
| Resolução de conflitos históricos | app | Não: 0 conflitos nos dados; registro cumulativo funciona |
| Código de saída da CLI na análise parcial | CLI e app | Não: o app detecta pela `metadata.analise_parcial` do relatório, não pelo código |
| Encerramento completo × parcial no app | app | Não: os registros já são separados; falta só a apresentação |

#### Testes (09/10)
- FONTE 503, pacotes 46, contrato Python, Coerencia 25: todos aprovados.
- Swift: `ContractCheck`, `BookMemoryCheck`, `DeskToolsCheck`, `ClosureCheck`,
  `FalsePositiveCheck`, `EditCheck`, `DeduplicationCheck`, `PartialAnalysisCheck`: todos aprovados.
- `xcodebuild` Release: aprovado.
- Comparações: 29 conjuntos e 3 textos independentes idênticos à Fase 7b; herança real reproduzida;
  58 relatórios reais lidos; simulação do salvamento.
- Herança e deduplicação: `BookMemoryCheck`, `DeduplicationCheck` e a herança real. Análise parcial:
  `test_languagetool_indisponivel` (6) e `PartialAnalysisCheck`.
- Depois da troca de versão para 1.5.0: FONTE, pacotes, contrato Python e `ContractCheck` de novo.
- Nenhuma chamada à API.

#### Versão proposta: FONTE 1.5.0 — Estabilização linguística
- `fonte/pyproject.toml` e `fonte/fonte/__init__.py` em 1.5.0; o contrato Python confere a versão.
- A montagem passa a rodar as 8 verificações Swift.
- README e versão do app ficam para a release (a linha “Versão atual” descreve a versão publicada).
- Sem tag, release ou push.

**Veredicto: APTO para estabilização.** Nenhum defeito impeditivo demonstrado. A solução de
preservação do histórico em “Limpar resíduos” é recomendada antes de usar essa limpeza, mas não
depende do motor e espera a aprovação do autor.
