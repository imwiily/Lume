# ExecPlan — Validador de decisões V5 (experimental): contrato da V4.1 avaliado por GPT-6.1 Sol

Branch `feature/validador-decisoes`. Módulo isolado `fonte/fonte/validador_v5.py` (V2, V3, V4 e V4.1 e seus
estados persistidos não são lidos nem alterados), execução em `scripts/experimento_v5.py`, testes em
`fonte/tests/test_validador_v5.py`. Sem interface; sem chamadas pagas nesta etapa.

## Objetivo
Comparar fidelidade editorial e custo do GPT-6.1 Sol com o Sonnet 5.5 da V4.1 nos mesmos 16 apontamentos,
com o mesmo contrato editorial (prompt, esquema, significados, antecedentes, derivação do resultado e
verificação determinística de evidências). Só o necessário para a API da OpenAI foi adaptado.

## Fatos conferidos na documentação oficial (11/10/2026)
Identificador `gpt-6.1-sol` (um único snapshot); endpoint `/v1/responses`; saída estruturada com
`text.format` JSON Schema estrito; `reasoning.effort` (low, medium padrão, high, xhigh, max); os tokens de
raciocínio contam no `max_output_tokens` e são cobrados como saída; uso em `usage.input_tokens_details`
(`cached_tokens`, `cache_write_tokens`) e `usage.output_tokens_details.reasoning_tokens`; preço padrão por
milhão: entrada US$ 2,00, leitura de cache US$ 0,10, escrita de cache US$ 2,50, saída US$ 10,00 (até 272 mil
tokens de entrada). A documentação recomenda reservar bastante folga para raciocínio.

## Isolamento
Estado `validacoes-v5.json` e trava próprios; chave de configuração com provedor, modelo e esforço (mudar
qualquer um torna a validação desatualizada, sem reprocesso automático). Nada de Sonnet, Opus ou resultados
anteriores é enviado ao GPT (testado). `store=false`. Chave só em `OPENAI_API_KEY` ou nas Chaves do macOS
(serviço `lume-openai`), nunca em arquivo, argumento ou registro.

## Orçamento
Obrigatório e preventivo por chamada (pior caso: entrada como escrita de cache + limite de saída inteiro);
o limite de saída por pedido é 10.000 + 4.000 por item, porque o raciocínio consome o mesmo limite.
Timeout conta o pior caso. Lote cortado é dividido. Teto exigido na execução.

## Fora de escopo
Interface, homologação, merge, qualquer chamada paga sem autorização expressa.
