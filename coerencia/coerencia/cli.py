"""Linha de comando: `analisar` um DOCX ou `avaliar` no conjunto anotado."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import time

from . import __version__
from .analise import Analise, normalizar
from .leitura import cenas, ler_docx, ler_paragrafos, sha256
from .modelo import ErroModelo, criar_modelo

RAIZ = Path(__file__).resolve().parents[1]
REPOSITORIO = RAIZ.parent


def rodar(paragrafos, modelo, pasta, maximo, registrar=print):
    inicio = time.monotonic()
    analise = Analise(paragrafos, cenas(paragrafos, maximo), modelo, pasta, registrar)
    registrar(f"{len(analise.cenas)} cenas, {len(paragrafos)} parágrafos. Lendo cena por cena…")
    analise.extrair()
    registrar(f"{len(analise.memoria)} fatos na memória ({len(analise.descartes)} descartados por trecho inexistente).")
    contradicoes = analise.julgar()
    return contradicoes, round(time.monotonic() - inicio, 1), analise


def mostrar(contradicoes):
    if not contradicoes:
        print("\nNenhuma contradição apontada.")
        return
    print(f"\n{len(contradicoes)} possíveis contradições:")
    for n, c in enumerate(contradicoes, 1):
        print(f"\n{n}. §{c['a']['paragrafo']} “{c['a']['trecho']}”  ×  §{c['b']['paragrafo']} “{c['b']['trecho']}”"
              f"  [confiança {c['confianca']}]\n   {c['explicacao']}")


def mostrar_pendencias(projeto, todas=False):
    itens = [p for p in projeto.pendencias if todas or p["status"] == "aberta"]
    if not itens:
        print("\nNenhuma pendência aberta.")
        return
    print(f"\n{len(itens)} pendência(s){'' if todas else ' abertas'}:")
    for p in itens:
        situacao = "" if p["status"] == "aberta" else f" [{p['status']}]"
        print(f"\n{p['id']}{situacao} · confiança {p['confianca']}\n"
              f"   {p['a']['titulo']}: “{p['a']['trecho']}”\n   {p['b']['titulo']}: “{p['b']['trecho']}”\n   {p['explicacao']}")


def mostrar_capitulos(projeto):
    caps = sorted(projeto.estado["capitulos"].values(), key=lambda c: c["ordem"])
    print(f"\n{'Capítulo':40} {'Situação':16} {'Última leitura':20} Tokens")
    for c in caps:
        print(f"{c['titulo'][:40]:40} {c.get('situacao', '?'):16} {c['lido_em']:20} {c.get('tokens', 0)}")


def analisar_projeto(args, caminho, antes):
    from .projeto import Projeto
    projeto = Projeto(args.projeto.expanduser().resolve())
    documento = projeto.estado.get("documento")
    if documento and documento != caminho.name and not args.reler:
        print(f"Aviso: o projeto foi criado com “{documento}”; comparando com “{caminho.name}”.")
    modelo = criar_modelo(args.modelo, args.pensar, args.contexto, args.esforco, args.modelo_juiz, args.teto)
    modelo.verificar()
    print(f"Coerencia {__version__} · projeto {projeto.pasta} · modelo {args.modelo}")
    inicio = time.monotonic()
    paragrafos = ler_docx(caminho)
    rodada = projeto.atualizar(caminho.name, paragrafos, modelo, args.cena, reler=args.reler)
    if sha256(caminho) != antes:
        raise SystemExit("O manuscrito mudou durante a análise. Rode novamente sobre a versão atual.")
    mostrar_capitulos(projeto)
    mostrar_pendencias(projeto)
    print(f"\nRodada: {rodada['enviados']}/{rodada['capitulos']} capítulos enviados · "
          f"{rodada['tokens_gastos']} tokens gastos (US$ {rodada['custo_usd']:.4f}) · ~{rodada['tokens_poupados_estimados']} poupados · "
          f"{time.monotonic() - inicio:.0f} s · manuscrito preservado.")
    from .projeto import capitulos
    from .relatorio import de_projeto
    relatorio = projeto.pasta / "relatorio.html"
    relatorio.write_text(de_projeto(projeto, capitulos(paragrafos), args.projeto), encoding="utf-8")
    print("Relatório: " + str(relatorio))
    print("Marque cada pendência com: coerencia decidir <ID> corrigida|intencional --projeto " + str(args.projeto))


def analisar(args):
    caminho = args.arquivo.expanduser().resolve()
    if not caminho.is_file():
        raise SystemExit("Arquivo não encontrado: " + str(caminho))
    antes = sha256(caminho)
    if args.projeto:
        return analisar_projeto(args, caminho, antes)
    pasta = (args.saida or REPOSITORIO / "build" / "coerencia" / f"{caminho.stem}-{datetime.now():%Y%m%d-%H%M%S}").expanduser().resolve()
    registro = pasta / "execucao.json"
    if registro.exists() and json.loads(registro.read_text())["sha256"] != antes:
        raise SystemExit("A pasta de saída pertence a outra versão do manuscrito. Escolha outra pasta.")
    modelo = criar_modelo(args.modelo, args.pensar, args.contexto, args.esforco, args.modelo_juiz, args.teto)
    modelo.verificar()
    paragrafos = ler_docx(caminho)
    print(f"Coerencia {__version__} · modelo {args.modelo}{' com raciocínio' if args.pensar else ''} · saída {pasta}")
    contradicoes, segundos, analise = rodar(paragrafos, modelo, pasta, args.cena)
    if sha256(caminho) != antes:
        raise SystemExit("O manuscrito mudou durante a análise. Rode novamente sobre a versão atual.")
    registro.write_text(json.dumps({"versao": __version__, "documento": caminho.name, "sha256": antes,
                                    "modelo": args.modelo, "pensar": args.pensar, "segundos": segundos,
                                    "cenas": len(analise.cenas), "fatos": len(analise.memoria),
                                    "chamadas": modelo.chamadas}, ensure_ascii=False, indent=2), encoding="utf-8")
    mostrar(contradicoes)
    custo = sum(c.get("custo_usd", 0) for c in modelo.chamadas)
    print(f"\nTempo: {segundos:.0f} s · {len(modelo.chamadas)} chamadas ao modelo · US$ {custo:.4f} · manuscrito preservado.")
    from .relatorio import avulso
    (pasta / "relatorio.html").write_text(avulso(caminho.name, args.modelo, contradicoes, paragrafos, custo), encoding="utf-8")
    print("Relatório: " + str(pasta / "relatorio.html"))
    print("Memória e julgamentos em " + str(pasta))


def casa(deteccao, gabarito):
    """A detecção, ou algum alerta agrupado com ela, corresponde ao gabarito?"""
    return any(_casa(d, gabarito) for d in [deteccao, *deteccao.get("relacionadas", [])])


def _casa(deteccao, gabarito):
    pa, pb = deteccao["a"]["paragrafo"], deteccao["b"]["paragrafo"]
    if gabarito["p"] not in (pa, pb):
        return False
    if gabarito["contra"] in (pa, pb) and gabarito["contra"] != gabarito["p"]:
        return True
    trechos = [normalizar(deteccao[k]["trecho"]) for k in ("a", "b") if deteccao[k]["paragrafo"] == gabarito["p"]]
    alvo = normalizar(gabarito["trecho"])
    return any(alvo in t or t in alvo for t in trechos)


def carregar_caso(caso, cache):
    """Parágrafos de um caso: DOCX, ou texto de um corpus JSON (lista de objetos
    com `id`/`paragrafos`, como no FONTE, ou dicionário nome → parágrafos)."""
    if "docx" in caso:
        return ler_docx(REPOSITORIO / caso["docx"])
    arquivo = REPOSITORIO / caso["corpus"]
    if arquivo not in cache:
        textos = json.loads(arquivo.read_text(encoding="utf-8"))["textos"]
        cache[arquivo] = textos if isinstance(textos, dict) else {t["id"]: t["paragrafos"] for t in textos}
    return ler_paragrafos(cache[arquivo][caso["texto"]])


def avaliar(args):
    casos = json.loads((RAIZ / "avaliacao" / "casos.json").read_text(encoding="utf-8"))
    modelo = criar_modelo(args.modelo, args.pensar, args.contexto, args.esforco, args.modelo_juiz, args.teto)
    modelo.verificar()
    pasta = (args.saida or REPOSITORIO / "build" / "coerencia" / f"avaliacao-{args.modelo.replace(':', '_')}-{datetime.now():%Y%m%d-%H%M%S}").resolve()
    pasta.mkdir(parents=True, exist_ok=True)
    corpus = {}
    total = {"esperadas": 0, "encontradas": 0, "alarmes_falsos": 0, "segundos": 0.0}
    linhas = []
    for caso in casos["casos"]:
        if args.caso and caso["id"] not in args.caso:
            continue
        paragrafos = carregar_caso(caso, corpus)
        print(f"\n== {caso['id']}")
        contradicoes, segundos, _ = rodar(paragrafos, modelo, pasta / caso["id"], args.cena)
        usados, acertos = set(), []
        for gabarito in caso["contradicoes"]:
            indice = next((i for i, d in enumerate(contradicoes) if i not in usados and casa(d, gabarito)), None)
            if indice is not None:
                usados.add(indice)
            acertos.append(indice is not None)
        falsos = [d for i, d in enumerate(contradicoes)
                  if i not in usados and not any(casa(d, g) for g in caso["contradicoes"])]
        total["esperadas"] += len(acertos); total["encontradas"] += sum(acertos)
        total["alarmes_falsos"] += len(falsos); total["segundos"] += segundos
        linhas.append({"caso": caso["id"], "encontradas": sum(acertos), "esperadas": len(acertos),
                       "alarmes_falsos": [{"a": f["a"], "b": f["b"], "explicacao": f["explicacao"]} for f in falsos],
                       "perdidas": [g for g, ok in zip(caso["contradicoes"], acertos) if not ok], "segundos": segundos})
        print(f"   → {sum(acertos)}/{len(acertos)} contradições, {len(falsos)} alarmes falsos, {segundos:.0f} s")
    total["custo_usd"] = round(sum(c.get("custo_usd", 0) for c in modelo.chamadas), 4)
    resumo = {"modelo": args.modelo, "modelo_juiz": args.modelo_juiz, "pensar": args.pensar, "total": total, "casos": linhas, "chamadas": len(modelo.chamadas)}
    (pasta / "avaliacao.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nTOTAL {args.modelo}{' (raciocínio)' if args.pensar else ''}: {total['encontradas']}/{total['esperadas']} contradições, "
          f"{total['alarmes_falsos']} alarmes falsos, {total['segundos'] / 60:.1f} min, US$ {total['custo_usd']:.4f}")
    print("Detalhes em " + str(pasta / "avaliacao.json"))


def main(argv=None):
    raiz = argparse.ArgumentParser(prog="coerencia", description=__doc__)
    raiz.add_argument("--version", action="version", version=__version__)
    comum = argparse.ArgumentParser(add_help=False)
    comum.add_argument("--modelo", default="claude-sonnet-5-5",
                       help="claude-sonnet-5-5 (padrão), claude-opus-5-5, claude-haiku-4-5 ou um modelo do Ollama local")
    comum.add_argument("--esforco", default="medium", choices=["low", "medium", "high", "xhigh", "max"],
                       help="Profundidade de raciocínio do Claude (Opus/Sonnet 5.5)")
    comum.add_argument("--pensar", action="store_true", help="Ollama: ativa o modo de raciocínio (mais lento)")
    comum.add_argument("--modelo-juiz", help="Modelo só para os julgamentos (ex.: leitura com Sonnet, juiz com Opus)")
    comum.add_argument("--teto", type=float, help="Gasto máximo em US$ nesta execução; para antes de ultrapassar")
    comum.add_argument("--cena", type=int, default=3500, help="Tamanho máximo de uma cena, em caracteres")
    comum.add_argument("--contexto", type=int, default=16384, help="Janela de contexto pedida ao modelo")
    comum.add_argument("--saida", type=Path, help="Pasta de trabalho (reaproveitada para retomar)")
    comandos = raiz.add_subparsers(dest="comando", required=True)
    a = comandos.add_parser("analisar", parents=[comum], help="Apontar contradições num DOCX")
    a.add_argument("arquivo", type=Path)
    a.add_argument("--projeto", type=Path, help="Pasta de projeto: só capítulos alterados vão ao modelo")
    a.add_argument("--reler", action="store_true", help="Com --projeto: reenviar todos os capítulos")
    v = comandos.add_parser("avaliar", parents=[comum], help="Medir no conjunto anotado (avaliacao/casos.json)")
    v.add_argument("--caso", action="append", help="Rodar só este caso (pode repetir)")
    s = comandos.add_parser("status", help="Capítulos, pendências e economia de um projeto")
    s.add_argument("--projeto", type=Path, required=True)
    s.add_argument("--todas", action="store_true", help="Incluir pendências já decididas")
    d = comandos.add_parser("decidir", help="Marcar uma pendência")
    d.add_argument("id")
    d.add_argument("situacao", choices=["corrigida", "intencional", "aberta"])
    d.add_argument("--projeto", type=Path, required=True)
    args = raiz.parse_args(argv)
    try:
        if args.comando == "analisar":
            analisar(args)
        elif args.comando == "avaliar":
            avaliar(args)
        else:
            from .projeto import Projeto
            pasta = args.projeto.expanduser().resolve()
            if not (pasta / "projeto.json").exists():
                raise SystemExit("Projeto não encontrado: " + str(pasta))
            projeto = Projeto(pasta)
            if args.comando == "decidir":
                pendencia = projeto.decidir(args.id, args.situacao)
                print(f"{pendencia['id']} marcada como {pendencia['status']}.")
            else:
                mostrar_capitulos(projeto)
                mostrar_pendencias(projeto, args.todas)
                gastos = sum(r["tokens_gastos"] for r in projeto.rodadas)
                poupados = sum(r["tokens_poupados_estimados"] for r in projeto.rodadas)
                custo = sum(r.get("custo_usd", 0) for r in projeto.rodadas)
                print(f"\n{len(projeto.rodadas)} rodadas · {gastos} tokens gastos (US$ {custo:.4f}) · ~{poupados} poupados.")
    except (ErroModelo, ValueError) as erro:
        print("Erro: " + str(erro), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nInterrompido. A memória das cenas concluídas foi mantida na pasta de saída.", file=sys.stderr)
        return 130
    return 0
