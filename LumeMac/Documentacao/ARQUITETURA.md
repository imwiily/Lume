# Arquitetura e limites — Lume 0.11.4 / FONTE 0.9.5

Os manuscritos são somente lidos. A sequência Linguístico → Morfossintático → Editorial → Coerência Global usa uma captura imutável do documento. Antes de gravar o relatório, a CLI confere novamente o SHA-256 do DOCX. Falha numa etapa impede as seguintes. O Auditor Final continua indisponível.

## Organização

| Local | Responsabilidade |
| --- | --- |
| `Lume/` | Interface SwiftUI, relatórios, decisões e seleção do motor |
| `Analisador/fonte/reader.py`, `contracts.py`, `pipeline.py` | Leitura DOCX, índices Unicode, contratos e execução sequencial |
| `linguistic.py`, `analysis.py`, `temporal.py`, `editorial/` | Regras linguísticas, temporais e editoriais |
| `grammar.py` | Crase, homófonos, concordância, regência e vírgula entre sujeito e verbo (etapa Morfossintática) |
| `languagetool.py` | Corretor gramatical LanguageTool local: filtros, falas e servidor embutido |
| `coerencia_ia.py` | Coerência com IA: projeto incremental do Coerencia (`../LumeCoerencia/`) na etapa Coerência global |
| `narrative*.py`, `semantic*.py`, `generic_facts.py` | Cenas, identidades, falantes, referências, eventos, fatos e comparações |
| `Engine/` | Entrada portátil, inventário, instalação atômica e reversão |
| `Scripts/build_engine.py` | Motor PyInstaller com teste após relocação |
| `Scripts/package_app.py` | Inclusão do motor, assinatura do app, diagnóstico e ZIP |
| `Scripts/validate_real_memory.py` | Comparação de manuscrito/relatório anterior com fontes e executável |
| `Scripts/preparar_languagetool.py` | LanguageTool fixado por SHA-256, sem dados grandes de outros idiomas, com Java mínimo (jlink) |
| `Scripts/avaliar_deteccao.py` | Avaliação cega da detecção no corpus anotado `Analisador/tests/corpus/deteccao/` |

Caminhos de módulos Python são relativos a `Analisador/fonte/`; os demais, a `LumeMac/`.

## Pacotes e compatibilidade

Pacote, API, relatório e decisões usam schema 1; memória narrativa usa schema 2. As extensões são aditivas. `manifest.json` declara versão, arquitetura, macOS mínimo, executável e inventário SHA-256. Links simbólicos devem resolver dentro do pacote. A assinatura atual é local (ad hoc); o hash assegura integridade, não identidade do publicador.

O app procura `Contents/Resources/Engine.lumemotor`. Um motor instalado só é usado se for de versão mais nova que o embutido; com versão igual ou anterior, o app usa o embutido e avisa. **Restaurar embutido** seleciona o motor incluído nesta versão. O app conserva `br.fonte.editorial` e `~/Library/Application Support/FONTE/`: relatórios, decisões e configuração de motores permanecem compatíveis. IDs/evidências novos não recebem decisões antigas por aproximação.

## Contrato de ocorrências

Os campos anteriores continuam presentes, inclusive `id`, `text`, `paragraph`, `start`, `end`, `category`, `priority`, `reason`, `source`, `layer`, evidências e contexto.

| Campo novo | Significado |
| --- | --- |
| `module` | `linguistic`, `morphosyntactic`, `editorial`, `global_coherence` ou `audit` |
| `category_code` | Identificador da categoria/regra, independente do rótulo em português |
| `severity` | `confirmed_error`, `probable_error`, `editorial_attention`, `possible_inconsistency` ou `author_query` |
| `confidence_score` | Força do indício de 0 a 1; valor heurístico, não probabilidade calibrada |
| `range` | Início inclusivo e fim exclusivo na projeção global de texto |
| `excerpt` | Substring exata sinalizada no original |
| `message` | Mesma explicação de `reason`, mantida para compatibilidade |
| `suggestion` | Substituição proposta somente para o trecho destacado; `null` quando não há solução única, string vazia para remoção |

`confidence` permanece uma string (`alta`, `média`, `baixa`) por compatibilidade. O número fica em `confidence_score`. A extensão é marcada por `metadata.occurrence_schema_version = 1`; `schema_version` do relatório continua em 1.

`start`/`end` antigos continuam relativos ao parágrafo, em pontos de código Unicode Python. `range` é relativo à concatenação dos parágrafos não vazios lidos, incluindo títulos e tabelas, unidos por um único `\n`. Não são offsets no XML do Word, páginas, grafemas ou unidades UTF-16. `metadata.text_index` registra separador, unidade, tamanho, hash e intervalos dos parágrafos. Emoji e acentos combinados são preservados.

A classificação é do motor. A decisão humana permanece independente. Falsos positivos não criam exceções automáticas e as sugestões não alteram texto.

## Eventos e etapas

