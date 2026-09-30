# Fechamento da cadeia de promoção v0.11

## Objetivo e escopo

Executar a ordem fornecida em 29/09/2026: candidatos explícitos, promoção seletiva,
memória entre cenas, histórico/validade derivados e instrumentação dos comparadores
existentes. Exemplo: aquisição → transferência conserva o objeto e encerra a posse
anterior; saída encerra localização sem inventar destino. Auditor Final, novas
categorias de erros e regras específicas de obras ficam fora do escopo.

## Estado observado

HEAD `24f73a869ee909b155a1b5faaa601744511d2354`, workspace com extensa implementação
local anterior, preservada. Fontes reais importados de LumeMac/Analisador/fonte.
`narrative.promote`, `generic_facts.extract_generic`, `finalize_memory` já extraem
fatos, mas não expõem candidatos. FactBank.consolidate deriva estados sem encerrar
todas as relações, e diagnostics informa comparação global null. Papéis eram
exportados somente depois da promoção. Baseline dos arquivos tocados em
LumeMac/Saida/fact-candidates-v011/before-source, não usar git HEAD como baseline.

## Arquivos e arquitetura

Motor em LumeMac/Analisador/fonte: manter semantic/narrative/generic_facts e acrescentar
um filtro interno de candidatos; sem novo estágio público. Extensões JSON aditivas,
schema de relatório 1/memória 2. Papéis alimentam propostas; filtros mantêm origem,
escopo, polaridade e limites de confiança. Consolidação copia fatos antes de derivar
validade. Manuscrito nunca é editado. Testes em Analisador/tests, contrato Swift
antigo e novo sem exigir mudança de interface.

## Etapas e critérios

- [x] Leitura das instruções, arquitetura, aceitação e implementação.
- [ ] Baseline: suíte atual, manuscritos A e B com configuração/hash iguais.
- [ ] Reproduções antes do patch: candidato/origem/descarte, transferência,
  saída, transições entre cenas, ruído, ambiguidade, confiança, pares globais.
- [ ] Candidatos explícitos e métricas com denominadores documentados (A05/A10).
- [ ] Papéis, identidade, relevância e persistência (A03/A04/A06/A09).
- [ ] Histórico/validade/current_state e classes prioritárias (A07/A08).
- [ ] Suíte completa, corpus sintético, integração, contratos Python/Swift (A01/A02/A11/A12).
- [ ] Manuscritos A e B e inspeção semântica comparável (A13).
- [ ] Revisão separada do diff e relatório de gates/limites (A14).

## Comandos e evidências

Saída própria: LumeMac/Saida/fact-candidates-v011. Executar comandos de
docs/testing/acceptance-v0.11.md. Baseline-tests.log: `.venv/bin/python -m unittest
discover -s tests -v` em Analisador. `Scripts/validate_real_memory.py` em LumeMac
com os DOCX externos e baselines indicados em docs/analises/2026-09-29-diagnostico-memoria-narrativa.md;
saídas before-manuscrito-b e before-manuscrito-a tornam-se baselines deste patch para after-*.
Fontes apenas nesta etapa; pacote instalado/executável não são evidência dos fontes.

Expectativas fixadas antes da implementação: controles triviais não persistem,
transferência explícita preserva destinatário mesmo com observador, ambiguidades
não produzem memória forte, nenhuma regressão nos testes existentes. Conversão
avaliada nos casos anotados antes/depois; aumento de volume real não prova precisão.
Falsos fatos e precisão em corpus independente continuam sem medida.

## Descobertas e validação

Em andamento. Resultados e gates serão atualizados com comandos efetivamente executados.

### Correção legítima de expectativa histórica

`test_ordered_object_transitions` esperava que tirar a chave do bolso deixasse
`object_location=bolso` como estado final. A ordem desta etapa exige expirar a
localização após retirada. A expectativa passa a `carried`, com asserts adicionais
de `source_location=bolso` e encerramento do fato anterior. O comparador existente
continua validando a origem contra a localização anterior: mesa → tirar do bolso
sem transição continua gerando `object_continuity`. Nenhum negativo foi removido.
