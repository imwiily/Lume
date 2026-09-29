# Lume 0.8 — relações temporais e acentuação contextual

Esta versão amplia a implementação de `Lume_Revisor_Mestre_Visao.md`, com **FONTE 0.6.0**. As novas regras usam relações sintáticas e confirmação lexical, sem depender de nomes ou frases de um manuscrito. O manuscrito percorre as etapas em uma estrutura imutável; nenhuma sugestão é aplicada ao DOCX.

**O ZIP contém o projeto e o comando de montagem, não um aplicativo macOS compilado.** A montagem deve ser feita no seu Mac M3, sem Rosetta. A compilação e o teste visual da interface macOS ainda precisam ser confirmados nesse sistema; consulte `VERIFICACAO.md`.

## O que esta etapa entrega

- Execução sequencial: Linguístico → Morfossintático → Contexto curto → Coerência global. O Auditor Final aparece como **ainda não disponível**.
- Relações temporais locais entre orações: futuro sob condicional, simultaneidade com “enquanto” e coordenação entre passado/presente. Formas ambíguas como “atravessamos” geram uma dúvida, sem correção obrigatória.
- Acentuação contextual de famílias como “construiam/construíam” e “caiam/caíam”, com eixo passado e indícios sintáticos. Há contraprovas para subjuntivos e imperativos legítimos.
- Pontuação duplicada, espaçamento e “que?” final também são examinados em falas e pensamentos. Reticências e formas como “tô”, “cê” e “pra” são preservadas. “Além de disso” e “que, não” continuam restritos à narração.
- Ocorrências com módulo, classificação, força do indício, trecho exato, sugestão opcional e posições locais/globais em Unicode. Os campos e IDs anteriores são mantidos onde a mesma regra e as mesmas evidências continuam aplicáveis.
- Progresso real por etapa, filtros por módulo/classificação, sugestões separadas do texto e botão **Etapas e alcance** na Mesa. O HTML também mostra as etapas e seus limites.
- Migração das configurações completas antigas. “Desativar todas” permanece desativado. O script de montagem executa as regressões antes de gerar o motor.

A opção **Ambas** executa todas as verificações disponíveis, nas quatro etapas. Os modos antigos **Linguística** e **Editorial** são mantidos como seleções de regras. Por compatibilidade, a verificação da ligação entre fala e narração continua selecionada pelo modo Linguística, embora sua execução agora pertença ao módulo Contexto curto.

## Alcance real

| Etapa | Implementado nesta versão | Ainda pendente |
| --- | --- | --- |
| Linguístico | Padrões determinísticos, quê final, pontuação em falas/pensamentos, repetição consecutiva e LanguageTool local opcional | Ampliação de ortografia, vocativos e concordância de alta precisão |
| Morfossintático | Tempo predominante, presença de verbo finito, quatro relações temporais locais e acentuação verbal contextual | Concordância sujeito-verbo, relações temporais mais amplas e maior robustez da análise sintática |
| Contexto curto | Regras existentes de ligação por aspas, repetições e referências específicas | Incisos por travessão mais profundos, ambiguidades de objetos e interpretação da cena |
| Coerência global | Variação gráfica de nomes na obra e dois padrões locais de cronologia | Banco de fatos, poderes, objetos, relações e continuidade semântica entre capítulos |
| Auditor Final | Estado reservado e limitação explícita | Revisor independente que encontra problemas novos |

Concluir uma etapa significa concluir suas regras disponíveis. **Esta entrega ainda não é o Revisor Mestre completo.** A força numérica do indício não é uma probabilidade calibrada de erro. Nenhuma decisão editorial treina ou silencia automaticamente as regras.

## Atualizar e testar no Mac

1. Extraia o ZIP e execute `bash Montar-Lume.command` na pasta `LumeMac`.
2. Abra o novo `Lume.app`. Se aparecer um motor ativo anterior ao FONTE 0.6.0, use **Motor de análise → Restaurar embutido**.
3. Escolha `Exemplo/Mestre/Manuscrito-modular.docx`, modo **Ambas**, tempo **Passado** e configuração padrão.
4. Confira a sequência das etapas, os filtros e a distinção entre erro confirmado, provável erro e atenção editorial. O relatório de demonstração incluído tem 11 ocorrências; não recebe correções automáticas.
5. Consulte **Etapas e alcance**: a auditoria deve estar indisponível, e a coerência global deve informar sua cobertura parcial.
6. Para isolar as regras novas, abra `Exemplo/Temporal/Manuscrito-temporal.docx`, importe `Exemplo/Temporal/Busca-temporal.json` e use Ambas/Passado. São esperadas 9 ocorrências, incluindo duas dúvidas temporais. Restaure a configuração padrão antes de analisar outros documentos com todas as regras.

