# Contrato de motor — versão 1

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

O protocolo de pacote, o relatório e as decisões permanecem em schema 1. A extensão é aditiva: ocorrências recebem `module`, `category_code`, `severity`, `confidence_score`, `range`, `excerpt`, `message` e `suggestion`; `confidence` continua qualitativo para os leitores antigos. A semântica dos offsets está em `IMPLEMENTACAO-MESTRE.md`.

`metadata.stages` registra o que realmente executou; `metadata.text_index` define a projeção de texto extraído. As linhas `LUME_PROGRESS {json}` são eventos locais para a interface. O parser ignora linhas incompletas e mensagens normais do processo. A captura do manuscrito é imutável; as etapas não recebem um editor de DOCX.

O Lume 0.7 exige motor >= 0.5.0 para analisar com as novas chaves de configuração. Configurações antigas completas recebem as quatro novas regras; se todas as antigas estavam desligadas, as novas também ficam desligadas. Os relatórios anteriores continuam legíveis, com módulo/classificação ausentes apresentados como informação não disponível.

A montagem executa testes Python antes do empacotamento e compila/executa o contrato Foundation/Swift após o build do aplicativo. A atualização somente do motor mantém o comando `bash Montar-Lume.command --motor`.

## FONTE 0.6.0 e Lume 0.8 — relações temporais

Três novas chaves de configuração: `coerencia_temporal`, `acentuacao_contextual` e `que_tonico_interrogativo`. O Lume 0.8 exige motor >= 0.6.0. Configurações anteriores completas com todas as regras desligadas continuam desligadas; configurações parciais herdam os padrões das regras não mencionadas.

As ocorrências temporais acrescentam `relation` e `temporal_evidence`, mantendo `related` como evidência navegável para leitores anteriores. O protocolo e os schemas continuam em 1. Quando uma regra temporal específica cobre o mesmo verbo, ela substitui o alerta genérico de tempo; seu ID é diferente e uma decisão antiga não é transferida automaticamente.

Pontuação duplicada e espaçamento agora alcançam falas/pensamentos; quê terminal tem regra própria. A acentuação contextual permanece na narração e as relações temporais seguem `tense_scopes`. As escolhas de registro coloquial não são normalizadas.

O diagnóstico do motor inclui uma relação entre condicional e futuro com sugestão e evidência. Os 30 novos testes incluem variação lexical, sujeitos diferentes, usos legítimos, omissão conhecida do parser e preservação dos offsets. Consulte `RELACOES-TEMPORAIS.md` e `VERIFICACAO.md`.
