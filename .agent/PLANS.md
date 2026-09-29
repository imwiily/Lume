# ExecPlans do Lume

Um ExecPlan é um plano vivo, suficiente para retomar a tarefa com o repositório e
este documento, sem depender de uma conversa anterior. Usá-lo em mudanças
arquiteturais, refactors significativos, mudanças entre módulos, schema, fact bank,
memória narrativa ou comportamento com risco de regressão nos manuscritos reais.
Correções pequenas e documentação simples não exigem um plano extenso.

Salvar planos de tarefas em `.agent/plans/<nome-da-tarefa>.md`, criando a pasta
quando necessário. Manter este arquivo como regra e modelo, sem misturar o status
de várias tarefas. Atualizar progresso, decisões e evidências durante a execução.

## Conteúdo obrigatório de cada plano

### Objetivo e escopo

Descrever o comportamento observável esperado, um exemplo antes/depois e o que
fica fora do pedido. Identificar quais critérios de `docs/testing/acceptance-v0.11.md`
serão comprovados. Não prometer ausência universal de erros.

### Estado atual observado no código

Registrar revisão Git, alterações locais relevantes, arquivos e funções reais,
contratos, ambiente e limitações. Separar implementação observada, resultados
históricos e objetivo futuro. Listar testes existentes e lacunas de cobertura.

### Arquivos afetados e preservação da arquitetura

Listar caminhos relativos à raiz Git e responsabilidade de cada mudança. Explicar
como são preservados manuscrito, pipeline, papéis semânticos, origem, confiança,
identidade, histórico e compatibilidade. Não criar uma segunda arquitetura.

### Etapas incrementais

Usar etapas pequenas, cada uma com comportamento esperado, teste que o demonstra,
mudança proposta e condição de encerramento. Para memória narrativa, considerar:

1. Candidatos e métricas de promoção/descarte.
2. Relevância e persistência local/entre cenas.
3. Histórico, encerramento de estados e estado atual derivado.
4. Posse, transferência, localização, conhecimento, relações e atributos.
5. Regressão completa, comparação real e revisão do diff.

Adaptar ao código já existente; não reimplementar funcionalidades aprovadas.

### Testes, critérios de aceitação e riscos

Relacionar cada critério a casos positivos, negativos e ambíguos. Registrar como
reproduzir a falha antes da correção e como distinguir uma falha de ambiente.
Cobrir risco de falsos fatos, identidade incorreta, perda de escopo/polaridade,
confiança inflada, transições ausentes e incompatibilidade de relatórios.

### Comandos e evidências

Indicar diretório de execução, comando exato, dependências, entradas e saídas novas.
Usar os comandos existentes de aceitação; não inventar um script de validação.
Para corpus real, registrar hash, configuração, baseline e versão do motor. Não
copiar manuscritos privados para fixtures versionadas. Explicar denominadores e
anotação usada em métricas. Guardar logs em uma saída própria de `LumeMac/Saida/`.

### Progresso, descobertas e decisões

Manter checklist de etapas concluídas e pendentes, com data e evidência. Registrar
achados inesperados e decisões com razão e impacto. Em retomadas, conferir código
e estado Git antes de confiar no status anterior.

### Validação realizada e resultado final

Listar testes executados, resultado, falhas, skips, regressões, métricas e revisão
final do diff. Indicar quais gates continuam pendentes e por quê. Não fechar a
implementação nem a release quando faltar evidência obrigatória; uma entrega de
documentação pode estar concluída sem certificar o funcionamento da v0.11.
