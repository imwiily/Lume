# Visão do Projeto Lume

O **Lume** deve evoluir de um corretor textual para um **revisor editorial mestre**, capaz de analisar um manuscrito em diferentes níveis de profundidade, de forma organizada, sequencial e verificável.

O objetivo não é apenas encontrar erros ortográficos ou gramaticais. O Lume deve funcionar como uma ferramenta de apoio editorial completa, capaz de identificar desde erros objetivos da língua portuguesa até problemas de coerência narrativa, continuidade, construção de diálogos, consistência temporal, referências ambíguas e contradições internas da obra.

A filosofia central do projeto é simples:

> **Tudo aquilo que mereceria a atenção de um revisor profissional antes da publicação deve, idealmente, ser apresentado pelo Lume.**

Isso não significa que toda ocorrência encontrada seja necessariamente um erro. O sistema deve distinguir claramente entre **erro confirmado**, **provável erro**, **atenção editorial** e **consulta ao autor**.

O Lume não deve substituir o editor. Ele deve ampliar sua capacidade de leitura e reduzir drasticamente a possibilidade de um problema passar despercebido.

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

> A frase combina futuro do pretérito e futuro do presente dentro da mesma projeção narrativa. Verifique se “não seria nada boa” expressa melhor a relação temporal pretendida.

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

> — Você entendeu o que eu disse, Helena — o rosto de Helena ficou todo vermelho.

O problema não é simplesmente pontuação.

O sistema deve entender que:

> o rosto de Helena ficou todo vermelho

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

Depois que os quatro módulos terminarem, o manuscrito deve passar por uma última etapa.

O Auditor Final não será apenas outro tipo de revisão.

Ele será o **controle de qualidade dos quatro módulos anteriores**.

Ele receberá:

- o manuscrito completo;
- todas as ocorrências já encontradas;
- o banco de fatos da obra;
- as análises anteriores;
- as áreas já consideradas seguras.

Sua missão será:

> **Procure problemas relevantes que os outros módulos deixaram passar.**

O auditor deve evitar repetir ocorrências existentes.

Ele deve procurar apenas novos problemas.

Isso também permitirá medir a qualidade dos módulos.

Por exemplo:

> Módulos principais: 182 ocorrências  
> Auditor final: 27 novas ocorrências

significa que ainda existem falhas importantes nos módulos.

Já:

> Módulos principais: 182 ocorrências  
> Auditor final: 2 novas ocorrências

indica que o sistema está amadurecendo.

A meta de longo prazo é fazer com que o Auditor encontre cada vez menos problemas novos.

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

> iria fazer algo que não irá ser bom

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

- Corrigir;
- Ignorar;
- Falso positivo;
- Intencional;
- Consultar autor;
- Adicionar exceção.

Essas decisões devem poder alimentar o Fonte-Revisor.

Isso permitirá que o sistema melhore ao longo do tempo.

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

Esses falsos negativos são especialmente importantes.

Exemplos:

> luz, que, não era comum

> seguimos até a praça

> iria propor um plano que irá ser muito caro

> nada além de disso

> apenas você Clara

> as folhas secas caiam

Cada um desses trechos deve virar um teste automático.

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

Se uma atualização fizer o sistema deixar de detectar um erro que já conseguia encontrar anteriormente, ocorre uma **regressão**.

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

# Filosofia de cobertura

O Lume Mestre deve ter uma filosofia diferente de um corretor convencional.

Para problemas de baixa confiança, é preferível:

> mostrar uma dúvida claramente identificada como dúvida

do que:

> esconder um possível problema importante.

Porém, isso não significa inundar o usuário de alertas.

Por isso a distinção entre:

- erro;
- provável erro;
- atenção;
- inconsistência;
- consulta.

O sistema deve procurar **alta cobertura sem perder honestidade sobre a confiança da análise**.

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

> “Os quatro revisores não sinalizaram este problema, mas a auditoria final encontrou uma possível inconsistência.”

O objetivo é transformar o Lume em uma ferramenta capaz de realizar uma **primeira leitura editorial extremamente profunda**, deixando para o editor humano principalmente aquilo que realmente exige interpretação, gosto, intenção autoral e decisão editorial.

Em outras palavras:

> **O Lume deve encontrar o problema.  
> O editor deve decidir o que fazer com ele.**

Essa é a visão central do **Lume como Revisor Mestre**.
