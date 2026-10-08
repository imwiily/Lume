"""Deduplicação entre detectores (núcleo compartilhado; estabilização, Fases 6a e 6b).

Deduplicação é quando duas fontes apontam o mesmo fenômeno e só uma ocorrência é apresentada.
Não é supressão linguística (a regra que decide que a evidência não basta para alertar): essas
ficam em cada regra, como os filtros do LanguageTool em `languagetool.check`.

FONTE × LanguageTool (`consolidar`, depois de todas as etapas): só se juntam alertas da mesma
família de fenômeno (`FAMILIAS`), que tocam o mesmo trecho **e** cuja correção dá o mesmo texto.
Trecho em comum não basta; sem correção comparável, os dois ficam. A ocorrência principal é a da
família (`principal`), escolhida família por família; a outra fica registrada nela (`absorvidos`,
`detectores`), com identidade, regra, classe e origem, para a memória editorial e as medições.
Nenhuma classe estatística muda: a principal mantém a sua, a absorvida não soma amostra.

Tempo verbal × coerência temporal e o mesmo ID entre etapas continuam como na Fase 6a. A
precedência interna de um mesmo detector (`temporal.PRECEDENCE`, o primeiro alerta por trecho em
`grammar`) fica no detector.

`observar`, quando definido (scripts de medição), recebe cada descarte: (mecanismo, descartado,
motivos). Não muda o resultado nem o relatório.
"""


observar = None

LANGUAGETOOL = "LanguageTool"

# Família → regras do FONTE, regras do LanguageTool (IDs do servidor 6.6 conferidos com frases de
# teste) e a fonte principal, com o motivo. Não há precedência fora destas famílias.
FAMILIAS = {
    "crase": {
        "fonte": {"crase"},
        "languagetool": {"CRASE_CONFUSION", "CRASE_CONFUSION_2", "ERROS_DE_CRASE_MARCOAGPINTO", "SAIR_AS_RUAS"},
        "principal": "fonte",
        "motivo": "regra específica com a direção da correção na mensagem; identidade igual com e sem o LanguageTool",
    },
    "pontuacao_duplicada": {
        "fonte": {"pontuacao_duplicada"},
        "languagetool": {"DOUBLE_PUNCTUATION", "DOUBLE_PUNCTUATION_XML"},
        "principal": "fonte",
        "motivo": "fenômeno objetivo detectado igual pelas duas fontes; identidade igual com e sem o LanguageTool",
    },
    "espacamento": {
        "fonte": {"espacamento"},
        "languagetool": {"ESPACO_DUPLO", "WHITESPACE_RULE", "SPACE_BEFORE_PUNCTUATION", "SPACE_BEFORE_PUNCTUATION2",
                         "COMMA_PARENTHESIS_WHITESPACE"},
        "principal": "fonte",
        "motivo": "fenômeno objetivo detectado igual pelas duas fontes; identidade igual com e sem o LanguageTool",
    },
    "maiuscula_inicial": {
        "fonte": {"capitalizacao_contextual"},
        "languagetool": {"UPPERCASE_SENTENCE_START"},
        "principal": "fonte",
        "motivo": "regra própria restrita ao pronome depois de ‘?’ ou ‘!’; identidade igual com e sem o LanguageTool",
    },
    "palavra_duplicada": {
        "fonte": {"palavra_consecutiva"},
        "languagetool": {"PORTUGUESE_WORD_REPEAT_RULE", "WORD_REPEAT_RULE"},
        "principal": "fonte",
        "motivo": "a regra própria só aponta palavras do léxico; identidade igual com e sem o LanguageTool",
    },
}


def do_languagetool(item):
    return item["source"].startswith(LANGUAGETOOL)


def regra_languagetool(item):
    """ID da regra do LanguageTool, gravado na origem (“LanguageTool local · ID”)."""
    return item["source"].rsplit(" · ", 1)[-1]


def familia(item):
    for nome, dados in FAMILIAS.items():
        if (regra_languagetool(item) in dados["languagetool"] if do_languagetool(item)
                else item.get("rule") in dados["fonte"]):
            return nome
    return None


def correcao(item):
    """Texto que substitui o trecho, se a ocorrência propõe um. A palavra dobrada do FONTE não traz
    sugestão, mas a correção é uma só: ficar com uma das palavras."""
    if item.get("suggestion") is not None:
        return item["suggestion"]
    if not do_languagetool(item) and item.get("rule") == "palavra_consecutiva":
        trecho = item["text"][item["start"]:item["end"]]
        return trecho.split()[0] if trecho.split() else None
    return None


def corrigido(item):
    proposta = correcao(item)
    if proposta is None:
        return None
    return item["text"][:item["start"]] + proposta + item["text"][item["end"]:]


