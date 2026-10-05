# Exemplos e corpus de demonstração

Os relatórios incluídos são registros das versões indicadas; contagens históricas podem mudar com o motor atual. Para avaliar uma atualização, gere outra pasta de saída. As amostras de desenvolvimento não medem precisão em corpus independente. Caminhos dentro de cada seção são relativos à subpasta indicada.

## Mestre

`Manuscrito-modular.docx` é uma amostra sintética pequena. Não é uma análise do manuscrito A completo.

Abra o documento, escolha Ambas, Passado e configuração padrão. O relatório incluído foi regenerado pelo FONTE 1.3.1 (spaCy 3.8.16 / pt_core_news_sm 3.8.0), com textos sintéticos, sem o LanguageTool.

Resultado observado: 11 alertas — 3 linguísticos, 3 morfossintáticos, 3 de contexto curto e 2 de coerência global limitada. O auditor está indisponível. Uma ocorrência pode ser uma escolha legítima: “São” e “Está”, por exemplo, continuam como atenção editorial, não erro confirmado.

Confira “Além de disso”, “que, não” e “..”. A fala “Tô aqui, cê vem pro jantar, primo?” e as reticências “...” devem permanecer preservadas pelas novas regras determinísticas. Filtre por módulo e classificação e registre uma decisão sem alterar o DOCX.

Nesta versão, “observa” recebe a explicação temporal específica, ligada a “abriu”, com a sugestão “observava”, classificada como provável erro. A quantidade total continua a mesma. Consulte também `../Temporal` para exemplos independentes desta amostra.

## Temporal

Amostra sintética; relatório regenerado pelo FONTE 1.0.0, com spaCy 3.8.16 e pt_core_news_sm 3.8.0. Não contém personagens nem depende do enredo do manuscrito A.

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

O DOCX original é preservado.
