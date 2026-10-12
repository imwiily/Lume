# ExecPlan — Coerência 2.0 (experimental): auditoria narrativa global por IA

Branch: `experimento/coerencia-2-ia` (worktree em `build/coerencia-2-worktree`, a partir de `main` 244ff7a).
Estado: protótipo tecnicamente concluído com respostas simuladas. **Não homologado editorialmente.**
**Integração (Lume 1.9.1):** `coerencia` 2.0.0 empacota `coerencia2`; `fonte/fonte/coerencia2_ia.py` adapta a leitura global às
ocorrências v1 (`rule=coerencia2_ia`, sempre `informacao` ou `diagnostico`, nunca impeditivas: `politica.destino`);
`--coerencia-versao 2` em `revisar` e `coerencia-estimar`; cliente de uma só requisição para Claude e Gemini
(`coerencia2/uma_requisicao.py`); seletor *Por cenas (1.x) / Global (2.0)* no app, padrão 1.x; cache e resultado em
`<projeto>/global2/`; a sonda do motor confere a versão 2.0.0 e o manifesto a registra. As seções abaixo são do protótipo.

## Objetivo e escopo
O Coerência 1.2.0 extrai fatos por cena e compara pares com a mesma entidade e aspecto. Isso não cobre causalidade,
lacunas, conhecimento do personagem, deslocamento sem explicação nem acontecimentos abandonados.
A 2.0 inverte o papel: o modelo lê a obra inteira e aponta; o Python lê, numera, limita a cobertura, controla custo e
cache e confere cada citação no texto original.

Antes/depois: 1.2.0 só vê "olhos verdes × castanhos"; 2.0 também pode apontar "a única estrada caiu e a entrega chega
normalmente" como lacuna de continuidade causal, com a ressalva de que pode ser intencional.

Fora do pedido: interface SwiftUI, contrato JSON de produção, decisões, FONTE, empacotamento, integração à Mesa.

## Estado observado
- `coerencia/coerencia/{analise,projeto,modelo,leitura}.py` (1.2.0) intactos. `fonte/fonte/coerencia_ia.py` intacto.
- Reaproveitado de `coerencia.modelo`: `Claude` (saída estruturada estrita, esforço, retomada automática, cache do
  prompt), `Orcamento`/`TetoAtingido` (pior caso reservado antes de cada chamada), `tarifa`, `Recusa`, `RespostaCortada`.
  De `coerencia.analise`: `normalizar` (importado). De `coerencia.leitura`: `Paragrafo`, mesma numeração do FONTE.
- Leitura do manuscrito: `fonte.reader.read_manuscript` (docx e Pages), como em `scripts/experimento_v5_1.py`.

## Arquivos
| Arquivo | Função |
| --- | --- |
| `coerencia/coerencia2/__init__.py`, `auditoria.py` | Pacote **fora** de `coerencia/coerencia/`: não entra no motor embutido (`packages = ["coerencia"]`). Esquema, prompt, estimativa, verificação das evidências, execução, cache. |
| `coerencia/tests/test_coerencia2.py` | 26 testes com modelo simulado e cliente `Claude` com API substituída. |
| `scripts/coerencia2_experimento.py` | `planejar`, `executar` (guardas de custo e autorização), `comparar`, `metricas`. |

## Como funciona
1. Todo o manuscrito vai numa só chamada (`[§N] texto`), com a marca de obra inacabada. Acima de
   `LIMITE_CARACTERES` (300 000) nada é enviado e a cobertura fica `nao_realizada`.
2. O modelo devolve `apontamentos` (categoria estável, natureza contradição|lacuna, prioridade atenção|sugestão,
   certeza alta|média|baixa, evidências, relevância da lacuna, leituras alternativas) e `fenomenos_descartados`
   (mistério, elipse, mudança explicada, sonho/lembrança, narrador não confiável, em aberto, compatível).
3. Cada evidência é localizada por regex tolerante só a espaço, aspas, travessões e caixa, no parágrafo indicado.
   Rejeita: parágrafo inexistente, trecho curto (< 2 palavras), inexistente, em outro parágrafo, ambíguo (2+ ocorrências).
   Posição exata em pontos de código (convenção do FONTE).
4. Situação: sem evidência verificada → descartado; evidência parcial, contradição com menos de dois trechos distintos
   ou lacuna sem relevância → `inconclusiva`. Nunca promove. Destino: `informacao` (atenção, certeza ≥ média, sustentada)
   ou `diagnostico`. `impeditivo` é sempre falso. Lacunas levam aviso fixo "não é contradição comprovada".
