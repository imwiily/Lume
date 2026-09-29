# Lume 0.11.4 — FONTE 0.9.4 embutido

Hotfix para Apple Silicon com macOS 27.0 ou posterior. O aplicativo completo inclui Python, modelo português e o motor FONTE 0.9.4, com as correções de memória narrativa verificadas em Echoes e Hikari. O manuscrito permanece inalterado; sugestões e decisões ficam nos relatórios.

## Atualização do motor FONTE 0.9.5 — memória narrativa

O motor 0.9.5 está disponível em [Motor-final/fonte-0.9.5-9b9a561f.lumemotor.zip](Saida/robustez-semantica/Motor-final/fonte-0.9.5-9b9a561f.lumemotor.zip). Extraia o ZIP e selecione a pasta `.lumemotor` em **Motor de análise → Instalar atualização…**. É compatível com o Lume 0.11.4; o aplicativo anterior continua com 0.9.4 embutido. Esta entrega atualiza apenas o motor e seu relatório HTML.

A atualização separa participantes locais de personagens canônicos, promove eventos com papéis e polaridade preservados e mantém estados, posse e conhecimento entre cenas. A confiança acompanha entidades, referências, eventos e fatos. Há 300 testes do analisador aprovados, além de paridade dos fontes com o motor em Echoes, Hikari e casos mínimos. A cobertura em prosa real ainda é parcial; os números e limites estão em [validação](Documentacao/VALIDACAO.md).

## Usar a entrega

Extraia `Lume.app.zip` e copie `Lume.app` para Aplicativos. Feche a versão anterior antes de abrir a nova. Não é necessário instalar Python ou importar um motor separadamente para usar o aplicativo completo.

A entrega deste hotfix está em `Saida/hotfix-0.11.4/Pacote/`, com aplicativo, ZIP e `release.json` (versões, diagnóstico e SHA-256). A assinatura é local/ad hoc, sem notarização para distribuição pública. O macOS mínimo do motor está no manifesto e no resumo da entrega.

A seleção de motores instalados anteriormente é preservada. Se **Motor de análise** mostrar uma versão anterior, use **Restaurar embutido** para ativar **FONTE 0.9.4**. Relatórios, decisões e preferências continuam na pasta `~/Library/Application Support/FONTE/`.

## Estrutura do projeto

| Pasta/arquivo | Conteúdo |
| --- | --- |
| `Lume/`, `Lume.xcodeproj/` | Aplicativo SwiftUI e projeto Xcode |
| `Analisador/` | Motor Python, dados linguísticos e testes |
| `Engine/` | Entrada portátil e gerenciamento de pacotes |
| `Scripts/` | Montagem do motor/app e validação em manuscritos |
| `Tests/` | Contratos, pacotes e verificações do HTML |
| `Exemplo/` | Manuscritos sintéticos, configurações e relatórios de referência |
| `Documentacao/` | Arquitetura, histórico, validação e visão do projeto |
| `Identidade/` | Recursos e guia visual |
| `Saida/` | Entregas, logs e intermediários locais; ignorados pelo Git |
| `Montar-Lume.command` | Entrada para montagem completa ou somente do motor |

Consulte [arquitetura e limites](Documentacao/ARQUITETURA.md), [histórico](Documentacao/HISTORICO.md), [validação](Documentacao/VALIDACAO.md), [visão do projeto](Documentacao/VISAO.md) e [índice dos exemplos](Exemplo/README.md). O diagnóstico dos manuscritos está em [`docs/analises/`](../docs/analises/). Licenças do léxico estão em [atribuições](Analisador/fonte/data/ATRIBUICAO.md) e `Analisador/fonte/data/PORTILEXICON-LICENSE.txt`.

## Montar o aplicativo

Execute na pasta `LumeMac`, em Mac Apple Silicon, com Xcode instalado e Python 3.10–3.13 nativo arm64:

```sh
bash Montar-Lume.command
```

