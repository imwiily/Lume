# ExecPlan — Validador de decisões V4.1 (experimental)

Branch `feature/validador-decisoes`. Módulo próprio `fonte/fonte/validador_v4_1.py` (a V4 e suas validações
persistidas ficam intactas; estado em `validacoes-v4-1.json`), execução em `scripts/experimento_v4_1.py`,
testes em `fonte/tests/test_validador_v4_1.py`. Sonnet 5.5 único avaliador; sem chamadas pagas nesta etapa.

## Diagnóstico a partir do primeiro experimento real da V4
1. A regra de prova de ausência combinada ao prompt levou o modelo a responder "incerta" em todos os desvios
   preservados: erros objetivos sob `Estilo do autor` viraram revisão recomendada sem distinção de natureza ou
   certeza, e a relevância lexical nunca chegou a ser avaliada.
2. O contrato misturava existência do problema com adequação da decisão e exigia provar ausência de intenção.
3. Ampliação de contexto: o modelo só via a janela local e pediu números de parágrafo sem mapa do capítulo; a
   busca por termos ordenava por proximidade (os nomes inundam o teto) e a hipótese do detector não era usada
   como consulta; o antecedente descrevia o fato sem repetir os nomes.
4. Reconciliação deixava a evidência de uma questão descartada no registro sem marca de que não sustentava
   resultado ativo.

## Contrato V4.1
Julgamento A (problema técnico): `existe`, `natureza` (objetivo/interpretativo), `certeza` (clara/discutivel),
`gravidade` (alta/media/baixa), `justificativa_detector`. Julgamento B (só preservação): `razao_literaria`
(identificada/nao_identificada/indicio_contrario/nao_se_aplica) com `evidencia_razao`. A adequação da decisão
é derivada pelo Lume. `nao_identificada` não é prova de ausência de intenção; só um indício concreto,
citado e autêntico, sustenta contestação. Sem exigência de repetir palavra. Prioridade da revisão em
categorias ordenadas (sem escala numérica nem calibração).

## Antecedentes
`recuperar_antecedentes`: relevância (IDF no capítulo × peso da origem: termo pedido, alvo, hipótese do detector),
anteriores ao alerta valem mais, determinístico, sem IA e sem regra por obra. Automático para categorias que
dependem de antecedente (classes do motor); nos demais itens só quando o modelo pede, numa única rodada.
Os números dos antecedentes ficam no registro, e a chave de conteúdo os usa: mudar outra parte do capítulo
não os reescolhe nem invalida a validação.

## Rastreabilidade
Cada evidência tem `sustenta` e `situacao` (ativa/descartada, com motivo e vínculo). Questão descartada ou
contestação rebaixada mantém a evidência, marcada.

## Economia
Sem chamada obrigatória nova; mesmos lotes, cache, limites de saída e teto. Estimativa do conjunto de 16:
entrada +12% (prompt maior e 2 itens com antecedentes), custo esperado +9%.

## Fora de escopo
Interface, homologação, merge. Resultados da V4 são referência de comparação, não gabarito.
