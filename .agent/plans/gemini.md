# ExecPlan — Google Gemini como provedor opcional

**Objetivo.** Coerência com IA e Auditoria final podem usar `gemini-3.8-flash` no lugar do Claude, sem mudar contratos,
sem chamadas automáticas e sem misturar resultados de modelos.

**Decisões.**
- Cliente `Gemini` em `coerencia/coerencia/modelo.py`, mesma interface do `Claude` (`json`, `verificar`, `chamadas`,
  `orcamento`); `criar_modelo` escolhe por prefixo `gemini-`. API REST Interactions via urllib: nada novo a empacotar.
- Cache: a identidade já inclui o nome do modelo; nada mudou nos estados guardados.
- Preços: `PRECOS_GEMINI` (tarifa de 2027, conservadora). `total_output_tokens + total_thought_tokens` pode contar o
  raciocínio duas vezes: superestima, nunca subestima. Pesquisa: US$ 0,014 por consulta, 5 consultas reservadas no teto.
- Pesquisa: subcomando `pesquisar-fundamento`, texto livre (pesquisa + esquema é prévia na API), uma chamada, pergunta
  montada pelo app só com a classe do apontamento.
- Swift: `AIProvider`, `GeminiKey`, seleção de provedor na Home, chave na `KeySheet`, confirmação por provedor,
  seção de pesquisa no inspetor. Execução duplicada continua barrada por `isBusy`.

**Validação.** `coerencia/tests/test_gemini.py`, `fonte/tests/test_gemini_auditoria.py`, `tests/ValidatorV5Check.swift`
(bloco 5b). Nenhuma chamada real à API.

**Pendências.** Calibrar custo e saída com uma medição real autorizada; confirmar `GET /v1beta/models/{modelo}`,
`usage` e `url_citation` contra uma resposta real; resultados da pesquisa ficam só na sessão; Validador sem Gemini.
