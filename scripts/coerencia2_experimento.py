"""Coerência 2.0 (experimental): planejar, executar uma leitura global e comparar com o Coerência 1.2.0.

Fora do app e do motor embutido. Só `executar` usa a rede, e recusa enviar sem --autorizo-envio, --teto,
--sha-esperado e sem que o pior caso caiba no teto. Os arquivos de saída contêm trechos do manuscrito: ficam
em `build/`, fora do Git.

    planejar    cobertura e custo, sem rede
    executar    UMA leitura global (modelo e esforço configuráveis); grava coerencia2-resultado.json
    comparar    resultado 2.0 × relatório do FONTE com Coerência 1.2.0 (rule=coerencia_ia): sobreposição,
                itens exclusivos e modelo de anotação humana
    ficha       tabela completa e ficha de anotação humana cega a partir do resultado
    metricas    precisão por versão a partir da anotação humana preenchida
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RAIZ / "fonte"), str(RAIZ / "coerencia")]

from coerencia.leitura import Paragrafo  # noqa: E402
from coerencia2 import auditoria as aud  # noqa: E402
from fonte.reader import read_manuscript  # noqa: E402
from fonte.settings import validate  # noqa: E402

VEREDITOS = ("procedente", "improcedente", "intencional", "duvida")


def _ler(args):
    caminho = Path(args.arquivo).expanduser().resolve()
    blocks, _ = read_manuscript(caminho, validate({}))
    paragrafos = [Paragrafo(b.number, b.text, b.chapter, bool(b.heading)) for b in blocks]
    return paragrafos, hashlib.sha256(caminho.read_bytes()).hexdigest(), caminho.name


def planejar(args):
    paragrafos, sha, nome = _ler(args)
    e = aud.estimar(paragrafos, args.modelo, args.esforco, nome, args.inacabada, args.limite, max_tokens=args.max_tokens)
    print(json.dumps({"manuscrito_sha256": sha, "estimativa": e}, ensure_ascii=False, indent=1))


def executar(args):
    from coerencia.modelo import Orcamento
    from coerencia2.uma_requisicao import criar_uma_requisicao
    paragrafos, sha, nome = _ler(args)
    if not sha.startswith(args.sha_esperado):
        raise SystemExit(f"Manuscrito {sha[:12]} não é o esperado ({args.sha_esperado}). Nada foi enviado.")
    e = aud.estimar(paragrafos, args.modelo, args.esforco, nome, args.inacabada, args.limite, max_tokens=args.max_tokens)
    print(json.dumps({"estimativa": e}, ensure_ascii=False), flush=True)
    if not e["cabe_em_uma_leitura"]:
        raise SystemExit(f"{e['motivo_se_nao_cabe']} Nada foi enviado (leitura global não realizada).")
    if e["custo_maximo_usd"] > args.teto:
        raise SystemExit(f"O pior caso (US$ {e['custo_maximo_usd']}) excede o teto (US$ {args.teto}): nada foi enviado.")
    if not args.autorizo_envio:
        raise SystemExit("Faltou --autorizo-envio: o texto do manuscrito só vai ao provedor com autorização explícita.")
    # Uma única requisição: sem repetição, sem verificação prévia e sem retomada no servidor.
    cliente = criar_uma_requisicao(args.modelo, args.esforco, args.max_tokens, Orcamento(args.teto))
    pasta = Path(args.saida)
    pasta.mkdir(parents=True, exist_ok=True)
    resultado = aud.auditar(paragrafos, cliente, nome, args.inacabada, args.limite, pasta)
    resultado["manuscrito"]["sha256_do_arquivo"] = sha
    (pasta / "coerencia2-resultado.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"cobertura": resultado["cobertura"]["tipo"], "apontamentos": len(resultado["apontamentos"]),
                      "rejeitados": len(resultado["rejeitados_pela_verificacao"]), "requisicoes": cliente.requisicoes, "max_tokens": cliente.max_tokens, "custo_usd": resultado["custo_usd"],
                      "tokens": {k: resultado["uso"][k] for k in ("tokens_entrada_total", "tokens_cache_leitura",
                                                                  "tokens_cache_criacao", "tokens_saida")},
                      "modelos": resultado["modelos_que_responderam"], "saida": str(pasta)}, ensure_ascii=False))


def _paragrafos_v1(item):
    return {item["paragraph"], *(r["paragraph"] for r in (item.get("related") or []))}


def comparar(args):
    v2 = json.loads(Path(args.v2).read_text(encoding="utf-8"))
    relatorio = json.loads(Path(args.v1).read_text(encoding="utf-8"))
    v1 = [f for f in relatorio["findings"] if f.get("rule") == "coerencia_ia"]
    if relatorio.get("sha256") != v2["manuscrito"].get("sha256_do_arquivo"):
        print("AVISO: o relatório 1.2.0 e o resultado 2.0 não são do mesmo arquivo; a comparação não vale.", file=sys.stderr)
    lado2 = [{"id": a["id"], "paragrafos": sorted({e["paragrafo"] for e in a["evidencias"]}), "item": a} for a in v2["apontamentos"]]
    lado1 = [{"id": f["id"], "paragrafos": sorted(_paragrafos_v1(f)), "item": f} for f in v1]
    cruza = lambda x, y: bool(set(x["paragrafos"]) & set(y["paragrafos"]))
    comuns = [(a["id"], b["id"]) for a in lado1 for b in lado2 if cruza(a, b)]
    saida = {
        "cobertura_2_0": v2["cobertura"], "custo_2_0_usd": v2["custo_usd"], "uso_2_0": aud.uso_do_resultado(v2), "modelos_2_0": v2["modelos_que_responderam"],
        "contagens": {"coerencia_1_2_0": len(lado1), "coerencia_2_0": len(lado2),
                      "ambos_no_mesmo_trecho": len(comuns),
                      "so_1_2_0": sum(not any(cruza(a, b) for b in lado2) for a in lado1),
                      "so_2_0": sum(not any(cruza(a, b) for b in lado1) for a in lado2)},
        "pares_sobrepostos": comuns,
        "modelo_de_anotacao": [{"versao": nome, "id": x["id"], "paragrafos": x["paragrafos"], "veredito": None,
                                "relevancia": None, "observacao": ""}
                               for nome, lado in (("1.2.0", lado1), ("2.0", lado2)) for x in lado],
        "vereditos_possiveis": VEREDITOS,
    }
    print(json.dumps(saida, ensure_ascii=False, indent=1))


def ficha(args):
    """Tabela completa (com tudo o que o modelo disse) e ficha de anotação cega (sem prioridade, certeza nem destino,
    para o julgamento humano não ser ancorado). Nada é filtrado nem reinterpretado."""
    v2 = json.loads(Path(args.v2).read_text(encoding="utf-8"))
    paragrafos, sha, _ = _ler(args)
    if sha != v2["manuscrito"].get("sha256_do_arquivo"):
        raise SystemExit("O arquivo não é o que foi analisado (SHA-256 diferente): a ficha não seria válida.")
    texto = {p.numero: p.texto for p in paragrafos}
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    linhas = ["# Coerência 2.0 — apontamentos (resposta original, sem filtro)", ""]
    for i, a in enumerate(v2["apontamentos"], 1):
        linhas += [f"## {i}. `{a['id']}` · {a['categoria']} · {a['natureza']} · {a['prioridade']} · certeza {a['certeza']}",
                   f"- Situação: {a['situacao']} · destino: {a['destino']} · pode ser intencional (modelo): {a['pode_ser_intencional']}",
                   f"- Título: {a['titulo']}", f"- Explicação: {a['explicacao']}"]
        if a["relevancia_da_lacuna"]:
            linhas.append(f"- Relevância da lacuna: {a['relevancia_da_lacuna']}")
        linhas.append(f"- Leituras alternativas: {a['leituras_alternativas'] or '—'}")
        linhas += [f"- §{e['paragrafo']} ({e['papel']}, {e['inicio']}–{e['fim']}): “{e['texto_original']}”"
                   for e in a["evidencias"]] + [""]
    (saida / "tabela-apontamentos.md").write_text("\n".join(linhas), encoding="utf-8")
    itens = [{"versao": "2.0", "id": a["id"], "paragrafos": sorted({e["paragrafo"] for e in a["evidencias"]}),
              "explicacao_da_ia": a["explicacao"],
              "evidencias": [{"paragrafo": e["paragrafo"], "trecho": e["texto_original"], "paragrafo_inteiro": texto[e["paragrafo"]]}
                             for e in a["evidencias"]],
              "veredito": None, "relevancia": None, "observacao": ""} for a in v2["apontamentos"]]
    (saida / "ficha-anotacao.json").write_text(json.dumps(
        {"manuscrito_sha256": sha, "vereditos_possiveis": VEREDITOS, "modelo_de_anotacao": itens},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"itens": len(itens), "saida": str(saida)}, ensure_ascii=False))


def metricas(args):
    itens = json.loads(Path(args.anotacao).read_text(encoding="utf-8"))["modelo_de_anotacao"]
    saida = {}
    for versao in sorted({i["versao"] for i in itens}):
        decididos = [i for i in itens if i["versao"] == versao and i["veredito"] in VEREDITOS[:3]]
        certos = sum(i["veredito"] == "procedente" for i in decididos)
        saida[versao] = {"anotados": len(decididos), "procedentes": certos,
                         "precisao": round(certos / len(decididos), 3) if decididos else None,
                         "sem_veredito": sum(i["versao"] == versao and i["veredito"] is None for i in itens)}
    print(json.dumps(saida, ensure_ascii=False, indent=1))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for nome, fn in (("planejar", planejar), ("executar", executar)):
        s = sub.add_parser(nome)
        s.add_argument("arquivo")
        s.add_argument("--modelo", default=aud.MODELO_PADRAO)
        s.add_argument("--esforco", default=aud.ESFORCO_PADRAO)
        s.add_argument("--limite", type=int, default=aud.LIMITE_CARACTERES)
        s.add_argument("--inacabada", action="store_true")
        s.add_argument("--max-tokens", type=int, default=aud.MAX_TOKENS,
                       help="limite de saída da requisição, raciocínio incluído (padrão 16000)")
        if nome == "executar":
            s.add_argument("--teto", type=float, required=True)
            s.add_argument("--sha-esperado", required=True)
            s.add_argument("--saida", required=True)
            s.add_argument("--autorizo-envio", action="store_true")
        s.set_defaults(fn=fn)
    s = sub.add_parser("comparar")
    s.add_argument("--v1", required=True, help="relatorio.json do FONTE com Coerência 1.2.0")
    s.add_argument("--v2", required=True, help="coerencia2-resultado.json")
    s.set_defaults(fn=comparar)
    s = sub.add_parser("ficha")
    s.add_argument("arquivo")
    s.add_argument("--v2", required=True)
    s.add_argument("--saida", required=True)
    s.set_defaults(fn=ficha)
    s = sub.add_parser("metricas")
    s.add_argument("--anotacao", required=True)
    s.set_defaults(fn=metricas)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
