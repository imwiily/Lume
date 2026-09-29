# ExecPlan — Coerência com IA dentro do Lume.app

Iniciado em 29/09/2026. Plano vivo.

## Objetivo e escopo

Levar o Coerencia (contradições narrativas com a API do Claude, modo projeto
incremental) para dentro do Lume.app, como opção da etapa Coerência global.

Decisões do usuário (29/09): com a IA ligada, a memória narrativa heurística do
FONTE não roda naquela análise (substituição); teto padrão US$ 1,00 por análise;
modelo padrão `claude-sonnet-5-5`. A IA vem desligada por padrão e nada é enviado
sem confirmação com custo estimado.

Fora do escopo: remover o código da memória narrativa antiga; mudar o número de
versão do app ou do motor; notarização.

## Arquitetura

- Fonte única do Coerencia em `LumeCoerencia/` (pacote `coerencia`), instalado no
  ambiente do Analisador e embutido no motor congelado.
- `fonte/coerencia_ia.py`: converte blocos do FONTE em parágrafos do Coerencia
  (mesma numeração), roda o projeto incremental e devolve pendências abertas como
  ocorrências v1 (`rule=coerencia_ia`, módulo `global_coherence`, severidade
  `possible_inconsistency`, trecho posterior como ocorrência e o anterior em
  `related`). IDs estáveis enquanto o texto não muda.
- CLI: `revisar … --coerencia-ia --coerencia-projeto P [--coerencia-modelo M]
  [--coerencia-teto T]` e `coerencia-estimar ARQUIVO --coerencia-projeto P`
  (JSON: capítulos a enviar, caracteres, custo estimado; não chama a API).
- Teto: capítulos concluídos ficam salvos; os restantes seguem na próxima rodada.
  Pares ainda não julgados são retomados (fatos marcados para reavaliação).
- Chave: app guarda nas Chaves do macOS (serviço `coerencia-anthropic`) e passa ao
  motor por variável de ambiente; o motor também lê o Keychain no terminal.
- App: seção “Coerência com IA (Claude)”, chave, modelo, teto; confirmação com
  estimativa antes de enviar.

## Etapas

- [x] Empacotar `coerencia` (pyproject) e instalar no ambiente do Analisador.
- [x] Teto que preserva progresso e retoma julgamentos.
- [x] Adaptador, pipeline e CLI no FONTE, com testes (modelo simulado).
- [x] App: chave, opções, estimativa e confirmação; build e contrato Swift.
- [x] Montagem do motor e do app com o Coerencia embutido.
- [x] Teste de ponta a ponta com a API em texto curto (centavos, com autorização).

## Resultado

Concluído em 29/09; evidências e pendências em `LumeMac/Documentacao/VALIDACAO.md` (seção “Coerência com IA no app”).
