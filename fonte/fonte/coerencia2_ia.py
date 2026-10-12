"""Coerência 2.0 no Lume: uma leitura global da obra, numa só requisição paga, depois de confirmação.

Opcional e desligada por padrão, como a Coerência 1.x. O motor (`coerencia2`) lê, numera, limita a cobertura, controla o
teto e confere cada citação no texto original; aqui os apontamentos viram ocorrências v1. Todos entram como
informação ou diagnóstico (classe nova, sem medição em livros reais) e nunca são impeditivos. O manuscrito só é lido;
cache e resultado ficam na pasta de projeto indicada pelo app (`global2/`). Plano: `.agent/plans/coerencia-2-ia.md`.
"""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from .analysis import explicar, finding

REGRA = "coerencia2_ia"
FONTE = "Coerencia 2.0 · IA ({})"
PASTA = "global2"
CONFIANCA = {"alta": ("média", .65), "media": ("média", .55), "baixa": ("baixa", .4)}


def _motor():
    try:
        import coerencia2  # noqa: F401
    except ImportError as erro:
        raise ValueError("Este motor não inclui a Coerência 2.0. Restaure o motor embutido desta versão do Lume.") from erro
    from coerencia import modelo as compartilhado
    from coerencia.leitura import Paragrafo
    from coerencia2 import auditoria
    from coerencia2.uma_requisicao import criar_uma_requisicao
    return Paragrafo, auditoria, criar_uma_requisicao, compartilhado


def _paragrafos(blocks):
    Paragrafo = _motor()[0]
    return [Paragrafo(b.number, b.text, b.chapter, bool(b.heading)) for b in blocks]


def _provedor(modelo):
    return "Gemini" if modelo.startswith("gemini-") else "Claude"


def estimar(blocks, pasta, modelo="claude-sonnet-5-5", esforco="medium"):
    """Mesma forma da estimativa da Coerência 1.x (para o app), sem chamar a API nem criar o cliente."""
    _, auditoria, _, _ = _motor()
    lista = _paragrafos(blocks)
    e = auditoria.estimar(lista, modelo, esforco)
    chave = auditoria._chave_cache(lista, modelo, esforco, "manuscrito", False, e["max_tokens"])
    arquivo = Path(pasta) / PASTA / "cache-global.json"
    try:
        guardado = json.loads(arquivo.read_text(encoding="utf-8")).get("chave") == chave
    except (OSError, ValueError):
        guardado = False
    enviar = bool(e["cabe_em_uma_leitura"]) and not guardado
    return {"versao": 2, "modelo": modelo, "provedor": e["provedor"], "capitulos": 1, "a_enviar": int(enviar),
            "titulos_a_enviar": ["Obra inteira (uma só requisição)"] if enviar else [], "caracteres": e["caracteres"] if enviar else 0,
            "custo_estimado_usd": (e["custo_esperado_usd"] or 0) if enviar else 0.0,
            "custo_maximo_usd": (e["custo_maximo_usd"] or 0) if enviar else 0.0,
            "do_cache": guardado, "cabe_em_uma_leitura": e["cabe_em_uma_leitura"], "motivo_se_nao_cabe": e["motivo_se_nao_cabe"],
            "premissa": e["premissa"]}


def _ocorrencia(apontamento, por_numero, fonte):
    evidencias = sorted(apontamento["evidencias"], key=lambda e: (e["paragrafo"], e["inicio"]))
    ancora, anteriores = evidencias[-1], evidencias[:-1]
    bloco = por_numero[ancora["paragrafo"]]
    relacionadas = [dict(paragraph=e["paragrafo"], chapter=por_numero[e["paragrafo"]].chapter,
                         text=por_numero[e["paragrafo"]].text, start=e["inicio"], end=e["fim"], document="atual")
                    for e in anteriores]
    texto = apontamento["explicacao"].strip() + "\n\n" + apontamento["aviso"]
    if apontamento.get("leituras_alternativas"):
        texto += " Leitura alternativa: " + apontamento["leituras_alternativas"].strip()
    item = asdict(finding(bloco, apontamento["categoria_titulo"], "Verificar", ancora["inicio"], ancora["fim"],
                          explicar(texto, "continuidade narrativa"), fonte))
    confianca, nota = CONFIANCA[apontamento["certeza"]]
    item.update(rule=REGRA, category_code="narrative_global_ai", layer="editorial", severity="possible_inconsistency",
                confidence=confianca, confidence_score=nota, related=relacionadas, suggestion=None, suggestion_kind="possible",
                destino=apontamento["destino"], impeditivo=False,
                coerencia2={"natureza": apontamento["natureza"], "prioridade": apontamento["prioridade"],
                            "certeza": apontamento["certeza"], "situacao": apontamento["situacao"],
                            "categoria": apontamento["categoria"]})
    item["id"] = hashlib.sha256(("coerencia2:" + apontamento["id"]).encode()).hexdigest()[:16]
    return item


def analisar(blocks, pasta, documento="manuscrito", modelo="claude-sonnet-5-5", teto=1.0, esforco="medium",
             registrar=print, avancar=None):
    """Uma leitura global; devolve (ocorrências, avisos, resumo da rodada). Falha do modelo não derruba a análise:
    a cobertura do resumo registra o que de fato aconteceu."""
    _, auditoria, criar_uma_requisicao, compartilhado = _motor()
    lista = _paragrafos(blocks)
    destino = Path(pasta) / PASTA
    try:
        cliente = criar_uma_requisicao(modelo, esforco, auditoria.MAX_TOKENS, compartilhado.Orcamento(teto))
    except compartilhado.ErroModelo as erro:
        raise ValueError("Coerência 2.0: " + str(erro)) from erro
    if avancar:
        avancar(0, 1)
    # Título fixo: entra na chave do cache, e a estimativa (que não sabe o documento) precisa chegar à mesma chave.
    resultado = auditoria.auditar(lista, cliente, "manuscrito", False, pasta=destino)
    if avancar:
        avancar(1, 1)
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "coerencia2-resultado.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    fonte = FONTE.format(_provedor(modelo))
    por_numero = {b.number: b for b in blocks}
    ocorrencias = [_ocorrencia(a, por_numero, fonte) for a in resultado["apontamentos"]]
    cobertura = resultado["cobertura"]
    avisos = []
    if cobertura["tipo"] != "global":
        avisos.append(f"Coerência 2.0: a leitura global não foi concluída ({cobertura['tipo']}). {cobertura.get('motivo') or ''}".strip())
    avisos.append(f"Coerência 2.0 ({modelo}): {'resposta reaproveitada do cache, sem custo' if resultado['do_cache'] else str(resultado['chamadas']) + ' requisição ao ' + ('Google' if modelo.startswith('gemini-') else 'provedor')}; "
                  f"custo estimado US$ {resultado['custo_usd']:.4f}; {len(ocorrencias)} apontamento(s), "
                  f"{len(resultado['rejeitados_pela_verificacao'])} rejeitado(s) pela conferência das citações. "
                  "São hipóteses para avaliação humana, nunca erros confirmados nem impeditivos; a precisão ainda não foi medida em livros reais.")
    rodada = {"versao": 2, "modelo": modelo, "capitulos": 1, "enviados": resultado["chamadas"], "cobertura": cobertura["tipo"],
              "custo_usd": resultado["custo_usd"], "do_cache": resultado["do_cache"], "apontamentos": len(ocorrencias),
              "rejeitados": len(resultado["rejeitados_pela_verificacao"]), "uso": resultado["uso"].get("fonte")}
    return ocorrencias, avisos, rodada
