# Lume

Ferramentas de revisão editorial para manuscritos em português. O manuscrito é sempre
somente lido; sugestões e decisões ficam em relatórios.

| Pasta | O que é |
| --- | --- |
| [`LumeMac/`](LumeMac/README.md) | App macOS (SwiftUI) e motor **FONTE** (Python): ortografia, gramática com LanguageTool embutido, tempo verbal e regras editoriais, tudo local; contradições narrativas pela Coerência com IA, opcional. |
| [`LumeCoerencia/`](LumeCoerencia/README.md) | Motor experimental **Coerencia**, só no terminal: contradições narrativas com a API do Claude, com leitura incremental por capítulo para economizar tokens. |
| [`docs/`](docs/) | Produto e critérios de aceitação da v0.11 (`product/`, `testing/`) e diagnósticos (`analises/`). |
| `.agent/` | Regras de ExecPlan (`PLANS.md`) e planos de cada tarefa (`plans/`). |
| [`AGENTS.md`](AGENTS.md) | Instruções para agentes de código que trabalham no repositório. |

Saídas de montagem e testes ficam em `LumeMac/Saida/` e `LumeCoerencia/Saida/`, fora do Git.

## Começar

- App e motor FONTE: veja [LumeMac/README.md](LumeMac/README.md) (`bash LumeMac/Montar-Lume.command`).
- Coerencia: veja [LumeCoerencia/README.md](LumeCoerencia/README.md) (chave da API nas Chaves do macOS,
  serviço `coerencia-anthropic`).
