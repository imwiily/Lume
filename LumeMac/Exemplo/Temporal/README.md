# Demonstração de relações temporais

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

“Talvez os estudantes saiam cedo.”, a afirmação sobre a água e a fala coloquial final permanecem sem alertas destas regras. Isso não certifica que qualquer frase semelhante será analisada corretamente; consulte as limitações em `../../RELACOES-TEMPORAIS.md`.

`relatorio.html` abre no navegador sem compilar o aplicativo. O DOCX original é preservado.