O novo Lume exige FONTE 0.6.0 ou posterior para enviar as novas regras de configuração. Relatórios e decisões anteriores continuam legíveis. Futuras atualizações compatíveis do motor permanecem independentes do aplicativo.

`Exemplo/Editorial` e o exemplo da raiz conservam JSONs anteriores para conferir a compatibilidade. `Exemplo/Mestre` demonstra as etapas; `Exemplo/Temporal` demonstra as novas relações com vocabulário variado.

O contrato inicial está em `IMPLEMENTACAO-MESTRE.md`; o alcance atual e as limitações das novas regras, em `RELACOES-TEMPORAIS.md`. A visão original está preservada em `Lume_Revisor_Mestre_Visao.md`.

## Montar uma vez no seu Mac M3

1. Extraia o ZIP para uma pasta permanente.
2. Tenha o Xcode instalado e aberto ao menos uma vez. Em **Xcode → Settings → Locations → Command Line Tools**, selecione a instalação do Xcode.
3. Para montar, é necessário Python 3.10–3.13 **nativo arm64**; a opção sugerida é 3.12. Essa exigência é apenas para a máquina que produz o pacote. O script cria ou reutiliza `Analisador/.venv`, instala as dependências e baixa o modelo quando necessário. A montagem requer internet.
4. Abra o Terminal, digite `cd `, arraste a pasta `LumeMac` extraída para o Terminal e pressione Enter. Execute:

```bash
bash Montar-Lume.command
```

O processo pode levar vários minutos. Ele empacota o motor, testa uma análise real, compila a interface, inclui o motor na aplicação, assina localmente e testa o executável incluído.

Ao terminar, abre uma pasta dentro de `Saida/` com:

- **`Lume.app`** — aplicativo completo. Pode ser copiado para Aplicativos.
- **`Lume.app.zip`** — cópia compactada do aplicativo completo.
- **`fonte-<versão>-<identificador>.lumemotor`** — pacote independente do analisador.
- **O mesmo motor em `.lumemotor.zip`** — para transferir a atualização mantendo os links internos.
- Registros de montagem e arquivos intermediários.

Mantenha a pasta `.lumemotor` completa: o executável e os dados trabalham juntos. O pacote gerado é para Apple Silicon e assume o macOS da máquina de montagem ou posterior. A assinatura é local/ad hoc; distribuição pública com Developer ID e notarização não está automatizada aqui.

Se houver erro, o script para sem entregar uma montagem como concluída. O registro do PyInstaller fica na pasta `build-engine-...`, e o da compilação em `xcodebuild.log`. O script não altera uma cópia já instalada do aplicativo.

## Atualizar somente o fonte-revisor

**Para quem recebe uma atualização:**

1. Extraia o ZIP do motor no Finder.
2. No Lume, abra **Motor de análise → Instalar atualização…**.
3. Selecione a pasta que termina em **`.lumemotor`**.
4. Aguarde a conferência e o teste. A versão ativa aparecerá como **FONTE X.Y.Z · atualizado**.

O aplicativo copia a atualização para seus dados locais; depois da instalação, a cópia recebida pode ser removida. Relatórios, decisões e manuscritos não são substituídos. Não há necessidade de recompilar o Lume para cada motor compatível.

**Para produzir uma atualização:**

Atualize o código em `Analisador/fonte`, ajuste a versão em `Analisador/fonte/__init__.py` e em `Analisador/pyproject.toml`, rode os testes e execute:

```bash
bash Montar-Lume.command --motor
```

Isso gera o `.lumemotor.zip` e testa o motor, sem compilar nem substituir a interface. O pacote inclui o runtime e as dependências para permitir também alterações nelas; por isso é maior que uma atualização composta apenas por regras Python.

