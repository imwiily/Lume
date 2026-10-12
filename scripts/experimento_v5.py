"""Experimento V5 do Validador de decisões: o contrato da V4.1 avaliado por GPT-6.1 Sol (API da OpenAI).

Experimental e fora da interface de produção. Nada chama a API sem `executar` e um teto explícito. Os casos
do experimento são dados externos (os mesmos 16 IDs da V3/V4/V4.1): o repositório é público e não guarda
trechos nem nomes de manuscritos reais.

    planejar   o que seria analisado, estimativa por cenário e teto mínimo (sem rede)
    executar   analisa só o que é novo; grava só na pasta do projeto V5; exige --teto e --sha-esperado
    comparar   matriz V3-A × V4 × V4.1 × V5 por dimensão, a partir de arquivos já gravados (só leitura)
    relatorio  resultados V5 já gravados em linguagem clara (fenômeno × problema confirmado, incerteza,
               evidências verificadas); só leitura, sem rede, nenhum registro é alterado
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RAIZ / "fonte"), str(RAIZ / "coerencia")]

from fonte import validador_v5 as v5  # noqa: E402
from fonte.reader import read_manuscript  # noqa: E402
from fonte.settings import load as carregar, validate  # noqa: E402

ESPECIAIS = (26, 227, 353, 470, 594)
ABREV = {"mantida": "MANT", "contestada": "CONT", "apontamento_inadequado": "B-AP", "inconclusiva": "INCO",
         "revisao_recomendada": "REVI", None: "-"}


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
    e = v5.estimar(blocks, findings, decisoes, args.projeto, modelo=args.modelo, esforco=args.esforco,
                   revalidar=args.revalidar or [], config=config, teto=args.teto)
    print(json.dumps({"manuscrito_sha256": sha, "estimativa": e, "diferencas_de_contrato": list(v5.DIFERENCAS_DE_CONTRATO)},
                     ensure_ascii=False, indent=1))


def executar(args):
    blocks, findings, decisoes, config, sha, caminho = _tudo(args)
    if not sha.startswith(args.sha_esperado):
        raise SystemExit(f"Manuscrito {sha[:12]} não é o esperado ({args.sha_esperado}).")
    progresso = lambda etapa, feitos, total: print(
        "V5_PROGRESSO " + json.dumps({"etapa": etapa, "feitos": feitos, "total": total}), flush=True)
    try:
        _, avisos, resumo = v5.avaliar(blocks, findings, decisoes, pasta=args.projeto, teto=args.teto, modelo=args.modelo,
                                       esforco=args.esforco, revalidar=args.revalidar or [], avancar=progresso,
                                       meta={"documento": caminho.name, "sha256_manuscrito": sha}, config=config)
    except v5.ValidacaoEmAndamento as erro:
        raise SystemExit(str(erro))
    for aviso in avisos:
        print(aviso, flush=True)
    print("V5_RESUMO " + json.dumps(resumo, ensure_ascii=False), flush=True)


def _tecnico(r):
    """Problema técnico em qualquer versão: (existe, natureza, certeza, gravidade)."""
    if not r:
        return ("-", "-", "-", "-")
    t = r.get("problema_tecnico")
    if t:
        return (t["existe"], t["natureza"], t["certeza"], t["gravidade"])
    av = r.get("avaliacao") or {}
    return (av.get("procede", "-"), "-", "-", "-")


def _legitimidade(r):
    if not r:
        return "-"
    av = r.get("avaliacao") or {}
    return r.get("razao_literaria") or av.get("legitimidade") or av.get("justificativa_editorial") or "-"


def _adequacao(r):
    if not r:
        return "-"
    return r.get("adequacao_decisao") or {"sim": "adequada", "nao": "inadequada", "incerto": "indeterminada"}.get(
        (r.get("avaliacao") or {}).get("decisao_coerente"), "-")


def comparar(args):
    def carregar_itens(caminho):
        return json.loads(Path(caminho).read_text(encoding="utf-8"))["itens"] if caminho and Path(caminho).exists() else {}
    fontes = {"V3-A": carregar_itens(args.v3_a), "V4": carregar_itens(args.v4), "V4.1": carregar_itens(args.v4_1),
              "V5": carregar_itens(args.v5)}
    relatorio = {f["id"]: f for f in json.loads(Path(args.relatorio).read_text(encoding="utf-8"))["findings"]}
    ids = json.loads(Path(args.ids).read_text(encoding="utf-8"))["ids"]
    print("Dimensões separadas: [problema técnico existe/natureza/certeza/gravidade] [legitimidade] "
          "[decisão humana → adequação] [resultado final]\n")
    for i in ids:
        f = relatorio[i]
        print(f"§{f['paragraph']} «{f['text'][f['start']:f['end']][:30]}» {f['category']} — decisão humana: "
              f"{next((r['decisao'] if 'decisao' in r else r.get('decisao_humana') for r in (d.get(i) for d in fontes.values()) if r), '-')}")
        for nome, d in fontes.items():
            r = d.get(i)
            if r is None:
                print(f"   {nome:<5} (sem resultado)")
                continue
            t = "/".join(x[:6] for x in _tecnico(r))
            print(f"   {nome:<5} técnico[{t}] legitimidade[{_legitimidade(r)[:14]}] adequação[{_adequacao(r)[:13]}] "
                  f"final[{ABREV.get(r.get('estado'), r.get('estado'))}] prioridade[{r.get('prioridade_revisao') or '-'}]")
    print("\n=== Avaliação especial (verificações, não gabarito) ===")
    for i in ids:
        f = relatorio[i]
        if f["paragraph"] not in ESPECIAIS:
            continue
        r41, r5 = fontes["V4.1"].get(i), fontes["V5"].get(i)
        print(f"§{f['paragraph']} «{f['text'][f['start']:f['end']][:30]}»")
        if r5 is None:
            print("   V5 não executado")
            continue
        t = r5.get("problema_tecnico", {})
        print(f"   recebeu antecedentes: {r5.get('antecedentes') or 'nenhum'} | pediu mais contexto: {bool(r5.get('pediu_mais_contexto'))}")
        print(f"   problema técnico: {t.get('existe')}/{t.get('natureza')}/{t.get('certeza')}/{t.get('gravidade')} → "
              f"prioridade {r5.get('prioridade_revisao') or '-'}")
        print(f"   legitimidade: {r5.get('razao_literaria')} | adequação da decisão: {r5.get('adequacao_decisao')} | "
              f"final: {r5.get('estado')} (V4.1: {r41.get('estado') if r41 else '-'})")
        print(f"   evidências ativas: {[(e['sustenta'], e['paragrafo']) for e in r5.get('evidencias_verificadas', []) if e['situacao'] == 'ativa']}"
              f" | descartadas: {[(e['sustenta'], e.get('motivo')) for e in r5.get('evidencias_verificadas', []) if e['situacao'] != 'ativa']}")
        print(f"   explicação: {r5.get('explicacao', '')[:320]}")


def relatorio(args):
    from fonte import apresentacao_validacao as ap
    itens, aviso = v5.ler(args.projeto)
    achados = {f["id"]: f for f in json.loads(Path(args.relatorio).read_text(encoding="utf-8"))["findings"]}
    if aviso:
        print(aviso)
    for ident, r in itens.items():
        if r.get("estado_validacao") != "analisada" or (args.so_inconclusivas and r.get("estado") != "inconclusiva"):
            continue
        f = achados.get(ident)
        print(f"### §{f['paragraph']} — {ident}" if f else f"### {ident}")
        print(ap.markdown(ap.apresentar(r, f)), "\n")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="comando", required=True)
    comuns = argparse.ArgumentParser(add_help=False)
    comuns.add_argument("arquivo")
    comuns.add_argument("--relatorio", required=True)
    comuns.add_argument("--decisoes", required=True)
    comuns.add_argument("--config")
    comuns.add_argument("--projeto", required=True, help="Pasta própria da V5 (nunca a da V4 ou V4.1)")
    comuns.add_argument("--modelo", default=v5.MODELO)
    comuns.add_argument("--esforco", default=v5.ESFORCO, choices=("low", "medium", "high", "xhigh", "max"))
    comuns.add_argument("--revalidar", nargs="*")
    a = sub.add_parser("planejar", parents=[comuns])
    a.add_argument("--teto", type=float)
    a.set_defaults(fn=planejar)
    b = sub.add_parser("executar", parents=[comuns])
    b.add_argument("--teto", type=float, required=True, help="Gasto máximo em US$ (sem padrão)")
    b.add_argument("--sha-esperado", required=True)
    b.set_defaults(fn=executar)
    c = sub.add_parser("comparar")
    c.add_argument("--relatorio", required=True)
    c.add_argument("--ids", required=True)
    for nome in ("v3-a", "v4", "v4-1", "v5"):
        c.add_argument("--" + nome)
    c.set_defaults(fn=comparar)
    d = sub.add_parser("relatorio")
    d.add_argument("--relatorio", required=True)
    d.add_argument("--projeto", required=True)
    d.add_argument("--so-inconclusivas", action="store_true")
    d.set_defaults(fn=relatorio)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
