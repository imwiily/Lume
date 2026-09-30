# Documentos do Pages e edição do texto no app

## Objetivo e escopo

1. **Leitura de `.pages`** (concluída nos fontes): escolher ou arrastar um documento do Pages
   e analisá-lo como um DOCX, sem exportar e sem abrir o Pages.
2. **Edição do texto no app** (não iniciada; depende de decisões do autor, abaixo).

Fora do escopo: reescrita automática, tabelas e caixas de texto do Pages, Pages ’09.

## Estado observado (30/09/2026, branch `organizacao-e-deteccao`, base `addc886`)

- O motor só lia DOCX (`reader.read_docx`); app e CLI recusavam `.pages`.
- `.pages` atual é um ZIP com `Index/*.iwa` (Snappy + protobuf). A raiz (objeto 1, tipo
  10000) aponta o corpo no campo 4; o corpo (tipo 2001) traz o texto no campo 3 e tabelas
  de atributos por posição UTF-16: estilo de parágrafo (5) e de caractere (8). Estilos
  (2022/2021) têm nome e origem no campo 1 e itálico no campo 11.2.
- O Pages 15.3 instalado aceita AppleScript: trocar uma palavra por
  `set word N of paragraph M of body text` preservou o itálico de outro trecho e gravou o
  arquivo. É o caminho viável para gravar edições num `.pages`; escrever IWA diretamente
  não é seguro.

## Arquivos

| Arquivo | Mudança |
| --- | --- |
| `fonte/fonte/pages.py` | Novo: Snappy, protobuf e parágrafos do corpo (só biblioteca padrão) |
| `fonte/fonte/reader.py` | `_blocks`/`_finish` comuns, `read_pages`, `read_manuscript` |
| `fonte/fonte/cli.py` | Usa `read_manuscript`; mensagem para `.pages` em pacote |
| `app/Lume/ReviewStore.swift`, `ContentView.swift` | Aceitam `.docx` e `.pages` |
| `fonte/tests/test_pages.py`, `fonte/tests/corpus/pages/` | Testes e documento sintético |

Manuscrito, pipeline, contratos JSON e offsets não mudam: o leitor entrega os mesmos
`Block` e o hash registrado é o do arquivo `.pages`.

## Validação da leitura

Ver `docs/validacao.md`, “Leitura de Pages”. Pendências: remontar motor e app
(`bash scripts/montar-lume.command`), contrato Swift, inspeção nativa da tela inicial e
teste com um `.pages` escrito diretamente no Pages pelo autor.

## Edição: decisão de 30/09/2026

O autor escolheu gravar no próprio `.pages`. Implementado: correção por alerta, só `.pages`,
com cópia, conferência pelo motor, restauração e herança de decisões por ID idêntico
(`app/Lume/ManuscriptEditor.swift`, `ReviewStore.applyCorrection`, `conferir-edicao` na CLI,
`tests/EditCheck.swift`). Invariante 1 do `AGENTS.md` reescrito. Pendente: exercitar o
fluxo no app, remontar motor e app, reanálise incremental (só o que mudou), DOCX e editor
livre. O texto abaixo registra as opções consideradas.

## Edição: opções consideradas

A edição contraria o invariante 1 do `AGENTS.md` (“o manuscrito é imutável”) e o item
“Nunca modificar manuscrito” de `app/Lume/AGENTS.md`. Antes de implementar, o autor decide:

- **Onde gravar:** numa cópia nova (o original continua intocado e o invariante vale para
  ele) ou no próprio arquivo (exige mudar o invariante e criar cópia de segurança).
- **Alcance:** corrigir o trecho de cada alerta (aceitar a sugestão ou digitar a correção)
  ou um editor livre do texto inteiro.
- **Formatos:** `.pages` exige o Pages instalado e a permissão de Automação do macOS;
  `.docx` pode ser gravado pelo motor (python-docx), preservando a formatação do trecho.

Riscos a cobrir: offsets depois de uma edição (alertas do mesmo parágrafo ficam
desatualizados até nova análise), decisões ligadas ao SHA-256 antigo, correspondência entre
o parágrafo do relatório e o do Pages, e falha no meio da gravação.
