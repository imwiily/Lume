"""Experimento V4.1 do Validador de decisões: Sonnet como único avaliador; dois julgamentos separados; antecedentes por relevância.

Experimental e fora da interface de produção. Nada chama a API sem `executar` e um teto explícito. Os casos
do experimento são dados externos (os mesmos IDs do experimento A/B da V3): o repositório é público e não
guarda trechos nem nomes de manuscritos reais.

    planejar   o que seria analisado e o que seria reutilizado sem custo, com estimativa (sem rede)
    executar   analisa só o que é novo (ou o que --revalidar pedir); grava só na pasta do projeto
    comparar   V4 × V3 por apontamento, a partir dos arquivos já gravados (só leitura)
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RAIZ / "fonte"), str(RAIZ / "coerencia")]

from fonte import validador_v4_1 as v4  # noqa: E402
from fonte.reader import read_manuscript  # noqa: E402
from fonte.settings import load as carregar, validate  # noqa: E402


def _tudo(args):
    relatorio = json.loads(Path(args.relatorio).read_text(encoding="utf-8"))
    decisoes = json.loads(Path(args.decisoes).read_text(encoding="utf-8"))
    config = carregar(Path(args.config)) if getattr(args, "config", None) else validate({})
    caminho = Path(args.arquivo).expanduser().resolve()
    blocks, _ = read_manuscript(caminho, config)
    return blocks, relatorio["findings"], decisoes.get("decisions", decisoes), config, \
        hashlib.sha256(caminho.read_bytes()).hexdigest(), caminho


def planejar(args):
    blocks, findings, decisoes, config, sha, _ = _tudo(args)
    revalidar = [i for i in (args.revalidar or [])]
    e = v4.estimar(blocks, findings, decisoes, args.projeto, revalidar=revalidar, config=config, teto=args.teto)
    p = v4.planejar(blocks, findings, decisoes, args.projeto, revalidar=revalidar, config=config)
    print(json.dumps({"manuscrito_sha256": sha, "estimativa": e, "situacoes": p["situacoes"],
                      "estados_ui": {i: v["estado_ui"] for i, v in p["itens"].items()}}, ensure_ascii=False, indent=1))


def executar(args):
    blocks, findings, decisoes, config, sha, caminho = _tudo(args)
    if not sha.startswith(args.sha_esperado):
        raise SystemExit(f"Manuscrito {sha[:12]} não é o esperado ({args.sha_esperado}).")
    meta = {"documento": caminho.name, "sha256_manuscrito": sha}
    progresso = lambda etapa, feitos, total: print(
        "V41_PROGRESSO " + json.dumps({"etapa": etapa, "feitos": feitos, "total": total}), flush=True)
    try:
        _, avisos, resumo = v4.avaliar(blocks, findings, decisoes, pasta=args.projeto, teto=args.teto,
                                       revalidar=args.revalidar or [], avancar=progresso, meta=meta, config=config)
    except v4.ValidacaoEmAndamento as erro:
        raise SystemExit(str(erro))
    for aviso in avisos:
        print(aviso, flush=True)
    print("V41_RESUMO " + json.dumps(resumo, ensure_ascii=False), flush=True)


def comparar(args):
    registros, _ = v4.ler(args.projeto)
    v3 = {}
    for rotulo, caminho in (("V4", args.v4), ("V3-A", args.v3_a)):
        if caminho:
            v3[rotulo] = json.loads(Path(caminho).read_text(encoding="utf-8"))["itens"]
    relatorio = {f["id"]: f for f in json.loads(Path(args.relatorio).read_text(encoding="utf-8"))["findings"]}
    ids = json.loads(Path(args.ids).read_text(encoding="utf-8"))["ids"]
    for i in ids:
        f = relatorio[i]
        r = registros.get(i, {})
        linha = f"§{f['paragraph']} «{f['text'][f['start']:f['end']][:26]}» {f['category'][:20]}"
        extras = " ".join(f"V3-{k}={v.get(i, {}).get('estado', '-')}" for k, v in v3.items())
        print(f"{linha:<62} V4={r.get('estado', '-'):<22} {extras}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="comando", required=True)
    comuns = argparse.ArgumentParser(add_help=False)
    comuns.add_argument("arquivo")
    comuns.add_argument("--relatorio", required=True)
    comuns.add_argument("--decisoes", required=True, help="JSON de decisões (use o filtrado do experimento)")
    comuns.add_argument("--config")
    comuns.add_argument("--projeto", required=True)
    comuns.add_argument("--revalidar", nargs="*", help="IDs de apontamentos desatualizados cuja nova análise foi confirmada")
    a = sub.add_parser("planejar", parents=[comuns])
    a.add_argument("--teto", type=float)
    a.set_defaults(fn=planejar)
    b = sub.add_parser("executar", parents=[comuns])
    b.add_argument("--teto", type=float, required=True, help="Gasto máximo em US$ (sem padrão)")
    b.add_argument("--sha-esperado", required=True)
    b.set_defaults(fn=executar)
    c = sub.add_parser("comparar")
    c.add_argument("--projeto", required=True)
    c.add_argument("--relatorio", required=True)
    c.add_argument("--ids", required=True)
    c.add_argument("--v4", help="validacoes-v4.json de referência")
    c.add_argument("--v3-a")
    c.set_defaults(fn=comparar)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