Cada evento de stdout tem prefixo `LUME_PROGRESS ` seguido de um objeto JSON com `module`, `title`, `state`, `finding_count`, `coverage` e `detail`; eventos concluídos acrescentam `duration_ms`.

- `running`: etapa iniciada.
- `completed`: as regras selecionadas disponíveis terminaram, sem afirmar cobertura completa.
- `skipped`: nenhuma regra aplicável foi selecionada naquele modo/configuração.
- `failed`: execução interrompida por exceção.
- `not_implemented`: etapa ainda indisponível; usado pelo Auditor Final.

As contagens correspondem aos alertas efetivamente emitidos por cada etapa. A remoção de IDs exatamente repetidos é uma validação técnica; **não é a auditoria editorial da visão**. Alertas distintos sobre o mesmo trecho não são descartados por proximidade.

## Cobertura atual

Linguístico cobre padrões determinísticos, pontuação, repetições e LanguageTool local opcional. Morfossintático cobre tempos, relações entre orações e acentuação contextual. Marcadores temporais, subjuntivo, imperativo, falas e pensamentos têm proteções específicas; isso não equivale a análise gramatical completa. Formas como “caminhamos” podem permanecer ambíguas.

Editorial usa contexto local, atribuição de falas e referentes, com abstenção quando há candidatos concorrentes. Coerência Global compara fatos com identidade, evidência e escopo: atributos, objetos, posse, conhecimento, presença, relações e cronologia. Transições reconhecidas evitam conflitos indevidos. Histórico e estado atual seguem a ordem textual, sem reconstrução completa de flashbacks. Suspeitas narrativas não viram erros confirmados nem correções automáticas.

### Robustez incorporada no FONTE 0.9.4


- Títulos, créditos e estilos de capítulo são reconhecidos antes da extração. O prólogo após os créditos continua sendo analisado. Parágrafos e posições Unicode permanecem estáveis.
- Interjeições, formas verbais e fragmentos nominais deixam de ser promovidos indiscriminadamente a personagens. Descrições humanas podem representar participantes ainda sem nome. Títulos como “Professora Maria” usam a mesma identidade de “Maria”.
- Cenas não são cortadas automaticamente a cada 12 parágrafos. Cortes explícitos e mudanças de capítulo continuam encerrando o contexto local. Referências consultam antecedentes recentes e preservam ambiguidades.
- Diálogos entre aspas, verbos antes/depois do nome, descrições de falantes e primeira pessoa têm cobertura ampliada. Pensamentos explicitamente marcados são separados da contagem de falas.
- A primeira pessoa recebe uma identidade provisória local. Formas verbais frequentes recuperam sua leitura mesmo quando o modelo as etiqueta como nomes. Referências a objetos têm controles próprios.
- Gestos depois de “disse” não se tornam conteúdo comunicado. Ator ausente não é substituído pelo próprio objeto. Eventos exportam papéis semânticos; fatos preservam sua evidência e a ligação com eventos de origem.
- Portas e janelas usam qualificadores e contexto espacial. Celulares e bolsas usam pistas de manuseio e contexto, inclusive em gerúndios. Transferências explícitas preservam o mesmo item. Comparações hipotéticas não introduzem objetos físicos.
- Idades aceitam numerais compostos por extenso. Conhecimento negativo tem cobertura ampliada. Idade declarada por falante identificado fica marcada como declaração, sem virar automaticamente fato do mundo narrado.
- Estados como abertura, fechamento e desligamento passam a ser preservados em mais construções, inclusive com primeira pessoa e pronome objeto. A presença em cena recebe também evidências de eventos e falas.
- A confiança dos fatos derivados incorpora dependências de referência e identidade. Comparadores excluem fatos de baixa confiança e declarações sem escopo adequado.
- As métricas explicitam denominadores. A conversão antiga é mantida por compatibilidade; uma medida adicional considera eventos originais elegíveis. Taxa de acerto e taxa de falsos fatos continuam sem valor até existir anotação humana.

## Limites da memória narrativa


Não há compreensão completa do enredo. Atribuições ambíguas permanecem sem resolução; grupos, personagens sem nome e narradores provisórios podem ocupar registros próprios. A ligação entre apelidos, sobrenomes, narradores e nomes completos ainda é parcial. Contextos de sonho, metáfora e mudança de ponto de vista continuam exigindo revisão humana. A identidade de objetos é uma hipótese apoiada nas pistas disponíveis, não uma garantia.

O extrator ainda deixa passar muitos fatos e turnos. A extração de idade a partir de fala exige falante identificado; por isso não se deve presumir que a idade da doutora em Hikari tenha sido recuperada. Estados e fatos de personagens com nome persistem no banco, mas identidades provisórias não são unidas automaticamente através de mudanças de foco.

Os dois manuscritos e os testes foram usados no desenvolvimento. Não constituem avaliação independente de precisão ou prova de estabilidade em todos os comprimentos. Não houve inspeção visual da interface nativa. O Auditor Final e a taxa de comparação global permanecem indisponíveis.


