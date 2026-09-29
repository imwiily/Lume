"""Relatório HTML autocontido: cada contradição com os dois parágrafos lado a lado.

O trecho citado aparece destacado dentro do parágrafo completo. Não carrega
nada de fora (sem scripts nem fontes externas) e funciona em modo claro e escuro.
"""
from datetime import datetime
from html import escape
import re

ESTILO = """
:root{--fundo:#faf8f4;--cartao:#fff;--texto:#1f1d1a;--suave:#6b665e;--borda:#e4ded3;--marca:#fbe3a1;--a:#2f6f9f;--b:#a6452f;
--alta:#a6452f;--media:#9a6b00;--baixa:#6b665e}
@media (prefers-color-scheme:dark){:root{--fundo:#161513;--cartao:#1f1e1b;--texto:#ece8e1;--suave:#a39d93;--borda:#34312c;
--marca:#6b5518;--a:#7fb3d9;--b:#e0907c;--alta:#e0907c;--media:#e0b54f;--baixa:#a39d93}}
*{box-sizing:border-box}body{margin:0;background:var(--fundo);color:var(--texto);font:16px/1.55 Georgia,"Times New Roman",serif}
main{max-width:1040px;margin:0 auto;padding:28px 16px 64px}h1{font-size:1.6rem;margin:0 0 4px}
.meta{color:var(--suave);font:14px/1.5 -apple-system,system-ui,sans-serif;margin-bottom:24px}
.cartao{background:var(--cartao);border:1px solid var(--borda);border-radius:10px;padding:18px;margin:0 0 18px}
.topo{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;font:14px/1.4 -apple-system,system-ui,sans-serif;margin-bottom:12px}
.id{font-weight:700}.selo{padding:1px 8px;border-radius:99px;border:1px solid currentColor;font-size:12px}
.alta{color:var(--alta)}.media{color:var(--media)}.baixa{color:var(--baixa)}.estado{color:var(--suave)}
.lados{display:grid;grid-template-columns:1fr 1fr;gap:14px}@media (max-width:720px){.lados{grid-template-columns:1fr}}
.lado{border-left:4px solid var(--a);padding:4px 0 4px 12px}.lado.b{border-left-color:var(--b)}
.rotulo{font:12px/1.4 -apple-system,system-ui,sans-serif;color:var(--suave);text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px}
mark{background:var(--marca);color:inherit;padding:0 2px;border-radius:3px}
.explicacao{margin-top:12px;font:15px/1.5 -apple-system,system-ui,sans-serif}
.relacionadas{margin-top:10px;font:13px/1.5 -apple-system,system-ui,sans-serif;color:var(--suave)}
.comando{font:12px/1.4 ui-monospace,Menlo,monospace;color:var(--suave);margin-top:10px}
table{width:100%;border-collapse:collapse;font:14px/1.4 -apple-system,system-ui,sans-serif;margin-bottom:24px}
td,th{text-align:left;padding:6px 8px;border-bottom:1px solid var(--borda)}th{color:var(--suave);font-weight:600}
.vazio{color:var(--suave);font-style:italic}
"""


def destacar(texto, trecho):
    """Envolve o trecho em <mark>, tolerando diferenças de espaço, aspas e caixa."""
    palavras = re.findall(r"\w+", trecho)
    if palavras:
        achado = re.search(r"\W+".join(map(re.escape, palavras)), texto, re.I)
        if achado:
            return escape(texto[:achado.start()]) + "<mark>" + escape(achado[0]) + "</mark>" + escape(texto[achado.end():])
    return escape(texto)


def lado(classe, rotulo, paragrafo, trecho):
    corpo = destacar(paragrafo, trecho) if paragrafo else f"<mark>{escape(trecho)}</mark>"
    return f'<div class="lado {classe}"><div class="rotulo">{escape(rotulo)}</div>{corpo}</div>'


