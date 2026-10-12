# ExecPlan — Validador V5.1 (consistência contextual)

Branch `feature/validador-decisoes`. Experimental, não homologado, fora da Mesa de Revisão (nenhuma mudança em Swift).
Base: V5 (GPT‑6.1 Sol), preservada. V2, V3, V4, V4.1 e V5 não foram alteradas.

## Problema

Na V5 o agrupamento em pedidos seguia só a ordem do relatório (`v4.lotes`): alertas do mesmo parágrafo podiam ser
julgados em chamadas diferentes, sem que o modelo soubesse da existência dos outros, sob a instrução "cada item é
independente". Sem canal para declarar dependência, uma diferença entre julgamentos semelhantes não tinha como ser
fundamentada nem verificada.

## Desenho (arquitetura híbrida D)

1. **Relações contextuais** (Python, sem IA; proximidade, não prova semântica): `mesma_frase` (heurística),
   `mesmo_paragrafo`, `mesma_construcao` (mesma categoria e regra, mesmas duas palavras à esquerda, última
   palavra que não seja artigo/pronome; capítulo igual). Só as duas primeiras vão ao pedido.
2. **Agrupamento seguro**: unidade indivisível = mesmo parágrafo/frase; limites de itens (6), contexto
   (9000 caracteres), pior caso financeiro e saída; divisão documentada (`divisoes`), referências preservadas;
   o orçamento nunca é esticado para manter um grupo (divide por orçamento antes de enviar).
3. **Pedido**: seção final por item com os relacionados (posição e ocorrência; sem decisão, veredito ou hipótese).
4. **Contrato**: campo `relacoes` (`independente`, `depende_de`, `mesma_questao`, `diferenca`, `incerta`) com
   `propriedade`, `motivo` e `trecho` opcional. Verificação estrutural: id fornecido àquele item, sem duplicata
   contraditória, motivo/propriedade conforme o tipo, trecho existente no contexto autorizado. A veracidade da
   explicação não é verificada: o estado é `diferenca_declarada` (formal), nunca "justificada".
5. **Consistência derivada** (na leitura, nunca persistida, nunca altera estado/decisão/diagnóstico/prioridade):
   `classificacoes_alinhadas` (só equivalência de campos; não confirma correção), `diferenca_nao_articulada`
   (atenção só quando `existe` difere), `diferenca_declarada`, `contradicao_declarada` (declarações
   explicitamente incompatíveis), `comparacao_indisponivel` (vizinho sem veredito: não é dependência) e, para
   dependências declaradas: `dependencia_declarada`, `dependencia_condicional`, `dependencia_nao_analisada`,
   `dependencia_circular` (ciclos por componentes fortemente conexos).
6. **Persistência**: `validacoes-v5-1.json` e `.lock` próprios (adaptadores mínimos; V5 intacta, não lida, não
   convertida). Chave de conteúdo = chave V4.1 + chave de relações (ids, tipo e posições dos relacionados enviados;
   nunca decisão, veredito nem hipótese do vizinho). Mudar veredito/decisão do vizinho não invalida ninguém.

## Arquivos

- novos: `fonte/fonte/validador_v5_1.py`, `fonte/tests/test_validador_v5_1.py` (40 testes, sem API),
  `scripts/experimento_v5_1.py` (planejar, agrupamento, simular-v5; sem modo executar).
- editados: `CHANGELOG.md` (nota).

## Fora do escopo desta etapa

Reavaliação conjunta por grupo (operação opcional futura, com estimativa, teto e confirmação); Mesa de Revisão;
qualquer chamada à API; comparação real V5.1 × V5 (depende de autorização).

## Pendências e riscos

- Custo real e raciocínio dependem de execução autorizada; as estimativas são por caracteres.
- `mesma_construcao` tem recall baixo por desenho; `mesma_frase` é heurística não validada em corpus.
- Pedidos maiores (até 6 itens) concentram o risco de truncamento/falha em uma chamada; o limite de saída escala
  por item e uma resposta cortada divide o lote.
