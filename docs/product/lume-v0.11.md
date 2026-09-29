# Lume v0.11 — memória narrativa confiável

> **Documento histórico.** A memória narrativa heurística descrita aqui foi removida em 29/09/2026 por não produzir alertas úteis; contradições narrativas passaram à Coerência com IA (`LumeCoerencia/`). Os gates de preservação do manuscrito, contratos e comandos de teste continuam válidos.

## Finalidade e estado observado

Lume é um aplicativo editorial macOS com interface SwiftUI e motor Python FONTE.
A última etapa da v0.11 deve decidir que informações merecem ser lembradas, por
quanto tempo permanecem válidas e como alimentam comparações globais.

Inspeção documental e de código em 29/09/2026: o README identifica Lume 0.11.4 e
FONTE 0.9.5. Já existem papéis semânticos, promoção de eventos, persistência seletiva,
histórico e cadeia de confiança. Isso não significa cobertura integral. A
[validação histórica](../../LumeMac/Documentacao/VALIDACAO.md) registra cobertura
parcial e métricas ainda não avaliadas. Este documento define requisitos, não uma
declaração de release aprovada nem uma auditoria exaustiva da implementação.

## Arquitetura preservada

| Caminho real, relativo à raiz Git | Responsabilidade |
| --- | --- |
| `LumeMac/Analisador/fonte/` | Leitura, contratos, pipeline, análise e memória |
| `LumeMac/Analisador/fonte/semantic_roles.py` | Papéis semânticos |
| `LumeMac/Analisador/fonte/semantic.py` | Estruturas semânticas e fact bank |
| `LumeMac/Analisador/fonte/narrative*.py` | Cenas, identidades, falas, referências e memória |
| `LumeMac/Analisador/fonte/generic_facts.py` | Extração e comparação de fatos genéricos |
| `LumeMac/Lume/` | Interface, decisões, relatórios, progresso e motores |
| `LumeMac/Engine/` | Entrada portátil e gerenciamento de pacotes |
| `LumeMac/Analisador/tests/`, `LumeMac/Tests/` | Regressões semânticas e integração |

O pipeline existente é Linguístico → Morfossintático → Editorial → Coerência
Global; memória narrativa e semântica são responsabilidades internas dessas
etapas. Não acrescentar uma etapa pública ou renomear módulos só para refletir
a cadeia conceitual abaixo. Auditor Final permanece `not_implemented`.

Consulte a [arquitetura existente](../../LumeMac/Documentacao/ARQUITETURA.md) para
contratos, offsets Unicode e compatibilidade. Relatório/API/decisões usam schema 1;
memória narrativa usa schema 2 no estado inspecionado. Evoluções exigem análise de
compatibilidade, sem renumeração automática motivada por esta especificação.

## Cadeia alvo

```text
Texto → Entidades → Correferência → Papéis semânticos → SEMANTIC_EVENT
→ FACT_CANDIDATE → RELEVANCE_FILTER → PERSISTENCE_FILTER
→ LOCAL_FACT / PERSISTENT_FACT → FACT_BANK → Coerência Global
```

Os nomes em maiúsculas são conceitos de produto, não exigência de renomear chaves
JSON ou classes. Hoje `persistence: local|persistent` representa parte dessa
distinção. Antes de implementar candidatos, mapear a promoção existente e registrar
lacunas; não presumir que já existe uma camada explícita `FACT_CANDIDATE`.

## Eventos, candidatos e fatos

Um candidato precisa guardar `event_id`, sujeito, relação, valor, tipo, confiança,
relevância, persistência proposta, nível de inferência, evidência e motivo. A
promoção/descarte deve ser rastreável. A decisão depende da consequência narrativa,
não de uma lista de verbos isolada.

Sorrir, olhar, respirar ou virar a cabeça normalmente não justificam memória
persistente. Ferimento, transferência, deslocamento relevante, conhecimento,
alteração de objeto ou relação podem justificá-la. O contexto determina exceções.

Tipos prioritários: `ATTRIBUTE_FACT`, `STATE_FACT`, `POSSESSION_FACT`,
`LOCATION_FACT`, `RELATION_FACT`, `KNOWLEDGE_FACT` e `TIME_FACT`. Transferência deve
preservar AGENT, OBJECT e RECIPIENT e produzir os efeitos de posse associados ao
mesmo evento; `TRANSFER_FACT` é uma categoria conceitual, sem obrigar novo schema.