## CLI e configuração

```sh
Analisador/.venv/bin/python -m fonte revisar manuscrito.docx --modo ambas --tempo passado --saida Saida/revisao-nova
```

`--tempo passado|presente` informa o tempo da narração (padrão: passado); não há mais detecção automática, que se mostrou pouco confiável. `--config busca.json` recebe a configuração exportada pelo Lume. `--original original.docx` acrescenta comparação editorial com uma versão anterior. A saída deve ser nova. Nenhum desses argumentos autoriza alterar o manuscrito. O modo geral limita as camadas executadas; configurações antigas com tudo desligado permanecem desligadas.

`--languagetool` ativa o corretor gramatical local. Se o motor tiver o corretor embutido (`languagetool/` ao lado de `runtime/` no pacote, `Analisador/.languagetool` nos fontes ou `FONTE_LANGUAGETOOL`), a CLI inicia o servidor numa porta livre de 127.0.0.1, com o Java do pacote, e o encerra ao terminar. Sem corretor embutido, ou com `--porta-lt`, usa um servidor já ativo (padrão 8081). `metadata.languagetool_origem` registra `embutido` ou `externo`. Sem a flag, a CLI não usa o corretor; o app a envia quando **Corretor gramatical local** está ligado, o que agora é o padrão.

O texto das falas é enviado ao corretor. Regras de estilo e registro ficam fora para não formalizar a voz. Maiúscula após travessão de inciso e grafia de nomes próprios (palavras com inicial maiúscula fora do início de frase, mais `ignored_names`) são descartadas; itálicos marcados como pensamento não recebem alertas de grafia. Um alerta do corretor sobre o mesmo trecho de uma regra FONTE é omitido. As regras de `grammar.py` revisam crase e homófonos também em falas; concordância, regência e vírgula entre sujeito e verbo só na narração. Regência é `editorial_attention`, porque a forma com ‘em’ é corrente no português brasileiro.

Consulte o [histórico](HISTORICO.md) para evolução dos contratos, a [validação](VALIDACAO.md) para evidências e a [visão](VISAO.md) para objetivos ainda não integralmente implementados.

## Coerência com IA

`revisar --coerencia-ia --coerencia-projeto P [--coerencia-modelo M] [--coerencia-teto T]` roda
o projeto incremental do Coerencia na etapa Coerência global e desliga, nessa análise, a
memória narrativa heurística. Pendências abertas viram ocorrências `rule=coerencia_ia`,
`severity=possible_inconsistency`: o trecho posterior é a ocorrência e o anterior vai em
`related`; o ID inclui as duas evidências. `metadata.coerencia_ia` registra capítulos
enviados, tokens, custo e interrupção por teto. Ao atingir o teto, capítulos lidos ficam
salvos e o restante segue na próxima análise (aviso no relatório). `coerencia-estimar`
devolve uma linha `LUME_ESTIMATIVA {json}` com capítulos a enviar e custo estimado, sem
chamar a API. A chave vem de `ANTHROPIC_API_KEY` ou das Chaves do macOS.

## Persistência seletiva no motor 0.9.5

`Scene.participants` conserva identidades locais com evidência, inclusive participantes sem nome. Na consolidação, `identity_tier` e `promotion_basis` distinguem personagens canônicos dos participantes temporários. O banco mantém ambos em coleções distintas; a presença em cena não exige promoção canônica. Não se associa automaticamente o narrador de uma cena ao narrador de outra quando a identidade não está estabelecida.

Cada fato mantém evento de origem, cadeia de confiança, entidade, cena, capítulo, trecho original, polaridade, inferência e tempo conhecido. `persistence` indica se a informação é elegível para memória entre cenas ou apenas registro local. `valid_from: null` representa tempo desconhecido. Atributos declarados em diálogo permanecem `reported` e não atestam o mundo narrado. `knowledge_history` conserva afirmações e negações; `knowledge_state` aponta para a última evidência qualificada por assunto. Descoberta não cria retroativamente fatos de desconhecimento.

A memória é consolidada por identidade ao longo do documento, sem carregar automaticamente a presença ou o referente local de uma cena para outra. Estados físicos podem sustentar atenção editorial entre cenas; cura explícita encerra a restrição reconhecida. Objetos genéricos de cenas diferentes ficam separados salvo pista suficiente de continuidade. Comparações continuam heurísticas: ausência de transição não equivale a erro confirmado.

Limites: não há resolução completa de elipses, homônimos, conhecimento implícito, todas as profissões/cargos/atributos civis nem cronologia absoluta sem âncora. O classificador usa o parser e padrões limitados de português; a precisão em manuscritos reais ainda requer corpus anotado. `fact_persistence_rate` mede a fração de fatos elegíveis para persistência, não a correção nem o uso efetivo entre cenas. `global_comparison_rate`, `false_fact_rate` e precisões canônicas permanecem nulos quando não avaliados.
