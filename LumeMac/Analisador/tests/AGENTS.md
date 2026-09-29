# Testes e regressão

Aplicar as instruções da raiz Git e de `../AGENTS.md`.

- Usar a infraestrutura `unittest` existente. Executar a partir de `Analisador/`
  para importar os fontes atuais; não criar uma suíte paralela em `tests/` na raiz.
- Para cada bug, criar primeiro a reprodução mínima genérica e demonstrar a falha
  esperada. Cobrir positivo, negativo, ambiguidade e substituições de nomes e objetos.
- Conferir trecho, parágrafo, categoria, severidade e sugestão; não apenas o total
  de alertas. Controles que não devem gerar alerta são tão importantes quanto os
  positivos.
- Manter o corpus `corpus/deteccao/` (desenvolvimento e validação) e as regressões
  históricas. Casos novos representam classes editoriais, não trechos de uma obra.
- A Coerência com IA é testada com modelo simulado; nenhum teste chama a API.
- Não enfraquecer asserts, remover testes ou regravar resultados esperados para
  esconder regressões. Explicar qualquer mudança legítima de expectativa.
- Não versionar Echoes/Hikari completos. Usar casos neutros; trechos reais somente
  quando fornecidos/autorizados.
- Registrar falhas e skips. Testes criados no desenvolvimento não medem precisão
  independente; taxas de acerto exigem corpus anotado.
