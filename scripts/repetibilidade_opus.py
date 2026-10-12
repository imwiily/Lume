"""Teste de repetibilidade do Opus direto (arquitetura candidata do Validador de decisões). PREPARADO, não executado.

Mede quanto o julgamento muda quando a MESMA entrada é enviada de novo, e quanto muda quando só a ordem ou o
agrupamento dos pedidos muda. Reutiliza `validador_v3.avaliar` (grupo A) sem alterá-lo; a ordem e o tamanho do
lote são alterados em memória, só neste processo. Cada rodada grava em pasta própria (nunca sobrescreve),
guarda os identificadores brutos das chamadas (id do pedido, modelo servido, tokens) e nenhum texto do manuscrito.

    plano     rodadas, chamadas e custo previstos (sem rede)
    executar  uma rodada, com teto obrigatório; recusa pasta existente e manuscrito com SHA diferente
    analisar  estabilidade por apontamento entre as rodadas já gravadas (só lê arquivos)
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RAIZ / "fonte"), str(RAIZ / "coerencia")]

from fonte import validador_v3 as v3  # noqa: E402

ARQUIVO = v3.ARQUIVO["A"]


def nucleo(registro):
    """Núcleo interpretativo de um julgamento: o que o modelo concluiu, sem o rótulo final."""
    av = registro.get("avaliacao") or {}
    return (av.get("procede"), av.get("decisao_coerente"))


def estabilidade(rodadas):
    """`rodadas`: lista de {id: registro}. Por apontamento: estados, concordância e se a variação é só de
    rótulo (mesmo núcleo) ou de interpretação (núcleo diferente). Ids ausentes numa rodada contam como instáveis."""
    ids = sorted(set().union(*[set(r) for r in rodadas])) if rodadas else []
    itens, n = {}, len(rodadas)
    for i in ids:
        regs = [r.get(i) for r in rodadas]
        estados = [x["estado"] if x else None for x in regs]
        nucleos = [nucleo(x) if x else None for x in regs]
        moda, freq = Counter(estados).most_common(1)[0]
        if len(set(estados)) == 1 and None not in estados:
            tipo = "estavel"
        elif len(set(nucleos)) == 1 and None not in nucleos:
            tipo = "so_rotulo"
        else:
            tipo = "interpretacao"
        # Contestada em algumas rodadas e não em todas é a variação mais custosa para o autor.
        cruza = "contestada" in estados and any(e != "contestada" for e in estados)
        itens[i] = {"estados": estados, "moda": moda, "concordancia": round(freq / n, 3), "tipo": tipo,
                    "cruza_contestacao": cruza, "editorial": [(x.get("avaliacao") or {}).get("justificativa_editorial") if x else None
                                                              for x in regs]}
    total = max(len(itens), 1)
    resumo = {"rodadas": n, "itens": len(itens),
              "estaveis": sum(v["tipo"] == "estavel" for v in itens.values()),
              "so_rotulo": sum(v["tipo"] == "so_rotulo" for v in itens.values()),
              "interpretacao": sum(v["tipo"] == "interpretacao" for v in itens.values()),
              "cruzam_contestacao": sum(v["cruza_contestacao"] for v in itens.values()),
              "concordancia_media": round(sum(v["concordancia"] for v in itens.values()) / total, 3)}
    return itens, resumo


def ler_rodadas(projeto):
    pastas = sorted(p for p in Path(projeto).glob("r[0-9]*") if (p / ARQUIVO).exists())
    return [(p.name, json.loads((p / ARQUIVO).read_text(encoding="utf-8"))["itens"]) for p in pastas]


def rodar_rodada(blocks, findings, decisoes, rodada, projeto, teto, *, ordem="original", lote=None, cliente=None,
                 meta=None, configuracao=None):
    """Executa uma rodada do grupo A. `cliente`: injeção para testes; sem ele, usa o Claude real com orçamento."""
    pasta = Path(projeto) / f"r{rodada}"
    if pasta.exists():
        raise ValueError(f"A pasta {pasta.name} já existe: cada rodada é nova (nada é sobrescrito).")
    if teto <= 0:
        raise ValueError("Informe um teto positivo.")
    achados = list(reversed(findings)) if ordem == "invertida" else list(findings)
    original = dict(v3.LOTE)
    if lote:
        v3.LOTE = dict(original, opus=(lote, original["opus"][1]))
    try:
        if cliente is None:
            from coerencia.modelo import Claude, Orcamento
            cliente = Claude(v3.OPUS, esforco=v3.ESFORCO, orcamento=Orcamento(teto))
            cliente.verificar()
        antes = len(cliente.chamadas)
        resultados, avisos, resumo = v3.avaliar(blocks, achados, decisoes, "A", pasta=pasta, teto=teto,
                                                clientes={"opus": cliente}, meta=dict(meta or {}, rodada=rodada,
                                                                                      ordem=ordem, lote=lote),
                                                configuracao=configuracao)
    finally:
        v3.LOTE = original
    brutas = [{k: c.get(k) for k in ("etapa", "pedido", "modelo_usado", "tokens_entrada", "tokens_cache",
                                     "tokens_cache_criacao", "tokens_saida", "segundos", "custo_usd", "presumido")}
              for c in cliente.chamadas[antes:]]
    (pasta / f"chamadas-brutas-r{rodada}.json").write_text(json.dumps(brutas, indent=1), encoding="utf-8")
    return resultados, avisos, resumo


def _carregar(args):
    from fonte.reader import read_manuscript
    from fonte.settings import load as carregar, validate
    relatorio = json.loads(Path(args.relatorio).read_text(encoding="utf-8"))
    decisoes = json.loads(Path(args.decisoes).read_text(encoding="utf-8"))
    config = carregar(Path(args.config)) if getattr(args, "config", None) else validate({})
    caminho = Path(args.arquivo).expanduser().resolve()
    blocks, _ = read_manuscript(caminho, config)
    return blocks, relatorio["findings"], decisoes.get("decisions", decisoes), config, \
        hashlib.sha256(caminho.read_bytes()).hexdigest(), caminho


def plano(args):
    blocks, findings, decisoes, config, sha, _ = _carregar(args)
    e = v3.estimar(blocks, findings, decisoes, "A", configuracao=config)
    n = args.rodadas
    print(json.dumps({
        "manuscrito_sha256": sha, "decisoes": e["elegiveis"], "rodadas": n,
        "rodadas_previstas": [f"r{k}: mesma entrada, mesma ordem, mesmo lote" for k in range(1, n - 1)] +
                             [f"r{n - 1}: ordem invertida", f"r{n}: um item por pedido (--lote 1)"],
        "pedidos_por_rodada": e["chamadas_opus"], "custo_esperado_por_rodada_usd": e["custo_esperado_usd"],
        "custo_maximo_por_rodada_usd": e["custo_maximo_usd"], "teto_minimo_por_rodada_usd": e["teto_minimo_usd"],
        "custo_esperado_total_usd": round(e["custo_esperado_usd"] * n, 2),
        "custo_maximo_total_usd": round(e["custo_maximo_usd"] * n, 2),
        "referencia": "consumo real do Grupo A (6 pedidos): US$ 0,26", "executado": False}, indent=1))


def executar(args):
    blocks, findings, decisoes, config, sha, caminho = _carregar(args)
    if not sha.startswith(args.sha_esperado):
        raise SystemExit(f"Manuscrito {sha[:12]} não é o esperado ({args.sha_esperado}).")
    _, avisos, resumo = rodar_rodada(blocks, findings, decisoes, args.rodada, args.projeto, args.teto,
                                     ordem=args.ordem, lote=args.lote, configuracao=config,
                                     meta={"documento": caminho.name, "sha256_manuscrito": sha})
    for a in avisos:
        print(a)
    print("REPETIBILIDADE_RESUMO " + json.dumps(resumo, ensure_ascii=False))


def analisar(args):
    rodadas = ler_rodadas(args.projeto)
    if len(rodadas) < 2:
        raise SystemExit("São necessárias ao menos duas rodadas gravadas.")
    itens, resumo = estabilidade([r for _, r in rodadas])
    print(json.dumps({"rodadas": [n for n, _ in rodadas], "resumo": resumo,
                      "instaveis": {i: v for i, v in itens.items() if v["tipo"] != "estavel"}}, ensure_ascii=False, indent=1))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="comando", required=True)
    comuns = argparse.ArgumentParser(add_help=False)
    comuns.add_argument("arquivo")
    comuns.add_argument("--relatorio", required=True)
    comuns.add_argument("--decisoes", required=True)
    comuns.add_argument("--config")
    a = sub.add_parser("plano", parents=[comuns])
    a.add_argument("--rodadas", type=int, default=5)
    a.set_defaults(fn=plano)
    b = sub.add_parser("executar", parents=[comuns])
    b.add_argument("--projeto", required=True)
    b.add_argument("--rodada", type=int, required=True)
    b.add_argument("--teto", type=float, required=True)
    b.add_argument("--sha-esperado", required=True)
    b.add_argument("--ordem", choices=("original", "invertida"), default="original")
    b.add_argument("--lote", type=int)
    b.set_defaults(fn=executar)
    c = sub.add_parser("analisar")
    c.add_argument("--projeto", required=True)
    c.set_defaults(fn=analisar)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
