# Aceitação da v0.11 — Lume

> **Documento histórico.** A memória narrativa heurística descrita aqui foi removida em 29/09/2026 por não produzir alertas úteis; contradições narrativas passaram à Coerência com IA (`LumeCoerencia/`). Os gates de preservação do manuscrito, contratos e comandos de teste continuam válidos.

Estes são critérios de fechamento, não resultados desta configuração documental.
Todos começam sem aprovação nova. A [validação histórica](../../LumeMac/Documentacao/VALIDACAO.md)
é referência de baseline; cada alteração funcional precisa de evidência própria.
Requisitos de produto: [lume-v0.11.md](../product/lume-v0.11.md).

## Gates de comportamento

| ID | Critério | Evidência mínima exigida |
| --- | --- | --- |
| A01 | Manuscrito e índices imutáveis | Bytes/SHA-256 antes/depois, trechos exatos, parágrafos e Unicode preservados |
| A02 | Front matter fora da memória narrativa | Créditos/títulos não geram fatos; prólogo e conteúdo narrativo continuam analisados |
| A03 | Identidades conservadoras | Genéricos ficam locais; ambiguidades ficam não resolvidas; objetos distintos não são fundidos |
| A04 | Sujeitos, falantes e papéis preservados | Ativa/passiva, paciente, objeto e destinatário corretos; sujeitos/falantes explícitos não regridem |
| A05 | Candidatos rastreáveis | Evento relevante gera candidato com origem, evidência e motivo de promoção/descarte |
| A06 | Local e persistente distintos | Ruído não atravessa cenas; estado relevante e ainda válido persiste com identidade comprovada |
| A07 | Histórico e transição corretos | Estado anterior encerrado; sucessor e estado atual coerentes, sem falso conflito |
| A08 | Classes prioritárias funcionam | Posse, transferência, localização, estado, conhecimento, relação, atributo e tempo com controles |
| A09 | Confiança, escopo e polaridade preservados | Dependência incerta limita fato/alerta; fala/hipótese não vira fato assertivo forte |
| A10 | Métricas auditáveis | Candidatos, promoções, descartes, persistência e pares globais com denominadores explícitos |
| A11 | Contratos compatíveis | JSON estrutural/semanticamente válido, IDs/origens válidos e leitores antigos preservados |
| A12 | Regressão semântica completa | Suítes, corpus sintético e casos históricos passam sem enfraquecer expectativas |
| A13 | Corpus real estável | Echoes e Hikari sem exceções, hash preservado e revisão dos casos semânticos esperados |
| A14 | Fechamento demonstrado | Diff revisado, resultados reproduzíveis, nenhum gate obrigatório pendente ou regressão conhecida |

Marcar cada gate como aprovado, falhou ou pendente com comando/caso, data e caminho
da evidência. Em tarefas menores, registrar quais gates foram afetados; fechamento
da v0.11 exige todos. Bloqueio de ambiente, corpus ausente ou teste ignorado não
conta como aprovação. O Auditor Final do produto continua fora do escopo.

## Casos mínimos esperados

- “João pegou a chave”: posse da chave vinculada ao evento e à identidade correta.
- “João entregou a chave a Maria”: a mesma chave passa a Maria, posse de João é
  encerrada/negada e ambos os efeitos preservam o evento de origem.
- “João machucou a perna” → outra cena: o estado relevante permanece. Cura explícita
  reconhecida encerra a restrição; o paciente curado não é confundido com quem curou.
- “Maria entrou no hospital” → “Maria saiu do hospital”: localização atual e
  encerramento da anterior corretos, sem inventar destino após a saída.
- “Maria não sabia do acidente” → “Maria descobriu o acidente”: histórico negativo
  e positivo, estado atual positivo e ausência de desconhecimento inventado.
- Porta fechada → abertura → porta aberta: transição legítima sem inconsistência.
  Carta intacta → rasgada → queimada: histórico preservado e estado final coerente.
- “Ana é irmã de Bruno”: relação simétrica; “Ana é mãe de Bruno” não é simétrica.
  Idade explicitamente declarada não é confundida com quantidade de objetos.
- Tempo sem âncora continua desconhecido; evidência textual não fabrica datas.
- “João sorriu”, “Maria olhou pela janela”, “Pedro respirou fundo”, “Ana virou a
  cabeça”: nos contextos mínimos, nenhum `PERSISTENT_FACT` sem consequência.
- “João encontrou Pedro. Ele guardou a carta”: se houver dois antecedentes
  compatíveis, não impor identidade nem promover fato forte. Destinatário explícito
  em “João entregou a carta a Maria enquanto Carlos observava” deve continuar Maria;
  a mera presença de Carlos não torna o destinatário ambíguo.
- Hipótese, negação, relato e falante incerto: nenhum fato assertivo forte indevido.
- Trocar nomes, objetos e contexto de gênero mantém a regra sem depender da obra.

Verificar fatos, sujeitos, papéis, escopo, confiança, origem, histórico e estado
final; acertar somente a categoria do alerta não basta. Cada bug real deve ter
reprodução sintética genérica antes de uma regressão específica autorizada.

## Testes existentes e comandos

O projeto usa `unittest`, não uma suíte `pytest` configurada. Os comandos abaixo
foram conferidos por inspeção; esta criação de documentos não os executou.
Usar o ambiente existente `Analisador/.venv` com dependências do `pyproject.toml`
e modelo `pt_core_news_sm`. Não reinstalar dependências por rotina.

