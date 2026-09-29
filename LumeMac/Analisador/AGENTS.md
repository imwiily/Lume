# Motor Python FONTE

Aplicar também o `AGENTS.md` da raiz Git. O pacote é `fonte-revisor`; código em
`fonte/`, testes em `tests/`. Preservar módulos e contratos existentes.

- Ler `../Documentacao/ARQUITETURA.md` antes de alterar o pipeline. Leitura,
  contratos e pipeline não recebem regras de obras.
- Regras linguísticas e gramaticais ficam em `linguistic.py`, `grammar.py`,
  `temporal.py` e `editorial/`; o corretor LanguageTool, em `languagetool.py`.
  Contradições narrativas são responsabilidade do Coerencia (`coerencia_ia.py`, com
  fonte única em `../../LumeCoerencia/`); não recriar memória narrativa heurística.
- Preservar offsets em pontos de código Unicode, trechos exatos e índices de
  parágrafo. Não trocar offsets por bytes, grafemas ou unidades UTF-16.
- Emitir progresso conforme o protocolo existente (`LUME_PROGRESS`, com
  `done`/`total`/`unit` opcionais); não anunciar Auditor Final implementado nem
  transformar suspeita em erro confirmado.
- Regras retiradas continuam aceitas nas configurações (`RETIRED_RULES`), sem efeito.
- Rodar `.venv/bin/python -c 'import fonte; print(fonte.__file__)'` nesta pasta;
  a importação deve apontar para os fontes locais. Executar
  `.venv/bin/python -m unittest discover -s tests -v`.
- Distinguir resultado nos fontes, pacote instalado e executável congelado; não
  apresentar um como outro.
