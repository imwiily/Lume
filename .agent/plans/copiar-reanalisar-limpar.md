# Copiar contexto, copiar parágrafo marcado, reanalisar e limpar resíduos

Origem: `sugestoes-de-melhorias.md` (pedido do autor, 06/10/2026). Mudança só de interface
(Swift); o motor e os contratos JSON não mudam.

## Objetivo e escopo

1. **Copiar contexto** — na mesa de leitura, copia todo o trecho mostrado na página: título do
   capítulo e os parágrafos (o do alerta e os vizinhos de `context`), na ordem da página.
2. **Copiar parágrafo com o destaque** — copia o parágrafo do alerta com o trecho destacado entre
   asteriscos (`antes *trecho* depois`) e, abaixo, a seção “Por que acendemos esta luz”.
3. **Reanalisar a obra** — na barra da mesa, roda de novo a análise do mesmo manuscrito com as
   mesmas opções e mantém as decisões já marcadas: pelo ID (mesmo trecho no mesmo parágrafo; o ID
   do FONTE inclui número, texto e posição) e, para os demais, pelo conteúdo (`BookMemory`, a
   mesma herança exata já usada entre análises). Nada por aproximação. A confirmação de envio à
   API continua valendo quando Coerência/Auditoria com IA estão ligadas.
4. **Limpar resíduos** — em Motor, apaga dados antigos em `~/Library/Application Support/FONTE`
   que contêm texto de leituras passadas, depois de mostrar o espaço liberado e pedir confirmação:
   relatórios antigos (mantém o aberto e o mais recente de cada livro; preserva
   `falsos-positivos.json`), registros (menos o atual), cópias de configuração por análise e
   temporários `lume-edicao-*`. Mantém decisões, livros, histórico de edições, cópias de
   segurança do manuscrito, projetos de Coerência/Auditoria (cache pago da API) e motores.

Fora do escopo: mudar o motor, apagar motores instalados, apagar cópias de segurança.

## Arquivos

- `app/Lume/Models.swift`: `Finding.pageParagraphs`, `contextText`, `markedParagraphText`;
  `CarriedDecisions`; `StorageCleanup` (plano e execução, testáveis fora do app).
- `app/Lume/ReviewStore.swift`: cópias, `reanalyze()`, aplicação das decisões levadas em
  `loadReport`, `cleanStorage()`.
- `app/Lume/ManuscriptView.swift`: botões de cópia; página usa `pageParagraphs`.
- `app/Lume/ContentView.swift`: botão Reanalisar na barra da mesa.
- `app/Lume/EngineView.swift`: painel Armazenamento.
- `tests/DeskToolsCheck.swift`: verificação Swift das funções puras.

## Testes

- `swiftc app/Lume/Models.swift tests/DeskToolsCheck.swift -o build/mesa-swift && build/mesa-swift`
- Checks existentes: `BookMemoryCheck`, `ContractCheck`, `EditCheck`, `FalsePositiveCheck`.
- `xcodebuild` do projeto (Debug) e inspeção nativa das telas.

## Progresso

- [x] Plano.
- [x] Implementação.
- [x] Verificações (06/10/2026): `DeskToolsCheck`, `BookMemoryCheck`, `EditCheck`,
  `FalsePositiveCheck` e `ContractCheck` (com `examples/Mestre/relatorio.json`) passam;
  `xcodebuild` Debug compila; capturas `LUME_SNAPSHOT` da mesa e de Motor inspecionadas (claro
  e escuro).
- [ ] Pendente: teste manual no app montado de Reanalisar (análise real) e da limpeza na pasta
  real, com confirmação.
- [x] 07/10: simulação do plano de limpeza na pasta real, sem apagar nada: 48 relatórios, 466
  registros e 99 configurações (108 MB); fica o mais recente de cada livro (13 pastas); nenhum item
  fora de Relatorios, Registros, Configuracoes ou temporários do Lume.
