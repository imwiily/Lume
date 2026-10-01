# Coerencia

Motor experimental, separado do Lume.app, que aponta **contradições narrativas** num
manuscrito DOCX (características, idades, vida/morte, objetos, posse, quantidades,
clima, horário) usando a **API do Claude**. O manuscrito é somente lido.

> **Privacidade:** os capítulos enviados vão aos servidores da Anthropic. Pelas
> políticas atuais, dados da API não são usados para treino por padrão e são apagados
> em até 30 dias (há exceções; ver Privacy Center da Anthropic). Um modelo local via
> Ollama continua possível com `--modelo <nome-do-ollama>`, e aí nada sai do computador.

O mesmo motor também está **dentro do Lume.app** (opção *Coerência com IA* na etapa Coerência global).

## Preparar

```sh
cd coerencia
/opt/homebrew/bin/python3 -m venv .venv
.venv/bin/python -m pip install python-docx anthropic
export ANTHROPIC_API_KEY=...        # chave criada em console.anthropic.com
```

## Revisar um livro em desenvolvimento (modo projeto)

```sh
.venv/bin/python -m coerencia analisar livro.docx --projeto Projetos/meu-livro
.venv/bin/python -m coerencia status --projeto Projetos/meu-livro
.venv/bin/python -m coerencia decidir C003 corrigida --projeto Projetos/meu-livro
.venv/bin/python -m coerencia decidir C004 intencional --projeto Projetos/meu-livro
```

Economia de tokens a cada nova rodada:

| Capítulo | O que acontece | Custo |
| --- | --- | --- |
| Texto igual, com ou sem pendências | Não é enviado; seus fatos seguem na memória | 0 |
| Texto alterado ou novo | Relido cena por cena | Só esse capítulo |
| Par de trechos já julgado com o mesmo contexto | Resposta vem do cache | 0 |

Contradições cruzam capítulos: um capítulo não enviado ainda participa da comparação
pelos fatos guardados. Pendência cujo trecho sumiu com a edição é encerrada sozinha;
a marcada como `intencional` não volta. `--reler` força o envio de tudo.

Cada análise lista no terminal as pendências abertas: os dois trechos, a confiança e a
explicação; `status --todas` mostra também as já decididas. Alertas sobre o mesmo ponto do
texto (trechos sobrepostos ou o mesmo par de parágrafos) aparecem uma vez só, com os demais em
`relacionadas`. No Lume.app, as pendências aparecem como alertas da etapa Coerência global.

A pasta do projeto guarda `projeto.json` (capítulos, hash e fatos com posição relativa
ao capítulo), `julgamentos.json` (cache), `pendencias.json`, `rodadas.json` (tokens,
custo, economia) e `cenas/` (respostas do modelo, para conferência).

## Outros comandos

```sh
.venv/bin/python -m coerencia analisar texto.docx                   # análise avulsa
.venv/bin/python -m coerencia avaliar                               # 22 contradições anotadas + 2 controles
.venv/bin/python -m coerencia avaliar --caso farol --modelo claude-opus-5-5
.venv/bin/python -m unittest discover -s tests -t .                 # testes, sem chamar a API
```

Modelos: `claude-sonnet-5-5` (padrão, US$ 2/10 por milhão de tokens de entrada/saída),
`claude-opus-5-5` (US$ 4/20), `claude-haiku-4-5` (US$ 1/5). Num teste com 4 textos
(7 contradições), o Sonnet encontrou 7/7 por US$ 0,14; o Opus, 6/7 por US$ 0,28.
`--modelo-juiz` usa outro modelo só nos julgamentos; `--teto` limita o gasto da execução. `--esforco` (low a max)
controla a profundidade de raciocínio no Opus e no Sonnet 5.5. Cada rodada mostra
tokens e custo estimado; o valor cobrado é o do console da Anthropic.

## Como funciona

1. O texto é dividido em capítulos e cenas.
2. Para cada cena, o modelo recebe o texto numerado e os fatos já conhecidos relevantes,
   e devolve fatos e possíveis conflitos em JSON com esquema.
3. Todo trecho citado precisa existir no parágrafo indicado; o resto é descartado.
4. Pares de fatos incompatíveis passam por um juiz, que vê os dois trechos e o contexto.

## Limites

Protótipo, não integrado ao Lume. O juiz reduz, mas não elimina, alarmes falsos. O
conjunto de avaliação é sintético e pequeno.
