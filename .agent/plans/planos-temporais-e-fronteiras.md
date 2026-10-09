# Falsos positivos morfossintáticos: verbo finito, fronteiras de oração e planos temporais

Pedido do autor (06/10/2026), a partir do relatório de um livro narrado no presente. Os
exemplos reais servem só para identificar as classes; os testes são escritos do zero, com
outras palavras e outros nomes.

## Objetivo e escopo

Famílias de falsos positivos e o comportamento esperado:

1. “Estrutura da frase” sem verbo finito quando há verbo finito (homógrafo etiquetado como
   nome/adjetivo, verbo finito ligado como complemento, verbo de relativa descartado).
   Esperado: uma validação independente antes do alerta (léxico + morfologia do modelo + posição
   de verbo); com discordância, não alertar.
2. Fragmento nominal real: continua atenção editorial de confiança baixa, com mensagem neutra;
   oposição (“por um lado / por outro”), enumeração e paralelismo reduzem a prioridade
   (classe `likely_literary_fragment`, sem alerta, contada nos metadados).
3. “Resíduo de edição” em `estão é` quando o primeiro verbo fecha uma relativa (“em que
   estão”). Esperado: verbos de orações diferentes não são auxiliares do mesmo predicado.
4–6. Narração no presente: passado em oração dependente (relativa, completiva, adverbial causal
   ou temporal) e mais-que-perfeito composto expressam anterioridade e não geram “Tempo verbal”;
   `coordinated_past_present` só compara predicados coordenados de verdade, nunca a âncora
   dentro de uma relativa/subordinada.
7. Imperfeito modal com infinitivo (“devia/podia + infinitivo”) não é passado narrativo.
8. Aspas de destaque (uma ou duas palavras no meio da oração, sem verbo nem pontuação interna)
   não ativam a regra de pontuação de diálogo.
9. LanguageTool: plural/singular de um nome já reconhecido, linha de créditos (parágrafo só
   com palavras em maiúscula, sem pontuação) e termo desconhecido recorrente (confiança baixa);
   “Nomes aceitos” da obra valem também para a grafia, com plural.
12. Duplicidade: na narração no presente, `coordinated_past_present` sobre o verbo no presente
   não se soma ao “Tempo verbal” do passado que lhe serve de âncora.
15. Subordinada isolada com verbo finito (“Quando as luzes se apagam.”): categoria própria
   `incomplete_subordinate_clause`, confiança baixa, mensagem que nomeia o subordinante.

Fora do escopo: reescrever o pipeline na ordem ideal do item 16 (as regras já consultam a árvore
de dependências; a mudança fica nas regras), inferência semântica de pensamento ou discurso.

## Arquivos

- `fonte/fonte/analysis.py`: validação de verbo finito, classes de fragmento, mensagens,
  fronteira de oração no resíduo, aspas de destaque, subordinada incompleta, passado legítimo.
- `fonte/fonte/temporal.py`: `legitimate_past`, imperfeito modal, coordenação estrutural.
- `fonte/fonte/pipeline.py`: consolidação de alertas temporais redundantes.
- `fonte/fonte/languagetool.py`: nomes no plural, créditos, termo recorrente.
- `app/Lume/SearchSettingsView.swift`: rótulo de “Nomes aceitos” (vale para grafia).
- `fonte/tests/test_planos_e_fronteiras.py` e corpus `fonte/tests/corpus/deteccao/`.

## Medidas

- Antes: corpus `todos` sem LanguageTool, 52/71 linguísticos, 8 alarmes falsos.
- Antes/depois em A, B (passado) e C (outro livro do autor, no presente), com LanguageTool, a partir de cópias
  no scratchpad; worktree em HEAD como motor “antes”.

## Progresso

- [x] Reprodução dos exemplos reais e das frases novas no motor atual.
- [x] Testes regressivos (falharam antes: 34 falhas, 5 erros).
- [x] Correções. Ajuste após a comparação real: imperfeito em oração dependente e ‘podia’ +
  infinitivo ficam com confiança baixa (podem ser simultaneidade real); oração dependente exige
  introdutor; coordenação de verbo finito com infinitivo/subjuntivo é tratada como erro da árvore.
- [x] FONTE 364 testes, Coerencia 25, pacotes 29, contrato Python, contrato Swift, build do app.
- [x] Corpus `todos`: linguística 52/71 → 54/73 (2 erros novos encontrados, nenhum perdido);
  alarmes falsos 8 → 9 (o novo é o imperfeito em relativa do texto novo, com confiança baixa).
- [x] A e B (passado): 25 → 25 e 5 → 5, sem diferença. C (presente): 179 → 156; 24 alertas
  saíram (anterioridade, fronteira, aspas, nomes, verbo finito), 1 entrou (subordinada isolada);
  36 imperfeitos em oração dependente seguem visíveis com confiança baixa.
