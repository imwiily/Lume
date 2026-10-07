# Arquitetura e limites

Os manuscritos são somente lidos. A sequência Linguístico → Morfossintático → Editorial → Coerência Global usa uma captura imutável do documento. Antes de gravar o relatório, a CLI confere novamente o SHA-256 do arquivo (DOCX ou Pages). Falha numa etapa impede as seguintes; a falha da Auditoria final, a última etapa, interrompe só ela. A Auditoria final com IA é opcional e desligada por padrão ([detalhes](#auditoria-final-com-ia)).

## Organização

| Local | Responsabilidade |
| --- | --- |
| `Lume/` | Interface SwiftUI, relatórios, decisões e seleção do motor |
| `fonte/fonte/reader.py`, `pages.py`, `contracts.py`, `pipeline.py` | Leitura de DOCX e Pages, índices Unicode, contratos e execução sequencial |
| `linguistic.py`, `analysis.py`, `temporal.py`, `editorial/` | Regras linguísticas, temporais e editoriais |
| `grammar.py` | Crase, homófonos, concordância, regência, vírgula entre sujeito e verbo, correlação de tempos, frase cortada e locuções (etapa Morfossintática) |
| `languagetool.py` | Corretor gramatical LanguageTool local: filtros, falas e servidor embutido |
| `coerencia_ia.py` | Coerência com IA: projeto incremental do Coerencia (`coerencia/`) na etapa Coerência global |
| `packaging/` | Entrada portátil, inventário, instalação atômica e reversão |
| `scripts/build_engine.py` | Motor PyInstaller com teste após relocação |
| `scripts/package_app.py` | Inclusão do motor, assinatura do app, diagnóstico e ZIP |
| `scripts/validate_real_memory.py` | Comparação de manuscrito/relatório anterior com fontes e executável |
| `scripts/preparar_languagetool.py` | LanguageTool fixado por SHA-256, sem dados grandes de outros idiomas, com Java mínimo (jlink) |
| `scripts/avaliar_deteccao.py` | Avaliação cega da detecção no corpus anotado `fonte/tests/corpus/deteccao/` |

Caminhos de módulos Python são relativos a `fonte/fonte/`; os demais, à raiz do repositório.

## Documentos do Pages

`pages.py` lê o `.pages` diretamente, sem abrir o Pages e sem dependências novas: o arquivo é
um ZIP com `Index/*.iwa` (blocos Snappy com mensagens protobuf). São lidos o texto do corpo, o
nome do estilo de cada parágrafo (variações sem nome usam o do estilo de origem) e o itálico
(estilo de caractere, com herança, ou estilo do parágrafo). `reader.py` aplica aos parágrafos
as mesmas regras de capítulos e front matter do DOCX; `read_manuscript` escolhe o leitor pela
extensão. O relatório não muda de formato: `document` traz o nome do arquivo e `sha256`, o
hash do `.pages`.

Limites: o formato não é documentado pela Apple e pode mudar entre versões do Pages (leitura
conferida com o Pages 15.3). Tabelas, caixas de texto, cabeçalhos, rodapés, notas e
comentários não são analisados; o nível de tópico não é lido (títulos vêm do nome do estilo
ou do texto). Documento com senha, salvo como pacote (pasta) ou do Pages ’09 é recusado com
orientação. O aviso de alterações controladas depende de campos não conferidos com um
documento real; texto excluído com o controle ligado pode ser lido como texto.

## Correção no manuscrito (Pages)

A correção é pedida pelo autor em cada alerta e vale só para `.pages`; o DOCX continua
somente leitura. `ReviewStore.applyCorrection` segue esta ordem:

1. confere que o SHA-256 do arquivo é o do relatório (ou o da última correção);
2. `ManuscriptEditor.plan` traduz o trecho do relatório para o parágrafo atual, somando as
   correções já gravadas nele; trecho que toca uma correção anterior é recusado;
3. na primeira correção, confirma com o autor e copia o arquivo para
   `Copias/<sha256 do relatório>/`;
4. o Pages (AppleScript via `osascript`) confere o texto do parágrafo e troca o trecho, um
   caractere por vez, preservando a formatação; documento aberto com alterações não salvas
   ou parágrafo diferente do esperado interrompem sem gravar;
5. o motor (`conferir-edicao`, só leitura) confirma que apenas aquele parágrafo mudou e
   devolve `LUME_EDICAO {"sha256": …}`; se falhar, o arquivo anterior é restaurado;
6. `Edicoes/<sha256 do relatório>.json` registra origem, hash atual, cópia e correções.

O relatório aberto não é reescrito: ele continua mostrando o texto analisado. Ao analisar de
novo o arquivo corrigido, os alertas de ID idêntico (mesmo parágrafo, texto, regra e trecho)
recebem a decisão anterior; nada é herdado por aproximação. A análise continua sendo refeita
por inteiro. Exige o Pages instalado e a permissão de Automação do macOS.

## Pacotes e compatibilidade

Pacote, API, relatório e decisões usam schema 1. As extensões são aditivas. `manifest.json` declara versão, arquitetura, macOS mínimo, executável e inventário SHA-256. Links simbólicos devem resolver dentro do pacote. A assinatura atual é local (ad hoc); o hash assegura integridade, não identidade do publicador.

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
- `failed`: execução interrompida por exceção. Na Auditoria final, a falha (API, teto, recusa) fica só nela: as demais etapas são mantidas no relatório, com um aviso.
- `not_implemented`: etapa indisponível. Era o estado do Auditor Final até o FONTE 1.3.1; relatórios antigos com ele continuam lidos.

As contagens correspondem aos alertas efetivamente emitidos por cada etapa. A remoção de IDs exatamente repetidos é uma validação técnica; **não é a auditoria editorial da visão**. Alertas distintos sobre o mesmo trecho não são descartados por proximidade.

## Cobertura atual

Linguístico cobre padrões determinísticos, pontuação, repetições e o LanguageTool embutido
(ortografia e gramática, também em falas). Morfossintático cobre o tempo verbal da narração
informado, relações entre orações, acentuação contextual e as regras de `grammar.py` (crase,
homófonos, concordância, regência, vírgula entre sujeito e verbo, correlação de tempos, frase
cortada e locuções). Editorial usa contexto
local: diálogos, repetições, gerundismo e referentes próximos, com abstenção quando há
candidatos concorrentes. Coerência Global cobre variações de nomes e prazos e, com a
Coerência com IA ligada, contradições narrativas. Suspeitas não viram erros confirmados nem
correções automáticas. Nada disso equivale a uma revisão gramatical completa.

`done`, `total` e `unit` opcionais nos eventos `running` indicam o andamento dentro da etapa
(parágrafos do corretor, cenas da Coerência com IA).

## Destino, impedimento e encerramento

Plano: [`.agent/plans/encerramento-editorial.md`](../.agent/plans/encerramento-editorial.md).
Princípio: o Lume interrompe o editor só com evidência suficiente, e a revisão precisa poder
terminar ([visão](visao.md#ocorrência-pendência-e-encerramento)).

- **Severidade e destino são coisas diferentes.** A severidade diz que tipo de problema é. O
  destino, aplicado pela política depois das etapas, diz o que o editor faz com ele:
  - `diagnostico`: fora de `findings`; numa lista própria do relatório, só para medir o motor;
  - `informacao`: visível de forma recolhida; não conta nem pede decisão;
  - `pendencia`: entra na fila e pede decisão.
- **Impeditivo** (`impeditivo: true`): pendência que precisa de decisão antes de encerrar. Exige
  precisão real ≥ 90% em ≥ 20 decisões, natureza objetiva e severidade de erro. Classes
  editoriais, narrativas, de repetição, referência, estilo ou continuidade nunca são impeditivas.
- **Política:** `fonte/fonte/data/politica.json` (aplicada por `fonte/fonte/politica.py`), por
  classe (regra × confiança), com as medições de `scripts/medir_precisao.py`. A confiança é
  evidência auxiliar: com 20 decisões ou mais, os dados decidem. Classe medida com menos de 50% de
  erro real vai para informação (critério de não-interrupção, não de qualidade); sem medição,
  confiança baixa vai para informação e as demais para pendência. Pendência não afirma que a regra
  é confiável. Classe nova entra como informação ou diagnóstico.
- **Relatório:** cada ocorrência leva `destino` e `impeditivo`; `metadata` leva `politica_versao`,
  `destinos` (contagem), `impeditivos` e `diagnostico` (lista fora de `findings`).
- **Política v1 (07/10/2026):** nenhuma classe é impeditiva. As duas que passam de 90% em 20
  decisões (tempo verbal da narração, diálogo contextual) são editoriais.
- **Compatibilidade:** os campos se somam ao contrato. Relatório antigo, sem destino, é lido
  como hoje: tudo pendência, nada impeditivo. Os IDs não mudam, então as decisões continuam.
- **Encerramento:** o app oferece **Encerrar revisão** quando nenhum impeditivo está sem decisão
  e registra observações e pendências abertas, data, versão do motor e versão da política. O
  estado se chama “Revisão concluída”, nunca “sem erros”.

- **Mesa (app):** duas partes, **Pendências** (padrão) e **Observações**. Os impeditivos ficam
  destacados no topo das pendências, com a contagem sempre visível, mesmo quando é zero. O
  diagnóstico fica em Etapas e alcance, fora do fluxo editorial. **Encerrar revisão** grava
  `Encerramentos/<sha256>.json` (`encerrada_em`, `versao_motor`, `versao_politica`,
  `pendencias_abertas`, `observacoes_abertas`, `impeditivos_abertos`). O registro vale para o mesmo
  texto e a mesma política. A decisão **Corrigido** é gravada pela correção no Pages.

## CLI e configuração

```sh
fonte/.venv/bin/python -m fonte revisar manuscrito.docx --modo ambas --tempo passado --saida build/revisao-nova
```

`--tempo passado|presente` informa o tempo da narração (padrão: passado); não há mais detecção automática, que se mostrou pouco confiável. `--config busca.json` recebe a configuração exportada pelo Lume. `--original original.docx` acrescenta comparação editorial com uma versão anterior. A saída deve ser nova. Nenhum desses argumentos autoriza alterar o manuscrito. O modo geral limita as camadas executadas; configurações antigas com tudo desligado permanecem desligadas.

`--languagetool` ativa o corretor gramatical local. Se o motor tiver o corretor embutido (`languagetool/` ao lado de `runtime/` no pacote, `fonte/.languagetool` nos fontes ou `FONTE_LANGUAGETOOL`), a CLI inicia o servidor numa porta livre de 127.0.0.1, com o Java do pacote, e o encerra ao terminar. Sem corretor embutido, ou com `--porta-lt`, usa um servidor já ativo (padrão 8081). `metadata.languagetool_origem` registra `embutido` ou `externo`. Sem a flag, a CLI não usa o corretor; o app a envia quando **Corretor gramatical local** está ligado, o que agora é o padrão.

O texto das falas é enviado ao corretor. Regras de estilo e registro ficam fora para não formalizar a voz. Maiúscula após travessão de inciso e grafia de nomes próprios (palavras com inicial maiúscula fora do início de frase, mais `ignored_names`) são descartadas; itálicos marcados como pensamento não recebem alertas de grafia. Um alerta do corretor sobre o mesmo trecho de uma regra FONTE é omitido. As regras de `grammar.py` revisam crase, homófonos, correlação de tempos e frase cortada também em falas; concordância, regência, vírgula entre sujeito e verbo e locuções só na narração. Regência é `editorial_attention`, porque a forma com ‘em’ é corrente no português brasileiro.

Consulte o [histórico](../CHANGELOG.md) para evolução dos contratos, a [validação](validacao.md) para evidências e a [visão](visao.md) para objetivos ainda não integralmente implementados.

## Coerência com IA

`revisar --coerencia-ia --coerencia-projeto P [--coerencia-modelo M] [--coerencia-teto T]` roda
o projeto incremental do Coerencia na etapa Coerência global. Pendências abertas viram ocorrências `rule=coerencia_ia`,
`severity=possible_inconsistency`: o trecho posterior é a ocorrência e o anterior vai em
`related`; o ID inclui as duas evidências. `metadata.coerencia_ia` registra capítulos
enviados, tokens, custo e interrupção por teto. Ao atingir o teto, capítulos lidos ficam
salvos e o restante segue na próxima análise (aviso no relatório). `coerencia-estimar`
devolve uma linha `LUME_ESTIMATIVA {json}` com capítulos a enviar e custo estimado, sem
chamar a API. A chave vem de `ANTHROPIC_API_KEY` ou das Chaves do macOS.

## Auditoria final com IA

Papel: **controle de qualidade do Lume**, não uma segunda camada de revisão editorial. Pela
política (v2):
- confiança baixa vai sempre para diagnóstico;
- as categorias de norma (ortografia, concordância, crase, regência) começam como observação;
- as categorias experimentais (pontuação, tempo verbal, estrutura, repetição, diálogo, referência,
  continuidade) começam no diagnóstico;
- a promoção a pendência depende só de dados medidos;
- nenhum achado da Auditoria é impeditivo por conta própria.

O prompt não mudou: nada é reenviado. O número de achados novos não mede maturidade; mede-se
quantos achados promovidos se confirmaram como erro real.

`revisar --auditoria-ia --auditoria-projeto P [--auditoria-modelo M] [--auditoria-teto T]
[--auditoria-esforco E]` roda a quinta etapa (`audit`). Desligada por padrão, porque custa
dinheiro; modelo padrão `claude-opus-5-5` e teto padrão US$ 1,00.

- Cada capítulo (ou janela de até 40 mil caracteres, com 2 parágrafos anteriores só como
  contexto) vai ao Claude com os alertas já emitidos nele. O pedido usa um prompt fixo e
  genérico e uma resposta em esquema estrito com 11 categorias.
- Cada trecho devolvido é conferido no parágrafo. O que estiver fora do trecho enviado, não
  existir, cair fora do escopo (regra desligada, tempo verbal fora de `tense_scopes`),
  sobrepor um alerta existente ou repetir outro achado é descartado e contado.
- Os achados viram ocorrências `rule=auditoria_ia`, `module=audit`, nunca
  `confirmed_error` e nunca com confiança `alta`. `metadata.auditoria_ia` registra trechos,
  pedidos, reaproveitados, achados por categoria, descartes por motivo, custo e interrupção
  por teto.
- `P/auditoria.json` guarda cada pedido concluído, identificado pelo texto (do trecho e do
  contexto), modelo, esforço, tempo e versão do prompt. Trechos iguais não são reenviados; a
  conferência roda de novo contra os alertas atuais.
- Ao atingir o teto, o que já foi auditado fica guardado e o restante segue na próxima
  análise. Outros erros da API interrompem só a etapa `audit`, e o relatório das demais
  etapas é mantido.
- `auditoria-estimar ARQUIVO --auditoria-projeto P [--tempo T]` devolve uma linha
  `LUME_ESTIMATIVA_AUDITORIA {json}` com os trechos a enviar e o custo estimado, sem rede. A
  estimativa foi calibrada numa medição curta com o Opus 5.5: o prompt fixo e o esquema somam
  cerca de 1.440 tokens por pedido e são lidos do cache a partir do segundo pedido. Para
  capítulos longos, a estimativa ainda é aproximada.

No app, a opção fica no painel “Auditoria final” da tela inicial, com modelo, teto e a mesma
chave da Coerência. Antes de qualquer envio, o app roda as estimativas de cada recurso ligado
(`coerencia-estimar` e `auditoria-estimar`) e mostra uma única confirmação com os trechos e o
custo de cada um. A chave vai só no ambiente do processo. Plano:
[auditor-final](../.agent/plans/auditor-final.md).


## Memória narrativa heurística (removida)

Até 29/09/2026 o FONTE tinha uma memória narrativa local (`semantic*.py`,
`narrative*.py`, `generic_facts.py`, `fact_*.py`): cenas, identidades, eventos, banco de
fatos e comparações. Ela foi removida por não produzir alertas úteis (0 de 11
contradições nos textos de teste; nenhum alerta nos manuscritos A e B). Relatórios antigos
com `scenes`, `fact_bank` e `narrative_summary` continuam legíveis no app; as regras
correspondentes ficam em `RETIRED_RULES` e são ignoradas. Contradições narrativas
passaram à Coerência com IA.
