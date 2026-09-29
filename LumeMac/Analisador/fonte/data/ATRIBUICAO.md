# PortiLexicon-UD

O índice `portilexicon.json.gz` foi derivado de `WORDmaster.txt`, `VERB.tsv` e `AUX.tsv` do repositório de Lucelene Lopes: <https://github.com/LuceleneL/PortiLexicon-UD>.

Commit fixado: `315e063da1f89c89e2097c6e72428ebefb9ab1d1`.

Referência: Lopes, L.; Duran, M.; Fernandes, P.; Pardo, T. (2022). *PortiLexicon-UD: a Portuguese lexical resource according to Universal Dependencies model*. LREC, p. 6635–6643.

O repositório distribui seus arquivos sob a licença MIT, copyright (c) 2023 Lucelene Lopes. A licença original está em `PORTILEXICON-LICENSE.txt`. Esta integração não implica endosso dos autores ao FONTE.

Transformações: normalização Unicode NFC, conversão para minúsculas e união das análises em indicadores de verbo finito, passado/presente/futuro do indicativo, formas não finitas e outras classes. O índice não conserva todos os lemas, pessoas ou modos; não é uma cópia integral da análise linguística original. Uma linha malformada de WORDmaster.txt foi ignorada e registrada nos metadados. Código de reprodução: `tools/build_lexicon.py`. Hashes e origem: `portilexicon-meta.json`.

O léxico tem ambiguidades e pode conter lacunas ou erros. As decisões editoriais continuam dependendo do contexto.
