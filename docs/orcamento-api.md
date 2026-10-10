# Orçamento da API (Lume 1.8)

Vale para a Coerência com IA e a Auditoria final com IA, ambas pelo cliente `Claude` em
`coerencia/coerencia/modelo.py`. Nenhum teste faz chamada paga.

## Defeitos da 1.7

| # | Defeito | Efeito |
| --- | --- | --- |
| A | O teto só comparava o gasto *já acumulado* (`gasto >= teto`) | Uma chamada saía mesmo quando seu pior caso estourava o teto |
| B | Escrita de cache (1,25 × entrada) era cobrada como entrada normal | Custo registrado abaixo do real |
| C | O preço usava o modelo *pedido*, não o que respondeu; modelo sem preço custava US$ 0 | Retomada automática (Opus 5 / 4.8, US$ 5/25 por milhão) e modelos novos subcontados; teto nunca disparava |
| C | `max_retries=4` dentro do SDK, invisível ao teto; timeout não contava nada | Até 5 envios por chamada sem nova conferência do teto |
| D | `teto=0` virava "sem limite" (`if teto`) | Teto zerado liberava gasto ilimitado |

## O que a 1.8 faz

1. **Reserva do pior caso antes de cada envio.** A chamada só sai se `gasto + pior_caso <= teto`
   (saldo exato é permitido). Pior caso = texto + esquema como escrita de cache (1,25 × entrada)
   + `max_tokens` (16000) × saída. Nos modelos com retomada automática (Opus 5.5 e Sonnet 5.5) são
   **duas tentativas somadas**: a original (a recusa no meio da saída, ou em categoria faturada, é
   cobrada) mais a tentativa no destino mais caro (Opus 5 / 4.8). O `max_tokens` é limite rígido da
   API: a parcela de saída de cada tentativa é garantida.
2. **Tarifas separadas** para entrada normal, escrita de cache, leitura de cache e saída, pelo
   modelo que respondeu (`modelo_usado`). `usage` de nível superior descreve só a tentativa final,
   que também consta em `usage.iterations`: soma-se `iterations` (cada tentativa na tarifa do seu
   modelo) e nunca se acrescenta o nível superior de novo. Modelo desconhecido paga, em cada coluna,
   o maior preço conhecido. Tarifas conferidas na página oficial de preços (10/10/2026): Sonnet 5.5
   US$ 2 / 2,50 / 0,10 / 10; Opus 5.5 US$ 4 / 5 / 0,20 / 20 (entrada / escrita 5 min / leitura / saída).
3. **Falhas e repetições.** O SDK não repete mais por conta própria. 429, 5xx e erros de rede (a
   API não cobra) têm até 2 repetições, cada uma conferindo o teto de novo. Tempo esgotado pode ter
   sido cobrado: o pior caso é somado ao gasto (`presumido: true` no registro) e não há repetição.
4. **Estimativa de tokens aprendida.** Se a medição real mostrar menos caracteres por token que o
   previsto (2,5), as reservas seguintes usam o valor medido.
5. **`teto=0` envia nada**; teto negativo, `nan` ou infinito é erro.

Registros antigos (sem `tokens_cache_criacao`) continuam legíveis; nenhum contrato JSON mudou
(só se acrescentaram os campos `tokens_cache_criacao` e `presumido` aos registros de chamada).

## Consequência que exige decisão

Com a retomada automática, o pior caso de **uma** chamada é ~US$ 0,57 com Sonnet 5.5 e ~US$ 0,72
com Opus 5.5 (duas tentativas de 16000 tokens de saída). Chamadas reais custam centavos, mas um teto
abaixo desse valor não envia nada (o app aceita tetos desde US$ 0,05; o padrão de US$ 1,00 envia
uma chamada por vez, com folga pequena). Quando isso ocorre, o aviso diz que a chamada **não foi
enviada** e qual teto mínimo estimado a liberaria. Perto do fim do
teto, a análise para quando o saldo não cobre o pior caso, mesmo que a chamada custasse pouco.

Alternativas (não implementadas, mudam comportamento):
- **Reduzir `max_tokens`** por etapa (os JSONs de saída são pequenos). Baixa o pior caso para
  ~US$ 0,05–0,10, mas aumenta respostas cortadas, que hoje já têm tratamento.
- **Avisar no app** o teto mínimo útil ao digitar o valor (toca na interface).

## Tetos entre recursos e execuções (semântica da 1.7, preservada)

- Coerência e Auditoria final têm tetos *independentes*, cada um por análise: o máximo declarado
  numa análise é a soma dos dois. O app já mostra os dois valores na confirmação.
- Leitor e juiz da Coerência (modelo `Dupla`) compartilham um teto.
- Análises sucessivas começam com teto novo; nada soma o gasto entre análises.
- Dois processos simultâneos não se enxergam.

Alternativa para decidir (não implementada): teto único por análise e/ou acumulado diário
guardado em arquivo. Exige mudar a interface e a semântica do campo "Teto por análise".

## Limites que a correção não elimina

- A parcela de **entrada** do pior caso é estimada por caracteres, não contada pelo tokenizador:
  é conservadora (2,5 caracteres por token, com aprendizado), mas não é garantia matemática.
- Retomada automática: a rota por categoria não é publicada. Reserva-se a primeira tentativa mais
  um destino Opus 5 / 4.8 (US$ 5/25). Se a rota for uma tentativa a mais, ou um modelo mais caro,
  o gasto real pode passar da reserva; o registro usa a tarifa de quem respondeu, então o excesso
  aparece no gasto e bloqueia as chamadas seguintes. Uma recusa antes de qualquer saída em categoria
  não faturada não é cobrada, mas aqui é contada (superestima, não subestima).
- Falhas 429/5xx e de rede: não encontrei, na documentação consultada, afirmação de que não são
  cobradas; trata-se como não cobradas por serem falhas antes de qualquer resposta. Isso **não está
  confirmado**. Só o timeout é presumido cobrado. Erro de rede depois de a API aceitar o pedido
  (sem ser timeout) não é contado.
- Preços ficam em `PRECOS` (conferidos em 10/10/2026); mudança de tabela exige atualização manual.
