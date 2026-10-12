# ExecPlan — Validador de decisões V4 (experimental): Sonnet avalia, Python confere a integridade

Branch `feature/validador-decisoes`. Módulo independente `fonte/fonte/validador_v4.py` (V2 e V3 intactos,
só reutilizados como infraestrutura), execução em `scripts/experimento_v4.py`, testes em
`fonte/tests/test_validador_v4.py`. Sem interface de produção; FONTE, Coerência e Auditor IA não mudam.

## Arquitetura
Lume seleciona e recupera o contexto local → **Sonnet 5.5** (único modelo) responde perguntas separadas →
**Python** confere a autenticidade e a consistência verificável → registro por apontamento com trava.

## Fiscalização determinística (universal, sem regra gramatical por categoria)
Existência literal da citação no contexto autorizado; parágrafo e posição calculados pelo Lume; conclusão
referente à ocorrência apontada (eco do ordinal e cobertura do alvo); marcação sem alterar o texto
(sinais e delimitadores sem colisão); esquema da resposta; contradições rebaixadas. Para contestar
`Estilo do autor`/`Intencional`, a prova de ausência de intenção precisa estar no contexto autorizado, fora do
alvo e tratar da mesma palavra (relevância lexical): uma frase neutra qualquer não serve. Isso verifica
autenticidade, não correção.

## Resultados
mantida · contestada · revisao_recomendada (problema real, mas não dá para concluir que a decisão
foi inadequada) · apontamento_inadequado · inconclusiva. O estado de validação por IA é separado da
decisão humana, que nunca muda.

## Trava persistente
`validacoes-v4.json` por apontamento (ID, decisão, chaves de conteúdo e de configuração, modelo, prompt,
resultado, evidências com posição e hash do parágrafo, tokens e custo, estado de validade) e trava de
sistema (`flock`) contra execuções simultâneas. Válida → reutilizada sem chamada; mudança no alerta, na
decisão ou no contexto relevante → `desatualizada` (sem reprocessar); mudança de modelo, prompt ou
configuração → `desatualizada_configuracao` (sem reprocessar); revalidação só por pedido explícito com
confirmação de custo. Registro "em processamento" de execução morta não vale como resultado.

## Contrato para a Mesa de Revisão (não ligado)
`nao_analisada, analisada, contestada, revisao_recomendada, inconclusiva, desatualizada, em_processamento`;
`planejar` informa quantas decisões seriam analisadas e quantas reutilizadas sem custo.

## Economia
Parágrafos de contexto compartilhados uma vez por lote; cache do prompt de sistema; limite de saída por
contrato (fixo + por item) aplicado em memória, sem alterar o Coerência; uma única ampliação de contexto por
item, dentro do teto; tokens e custo por chamada gravados. O "orçamento global" existe só na branch
experimental `experiment/haiku-5.5`; aqui vale o teto por execução (`Orcamento`).

## Primeiro experimento real (aguarda autorização financeira)
Os mesmos 16 apontamentos e o mesmo manuscrito do experimento A/B da V3, pasta de projeto nova, V3 só na
análise posterior. Critérios editoriais a verificar, caso a caso: erros objetivos contestados com prova
autêntica; escolhas legítimas preservadas; intenção indeterminada em `revisao_recomendada`; nenhuma
contestação sustentada por frase neutra. Não homologado.
