# ExecPlan — Interface do Lume a partir da referência do Stitch

Iniciado em 05/10/2026. Plano vivo.

## Objetivo e escopo

Refazer a camada visual em SwiftUI usando como referência as telas finais do Stitch em
`~/stitch_lume_macos_editorial_workspace/`, que é só leitura. As telas são:

- `lume_in_cio`;
- `lume_prepara_o_do_manuscrito`;
- `lume_an_lise_em_andamento`;
- `lume_mesa_de_leitura`;
- `lume_motor_fonte_2`;
- `cone_lume_chama_e_livro`;
- `nocturne_candlelight_2/DESIGN.md`.

Identidade: “O manuscrito é papel. O Lume é instrumento. A atenção é luz.” e “Lume encontra.
Lume explica. O editor decide.”

Fora do escopo: motores Python, detecção, Coerencia, Auditoria, schemas JSON,
`SearchSettings`, `ReviewDecision`, `ManuscriptEditor` (backup, hash, AppleScript, conferência,
rollback), versão e distribuição. Nenhuma chamada à API.

### Divergências deliberadas do Stitch

O código real vence o mockup. Ficam de fora:

- **Coluna fixa de capítulos e estrutura com contagem de palavras.** Os capítulos ficam num
  menu da barra de ferramentas, que leva ao primeiro alerta do capítulo. A preparação não
  tem esses dados antes da análise.
- **Dados fictícios:** “VOLP”, “Léxico pt-BR”, “381.000 vocábulos”, “Divergências 14 notas”,
  avatar, conta, “Sessão de prova”, “Recomendado”, “Relatório holístico”, “Integridade binária
  verificada”, “100% no Mac”, “Processamento”, tempo restante e trecho processado ao vivo.
- **Interruptor da Coerência dentro da tela de progresso.** No lugar dele aparece o estado
  real da etapa.
- **Página com o capítulo inteiro.** O relatório só traz o parágrafo do alerta e o contexto
  próximo (`context`), então a página mostra esses parágrafos.
- **“Registro” como aba:** vira uma tela que mostra o arquivo de registro da última operação
  (`store.logURL`), que já existe. As ações atuais continuam: abrir no editor e mostrar no
  Finder.

## Estado atual observado

- Revisão `ede2a80` (Lume 1.5). A árvore está limpa, exceto `sugestoes-de-melhorias.md`, que
  fica fora do Git.
- `ContentView.swift`, com 1.393 linhas, concentra:
  - `NavigationSplitView` com `NightRail`;
  - `EngineControls` em popover;
  - `HomeView` (início e preparação juntos), `AuditSheet`, `ReadingDesk` e `ReadingInProgress`;
  - `FindingsColumn`, `TenseNotice` e `FindingCard`;
  - `ReadingPage` (página, nota, correção e decisões);
  - `StatusLine`, `CoverageSheet`, `KeySheet` e `SearchSettingsView`.
- `LumeTheme.swift` tem tokens, `LumeFont` (SF Rounded), a marca (`LumeMark`, `OpenBook` em
  traço, `Flame`), `LumeButtonStyle` em cápsula, `Sheet` e `Kicker`.
- `SobreView.swift` tem a janela Sobre e as licenças.
- O projeto Xcode lista cada arquivo explicitamente (`project.pbxproj` escrito à mão); arquivo
  novo precisa entrar no grupo e na fase de fontes. O alvo mínimo é macOS 13.
- O modo de captura (`LUME_SNAPSHOT`, só Debug, em `LumeApp.swift`) desenha telas em PNG.
- O estado vem do `ReviewStore`: `screen`, `isAnalyzing`, `analysisFailed`, `analysisStages`,
  filtros, decisões, Pages, IA e motor. A interface nova não cria outro store. O único estado
  local novo é a seção visível (Motor ou Registro) e a visibilidade do inspetor.

## Arquivos

