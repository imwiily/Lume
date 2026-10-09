# Visão do Projeto Lume

O **Lume** deve evoluir de um corretor textual para um **revisor editorial mestre**, capaz de analisar um manuscrito em diferentes níveis de profundidade, de forma organizada, sequencial e verificável.

O objetivo não é apenas encontrar erros ortográficos ou gramaticais. O Lume deve funcionar como uma ferramenta de apoio editorial completa, capaz de identificar desde erros objetivos da língua portuguesa até problemas de coerência narrativa, continuidade, construção de diálogos, consistência temporal, referências ambíguas e contradições internas da obra.

A filosofia central do projeto é simples:

> **O Lume interrompe o editor só quando há evidência suficiente para justificar a interrupção.**
>
> **Poucos alertas. Alta confiança. Alto valor editorial. Um ponto de encerramento claro.**

O objetivo não é tornar impossível encontrar outro erro depois do Lume. É tornar improvável que
um problema relevante passe despercebido, sem tornar a revisão interminável. **O manuscrito
precisa poder chegar ao fim.**

Um alerta tem custo: o editor para a leitura, procura o contexto, interpreta, decide, registra e,
se o alerta for ruim, passa a desconfiar dos próximos. Por isso a precisão vale tanto quanto a
cobertura. Um detector que encontra quase tudo mas produz dezenas de dúvidas inúteis é pior, na
prática editorial, do que um que encontra um pouco menos e quase nunca interrompe sem razão.

