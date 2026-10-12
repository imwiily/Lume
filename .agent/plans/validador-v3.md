# ExecPlan — Validador de decisões V3 (experimental): Haiku localiza, Opus avalia

Branch `feature/validador-decisoes`. Capacidade experimental e independente do V2 (`validador_decisoes.py`,
inalterado); sem interface de produção. Código: `fonte/fonte/validador_v3.py`; execução:
`scripts/experimento_v3.py`; testes: `fonte/tests/test_validador_v3.py`.

## Hipótese
Separar a recuperação de contexto do julgamento editorial aumenta a precisão e reduz os falsos negativos
da triagem Haiku → Sonnet da V2.

## Arquitetura
Lume seleciona e extrai localmente → (grupo B) Haiku devolve só referências (parágrafo, posições, tipo) e
lacunas (tipo e termo copiado do texto) → Lume confere cada referência e extrai o literal → Opus julga
TODAS as decisões com o contrato do juiz da V2 (mesmo `SISTEMA_JUIZ`, `_julgar`, reconciliação) mais
um adendo de contexto → Lume verifica evidências e registra. O Opus pode pedir mais contexto uma única
vez por item (parágrafos do capítulo ou termos), atendido localmente e sujeito ao orçamento.

## Garantias de que o Haiku não julga
Sem campo de veredito no esquema; não recebe decisão humana, hipótese do detector nem resultados
anteriores; só referências verificadas e etiquetas de enumeração chegam ao Opus (texto livre do Haiku
nunca é encaminhado); campos extras na resposta são ignorados; resultado final vem só do Opus.

## Grupos (diferença única: contexto adicional do Haiku)
A — Opus direto. B — Haiku + Opus. Mesmo manuscrito, decisões, modelo, esforço, janela (±3), contrato
e critérios. Estado em arquivos separados (`validacao-v3-A.json`, `validacao-v3-B.json`); chaves
incluem grupo e versão: nada da V1/V2 é reaproveitado.

## Conjunto
16 decisões: 13 casos nomeados por ID estável (dados externos, fora do repositório) + 3 por amostragem
reprodutível de categorias diferentes (`--semente`).

## Não executado
Nenhuma chamada paga. Execução depende de autorização financeira expressa, grupo a grupo.

## Conclusão do experimento comparativo A/B (11/10/2026)

16 decisões de um manuscrito real de referência, Opus 5.5 com esforço médio, mesmo contrato do juiz V2.
- **Custo:** A (Opus direto) US$ 0,26; B (Haiku + Opus) US$ 0,29 (+10%). Estimativa prévia: 2× o real.
- **Contexto do Haiku:** 7 referências pedidas, 2 verificadas, 5 redundantes (já na janela). Em 14 de 16 itens
  o Opus B recebeu o mesmo pedido que o A. Nenhum pedido de contexto adicional do Opus nos dois grupos.
- **Efeito:** nenhum ganho de julgamento demonstrado; um ganho de evidência (literal no lugar da premissa
  do detector). Três itens mudaram de classe entre A e B, todos com entrada idêntica: variação do próprio
  modelo, do tamanho da diferença que se media.
- **Decisão:** Opus direto é a arquitetura candidata preferencial. O Haiku não é obrigatório.
  **Não homologado** para publicação nem integrado à Mesa de Revisão. V2 e V3 experimental permanecem
  intactos (hashes preservados no diretório do experimento). Plano: `validador-opus-homologacao.md`.
