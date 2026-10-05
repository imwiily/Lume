# Lume · Nocturne & Candlelight

**O manuscrito é papel. O Lume é instrumento. A atenção é luz.**

**Lume encontra. Lume explica. O editor decide.**

O Lume é uma ferramenta editorial nativa do Mac com identidade literária. A interface usa
a estrutura de um instrumento (painéis planos, contornos finos, cantos pequenos). O texto
do autor aparece como papel, em serifada e com margens largas. A cor da vela aparece só
onde há atenção: o trecho iluminado, a chama do parágrafo, o andamento da leitura. Não
deve parecer site, SaaS, Word, chatbot nem ferramenta genérica de IA.

A referência visual veio do projeto final no Google Stitch. O comportamento real do Lume
prevalece sobre o mockup. As divergências estão em
[`.agent/plans/interface-stitch.md`](../../.agent/plans/interface-stitch.md).

## Símbolo

Uma chama em gota, na cor da vela e com uma gota de papel no centro, sobre um livro aberto
em duas páginas cheias, separadas pela lombada. O fundo é um quadrado noturno de cantos
contínuos. Nos textos corridos, escreva **Lume** com inicial maiúscula.

- `LumeMark` em `app/Lume/LumeTheme.swift`: o símbolo em formas do SwiftUI (`Teardrop`,
  `BookPages`), sem imagens.
- `simbolo.svg` e `marca.svg`: o mesmo desenho em vetor; a marca acompanha o nome em New York.
- `app/Lume/Assets.xcassets/AppIcon.appiconset`: o ícone em todos os tamanhos, gerado pelas
  capturas (`icone-1024.png`).

## Paleta

Cores de marca, iguais nos dois modos:

| Nome | Código | Uso |
| --- | --- | --- |
| Noite | `#2A1F3D` | Estrutura, ação principal, símbolo |
| Noite profunda | `#1B1428` | Fundo do símbolo e do painel do Sobre |
| Vela | `#F2C46D` | Atenção: chama, trecho iluminado, andamento |
| Linho | `#F7F1EA` | Fundo da janela no claro, texto sobre noite |
| Papel | `#FFFCF7` | Página do manuscrito e cartões em relevo |
| Rosa-chama | `#E7A493` | Reservada; a marca não usa gradiente |

Tokens de interface em `LumeTheme` (claro / escuro):

| Token | Claro | Escuro | Uso |
| --- | --- | --- | --- |
| `canvas` | `#F7F1EA` | `#17121F` | Fundo da janela |
| `surface` | `#FBF7F1` | `#1F1829` | Painéis, colunas laterais |
| `raised` | `#FFFCF7` | `#272033` | Cartões, botões, item selecionado |
| `paper` | `#FFFCF7` | `#221B2C` | Página do manuscrito |
| `sunken` | `#F0E8DF` | `#2C2438` | Campos, controles segmentados |
| `line` / `lineStrong` | `#E6DCD1` / `#CFC4B8` | `#372D44` / `#4E4362` | Contornos |
| `ink` | `#221A2E` | `#F4EDE4` | Texto principal |
| `secondary` / `tertiary` | `#5E5468` / `#7D7286` | `#B9ADC4` / `#968AA2` | Legendas |
| `accent` / `onAccent` | `#2A1F3D` / `#F7F1EA` | `#D9CCEE` / `#1B1428` | Ação principal, seleção |
| `glow` / `glowLine` | `#FCEBC6` / `#D9A441` | `#4A3A22` / `#F2C46D` | Luz sobre o trecho e traço sob ele |
| `amber` | `#7A5410` | `#F2C46D` | Texto na cor da vela, atenção editorial |
| `error` | `#A8323F` | `#F49AA4` | Erro confirmado |
| `rose` | `#A24E3E` | `#F0A898` | Provável erro |
| `style` | `#3F55A0` | `#AFC0F5` | Estilo do autor, possível inconsistência |
| `sage` | `#3A7257` | `#9ED2B5` | Falso positivo, aceito |

Cada classificação e cada decisão tem ícone e nome escrito, além da cor. O trecho
sinalizado recebe luz, não a aparência de erro.

