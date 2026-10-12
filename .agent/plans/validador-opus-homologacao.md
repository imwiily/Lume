# ExecPlan — Homologação do Opus direto como arquitetura candidata do Validador de decisões

Estado em 11/10/2026: **candidata, não homologada**. Nada disto integra o Opus à Mesa de Revisão; o
Validador V2 e o V3 experimental ficam como estão. Nenhuma decisão humana ou manuscrito é alterado.

## Motivo
O experimento A/B (ver `validador-v3.md`) não mostrou benefício do Haiku e mostrou variação do Opus entre
execuções com entrada idêntica. Antes de qualquer integração é preciso medir repetibilidade e precisão.

## Achados que a homologação precisa tratar
1. **Repetibilidade:** 3 de 14 itens com entrada byte a byte idêntica mudaram de classe (1 só de rótulo,
   2 de interpretação). O pedido à API não define temperatura nem semente (modelo com raciocínio adaptativo).
   O id do pedido da API não era gravado: o script de repetibilidade passa a gravá-lo.
2. **Reconciliação:** a regra atual só compara alertas com trechos sobrepostos. Alertas do mesmo fenômeno no
   mesmo parágrafo, sem sobreposição, podem receber critérios opostos sem aviso. Só os itens do experimento
   entram na reconciliação (um subconjunto).
3. **"Ausência de razão" fraca:** a prova contextual exigida para contestar `Estilo do autor`/`Intencional`
   é verificada só quanto à existência e à posição (fora do alvo); uma frase qualquer a satisfaz. Nunca
   houve `justificativa_editorial=presente` em 32 julgamentos.
4. **Premissa herdada:** a hipótese do detector de tempo verbal repete o tempo declarado pelo usuário.
5. **Recorrência não informada:** o modelo não sabe que o mesmo fenômeno ocorre várias vezes no parágrafo
   ou no capítulo, o que é indício de voz.

## Plano de homologação (cada fase tem critério verificável editorialmente)
Os limiares abaixo são propostas a aprovar; não foram tratados como aceitos.

**Fase 1 — Repetibilidade** (`scripts/repetibilidade_opus.py`, preparado, não executado). 5 rodadas do grupo A
no mesmo conjunto: 3 idênticas, 1 em ordem invertida, 1 com um item por pedido. Registra id do pedido e modelo
servido por chamada. Métricas: concordância por item, variação só de rótulo × de interpretação, itens em que a
contestação aparece em algumas rodadas e não em todas. Critério proposto: nenhum item cruza contestação entre
rodadas idênticas; itens instáveis ficam marcados para revisão humana obrigatória.

**Fase 2 — Corpus sintético controlado** (escrito do zero, publicável): ≥ 30 decisões em três grupos —
erros objetivos rotulados como estilo, escolhas literárias legítimas (oralidade, voz, repetição de ritmo,
anterioridade) e casos ambíguos. Mede precisão e cobertura das contestações sem depender de manuscrito real.
Critério proposto: nenhuma escolha legítima contestada; ≥ 80% dos erros objetivos contestados; ambíguos
inconclusivos.

**Fase 3 — Revisão editorial cega** do conjunto real: o autor classifica cada contestação (procedente,
improcedente, inconclusiva) sem ver o modelo nem a versão. Critério proposto: precisão das contestações
registrada com intervalo; nenhuma contestação improcedente em categorias editoriais sem aviso na interface.

**Fase 4 — Melhorias candidatas (só depois das fases 1 a 3, cada uma com teste próprio):** contexto de
recorrência local, verificação de relevância da prova de ausência, consistência entre alertas do mesmo
parágrafo sem sobreposição, neutralização da premissa de tempo. Mudam o prompt: nova versão e nova medição.

## Fora de escopo
Integração à Mesa de Revisão, alteração de decisões, publicação, tag ou merge.
