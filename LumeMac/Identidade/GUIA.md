# Lume · Luz de leitura

**Uma luz acesa ao lado de quem escreve.**

Lume ilumina um ponto do texto e devolve a decisão a quem escreve. A identidade parte
de uma cena simples: um livro aberto à noite e uma chama que acompanha a leitura. Ela
não julga o texto, só mostra onde olhar.

## Valores

| Valor | Como aparece |
| --- | --- |
| **Poética** (central) | A chama sobre o livro. Títulos em serifada. Frases como “Que texto vamos iluminar hoje?” e “Por que acendemos esta luz”. |
| **Carinhosa** (central) | Saudação pelo horário. Alertas tratados como perguntas (“Cada alerta é uma pergunta, não uma sentença”). O trecho recebe uma luz rosada ao fundo, sem vermelho agressivo. |
| **Elegante** (central) | Poucas cores, bastante respiro, cantos contínuos, sombras leves e hierarquia pela tipografia. |
| Valorizada | O texto do autor aparece numa página de papel, em corpo grande e ajustável, e nunca é alterado. |
| Amigável | Linguagem direta, botões em cápsula, arrastar e soltar o manuscrito. |
| Acessível | Contraste AA em todas as cores de texto nos dois modos. O sentido nunca depende só da cor. Há atalhos de teclado e rótulos para leitores de tela. |
| Esperta | Filtros recolhidos num só botão, anel de progresso das avaliações e atalhos ⌘1–⌘6 e ⌘[ / ⌘]. |
| Bela | Gradiente noturno, brilho de vela e tipografia de livro. |
| Agregadora | Língua e história lado a lado, e a Coerência com IA integrada à mesma leitura. |

## Símbolo e nome

Uma chama de vela (gradiente de vela a rosa) paira sobre um livro aberto, desenhado com
duas linhas de página em cor de linho. O fundo é um quadrado de cantos contínuos na cor
noite, com um halo dourado atrás da chama. Nos textos corridos, escreva **Lume** com
inicial maiúscula.

- `simbolo.svg`: o símbolo em vetor, com geometria igual à de `LumeMark` em `Lume/LumeTheme.swift`.
- `marca.svg`: o símbolo acompanhado do nome em New York.
- `previa-*.png`: capturas reais da interface, renderizadas pelo próprio app (veja abaixo).
- `Lume/Assets.xcassets/AppIcon.appiconset`: o ícone em todos os tamanhos, gerado do mesmo desenho.

## Paleta

Cores de marca, iguais nos dois modos:

| Nome | Código | Uso |
| --- | --- | --- |
| Noite | `#2A1F3D` → `#1B1428` | Trilho lateral, símbolo, seleção forte |
| Vela | `#F2C46D` | Ação principal, luz do símbolo, progresso |
| Rosa-chama | `#E7A493` | Fim do gradiente da chama e do anel |
| Linho | `#F7F1EA` | Traço do livro, texto sobre noite |

Cores de interface (claro / escuro):

| Papel | Claro | Escuro | Uso |
| --- | --- | --- | --- |
| Fundo | `#F7F1EA` | `#18131F` | Tela |
| Papel | `#FFFCF7` | `#221B2D` | Cartões, página de leitura |
| Lavanda | `#EEE7F4` | `#2E2540` | Seleção, sugestões, avisos suaves |
| Linha | `#E6DCD2` | `#3A3047` | Contornos |
| Tinta | `#2B2238` | `#F4EDE4` | Texto principal |
| Texto secundário | `#6A5F74` | `#B8ACC2` | Legendas |
| Ameixa | `#5B3F8C` | `#CDB8F2` | Destaques interativos, seleção |
| Rosa-argila | `#A24E3E` | `#F0A898` | Palavra sinalizada, atenção editorial |
| Luz do trecho | `#F8DCCF` | `#5A3A3A` | Fundo do trecho sinalizado |
| Carmim | `#A8323F` | `#F49AA4` | Erro |
| Anil | `#3F55A0` | `#AFC0F5` | Estilo do autor, consulta ao autor |
| Sálvia | `#3A7257` | `#9ED2B5` | Falso positivo, aceito |
| Âmbar | `#8A5A12` | `#F2C46D` | Intencional, possível inconsistência |

Todas as cores de texto têm contraste de pelo menos 4,5:1 sobre fundo, papel e lavanda
do mesmo modo. Vela sobre Noite (e o inverso) chega a 9,5:1. Cada decisão tem cor,
ícone e nome escrito.

## Tipografia

- **New York** (`design: .serif`): voz e leitura. Saudações, títulos, o trecho do
  manuscrito e as sugestões.
- **SF Pro Rounded** (`design: .rounded`): a interface. Rótulos, explicações, botões e
  números.
- O rótulo pequeno (`Kicker`) vai em versalete espaçado, precedido de uma chama.

## Telas

1. **Início**: saudação pelo horário, área para arrastar o manuscrito e três cartões de
   leitura (A língua, A história, Leitura completa). Abaixo vêm dois blocos: A língua
   (tempo da narração, corretor local) e A história (Coerência com IA, comparação com o
   original). A barra inferior tem “Seu texto, no seu Mac.” e o botão **Começar a leitura**.
2. **Lendo com atenção…**: o símbolo respira e as etapas aparecem numa linha de luzes,
   com o andamento (“420 de 1.274 parágrafos”).
3. **Mesa de leitura**:
   - à esquerda, os pontos de atenção em cartões, com busca e filtros num popover;
   - à direita, a página: o trecho com luz rosada ao fundo, a nota de margem “Por que
     acendemos esta luz” com a sugestão (trecho → proposta) e as seis decisões em cartões.
4. **Trilho noturno**: barra lateral nativa que sobe até os botões da janela, com
   Início, Leitura, Registro e Motor (um popover com a instalação e as atualizações do FONTE).
5. **Barra de ferramentas**: uma só, no padrão do Mac. Título e subtítulo mostram o
   manuscrito e o andamento (“Mesa de leitura · 12 de 286 avaliados”). À direita ficam
   os ícones de Capítulos, Etapas e alcance, Abrir relatório, Exportar e Mais opções.
6. **Sobre o Lume**: painel noturno com o símbolo, as versões e a frase da marca; à direita,
   os componentes de terceiros e o texto de cada licença, lidos do motor embutido.

## Prévias

As prévias são renderizadas pelo próprio app, em compilação Debug e sem abrir janela:

```sh
LUME_SNAPSHOT=/pasta/de/saida \
LUME_SNAPSHOT_REPORT=/caminho/relatorio.json LUME_SNAPSHOT_INDEX=3 \
  <DerivedData>/Build/Products/Debug/Lume.app/Contents/MacOS/Lume
```

A mesma execução grava `icone-1024.png`, a base do AppIcon (redimensionar com `sips`).
