# Histórico do Lume e FONTE

As seções antigas descrevem a cobertura e os resultados de cada entrega, não o estado atual. Nas seções anteriores à 1.0, caminhos citados são da antiga pasta `LumeMac/`; a correspondência com a estrutura atual está em [README.md](README.md#estrutura).

## Lume 1.3 / FONTE 1.2.0 · Coerencia 1.1.0 — 01/10/2026

Só a interface mudou; o motor é o mesmo da 1.2 e os alertas não mudam.

- Extrair falsos positivos: campos ausentes (relatórios antigos, alerta sem sugestão) passam a
  ser gravados como `null`, para todas as entradas terem as mesmas chaves. Novo teste
  `tests/FalsePositiveCheck.swift`, executado na montagem.
- Página do alerta mais compacta: cabeçalho em duas linhas curtas, avaliações em botões
  numa linha (três por linha em janelas estreitas) e correção, avaliação e **Confirmar**
  logo abaixo da explicação do alerta. Relacionados, contexto e avisos vêm depois; a força
  do indício foi para “Detalhes da análise”. “Copiar parágrafo” virou ícone, que mostra
  “Copiado” ao clicar. A lista de alertas não mostra mais o anel azul de foco.
- **Editar parágrafo**: opção, ao lado de Corrigir, para reescrever o parágrafo inteiro do
  alerta. O Lume reduz a edição à menor troca contínua (o resto do parágrafo e a
  formatação não são tocados), recusa trocas sobre correções já gravadas e usa a mesma
  cópia de segurança e conferência pelo motor. Testes em `tests/EditCheck.swift`.

## Lume 1.2 / FONTE 1.2.0 · Coerencia 1.1.0 — 01/10/2026

- Página do alerta reorganizada: texto, “Copiar parágrafo” e **Confirmar** (habilitado
  quando a avaliação não é “Pendente”; passa ao próximo alerta da lista), as seis
  avaliações numa linha e em cartões do mesmo tamanho, “Por que acendemos esta luz” e, por
  último, “Corrigir no manuscrito”. A explicação de cada avaliação fica na dica do cartão.
- **Extrair falsos positivos**, na linha de estado: grava em JSON os alertas marcados como
  falso positivo (regra, módulo, trecho, parágrafo e motivo) para estudar as regras. O
  arquivo contém trechos do manuscrito e não deve ir para o repositório.
- Relatório HTML removido. O FONTE grava só `relatorio.json` (lido pelo app), sem a opção
  `--abrir`; o Coerencia avulso deixa de gerar `relatorio.html` e mostra as pendências no
  terminal (`contradicoes.json` continua na pasta de saída). Saem também o menu “Abrir
  relatório HTML”, os testes DOM em Node/jsdom, os `.html` dos exemplos e os exemplos da
  memória narrativa removida (`Generico`, `Memoria`, `Memoria111`, `Qualidade113`).

## Lume 1.1 / FONTE 1.1.0 — 30/09/2026

Documentos do Pages: leitura direta e correção no próprio arquivo. O Coerencia continua na 1.0.0.

- Leitura direta de documentos do Pages (`.pages`), sem exportar para Word e sem abrir o
  Pages: texto do corpo, capítulos (pelo nome do estilo ou pelo texto) e itálicos. O arquivo
  continua intocado e o relatório registra o SHA-256 do `.pages`. Tabelas e caixas de texto
  do Pages não são analisadas; documentos com senha ou salvos como pacote são recusados com
  orientação. A comparação com o original também aceita `.pages`.
- **Corrigir no manuscrito** (só `.pages`): em cada alerta, o autor pode gravar a sugestão ou
  um texto próprio no lugar do trecho destacado, no próprio arquivo. O Lume guarda uma cópia
  antes da primeira correção, usa o Pages para a troca (formatação preservada), confere pelo
  motor que só aquele parágrafo mudou e desfaz se não conferir. Ao analisar de novo, as
  decisões dos alertas que não mudaram são mantidas. O invariante do manuscrito imutável
  passa a valer para a análise; a correção é sempre um pedido explícito do autor.

## Lume 1.0.1 / FONTE 1.0.1 — 29/09/2026

Manutenção da 1.0: repositório reorganizado e aberto sob licença MIT, dados de manuscritos
reais removidos e uma correção de detecção. O Coerencia continua na 1.0.0.

- Trechos, nomes e adaptações próximas de manuscritos reais removidos de testes, exemplos,
  prévias e documentos (inclusive do histórico do Git); substituídos por textos sintéticos.
  Os relatórios de exemplo Mestre, Editorial e Temporal foram regenerados pelo FONTE 1.0.0
  com as mesmas contagens. Removido o diagnóstico da memória narrativa (módulo já retirado).
  Os títulos dos manuscritos reais de referência passam a ser citados como “manuscrito A” e
  “manuscrito B”.
- Adjetivo posposto (“a tarde inteira”) não é mais lido como verbo quando o modelo o liga a
  outro verbo sem conjunção nem pontuação.
- Licença MIT para o código do Lume (app, FONTE e Coerencia); componentes de terceiros
  mantêm as próprias licenças, listadas em **Sobre o Lume**.
- Repositório reorganizado no padrão do GitHub: `app/` (SwiftUI e Xcode), `fonte/` (motor
  FONTE), `coerencia/`, `packaging/`, `scripts/`, `tests/`, `examples/`, `docs/` e `build/`
  (saídas locais). `HISTORICO.md` virou este `CHANGELOG.md`; o guia do app virou o README da
  raiz. A montagem passou a ser `bash scripts/montar-lume.command`, executada da raiz.

## Lume 1.0 / FONTE 1.0.0 / Coerencia 1.0.0 — 29/09/2026

Primeira versão oficial. Detecção de erros para qualquer texto, Coerência com IA opcional e
nova identidade visual.

- Corretor gramatical LanguageTool embutido no motor, ligado por padrão, revisando também as falas.
- Regras de crase, homófonos, concordância, regência e vírgula entre sujeito e verbo.
- Avaliação cega da detecção (`scripts/avaliar_deteccao.py`, corpus `tests/corpus/deteccao/`).
- Coerência com IA (Claude) na etapa Coerência global, com leitura incremental por capítulo,
  estimativa e confirmação de custo, teto de gasto e chave nas Chaves do macOS.
- Progresso dentro da etapa (“420 de 1.274 parágrafos”).
- Tempo da narração informado (passado ou presente); detecção automática removida.
- O app usa o motor embutido, salvo se o motor instalado for de versão mais nova.
- **Removida a memória narrativa heurística** (cenas, identidades, eventos, banco de fatos e
  comparações). Relatórios e configurações antigos continuam legíveis.
- Segunda rodada de falsos positivos dos relatórios reais: nomes que só aparecem com
  maiúscula, maiúscula após dois-pontos, particípio após “todos”, verbo antes de gerúndio,
  “agora sim”, verbo de fala não visto pelo modelo (e “terminar” como elocução), vírgula
  após exclamação com verbo em 1.ª pessoa, “para” verbal, repetição paralela ou em eco e
  onomatopeia reduplicada. Manuscrito A 228 → 214 e manuscrito B 20 → 18 alertas, sem perder erros
  confirmados; corpus inalterado (53/55) e controle novo `dev-controle-arena`.
- **Nova identidade visual “Luz de leitura”** (`docs/identidade/README.md`): paleta noite, vela e
  linho, símbolo da chama sobre o livro, novo ícone e interface refeita (Início com arrastar e
  soltar, Mesa de leitura com página e nota de margem, atalhos ⌘1–⌘6 e ⌘[ / ⌘]).
- Topo no padrão do Mac: barra lateral até os botões da janela e barra de ferramentas única.
- Janela **Sobre o Lume** com versões, créditos e as licenças de todos os componentes que
  seguem no motor (índice `licencas/indice.json`, gerado na montagem).
- Limites conhecidos: a assinatura é local (ad hoc), sem notarização; o Auditor Final
  continua indisponível.

## FONTE 0.9.5 — robustez semântica e memória narrativa

Atualização independente de motor, mantendo protocolos e schema de relatório. `narrative_memory.py` concentra promoção seletiva, classificação dos participantes e proveniência/confiança. O banco distingue `characters` e `local_participants`; fala e recorrência ou ação relevante podem promover uma identidade anônima singular. Referências inequívocas atualizam o foco discursivo; cortes explícitos continuam exigindo reintrodução do referente.

Encontros diferenciam agente e paciente; leitura conserva objeto; transferências preservam origem e destinatário. Conhecimento afirmado ou negado, descoberta, criação, encontro de objeto e cura/ferimento podem gerar fatos ligados ao evento original. Encontrar um objeto não afirma posse. Identificadores de fatos incluem os participantes e a polaridade, evitando colisão entre entrega e recebimento.

Estados físicos explícitos e inferências limitadas mantêm pesos distintos. Cura pode explicar uma ação posterior; incompatibilidade sem transição gera suspeita editorial. Posse, localização, conhecimento e estados têm histórico persistente. Identidade de objetos entre cenas exige evidência como proprietário, qualificador ou retomada explícita. Números compostos, horários e deslocamentos temporais simples foram ampliados.

O relatório apresenta participantes locais, fatos persistentes e confiança. Métricas de precisão e taxa de comparação global continuam não avaliadas; não são zeros nem garantia de correção. Nenhum Auditor Final, regra de mundo específica ou reescrita automática foi introduzido.

## Lume 0.11.4 — hotfix com FONTE 0.9.4

O aplicativo inclui o motor portátil FONTE 0.9.4, com Python, dependências e modelo português. A montagem verifica versão, inventário, saúde e assinatura antes de gerar o ZIP e seu resumo `release.json`. O empacotamento compartilhado está em `scripts/package_app.py`; entregas ficam separadas dos intermediários na subpasta `Pacote/`.

Documentação consolidada em README, arquitetura, histórico, validação e visão do projeto; exemplos têm um único índice. Licenças, corpus, testes e evidências de análises permanecem preservados. Não há alteração nova de regras linguísticas neste hotfix.

## Contrato de motor — versão 1

Um pacote é uma pasta `.lumemotor` com `manifest.json`, `runtime/lume-engine` e os arquivos incluídos pelo PyInstaller. O `lume-engine` executa a CLI do fonte-revisor diretamente, sem `python -m`.

O manifesto declara `package_schema`, `api_version`, `report_schema`, `decision_schema`, `engine_version`, `platform`, `architecture`, `minimum_os`, `executable` e `files`. O inventário relaciona todos os arquivos regulares por SHA-256 e os links simbólicos por destino relativo. Links precisam resolver dentro do pacote. O empacotador gera esse manifesto automaticamente, depois de o PyInstaller assinar seus binários internos.

A interface 0.8 usa protocolo 1, macOS e arm64. Antes de executar um candidato, o controlador embutido confere o inventário, arquitetura, versão mínima do sistema e protocolos. Após copiar, confere novamente, move o pacote para um diretório próprio e executa `--lume-probe` no caminho definitivo. O teste deve concluir em até 120 segundos.

O teste de saúde cria um DOCX temporário, lê seu conteúdo, carrega o modelo de português, confirma um alerta conhecido e verifica a disponibilidade do template HTML. Não certifica a qualidade linguística de toda a versão; regressões de análise devem ser cobertas pelos testes do fonte-revisor.

A ativação escreve `engine-state.json` de forma atômica e conserva a referência anterior. As operações de instalação/restauração usam bloqueio de arquivo para evitar duas alterações concorrentes. Uma interrupção antes da troca deixa o estado anterior; pode deixar uma pasta intermediária, que não é selecionada como motor.

O controlador de atualização utilizado pelo aplicativo sempre é o da cópia embutida, inclusive quando outro motor está ativo. Os motores importados fornecem a análise. O motor de reserva permanece dentro do bundle e não é sobrescrito por atualizações. Não modifique o conteúdo de uma pasta `.lumemotor` já distribuída; gere outro pacote.

Não há atualização automática por rede, verificação de publicador, notarização nem coleta de manuscritos. A escolha manual de um pacote autoriza executar o código dele. O inventário identifica alteração de conteúdo e arquivos faltantes, mas um autor de pacote pode criar seu próprio inventário; ele não é uma assinatura digital de autoria.

Para mudar regras, modelo ou dependências mantendo o protocolo, gere apenas um pacote de motor. Para mudar o protocolo, coordenar uma migração de dados ou alterar o controlador embutido, é necessária uma versão nova do aplicativo.

## Extensão compatível do FONTE 0.3.0

Relatórios permanecem no schema 1: os campos novos `layer`, `rule`, `confidence`, `related` e `context` são opcionais para leitura no Lume 0.4. Relatórios antigos continuam abrindo; a ausência de camada é tratada como linguística. As evidências usam `paragraph`, `chapter`, `text`, `start`, `end` e `document` (`atual` ou `original`), com offsets em pontos de código Unicode.

A CLI aceita `--modo linguistica|editorial|ambas` (padrão: linguistica) e `--original caminho.docx` nos modos editoriais. O modo editorial não carrega spaCy. Os IDs linguísticos existentes não mudaram. IDs editoriais incluem as evidências relacionadas, para não reaplicar uma decisão quando a evidência mudar.

O Lume 0.4 conserva decisões reconhecidas de outros modos do mesmo manuscrito. Clientes antigos não reconhecem as decisões novas `Intencional` / `Aceito editorialmente`; use o Lume 0.4 ou o HTML 0.3 para mantê-las. O motor 0.3 continua atendendo aos comandos antigos. Ao retornar a um motor 0.2.1, selecione Linguística: os novos modos exigem 0.3.0.

## FONTE 0.4.0 e Lume 0.5

Novo argumento `--config caminho.json`: schema de configuração 1, com validação estrita no motor. Sem esse argumento a CLI preserva o comportamento linguístico anterior. O Lume 0.5 sempre envia uma configuração completa, por isso exige motor >= 0.4.0. O protocolo de pacote e o schema de relatório continuam em 1; os campos opcionais novos são `metadata.search_settings` e `metadata.chapters`.

A configuração persistida por caminho fica nas preferências do app. Uma cópia é salva em `Application Support/FONTE/Configuracoes/` por execução e outra nos metadados do relatório. A cópia no relatório garante reprodutibilidade dos filtros selecionados; não implica que a interface tenha carregado esses critérios ao abrir um relatório antigo.

IDs de alertas que mantiverem posição, texto e evidência continuam recuperáveis. A separação de fala/inciso e a nova identificação de capítulo podem alterar evidências ou remover alertas. A regra de repetição consecutiva da busca configurada usa um ID novo. Decisões antigas permanecem guardadas, mas não são transferidas para alertas diferentes por semelhança.

## Lume 0.6 — somente interface

Motor FONTE 0.4.0, formatos e regras preservados. Estado de navegação explícito em `ReviewStore`: preparação, Mesa em análise, resultado e recuperação. Só transita para análise após as validações iniciais. Abrir um relatório válido entra diretamente na Mesa; selecionar outro manuscrito retorna à preparação. Voltar à preparação preserva o relatório em memória e suas decisões.

O seletor da configuração usa botões explícitos; não depende do cálculo de largura do `TabView` nativo. A janela principal tem mínimo de 1040 × 680; a configuração usa largura de 720 e altura limitada ao espaço visível da tela principal.


## FONTE 0.5.0 e Lume 0.7 — etapa 1 modular

O protocolo de pacote, o relatório e as decisões permanecem em schema 1. A extensão é aditiva: ocorrências recebem `module`, `category_code`, `severity`, `confidence_score`, `range`, `excerpt`, `message` e `suggestion`; `confidence` continua qualitativo para os leitores antigos. A semântica dos offsets está em [arquitetura e limites](docs/arquitetura.md).

`metadata.stages` registra o que realmente executou; `metadata.text_index` define a projeção de texto extraído. As linhas `LUME_PROGRESS {json}` são eventos locais para a interface. O parser ignora linhas incompletas e mensagens normais do processo. A captura do manuscrito é imutável; as etapas não recebem um editor de DOCX.

O Lume 0.7 exige motor >= 0.5.0 para analisar com as novas chaves de configuração. Configurações antigas completas recebem as quatro novas regras; se todas as antigas estavam desligadas, as novas também ficam desligadas. Os relatórios anteriores continuam legíveis, com módulo/classificação ausentes apresentados como informação não disponível.

A montagem executa testes Python antes do empacotamento e compila/executa o contrato Foundation/Swift após o build do aplicativo. A atualização somente do motor mantém o comando `bash scripts/montar-lume.command --motor`.

## FONTE 0.6.0 e Lume 0.8 — relações temporais

Três novas chaves de configuração: `coerencia_temporal`, `acentuacao_contextual` e `que_tonico_interrogativo`. O Lume 0.8 exige motor >= 0.6.0. Configurações anteriores completas com todas as regras desligadas continuam desligadas; configurações parciais herdam os padrões das regras não mencionadas.

As ocorrências temporais acrescentam `relation` e `temporal_evidence`, mantendo `related` como evidência navegável para leitores anteriores. O protocolo e os schemas continuam em 1. Quando uma regra temporal específica cobre o mesmo verbo, ela substitui o alerta genérico de tempo; seu ID é diferente e uma decisão antiga não é transferida automaticamente.

Pontuação duplicada e espaçamento agora alcançam falas/pensamentos; quê terminal tem regra própria. A acentuação contextual permanece na narração e as relações temporais seguem `tense_scopes`. As escolhas de registro coloquial não são normalizadas.

O diagnóstico do motor inclui uma relação entre condicional e futuro com sugestão e evidência. Os 30 novos testes incluem variação lexical, sujeitos diferentes, usos legítimos, omissão conhecida do parser e preservação dos offsets. Consulte [arquitetura e limites](docs/arquitetura.md) e [validação](docs/validacao.md).

## FONTE 0.7.0 / Lume 0.9

Atualização orientada pelo diagnóstico: proteções temporais compartilhadas com a regra antiga, sugestão contraída “irá ser” → “seria”, vocativos, capitalização restrita e início do Editorial por janelas curtas. Detalhes, contraprovas e pendências em [arquitetura e limites](docs/arquitetura.md).

Novas chaves: `vocativo`, `capitalizacao_contextual`, `dialogo_contextual`, `referente_contextual`, `gerundismo`. Configuração e relatório continuam no schema 1, com campos aditivos `suggestion_kind` e `scene_evidence`. O modo Editorial passa a carregar spaCy quando alguma das três regras contextuais está ativa; com elas desligadas, as regras editoriais anteriores continuam independentes do modelo. A interface exige motor 0.7.0 ou posterior. A mudança de intervalo da sugestão temporal gera um novo ID; decisões anteriores não são transferidas por semelhança.

## Lume 0.10 / FONTE 0.8.0 — memória narrativa

Editorial com cenas e eventos compartilhados com um banco de fatos por análise. Primeiros comparadores de habilidade exclusiva, estado de objeto e aniversário cronológico, com evidências e sem substituição automática. Memória consultável no HTML/JSON, resumo e novas opções no app. Detalhes de cobertura em [arquitetura e limites](docs/arquitetura.md) e corpus reproduzível em `examples/Memoria`.

A montagem também verifica se o código instalado corresponde aos fontes, evitando empacotar silenciosamente arquivos antigos de um cache com datas futuras.

## Lume 0.10.1 / FONTE 0.8.1 — falha no Editorial

Corrige a interrupção “Ocorrência incompatível com o manuscrito original” em ações narrativas iniciadas por verbos com clítico, como `— Não vou — virou-se Helena.`. O spaCy considera `virou-se` um token não inteiramente alfabético; a seleção anterior pulava esse verbo e iniciava o destaque em `Helena`, depois do fim do próprio verbo. A seleção agora reconhece tokens que contêm letras, incluindo hífens e acentos decompostos, preservando os offsets originais.

Inclui regressões para `virou-se`, `aproximou-se`, `sentou-se` e `ergueu-se`, além do controle com fala encerrada corretamente. O diagnóstico do motor portátil também executa o caso que causava a falha. A validação de intervalos permanece estrita; mensagens de falha agora identificam módulo, regra, parágrafo e intervalo sem expor o texto do manuscrito.

## 0.11 — FONTE 0.9.0

Build inicial de qualidade da memória: classificação de candidatos, referências conservadoras, sujeitos pronominais, tipos de evento semântico, habilidades demonstradas, estado de objeto e diagnóstico de conversão. Detalhes, validação e itens ainda parciais: [arquitetura e limites](docs/arquitetura.md). Entrega em `build/qualidade-0.11/`.

## 0.11.1 — FONTE 0.9.1

Melhora falantes explícitos/pronominais e alternância restrita; propaga referências e sujeitos compartilhados; consolida USE_ABILITY; amplia fatos de posse, localização, morte e estado; separa itens homônimos por introdução/dono/descrição. O teste fogo × gelo produz os dois fatos da mesma personagem. Ver [arquitetura e limites](docs/arquitetura.md) e `examples/Memoria111`.

## Lume 0.11.2 / FONTE 0.9.2 — fatos editoriais genéricos

Camada de atributos, estados, relações, posse, conhecimento, presença e cronologia integrada à memória narrativa. Comparações levam em conta identidade, transições reconhecidas e contexto temporal, mantendo suspeitas e perguntas ao autor em vez de erros confirmados. Nova opção de busca e rótulos no HTML. Corpus neutro obrigatório, contraprovas e substituições de entidades passam a orientar as regras; regressões anteriores permanecem.

Detalhes e limites: [arquitetura e limites](docs/arquitetura.md). A atualização não declara compreensão universal nem encerra os critérios de generalização da série v0.11.x.

## Lume 0.11.3 / FONTE 0.9.3 — qualidade dos fatos

Sujeitos por predicado, agente/paciente em passivas, atributos com vínculo correto, transições de objetos em ordem textual, conhecimento por personagem e tempo, presença após entrada/saída e comparação dos fatos já reconhecidos. Quantidades deixam de virar idade; menções deixam de virar localização; estados físicos deixam de inventar o autor da lesão. Hipóteses mantêm seu escopo ao separar orações.

Histórico e estado atual ficam ligados às evidências. A abordagem permanece conservadora e genérica. Detalhes, contraprovas e limites em [arquitetura e limites](docs/arquitetura.md).

## FONTE 0.9.4 — robustez em manuscritos reais

Corrigidos front matter, promoção indevida de personagens, atribuição de falas entre aspas, reinício artificial de cenas, narrador em primeira pessoa, conteúdo de fala capturado em gerúndios, autorreferência de objetos e identidade contextual de itens. Inclui numerais compostos, conhecimento negativo, estados de objetos, papéis semânticos, confiança e métricas com definições explícitas. Declarações de personagens preservam seu escopo.

278 testes do analisador e 14 de pacotes aprovados; contratos Python/Swift aprovados. Os manuscritos A e B foram reanalisados pelos fontes e pelo motor portátil final, com resultados semânticos idênticos e DOCX preservados. A cobertura continua parcial; detalhes e limitações em [arquitetura e limites](docs/arquitetura.md). O pacote é uma atualização independente do motor, instalado pelo menu do Lume.