Todo fato precisa preservar trecho original, capítulo, parágrafo, cena, entidade,
`event_id`/`source_event_ids`, confiança, nível de inferência, escopo, polaridade,
`valid_from` e `valid_until`, com equivalentes documentados no contrato. Tempo
desconhecido permanece desconhecido; ordem textual não prova cronologia absoluta.

## Identidade, papéis e confiança

- Distinguir `canonical_character`, `local_participant`, `unresolved_participant`;
  para objetos, `persistent_object`, `local_object`, `unresolved_object`, usando
  representações compatíveis com o schema existente.
- Um substantivo humano genérico ou uma presença isolada não cria personagem
  canônico. Um objeto genérico não é automaticamente o mesmo em cenas distintas.
- Usar nome, qualificador, posse, localização, manuseio, cena e histórico como
  evidências de identidade; não consolidar um objeto não resolvido por conveniência.
- Reutilizar AGENT, PATIENT, OBJECT, RECIPIENT, LOCATION, SOURCE, DESTINATION,
  INSTRUMENT e HOLDER. Sujeito gramatical não equivale sempre a agente, sobretudo
  na voz passiva; paciente humano não deve virar objeto físico.
- Propagar `entity_confidence`, `reference_confidence`, `event_confidence`,
  confiança dos papéis e `inference_level` para `fact_confidence`. Dependências
  incertas limitam a força do resultado; não elevar confiança sem nova evidência.
- Sujeito não resolvido ou falante incerto não pode sustentar fato persistente
  forte. Declaração, hipótese, desejo e negação preservam seus escopos e polaridade;
  uma fala não atesta automaticamente o mundo narrado.

## Persistência e transições

`LOCAL_FACT` é restrito à cena/intervalo pertinente. `PERSISTENT_FACT` atravessa
cenas enquanto relevante e válido. Mudança de cena não apaga um ferimento nem
transporta automaticamente presença, emoções transitórias ou referentes locais.

Manter histórico de estados mutáveis; transição reconhecida encerra o estado
anterior e inicia o sucessor. `current_state` deriva desse histórico, sem manter
uma segunda verdade desconectada. Posse anterior deve cessar em uma transferência;
saída encerra localização anterior quando aplicável; cura reconhecida encerra a
restrição física pertinente. Destruição não apaga a evidência histórica do objeto.

Conhecimento mantém assunto e polaridade: “não sabia” difere de “descobriu”. Não
inventar desconhecimento anterior a uma descoberta. Relações simétricas podem
ter vínculo bilateral; não aplicar simetria a relações direcionais como pai/filho.

## Instrumentação e fechamento

Requisitos de instrumentação: `fact_candidate_count`, `promoted_fact_count`,
`discarded_fact_candidate_count`, `persistent_fact_count`, `local_fact_count`,
`fact_persistence_rate`, motivos de descarte e pares globais elegíveis/comparados.
Documentar unidades e denominadores: um evento/candidato pode originar vários
efeitos, portanto contagem de fatos não equivale à de eventos promovidos.

`global_comparison_rate = global_compared_fact_pairs / global_eligible_fact_pairs`;
sem pares elegíveis, usar ausência de medida conforme contrato, sem inventar 100%.
No estado inspecionado, `global_comparison_rate` é `null`/não instrumentada.
Precisão e taxa de falsos fatos exigem anotação; volume e preenchimento não as
substituem. Não redefinir denominadores para fabricar melhora antes/depois.

Fechar a v0.11 exige os [gates de aceitação](../testing/acceptance-v0.11.md), incluindo
casos simples, negativos, ambiguidades, regressões reais e compatibilidade. Aumento
de fatos úteis precisa vir acompanhado de controle de falsos fatos. Regras devem
funcionar com nomes e contextos diferentes de Echoes/Hikari.

Manter apenas os comparadores previstos: atributo, estado, posse, localização,
relação, conhecimento, presença e cronologia. Não incluir Auditor Final, sistemas
mágicos específicos, interpretação literária, causalidade complexa, inferência
psicológica ou reescrita automática nesta etapa.
