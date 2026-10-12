# ExecPlan — Integração supervisionada do Validador V5 ao Lume

Branch `feature/validador-decisoes`. V5 (GPT‑6.1 Sol, medium) como segunda opinião editorial supervisionada, em piloto
interno, **desligada por padrão**. A decisão humana é a autoridade final; a IA nunca altera decisões nem manuscrito.
V2 e a inferência da V5 permanecem intactas.

## Fases

- [x] **Fase 1 — backend Python** (`fonte/fonte/validador_v5_integracao.py`, 3 subcomandos na CLI, 28 testes).
- [x] **Fase 2 — fundação Swift** (sem interface): chave da OpenAI (`lume-openai`) no Keychain, argumentos sem
      segredos (`--tentativas 1`, versão exata, sem contexto parcial/adicional/reanálise), modelos e protocolo JSON
      (`app/Lume/ValidatorV5.swift`), `safeTail` no `PythonRunner`, estado/métodos do `ReviewStore` guardados pelo
      piloto (desligado), teste `tests/ValidatorV5Check.swift` e contrato `fonte/tests/test_validador_v5_swift_contrato.py`.
- [x] **Fase 3 — interface** (inativa para uso real): opção "Piloto: Validador V5" e chave da OpenAI na `KeySheet`,
      "Segunda opinião…" no inspetor e na linha de status, seleção explícita (nada marcado, limite 40, teto até US$ 5,00),
      confirmação com autorização por execução e pré-visualização, revalidação antes do envio, resultados na Mesa e no
      inspetor, `ValidatorV5Coordinator` (fluxo testável), cenas DEBUG com fixtures.
- [ ] **Fase 4 — piloto supervisionado**: ver bloqueadores.

## Bloqueadores registrados para a Fase 4

1. **Retomada de contexto adicional sem reprocessamento pago desnecessário.** Hoje a segunda rodada fica desligada e o
   pedido do modelo vira pendência; resolvê-la exige `--reanalisar` (que reenvia o item inteiro). É preciso um caminho
   que reaproveite a primeira resposta e pague só o contexto adicional, sem tocar a inferência da V5.
2. **Janela de concorrência na movimentação do histórico.** `_reanalisar` segura a trava da V5, grava o histórico e a
   solta antes de `v5.avaliar` retomá-la. É preciso mover e executar sob a mesma trava (ou torná-la reentrante) para
   fechar a janela.
3. **Autorização explícita e limite financeiro validados antes da execução real.** A interface só pode chamar a
   execução depois de uma confirmação por rodada (obra, capítulos, itens, provedor, custo esperado/máximo e teto) e o
   teto precisa ser conferido de novo no backend no momento do envio; teste ponta a ponta com cliente simulado antes
   de qualquer chamada real.

## Limitações conhecidas (Fase 2)

- O app atual ainda não enxerga os subcomandos V5 com o motor embutido antigo (reconstrução do motor é etapa à parte).
- `ValidatorBackend` só tem valor no `UserDefaults` e nenhuma tela o liga.
- Isolamento Anthropic × OpenAI testado por serviços distintos, memória e itens de teste descartáveis no Keychain;
  o `AnthropicKey` real não foi alterado nem exercitado.

## Pendências da Fase 3 para a Fase 4

- Pré-visualização aproximada: usa o relatório (parágrafo, hipótese, decisão, contexto ±2). O texto exato do pedido
  (até ±3 parágrafos do manuscrito) exige um subcomando de pré-visualização no backend.
- Os métodos do `ReviewStore` (processo do motor) só foram validados por compilação e pelo coordenador simulado; não há
  teste automatizado do `PythonRunner` com os subcomandos V5 (o motor embutido ainda não os tem).
- `ValidatorV5ResultsSheet` mostra a lista, mas não há marca por linha na coluna de alertas.
- Ainda valem os três bloqueadores da Fase 4 listados acima.
