"""Auditoria final com IA: depois das quatro etapas, o Claude relê cada capítulo com os
alertas já emitidos e procura só problemas novos.

Opcional e desligada por padrão, porque custa dinheiro. Nada é enviado sem confirmação. Os
trechos devolvidos pelo modelo são conferidos no parágrafo, e o que não existir é
descartado. Plano: `.agent/plans/auditor-final.md`.
"""


def auditar(blocks, anteriores, avancar=None, **opcoes):
    """Devolve (ocorrências novas, avisos, resumo da rodada). `anteriores` é uma cópia dos
    alertas das etapas anteriores, só para leitura."""
    raise ValueError("Auditoria final com IA: ainda não disponível neste motor.")
