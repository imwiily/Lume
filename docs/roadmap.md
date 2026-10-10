# Roadmap

Aprovado em 10/10/2026. O Lume é pessoal, gratuito, de código aberto e distribuído só pelo GitHub.

| Versão | Janela | Escopo |
| --- | --- | --- |
| 1.8 | outubro de 2026 | Correções urgentes: orçamento da API, segurança das atualizações e integridade documental. Sem regras novas, sem mudança de prompts, contratos JSON ou interface. |
| 1.9 | fevereiro–março de 2027 | Correções menores e estabilização. |
| 2.0 | junho–julho de 2027 | Homologação integral, nenhum defeito grave conhecido e validação editorial independente. |

A branch de trabalho da 1.8 é `release/lume-1.8`. Os números de versão dos componentes e do app só
mudam na entrega de cada versão. Resultados do experimento Haiku 5.5 (`experiment/haiku-5.5`) não
entram na 1.8 sem decisão própria.

## 1.8 — andamento

- [x] Orçamento da API (Coerência e Auditoria final): ver [orcamento-api.md](orcamento-api.md).
- [x] Segurança das atualizações: auditada em 10/10/2026; três problemas de baixa gravidade
  (limpeza de `Engines/` e `.staging-*`, mensagem de link pendente, impressão digital do pacote)
  transferidos para a 1.9.
- [x] Integridade documental (correção no Pages): ver [validacao.md](validacao.md).
- Entregue em 10/10/2026 sem validação manual da interface (decisão do proprietário).
