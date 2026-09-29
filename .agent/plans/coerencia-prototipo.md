# ExecPlan — Coerencia: motor separado de contradições com modelo local

Iniciado em 29/09/2026. Plano vivo.

## Objetivo e escopo

Protótipo de terminal, fora do Lume.app, em `LumeCoerencia/`, que lê um DOCX e
aponta contradições narrativas (características, estados, posse, quantidades,
nomes, clima/horário, vida/morte) usando um modelo de linguagem local (Ollama,
127.0.0.1). A memória da história fica em arquivos JSON por cena, para que o
modelo nunca precise do livro inteiro no contexto.

Fora do escopo: integração com o app ou com o motor FONTE, gramática, alteração
do manuscrito, serviços na nuvem. Decisão do usuário: motor separado, só terminal.

## Estado observado

- Mac M3 16 GB; Ollama 0.34.4 via Homebrew, servidor iniciado sob demanda.
- Modelos: `qwen3.5:9b` (6,6 GB) e `gemma4:e4b-it-qat` (6,1 GB). Qwen3.8-27B
  (~14–17 GB em 4 bits) não cabe com folga; fica como teste opcional.
- Linha de base: a memória narrativa do FONTE encontrou 0 de 11 contradições nos
  cinco textos de teste do usuário e 0 de 11 no corpus sintético.

## Arquitetura

1. Leitura: parágrafos não vazios numerados como no FONTE (1 = primeiro), títulos
   de capítulo, cenas por capítulo e tamanho máximo.
2. Extração por cena: modelo recebe a cena numerada e os fatos já conhecidos
   relevantes; devolve fatos e conflitos em JSON com esquema. Todo trecho citado
   precisa existir literalmente no parágrafo indicado; o resto é descartado.
3. Memória: `cenas/NNN.json` (resultado verificado, reutilizável ao retomar) e
   `memoria.json` (fatos acumulados).
4. Comparação: pares de fatos com a mesma entidade e aspecto e valores diferentes,
   mais conflitos sugeridos na extração, vão a um juiz (modelo) com os dois
   trechos e o contexto; só `contradicao=true` entra no resultado.
5. Avaliação: 22 contradições anotadas (5 textos do usuário + 6 do corpus
   sintético) e 2 textos de controle sem contradição.

Invariantes: manuscrito só lido (SHA-256 antes/depois); fatos sempre com trecho,
parágrafo e fonte (narrador/fala); dúvida não vira alerta forte; nenhuma regra
ou prompt usa nomes das obras.

## Etapas

- [x] Instalar Ollama e modelos (qwen3.5:9b, gemma4:e4b-it-qat).
- [x] Leitura, cliente, memória, extração, juiz, CLI.
- [x] Testes com modelo simulado (21).
- [x] Teste local: Qwen3.5 9B no caso “farol”: 1/2 contradições, 0 alarmes, 6,2 min.
- [x] Decisão do usuário (29/09): usar a API do Claude; avaliação local interrompida.
- [x] Cliente da API (saída estruturada, esforço, fallback de recusa, cache do sistema,
      tokens e custo por chamada); Opus 5.5 como padrão.
- [x] Modo projeto: capítulos inalterados não são enviados; cache de julgamentos;
      pendências com decisão do autor (corrigida/intencional) e encerramento por edição.
- [ ] Avaliação com a API (depende da chave do usuário e de autorização de gasto).

Os textos de teste entregues como DOCX foram removidos da raiz pelo usuário; o
conteúdo está em `LumeCoerencia/avaliacao/textos.json`.

## Resultado

Pendente da avaliação com a API.
