# Estrutura do repositório no padrão do GitHub

## Objetivo

Reorganizar as pastas com nomes convencionais do GitHub, sem mudar comportamento: o app,
os motores, os contratos JSON, os nomes de pacotes Python (`fonte`, `coerencia`) e a pasta de
dados do usuário (`~/Library/Application Support/FONTE`) continuam iguais.

## Mapa

| Antes | Depois |
| --- | --- |
| `LumeMac/Lume/`, `LumeMac/Lume.xcodeproj/` | `app/Lume/`, `app/Lume.xcodeproj/` |
| `LumeMac/Analisador/` | `fonte/` |
| `LumeCoerencia/` | `coerencia/` |
| `LumeMac/Engine/` | `packaging/` |
| `LumeMac/Scripts/`, `LumeMac/Montar-Lume.command` | `scripts/`, `scripts/montar-lume.command` |
| `LumeMac/Tests/` | `tests/` |
| `LumeMac/Exemplo/` | `examples/` |
| `LumeMac/Identidade/` (`GUIA.md`) | `docs/identidade/` (`README.md`) |
| `LumeMac/Documentacao/*.md` | `docs/arquitetura.md`, `docs/validacao.md`, `docs/visao.md`, `CHANGELOG.md` |
| `LumeMac/README.md` | `README.md` (raiz) |
| `LumeMac/Saida/`, `LumeCoerencia/Saida/` | `build/`, `build/coerencia/` |

## Decisões

- Pastas movidas com `mv` (não `git mv`) para levar junto o que está fora do Git:
  `fonte/.venv`, `fonte/.languagetool`, saídas e `coerencia/Projetos`.
- Scripts passam a rodar da raiz; `montar-lume.command` faz `cd` para a raiz.
- Registros históricos (`docs/validacao.md`, seções antigas do `CHANGELOG.md`, planos em
  `.agent/plans/`) mantêm os caminhos antigos, com nota de correspondência.

## Validação

`bash scripts/montar-lume.command` completo (suítes do FONTE e dos pacotes, contratos
Python/Swift, motor congelado, app empacotado), suíte do Coerencia, links Markdown e build
Debug do Xcode.