O comando prepara `Analisador/.venv`, instala dependências, executa regressões, prepara o corretor gramatical embutido, congela o motor, compila a interface e monta a entrega. O corretor (LanguageTool 6.6, com Java mínimo gerado por jlink) é preparado uma vez em `Analisador/.languagetool` por `Scripts/preparar_languagetool.py`; isso exige um JDK 17 ou posterior (por exemplo, `brew install openjdk`) e acrescenta cerca de 210 MB ao motor. Tudo roda no Mac, sem serviço na nuvem. `Scripts/build_engine.py --sem-languagetool` monta um motor sem ele. A preparação requer internet. Cada execução cria uma pasta própria em `Saida/`; o aplicativo completo, ZIP e resumo ficam em `Pacote/`. Logs e intermediários ficam separados nessa mesma execução. Uma falha interrompe a montagem; não use como entrega uma pasta que não tenha `release.json`.

Para compilar a interface e reaproveitar um motor já produzido nesta versão, sem congelá-lo novamente:

```sh
xcodebuild -project Lume.xcodeproj -scheme Lume -configuration Release -derivedDataPath Saida/nova-montagem/DerivedData ARCHS=arm64 build
Analisador/.venv/bin/python Scripts/package_app.py --app Saida/nova-montagem/DerivedData/Build/Products/Release/Lume.app --engine /caminho/fonte-0.9.4.lumemotor --output Saida/nova-montagem/Pacote
```

A saída do empacotador deve ser nova. Ele recusa motor de versão diferente dos fontes, valida inventário e funcionamento, inclui o pacote inteiro, assina o aplicativo e repete as verificações no motor embutido. Não altera uma cópia já instalada do Lume. Uma execução direta no Xcode mantém o modo de desenvolvimento com analisador externo; use o aplicativo empacotado para testar o motor embutido.

## Atualizações independentes do motor

```sh
bash Montar-Lume.command --motor
```

Esse comando produz `.lumemotor` e `.lumemotor.zip`, sem compilar a interface. Quem recebe uma atualização deve extrair o ZIP e selecionar a pasta `.lumemotor` em **Motor de análise → Instalar atualização…**. O app valida e testa antes de ativar. **Voltar à versão anterior** reverte a seleção; **Restaurar embutido** retorna ao motor do aplicativo. **Verificar motor** executa o diagnóstico da seleção atual.

Mantenha o pacote inteiro: o executável depende dos arquivos e links internos. Motores são código executável; importe somente pacotes de origem conhecida. O inventário verifica consistência, sem autenticar o publicador.

## Testes e cobertura

Na pasta `LumeMac`, com o ambiente preparado:

```sh
PYTHONPATH=Analisador Analisador/.venv/bin/python -m unittest discover -s Analisador/tests
Analisador/.venv/bin/python -m unittest discover -s Tests -p 'test_*.py'
PYTHONPATH=Analisador Analisador/.venv/bin/python Tests/check_python_contract.py
```

A montagem completa executa também o contrato Swift.

Para medir a detecção em textos que o motor não conhece, use a avaliação cega. Ela gera um DOCX por texto do corpus anotado em `Analisador/tests/corpus/deteccao/`, executa o motor e conta erros encontrados e alarmes falsos por categoria:

```sh
Analisador/.venv/bin/python Scripts/avaliar_deteccao.py --conjunto validacao --languagetool --saida Saida/avaliacao-nova
```

O conjunto `desenvolvimento` pode orientar correções; `validacao` fica reservado para medir. Os dois são sintéticos e foram escritos junto com as regras, por isso não substituem textos anotados por outra pessoa. Textos próprios podem ser acrescentados no mesmo formato. Os scripts DOM em `Tests/` requerem Node e jsdom. `Scripts/validate_real_memory.py` recebe `--docx`, `--baseline`, `--output` e `--engine` para comparar uma análise anterior com fontes e executável preservando o original.

A revisão narrativa é heurística e parcial. Ambiguidades, aliases, mudança de foco, sonhos e fatos implícitos ainda podem gerar omissões. Confiança não é probabilidade calibrada. O Auditor Final permanece indisponível. As amostras e os dois manuscritos usados no desenvolvimento não constituem uma avaliação independente de precisão.
