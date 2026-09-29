# Motor Python FONTE

Aplicar também o `AGENTS.md` da raiz Git. O pacote é `fonte-revisor`; código em
`fonte/`, testes em `tests/`. Preservar módulos e contratos existentes.

- Ler `../Documentacao/ARQUITETURA.md` e os documentos v0.11 na raiz antes de
  alterar memória. Leitura/contratos/pipeline não devem receber regras de obras.
- Usar os papéis de `semantic_roles.py` e eventos já resolvidos na promoção.
  Mapear `semantic.py`, `generic_facts.py` e `narrative*.py` antes de introduzir
  um novo estágio; não duplicar extração ou banco de fatos.
- Garantir origem, evidência, escopo, polaridade, cadeia de confiança e identidade
  ao promover candidatos. Fatos locais, persistentes e descartados precisam de
  justificativa rastreável. Nenhuma dependência incerta ganha confiança por padrão.
- Preservar snapshot do manuscrito e saídas das etapas anteriores. Novos registros
  derivados não autorizam reescrever fatos/eventos de origem. Transições atualizam
  a visão derivada do histórico de forma coerente.
- Preservar offsets em pontos de código Unicode, trechos exatos e índices de
  parágrafo. Não trocar offsets por bytes, grafemas ou unidades UTF-16.
- Emitir progresso conforme o protocolo existente; não anunciar Auditor Final
  implementado nem transformar suspeita narrativa em erro confirmado.
- Rodar `.venv/bin/python -c 'import fonte; print(fonte.__file__)'` nesta pasta;
  a importação deve apontar para os fontes locais. Executar
  `.venv/bin/python -m unittest discover -s tests -v` e os demais gates aplicáveis
  de `../../docs/testing/acceptance-v0.11.md`.
- Alterações de schema/fact bank/memória entre módulos exigem ExecPlan. Distinguir
  resultado nos fontes, pacote instalado e executável; não apresentar um como outro.
