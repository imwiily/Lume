# Decisões por livro, pelo nome do arquivo

## Objetivo e escopo

Hoje as decisões do autor ficam em `Decisoes/<SHA-256 do arquivo>.json`. Qualquer
gravação do manuscrito fora do Lume (editar no Pages, ou só abrir e salvar) muda o
SHA-256 e a nova análise começa com todos os alertas pendentes. A ponte existente só
cobre correções feitas pelo próprio Lume (`Edicoes/<origem>.json`).

Comportamento esperado: ao abrir uma análise nova de um manuscrito com o mesmo nome
(sem extensão, sem diferenciar maiúsculas), cada alerta idêntico ao de antes recupera
a decisão. Idêntico = mesma categoria, regra, origem, texto do parágrafo, trecho e
evidências relacionadas; o número do parágrafo e o capítulo não entram, para que
inserir ou apagar parágrafos não zere o resto do livro.

Exemplo: análise de “Livro.pages” com 50 decisões; o autor edita 3 parágrafos no
Pages e analisa de novo. Antes: 0 decisões mantidas. Depois: as decisões dos alertas
cujos parágrafos não mudaram voltam; os alertas dos parágrafos editados ficam pendentes.

Fora do escopo: assinatura gravada no manuscrito (fere o invariante 1), seguir
arquivos renomeados, importar `lume-decisoes.json` de outra versão, permitir correção
no Pages sem nova análise depois de uma edição externa (continua exigindo análise).

## Estado atual observado (revisão `b77a6ca`)

- `app/Lume/ReviewStore.swift`: `decisionURL` (SHA do arquivo), `loadReport`,
  `inheritedDecisions` (só via `EditLog`), `autosave`, `payload`.
- `app/Lume/Models.swift`: `Finding`, `DecisionFile` (schema 1, por SHA).
- ID do alerta (`fonte/fonte/analysis.py:finding`) inclui o número do parágrafo.
- Dados reais (só contagens): cadeia de 6 análises do manuscrito A em `.pages`. Na
  última transição, feita após edição no Pages, 50 decisões → 0 herdadas. Simulação do
  critério de conteúdo: 30 herdadas; nas transições com ponte do Lume, o critério de
  conteúdo herda exatamente o mesmo número que o atual (7, 10, 33, 33).

## Arquivos afetados

- `app/Lume/Models.swift`: `Finding.contentKey`, `BookMemory` (arquivo do livro,
  herança por conteúdo, nome do livro). Lógica pura, testável sem AppKit.
- `app/Lume/ReviewStore.swift`: grava `Livros/<nome>.json` a cada salvamento de
  decisões; ao abrir relatório sem decisões próprias, herda do livro (depois da ponte
  do Lume); migração única a partir do relatório mais recente com o mesmo nome em
  `Relatorios/` que tenha decisões.
- `tests/BookMemoryCheck.swift` e `scripts/montar-lume.command`: teste novo.
- `CHANGELOG.md`, `docs/validacao.md`.

Preservação: o manuscrito não é lido nem alterado por esta mudança; `Decisoes/<sha>.json`
continua sendo gravado e tem prioridade; exportar/importar decisões não muda; o motor
não muda.

## Regras de herança

1. Decisões do próprio relatório (`Decisoes/<sha>.json`) têm prioridade.
2. Sem elas: ponte de correções do Lume (atual) e, para o resto, o livro.
3. Só decisões diferentes de “Pendente”.
4. Chave repetida (parágrafos idênticos com o mesmo alerta): herda na ordem do
   relatório só se a quantidade for a mesma antes e depois; senão, nenhuma.
5. Limitação aceita: o livro reflete o último relatório salvo com aquele nome; abrir um
   relatório antigo e decidir algo nele substitui o arquivo do livro.

## Etapas

1. [x] Reproduzir com dados reais (contagens acima).
2. [x] `BookMemory` + `BookMemoryCheck.swift`: mesmo texto com outro SHA; parágrafo
   editado; parágrafo inserido; chaves repetidas iguais e diferentes; pendentes; nome
   `.docx`/`.pages` e maiúsculas; schema.
3. [x] Integração no `ReviewStore` e migração.
4. [ ] Montagem completa; conferência com os dados reais (contagens); documentação.

## Comandos

```sh
swiftc app/Lume/Models.swift tests/BookMemoryCheck.swift -o build/livro-swift && build/livro-swift
bash scripts/montar-lume.command
```

## Progresso e decisões

- 03/10/2026: o autor escolheu o nome do arquivo como identidade do livro (em vez de
  assinatura no texto). Extensão ignorada para que `.docx` → `.pages` mantenha decisões.
- 03/10/2026: `BookMemoryCheck` falhou antes da implementação (tipo inexistente) e passou
  depois. Com os relatórios reais, a herança em Swift deu 7, 10, 33, 32 e 30; o 32 (Python: 33)
  vem de dois relatórios com o mesmo SHA-256 e 168/166 alertas (regras mudaram entre eles), não
  da lógica.
