# Pendência do motor — anterioridade com verbo aspectual + infinitivo

Registrada em 10/10/2026 durante a investigação do Validador de decisões. **Não corrigida**: o FONTE
não foi alterado nesta entrega (fora do escopo; ver `.agent/plans/validador-decisoes.md`).

## Falha observada (texto sintético, FONTE 1.5.0, narração no presente)

`temporal.past_plane` devolve `"anterior"` para o perfeito em oração completiva simples, mas `None`
quando o verbo da completiva é aspectual e rege um infinitivo (“começar a”, “passar a”, “terminar de”).
`None` equivale a “passado da linha principal”, e o alerta de tempo verbal é emitido.

| Frase | Verbo | `past_plane` |
|---|---|---|
| Ela está sentindo que perdeu o controle. | perdeu | `anterior` (correto) |
| Ela acha que quis ajudar. | quis | `anterior` (correto) |
| Ela está sentindo que **começou a** perder o controle. | começou | **`None`** |
| Ele sente que **começou a** duvidar de tudo. | começou | **`None`** |
| Ela percebe que **terminou de** arrumar a casa. | terminou | **`None`** |
| Ela sabe que **passou a** odiar o barulho. | passou | **`None`** |
| Ele sente que **começou a** chover. | começou | **`None`** |

Todas têm o mesmo perfil (`ccomp` de um verbo no presente), a mesma leitura legítima (fato anterior ao
agora) e o mesmo resultado indevido.

## Onde olhar (hipótese, não verificada)
`fonte/fonte/temporal.py`: `dependent_clause` → `predicate`, `misattached` e `introduced`. A diferença
entre os dois grupos de frases está na presença do infinitivo preposicionado (`xcomp`) sob o verbo.

## Critério para a correção futura
Classe, não caso isolado (AGENTS.md): perfeito de verbo aspectual/fasal + `a|de` + infinitivo dentro de
completiva de verbo de percepção ou cognição no presente. Positivos e negativos próprios; medir com
`scripts/avaliar_deteccao.py` e conferir que a precisão das pendências não cai.
