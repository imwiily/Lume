# Lume

**Um olhar sobre o texto.**

Lume é o nome escolhido para a interface de revisão editorial. O nome remete à luz: tornar um ponto do texto visível para a avaliação humana. A identidade transmite atenção, tranquilidade e respeito pela autoria.

## Símbolo e assinatura

Um livro aberto, desenhado com traços contínuos, recebe um pequeno ponto de luz acima da dobra. O símbolo usa formas simples para funcionar no ícone do Mac e na barra lateral. A assinatura visual usa `lume` em letras minúsculas; nos textos corridos, escreva **Lume**.

- `simbolo.svg`: símbolo vetorial com fundo verde.
- `marca.svg`: composição vetorial do símbolo com o nome.
- `previa-interface.svg` e `.png`: composição ilustrativa do desenho da interface. A tipografia e os controles finais dependem do macOS; esta imagem não é captura de um aplicativo em execução.
- `Lume/Assets.xcassets/AppIcon.appiconset`: ícones em todas as dimensões declaradas para o projeto macOS.

## Paleta principal

| Cor | Código | Uso |
| --- | --- | --- |
| Verde profundo | `#173E36` | Navegação, marca e ações principais |
| Marfim | `#F4EFE5` | Fundo de leitura |
| Papel | `#FFFCF6` | Cartões e trechos |
| Tinta | `#233D34` | Texto principal |
| Texto secundário | `#5D695F` | Legendas e orientações |
| Cobre | `#97512F` | Palavra sinalizada e destaque editorial |
| Areia | `#DCB58B` | Luz do símbolo e ação sobre verde |
| Sálvia | `#E8EDE4` | Seleção de alerta e de decisão |

A aparência escura adapta fundo, texto e destaques. A barra lateral mantém o verde nas duas aparências. Vermelho discreto identifica erro confirmado; azul identifica escolha de estilo. O significado também aparece por escrito e por ícone, sem depender apenas da cor.

## Tipografia

No aplicativo, títulos e trechos usam a fonte serifada do sistema (`.serif`), enquanto botões, filtros e orientações usam a fonte padrão do macOS. Não há fontes externas para instalar. O manuscrito começa em 21 pontos, ajustáveis de 17 a 28. Os SVGs usam Georgia ou Liberation Serif como alternativas portáveis; são referências visuais, não arquivos tipográficos oficiais.

## Interface

A barra lateral reúne manuscrito, progresso e preparação da análise. A lista central apresenta pontos de atenção. A área maior à direita mostra o parágrafo, a justificativa e as decisões. Avisos e dados técnicos ficam em seções expansíveis.

A decisão selecionada recebe contorno reforçado e marca de confirmação. Os destaques do manuscrito usam cobre e sublinhado. Alterações são deliberadas: escolher uma avaliação não salta automaticamente para outro trecho.

## Linguagem

Preferir “ponto de atenção”, “avaliação” e “trecho sinalizado”. Reservar “erro confirmado” para a classificação feita pelo revisor. Evitar promessas de correção perfeita ou de treinamento automático com o feedback. O texto original é preservado.

## Continuidade

Lume é a identidade do aplicativo. O motor continua sendo FONTE 0.4.0; nomes internos, dados locais e formato JSON foram preservados para compatibilidade.
