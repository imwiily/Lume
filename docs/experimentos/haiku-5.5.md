# Experimento: Claude Haiku 5.5 (encerrado em 10/10/2026)

Branch `experiment/haiku-5.5`, a partir de `v1.7` (`ecffe56`). Não integrado à versão estável.

**Situação: ENCERRADO — compatibilidade técnica aprovada; substituição editorial não aprovada.**

## O que o código experimental faz

- `coerencia/coerencia/modelo.py`: aceita `claude-haiku-5-5` (esforço sem `fallbacks`, tarifa por faixa de
  100 mil tokens, erro se outro modelo responder); `OrcamentoGlobal`, ativado só por
  `LUME_ORCAMENTO_GLOBAL` (arquivo) e `LUME_ORCAMENTO_GLOBAL_LIMITE`, que acumula gasto entre execuções,
  confere o pior caso de cada chamada antes de enviá-la e usa a contabilidade completa (escrita de cache).
- `coerencia avaliar` grava esforço, tokens, modelos usados e trechos descartados em `avaliacao.json`.
- `scripts/avaliar_deteccao.py`: `--auditoria-esforco` e `--texto`.
- Modelos padrão, prompts, categorias e interface não mudaram.

## Resultados (corpus sintético, uma execução por configuração)

| Componente | Referência | Haiku medium | Haiku high |
|---|---|---|---|
| Coerência, 3 casos comparáveis (9 contradições) | Sonnet 5.5: 8/9 | 6/9 | 6/9 |
| Auditoria final, 6 textos (22 erros perdidos pelas regras) | Opus 5.5: 7 acertos | 5 acertos, 1 falso positivo | 5 acertos, 0 falsos positivos |

Gasto total: US$ 0,342 de US$ 0,50 autorizados. Economia observada: cerca de 85–96%, conforme a comparação.

## Limitações e pendências

- Referência Sonnet incompleta (3 de 5 casos), por teto de gasto; amostra editorial pequena.
- Haiku não ampliou a cobertura da Auditoria: seus acertos são subconjunto dos do Opus.
- A conta de custo da versão estável subestima a escrita de cache, e a tabela interna de preços do Sonnet 5.5
  tem a leitura de cache em US$ 0,20 (oficial: US$ 0,10). Corrigir à parte, na versão estável.
- O cache da Coerência não isola por nível de esforço (chave = modelo + pedido); melhorar antes de
  qualquer modo com mais de um esforço.
- Haiku high fica como candidato a um futuro modo econômico opcional; nenhuma decisão tomada.
