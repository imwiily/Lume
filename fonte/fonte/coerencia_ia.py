"""Coerência com IA: o projeto incremental do Coerencia dentro da etapa Coerência global.

Opcional e desligado por padrão. Os capítulos alterados são enviados à API do
Claude (Anthropic); os inalterados não. As pendências abertas viram ocorrências v1:
o trecho posterior é a ocorrência e o anterior vai em `related`. O manuscrito só é
lido; a memória fica na pasta de projeto indicada pelo app.
"""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re

from .analysis import explicar, finding

REGRA = "coerencia_ia"
CATEGORIA = "Contradição narrativa"
FONTE = "Coerencia · IA (Claude)"


def _coerencia():
    try:
        import coerencia  # noqa: F401
    except ImportError as erro:
        raise ValueError("Este motor não inclui a Coerência com IA. Restaure o motor embutido desta versão do Lume.") from erro
    from coerencia.leitura import Paragrafo
    from coerencia.projeto import Projeto, capitulos
    from coerencia.modelo import ErroModelo, criar_modelo
    return Paragrafo, Projeto, capitulos, ErroModelo, criar_modelo


def paragrafos(blocks):
    """Mesma numeração do FONTE: blocos não vazios, títulos incluídos."""
    Paragrafo = _coerencia()[0]
    return [Paragrafo(b.number, b.text, b.chapter, bool(b.heading)) for b in blocks]


def estimar(blocks, pasta, modelo="claude-sonnet-5-5"):
    _, Projeto, *_ = _coerencia()
    return Projeto(pasta).estimar(paragrafos(blocks), modelo)


def _intervalo(texto, trecho):
    palavras = re.findall(r"\w+", trecho)
    achado = re.search(r"\W+".join(map(re.escape, palavras)), texto, re.I) if palavras else None
    return (achado.start(), achado.end()) if achado else (0, len(texto))


def analisar(blocks, pasta, documento="manuscrito", modelo="claude-sonnet-5-5", teto=1.0, esforco="medium",
             registrar=print, avancar=None):
    """Roda uma rodada incremental e devolve (ocorrências, avisos, resumo da rodada)."""
    _, Projeto, capitulos, ErroModelo, criar_modelo = _coerencia()
    lista = paragrafos(blocks)
    cliente = criar_modelo(modelo, esforco=esforco, teto=teto)
    try:
        cliente.verificar()
        projeto = Projeto(pasta)
        rodada = projeto.atualizar(documento, lista, cliente, registrar=registrar, avancar=avancar)
    except ErroModelo as erro:
        raise ValueError("Coerência com IA: " + str(erro)) from erro
    por_numero = {b.number: b for b in blocks}
    caps = {c.id: c for c in capitulos(lista)}
    ocorrencias, avisos = [], []

    def localizar(lado):
        cap = caps.get(lado["capitulo"])
        if cap is None or not 0 <= lado["rel"] < len(cap.paragrafos):
            return None
        bloco = por_numero[cap.paragrafos[lado["rel"]].numero]
        return bloco, _intervalo(bloco.text, lado["trecho"])

    for pendencia in projeto.pendencias:
        if pendencia["status"] != "aberta":
            continue
        a, b = localizar(pendencia["a"]), localizar(pendencia["b"])
        if not a or not b:
            continue
        (bloco_a, (ia, fa)), (bloco_b, (ib, fb)) = a, b
        relacionado = [dict(paragraph=bloco_a.number, chapter=bloco_a.chapter, text=bloco_a.text,
                            start=ia, end=fa, document="atual")]
        explicacao = pendencia["explicacao"]
        if pendencia.get("relacionadas"):
            explicacao += f" (Também apontado em {len(pendencia['relacionadas'])} outro(s) trecho(s) próximo(s).)"
        item = asdict(finding(bloco_b, CATEGORIA, "Verificar", ib, fb,
                              explicar(explicacao, "contradição de continuidade"), FONTE))
        alta = pendencia.get("confianca") == "alta"
        item.update(rule=REGRA, category_code="narrative_contradiction_ai", layer="editorial",
                    severity="possible_inconsistency", confidence="alta" if alta else "média",
                    confidence_score=.85 if alta else .65, related=relacionado, suggestion=None,
                    suggestion_kind="possible")
        # A identidade inclui o trecho anterior: outra evidência não herda decisão antiga.
        identidade = item["id"] + json.dumps(relacionado, ensure_ascii=False, sort_keys=True)
        item["id"] = hashlib.sha256(identidade.encode()).hexdigest()[:16]
        ocorrencias.append(item)
    if rodada.get("interrompida"):
        faltam = rodada["a_enviar"] - rodada["enviados"]
        avisos.append(f"Coerência com IA: teto de gasto atingido. {faltam} capítulo(s) e parte dos julgamentos ficaram "
                      f"para a próxima análise; o que foi lido está salvo. {rodada['interrompida']}")
    avisos.append(f"Coerência com IA ({modelo}): {rodada['enviados']} de {rodada['capitulos']} capítulos enviados à "
                  f"Anthropic; custo estimado US$ {rodada['custo_usd']:.4f}. Contradições são suspeitas para avaliação "
                  "humana, não erros confirmados.")
    return ocorrencias, avisos, rodada