O Lume não promete que nenhum erro restante existe. Ele é uma ferramenta conservadora de
auditoria editorial: quando ele interrompe, há uma boa razão para olhar. O sistema distingue
**erro confirmado**, **provável erro**, **atenção editorial**, **possível inconsistência** e
**consulta ao autor**, e separa o que é pendência do que é só informação (ver
[Ocorrência, pendência e encerramento](#ocorrência-pendência-e-encerramento)).

O Lume não substitui o editor.

---

## Arquitetura geral

O processo de revisão não deve mais acontecer de forma misturada.

O manuscrito deve passar por uma sequência de módulos especializados, sendo que cada módulo termina sua análise antes do próximo começar.

A ordem será:

**Manuscrito original  
→ Módulo Linguístico  
→ Módulo Morfossintático  
→ Módulo Editorial de Contexto Curto  
→ Módulo de Coerência Global  
→ Auditor Final  
→ Relatório editorial completo**

O manuscrito original deve permanecer **imutável durante todo o processo**.

Nenhum módulo pode alterar automaticamente o texto antes de todas as análises terminarem.

As correções são apenas sugestões. A decisão final pertence ao editor.

Isso é essencial porque alterações prematuras poderiam modificar offsets, frases, parágrafos e contexto utilizados pelos módulos seguintes.

---

# Módulo 1 — Revisão Linguística Determinística

O primeiro módulo será responsável pelos problemas linguísticos mais objetivos.

Ele deve procurar aquilo que, em condições normais, não deveria escapar de uma revisão automática.

Entram nesse módulo:

- ortografia;
- acentuação;
- erros de digitação;
- pontuação duplicada;
- espaços incorretos;
- maiúsculas e minúsculas;
- vocativos;
- concordância simples;
- regências muito seguras;
- vírgulas estruturalmente impossíveis;
- construções gramaticais inválidas conhecidas;
- padrões linguísticos de alta confiança.

Exemplos:

> as folhas secas **caiam**

deve ser identificado como provável erro de:

> as folhas secas **caíam**

Outro exemplo:

> não restava nada **além de disso**

deve ser detectado porque a construção é inadequada.

Também:

> Esses turistas**.. São** tão curiosos

deve gerar uma ocorrência de pontuação.

Esse módulo deve ser altamente determinístico e conservador.

Quando uma regra for realmente segura, o resultado poderá ser classificado como:

**ERRO CONFIRMADO**

A prioridade aqui é uma combinação de **cobertura alta e baixíssimo índice de falso positivo**.

O Fonte-Revisor atual deve ser reaproveitado como base deste módulo em vez de ser descartado.

---

# Módulo 2 — Análise Morfossintática

Depois que a revisão linguística terminar, o manuscrito deve passar por uma análise estrutural mais profunda.

Esse módulo precisa compreender a relação entre:

- verbos;
- sujeitos;
- objetos;
- tempos verbais;
- modos verbais;
- orações;
- subordinadas;
- coordenações;
- verbos de elocução;
- ações simultâneas;
- relações temporais.

Seu principal objetivo é encontrar erros que não podem ser detectados apenas por palavras isoladas.

Por exemplo:

> disse ela enquanto **seguimos** até a praça

O módulo deve perceber que a ação descrita ocorre no mesmo contexto passado de “disse”, tornando:

> seguíamos

uma possibilidade muito mais coerente.

Outro exemplo:

> Ele **iria** propor um plano que **irá** ser muito caro.

O sistema deve perceber o conflito entre:

> iria

e:

> irá

dentro da mesma projeção temporal.

O resultado poderia ser:

**PROVÁVEL ERRO — COERÊNCIA TEMPORAL**

com uma explicação semelhante a:

> A frase combina futuro do pretérito e futuro do presente dentro da mesma projeção narrativa. Verifique se “seria muito caro” expressa melhor a relação temporal pretendida.

O objetivo não é apenas dizer que algo está errado.

O Lume deve explicar **por que aquilo foi sinalizado**.

---

# Módulo 3 — Revisão Editorial de Contexto Curto

A partir desse módulo, o Lume deixa de olhar apenas para frases individuais.

Ele começa a trabalhar com blocos maiores de texto, como:

- parágrafo atual;
- parágrafos anteriores;
- parágrafos seguintes;
- sequência de falas;
- pequena cena.

Esse módulo deve analisar questões como:

- diálogo mal estruturado;
- inciso de fala incorreto;
- pensamento confundido com diálogo;
- quebra de ponto de vista;
- repetição involuntária;
- referente ambíguo;
- objeto introduzido de forma confusa;
- sequência de ações difícil de acompanhar;
- informação repetida desnecessariamente;
- mudança repentina de foco;
- problemas de clareza narrativa.

Um exemplo seria:

> — Você entendeu o que eu disse, Helena — a voz de Helena falhou de repente.

O problema não é simplesmente pontuação.

O sistema deve entender que:

> a voz de Helena falhou de repente

não é uma oração de elocução.

Então o Lume poderia apresentar:

**ATENÇÃO EDITORIAL**

> O trecho após o travessão parece ser uma ação narrativa independente, e não um inciso de elocução. Considere encerrar a fala antes da descrição.

Outro exemplo seria uma cena em que a personagem utiliza:

> o dispositivo

para criar fumaça e, pouco depois, aparece outro:

> o dispositivo

com uma função completamente diferente.

O sistema poderia indicar:

**REFERENTE POSSIVELMENTE AMBÍGUO**

> Dois objetos aparentemente diferentes são chamados de “o dispositivo” em uma sequência muito próxima. Considere identificá-los de forma distinta.

Essa camada deve se comportar mais como um **revisor editorial humano** do que como um corretor gramatical tradicional.

---

# Módulo 4 — Coerência Global

Este será um dos módulos mais importantes do Lume.

Ele deve analisar a obra como um todo.

Antes de procurar inconsistências, o sistema deve construir uma espécie de **memória interna do manuscrito**.

Essa memória poderá registrar fatos como:

## Personagens

### Personagem A
- irmã: Personagem B;
- profissão: relojoeira;
- condição inicial: não sabe nadar.

### Personagem C
- aluno do último ano;
- habilidade apresentada: memória fotográfica.

## Lugares

- escola da cidade;
- vilarejo vizinho;
- hospital próximo à casa da Personagem A.

## Objetos

- relógio de bolso;
- bicicleta;
- mapa antigo;
- lanterna.

## Regras do mundo

- a ponte fecha à noite;
- a cidade não tem energia elétrica;
- cartas levam três dias para chegar.

A partir disso, o módulo deve procurar inconsistências posteriores.

Por exemplo:

> A Personagem C tem memória fotográfica.

E posteriormente:

> A Personagem C não conseguia lembrar o rosto que tinha visto um minuto antes.

O Lume não deve afirmar automaticamente que existe um erro.

Ele deve apresentar algo semelhante a:

**POSSÍVEL INCONSISTÊNCIA DE CARACTERIZAÇÃO**

> A memória fotográfica da Personagem C foi apresentada antes. Neste trecho, ela não lembra um rosto visto há pouco. Isso pode ser intencional, mas a relação entre os dois trechos ainda não está clara no texto.

Outros exemplos que esse módulo deve conseguir detectar futuramente:

- personagem com idade diferente em capítulos distintos;
- nome escrito de formas diferentes;
- relação familiar contraditória;
- personagem sabendo algo que ainda não deveria saber;
- objeto destruído reaparecendo posteriormente;
- personagem afirmando nunca ter feito algo que já fez;
- distância ou duração de viagem incompatível;
- cronologia impossível;
- poderes funcionando de formas contraditórias;
- regras do universo sendo quebradas sem explicação;
- mudança de localização sem transição;
- personagem presente em dois lugares incompatíveis.

Esse módulo deve funcionar como um **revisor de continuidade**.

---

# Auditor Final

Depois que os quatro módulos terminarem, o manuscrito pode passar por uma última etapa, opcional.

O Auditor Final é principalmente o **controle de qualidade do próprio Lume**. Ele relê o texto com
as ocorrências já emitidas e procura o que os módulos deixaram passar, mas nem todo achado dele vira
trabalho para o editor:

- **achados sólidos** (categoria objetiva, trecho conferido, correção mínima) → revisão editorial,
  nunca como impedimento;
- **achados fracos ou experimentais** → diagnóstico do motor, para melhoria futura, fora da mesa.

O número de achados novos do Auditor não mede a maturidade do Lume. Mede-se quantos achados
promovidos se confirmaram como erro real. Um achado do Auditor também não cria automaticamente
uma regra: ele passa pela mesma pergunta de qualquer falso negativo (ver
[Falsos negativos](#falsos-negativos)).

---

# Classificação das ocorrências

O Lume não deve tratar tudo como erro.

As ocorrências devem possuir níveis diferentes.

Uma possível classificação é:

## Erro confirmado

Algo linguisticamente muito seguro.

Exemplo:

> além de disso

## Provável erro

Há forte evidência, mas ainda existe alguma possibilidade contextual.

Exemplo:

> venderia o carro que ninguém irá comprar

## Atenção editorial

Não existe necessariamente erro gramatical, mas o trecho merece revisão.

Exemplo:

> dois objetos diferentes chamados apenas de “o dispositivo”.

## Possível inconsistência

Um fato parece contradizer outro trecho da obra.

Exemplo:

> gravidade × pressão do ar.

## Consulta ao autor

O editor não deve decidir sozinho.

Exemplo:

> “poderiam vê-los”, sem referente claro.

Isso é fundamental para evitar um dos problemas encontrados em ferramentas como LanguageTool: transformar decisões estilísticas ou narrativas em “erros gramaticais”.

A severidade diz **que tipo** de problema é. Ela não decide sozinha se o alerta vira trabalho:
isso é o destino, abaixo.

---

# Ocorrência, pendência e encerramento

Quatro coisas diferentes, que não devem ser confundidas:

1. **Ocorrência detectada:** tudo o que uma etapa encontrou e passou pela conferência do trecho.
2. **Informação:** ocorrência mostrada de forma recolhida, que não conta como pendência nem pede
   decisão.
3. **Pendência editorial:** ocorrência que entra na fila e pede decisão.
4. **Impedimento:** pendência que precisa de decisão antes de encerrar a revisão.

Há ainda o **diagnóstico**: o que o motor detectou com evidência fraca ou em caráter experimental.
Fica fora da mesa e serve só para medir e melhorar o Lume.

O destino de cada classe (regra × confiança) vem de uma **política versionada**, calibrada com a
precisão medida nas decisões reais dos editores. **A confiança é evidência auxiliar; o destino
editorial é decidido pela política.** Com amostra suficiente, os dados prevalecem sobre o rótulo:
o diálogo contextual, marcado com confiança baixa, acertou 91% em 32 decisões e continua na fila.

- **Observação:** uma classe com pelo menos 20 decisões e menos de 50% de erro real sai da fila.
  Esse limiar é um **critério de não-interrupção, não de qualidade**: uma classe com 49% não é
  “boa”; apenas não é confiável o bastante para interromper o editor, e sua qualidade continua
  acompanhada pelas métricas. Classes de confiança baixa sem 20 decisões também começam como
  observação.
- **Pendência** significa só que a classe ainda merece atenção editorial segundo a política atual.
  Não é afirmação de que a regra é confiável.

Uma classe só é **impeditiva** se tiver ao mesmo tempo:

- precisão real de 90% ou mais, com pelo menos 20 decisões;
- natureza objetiva e determinável (crase, homófonos, concordância, pontuação duplicada,
  espaçamento, construção inválida, quê tônico, acentuação contextual, “que, não” e o corretor
  ortográfico e gramatical). A natureza objetiva é propriedade da classe, não sinônimo de
  impeditivo;
- severidade de erro confirmado ou provável erro.

Precisão e gravidade são dimensões diferentes: classes editoriais, narrativas, de repetição,
referência, estilo ou continuidade interpretativa nunca são impeditivas, mesmo com precisão alta.
Uma classe nova começa como informação ou diagnóstico e só sobe com medição em livros reais.

## Revisão concluída

Zero ocorrências não é o critério. Um livro pode estar pronto com construções intencionais, falsos
positivos decididos, escolhas de estilo aceitas e observações que o editor escolheu não abrir.

O editor pode **encerrar a revisão** quando nenhum impedimento estiver sem decisão. O encerramento
registra quantas observações e pendências não impeditivas ficaram abertas, a data, a versão do
motor e a versão da política. O estado final se chama **Revisão concluída**.

O Lume não certifica perfeição, nem “texto sem erros”. Ele certifica que o processo de auditoria
definido terminou.

Decisões já tomadas (falso positivo, intencional, estilo do autor, aceito editorialmente,
corrigido) continuam valendo e não deixam o livro “inacabado”. Uma decisão só reabre com evidência
nova: o parágrafo mudou.

---

# Preservação da voz do autor

O Lume deve respeitar a identidade textual da obra.

Ele não deve tentar transformar automaticamente uma escrita juvenil, informal, coloquial ou estilizada em português acadêmico.

Expressões como:

> tô  
> cê  
> pra  
> cara  
> mano

podem ser perfeitamente adequadas dentro de diálogos.

O sistema deve aprender a distinguir:

**voz do personagem**

de:

**erro da narrativa**

Da mesma forma, uma quebra deliberada de regra pode ser válida quando existe intenção estilística.

O papel do Lume é sinalizar e explicar.

Não decidir sozinho.

---

# Sistema de decisões editoriais

O Lume deve registrar as decisões do editor.

Quando uma ocorrência for apresentada, o editor poderá marcar, por exemplo:

- Corrigido;
- Erro confirmado;
- Falso positivo;
- Intencional;
- Estilo do autor;
- Aceito editorialmente.

Essas decisões alimentam a **medição de precisão** de cada classe, que define a política de
destino. Elas não criam exceções automáticas.

Mas o aprendizado não deve ser cego.

Se um editor marcar uma ocorrência como falso positivo, isso não significa que toda ocorrência semelhante deverá ser automaticamente ignorada no futuro.

O sistema deve armazenar:

- trecho;
- contexto;
- regra;
- categoria;
- decisão;
- justificativa quando disponível.

---

# Corpus de testes

O projeto deve possuir uma suíte de testes editoriais.

Um manuscrito real do autor (**manuscrito A**) será inicialmente um dos principais corpora de validação.

Já temos três tipos de exemplos extremamente úteis:

## Erros detectados corretamente

Casos em que o Lume atual funcionou.

## Falsos positivos

Casos em que o Lume indicou algo que o editor decidiu manter.

## Falsos negativos

Erros reais que o Lume não encontrou.

Encontrar um falso negativo **não** significa criar uma regra. A pergunta é:

> Este erro pertence a uma classe generalizável, relevante e detectável com boa precisão o
> bastante para justificar um novo alerta?

Se a resposta for não, o erro fica fora da cobertura automática. Isso não é fracasso; é a
delimitação responsável do sistema.

Exemplos históricos de falsos negativos que viraram testes:

> luz, que, não era comum

> seguimos até a praça

> iria propor um plano que irá ser muito caro

> nada além de disso

> apenas você Clara

> as folhas secas caiam

Quando a classe passa pela pergunta acima, o caso vira teste automático, escrito do zero.

Por exemplo:

```text
TESTE: LUME-TEMP-001

Entrada:
"Ele iria propor um plano que irá ser muito caro."

Resultado esperado:
categoria: temporal_consistency
módulo: morphosyntactic
severidade: probable_error
```

Antes de uma nova versão do Fonte-Revisor ser distribuída, todos os testes devem ser executados.

Se uma atualização fizer o sistema deixar de detectar um erro que já conseguia encontrar anteriormente, ocorre uma **regressão**. Também é regressão uma atualização que baixa a precisão das pendências: alertas novos que interrompem sem razão.

A versão não deve ser considerada pronta até que isso seja analisado.

---

# Formato comum de ocorrências

Todos os módulos devem produzir resultados em um formato padronizado.

Por exemplo:

```json
{
  "id": "FR-000142",
  "module": "morphosyntactic",
  "category": "temporal_consistency",
  "severity": "probable_error",
  "confidence": 0.96,
  "range": {
    "start": 18432,
    "end": 18491
  },
  "excerpt": "Ele iria propor um plano que irá ser muito caro.",
  "message": "Possível incompatibilidade entre futuro do pretérito e futuro do presente.",
  "suggestion": "Ele iria propor um plano que seria muito caro."
}
```

Isso separa completamente:

**motor de revisão**

de:

**interface do Lume**.

O aplicativo Swift não precisa saber como um problema foi descoberto.

Ele apenas recebe a ocorrência e a apresenta ao usuário.

---

# Aplicativo Lume e Fonte-Revisor

O projeto deve continuar separado em duas partes.

## Lume.app

Responsável por:

- interface Swift;
- abertura de manuscritos;
- exibição de ocorrências;
- navegação pelo texto;
- filtros;
- decisões do editor;
- progresso da revisão;
- atualização do motor;
- relatórios.

## Fonte-Revisor

Responsável por:

- análise linguística;
- análise morfossintática;
- análise editorial;
- coerência global;
- auditoria;
- regras;
- modelos;
- testes.

O Fonte-Revisor deve continuar podendo ser **atualizado independentemente do aplicativo**.

Assim, novas regras, modelos e módulos poderão ser distribuídos sem exigir uma nova versão completa do Lume.

---

# Progresso da análise

O aplicativo deve mostrar claramente em qual etapa está.

Em vez de simplesmente mostrar:

> Analisando manuscrito...

o ideal seria algo semelhante a:

```text
Revisão Mestre

✓ Revisão linguística
  34 ocorrências

✓ Análise morfossintática
  11 ocorrências

● Revisão editorial
  Cena 17 de 41

○ Coerência global

○ Auditoria final
```

Quando tudo terminar, o editor poderá filtrar os resultados por módulo:

```text
Todas                 72
Linguístico           31
Morfossintático       14
Editorial             18
Coerência global       6
Auditoria               3
```

Também deve ser possível filtrar por severidade.

---

# Precisão antes de cobertura irrestrita

Para problemas de evidência fraca, o Lume prefere **não interromper** o editor. Uma dúvida de
baixa confiança não tem o mesmo peso de um erro objetivo: ela fica como informação, como
diagnóstico do motor ou não é emitida.

O sistema busca reduzir a chance de um problema relevante passar, sem transformar cada frase
discutível em pendência. A métrica principal é a precisão das pendências (quantas justificavam a
interrupção), ao lado da cobertura nos erros relevantes, e não a cobertura máxima.

O Lume não deve virar:

- um revisor literário opinativo;
- um detector de qualquer coisa incomum;
- um gerador de possibilidades;
- um substituto do editor;
- uma ferramenta que precise chegar a zero alertas;
- uma ferramenta que aprende uma regra nova para cada erro isolado encontrado depois;
- uma máquina otimizada só para a pontuação em corpus sintético.

---

# Desenvolvimento incremental

A versão atual do Lume não deve ser descartada.

A reestruturação deve acontecer de maneira incremental.

O código funcional existente deve ser preservado sempre que possível.

O Fonte-Revisor atual deve inicialmente ser reorganizado como o **Módulo Linguístico**.

Depois devem ser adicionados:

1. **Módulo Morfossintático**;
2. **Módulo Editorial**;
3. **Coerência Global**;
4. **Auditor Final**.

Cada módulo deve possuir seus próprios testes antes que o próximo seja considerado concluído.

---

# Objetivo final

O Lume não deve ser apenas um programa que diz:

> “há uma vírgula errada aqui”.

A visão de longo prazo é que ele consiga dizer:

> “Esta vírgula está incorreta por esta razão.”

> “Este verbo parece incompatível com o tempo narrativo estabelecido.”

> “Esta ação após o diálogo não parece ser um verbo de elocução.”

> “Não ficou claro a qual objeto este pronome se refere.”

> “Este personagem afirma algo incompatível com o capítulo 3.”

> “A habilidade foi anteriormente definida como gravidade; aqui aparece como pressão do ar. Verifique se a relação é intencional.”

O objetivo é uma **primeira leitura editorial confiável**, que deixa para o editor humano aquilo que
exige interpretação, gosto, intenção autoral e decisão editorial, e que sabe quando terminou.

Em outras palavras:

> **Quando o Lume interrompe, há uma boa razão para olhar.  
> O editor decide o que fazer.  
> E a revisão chega ao fim.**

Essa é a visão central do **Lume como Revisor Mestre**.
