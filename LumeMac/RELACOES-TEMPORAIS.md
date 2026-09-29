# Relações temporais — Lume 0.8 / FONTE 0.6.0

O requisito é analisar textos variados em português, sem condicionamento a personagens, enredo ou frases de uma obra. As regras novas consultam morfologia, dependências sintáticas, conectivos e um léxico geral. Os testes variam sujeitos e verbos e incluem usos legítimos. Isso demonstra generalização nos casos testados; não comprova cobertura de todos os textos, gêneros ou erros.

## Regras disponíveis

| Regra e exemplo | Resultado | Condições e limites |
| --- | --- | --- |
| “O artesão fabricaria um vaso que receberá pinturas.” | Provável erro; “receberia”; evidência em “fabricaria” | Futuro ligado por oração relativa/completiva a condicional. Referência futura explícita própria pode bloquear o alerta. A alternância pode ser intencional. |
| “A enfermeira explicava o procedimento enquanto os alunos anotam.” | Provável erro; “anotavam” | Dependência de simultaneidade com “enquanto”; não é uma comparação de quaisquer verbos próximos. Há proteção para contrastes frequentes e referências temporais próprias. |
| “O guia esperou enquanto atravessamos a ponte.” | Atenção editorial, sem substituição proposta | “Atravessamos” pode ser presente ou pretérito perfeito. O perfeito é legítimo em um intervalo concluído; a forma não é tratada como erro confirmado ou provável. |
| “O objeto parecia intacto e está quebrado.” | Atenção editorial; “estava” como alternativa | Coordenação sob passado, inclusive caminhos sintáticos intermediários. Pode haver mudança legítima para o presente do narrador ou uma consequência ainda válida. |
| “Os operários construiam casas.” | Provável erro; “construíam” | Eixo passado configurado/inferido, verbo principal, sujeito expresso e forma acentuada confirmada no léxico. A mesma família cobre “caiam”, “saiam”, “distribuiam” e outras formas; não há troca cega por grafia. |
| “— O que? Tô surpreso..” | “que” → “quê”; dois pontos finais para conferência | Também examina falas/pensamentos. Preserva “tô”, “cê”, “pra”, reticências de três ou mais pontos e interrogação expressiva. |

As sugestões ficam separadas do manuscrito. As evidências registram o verbo que fundamenta a relação, com seu parágrafo e intervalo exato. Os números de confiança representam força heurística do indício, sem calibração estatística.

## Proteções e configuração

- Relações temporais seguem os escopos de tempo verbal, com narração como padrão. Falas e pensamentos só entram nessa regra quando selecionados. Orações de falas diferentes não são concatenadas para inventar uma dependência.
- Acentuação contextual examina narração no eixo passado. Indícios como “talvez”, “que”, “caso” e “se”, pergunta/exclamação e certos sujeitos de tratamento impedem a sugestão. Formas já acentuadas, inclusive com Unicode decomposto, permanecem intactas.
- Pontuação duplicada, espaços e quê final alcançam narração, diálogo e pensamento. As outras regras sintáticas determinísticas continuam restritas à narração.
- As três chaves novas podem ser desligadas separadamente. Configurações completas antigas com todas as regras desligadas não reativam verificações.
- O alerta temporal específico substitui o alerta genérico de tempo sobre o mesmo verbo. A evidência nova produz uma ocorrência distinta; decisões antigas não são atribuídas por semelhança.

## Limitações observadas

O modelo pequeno de português pode errar classe, modo ou dependência. Em “O motor vibrava enquanto a peça gira.”, o modelo usado nesta entrega classifica “gira” como adjetivo. A nova regra se abstém e deixa de apontar a possível alternância. Essa omissão está registrada em teste; aprovação do teste não significa que o erro passou a ser detectado.

Os bloqueios de tempo explícito e de predicados estativos são conservadores. Podem evitar falsos positivos e também ocultar problemas reais. A recuperação lexical de certas formas condicionais ajuda, mas não substitui uma análise sintática correta. Formas ambíguas como “caminhamos” não revelam sozinhas qual tempo o autor pretendia.

“O cientista explicou que a água ferve a cem graus.” e futuros legítimos de discurso relatado não recebem alerta das **novas regras de relação** nos testes. A regra anterior de tempo predominante é separada e ainda pode produzir atenção editorial nesses casos quando ativada. O exemplo Temporal a desliga para permitir a inspeção isolada das regras novas.

Acentuação depende de contexto limitado e pode deixar escapar sujeitos implícitos, subordinadas e análises incertas. No modo automático, se não houver eixo passado inferido, essa regra não decide. Não há correção ortográfica geral embutida nesta família.

Os exemplos são sintéticos e conhecidos durante o desenvolvimento. Não houve avaliação independente em corpus anotado de autores/gêneros variados, medição de precisão/recall nem revisão do manuscrito completo de Hikari No Sekai nesta entrega.

## Continuação do projeto

Permanecem pendentes: vocativos confiáveis, concordância mais ampla, ligação por travessão entre fala e ação, resolução semântica de referentes, banco de fatos entre capítulos e Auditor Final independente. A próxima ampliação deve usar exemplos anotados de diferentes textos, preservar as contraprovas e distinguir erros prováveis de dúvidas editoriais.

O contrato modular permanece descrito em `IMPLEMENTACAO-MESTRE.md`; resultados de verificação e passos no Mac estão em `VERIFICACAO.md`.