## Tipografia e forma

- **New York** (`LumeFont.display`, `design: .serif`): manuscrito, capítulos, títulos e
  saudações.
- **SF Pro** (`LumeFont.ui`): a interface. Rótulos, explicações, botões e números.
- **Rótulos de seção** (`Kicker`): versalete espaçado. A chama só aparece quando o rótulo
  fala de atenção, como em “Por que acendemos esta luz”.
- **Raios** (`LumeRadius`): 4, 6 e 8 pontos. Sem cápsulas e quase sem sombras.
- **Página do manuscrito:** com espaço, cerca de 65–75 caracteres por linha; tamanho
  ajustável de 15 a 28 pontos.

## Telas

1. **Barra:** o símbolo, o nome e a navegação (Início, Leitura, Registro, Motor). Título e
   subtítulo mostram o manuscrito e o andamento. Na Mesa aparecem também Capítulos (leva ao
   primeiro alerta de cada capítulo), Etapas e alcance, o botão do inspetor, Abrir relatório,
   Exportar decisões e Mais opções.
2. **Início:** a saudação pelo horário, “Que texto vamos iluminar hoje?”, Escolher manuscrito
   e Abrir relatório, os formatos e o aviso de que as análises do FONTE acontecem neste Mac.
3. **Preparação:** o manuscrito escolhido, “Tudo pronto para uma leitura atenta.”, os três
   modos e os painéis A língua (tempo da narração, corretor local), A história (Coerência com
   IA, comparação com o original) e Auditoria final. Também tem “Ajustar o que procurar…”,
   com o número de verificações ativas.
4. **Lendo com atenção…:** as etapas reais do motor, com o andamento quando o motor o informa,
   e “Interromper leitura”.
5. **Mesa de leitura:** Pontos de atenção | Manuscrito | Inspetor editorial.
   - O aviso de tempo contradito fica no topo da lista.
   - A página mostra o parágrafo do alerta iluminado entre os parágrafos próximos do
     relatório, com a chama e o § na margem.
   - O inspetor traz classificação, título, trecho, “Por que acendemos esta luz”, sugestão,
     evidências, as ações no Pages (Corrigir no manuscrito, Editar parágrafo), a decisão
     editorial e os detalhes técnicos.
   - Numa janela estreita, o inspetor desce para baixo da página e o manuscrito mantém a
     largura.
6. **Registro:** a saída do motor na última operação, com “Abrir no editor” e “Mostrar no
   Finder”.
7. **Motor:** a versão do FONTE carregada e as ações Verificar motor, Instalar atualização…,
   Voltar à versão anterior e Restaurar embutido.
8. **Sobre o Lume:** o painel noturno com o símbolo e as versões; à direita, os componentes de
   terceiros e as licenças, lidos do motor embutido.

## Capturas

As capturas são renderizadas pelo próprio app, em compilação Debug e sem abrir janela, nos
modos claro e escuro. As entradas são relatórios e documentos sintéticos; nenhum manuscrito
real e nenhuma chamada à API:

```sh
LUME_SNAPSHOT=/pasta/de/saida \
LUME_SNAPSHOT_ENGINE=/caminho/fonte-x.lumemotor \
LUME_SNAPSHOT_REPORT=/caminho/relatorio.json LUME_SNAPSHOT_REPORT_DOC=/caminho/manuscrito.docx \
LUME_SNAPSHOT_AUDIT_REPORT=… LUME_SNAPSHOT_AUDIT_DOC=… \
LUME_SNAPSHOT_PAGES_REPORT=… LUME_SNAPSHOT_PAGES_DOC=/caminho/manuscrito.pages \
LUME_SNAPSHOT_LOG=/caminho/registro.txt \
  <DerivedData>/Build/Products/Debug/Lume.app/Contents/MacOS/Lume
```

- `LUME_SNAPSHOT_ONLY=prefixo` desenha só as telas cujo nome começa com o prefixo.
- A captura liga a Coerência e a Auditoria para mostrar as opções e restaura os valores do
  autor ao terminar.
- A mesma execução grava `icone-1024.png`, a base do AppIcon (redimensionar com `sips`).
