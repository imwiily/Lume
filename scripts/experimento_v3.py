"""Experimento V3 do Validador de decisões: Opus direto (A) × Haiku localizador + Opus (B).

Experimental e fora da interface de produção. Nada chama a API sem `executar` e um teto explícito.
Os casos do experimento são dados externos (--casos): o repositório é público e não guarda trechos nem
nomes de manuscritos reais.

    selecionar  resolve os casos em IDs estáveis, completa por amostragem reprodutível e grava os arquivos
    estimar     chamadas, tokens, custo e teto mínimo por grupo, sem rede
    executar    roda um grupo (A ou B) com o teto informado; grava só na pasta do experimento
    comparar    tabela por apontamento entre A e B (e referências, se informadas)
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RAIZ / "fonte"), str(RAIZ / "coerencia")]

from fonte import validador_decisoes as vd  # noqa: E402
from fonte import validador_v3 as v3  # noqa: E402
from fonte.reader import read_manuscript  # noqa: E402
from fonte.settings import load as carregar, validate  # noqa: E402


def carregar_tudo(args):
    relatorio = json.loads(Path(args.relatorio).read_text(encoding="utf-8"))
    decisoes = json.loads(Path(args.decisoes).read_text(encoding="utf-8"))
    configuracao = carregar(Path(args.config)) if getattr(args, "config", None) else validate({})
    manuscrito = Path(args.arquivo).expanduser().resolve()
    blocks, _ = read_manuscript(manuscrito, configuracao)
    sha = hashlib.sha256(manuscrito.read_bytes()).hexdigest()
    return blocks, relatorio["findings"], decisoes.get("decisions", decisoes), configuracao, sha, manuscrito


def selecionar(args):
    relatorio = json.loads(Path(args.relatorio).read_text(encoding="utf-8"))
    decisoes_json = json.loads(Path(args.decisoes).read_text(encoding="utf-8"))
    findings, decisoes = relatorio["findings"], decisoes_json.get("decisions", decisoes_json)
    casos = json.loads(Path(args.casos).read_text(encoding="utf-8"))
    nomeados = v3.resolver_casos(findings, casos)
    elegiveis = {f["id"] for f in vd.selecionar(findings, decisoes)[0]}
    fora = [i for i in nomeados if i not in elegiveis]
    if fora:
        raise SystemExit(f"Casos sem decisão elegível: {fora}")
    complemento = v3.amostrar_complemento(findings, decisoes, nomeados, args.complemento, args.semente)
    ids = nomeados + complemento
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "ids.json").write_text(json.dumps({"nomeados": nomeados, "complemento": complemento, "semente": args.semente,
                                                "ids": ids}, indent=1), encoding="utf-8")
    filtrado = dict(decisoes_json, decisions={i: decisoes[i] for i in ids})
    (saida / "decisoes.json").write_text(json.dumps(filtrado, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(nomeados)} casos nomeados + {len(complemento)} amostrados = {len(ids)}; gravado em {saida}")


def estimar(args):
    blocks, findings, decisoes, config, sha, _ = carregar_tudo(args)
    grupos = v3.GRUPOS if args.grupo == "ambos" else (args.grupo,)
    saida = {g: v3.estimar(blocks, findings, decisoes, g, pasta=args.projeto, configuracao=config) for g in grupos}
    saida["manuscrito_sha256"] = sha
    print(json.dumps(saida, ensure_ascii=False, indent=1))


def executar(args):
    blocks, findings, decisoes, config, sha, manuscrito = carregar_tudo(args)
    if args.sha_esperado and not sha.startswith(args.sha_esperado):
        raise SystemExit(f"Manuscrito {sha[:12]} não é o esperado ({args.sha_esperado}).")
    meta = {"documento": manuscrito.name, "sha256_manuscrito": sha}
    progresso = lambda etapa, feitos, total: print(f"V3_PROGRESSO {json.dumps({'etapa': etapa, 'feitos': feitos, 'total': total})}", flush=True)
    _, avisos, resumo = v3.avaliar(blocks, findings, decisoes, args.grupo, pasta=args.projeto, teto=args.teto,
                                   avancar=progresso, meta=meta, configuracao=config)
    for aviso in avisos:
        print(aviso, flush=True)
    print("V3_RESUMO " + json.dumps(resumo, ensure_ascii=False), flush=True)


def comparar(args):
    base = Path(args.projeto)
    carregar_estado = lambda g: json.loads((base / v3.ARQUIVO[g]).read_text(encoding="utf-8"))["itens"]
    a, b = carregar_estado("A"), carregar_estado("B")
    relatorio = {f["id"]: f for f in json.loads(Path(args.relatorio).read_text(encoding="utf-8"))["findings"]}
    ids = json.loads(Path(args.ids).read_text(encoding="utf-8"))["ids"]
    for i in ids:
        f = relatorio[i]
        linha = f"§{f['paragraph']} «{f['text'][f['start']:f['end']][:30]}» {f['category'][:22]}"
        ra, rb = a.get(i, {}), b.get(i, {})
        print(f"{linha:<70} A={ra.get('estado', '-'):<24} B={rb.get('estado', '-'):<24}"
              f"{' ≠' if ra.get('estado') != rb.get('estado') else ''}"
              f"{' (ctx alterou)' if rb.get('contexto_alterou_conclusao') else ''}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="comando", required=True)
    comuns = argparse.ArgumentParser(add_help=False)
    comuns.add_argument("arquivo", help="Manuscrito atual (DOCX ou Pages)")
    comuns.add_argument("--relatorio", required=True)
    comuns.add_argument("--decisoes", required=True, help="JSON de decisões (use o filtrado de `selecionar`)")
    comuns.add_argument("--config")
    s = sub.add_parser("selecionar")
    s.add_argument("--relatorio", required=True)
    s.add_argument("--decisoes", required=True)
    s.add_argument("--casos", required=True, help="JSON externo: [{paragrafo, trecho, ocorrencia?}]")
    s.add_argument("--complemento", type=int, default=3)
    s.add_argument("--semente", default="v3")
    s.add_argument("--saida", required=True)
    s.set_defaults(fn=selecionar)
    e = sub.add_parser("estimar", parents=[comuns])
    e.add_argument("--grupo", choices=("A", "B", "ambos"), default="ambos")
    e.add_argument("--projeto")
    e.set_defaults(fn=estimar)
    x = sub.add_parser("executar", parents=[comuns])
    x.add_argument("--grupo", choices=v3.GRUPOS, required=True)
    x.add_argument("--projeto", required=True)
    x.add_argument("--teto", type=float, required=True, help="Gasto máximo em US$ deste grupo (sem padrão)")
    x.add_argument("--sha-esperado", help="Prefixo do SHA-256 do manuscrito; aborta se diferente")
    x.set_defaults(fn=executar)
    c = sub.add_parser("comparar")
    c.add_argument("--projeto", required=True)
    c.add_argument("--relatorio", required=True)
    c.add_argument("--ids", required=True)
    c.set_defaults(fn=comparar)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
