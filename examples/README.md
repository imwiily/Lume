# Exemplos e corpus de demonstração

Os relatórios incluídos são registros das versões indicadas; contagens históricas podem mudar com o motor atual. Para avaliar uma atualização, gere outra pasta de saída. As amostras de desenvolvimento não medem precisão em corpus independente. Caminhos dentro de cada seção são relativos à subpasta indicada.

## Generico

`Manuscrito-generico.docx` reúne os onze casos obrigatórios em capítulos separados. Os sete positivos devem produzir `age_conflict`, `object_continuity`, `premature_knowledge`, `scene_presence`, `relationship_conflict`, `object_state_conflict` e `chronology_conflict`. Os quatro controles não devem produzir alertas da regra `coerencia_generica`.

Execute no modo Editorial ou Ambas. Outras regras podem produzir observações independentes. Fonte reproduzível dos textos: `fonte/tests/corpus/generic.json`.

## Memoria

Abra `Manuscrito-memoria.docx` no Lume 0.10, importe `Busca-memoria.json` e use modo Editorial. O resultado esperado é cinco ocorrências: habilidade, estado de objeto, cronologia, ação narrativa após fala e referente ambíguo.

`Relatorio/relatorio.html` permite examinar as duas cenas e os sete fatos extraídos. `Relatorio/relatorio.json` contém a memória e as evidências completas. O exemplo contém problemas intencionalmente inseridos para regressão; não mede precisão em textos independentes.

## Memoria111

`amostra.txt` é o texto de referência; `amostra.docx` contém os mesmos oito parágrafos para exercício da CLI e do aplicativo.

Resultados esperados:

- Íris possui habilidade exclusiva de fogo e demonstra gelo em um evento `USE_ABILITY` com sujeito resolvido de “Ela”. São dois fatos separados, com o mesmo ID de personagem.
- “disse ela” atribui a fala a Íris.
- Entrada na torre, aquisição e perda da chave produzem três fatos adicionais. A chave mantém a identidade.
- Os dois dispositivos têm donos explícitos diferentes e IDs distintos; a destruição de um não conflita com o estado intacto do outro.
- Sete fatos, oito eventos semânticos, conversão de 7/8 e um conflito global (fogo × gelo). Taxas são desta amostra de desenvolvimento, não uma avaliação de precisão em corpus independente.

Para reproduzir, na raiz do repositório:

```sh
fonte/.venv/bin/python -m fonte.cli revisar examples/Memoria111/amostra.docx --saida build/amostra-111-nova --modo ambas
```

Use uma pasta de saída nova a cada execução. O teste `tests/check_memory_111_dom.cjs` aceita o caminho do HTML gerado como primeiro argumento e requer jsdom.

## Mestre

`Manuscrito-modular.docx` é uma amostra sintética pequena. Não é uma análise do manuscrito completo de Hikari No Sekai.

Abra o documento no Lume 0.8, escolha Ambas, Passado e configuração padrão. Os relatórios incluídos foram produzidos por FONTE 0.6.0 com spaCy 3.8.16 / pt_core_news_sm 3.8.0.

Resultado observado: 11 alertas — 3 linguísticos, 3 morfossintáticos, 3 de contexto curto e 2 de coerência global limitada. O auditor está indisponível. Uma ocorrência pode ser uma escolha legítima: “São” e “Está”, por exemplo, continuam como atenção editorial, não erro confirmado.

Confira “Além de disso”, “que, não” e “..”. A fala “Tô aqui, cê vem pra casa, maninho?” e as reticências “...” devem permanecer preservadas pelas novas regras determinísticas. Filtre por módulo e classificação e registre uma decisão sem alterar o DOCX.

`relatorio.html` abre diretamente no navegador e permite experimentar os filtros antes de compilar o aplicativo.

Nesta versão, “observa” recebe a explicação temporal específica, ligada a “abriu”, com a sugestão “observava”. A quantidade total continua a mesma. Consulte também `../Temporal` para exemplos independentes desta amostra.

## Qualidade113

Analise `Manuscrito-qualidade.docx` no modo Editorial ou Ambas. `casos.json` contém os textos e categorias esperadas por capítulo. Os sete casos positivos devem gerar um alerta genérico cada; estados com transição legítima, hipótese e estado físico sem contradição não devem gerar alerta genérico. Outras regras editoriais podem emitir observações independentes.

A suíte `test_fact_quality.py` verifica adicionalmente os papéis, os fatos, o histórico, a evidência e as contraprovas.

## Temporal

Amostra sintética para o Lume 0.8 / FONTE 0.6.0, com spaCy 3.8.16 e pt_core_news_sm 3.8.0. Não contém personagens nem depende do enredo de Hikari No Sekai.

Abra `Manuscrito-temporal.docx`, importe `Busca-temporal.json` e selecione **Ambas / Passado**. A configuração isola coerência temporal, acentuação contextual, quê final e pontuação duplicada; as demais regras ficam desligadas. Restaure o padrão antes de uma revisão geral.

São esperadas **9 ocorrências**: 2 linguísticas e 7 morfossintáticas. Dessas, 7 são prováveis erros e 2 são atenção editorial; nenhuma é erro confirmado. Contexto curto e coerência global ficam desativados por essa configuração. Auditoria continua indisponível.

| Trecho | Sugestão/decisão a avaliar |
| --- | --- |
| receberá | receberia |
| ligará | ligaria |
| anotam | anotavam |
| atravessamos | Conferir a intenção; presente e perfeito têm a mesma grafia |
| está | estava, se a descrição permanece no passado |
| construiam | construíam |
| distribuiam | distribuíam |
| que? | quê? |
| .. | Conferir ponto ou reticências; sem substituição única |

“Talvez os estudantes saiam cedo.”, a afirmação sobre a água e a fala coloquial final permanecem sem alertas destas regras. Isso não certifica que qualquer frase semelhante será analisada corretamente; consulte as limitações em [arquitetura e limites](../docs/arquitetura.md).

`relatorio.html` abre no navegador sem compilar o aplicativo. O DOCX original é preservado.
