# Histórico do Lume e FONTE

As seções antigas descrevem a cobertura e os resultados de cada entrega, não o estado atual. Nas seções anteriores à 1.0, caminhos citados são da antiga pasta `LumeMac/`; a correspondência com a estrutura atual está em [README.md](README.md#estrutura).

## Em desenvolvimento

Ferramentas da mesa de leitura (só interface; o motor e os contratos não mudam).

- **Copiar contexto:** copia o título do capítulo e todos os parágrafos mostrados na página.
- **Copiar parágrafo marcado:** copia o parágrafo com o trecho destacado entre asteriscos e,
  abaixo, “Por que acendemos esta luz”.
- **Reanalisar:** na barra da mesa, analisa a obra de novo com as mesmas opções e mantém as
  decisões já marcadas: pelo ID do alerta e, nos demais, pelo conteúdo idêntico. A confirmação
  de envio à API continua valendo.
- **Limpar resíduos** (em Motor): apaga relatórios, registros e configurações de leituras
  antigas, depois de mostrar o espaço a liberar. Mantém o relatório aberto, o mais recente de cada
  livro, os falsos positivos extraídos, as decisões, as cópias de segurança, os projetos com IA e
  os motores.
- Verificação nova: `tests/DeskToolsCheck.swift`.

Falsos positivos morfossintáticos (FONTE), a partir de um livro narrado no presente:

- **Verbo finito:** antes de dizer que um segmento não tem verbo finito, uma segunda validação
  aceita a forma que o modelo e o léxico dão como finita, a que o léxico só conhece como verbo
  (“havia”) e o homógrafo na posição do verbo (depois do grupo nominal sujeito ou de um relativo).
  Na discordância entre as fontes, não há alerta.
- **Fragmentos:** a mensagem ficou neutra; oposição (“por outro lado”), enumeração e paralelismo
  contam como fragmento deliberado, sem alerta.
- **Subordinada isolada** (“Quando as luzes se apagam.”): categoria própria
  `incomplete_subordinate_clause`, confiança baixa, a partir de três palavras.
- **Fronteira de oração:** o verbo que fecha uma relativa (“o porão em que dormem é…”) não forma
  resíduo de edição com o verbo seguinte.
- **Narração no presente:** passado em oração dependente (relativa, completiva, adverbial),
  mais-que-perfeito composto e “devia/podia” + infinitivo não geram “Tempo verbal”; a relação
  coordenada não usa como âncora um verbo de relativa ou um imperfeito modal; o mesmo desvio não
  recebe dois alertas.
- **Aspas de destaque** (até três palavras no meio da oração, sem verbo nem pontuação interna)
  não ativam a regra de pontuação de diálogo.
- **Nomes da obra:** plural e singular de um nome reconhecido, linhas de créditos e “Nomes
  aceitos” valem para a grafia; termo desconhecido recorrente fica com confiança baixa.

Classes de erro que escapavam às regras locais (FONTE), com três verificações novas, ligadas por
padrão e desligáveis nos ajustes:

- **Correlação de tempos** (`correlacao_tempos`): “antes que”, “embora”, “se”, “ainda que” etc. com
  o imperfeito do subjuntivo e a oração principal no presente do indicativo. “Como se” fica de fora
  (pede sempre o imperfeito); nas concessivas, só atenção editorial.
- **Frase cortada** (`frase_cortada`): frase que termina em preposição, contração ou “cada” depois
  de verbo; parágrafo sem pontuação final; “Que” maiúsculo depois de reticências quando a oração
  continua (“Eu prometi… que voltaria”).
- **Locuções** (`locucoes`): “ao invés de” onde a norma pede “em vez de”; “embora” seguido só de
  um nome.
- **Concordância:** verbo de ligação no singular, sem sujeito expresso, com predicativo no plural.
- **Vírgula entre sujeito e verbo:** sujeito com oração relativa restritiva fechada por vírgula
  sem abertura; incisos de fala (“…, disse ele, …”) deixaram de ser apontados.
- **Variação de nomes:** o mesmo termo da obra com e sem maiúscula no meio da frase.
- **Tempo verbal e estrutura:** forma só verbal ligada como complemento (“de uma havia”) mantém o
  tempo; forma depois de “todo o” ou de preposição + artigo não conta como verbo.

Explicações dos alertas em linguagem simples: cada uma diz o que acontece com palavras do dia a dia
e, quando ajuda, um exemplo; o nome gramatical fica numa linha final (“Na gramática: …”), para quem
quiser pesquisar. Vale para todas as regras do FONTE (as mensagens do LanguageTool e da IA têm texto
próprio). Um teste garante o formato nos dois corpora; a detecção não mudou.
Os relatórios de `examples/` (Mestre, Editorial, Temporal) foram regenerados: mesmos alertas,
explicações novas.

LanguageTool, a partir das marcações de falso positivo: sugestão de grafia a duas letras ou mais da
palavra (“taser” → “fazer”) fica com confiança baixa e lembra que palavra estrangeira vai em itálico;
gerúndio que descreve um nome (“os passos do lobo correndo cessam”) não é tratado como auxiliar.

Encerramento editorial, primeira parte ([plano](.agent/plans/encerramento-editorial.md)): o objetivo
do Lume passa a ser interromper o editor só com boa razão e deixar o manuscrito chegar ao fim.

- **Documentação:** visão, `AGENTS.md`, arquitetura, validação e README com a nova definição de
  sucesso (precisão antes de cobertura irrestrita, “Revisão concluída”, Auditoria como controle de
  qualidade, nenhuma regra a partir de caso isolado).
- **Medição:** `scripts/medir_precisao.py` calcula a precisão real de cada classe a partir das
  decisões guardadas, sem gravar trechos. A avaliação do corpus mostra primeiro a precisão das
  pendências (97% no corpus atual) e os alarmes falsos por 10 mil palavras.
- **Política de destino v1** (`fonte/fonte/data/politica.json`): cada ocorrência leva `destino`
  (`pendencia`, `informacao` ou `diagnostico`) e `impeditivo`. Repetição próxima e classes de
  confiança baixa sem medição viram observações. Nenhuma classe é impeditiva nesta versão. IDs,
  trechos e severidades não mudam, e as decisões continuam valendo. Manuscritos: A 63 → 37
  pendências e 26 observações; B 15 → 2 e 13.
- **Regra `tratamento` retirada** por decisão do autor (nasceu de um caso isolado). A chave
  continua aceita nas configurações salvas, sem efeito.

Encerramento editorial, segunda parte:

- **Auditoria final como controle de qualidade** (política v2):
  - confiança baixa vai sempre para o diagnóstico;
  - as categorias experimentais começam no diagnóstico;
  - ortografia, concordância, crase e regência começam como observação;
  - a promoção depende só de dados, e nada da Auditoria é impeditivo.
  - O prompt não mudou: nada é reenviado nem custa.
- **Mesa em duas partes:**
  - **Pendências** (padrão) e **Observações**, com a contagem de cada uma;
  - **Impeditivos** em destaque no topo das pendências, sempre visíveis, mesmo zerados;
  - observações mais discretas, com a etiqueta “Observação” em vez de “Pendente de decisão”;
  - o diagnóstico do motor em Etapas e alcance, fora do fluxo editorial.
- **Revisão concluída:** **Encerrar revisão** fica disponível quando nenhum impeditivo está sem
  decisão. O registro guarda as pendências e observações abertas, a data e as versões do motor e
  da política, e vale para o mesmo texto e a mesma política.
- **Decisão “Corrigido”:** gravada pela correção no Pages. É o atalho ⌘7; os atalhos antigos não
  mudam.
- **Título da janela:** pendências sem decisão, no lugar de “X de Y avaliados”.
- **Compatibilidade:** relatórios antigos abrem com tudo em Pendências, sem impeditivos, e as
  decisões antigas continuam valendo.
- **Verificação nova:** `tests/ClosureCheck.swift`. A montagem passa a rodar também a verificação
  da mesa.

Narração no passado com dois planos e marcas que não são narração (FONTE), a partir de um texto de
terceiros (61 → 39 alertas, sem perder nenhum erro do corpus):

- **Fala no meio do parágrafo:** cada linha (quebra de linha manual) pode abrir fala com travessão
  ou hífen; a fala aberta continua na linha seguinte quando essa linha a fecha (“… - disse ela.”).
- **Narrador que fala de si no presente:** “me chamo”, “sou” + nome ou adjetivo, “acho/sinto/confesso
  que…”, “vou contar” e “quem eu sou” não geram tempo verbal. Ação da cena (“Abro a janela”, “Sinto
  o frio”), passiva (“Sou empurrado”) e comentário depois de um passado na mesma frase continuam.
- **Listas e rótulos** (“Equipe 2 Ana Rui”, “Parte 3”): sem tempo verbal nem pontuação final.
- **‘era’ nome** depois de determinante e adjetivo, antes de verbo ou ‘de’ (“Uma nova era começa”).
- **Tratamento** (`tratamento`, regra nova, ligada por padrão): ‘você’ com verbo na forma de ‘tu’
  no mesmo trecho (“Você tinhas razão”), como atenção editorial. A mistura entre falas diferentes
  do mesmo personagem continua fora do alcance local.

Mensagens do LanguageTool em linguagem simples: as regras mais frequentes nos relatórios reais
(ortografia, conectores, travessão, por que/porque, concordância, crase nos dois sentidos, hífen,
palavras parecidas etc.) têm explicação própria; as demais mantêm a mensagem do corretor. Todas
terminam com a linha “Na gramática:”. A identidade dos alertas não muda, e as decisões continuam.

Coerência com IA: a instrução pede explicações curtas, com palavras do dia a dia, e o alerta ganha
a linha “Na gramática: contradição de continuidade.” Mudar a instrução não reenvia capítulos: o
reenvio depende só do texto, e o cache dos julgamentos não inclui a instrução; o estilo novo vale
para capítulos novos ou alterados.

Auditoria final com IA (instrução versão 4): nunca sugere mudança de estilo (sinônimo, frase
reorganizada, repetição expressiva cortada, ritmo); a sugestão corrige só o erro, com a menor mudança.
“Repetição” vale só para palavra dobrada por acidente (“o o”) — e o código descarta, contando como
estilo, qualquer outra repetição que o modelo devolva. Explicações em linguagem simples, com o termo
gramatical na linha final. A mudança de versão faz os capítulos serem auditados de novo.

## Lume 1.6 · FONTE 1.4.0 · Coerencia 1.2.0 — 05/10/2026

Interface refeita a partir da referência do Stitch (“O manuscrito é papel. O Lume é instrumento.
A atenção é luz.”). O funcionamento não mudou: mesmas etapas, decisões, contratos, correção no
Pages e recursos com IA.

- **Identidade:**
  - SF Pro na interface e New York no manuscrito;
  - cantos pequenos, sem cápsulas e quase sem sombras;
  - a cor da vela só onde há atenção;
  - tokens claros e escuros em `LumeTheme`;
  - símbolo novo (chama em gota sobre um livro aberto de páginas cheias) em SwiftUI, em
    `docs/identidade/*.svg` e no ícone do app.
- **Janela:** o trilho lateral deu lugar a uma navegação na barra (Início, Leitura, Registro,
  Motor).
  - **Registro** mostra no app a saída do motor da última operação.
  - **Motor** virou uma tela com a versão carregada e as mesmas ações.
- **Início e preparação:** separados.
  - A preparação mostra o manuscrito, os três modos, os painéis A língua, A história e
    Auditoria final.
  - “Ajustar o que procurar…” mostra quantas verificações estão ativas.
- **Lendo com atenção…:** etapas numeradas com o estado real e a barra de andamento quando o
  motor informa. Corrigida a animação da chama, que fazia o layout da tela oscilar.
- **Mesa de leitura:** Pontos de atenção | Manuscrito | Inspetor editorial.
  - A página mostra o parágrafo iluminado entre os parágrafos próximos do relatório, com a
    chama e o § na margem.
  - O inspetor reúne:
    - a classificação;
    - “Por que acendemos esta luz”, a sugestão e as evidências;
    - as ações no Pages, separadas da decisão;
    - as seis decisões;
    - os detalhes técnicos.
  - Numa janela estreita, o inspetor desce para baixo da página.
  - O menu Capítulos leva ao primeiro alerta do capítulo.
- **“Ajustar o que procurar”:** seções numa barra lateral. As regras continuam vindo de
  `SearchRule.all`.
- **Código:** `ContentView.swift` foi dividido em `HomeView`, `ReadingProgressView`,
  `ReadingDeskView`, `FindingsColumn`, `ManuscriptView`, `FindingInspector`,
  `SearchSettingsView` e `EngineView`. O `ReviewStore` continua sendo a única fonte de estado.

## Lume 1.5 / FONTE 1.4.0 · Coerencia 1.2.0 — 05/10/2026

Auditoria final com IA, aviso de tempo contradito e falsos positivos salvos ao lado do relatório.

- Auditoria final com IA (Claude), desligada por padrão porque custa dinheiro. Depois das
  outras etapas, o Claude relê cada capítulo com os alertas já encontrados e aponta só
  problemas novos, como suspeitas: nunca erro confirmado, nunca confiança alta.
  - Opus 5.5 e teto de US$ 1,00 por padrão.
  - Os trechos citados são conferidos no texto, e o que não existir ou repetir um alerta é
    descartado.
  - Só trechos novos ou alterados são enviados.
  - Antes do envio, uma única confirmação mostra trechos e custo da Coerência e da Auditoria.
  - Uma falha da auditoria interrompe só ela, e o relatório das outras etapas é mantido.
  - Desligada, a etapa aparece como “Não selecionado” (`skipped`).
  - Na linha de comando: `revisar --auditoria-ia --auditoria-projeto P` e `auditoria-estimar`
    (veja a [arquitetura](docs/arquitetura.md#auditoria-final-com-ia)).
  - A estimativa de custo foi calibrada numa medição curta e ainda é aproximada para capítulos longos.
- Aviso quando a narração contradiz o tempo escolhido: com Passado ou Presente escolhido, se ao
  menos 20 verbos da narração e 70% dos que têm tempo identificado estão no outro tempo, o
  relatório traz um aviso em “Sobre esta análise” e o campo opcional `metadata.tempo_contradito`
  (`escolhido`, `predominante`, `passado`, `presente`); o app mostra uma faixa no topo da lista
  de alertas. Os alertas não mudam. Sem aviso quando o escopo do tempo verbal inclui falas ou
  pensamentos (o presente comum nelas distorce a contagem) ou quando a regra está desligada.
  Motivo: um livro narrado no presente, analisado como passado, gerou milhares de alertas de
  tempo verbal.
- **Extrair falsos positivos** grava `falsos-positivos.json` na pasta do relatório, sem
  perguntar o local (cada extração refaz o arquivo com as marcações atuais), e mostra
  **Mostrar no Finder**. O painel de salvar só aparece se a pasta não aceitar gravação.
- Frases de testes, exemplos, comentários e documentação parecidas com manuscritos reais foram
  reescritas com outras palavras e outros contextos, mantendo o fenômeno que cada caso cobre.
  Os DOCX de exemplo `Manuscrito-editorial` e `Mestre/Manuscrito-modular` mudaram e os
  relatórios `examples/Editorial` e `examples/Mestre` foram regenerados pelo FONTE 1.3.1.
- Coerencia 1.2.0: o cliente da API distingue recusa, resposta cortada e teto atingido
  (`Recusa`, `RespostaCortada`, `TetoAtingido`, subclasses de `ErroModelo`, com as mesmas
  mensagens). A Coerência funciona como antes.

## Lume 1.4.1 / FONTE 1.3.1 · Coerencia 1.1.0 — 04/10/2026

Correção: uma ocorrência com trecho inválido não descarta mais a análise inteira.

- Concordância nominal com o predicativo antes do sujeito (“Estavam apagada as luzes”): o
  trecho ia do substantivo ao adjetivo e, com o substantivo depois, ficava com o início além do
  fim. A conferência de integridade recusava o relatório e a etapa morfossintática falhava,
  perdendo toda a análise já feita. O trecho agora vai do primeiro termo ao último. O defeito
  existia desde a 0.11.
- Ocorrência cujo trecho ou evidência não corresponde ao manuscrito (sempre um defeito de regra)
  passa a ser descartada sozinha: a etapa termina, o relatório traz um aviso em “Sobre esta
  análise” com a regra afetada, e os detalhes ficam em `metadata.ocorrencias_descartadas`
  (chave nova). Nenhum alerta aponta trecho inexistente. Captura divergente do manuscrito,
  classificação inválida e identificador repetido continuam interrompendo a etapa.
- O app abre relatórios de até 200 MB (antes 25 MB). Um livro de 13 mil parágrafos gerou um
  relatório de 36 MB que terminava a análise mas não abria; ele é lido em cerca de 1 s.

## Lume 1.4 / FONTE 1.3.0 · Coerencia 1.1.0 — 04/10/2026

O tempo verbal passa a ser lido na sequência de ações da cena, e não só verbo a verbo; menos
alertas sobre presentes legítimos e fragmentos deliberados.

- Sequência temporal: o tempo verbal passa a ser lido também na sequência de ações, com o
  estado narrativo local (até 4 frases antes e 2 depois, no mesmo parágrafo ou no anterior).
  Três alertas novos, de confiança alta, em `Coerência temporal entre orações`:
  `past_present_past` (ação no presente entre ações no passado do mesmo plano),
  `coordinated_tense_mismatch` (ações coordenadas do mesmo sujeito em tempos diferentes, nos
  dois sentidos: “pega … e abriu”, “puxou … e solta”) e `same_subject_narrative_shift` (presente
  depois de uma cadeia de ações no passado do mesmo sujeito).
- O presente que não é evento narrativo (pergunta ou exclamação, verdade geral, hábito, fala
  relatada, propriedade com ‘ser’, ‘ter’, ‘haver’ ou ‘parecer’, modal com infinitivo) continua
  visível em `Tempo verbal`, com confiança baixa. ‘estar’ (estado passageiro, progressivo) e
  ‘parecer’ + infinitivo seguem com confiança média. “Há dez minutos” numa narração no passado
  ganha explicação própria, com confiança baixa.
- Verbos que o modelo lê como nome ou adjetivo (“Procura…” no início da frase, “Ela segura a
  mochila”, “Abri”) são reconhecidos pelo léxico e pela sintaxe na sequência temporal.
- Estado temporal local da cena (`local_state`: proporção de passados nos últimos verbos da
  janela; passado firme com dois ou mais passados, três quartos da janela e o último verbo no
  passado). O passado depois do presente confirma, mas não é exigido. Novo alerta
  `local_narrative_tense_shift` (confiança média): ação de outro sujeito, ancorada na cena
  (entidade nova, retomada, 1ª pessoa ou perífrase aspectual), no presente numa cena narrada no
  passado. `same_subject_narrative_shift` usa a cadeia mais recente de sujeito consistente e
  aceita um só passado quando o presente sem sujeito continua a ação anterior (confiança média).
  Precedência, um alerta por verbo: coordenação, passado-presente-passado, mesmo sujeito, cena,
  genérico. Separador de cena e parágrafos só de diálogo interrompem o estado; a troca de
  parágrafo não.
- Coordenação: o auxiliar finito de uma locução (“estava observando”) serve de âncora; orações
  coordenadas com outro sujeito (“…ficam mais altos, mas ele não conseguia…”) recebem confiança
  média; ‘vira’ (virar/ver) é desempatado pelo lema. Presente → passado (“Ela ergue a arma. O
  homem recuou.”) e “continua deslizando… Então bateu” entram na sequência.
- `conditional_tense_mismatch`: “se” + imperfeito do subjuntivo com consequência no futuro ou
  presente (“se chegasse, conseguirá”), e “se” + presente ou futuro do subjuntivo com futuro do
  pretérito (“se parar, morreria”). Discurso indireto fica de fora. Sem sugestão.
- Sugestão no aspecto da âncora: perfeito com perfeito (“caiu e se quebra” → “quebrou”),
  imperfeito com imperfeito; âncoras mistas ou forma incerta, nenhuma sugestão.
- Precedência explícita por verbo (condicional, coordenação, passado-presente-passado, mesmo
  sujeito, cena, genérico). `metadata.temporal_relations` lista os detectores novos.
- Função do presente: ‘estar’ + adjetivo ou particípio é estado passageiro (fora da sequência,
  peso médio no genérico); pergunta reconhecida mesmo quando o modelo separa o “?”;
  demonstrativo próximo no sujeito (“esse diretor…”) é comentário do narrador; pronome retoma
  só nome de gênero e número compatíveis; parágrafo que abre com hífen ou travessão fica fora da
  sequência.
- Concordância pelo núcleo: determinante singular (“nenhuma palavra conseguiram”) e partitivo
  “um/uma de” (“uma das portas estavam”), fora de “um dos que”; aposto entre vírgulas e plural
  sem -m/-ão ficam de fora.
- Depuração com o manuscrito real (instrumentação `trace` em `temporal.analyze`, só para
  desenvolvimento): fala intercalada curta não zera mais a cena (cada parágrafo de fala pesa uma
  frase); frases sem verbo não consomem a janela; um só passado sem presente na janela já
  estabelece o estado; marcas de tempo valem só para o verbo que as governa (“desde que saímos”,
  “a reunião de hoje”, “mais forte ainda” não liberam o verbo principal); perífrase em que o modelo
  pôs o gerúndio como raiz (“Fico olhando”); ‘para’ verbo (“o carro para no meio”); verbo
  finito nunca logo depois de preposição (“em volta dele”).
- Marcador discursivo (“Tá.”, “Tá bom.”, “Não importa.”): sem alerta temporal. O ramo presente →
  passado não dispara mais com estado vazio: sem verbos antes, `local_state` é `unknown` e o
  passado que confirma aparece em `following_narrative_verbs`.
- Fallback superficial de coordenação quando a análise sintática se perde (“Mariana segura a
  bolsa e saiu”), com confiança média e `temporal_evidence.surface`.
- ‘Talvez’ + futuro do pretérito (`modal_mood_mismatch`, confiança média, sem sugestão), fora de
  condicional e de comparativa; condicional com “se” + forma igual ao infinitivo (futuro do
  subjuntivo); consequência de condicional é hipótese, não ação.
- Vocativo com aposto de afeto sem vírgulas (“Pedro meu amigo venha aqui” → “Pedro, meu amigo,”).
- `temporal_evidence` ganha `function`, `local_state`, `local_tense_score`,
  `previous_narrative_verbs`, `same_scene` e `same_subject` (campos novos; os antigos ficam).
- ‘Ainda’ só mantém no presente um estado que continua (“está quebrado ainda”), não uma ação
  (“ainda caem pelo chão”). Verbos de memória e crença do narrador (“não lembro”) contam como
  estado, mesmo com o lema errado do modelo (radical + terminação).
- Resíduo de edição: dois auxiliares conjugados seguidos no mesmo predicado (“tinha havia
  percebido”), sob “Estrutura da frase”.
- Concordância: “nenhum/cada” etiquetado como numeral e concordância por atração (“a lista de
  objetos estavam”); coletivos e quantificadores partitivos (“a maioria dos”, “um monte de”)
  ficam de fora.
- Verbo único da frase sem objeto, abrindo-a ou logo depois do grupo nominal que a abre
  (“Caminho até a janela.”, “O relógio demora a bater.”), entra na sequência temporal mesmo
  quando o modelo o lê como nome. Palavra sozinha (“Nada.”) e palavras gramaticais que o léxico
  também lista como verbo (“Aquela”, “Apenas”, “Pelo”) ficam de fora. A 1ª do plural igual no
  presente e no perfeito (“passamos”) serve de âncora no passado.
- ‘Ainda’ com ‘estar’ sem predicativo (“ainda está no quintal”) não libera o presente.
- Função do presente: ‘parecer’ + adjetivo com sujeito pessoa é estado passageiro; hábito sem
  conjunção (“durante todo o ano”, “normalmente”, ‘costumar’) e propriedade genérica (“O ferro
  conduz eletricidade”) são verdade geral, com confiança baixa.
- “era” nome depois de artigo indefinido ou contração (“uma era de ouro”, “nessa era”) não é
  verbo; “Essa era a última carroça” continua cópula.
- Fala aberta por hífen e espaço (“- Vamos.”) é reconhecida como o travessão, respeitando a
  escolha de analisar ou não o tempo verbal no diálogo; o hífen de palavra composta continua
  dentro da fala.
- Nova suspeita em `Estrutura da frase` (confiança baixa,
  `fragmentos_sem_verbo.subordinate_without_main`): oração subordinada sem principal (“Quando
  saiu do consultório depois de assinar os papéis.”). Frase com vírgula, nome seguido só de
  relativa (“Uma coisa que ninguém esperava.”) e subordinada intercalada ficam de fora.

## Lume 1.3.1 / FONTE 1.2.1 · Coerencia 1.1.0 — 03/10/2026

Decisões mantidas depois de editar o manuscrito fora do Lume, menos alertas sobre fragmentos
deliberados e explicações mais claras.

- Decisões por livro: o Lume guarda as decisões de cada manuscrito pelo nome do arquivo (sem a
  extensão; `.docx` e `.pages` com o mesmo nome são o mesmo livro), em
  `~/Library/Application Support/FONTE/Livros/`. Antes, editar ou só salvar o arquivo no Pages
  mudava o SHA-256 e a nova análise começava toda pendente. Agora cada alerta idêntico ao da
  análise anterior (mesmo texto do parágrafo, trecho, regra e evidências, ainda que o parágrafo
  tenha mudado de posição) recupera a decisão; alertas de parágrafos editados ficam pendentes.
  Na primeira análise depois da atualização, as decisões já salvas do mesmo livro são usadas.
- Estrutura da frase: deixa de alertar o complemento solto que retoma o verbo da frase
  anterior (“Pensei no jardim. Naquela mulher de chapéu azul.”), com a mesma preposição e sem
  vírgula, e o pensamento suspenso por reticências concluído por expressão nominal curta
  (“Depois do exame… nenhuma resposta.”). A mensagem passa a citar o trecho e não traz mais o
  aviso técnico sobre o analisador.
- Ação narrativa após fala: a explicação diz o que falta (pontuação para encerrar a fala,
  maiúscula na ação) e dá um exemplo montado com o próprio texto.
- Regência de “chegar em”: vira nota de registro, com prioridade “Explorar” e sem sugestão de
  troca, já que a forma é corrente no português brasileiro.
- Vírgula em “além disso” (LanguageTool, `VERB_COMMA_CONJUNCTION`): sem alerta quando “além de”
  completa um pronome ou sintagma (“não sobrou nada além disso”, “ninguém além dele”, “coisa
  alguma além daquilo”, “nenhum caderno além desse”); o conector sem vírgulas (“cansado e além
  disso precisava”) continua apontado. A mensagem dessa regra deixa de afirmar que o conector
  “só deve ser utilizado no início duma frase”.
- Estrutura da frase: o segmento sem verbo finito passa por uma classificação com a frase
  anterior e a seguinte. Só a oração incompleta (subordinante ou relativo sem oração, ou corte
  em palavra que pede continuação) recebe o alerta normal, com mensagem própria. Predicação
  elíptica (adjetivo que concorda com um referente da frase anterior: “Encontramos três
  garrafas. Verdes. Minúsculas diante das ondas.”), fragmento adverbial (“Primeiro bem devagar
  e, em seguida, mais depressa.”), frase nominal com núcleo sem artigo e sequência de
  fragmentos descritivos ficam sem alerta; o resto aparece com confiança baixa. O relatório
  conta as classes em `metadata.fragmentos_sem_verbo`.
- Verbo de ligação: “era”, “seria” e outras cópulas que o modelo etiqueta como verbo ou
  advérbio (e que também são substantivos no léxico) deixam de ser lidas como substantivo. A
  relação sintática de cópula ou auxiliar passa a valer como verbo, junto com a morfologia do
  modelo ou o léxico.
- Corpus de desenvolvimento: controles `dev-controle-elipse`, `dev-controle-reticencias` e
  `dev-controle-alem`.

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
