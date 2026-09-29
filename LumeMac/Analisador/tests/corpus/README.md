# Corpus editorial

A — `generic.json`: os sete testes positivos e quatro negativos obrigatórios da proposta v0.11.x. `test_generic_facts.py` executa esse arquivo, acrescenta casos de estados, transferência, identidade, duração, ordem, localização, negação e substituições de nomes/objetos/relações. Cada caso deve isolar uma classe editorial.

B — `test_genre_contexts` em `test_generic_facts.py`: controles de transferência do mesmo mecanismo para oito contextos de gênero. É um teste controlado, não uma medição independente de generalização.

C — `test_narrative_111.py`, `test_narrative_quality.py`, `test_semantic.py` e exemplos Memoria/Memoria111: regressões anteriores permanecem. Novos defeitos de manuscritos devem primeiro receber um caso mínimo no corpus A; só depois uma regressão com o trecho real, quando disponível e autorizado.

Nenhuma regra deve depender do nome de uma personagem ou obra. Testes criados durante o desenvolvimento não medem precisão/recall em narrativas desconhecidas.

Na 0.11.3, `test_fact_quality.py` acrescenta 36 testes de qualidade, com subcasos. O critério inclui fatos/entidades corretos, papéis ativos e passivos, histórico e estados finais, escopo e alertas; não basta acertar a categoria do alerta. A demonstração integrada fica em `Exemplo/Qualidade113/`.
