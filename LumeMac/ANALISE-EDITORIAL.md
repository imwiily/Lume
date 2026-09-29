# Análise editorial — FONTE 0.4.0

O motor gera suspeitas para avaliação humana. Não altera o texto, não escolhe a grafia oficial de nomes e não corrige automaticamente.

| Regra | Evidência procurada | Limite principal |
| --- | --- | --- |
| Duração | “amanhã e/nem nos N dias seguintes” versus suspensão/afastamento de M dias | Compara no máximo oito parágrafos seguintes da mesma seção; pode confundir pessoas ou eventos. Confiança alta é na diferença aritmética, não na existência de erro. |
| Adiamento | Atividade adiada para amanhã perto de “mais N dias” | Só é contraditório se a data original era hoje e o evento é o mesmo; confiança média. |
| Frase duplicada | Frases de seis palavras ou mais entre oito frases próximas | Pode ser refrão ou repetição deliberada. Não procura paráfrases. |
| Palavra próxima | Palavra repetida entre duas posições e a distância configurada (padrão: oito) | Ignora várias palavras funcionais e algumas locuções; ainda produz falsos positivos. Confiança baixa. |
| Grafia de nome | Candidatos iniciados em maiúscula, fora do léxico, mesma inicial e uma inserção/remoção/substituição diferente; ao menos uma variante recorrente | Pode confundir nomes distintos; não encontra toda grafia variante. Analisa o documento todo. |
| Referência | “Eles/Elas estavam/estão/ficaram tão/muito/bem perto”, sem indicação simples de plural no contexto | Heurística estreita, não é resolução geral de pronomes. Referentes distantes podem ser legítimos. |
| Cicatriz de edição | Redução de ao menos oito palavras perto de eles/elas/isso/aquilo ao comparar original e revisão | Apenas indício de proximidade de corte; não prova remoção do antecedente. Alinhamento pode falhar; limite de 120 mil tokens somados. |

As regras de continuidade param em títulos e em alguns marcadores explícitos de mudança de dia. Isso não equivale a identificar todas as cenas. A marcação de capítulos depende dos estilos/títulos reconhecidos pelo leitor DOCX.

Continuidade e referências examinam falas e itálicos. Repetições seguem as áreas configuradas. A configuração pode tratar aspas como falas, pensamentos ou narração e usar itálico para identificar pensamentos marcados. A referência ao original aparece com o rótulo “Original”; os outros trechos são do manuscrito atual. Os dois arquivos são somente lidos.

As avaliações não ajustam limiares nem treinam modelos automaticamente. Elas podem ser exportadas para orientar futuras alterações de regras, com revisão humana. Todos os dados permanecem locais.

## CLI

```bash
python -m fonte revisar revisado.docx --modo editorial --original original.docx --saida resultado-novo
python -m fonte revisar revisado.docx --modo ambas --tempo passado --saida resultado-completo
```

O argumento `--original` é opcional. A pasta de saída deve ser nova; o programa recusa sobrescrever relatórios. Para comparar textos do Pages, exporte ambos para DOCX.

## Filtros de busca

`--config busca.json` aceita a configuração exportada pelo Lume. O modo geral da CLI limita as camadas executadas, mesmo se uma regra da outra camada estiver ativada. Repetições de palavras não atravessam a fronteira entre fala, narração e pensamento. “Mesma frase” é uma divisão por pontuação simples; abreviações e reticências podem dividir a frase diferentemente da leitura humana.

“Frases com as mesmas palavras” normaliza pontuação e maiúsculas. “Sequências semelhantes” usa semelhança lexical, não equivalência de sentido, e pode sinalizar frases com significado diferente. A janela de frases permanece limitada às oito frases elegíveis recentes. Não identifica o personagem que fala. Não existe correção automática.

Para capítulos, `chapter_auto=false` desativa as regras automáticas; `chapter_titles` e `chapter_styles` continuam ativos. Títulos cadastrados são comparados por texto exato ignorando maiúsculas e espaços nas extremidades. Numeração por extenso não cobre todas as formas possíveis; títulos não reconhecidos podem ser cadastrados.