def equivalentes(fonte, languagetool):
    """Mesmo fenômeno: mesma família, trecho em comum e a mesma correção do parágrafo."""
    nome = familia(fonte)
    if nome is None or familia(languagetool) != nome or not sobrepoe(fonte, languagetool):
        return False
    texto = corrigido(fonte)
    return texto is not None and texto == corrigido(languagetool)


def _descartar(itens, mecanismo, motivos):
    """Mantém a ordem; `motivos(item)` devolve as ocorrências que o fazem cair (vazio: fica)."""
    mantidos = []
    for item in itens:
        causa = motivos(item)
        if causa:
            if observar:
                observar(mecanismo, item, causa)
            continue
        mantidos.append(item)
    return mantidos


def intervalo(item):
    return item["paragraph"], item["start"], item["end"]


def sobrepoe(item, outro):
    """Mesmo parágrafo e algum caractere em comum."""
    return (item.get("paragraph") == outro.get("paragraph") and outro["start"] < item["end"]
            and item["start"] < outro["end"])


def contido(item, outro):
    """`item` inteiro dentro de `outro`, no mesmo parágrafo."""
    return (item["paragraph"] == outro["paragraph"] and outro["start"] <= item["start"]
            and item["end"] <= outro["end"])


def relacao_que_repete_tempo_verbal(relacoes, tempo_verbal, forma_narrativa):
    """Mesma mudança de tempo vista pelos dois lados: a relação cujo verbo apontado está no tempo da
    narração cai quando o outro verbo da relação (exatamente o mesmo trecho) já tem o alerta de
    tempo verbal; o desvio é o outro verbo."""
    marcados = {intervalo(f): f for f in tempo_verbal if f["category"] == "Tempo verbal"}

    def motivos(item):
        if not forma_narrativa or item.get("temporal_evidence", {}).get("target_form") != forma_narrativa:
            return []
        return [marcados[chave] for r in item.get("related", [])
                if (chave := (r.get("paragraph"), r.get("start"), r.get("end"))) in marcados]
    return _descartar(relacoes, "relacao_que_repete_tempo_verbal", motivos)


def tempo_verbal_sob_relacao(tempo_verbal, relacoes):
    """A explicação específica substitui a genérica: o alerta de tempo verbal contido no trecho de
    uma relação temporal cai."""
    return _descartar(tempo_verbal, "tempo_verbal_sob_relacao",
                      lambda item: [f for f in relacoes if contido(item, f)] if item["category"] == "Tempo verbal" else [])


def mesmo_id(lote, anteriores):
    """Entre etapas: a ocorrência com o ID de uma anterior (resultado idêntico) não se repete; o mesmo
    ID com resultado diferente é defeito e interrompe. Devolve as novas, na ordem."""
    vistos = {f["id"]: f for f in anteriores}
    novas = []
    for item in lote:
        if item["id"] in vistos:
            if item != vistos[item["id"]]:
                raise ValueError("Identificador de ocorrência associado a resultados diferentes.")
            if observar:
                observar("mesmo_id", item, [vistos[item["id"]]])
            continue
        novas.append(item)
        vistos[item["id"]] = item
    return novas


def registro(item, nome):
    """O que fica de uma ocorrência absorvida: identidade, origem, regra, classe e trecho."""
    from .politica import classe
    dados = {"id": item["id"], "rule": item.get("rule"), "classe": classe(item), "category": item["category"],
             "category_code": item.get("category_code"), "source": item["source"], "module": item.get("module"),
             "paragraph": item["paragraph"], "start": item["start"], "end": item["end"],
             "excerpt": item.get("excerpt"), "suggestion": item.get("suggestion"), "severity": item.get("severity"),
             "confidence": item.get("confidence"), "familia": nome}
    if item.get("related"):
        dados["related"] = item["related"]
    return dados


def consolidar(ocorrencias):
    """FONTE × LanguageTool: junta as equivalentes na principal da família. Devolve (ocorrências,
    quantas foram absorvidas por etapa). A principal mantém ID, classe e regra."""
    principais = [f for f in ocorrencias if not do_languagetool(f) and familia(f)]
    absorvidas, por_etapa = set(), {}
    for item in ocorrencias:
        if not do_languagetool(item) or familia(item) is None:
            continue
        candidatas = [f for f in principais if equivalentes(f, item)]
        if not candidatas:
            continue
        nome = familia(item)
        if FAMILIAS[nome]["principal"] != "fonte":
            continue
        principal = candidatas[0]
        principal.setdefault("absorvidos", []).append(registro(item, nome))
        principal["detectores"] = list(dict.fromkeys([principal["source"], *(a["source"] for a in principal["absorvidos"])]))
        absorvidas.add(id(item))
        por_etapa[item.get("module")] = por_etapa.get(item.get("module"), 0) + 1
        if observar:
            observar("consolidar", item, [principal])
    return [f for f in ocorrencias if id(f) not in absorvidas], por_etapa