def cartao(ident, estado, confianca, a, b, explicacao, relacionadas=(), comando=""):
    conf = confianca if confianca in ("alta", "media", "baixa") else "media"
    extra = ""
    if relacionadas:
        itens = "; ".join(f"“{escape(r['a']['trecho'])}” × “{escape(r['b']['trecho'])}”" for r in relacionadas)
        extra = f'<div class="relacionadas">Também apontado: {itens}</div>'
    estado_html = f'<span class="estado">{escape(estado)}</span>' if estado else ""
    return (f'<section class="cartao"><div class="topo"><span class="id">{escape(ident)}</span>'
            f'<span class="selo {conf}">confiança {"média" if conf == "media" else conf}</span>{estado_html}</div>'
            f'<div class="lados">{lado("a", *a)}{lado("b", *b)}</div>'
            f'<div class="explicacao">{escape(explicacao)}</div>{extra}'
            + (f'<div class="comando">{escape(comando)}</div>' if comando else "") + "</section>")


def pagina(titulo, meta, corpo):
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    return (f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(titulo)}</title>'
            f'<style>{ESTILO}</style></head><body><main><h1>{escape(titulo)}</h1>'
            f'<div class="meta">{escape(meta)} · gerado em {agora}</div>{corpo}</main></body></html>')


def avulso(documento, modelo, contradicoes, paragrafos, custo):
    """Relatório de uma análise avulsa (sem projeto)."""
    texto = {p.numero: p.texto for p in paragrafos}
    cartoes = [cartao(f"{n}", "", c.get("confianca"),
                      (f"§{c['a']['paragrafo']} · antes", texto.get(c["a"]["paragrafo"]), c["a"]["trecho"]),
                      (f"§{c['b']['paragrafo']} · depois", texto.get(c["b"]["paragrafo"]), c["b"]["trecho"]),
                      c["explicacao"], c.get("relacionadas", ()))
               for n, c in enumerate(contradicoes, 1)]
    corpo = "".join(cartoes) or '<p class="vazio">Nenhuma contradição apontada.</p>'
    return pagina(f"Contradições · {documento}",
                  f"{len(contradicoes)} apontadas · modelo {modelo} · US$ {custo:.4f}", corpo)


def de_projeto(projeto, capitulos, pasta_projeto):
    """Relatório do projeto: capítulos e pendências abertas, com o texto atual."""
    por_id = {c.id: c for c in capitulos}

    def paragrafo(lado_):
        cap = por_id.get(lado_["capitulo"])
        if cap is None or not 0 <= lado_["rel"] < len(cap.paragrafos):
            return None
        return cap.paragrafos[lado_["rel"]].texto

    linhas = "".join(
        f"<tr><td>{escape(c['titulo'])}</td><td>{'com pendências' if c.get('situacao') == 'com_pendencias' else 'sem pendências'}"
        f"</td><td>{escape(c['lido_em'].replace('T', ' '))}</td><td>{c.get('tokens', 0)}</td></tr>"
        for c in sorted(projeto.estado["capitulos"].values(), key=lambda c: c["ordem"]))
    abertas = [p for p in projeto.pendencias if p["status"] == "aberta"]
    cartoes = "".join(cartao(
        p["id"], "aberta", p.get("confianca"),
        (f"{p['a']['titulo']} · antes", paragrafo(p["a"]), p["a"]["trecho"]),
        (f"{p['b']['titulo']} · depois", paragrafo(p["b"]), p["b"]["trecho"]),
        p["explicacao"], p.get("relacionadas", ()),
        f"coerencia decidir {p['id']} corrigida|intencional --projeto {pasta_projeto}") for p in abertas)
    fechadas = len(projeto.pendencias) - len(abertas)
    custo = sum(r.get("custo_usd", 0) for r in projeto.rodadas)
    corpo = (f"<table><tr><th>Capítulo</th><th>Situação</th><th>Última leitura</th><th>Tokens</th></tr>{linhas}</table>"
             + (cartoes or '<p class="vazio">Nenhuma pendência aberta.</p>'))
    return pagina(f"Contradições · {projeto.estado.get('documento', 'projeto')}",
                  f"{len(abertas)} abertas, {fechadas} decididas ou resolvidas · {len(projeto.rodadas)} rodadas · "
                  f"US$ {custo:.4f} no total", corpo)