5. ID = hash de categoria + posições verificadas (independe da redação do modelo). Resposta bruta em
   `cache-global.json` (chave: versão do prompt, modelo, esforço, texto); repetir não paga de novo.
6. Resultado registra modelo solicitado, modelos que responderam, custo, cobertura (`global`, `incompleta`,
   `nao_realizada` com motivo) e o hash do texto lido. O manuscrito é só lido.

## Proposta para manuscritos maiores (não implementada)
Contexto acumulado e recuperação, só depois de validar a leitura global:
1. Passo de memória: por capítulo, o modelo resume e lista entidades, regras, promessas e questões abertas (cada item com § e
   citação literal verificada pelo Python). A memória é cache por hash de capítulo.
2. Passo de auditoria por janela: capítulos novos ou alterados + memória acumulada + recuperação, por palavra-chave e
   entidade, das passagens originais ligadas às perguntas pendentes.
3. Passo de fechamento: o que foi aberto e não acompanhado, com evidências recuperadas do texto original.
4. Toda cobertura parcial é declarada no resultado. Só vale a pena se a 2.0 mostrar valor na leitura global.

## Testes e limites da validade
- Simulados (26): 10 casos sintéticos pedidos, rejeição de citação inexistente/ambígua/em outro parágrafo, rebaixamento,
  limite sem envio, resposta cortada, teto, cache, ordem e IDs estáveis, imutabilidade, pedido ao `Claude`.
- **Não medem** a capacidade do Claude. As respostas foram escritas à mão. Precisão, cobertura e falsos positivos
  editoriais só podem sair de execuções reais autorizadas.

## Experimento seguinte: comparar 1.2.0 × 2.0 no mesmo manuscrito
Pré-requisitos: autorização explícita do autor, teto de gasto definido e manuscrito que caiba no limite.
1. Fixar o arquivo e registrar o SHA-256. Nenhum trecho de manuscrito real vai ao repositório; saídas em `build/`.
2. Baseline 1.2.0: relatório do FONTE do mesmo arquivo com a Coerência com IA já executada (`rule=coerencia_ia`).
   Se for refazer, anotar custo medido.
3. `scripts/coerencia2_experimento.py planejar` → conferir cobertura e custo máximo.
4. `executar` com `--teto`, `--sha-esperado`, `--saida build/…` e `--autorizo-envio`. Uma chamada; sem repetição.
5. `comparar --v1 relatorio.json --v2 coerencia2-resultado.json`: sobreposição por parágrafo, itens exclusivos e modelo de anotação.
6. Anotação cega: o autor julga cada item (`procedente`, `improcedente`, `intencional`, `duvida`) sem ver a versão de origem
   (embaralhar `modelo_de_anotacao` antes de entregar). A 2.0 não vê as decisões nem a anotação.
7. `metricas`: precisão por versão (procedentes ÷ procedentes+improcedentes+intencionais), itens só da 2.0 (ganho de
   cobertura), itens só da 1.2.0 (perda), taxa de citações rejeitadas, custo por apontamento procedente.
8. Critério para considerar a 2.0 (política do AGENTS): classe nova entra como informação ou diagnóstico; vira pendência
   só com precisão medida em livros reais (≥ 20 decisões). Impeditiva nunca (classe narrativa).
Contaminação: não alterar o prompt depois de ver os resultados do mesmo manuscrito; nova versão do prompt exige outro
manuscrito ou um conjunto de teste reservado. `VERSAO_PROMPT` entra na chave de cache.

## Limitações conhecidas
- `MAX_TOKENS` fixo em 16 000 no `Claude.json` compartilhado: obras com muitos apontamentos podem cortar a resposta
  (reportado como cobertura `incompleta`, sem aproveitar o JSON truncado).
- O limite de 300 000 caracteres é uma escolha conservadora, não medida; o custo esperado usa premissa não calibrada.
- A verificação garante que a citação existe, não que o julgamento está certo.
- Evidência de lacuna pode ser um só trecho; ambiguidade de trecho curto repetido é rejeitada (perde recall).
- Narrativa não linear, voz de personagem e ironia dependem inteiramente do modelo.
- Sem integração ao relatório, à Mesa, a decisões ou a identidade de alerta.