| Arquivo | Conteúdo |
| --- | --- |
| `LumeTheme.swift` | Tokens claro/escuro, `LumeFont` (SF Pro e New York), raios, marca nova, botões, painel, rótulos, etiqueta de severidade |
| `ContentView.swift` | Janela: barra com marca e navegação (Início, Leitura, Registro, Motor), roteamento, folhas e alertas |
| `HomeView.swift` | Início vazio e preparação do manuscrito (modos, língua, história, auditoria, ação) |
| `ReadingProgressView.swift` | “Lendo com atenção…” com `store.analysisStages` |
| `ReadingDeskView.swift` | Mesa: três painéis com `HSplitView`, menu de capítulos, recuperação e linha de estado |
| `FindingsColumn.swift` | Pontos de atenção, busca, filtros, aviso de tempo contradito e cartões |
| `ManuscriptView.swift` | Página de papel: contexto, parágrafo iluminado, tamanho do texto, copiar |
| `FindingInspector.swift` | Inspetor: classificação, explicação, sugestão, evidências, Pages, decisões, detalhes |
| `SearchSettingsView.swift` | “Ajustar o que procurar”, com a mesma lógica |
| `EngineView.swift` | Motor, Registro e folhas (chave, etapas e alcance) |
| `SobreView.swift` | Mesma função, identidade nova |
| `LumeApp.swift` | Capturas novas no modo Debug |
| `Assets.xcassets/AppIcon.appiconset` | Ícone regerado a partir da marca nova |

## Etapas

1. Tokens, tipografia, marca e componentes compartilhados (`LumeTheme`).
2. Janela e navegação (`ContentView`), com as views antigas ainda funcionando.
3. Início.
4. Preparação.
5. Análise em andamento.
6. Mesa: lista, manuscrito e inspetor; aviso de tempo; falsos positivos; capítulos.
7. Inspetor e decisões: Pages separado da decisão; DOCX somente leitura.
8. Motor, Registro, Sobre, folhas e “Ajustar o que procurar”.
9. Claro e escuro.
10. Remoção das views antigas.
11. Capturas, contrato Swift, verificações e revisão do diff.

Cada etapa termina com `xcodebuild` Debug sem erros.

## Validação

- `xcodebuild` Debug e Release (pela montagem, se for feita).
- Verificações Swift: `ContractCheck`, `EditCheck`, `FalsePositiveCheck` e `BookMemoryCheck`.
- Capturas nos modos claro e escuro:
  - início vazio;
  - preparação;
  - análise com auditoria;
  - mesa com e sem seleção;
  - achado da Auditoria;
  - aviso de tempo contradito;
  - Pages editável;
  - DOCX somente leitura;
  - “Ajustar o que procurar”;
  - Motor;
  - Registro;
  - Sobre.
- Relatórios das capturas: exemplos sintéticos do repositório e relatórios gerados localmente
  com o modelo simulado. Nada dos manuscritos reais e nenhuma chamada à API.

## Progresso

- [x] 1–11, em 05/10/2026.

### Descobertas

- `ContentView` antigo usava `NavigationSplitView`, que dava tamanho à janela. Sem ele, o modo
  de captura precisava de tamanho mínimo na raiz, como a cena real (`minWidth: 1040`).
- **Animação da chama:** `withAnimation(.repeatForever)` no `onAppear` da tela de progresso
  animava também o layout inicial. A tela oscilava de tamanho e o modo de captura chegou a
  abortar num ciclo de restrições. A animação agora vale só para a escala do círculo.
- **Preferências nas capturas:** ligar a Coerência e a Auditoria grava em `UserDefaults`. O
  modo de captura restaura os valores ao terminar, e o script de captura também os restaura
  por fora. Numa execução que abortou, `auditAI` ficou gravado e foi restaurado à mão.
- **Configuração de busca:** a captura de “Ajustar o que procurar” gravou a configuração de um
  documento do scratchpad. A entrada foi removida.
- **Atalho recusado:** ⌘↩ para “Confirmar” foi retirado, porque estava na lista de sugestões que
  o autor recusou.

## Validação

- `xcodebuild` Debug e Release sem erros nem avisos nos arquivos do app.
- Verificações Swift aprovadas: `ContractCheck` (relatório antigo de exemplo e relatório com
  auditoria), `EditCheck`, `FalsePositiveCheck` e `BookMemoryCheck`.
- Sem mudanças em Python; nenhuma chamada à API.
- Capturas inspecionadas nos modos claro e escuro: início vazio, preparação, análise com
  auditoria, mesa (com seleção, sem seleção, estreita), achado da auditoria, aviso de tempo
  contradito (com DOCX somente leitura), Pages editável, “Ajustar o que procurar”, Motor,
  Registro e Sobre.
- Relatórios das capturas: texto sintético novo (sem sequências de 5 palavras em comum com A e
  B), o `.pages` sintético do repositório e o relatório com a auditoria simulada.
- **Não inspecionado:** o alerta do sistema “Enviar à Anthropic?”, que não é desenhado pelo
  modo de captura; o texto dele não mudou.
