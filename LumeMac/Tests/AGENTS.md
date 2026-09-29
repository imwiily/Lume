# Integração, contratos e relatórios

Aplicar também o `AGENTS.md` da raiz Git. Esta pasta reúne testes de pacotes,
contrato Python/Swift e DOM; a semântica unitária fica em `../Analisador/tests/`.

- Seguir comandos e condições de `../../docs/testing/acceptance-v0.11.md`.
  Executar testes Python a partir de `LumeMac/`, com `PYTHONPATH=Analisador`.
- Preservar compatibilidade JSON, decisões, configurações, Unicode e mensagens de
  progresso. Testar imutabilidade do DOCX e recusa de sobrescrever saídas existentes.
- Testar instalação/reversão em temporários, sem substituir o aplicativo ou motor
  ativo do usuário para satisfazer uma verificação.
- Cada teste DOM exige o relatório de seu cenário. Gerar saídas novas pelos fontes
  atuais; não alterar manualmente HTML/JSON para fazer contagens passarem.
- Distinguir fontes atuais, pacote instalado, motor portátil e app embutido nas
  evidências. Paridade de execução não comprova precisão semântica.
- Não remover controles de integridade, compatibilidade ou negativos para passar.
  Dependência ausente, skip ou inspeção não realizada deve constar como pendência.
