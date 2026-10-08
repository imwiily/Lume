"""Deduplicação entre detectores (núcleo compartilhado; estabilização, Fase 6a).

Deduplicação é quando duas fontes apontam o mesmo trecho e só uma ocorrência é apresentada.
Não é supressão linguística (a regra que decide que a evidência não basta para alertar): essas
ficam em cada regra, como os filtros do LanguageTool em `languagetool.check`.

Cada mecanismo abaixo reproduz o comportamento anterior à Fase 6a, com o mesmo critério de
equivalência e a mesma precedência. Nenhum prova que o fenômeno é o mesmo: hoje a coincidência de
trecho basta (registrado no plano; a Fase 6b avalia, classe por classe). A precedência interna de um
mesmo detector (`temporal.PRECEDENCE`, o primeiro alerta por trecho em `grammar`) fica no detector.

`observar`, quando definido (scripts de medição), recebe cada descarte: (mecanismo, descartado,
motivos). Não muda o resultado nem o relatório.
"""

observar = None


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


def languagetool_sob_regras_linguisticas(languagetool, fonte):
    """Etapa linguística: o alerta do LanguageTool que toca um trecho já apontado por uma regra
    linguística do FONTE (inclusive a palavra dobrada) cai, qualquer que seja o fenômeno."""
    return _descartar(languagetool, "languagetool_sob_regras_linguisticas",
                      lambda item: [f for f in fonte if sobrepoe(item, f)])


def gramatica_sob_languagetool(gramatica, anteriores):
    """Etapa morfossintática: a regra gramatical do FONTE que toca um trecho já apontado pelo
    LanguageTool cai, qualquer que seja o fenômeno."""
    languagetool = [f for f in anteriores if f["source"].startswith("LanguageTool")]
    return _descartar(gramatica, "gramatica_sob_languagetool",
                      lambda item: [f for f in languagetool if sobrepoe(item, f)])


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
