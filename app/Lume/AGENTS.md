# Interface SwiftUI

Aplicar também o `AGENTS.md` da raiz Git. Esta pasta cuida da experiência macOS,
relatórios, decisões editoriais, progresso e escolha/execução do motor.

- Manter análise linguística, papéis semânticos, fatos e comparadores no Python.
  Consumir os contratos; não reproduzir heurísticas de análise na interface.
- Preservar compatibilidade de `Models.swift`, decisões e configurações antigas.
  Uma configuração com regras desativadas não pode reativá-las silenciosamente.
- Exibir evidências e limitações do motor. Diferenciar confiança heurística,
  severidade e decisão humana; etapa concluída não significa cobertura completa.
- Preservar seleção de motor, relatórios e decisões existentes. IDs/evidências
  novos não herdam decisões antigas por aproximação. Nunca modificar manuscrito.
- Respeitar índices Unicode Python na apresentação Swift. Validar emoji e acentos
  combinados; destaque não pode mudar ou truncar texto.
- Para mudanças de contrato, executar `../../tests/ContractCheck.swift` conforme
  `../../docs/testing/acceptance-v0.11.md`, com relatórios legados e atuais.
  Para código Swift, executar build pertinente; mudanças visuais requerem inspeção
  nativa. Testes de HTML ou mera compilação não substituem essa inspeção.
- Usar o projeto Xcode existente em `../Lume.xcodeproj/`; não criar pacote Swift
  paralelo ou alterar versão/distribuição incidentalmente.
