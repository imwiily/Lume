# Remover o relatório HTML e resíduos

## Objetivo e escopo

O motor passa a gravar só `relatorio.json`; o app já revisa tudo pela própria janela.
Antes: `fonte revisar` gravava `relatorio.html` + `relatorio.json` e `--abrir` abria o HTML.
Depois: só o JSON; o Coerencia avulso imprime as pendências e mantém os JSON da pasta.
Fora do escopo: contratos JSON, leitura de relatórios antigos (inclusive `narrative_summary`,
mantido em `Models.swift` por compatibilidade) e regras de detecção.

## Estado observado (branch `organizacao-e-deteccao`, base 28a65d9)

- `fonte/fonte/report.py` + `report.html`: único uso em `cli.py`, `packaging/lume_engine.py`
  (teste de saúde) e `fonte/tests/test_fonte.py`.
- `coerencia/coerencia/relatorio.py`: usado só pelo CLI e por `RelatorioTests`.
- `tests/check_*_dom.cjs`: dependiam dos `.html` de `examples/`; exigiam jsdom, ausente.
- `examples/Generico`, `Memoria`, `Memoria111`, `Qualidade113`: memória narrativa removida
  em 29/09/2026; citavam regras e testes inexistentes; nenhum teste os usava.
- Swift: `openHTML()` e o menu “Abrir relatório HTML”; `LightRing` sem uso.
- `vulture` (confiança mínima 0) em `fonte/fonte`, `coerencia/coerencia`, `packaging`,
  `scripts`: nenhuma função ou classe sem uso.

## Etapas e evidências

1. Remover geração/abertura do HTML no FONTE e no Coerencia; testes passam a exigir que a
   saída tenha só `relatorio.json`. Removidos os testes do próprio HTML (escape de
   `</script>`, destaque em `<mark>`), que não têm mais objeto.
2. Remover arquivos HTML, DOM e exemplos obsoletos; atualizar documentação.
3. Swift: menu e `openHTML`, `LightRing`.

Comandos (raiz): suítes do FONTE, pacotes, contrato Python, Coerencia e
`bash scripts/montar-lume.command` (contrato Swift, build Release e saúde do motor).

## Resultado — 01/10/2026

FONTE 229 testes OK; pacotes 25 OK; contrato Python OK; Coerencia 24 OK; montagem completa
OK. Alertas não mudam (nenhuma regra alterada), então não há comparação A/B.