A importação é manual e local. Os pacotes contêm código executável e devem vir de uma origem em que você confia. SHA-256 verifica consistência do conteúdo; não autentica a identidade do autor do pacote. Não há servidor de atualização ou assinatura de publicador configurados nesta versão.

## Voltar a uma versão anterior

- **Voltar à versão anterior:** alterna entre o motor ativo e o anterior. Se o anterior era o original, volta ao embutido.
- **Restaurar embutido:** seleciona explicitamente a versão incluída no aplicativo. Também recupera a seleção caso o arquivo de estado tenha sido corrompido, preservando uma cópia dele.
- **Verificar motor:** executa o diagnóstico do motor atualmente selecionado.

A troca só acontece após a validação e o teste. Uma instalação que falha preserva o motor anterior. Problemas linguísticos que não aparecem no teste automático podem ser tratados voltando manualmente à versão anterior.

As versões instaladas ficam em `~/Library/Application Support/FONTE/Engines/`; a escolha ativa e a anterior ficam em `engine-state.json`. O aplicativo original em `/Applications` não é modificado para instalar motores novos. As versões antigas são mantidas nesta primeira implementação, sem limpeza automática.

## Compatibilidade e dados antigos

A interface continua usando `br.fonte.editorial` e a pasta de dados FONTE. Relatórios JSON e decisões da versão anterior continuam abrindo. Mudanças na segmentação ou nas evidências podem criar IDs novos; decisões não são atribuídas por aproximação a esses alertas. Feche o aplicativo antigo antes de abrir o novo.

O protocolo do motor, do relatório e das decisões é **versão 1**. Um pacote que declara um protocolo diferente é recusado. Mudanças futuras na estrutura das informações exibidas podem exigir também uma atualização da interface; mudanças compatíveis nas regras, no modelo ou nas dependências podem ser entregues somente como motor.

A análise usa FONTE 0.6.0 neste projeto. As regras estão distribuídas entre as etapas sequenciais, com cobertura parcial explicitada. O corretor LanguageTool continua opcional e depende de um servidor local separado na porta 8081.

## Trabalhar no Xcode

Abra `Lume.xcodeproj`, esquema **Lume**, destino **My Mac**. Uma execução direta pelo Xcode não inclui automaticamente o motor; ela mantém o modo anterior de desenvolvimento, que permite escolher a pasta do analisador e usar sua `.venv`.

Use **o `Lume.app` produzido por `Montar-Lume.command`** para testar o motor embutido e os botões de atualização. Não copie somente o executável nativo ou somente o diretório `runtime` para o app.

## Estrutura

| Local | Função |
| --- | --- |
| `Lume/` | Interface SwiftUI e seleção do motor |
| `Analisador/` | Código-fonte Python, léxico e testes linguísticos |
| `Engine/lume_engine.py` | Entrada do motor portátil, análise e teste de saúde |
| `Engine/engine_packages.py` | Validação, instalação, troca atômica e restauração |
| `Scripts/build_engine.py` | Empacotamento PyInstaller e teste do pacote |
| `Montar-Lume.command` | Montagem completa ou somente do motor |
| `Tests/test_engine_packages.py` | Testes de instalação e recuperação |
| `Identidade/` | Símbolo, paleta e prévia ilustrativa do design |

## Testes e verificação

Na pasta do projeto, depois de preparar `Analisador/.venv`:

```bash
Analisador/.venv/bin/python -m unittest discover -s Tests -p 'test_engine_packages.py' -v
Analisador/.venv/bin/python Tests/check_python_contract.py
```

Para os testes linguísticos:

```bash
cd Analisador
.venv/bin/python -m unittest discover -s tests -q
```

No Mac, após montar, abra o `Lume.app`, analise o exemplo, importe o motor gerado, confira a versão, volte à anterior e restaure o embutido. Confira também as decisões salvas anteriormente e a importação/exportação. A etapa nativa não foi executada no ambiente Linux de criação.

Referências de empacotamento: https://pyinstaller.org/en/stable/usage.html e https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html . O PyInstaller exige montagem na plataforma de destino e preservação dos links simbólicos dos pacotes.

As atribuições do léxico permanecem em `Analisador/fonte/data/ATRIBUICAO.md` e `PORTILEXICON-LICENSE.txt`.

As imagens de prévia em `Identidade/` são registros do design anterior; não representam o novo fluxo de telas.
