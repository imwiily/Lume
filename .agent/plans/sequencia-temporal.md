# Sequência temporal entre verbos, frases e sujeito

## Objetivo e escopo

Passar de “presente encontrado em texto no passado” para “presente que representa um evento
narrativo, entre ações no passado, do mesmo sujeito e cena”. Aumentar o recall de quebras
temporais reais e, ao mesmo tempo, dar peso menor aos presentes legítimos (verdade geral,
estado, propriedade, pensamento, comentário).

Antes/depois esperado:
- “Ele fechou a porta. Caminha até a janela. Depois voltou.” — antes: `Tempo verbal`, média,
  igual a qualquer presente. Depois: `past_present_past`, confiança alta.
- “Ela pega a chave e abriu o portão.” — antes: `Tempo verbal` genérico (ou nada, quando o
  modelo lê o verbo como adjetivo). Depois: `coordinated_tense_mismatch`, alta.
- “O gelo derrete quando a temperatura aumenta.” — antes: `Tempo verbal`, média. Depois:
  continua visível, com confiança baixa (verdade geral).

Fora do escopo: Auditor Final (fora do escopo atual em `AGENTS.md`; avaliado abaixo, não
implementado), novas regras de dêixis com alerta próprio, correferência além de sujeito
explícito igual ou elíptico compatível.

## Estado atual observado (revisão `551ad7c`)

- `fonte/fonte/analysis.py` (`Tempo verbal`): cada verbo finito comparado ao tempo
  predominante do documento; peso único (Verificar, média, editorial_attention); exceções em
  `temporal.legitimate_present`.
- `fonte/fonte/temporal.py` (`relations`): só dentro da frase, caminhando do presente para o
  passado na árvore. `coordinated_past_present` cobre passado → presente coordenado; o sentido
  presente → passado (“pega … e abriu”) nunca é examinado. Nenhuma janela entre frases.
- `temporal.form` só aceita a etiqueta do modelo: “segura” etiquetado ADJ (com sujeito e
  objeto) e “Procura” no início da frase (NOUN) ficam sem tempo.
- `fonte/fonte/pipeline.py`: o alerta específico do módulo temporal substitui o genérico no
  mesmo trecho.
- `grammar.agreement`: “nenhum/cada” exige DET/PRON (o modelo dá NUM); não há concordância por
  atração (“a lista de objetos estavam”).
- Resíduos: palavra repetida coberta; dois auxiliares finitos diferentes não.

## Arquivos afetados

- `fonte/fonte/temporal.py`: `event_tense` (modelo + léxico + sintaxe, com segunda leitura em
  minúscula), `present_function` (classificação semântica conservadora), `sequence` (estado
  narrativo local e os três detectores), mapeamento de confiança `alta`.
- `fonte/fonte/pipeline.py`: chama `sequence` na etapa morfossintática, sob a regra
  `coerencia_temporal`; o alerta específico substitui o genérico.
- `fonte/fonte/analysis.py`: `Tempo verbal` genérico com confiança baixa quando o presente não
  é evento narrativo; resíduo de edição (dois auxiliares finitos) sob `palavra_consecutiva`.
- `fonte/fonte/grammar.py`: “nenhum/cada” etiquetado NUM; concordância por atração.
- Testes novos em `fonte/tests/test_temporal_sequence.py`; corpus de desenvolvimento.

Sem mudança de schema: os alertas novos usam `rule="coerencia_temporal"` e `relation` com o
subtipo, como os existentes; IDs dos alertas genéricos não mudam (só confiança).

## Estado narrativo local

Eventos = predicados finitos da narração (passado/presente), em ordem, com frase, bloco,
sujeito (explícito ou elíptico com pessoa/número) e função. Janela: até 4 frases antes e 2
depois, no mesmo parágrafo ou no anterior; título zera. `past_present_past`: presente evento
entre passados (antes e depois). `coordinated_tense_mismatch`: verbos em `conj`, sujeito igual
ou elíptico compatível, tempos presente/passado. `same_subject_narrative_shift`: presente
evento após ≥2 passados do mesmo sujeito (ou elíptico compatível) sem presente vizinho.

## Etapas

1. [x] Testes (devem detectar, não devem, ambíguos, resíduos, concordância) falhando.
2. [x] `event_tense` + `present_function` + `sequence`; integração no pipeline.
3. [x] Rebaixar o genérico; resíduos; concordância.
4. [x] Suítes, corpus, manuscritos A/B antes/depois; documentação.

## Auditor Final (avaliação)

Uma auditoria independente exigiria uma segunda leitura com critérios próprios (não os mesmos
detectores). A janela de `sequence` já é uma leitura independente da regra genérica para tempo
verbal; promovê-la a etapa `audit` mudaria a etapa marcada como `not_implemented` no contrato e
na interface. Fica como proposta para o autor decidir.

## Progresso e decisões

- 03/10/2026: diagnóstico com os exemplos do pedido no pipeline atual (tense=passado): 10 de 13
  casos já geram `Tempo verbal` genérico (média); 3 não geram (“Procura” lido como substantivo,
  “segura” como adjetivo); os 5 presentes legítimos recebem o mesmo alerta, com o mesmo peso.
- 03/10/2026: implementado. Achados durante a validação: (1) a 1ª pessoa não pode ser
  “comentário do narrador” (esconderia “Abri… Procuro… Acendi”); (2) “estar” e “parecer” +
  infinitivo narram e não são estado; (3) a morfologia do modelo erra a pessoa na 1ª pessoa sem
  sujeito, então a coordenação compara o sujeito herdado; (4) formas só verbais no léxico
  (“Abri”, “Procuro”) bastam contra a etiqueta do modelo; (5) quantificadores partitivos na
  concordância. Resultados em `docs/validacao.md`.

## Etapa 2 — estado temporal local (03/10/2026)

Diagnóstico com os exemplos do pedido: `same_subject_narrative_shift` já detectava a maioria
dos presentes no fim de sequência (sem exigir passado depois). Escapavam: outro sujeito na mesma
cena (não havia detector de cena); presente seguido de outro presente na mesma frase (tratado
como mudança deliberada); ‘ainda’ tratado como âncora no presente; verbos lidos pelo modelo
como nome, adjetivo ou infinitivo; objeto posposto lido como sujeito; pessoa e número
comparados como texto único. Implementado `local_state`, `local_narrative_tense_shift`,
cadeia de sujeito consistente, quebras de cena, evidências. Resultados em `docs/validacao.md`.

## Etapa 3 — coordenação, condicionais e concordância (03/10/2026)

Diagnóstico: a maior parte dos exemplos já era detectada. Faltavam: locução no passado como
âncora (o auxiliar finito era descartado), coordenação com outro sujeito, ‘vira’ ambíguo,
marca de tempo da oração coordenada contaminando a principal, “?” separado pelo modelo,
pronome × nome na cadeia, regra de condicional (inexistente), núcleo singular com determinante
e partitivo “uma das”. Pendente: comparação nos manuscritos de referência (arquivos ausentes).
