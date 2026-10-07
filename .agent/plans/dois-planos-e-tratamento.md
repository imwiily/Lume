# Narração no passado com dois planos, marcas não narrativas e tratamento tu/você

Pedido do autor (agenda de 07/10/2026). Os casos vieram de um texto de terceiros narrado no
passado (61 alertas, 33 de tempo verbal na versão 1.6) e de pendências antigas. O texto real serve
só para identificar as classes; os testes e o corpus são escritos do zero, com outras palavras e
outros nomes.

## Objetivo e escopo

1. Fala que começa numa linha do meio do parágrafo (quebra de linha manual + travessão ou hífen)
   era lida como narração. Esperado: cada linha pode abrir fala; a fala aberta continua na linha
   seguinte só se essa linha a fechar (“… - disse ela.”); linha sem fechamento não é engolida.
2. Narrador em primeira pessoa falando de si no presente numa história no passado (“me chamo”,
   “sou” + nome/adjetivo, “acho/sinto/confesso que”, “vou contar”, “quem eu sou”). Esperado: sem
   alerta de tempo. Continuam alertando: ação da cena (“Abro a janela”, “Sinto o frio”), passiva
   (“Sou empurrado”), “Vou até…”, e o comentário precedido de um passado na mesma frase
   (“Quando o barco atracou, sinto que…”), que o prende à cena.
3. Lista ou rótulo (linha sem pontuação final só com iniciais maiúsculas e números: “Equipe 2 Ana
   Rui”, “Parte 3”). Esperado: sem tempo verbal nem “Pontuação final ausente”.
4. Tratamento misto: ‘você’ e verbo na forma de ‘tu’ no mesmo trecho. Regra nova `tratamento`,
   atenção editorial, confiança .6, desligável nos ajustes. A mistura entre falas diferentes do
   mesmo personagem exige saber quem fala e fica fora.
5. ‘era’ nome depois de determinante + adjetivo e antes de verbo ou ‘de’ (“Uma nova era começa”).

Fora do escopo: nota do autor antes do primeiro capítulo, marcador de ponto de vista e
adjetivo sozinho depois de ponto, lido como verbo (ambíguos), discurso sem marca de fala, palavra estrangeira sem itálico
(o LanguageTool já baixa a confiança e lembra o itálico), e “Olho”/“Corri… entro” no início da
frase sem sujeito: o modelo pequeno não os etiqueta como verbo, e forçar a leitura verbal traria
alarmes em “Grito no corredor.” ou “Passo a passo…”.

## Arquivos

- `fonte/fonte/segments.py`: fala por linha.
- `fonte/fonte/temporal.py`: `narrator_frame` em `legitimate_present`; lista/rótulo fora.
- `fonte/fonte/analysis.py`: `lista_ou_rotulo`; tempo verbal ignora lista/rótulo.
- `fonte/fonte/grammar.py`: regra `tratamento`; “Pontuação final ausente” ignora lista/rótulo.
- `fonte/fonte/lexicon.py`: ‘era’ nome depois de determinante + adjetivo.
- `fonte/fonte/settings.py`, `app/Lume/Models.swift`: regra `tratamento` (nova, ligada por padrão).
- Testes: `fonte/tests/test_dois_planos_e_marcas.py`, `fonte/tests/test_tratamento.py`; corpus
  `dev-narrador-e-listas`; categoria `tratamento` em `tests/test_detection_benchmark.py`.

## Medidas

Linha de base: o motor de hoje com as cinco mudanças desligadas por patch (script fora do
repositório, `segments.py` de HEAD), sem LanguageTool, a partir de cópias no scratchpad.

## Progresso

- [x] Reprodução no texto de terceiros e testes que falham antes (14 falhas).
- [x] Correções; ajustes depois da comparação real: fala aberta que continua na linha que a
  fecha; passado anterior prende o comentário do narrador à cena; contrações fora do tratamento.
- [x] FONTE 408 testes, Coerencia 25, pacotes 29, contrato Python, contratos Swift (exemplo e
  relatório novo), mesa, edição, falsos positivos, decisões por livro, build Debug do app.
- [x] Corpus `todos`: linguística 65/84 → 66/85 (tratamento 1/1, nenhum perdido); ocorrências
  88 → 82; alarmes falsos 12 → 9; ocorrências sobre trechos aceitáveis 10 → 6.
- [x] A: 64 → 63 (sai “sou” + predicado na voz do narrador, ambíguo: pode ser pensamento da
  cena). B 15 → 15 e C (presente) 29 → 29, sem diferença. Texto de terceiros 61 → 39 (22 saíram, nenhum
  entrou). A regra de tratamento não aponta nada nos quatro textos.
