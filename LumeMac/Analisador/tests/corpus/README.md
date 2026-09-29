# Corpus de avaliação

`deteccao/` contém textos sintéticos com erros anotados, usados por
`Scripts/avaliar_deteccao.py` para medir a detecção (erros encontrados e alarmes
falsos, por categoria):

- `desenvolvimento.json` pode orientar a criação e o ajuste de regras;
- `validacao.json` fica reservado para medir, sem ajustar regras a partir dele.

Casos novos, inclusive os vindos do uso real do app, devem representar uma classe de
erro (com um exemplo parecido que não é erro) e nunca depender do nome de uma
personagem ou obra. O corpus é escrito junto com as regras e não substitui uma
avaliação independente.

A memória narrativa heurística e o corpus `generic.json` foram removidos em 29/09/2026;
as contradições narrativas passaram a ser verificadas pela Coerência com IA
(`../../../LumeCoerencia/`).
