"""Experimento V5.1 do Validador de decisões: consistência contextual (somente leitura local).

Experimental e fora da interface de produção. Só o modo `executar` chama a API, com autorização explícita e no máximo uma requisição. Os casos são dados externos; o repositório é público e a
saída traz posições (§parágrafo:início) e contagens, nunca trechos de manuscrito.

    planejar      estimativa por componente e teto mínimo (sem rede, sem estado)
    agrupamento   composição dos pedidos da V5 (v4.lotes) × V5.1, parágrafos divididos e custos estimados
    executar      UMA requisição real (GPT-6.1 Sol) para os `--apenas` ids; sem repetição, sem segunda rodada;
                  recusa enviar se o pior caso exceder o teto; exige --teto e --sha-esperado
    simular-v5    camada local de consistência aplicada, em memória, a resultados V5 já gravados; nada é
                  reescrito e os resultados V5 não viram resultados V5.1
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RAIZ / "fonte"), str(RAIZ / "coerencia")]

from fonte import validador_v5 as v5  # noqa: E402
from fonte import validador_v5_1 as v51  # noqa: E402
from fonte.reader import read_manuscript  # noqa: E402
from fonte.settings import load as carregar, validate  # noqa: E402


def _tudo(args):
    relatorio = json.loads(Path(args.relatorio).read_text(encoding="utf-8"))
    decisoes = json.loads(Path(args.decisoes).read_text(encoding="utf-8"))
    config = carregar(Path(args.config)) if getattr(args, "config", None) else validate({})
    caminho = Path(args.arquivo).expanduser().resolve()
    blocks, _ = read_manuscript(caminho, config)
    return blocks, relatorio["findings"], decisoes.get("decisions", decisoes), config, \
        hashlib.sha256(caminho.read_bytes()).hexdigest()


def planejar(args):
    blocks, findings, decisoes, config, sha = _tudo(args)
    e = v51.estimar(blocks, findings, decisoes, None, modelo=args.modelo, esforco=args.esforco, config=config,
                    teto=args.teto)
    print(json.dumps({"manuscrito_sha256": sha, "estimativa": e}, ensure_ascii=False, indent=1))


def agrupamento(args):
    blocks, findings, decisoes, config, sha = _tudo(args)
    c = v51.comparar_com_v5(blocks, findings, decisoes, modelo=args.modelo)
    print(json.dumps({"manuscrito_sha256": sha, "comparacao": c}, ensure_ascii=False, indent=1))


def executar(args):
    ErroModelo = v5._erros()[0]
    from coerencia.modelo import Orcamento, RespostaCortada

    class UmaChamada(v5.OpenAI):
        TENTATIVAS = 1                                   # nenhuma repetição por 429, 5xx ou timeout
        enviadas = 0

        def json(self, *a, **k):
            if self.enviadas >= 1:
                raise ErroModelo("Uma única requisição foi autorizada.")
            self.enviadas += 1
            try:
                return super().json(*a, **k)
            except RespostaCortada:                      # truncamento: não divide nem repete
                return {"avaliacoes": []}

    blocks, findings, decisoes, config, sha = _tudo(args)
    if not sha.startswith(args.sha_esperado):
        raise SystemExit(f"Manuscrito {sha[:12]} não é o esperado ({args.sha_esperado}).")
    ids = set(args.apenas)
    p = v51.planejar(blocks, findings, decisoes, args.projeto, modelo=args.modelo, esforco=args.esforco, config=config)
    alvo = [i for i in p["a_analisar"] if i["id"] in ids]
    if {i["id"] for i in alvo} != ids:
        raise SystemExit("Algum id não é elegível ou já tem resultado válido neste projeto.")
    lotes, divisoes = v51.agrupar(alvo, blocks, p["arestas"])
    texto, _ = v51.pedido(lotes[0], blocks, {i["id"]: i["antecedentes"] for i in lotes[0] if i.get("antecedentes")})
    cliente = UmaChamada(args.modelo, args.esforco, orcamento=Orcamento(args.teto))
    pior = cliente.custo_maximo(v51.SISTEMA, texto, v51.ESQUEMA, v5.limite_de_saida(len(lotes[0])))
    print(json.dumps({"verificacao_local": {
        "pedidos": len(lotes), "itens": [len(l) for l in lotes], "divisoes": divisoes, "caracteres_do_pedido": len(texto),
        "relacionados_por_item": {i["id"]: [(r["id"], r["tipo"]) for r in i["relacionados"]] for i in lotes[0]},
        "pior_caso_usd": round(pior, 4), "teto_usd": args.teto, "modelo": args.modelo, "esforco": args.esforco}},
        ensure_ascii=False), flush=True)
    if len(lotes) != 1 or divisoes or pior > args.teto:
        raise SystemExit("Pedido não cabe em uma única requisição dentro do teto: nada foi enviado.")
    registros, avisos, resumo = v51.avaliar(blocks, findings, decisoes, pasta=args.projeto, teto=args.teto,
                                            modelo=args.modelo, esforco=args.esforco, cliente=cliente,
                                            rodada_extra=False, apenas=ids, config=config,
                                            meta={"documento": Path(args.arquivo).name, "sha256_manuscrito": sha})
    for aviso in avisos:
        print(aviso, flush=True)
    print("V5_1_RESUMO " + json.dumps(resumo, ensure_ascii=False))


def simular_v5(args):
    blocks, findings, decisoes, config, sha = _tudo(args)
    guardados, aviso = v5.ler(args.projeto_v5)
    avaliar, _, _ = v51.preparar(blocks, findings, decisoes, None, args.modelo)
    arestas = v51.relacoes_contextuais(avaliar)
    virtuais = {}
    for i in avaliar:
        r = guardados.get(i["id"])
        if r and r.get("estado_validacao") == "analisada":
            virtuais[i["id"]] = {**r, "chave_conteudo": i["chave_conteudo"], "chave_configuracao": i["chave_configuracao"],
                                 "relacoes": []}                    # a V5 não declarava relações
    rel = v51.consistencia(avaliar, virtuais, arestas)
    nome = lambda ident: next(f"§{i['_bloco'].number}:{i['start']}" for i in avaliar if i["id"] == ident)
    pares = [{"a": nome(p["a"]), "b": nome(p["b"]), "relacao": p["relacao"], "estado": p["estado"],
              "grau": p.get("grau"), "atencao": p["atencao"]} for p in rel["pares"]
             if p["a"] in virtuais or p["b"] in virtuais]
    print(json.dumps({"manuscrito_sha256": sha, "aviso": aviso, "resultados_v5_lidos": len(virtuais),
                      "simulacao": "em memória; nenhum arquivo foi gravado", "resumo": rel["resumo"],
                      "pares": pares}, ensure_ascii=False, indent=1))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for nome, fn in (("planejar", planejar), ("agrupamento", agrupamento), ("executar", executar),
                     ("simular-v5", simular_v5)):
        s = sub.add_parser(nome)
        s.add_argument("arquivo")
        s.add_argument("--relatorio", required=True)
        s.add_argument("--decisoes", required=True)
        s.add_argument("--config")
        s.add_argument("--modelo", default=v51.MODELO)
        s.add_argument("--esforco", default=v51.ESFORCO)
        s.add_argument("--teto", type=float)
        if nome == "executar":
            s.add_argument("--projeto", required=True)
            s.add_argument("--apenas", nargs="+", required=True)
            s.add_argument("--sha-esperado", required=True)
        if nome == "simular-v5":
            s.add_argument("--projeto-v5", required=True)
        s.set_defaults(fn=fn)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
