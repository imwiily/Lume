# Testes semânticos e regressão

Aplicar as instruções da raiz Git e de `../AGENTS.md`.

- Usar a infraestrutura `unittest` existente. Executar a partir de `Analisador/`
  para importar os fontes atuais; não criar uma suíte paralela em `tests/` na raiz.
- Para cada bug, criar primeiro a reprodução mínima genérica e demonstrar a falha
  esperada. Cobrir positivo, negativo, ambiguidade e substituições de identidade.
- Conferir entidade, sujeito/objeto/destinatário, escopo, polaridade, evidência,
  confiança, origem, validade, histórico e estado atual; não apenas total de alertas.
- Preservar controles que não geram fatos persistentes ou alertas fortes. Um
  resultado `unresolved` pode ser correto; não exigir resolução artificial.
- Manter `corpus/generic.json` e as regressões históricas. Casos novos devem
  representar classes editoriais e não ensinar regras particulares de manuscritos.
- Não enfraquecer asserts, remover testes ou regravar golden outputs para esconder
  regressões. Explicar qualquer mudança legítima de expectativa e preservar a prova.
- Não versionar Echoes/Hikari completos. Usar casos neutros; trechos reais somente
  quando fornecidos/autorizados. Testes selecionados não substituem corpus integral.
- Registrar falhas e skips. Testes criados no desenvolvimento não medem precisão
  independente; taxas de acerto exigem corpus anotado.
