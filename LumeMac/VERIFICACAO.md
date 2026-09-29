# Verificação — Lume 0.8 / FONTE 0.6.0

Verificações realizadas no ambiente Linux de desenvolvimento, com Python 3.12, spaCy 3.8.16 e pt_core_news_sm 3.8.0.

## Resultado observado

- **129 testes do analisador aprovados**, sem falhas ou testes ignorados: 99 testes existentes (ajustados onde o alcance de pontuação mudou) e 30 novos testes, vários com subcasos. Os novos testes cobrem variação de sujeitos/verbos, relações sintáticas, homógrafos, subjuntivos, diálogos, configuração e Unicode.
- **14 testes de pacotes aprovados**: integridade, instalação, reversão, recuperação, argumentos e preservação do motor anterior em falhas.
- Contrato Python/CLI aprovado: Unicode, caminhos especiais, SHA-256, preservação do DOCX, bloqueio de sobrescrita e relação temporal com sugestão, evidência e intervalo global.
- Diagnóstico `Engine/lume_engine.py --lume-probe` aprovado em execução Python: versão 0.6.0, protocolos v1 e amostras linguística/editorial/modular/temporal. O binário congelado não foi gerado neste ambiente.
- Testes DOM dos relatórios antigo, modular e temporal aprovados: filtros, contagens, sugestões, classificação, evidências, contexto, decisões e importação/exportação. Homógrafo ambíguo não recebe sugestão obrigatória.
- HTML temporal renderizado e inspecionado em Chromium, em larguras de 1280 e 390 pixels; sem transbordamento horizontal. Os testes visuais são do HTML, não da interface nativa.
- Sintaxe dos sete arquivos da aplicação Swift e do contrato Swift validada com tree-sitter-swift. Script de montagem validado com `bash -n`.
- Demonstrações geradas pela CLI: Mestre com 11 ocorrências (3/3/3/2) e Temporal com 9 (2 linguísticas, 7 morfossintáticas). Na amostra Temporal, duas ocorrências são dúvidas editoriais e sete são prováveis erros, sem erro confirmado. Auditoria declarada indisponível. Falas coloquiais e reticências normais não geram alertas das novas regras.

Não houve compilação com SDK Apple, execução do contrato Swift, empacotamento PyInstaller arm64, assinatura ou inspeção visual de `Lume.app`. A validação sintática não verifica tipos/API SwiftUI e não substitui a compilação no Mac. O script de montagem agora executa os testes Python, compila o app e compila/executa o contrato Swift antes de finalizar a entrega nativa.

Não houve avaliação do manuscrito completo de Hikari No Sekai nem medição de precisão/recall em corpus anotado independente. Os exemplos e contraprovas são conhecidos durante o desenvolvimento. Há omissão conhecida quando o parser classifica “gira” como adjetivo; o teste documenta a abstenção, não a recuperação desse caso. O LanguageTool real não foi iniciado; o teste de sua integração permanece simulado. Os números de confiança são heurísticos e a cobertura é parcial.

## Confirmação no Mac M3

1. Execute `bash Montar-Lume.command`. Em caso de falha, conserve os logs em `Saida/`.
2. Abra o app gerado e confira FONTE 0.6.0; restaure o motor embutido se houver atualização antiga ativa.
3. Analise `Exemplo/Mestre/Manuscrito-modular.docx` em Ambas/Passado com configuração padrão. Confira progresso sequencial, contagens, filtros, destaques e sugestões.
4. Abra **Etapas e alcance** e confirme que o Auditor Final está indisponível. Não deve haver certificado de revisão completa.
5. Teste uma janela mínima e uma ampliada, nos modos claro e escuro. Confira o botão de analisar, os seletores e a rolagem.
6. Registre e exporte uma decisão; reabra o relatório e confirme a restauração. Abra também os JSONs anteriores de `Exemplo/Editorial`.
7. Interrompa uma análise e retome o relatório anterior. Nenhum resultado anterior deve aparecer como resultado da execução interrompida.
8. Importe uma configuração anterior com todas as regras desligadas; confirme que as regras acrescentadas também ficam desligadas.
9. Abra `Exemplo/Temporal/Manuscrito-temporal.docx`, importe `Exemplo/Temporal/Busca-temporal.json` e use Ambas/Passado. Confira as 9 ocorrências, incluindo “atravessamos” como dúvida sem substituição obrigatória. Restaure a configuração padrão depois.

## Reproduzir as verificações

```bash
cd Analisador
.venv/bin/python -m unittest discover -s tests -v
cd ..
Analisador/.venv/bin/python -m unittest discover -s Tests -p 'test_*.py' -v
Analisador/.venv/bin/python Tests/check_python_contract.py
```

Os três scripts DOM (`check_report_dom.cjs`, `check_modular_report_dom.cjs` e `check_temporal_report_dom.cjs`) em `Tests/` requerem `jsdom` disponível ao Node. O contrato nativo requer `swiftc` e Foundation; o script de montagem o executa automaticamente no Mac.