### Analisador: executar em `LumeMac/Analisador/`

```sh
.venv/bin/python -c 'import fonte; print(fonte.__file__)'
.venv/bin/python -m unittest discover -s tests -v
```

A primeira saída deve apontar para `LumeMac/Analisador/fonte/__init__.py`. A
documentação histórica registra risco de testar uma cópia instalada antiga;
confirmar a origem antes de usar resultados como prova. A suíte completa inclui
unitários, semântica, negativos, ambiguidades e regressões existentes.

Para iterar em persistência, sem substituir a suíte completa:

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_persistent_memory.py' -v
```

Mapas de cobertura: `test_semantic.py`, `test_fact_quality.py`,
`test_generic_facts.py`, `test_persistent_memory.py`, `test_real_narrative.py`,
`test_narrative_111.py`, `test_narrative_quality.py`, `test_pipeline.py` e demais
testes da descoberta. O corpus `tests/corpus/generic.json` é exercitado por
`test_generic_facts.py`; consulte seu [README](../../LumeMac/Analisador/tests/corpus/README.md).
O arquivo `test_real_narrative.py` contém regressões selecionadas e não substitui
analisar os manuscritos completos.

### Integração: executar em `LumeMac/`

```sh
PYTHONPATH=Analisador Analisador/.venv/bin/python -m unittest discover -s Tests -p 'test_*.py' -v
PYTHONPATH=Analisador Analisador/.venv/bin/python Tests/check_python_contract.py
```

O contrato Python verifica CLI/JSON, Unicode, hash, intervalos e proteção contra
sobrescrita. Novos campos narrativos também precisam de testes de invariantes:
JSON parseável sozinho não comprova schema ou correção semântica.

Para alterações de interface/contrato, executar o contrato Swift e build pertinente.
O comando abaixo cria apenas uma pasta temporária nova para o executável de teste;
o relatório usado deve conter achados, conforme exige `ContractCheck.swift`:

```sh
lume_contract_dir=$(mktemp -d)
swiftc Lume/Models.swift Lume/PythonRunner.swift Tests/ContractCheck.swift -o "$lume_contract_dir/contrato-swift"
"$lume_contract_dir/contrato-swift" Exemplo/Mestre/relatorio.json "$PWD/Analisador/.venv/bin/python"
```

Testar também relatório atual quando o contrato mudar. Testes DOM em `Tests/`
exigem Node/jsdom e o relatório correspondente ao cenário esperado; não apontar
um teste de sete fatos para qualquer relatório. Mudanças no HTML exigem DOM
pertinente; mudanças visuais exigem inspeção visual apropriada. Registrar ambiente
ausente como pendência. Não usar a montagem completa como substituto de aceitação
semântica. Ver comandos de build no [README](../../LumeMac/README.md).

## Corpus real e comparação antes/depois

Mudanças de análise exigem Echoes; mudanças de memória narrativa/global exigem
também Hikari. Para fechar a v0.11, ambos são obrigatórios. Manter DOCX externos,
sem versionar seu conteúdo nem modificar entradas para melhorar resultados.

Já existe `LumeMac/Scripts/validate_real_memory.py`. Em `LumeMac/`, usar o modelo
abaixo substituindo os caminhos ilustrativos por entradas existentes e uma saída nova:

```sh
Analisador/.venv/bin/python Scripts/validate_real_memory.py \
  --docx '/caminho/real/manuscrito.docx' \
  --baseline '/caminho/real/relatorio-anterior.json' \
  --output 'Saida/validacao-tarefa-corpus-nova' \
  --engine '/caminho/real/pacote.lumemotor/fonte-engine'
```

`--engine` é opcional para validar fontes; para uma entrega do motor, fornecer o
executável real indicado pelo pacote e comprovar paridade. O nome/caminho do
executável deve ser conferido no manifesto, não presumido a partir do exemplo.
Repetir separadamente por manuscrito com saídas diferentes. O baseline deve
corresponder ao mesmo hash do DOCX. O script preserva hash/índice, verifica origem
e evidência dos fatos e compara fontes/motor quando fornecido.

Esse script não aprova sozinho precisão, falsos fatos ou todos os gates. Acrescentar
avaliação semântica dos casos esperados: continuidade, falantes, estados físicos,
posse, objetos e cenas longas em Echoes; volume, múltiplos personagens, diálogos,
objetos e mudanças de cena em Hikari. Manter configuração e denominadores
comparáveis; registrar alterações nas definições das métricas.

A conversão de eventos elegíveis deve melhorar sem aumento indevido de falsos
fatos, demonstrado em casos anotados. Fixar expectativas e tolerâncias antes do
patch; não inventar metas percentuais depois de ver os números. Sem anotação,
precisão e `false_fact_rate` continuam não avaliadas. A taxa global ainda não
instrumentada permanece pendente para o fechamento, não zero nem 100%.

## Evidência final

Registrar revisão/estado dos fontes, ambiente, arquivos alterados, testes novos,
comandos/diretórios, contagens, falhas/skips, corpus e hashes, configuração,
métricas/denominadores, logs, paridade quando aplicável e limitações. Revisar o
diff para hard-code, confiança artificial, mutação do original e testes enfraquecidos.
Não declarar aprovação integral com regressão conhecida ou gate obrigatório sem
prova. Alterações exclusivamente documentais exigem revisão de conteúdo, caminhos,
links locais e diff, sem build ou execução de corpus.
