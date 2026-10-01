# Validação

Os registros abaixo pertencem às versões indicadas. Caminhos citados nos registros anteriores à 1.0 são da antiga pasta `LumeMac/` (correspondência em [README.md](../README.md#estrutura)); os comandos abaixo usam a raiz do repositório. As verificações do hotfix aparecem primeiro; os registros anteriores são mantidos para rastreabilidade.


## Lume 1.2 / FONTE 1.2.0 · Coerencia 1.1.0 — 01/10/2026

Interface do alerta reorganizada, extração de falsos positivos e remoção do relatório HTML.
Nenhuma regra de detecção mudou; os alertas são os mesmos da 1.1, por isso não houve
comparação nos manuscritos A e B.

- 229 testes do analisador, 25 dos pacotes, 24 do Coerencia e o contrato Python aprovados. Saíram
  os testes do próprio HTML (escape de `</script>` e destaque `<mark>`) e os cinco testes DOM;
  o teste de integração e o contrato Python passam a exigir que a saída contenha só
  `relatorio.json`.
- `vulture` sem funções ou classes sem uso em `fonte/fonte`, `coerencia/coerencia`,
  `packaging` e `scripts`.
- Montagem completa aprovada: contratos Swift, build Release arm64 e teste de saúde do motor
  1.2.0. SHA-256 do `Lume.app.zip`:
  `94ffa0a50ab786a619d31c70e1952fef9a251c7081f4d27697122ebfc8bc2a56`.
- Interface nova (botão Confirmar, avaliações numa linha, Extrair falsos positivos) conferida
  pelo autor no app montado em 01/10/2026. Pendência: a extração de falsos positivos não tem
  teste automatizado.

## Lume 1.1 / FONTE 1.1.0 — 30/09/2026

Leitura de Pages conferida nos fontes; a montagem completa está registrada ao final desta seção.

- 227 testes do analisador na leitura (11 novos em `fonte/tests/test_pages.py`), 25 dos pacotes, 29 do
  Coerencia e o contrato Python aprovados. Build Debug do Xcode concluído; o contrato Swift
  não foi executado (nenhum modelo mudou) e a interface não foi inspecionada visualmente.
- Os oito DOCX de `examples/` e os manuscritos A e B foram convertidos para `.pages` pelo
  Pages 15.3 em cópias temporárias fora do repositório. A leitura do `.pages` devolveu os
  mesmos blocos do DOCX (texto, capítulo, título, papel e itálicos): 8/8 exemplos, A e B
  (236 e 1274 parágrafos não vazios).
- A refatoração de `read_docx` devolve blocos e avisos idênticos aos da revisão `addc886`
  nesses dez arquivos; nenhum alerta muda.
- `fonte/tests/corpus/pages/manuscrito-sintetico.pages` foi criado no Pages com texto
  escrito para o teste.
- Limites: só o Pages 15.3 foi conferido; tabelas inline, notas e alterações controladas do
  Pages não foram exercitadas com documentos reais.

### Correção no manuscrito

- 230 testes do analisador (3 da conferência de correções) aprovados; `tests/EditCheck.swift`
  valida o cálculo das posições (emoji, acento combinado, correções sucessivas, inserção,
  recusas) e o histórico JSON.
- Ponta a ponta numa cópia do documento sintético, com o Pages 15.3: troca depois de emoji,
  troca de palavra em itálico (itálico mantido), inserção após acento combinado e remoção;
  `conferir-edicao` aprovou e os demais parágrafos ficaram idênticos. Parágrafo diferente
  do esperado foi recusado sem alterar o arquivo.
- Achado: o Pages só abre o arquivo no lugar quando a referência é criada fora do bloco
  `tell`; do contrário mostra “operação não permitida” e abre uma cópia sem título.
- Achado no primeiro uso real: texto passado ao `osascript` como argumento chega com os
  acentos decompostos (“á” vira “a” + acento combinado); a conferência do motor recusou e o
  arquivo foi restaurado. Os textos agora seguem como códigos Unicode. Numa cópia temporária
  do manuscrito A, sete sugestões com acento foram gravadas e conferidas (7/7).
- `scripts/montar-lume.command` completo na 1.1: 230 testes do analisador e 25 dos pacotes,
  contratos Python e Swift, `EditCheck`, motor arm64 1.1.0 congelado e app 1.1 (build 19)
  assinado ad hoc. O motor embutido analisou o `.pages` sintético; 29 testes do Coerencia.
- No app empacotado, o autor gravou uma correção num manuscrito real; a segunda falhou pelo
  defeito dos acentos acima e foi desfeita pela conferência.
- Não verificado: o fluxo pela interface (botão, confirmação, cópia, restauração, herança
  de decisões na reanálise) foi compilado, mas não exercitado no app; permissão de
  Automação pedida pelo app empacotado; documento já aberto no Pages; manuscritos reais.

## Lume 1.0 / FONTE 1.0.0 — 29/09/2026

- `scripts/montar-lume.command` completo: 216 testes do analisador, 25 dos pacotes e 29 do Coerencia
  aprovados; contratos Python e Swift validados; motor arm64 1.0.0 congelado, relocado e testado
  com o LanguageTool embutido; app 1.0 (build 17) assinado ad hoc e verificado (`codesign --verify --deep --strict`).
- Licenças: 58 componentes em `Engine.lumemotor/licencas/indice.json`, todos com arquivos presentes
  no pacote e listados no manifesto. Janela Sobre inspecionada em renderização nativa (claro e escuro).
- Detecção: corpus cego 53/55 com 7 alarmes falsos; controles `dev-controle-costureira` e
  `dev-controle-arena` sem alarmes. Manuscrito A 228 → 214 e manuscrito B 20 → 18 na última rodada de
  falsos positivos, sem perder erros confirmados pelo autor.
- Limites: sem notarização (uso no próprio Mac); Auditor Final indisponível; o corpus é
  sintético e não substitui textos anotados por outra pessoa.

## Revisão das regras no relatório do manuscrito A revisado — 29/09/2026

As 286 ocorrências de um relatório real do app (manuscrito A revisado, passado, corretor embutido)
foram lidas uma a uma. Alarmes falsos corrigidos por causa geral, com reproduções neutras:
verbos de fala com lema errado pelo modelo (“perguntei”, “respondemos”), vocativo em conjunção
ou verbo (“Mas você”, “Achei você”), “Porque … , hein?”, “o que quer que”, nome próprio após
vírgula, onomatopeias e interjeições (“Humm”, “Fwoosh!”, “BOOOOM”), palavra cortada na fala,
sujeito posposto a verbo de fala sem crase e duas sugestões de estilo do LanguageTool.
Mesmo arquivo e configuração: 286 → 228 ocorrências, 58 alarmes falsos removidos, nenhum
acerto perdido e nenhuma ocorrência nova. Validação 19/20 com alarmes 6 → 5; manuscrito B 127 → 126
(saiu o vocativo falso “Achei você”). 204 testes do analisador.

Observações para o autor: a partir do §1080 a narração alterna presente e passado nos mesmos
parágrafos (a maior parte dos 126 alertas de tempo verbal); “Estrutura da frase” aponta
fragmentos intencionais e pode ser desligada na configuração da busca.

## Coerência com IA em texto real, revisada pelo autor — 29/09/2026

Manuscrito A revisado (~13 mil palavras, 29 cenas, Sonnet 5.5, US$ 0,77): 2 alertas, ambos de
confiança média, avaliados pelo autor. C001 (duas marcações de tempo
aparentemente incompatíveis): **alarme falso**; o intervalo entre as cenas torna o texto coerente.
C002 (objeto descrito de forma ambígua): **problema real de redação**; uma preposição levava a
uma leitura de distância em vez de tamanho. Precisão nesta
amostra: 1 de 2. Contradições não detectadas neste texto: desconhecidas (sem gabarito). Uma
nova exportação com o mesmo texto não reenviou nada (0 capítulos, US$ 0).

## Remoção da memória narrativa heurística — 29/09/2026

Removidos 11 módulos (`semantic*.py`, `narrative*.py`, `generic_facts.py`, `fact_*.py`) e 181
testes exclusivos deles; as regras correspondentes ficam aceitas e ignoradas em configurações
antigas (Python e Swift, com teste). Suítes: 196 testes do analisador, 25 de integração,
contratos Python e Swift, build Release. Comparação com o motor anterior (`Pacote-3`), mesmos
arquivos e configurações: Manuscrito B 127 → 127 ocorrências e manuscrito A 1.139 → 1.139, com os mesmos
IDs; a memória narrativa não gerava nenhum alerta nesses livros. `validate_real_memory.py`
passa a comparar ocorrências e preservação do arquivo, sem banco de fatos.

## Coerência com IA no app — 29/09/2026

Plano em `.agent/plans/coerencia-no-lume.md`. 375 testes do analisador (6 novos da integração, com modelo simulado),
25 de integração, contratos Python e Swift, build Release sem avisos nos arquivos alterados. Motor congelado com o
Coerencia e o SDK da Anthropic: diagnóstico `coherence_ai: true`, estimativa sem API e erro claro com chave inválida.
Ponta a ponta com a API real pelo motor do app empacotado (texto de 2 capítulos): contradição de cor dos olhos apontada
com os dois trechos, memória narrativa heurística não executada, US$ 0,013. A estimativa inicial (só por caractere)
previa US$ 0,0005; recalibrada com custo fixo por cena a partir de duas medições (manuscrito A US$ 0,77 e este teste),
passou a prever US$ 0,0124. App em `build/coerencia-app/Pacote/` (335 MB), assinatura local.

Pendências: inspeção visual da nova seção, da folha da chave e do alerta de confirmação no app; o primeiro acesso do
app à chave pode pedir autorização das Chaves do macOS; calibração de custo com mais textos.

## Detecção generalizada — corretor embutido e regras gramaticais — 29/09/2026

Fontes locais sobre a versão 0.9.5 (sem mudança de número de versão). Plano e decisões em `.agent/plans/deteccao-generalizada.md`; evidências em `build/deteccao-generalizada/`. Em 29/09, os intermediários (`Pacote`, `Pacote-2`, `motor`, `motor-2`, `DerivedData`, rodadas intermediárias em `real/`) foram removidos; ficaram a entrega final (`Pacote-3`, `motor-3`), as linhas de base e a rodada final dos manuscritos, e os logs e resultados de avaliação.

Avaliação cega em textos sintéticos inéditos (`fonte/tests/corpus/deteccao/`). O conjunto `validacao` não foi usado para criar nem ajustar regras. Denominadores: erros anotados; alarmes falsos são ocorrências fora de erros e de trechos anotados como aceitáveis.

| Conjunto `validacao` (4 textos, 1 de controle) | Erros linguísticos | Contradições | Alarmes falsos |
| --- | ---: | ---: | ---: |
| Antes, padrão do app (sem corretor) | 5 / 20 | 0 / 4 | 5 |
| Antes, LanguageTool externo | 13 / 20 | 0 / 4 | 21 |
| Depois, sem corretor (regras FONTE) | 14 / 20 | 0 / 4 | 5 |
| Depois, padrão novo (corretor embutido) | 19 / 20 | 0 / 4 | 6 |

As linhas “antes” foram recontadas com a correção do placar (trecho com limite de palavra), aplicada igualmente a todas. Os 6 alarmes restantes: repetição de ‘letra’ a curta distância, tempo verbal em narração no presente (‘era’) e em fala sem travessão inicial (‘diz’, ‘ajuda’), vocativo antigo em ‘Foi você?’ e sugestão de vírgula do LanguageTool. Perdido: crase em ‘a luz de uma vela’. Nenhuma contradição narrativa é detectada; a memória narrativa não foi alterada nesta etapa.

- 364 testes do analisador (38 novos) e 25 de integração (8 novos) aprovados; contrato Python e contrato Swift aprovados; build Release arm64 aprovado.
- LanguageTool 6.6 embutido com os dados grandes de outros idiomas removidos (o registro de idiomas é mantido, porque o detector de idioma o exige; português consulta o dicionário de inglês) e Java 25 mínimo por jlink: resultados idênticos ao LanguageTool completo em todo o corpus.
- Motor congelado `fonte-0.9.5-ea34d868.lumemotor` (318 MB; ZIP 176 MB) validado após relocação, com o corretor iniciado pelo Java do pacote; paridade exata entre fontes e executável no corpus. App empacotado e assinado localmente (322 MB; ZIP 177 MB). Nenhum app instalado foi substituído.
- Manuscritos A e B: as versões com o SHA-256 das validações anteriores não estão mais disponíveis. Usados o manuscrito B (3b618a66…) e o manuscrito A (fe8ede95…), com as mesmas configurações, contra o motor 0.9.5 congelado como linha de base. Hash e índice textual preservados, fatos com origem válida. Todas as ocorrências anteriores foram mantidas; 19 novas (17 no manuscrito B, 2 no manuscrito A), todas revistas manualmente e consideradas corretas. A primeira rodada mostrou 6 alarmes (concordância e vírgula em vocativos de fala marcada por hífen) e a remoção de um verbo real; foram corrigidos com reproduções genéricas antes da rodada final. Pequenas diferenças na memória narrativa (1 objeto no manuscrito B, 1 evento no manuscrito A) já existiam nos fontes antes desta etapa.

Rodada do usuário (`texto-teste-farol.docx`, na raiz Git, gabarito ao lado): no app, 14/18 erros linguísticos, 0/2 contradições e 3 alarmes falsos (nome próprio lido como plural pelo modelo). Corrigidos com reproduções genéricas: plural exige terminação em -s; ‘há’ com “mais de/cerca de”; ‘em baixo’ isolado; novo alerta de atenção para pronome reto como objeto (“ajudou ela”), fora de incisos de fala e verbos intransitivos. Depois: 17/18, 0/2, nenhum alarme falso (esse texto deixou de ser cego). Validação continua 19/20; manuscrito B/manuscrito A ganharam 5 alertas de pronome, todos corretos na norma (2 em falas marcadas por hífen). 366 testes do analisador aprovados. Motor e app remontados em `build/deteccao-generalizada/Pacote-2/`, com paridade entre fontes e executável no texto de teste.

Segunda rodada do usuário (`texto-teste-restaurante.docx`): no app, 9/15 erros linguísticos, 0/3 contradições. Corrigidas com reproduções genéricas: ‘haver’ existencial no plural (fora de auxiliar e de “haver de”), ‘mas/mais’ seguido de artigo quando há verbo conjugado no mesmo trecho, adjetivo substantivado como objeto na crase, ‘porque’ depois de vocativo em pergunta direta (verbos confirmados também pelo léxico), e ‘ler/recitar/citar/ditar/cantar/declamar’ como verbos de fala. Depois: 13/15; ficam de fora ‘com as mãos firme’ (adjetivo após preposição, ambíguo) e vírgula após sujeito oracional numa fala. Validação 19/20 e farol 17/18 sem mudança; manuscrito A ganhou ‘houverem’ e uma pergunta com ‘porque’, ambos corretos (um “É porque…, viu?” causal foi evitado antes da rodada final). 369 testes aprovados. Remontado em `build/deteccao-generalizada/Pacote-3/`, com paridade no texto de teste.

Pendências: testes DOM do HTML (jsdom ausente; só a sintaxe do JavaScript foi verificada); inspeção visual nativa do app (a mudança visível é o corretor ligado por padrão e cinco regras na configuração de busca); avaliação por corpus anotado por outra pessoa. Motores antigos selecionados no app recebem `--languagetool` por padrão e falham sem servidor externo; a opção pode ser desligada.

## FONTE 0.9.5 — memória narrativa — 29/09/2026

- 300 testes do analisador aprovados, incluindo 22 novos testes com subcasos. Execução em `fonte/` garante importação dos fontes atuais; executar a partir de `LumeMac/` pode importar a cópia antiga instalada no ambiente virtual.
- 17 testes de pacotes aprovados. Contrato CLI/JSON aprovado após a atualização da versão; JavaScript do HTML passou na verificação de sintaxe. A interface nativa e o DOM completo não foram inspecionados nesta entrega.
- Motor arm64 0.9.5 gerado e validado após relocação. A montagem exigiu permissão para atualizar o cache do PyInstaller fora do sandbox. Nenhum aplicativo instalado foi substituído.
- Paridade exata de `findings`, cenas, banco e diagnósticos entre fontes e executável nos manuscritos A e B e num DOCX de casos mínimos. Este último tem 19 fatos com IDs únicos e exatamente uma suspeita física; a cura posterior explica o segundo chute.
- SHA-256 e índice textual dos dois manuscritos reais preservados. Os arquivos não foram copiados para testes versionados; as regressões neutras estão em `fonte/tests/test_persistent_memory.py`.

Comparação com a cópia instalada do motor **0.9.4**, usando os mesmos manuscritos e configurações:

| Manuscrito | Personagens canônicos | Fatos totais | Referências vinculadas | Falantes identificados |
| --- | ---: | ---: | ---: | ---: |
| Manuscrito B | 11 → 4 | 8 → 9 | 31.2% → 66.9% | 16.9% → 20.2% |
| Manuscrito A | 30 → 23 | 7 → 11 | 27.3% → 30.6% | 19.0% → 19.4% |

Essas taxas medem preenchimento, não acurácia. A redução de personagens inclui a separação de participantes locais; não significa que todos os removidos eram falsos. Os fatos totais incluem registros locais: apenas 3 no manuscrito B e 8 no manuscrito A foram classificados para persistência. O ganho de fatos reais foi modesto e a cobertura ainda é baixa. Não há base para declarar os critérios de sucesso integralmente atingidos em manuscritos reais.

A definição de evento elegível foi ampliada para incluir conhecimento, descoberta, transferência, criação, encontro e uso; por isso, as taxas de conversão não são diretamente comparáveis às da versão anterior. Fatos por cena não reiniciam a memória consolidada, mas uma referência ambígua não é resolvida apenas para aumentar essas taxas. Precisão de personagens/objetos e falsos fatos continuam sem avaliação anotada.

O ensaio por prefixos do mesmo manuscrito mediu o manuscrito A com 100/200/400/802 parágrafos em 0,188/0,386/0,849/1,662 s, sem carga inicial do modelo. É uma execução local com outros processos ativos, não benchmark calibrado. Não houve colapso de execução nesse ensaio; isso não comprova estabilidade de precisão.

Entrega: `build/robustez-semantica/Motor-final/fonte-0.9.5-9b9a561f.lumemotor` e respectivo ZIP. Evidências finais em `Validacao-manuscrito-b/`, `Validacao-manuscrito-a/`, `Casos-fontes/`, `Casos-motor/`, `baseline-0.9.4.json`, `desempenho-prefixos.json`, `testes-analisador.log` e `contrato-python.log`, sob `build/robustez-semantica/`. As pastas `Entrega/`, `manuscrito-b/`, `manuscrito-a/` e sufixadas `-final` registram iterações anteriores; use somente `Motor-final/` para instalar.

## Hotfix Lume 0.11.4 / FONTE 0.9.4 — 29/09/2026

- Build Release arm64 aprovado no Xcode 27.0; versão 0.11.4, build 16. A compilação exigiu execução autorizada fora do sandbox para as macros Swift.
- Motor final 0.9.4 reaproveitado da entrega já validada em `build/robustez-0.9.4/Pacote-final/`. Nenhuma regra Python foi alterada neste hotfix. A rodada anterior registrou 278 testes do analisador e paridade do manuscrito B/manuscrito A entre fontes e executável.
- 17 testes de pacotes/empacotamento aprovados: os 14 existentes e três novos para recusa de motor antigo, preservação de entrega existente e recusa de outro aplicativo. Contrato Swift aprovado para JSON, decisões, Unicode e execução Python. Sintaxe do comando de montagem validada.
- Inventário, assinatura local e diagnóstico aprovados no app completo. O ZIP foi extraído em outra pasta; assinatura, inventário, versão e diagnóstico foram verificados novamente. `release.json` registra versões, macOS mínimo 27.0, probe e SHA-256 do ZIP.
- O executável embutido analisou os dez cenários de `examples/Qualidade113`: sete alertas genéricos esperados e três controles sem alerta genérico. Os outros dois alertas são de repetição de palavra. Categorias conferidas por capítulo; SHA-256 do DOCX preservado.
- Documentação Markdown do projeto reduzida de 23 para 9 arquivos, incluindo licenças, guia visual e instruções do corpus preservados. Na raiz de `LumeMac`, de 14 para um README. Visão original preservada byte a byte; links locais conferidos. Os 20 documentos anteriores à consolidação estão no backup `documentacao-anterior.tar.gz` desta saída.

Entrega e evidências: `build/hotfix-0.11.4/Pacote/`, `validacao-hotfix.json`, `testes-pacotes.log`, `contrato-swift.log`, `xcodebuild.log`, `empacotamento.log` e `Analise-embutido/`. Intermediários de compilação e a extração temporária do ZIP podem ser recriados; não compõem a entrega.

Não houve instalação em Aplicativos nem inspeção visual da interface nativa. A seleção de um motor previamente instalado continua tendo prioridade; **Restaurar embutido** ativa o FONTE 0.9.4 desta entrega.

## Registro histórico — Lume 0.8 / FONTE 0.6.0

Verificações realizadas no ambiente Linux de desenvolvimento, com Python 3.12, spaCy 3.8.16 e pt_core_news_sm 3.8.0.

## Resultado observado

- **129 testes do analisador aprovados**, sem falhas ou testes ignorados: 99 testes existentes (ajustados onde o alcance de pontuação mudou) e 30 novos testes, vários com subcasos. Os novos testes cobrem variação de sujeitos/verbos, relações sintáticas, homógrafos, subjuntivos, diálogos, configuração e Unicode.
- **14 testes de pacotes aprovados**: integridade, instalação, reversão, recuperação, argumentos e preservação do motor anterior em falhas.
- Contrato Python/CLI aprovado: Unicode, caminhos especiais, SHA-256, preservação do DOCX, bloqueio de sobrescrita e relação temporal com sugestão, evidência e intervalo global.
- Diagnóstico `packaging/lume_engine.py --lume-probe` aprovado em execução Python: versão 0.6.0, protocolos v1 e amostras linguística/editorial/modular/temporal. O binário congelado não foi gerado neste ambiente.
- Testes DOM dos relatórios antigo, modular e temporal aprovados: filtros, contagens, sugestões, classificação, evidências, contexto, decisões e importação/exportação. Homógrafo ambíguo não recebe sugestão obrigatória.
- HTML temporal renderizado e inspecionado em Chromium, em larguras de 1280 e 390 pixels; sem transbordamento horizontal. Os testes visuais são do HTML, não da interface nativa.
- Sintaxe dos sete arquivos da aplicação Swift e do contrato Swift validada com tree-sitter-swift. Script de montagem validado com `bash -n`.
- Demonstrações geradas pela CLI: Mestre com 11 ocorrências (3/3/3/2) e Temporal com 9 (2 linguísticas, 7 morfossintáticas). Na amostra Temporal, duas ocorrências são dúvidas editoriais e sete são prováveis erros, sem erro confirmado. Auditoria declarada indisponível. Falas coloquiais e reticências normais não geram alertas das novas regras.

Não houve compilação com SDK Apple, execução do contrato Swift, empacotamento PyInstaller arm64, assinatura ou inspeção visual de `Lume.app`. A validação sintática não verifica tipos/API SwiftUI e não substitui a compilação no Mac. O script de montagem agora executa os testes Python, compila o app e compila/executa o contrato Swift antes de finalizar a entrega nativa.

Não houve avaliação do manuscrito A completo nem medição de precisão/recall em corpus anotado independente. Os exemplos e contraprovas são conhecidos durante o desenvolvimento. Há omissão conhecida quando o parser classifica “gira” como adjetivo; o teste documenta a abstenção, não a recuperação desse caso. O LanguageTool real não foi iniciado; o teste de sua integração permanece simulado. Os números de confiança são heurísticos e a cobertura é parcial.

## Confirmação no Mac M3

1. Execute `bash scripts/montar-lume.command`. Em caso de falha, conserve os logs em `build/`.
2. Abra o app gerado e confira FONTE 0.6.0; restaure o motor embutido se houver atualização antiga ativa.
3. Analise `examples/Mestre/Manuscrito-modular.docx` em Ambas/Passado com configuração padrão. Confira progresso sequencial, contagens, filtros, destaques e sugestões.
4. Abra **Etapas e alcance** e confirme que o Auditor Final está indisponível. Não deve haver certificado de revisão completa.
5. Teste uma janela mínima e uma ampliada, nos modos claro e escuro. Confira o botão de analisar, os seletores e a rolagem.
6. Registre e exporte uma decisão; reabra o relatório e confirme a restauração. Abra também os JSONs anteriores de `examples/Editorial`.
7. Interrompa uma análise e retome o relatório anterior. Nenhum resultado anterior deve aparecer como resultado da execução interrompida.
8. Importe uma configuração anterior com todas as regras desligadas; confirme que as regras acrescentadas também ficam desligadas.
9. Abra `examples/Temporal/Manuscrito-temporal.docx`, importe `examples/Temporal/Busca-temporal.json` e use Ambas/Passado. Confira as 9 ocorrências, incluindo “atravessamos” como dúvida sem substituição obrigatória. Restaure a configuração padrão depois.

## Reproduzir as verificações

```bash
cd fonte
.venv/bin/python -m unittest discover -s tests -v
cd ..
fonte/.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
fonte/.venv/bin/python tests/check_python_contract.py
```

Os três scripts DOM (`check_report_dom.cjs`, `check_modular_report_dom.cjs` e `check_temporal_report_dom.cjs`) em `tests/` requerem `jsdom` disponível ao Node. O contrato nativo requer `swiftc` e Foundation; o script de montagem o executa automaticamente no Mac.

## Atualização do diagnóstico — Lume 0.9 / FONTE 0.7.0

Verificada no Mac Apple Silicon com Xcode 27.0, Python 3.13, spaCy 3.8.16 e modelo pt_core_news_sm 3.8.0:

- 144 testes do analisador aprovados, incluindo os trechos do diagnóstico e a camada editorial contextual.
- 14 testes de pacotes aprovados.
- Contratos Python e Swift executados e aprovados: JSON, Unicode, decisões, execução e preservação de arquivos.
- Build Release arm64 aprovado no Xcode; a primeira tentativa no sandbox foi bloqueada nas macros Swift, e a compilação fora dessa restrição passou.
- Motor portátil 0.7.0 congelado, relocacionado e validado. Aplicativo montado e assinatura local verificada com `codesign --verify --deep --strict`.
- Teste no executável embutido final: quatro controles temporais preservados, sugestão “irá ser” → “seria”, vocativo, retomada de diálogo e gerundismo confirmados. Probe retorna `healthy: true` e versão 0.7.0.

Artefatos e logs em `build/diagnostico-0.9/`, incluindo `Lume.app`, `Lume.app.zip`, pacote `.lumemotor`, logs e `diagnostico-executavel.json`. Não houve instalação sobre outro aplicativo nem inspeção visual da interface nativa nesta atualização. Não houve medição em corpus independente; os limites e o trabalho futuro estão em [arquitetura e limites](ARQUITETURA.md).

## Memória narrativa — Lume 0.10 / FONTE 0.8.0

Verificada no Mac Apple Silicon, com Python 3.13, spaCy 3.8.16, pt_core_news_sm 3.8.0 e Xcode 27.0:

- 153 testes do analisador aprovados, incluindo nove novos testes com múltiplos controles negativos. A suíte foi executada com os fontes e novamente com o pacote instalado atualizado.
- 14 testes de pacotes aprovados. Contratos Python e Swift aprovados; o contrato Swift leu o novo relatório de memória, preservando compatibilidade com os campos antigos.
- Quatro testes DOM aprovados: relatório antigo, modular, temporal e memória narrativa. No novo HTML, painel, sete evidências de fatos, cinco ocorrências e filtros de módulo/classificação foram verificados.
- Build Release arm64 aprovado; montagem portátil 0.8.0 e probe do executável final com `healthy: true`. Assinatura local verificada por `codesign --verify --deep --strict` e inventário do motor embutido preservado.
- A demonstração analisada pelo motor embutido gerou duas cenas, sete fatos e cinco ocorrências. Cenas, banco e ocorrências do executável final são idênticos aos produzidos pelos fontes.
- Cache antigo de setuptools com timestamps futuros foi identificado e movido para backup antes da reinstalação. A montagem agora verifica a identidade dos arquivos instalados com os fontes.

Entrega em `build/estrutura-0.10/Lume.app` e `Lume.app.zip`; há também pacote independente `.lumemotor` e ZIP. Logs, cache anterior e relatório do executável estão na mesma pasta. Não houve instalação sobre outro aplicativo. A primeira tentativa de compilação/empacotamento foi bloqueada pelo sandbox; as execuções autorizadas fora dele passaram.

Não houve inspeção visual da interface nativa nem do HTML. A tentativa de abrir o HTML local no navegador integrado foi bloqueada pela política de URLs; a verificação do relatório foi feita por testes DOM locais. Os limites semânticos e os comparadores ainda ausentes estão descritos em [arquitetura e limites](ARQUITETURA.md); não houve avaliação em corpus independente.

## Correção do Editorial — Lume 0.10.1 / FONTE 0.8.1

Reproduzida a falha de intervalo invertido com `— Não vou — virou-se Helena.`: a regra gerava início 21 e fim 20. Corrigida a seleção do primeiro token lexical, preservando o validador estrito.

- 154 testes do analisador e 14 testes de pacotes aprovados; contrato Python aprovado. Pacote instalado comparado byte a byte com os fontes Python/HTML.
- Build Release arm64 aprovado. Assinatura local e inventário do motor embutido validados. Probe do aplicativo final: versão 0.8.1, `healthy: true`, incluindo a regressão do clítico.
- DOCX de regressão executado pelo motor embutido no modo Ambas: quatro ações pronominais reconhecidas com intervalos corretos, todas as etapas disponíveis concluídas, seis ocorrências no total e hash do DOCX preservado. Auditor permanece indisponível. A primeira execução de verificação usou o modo padrão Linguística; a execução completa usou Ambas explicitamente.
- Entrega em `build/correcao-0.10.1/Lume.app` e `Lume.app.zip`, com pacote `.lumemotor` independente, logs e DOCX/relatório de regressão.

O manuscrito específico que gerou o erro relatado não foi fornecido nesta correção; a reprodução usa exemplos mínimos que geravam exatamente a mesma falha de validação. Não houve inspeção visual da interface.

## Qualidade da memória — Lume 0.11 / FONTE 0.9.0

164 testes do analisador e 14 de pacotes passaram. Contratos Python/Swift, igualdade dos fontes instalados, build Release arm64, motor portátil, probe final, assinatura local e inventário aprovados. A amostra foi executada pelo motor embutido e confirmou os casos de local, referência, falante, habilidade e estado do pingente. Logs em `build/qualidade-0.11/`. PyInstaller e Swift exigiram execução autorizada fora do sandbox. Não houve inspeção visual nem teste DOM (jsdom ausente). Cobertura parcial e critérios ainda pendentes documentados em [arquitetura e limites](ARQUITETURA.md).

## Memória narrativa — Lume 0.11.1 / FONTE 0.9.1

- 194 testes do analisador aprovados (30 novos, com subcasos) e 14 testes de pacotes aprovados. Contrato Python aprovado; contrato Swift aprovado com o relatório antigo e com o relatório v0.11.1 produzido pelo executável final.
- Quatro testes DOM legados aprovados. O novo teste DOM confirma os sete fatos, nomes de valores, identidades distintas, evidências e filtro global no HTML final. jsdom encontrado no ambiente de testes local `/private/tmp/lume-dom-check/node_modules`.
- Fontes instalados idênticos byte a byte aos arquivos Python/HTML do projeto. Build Xcode Release arm64 aprovado. Motor final empacotado após os últimos controles de oração/futuro; probe com versão 0.9.1 e `healthy: true`, incluindo fogo/gelo, falante pronominal e separação de objetos.
- `Lume.app` e ZIP montados; assinatura local verificada e inventário do motor embutido preservado. Cenas, banco, diagnóstico e ocorrências do motor final são idênticos aos da execução pelos fontes na amostra. Hash do DOCX confirmado após análise.
- Amostra `examples/Memoria111`: sete fatos, oito eventos semânticos, conversão de 87,5%, referências e falante resolvidos, um conflito global (fogo/gelo). Esses números valem somente para a amostra conhecida, não medem precisão geral. Nenhuma instalação sobre outro aplicativo e nenhuma inspeção visual nativa foram realizadas.

Entrega em `build/qualidade-0.11.1/Lume.app` e `Lume.app.zip`; motor final em `motor-final/`, relatório final em `Relatorio/` e logs na pasta de saída. A primeira montagem intermediária foi preservada separadamente. O sandbox exigiu as autorizações de compilação/empacotamento já aplicadas na versão anterior.

## Coerência genérica — Lume 0.11.2 / FONTE 0.9.2

- 209 testes do analisador e 14 testes de pacotes aprovados. Corpus A obrigatório, exemplos adicionais, contraprovas, substituições de nomes/objetos/locais/parentesco e oito contextos de gênero cobertos.
- Contrato Python aprovado, incluindo preservação do DOCX, Unicode e bloqueio de sobrescrita. Contrato Swift aprovado com o relatório genérico. Build Release arm64 aprovado.
- Corpus DOCX obrigatório produziu sete alertas genéricos nos casos positivos e nenhum nos quatro negativos. Fatos, cenas e ocorrências do executável foram comparados aos fontes.
- Motor portátil com probe `healthy: true`; aplicativo com assinatura local e inventário verificados. Artefatos em `build/generica-0.11.2/`.
- Sintaxe JavaScript do relatório gerado validada. Não houve teste DOM (jsdom indisponível) nem inspeção visual da interface nativa. PyInstaller e compiladores Apple exigiram autorização fora do sandbox para seus caches/macros.

Cobertura heurística parcial; os controles foram escritos durante o desenvolvimento. Não houve medição em corpus independente. Limites em [arquitetura e limites](ARQUITETURA.md).

## Qualidade dos fatos — Lume 0.11.3 / FONTE 0.9.3

- **245 testes do analisador e 14 testes de pacotes aprovados.** São 36 testes novos de qualidade (com subcasos), verificando entidades, sujeitos/objetos/pacientes, hipóteses, fatos, estado final, conhecimento, tempo e alertas.
- Contratos Python e Swift aprovados. Build Release arm64 aprovado. Fontes Python/HTML instalados conferidos byte a byte com o workspace.
- Demonstração de dez cenários executada nos fontes e no motor final embutido: sete ocorrências genéricas esperadas, nenhum alerta genérico nos três controles. Fatos, cenas e ocorrências idênticos; SHA-256 e bytes do DOCX preservados. Nenhum desses alertas é erro confirmado.
- Probe do executável final com versão 0.9.3 e `healthy: true`, incluindo transferência passiva e controle contra quantidade confundida com idade. Assinatura local do app e inventário do motor verificados.
- Aplicativo, ZIP, motor independente, relatórios, logs e `validacao-final.json` em `build/qualidade-0.11.3/`. O empacotamento e os compiladores Apple foram executados com autorização para seus caches/macros fora do sandbox.

Não houve inspeção visual da interface nativa ou teste DOM nesta rodada. Cobertura parcial e testes de desenvolvimento, sem avaliação independente de precisão/recall. Detalhes em [arquitetura e limites](ARQUITETURA.md).

## Robustez em manuscritos reais — FONTE 0.9.4

- 278 testes do analisador (33 novos) e 14 testes de pacotes aprovados. Contratos Python e Swift aprovados, inclusive leitura do relatório novo do manuscrito A. Sintaxe JavaScript do HTML validada e fontes instalados conferidos byte a byte.
- Motor portátil final com probe `healthy: true`, inventário validado e teste após relocação. O empacotamento exigiu acesso autorizado ao cache externo do PyInstaller. Não foi necessária recompilação da interface para instalar este motor compatível.
- Os dois DOCX coincidem com os hashes dos relatórios fornecidos e permanecem intactos. Os índices Unicode foram preservados. Cenas, fatos, eventos, referências, métricas e ocorrências do motor final são idênticos aos dos fontes.
- Manuscrito B: 41 → 11 registros de personagens; 0 → 15 falantes identificados; 8 fatos no total, com remoção dos conteúdos `tells` falsos e recuperação do celular desligado. Celulares, bolsas e portas dos contextos auditados têm IDs distintos.
- Manuscrito A: 96 → 30 registros de personagens; 62 → 96 falantes identificados; 2 → 7 fatos. Recuperado um falante nomeado, chegada em primeira pessoa e abertura de porta. Controladas associações falsas de localização com o ano escolar e oração de outro sujeito.
- Os denominadores de referências e falas mudaram por inclusão de pronomes objeto e exclusão de pensamentos explícitos. Os números medem cobertura nos casos conhecidos; não medem precisão independente. Permanecem omissões, identidades provisórias e diálogos sem falante. Nenhuma inspeção visual nativa foi realizada.

Entrega final: `build/robustez-0.9.4/Pacote-final/fonte-0.9.4-f01ce613.lumemotor.zip`. Relatórios e paridade: `build/robustez-0.9.4/Validacao-final/`. Regressões reais selecionadas: `verificacao-casos-reais.json`. Montagens anteriores na pasta são intermediárias preservadas. O motor ativo do aplicativo não foi substituído automaticamente.
