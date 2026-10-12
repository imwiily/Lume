"""Validador V5.1 (experimental): relações contextuais, agrupamento seguro, declarações verificáveis e camada local de
consistência. Cliente e transporte simulados; nenhum teste usa a rede e todo texto é sintético."""
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from fonte import validador_v4 as v4
from fonte import validador_v4_1 as v41
from fonte import validador_v5 as v5
from fonte import validador_v5_1 as v51
from fonte.reader import Block
import test_validador_v4_1 as T
import test_validador_v5 as T5

PARAGRAFO_20 = ("A gravura retrata uma ponte. Alguns viajantes cruzavam o vale com mulas. "
                "Ao fundo, o guia segura um bastão que parece de bronze, e o curioso era que ele brilha. "
                "Ele era coberto de inscrições. A gravura é velha, mas foi o que a equipe achou. "
                "O cartógrafo ainda está na mesa.")
PARAGRAFO_19 = "A equipe abriu o baú; um dos itens prendeu o olhar de todos: era uma chave."


def livro(extra=None):
    textos = {n: f"Parágrafo neutro número {n}, sobre o mar e o porto." for n in range(2, 80)}
    textos.update({18: T.ALVO, 19: PARAGRAFO_19, 20: PARAGRAFO_20,
                   30: "Então, antes que tocasse o sino, o vigia parou.",
                   50: "Porém, antes que clareasse o dia, a luz apagou.",
                   60: "Ela pediu que ele chegasse cedo ao porto."})
    textos.update(extra or {})
    return [Block(1, "Capítulo 1", "Capítulo 1", heading=True)] + [Block(n, t, "Capítulo 1") for n, t in sorted(textos.items())]


def cenario(b=None, com_construcao=True):
    b = b or livro()
    a = {"estava": T.alerta(b, 18, "estava", "Concordância verbal"),
         "prendeu": T.alerta(b, 19, "prendeu", "Tempo verbal"), "era19": T.alerta(b, 19, "era", "Tempo verbal"),
         "cruzavam": T.alerta(b, 20, "cruzavam", "Tempo verbal"), "era1": T.alerta(b, 20, "era", "Tempo verbal", nth=0),
         "era2": T.alerta(b, 20, "era", "Tempo verbal", nth=1), "foi": T.alerta(b, 20, "foi", "Tempo verbal")}
    if com_construcao:
        a["c30"] = T.alerta(b, 30, "tocasse", "Correlação de tempos")
        a["c50"] = T.alerta(b, 50, "clareasse", "Correlação de tempos")
        a["c60"] = T.alerta(b, 60, "chegasse", "Correlação de tempos")
    f = list(a.values())
    return b, f, {x["id"]: "Estilo do autor" for x in f}, a


RELACIONADOS = re.compile(r"\[RELACOES ITEM (\w+)\]\n((?:- com=\w+.*\n?)+)")


def relacionados_do(usuario):
    return {i: re.findall(r"com=(\w+)", bloco) for i, bloco in RELACIONADOS.findall(usuario)}


class Cliente:
    """Cliente simulado com a interface do OpenAI da V5: `json`, `chamadas`, `modelo`."""
    modelo = v5.MODELO

    def __init__(self, mapa=None, relacoes=None, custo=0.01):
        self.mapa, self.relacoes, self.custo = mapa or {}, relacoes or {}, custo
        self.pedidos, self.chamadas, self.limites = [], [], []

    def json(self, sistema, usuario, esquema, etapa, max_saida=None):
        self.pedidos.append(usuario)
        self.limites.append(max_saida)
        rel = relacionados_do(usuario)
        itens = []
        for i in T.ids_do(usuario):
            e = T.base(i, usuario, **self.mapa.get(i, {}))
            e["relacoes"] = self.relacoes.get(i, [{"com": c, "tipo": "independente", "propriedade": "", "motivo": "",
                                                    "trecho": ""} for c in rel.get(i, [])])
            itens.append(e)
        self.chamadas.append({"etapa": etapa, "custo_usd": self.custo, "tokens_entrada": 1000, "tokens_cache": 100,
                              "tokens_saida": 200, "modelo_usado": self.modelo, "pedido": f"req_{len(self.chamadas)}",
                              "segundos": 1.0})
        return {"avaliacoes": itens}


def rodar(b, f, dec, pasta, cliente=None, teto=5.0, **kw):
    c = cliente or Cliente()
    r = v51.avaliar(b, f, dec, pasta=pasta, teto=teto, cliente=c, **kw)
    return (*r, c)


INTERPRETATIVO = {"existe": "sim", "natureza": "interpretativo", "certeza": "discutivel", "gravidade": "baixa",
                  "razao_literaria": "nao_identificada", "explicacao": "Oscilação de tempo discutível.",
                  "evidencia": "Ela era coberta"}


def item_de(avaliar, f):
    return next(i for i in avaliar if i["id"] == f["id"])


def registro(item, existe="sim", estado="mantida", relacoes=(), natureza="interpretativo", certeza="discutivel"):
    return {"id": item["id"], "estado": estado, "estado_validacao": "analisada", "decisao_humana": item["decisao"],
            "chave_conteudo": item["chave_conteudo"], "chave_configuracao": item["chave_configuracao"],
            "problema_tecnico": {"existe": existe, "natureza": natureza, "certeza": certeza, "gravidade": "baixa"},
            "relacoes": list(relacoes)}


def declaracao(com, tipo, propriedade="", motivo="", trecho="", autentico=None):
    problemas = []
    if tipo in v51.EXIGEM_MOTIVO and not motivo:
        problemas.append("motivo_ausente")
    if tipo in v51.EXIGEM_PROPRIEDADE and not propriedade:
        problemas.append("propriedade_ausente")
    return {"com": com, "tipo": tipo, "propriedade": propriedade, "motivo": motivo, "trecho": trecho,
            "trecho_autentico": autentico, "completa": not problemas, "problemas": problemas}


class RelacoesContextuaisTests(unittest.TestCase):
    def setUp(self):
        self.b, self.f, self.dec, self.a = cenario()
        self.avaliar = v51.preparar(self.b, self.f, self.dec)[0]
        self.arestas = v51.relacoes_contextuais(self.avaliar)

    def tipo(self, x, y):
        ids = {self.a[x]["id"], self.a[y]["id"]}
        return next((e["tipo"] for e in self.arestas if {e["a"], e["b"]} == ids), None)

    def test_same_sentence_same_paragraph_and_construction_are_distinguished(self):
        self.assertEqual(self.tipo("prendeu", "era19"), "mesma_frase")            # dois-pontos não encerram a frase
        self.assertEqual(self.tipo("cruzavam", "era1"), "mesmo_paragrafo")
        self.assertEqual(self.tipo("era1", "era2"), "mesmo_paragrafo")
        self.assertEqual(self.tipo("era2", "foi"), "mesmo_paragrafo")
        self.assertEqual(self.tipo("c30", "c50"), "mesma_construcao")
        self.assertTrue(next(e for e in self.arestas if e["tipo"] == "mesma_construcao")["heuristica"])

    def test_pronoun_context_and_other_paragraphs_are_not_related(self):
        self.assertIsNone(self.tipo("c60", "c30"))           # "que ele chegasse": gatilho é pronome, não construção
        self.assertIsNone(self.tipo("estava", "prendeu"))     # vizinhança de parágrafo não é relação
        self.assertIsNone(self.tipo("cruzavam", "c30"))

    def test_relations_are_proximity_not_dependency(self):
        for e in self.arestas:
            self.assertIn(e["tipo"], v51.TIPOS_CONTEXTUAIS)
            self.assertNotIn(e["tipo"], v51.TIPOS_DECLARADOS)

    def test_cross_paragraph_construction_stays_out_of_the_prompt_and_the_key(self):
        c30 = item_de(self.avaliar, self.a["c30"])
        self.assertEqual(c30["relacionados"], [])
        self.assertEqual(c30["chave_relacoes"], v51._chave_relacoes([]))

    def test_related_are_nearest_first_and_capped_with_omission_counted(self):
        texto = " ".join(f"Ele chegou{k} ali." for k in range(11))
        b = livro({22: texto})
        f = [T.alerta(b, 22, f"chegou{k}", "Tempo verbal") for k in range(11)]
        avaliar = v51.preparar(b, f, {x["id"]: "Estilo do autor" for x in f})[0]
        primeiro = min(avaliar, key=lambda i: i["start"])
        self.assertEqual(len(primeiro["relacionados"]), v51.RELACIONADOS_MAX)
        self.assertEqual(primeiro["relacionados_omitidos"], 10 - v51.RELACIONADOS_MAX)
        distancias = [r["inicio"] for r in primeiro["relacionados"]]
        self.assertEqual(distancias, sorted(distancias))


class AgrupamentoTests(unittest.TestCase):
    def test_paragraph_with_several_alerts_is_grouped_where_v5_would_split_it(self):
        b, f, dec, a = cenario(com_construcao=False)
        avaliar = v51.preparar(b, f, dec)[0]
        ids20 = {a[k]["id"] for k in ("cruzavam", "era1", "era2", "foi")}
        pedidos_v5 = v4.lotes(avaliar, b)
        self.assertGreater(len({k for k, l in enumerate(pedidos_v5) for i in l if i["id"] in ids20}), 1)
        lotes, divisoes = v51.agrupar(avaliar, b, v51.relacoes_contextuais(avaliar))
        self.assertEqual(len({k for k, l in enumerate(lotes) for i in l if i["id"] in ids20}), 1)
        self.assertEqual(divisoes, [])
        self.assertEqual(sorted(i["id"] for l in lotes for i in l), sorted(i["id"] for i in avaliar))

    def test_grouping_does_not_presume_equal_results(self):
        b, f, dec, a = cenario(com_construcao=False)
        mapa = {a["cruzavam"]["id"]: {"existe": "nao"}, a["era1"]["id"]: {"existe": "incerto"},
                a["era2"]["id"]: dict(INTERPRETATIVO)}
        with TemporaryDirectory() as pasta:
            r, _, resumo, c = rodar(b, f, dec, pasta, Cliente(mapa))
        estados = {k: r[a[k]["id"]]["estado"] for k in ("cruzavam", "era1", "era2")}
        self.assertEqual(estados, {"cruzavam": "mantida", "era1": "inconclusiva", "era2": "revisao_recomendada"})
        self.assertEqual([x for x in c.pedidos if "[ITEM " + a["cruzavam"]["id"] in x and "[ITEM " + a["era1"]["id"] in x]
                         != [], True)                                 # os quatro do parágrafo viajam juntos

    def test_prompt_lists_related_positions_but_never_decisions_verdicts_or_hypotheses(self):
        b, f, dec, a = cenario(com_construcao=False)
        dec[a["era1"]["id"]] = "Falso positivo"
        dec[a["era2"]["id"]] = "Intencional"
        for x in f:
            x["reason"] = f"Hipótese especial {x['id']}"
        avaliar = v51.preparar(b, f, dec)[0]
        lote = [i for i in avaliar if i["_bloco"].number == 20]
        texto, autorizado = v51.pedido(lote, b)
        bloco = texto[texto.index("Apontamentos relacionados"):]
        self.assertIn(f"com={a['era1']['id']}", bloco)
        self.assertRegex(bloco, r"posições \d+–\d+, ocorrência 1 de 2, mesmo parágrafo")
        for proibido in ("Falso positivo", "Intencional", "Estilo do autor", "Hipótese especial", "mantida",
                         "inconclusiva", "contestada"):
            self.assertNotIn(proibido, bloco)
        self.assertEqual({n for n, _, _ in autorizado[lote[0]["id"]]} - {*range(17, 24)}, set())  # só a janela do item

    def test_large_group_is_split_documented_and_keeps_references(self):
        texto = " ".join(f"Ele chegou{k} ali." for k in range(8))
        b = livro({22: texto})
        f = [T.alerta(b, 22, f"chegou{k}", "Tempo verbal") for k in range(8)]
        dec = {x["id"]: "Estilo do autor" for x in f}
        avaliar = v51.preparar(b, f, dec)[0]
        lotes, divisoes = v51.agrupar(avaliar, b, v51.relacoes_contextuais(avaliar))
        self.assertTrue(all(len(l) <= v51.LOTE_MAX_ITENS for l in lotes))
        self.assertEqual(len(divisoes), 1)
        self.assertEqual((divisoes[0]["motivo"], divisoes[0]["referencias_preservadas"]), ("excede_itens", True))
        self.assertEqual(sorted(i for p in divisoes[0]["partes"] for i in p), sorted(i["id"] for i in avaliar))
        self.assertGreater(len(lotes), 1)
        for i in avaliar:                                      # cada item continua listando os outros 7
            self.assertEqual(len(i["relacionados"]), 7)
        com_extras = [v51.pedido(l, b)[0] for l in lotes]
        for t in com_extras:
            self.assertEqual(len(re.findall(r"\[RELACOES ITEM", t)), t.count("[ITEM "))

    def test_context_limit_also_splits(self):
        b, f, dec, a = cenario(com_construcao=False)
        avaliar = [i for i in v51.preparar(b, f, dec)[0] if i["_bloco"].number == 20]
        lotes, divisoes = v51.agrupar(avaliar, b, v51.relacoes_contextuais(avaliar), maximo_caracteres=100)
        self.assertEqual([d["motivo"] for d in divisoes], ["excede_contexto"])
        self.assertEqual(sum(len(l) for l in lotes), 4)

    def test_chapter_change_never_shares_a_request(self):
        b = livro()
        b = [Block(x.number, x.text, "Capítulo 2") if x.number >= 55 else x for x in b]
        f = [T.alerta(b, 50, "clareasse", "Tempo verbal"), T.alerta(b, 60, "chegasse", "Tempo verbal")]
        avaliar = v51.preparar(b, f, {x["id"]: "Estilo do autor" for x in f})[0]
        lotes, _ = v51.agrupar(avaliar, b, v51.relacoes_contextuais(avaliar))
        self.assertEqual(len(lotes), 2)
        for l in lotes:
            self.assertEqual(len({i["_bloco"].chapter for i in l}), 1)

    def test_construction_partners_are_adjacent_when_they_fit(self):
        b, f, dec, a = cenario()
        avaliar = v51.preparar(b, f, dec)[0]
        lotes, _ = v51.agrupar(avaliar, b, v51.relacoes_contextuais(avaliar))
        onde = {i["id"]: k for k, l in enumerate(lotes) for i in l}
        self.assertEqual(onde[a["c30"]["id"]], onde[a["c50"]["id"]])


class BudgetTests(unittest.TestCase):
    def pedidos_ok(self, mapa=None):
        return lambda corpo: T5.resposta({"avaliacoes": [
            {**T.base(i, corpo["input"], **(mapa or {}).get(i, {})), "relacoes": []} for i in T.ids_do(corpo["input"])]})

    def test_group_is_divided_by_budget_never_stretched(self):
        b, f, dec, a = cenario(com_construcao=False)
        so20 = [x for x in f if x["paragraph"] == 20] if "paragraph" in f[0] else [a[k] for k in ("cruzavam", "era1", "era2", "foi")]
        dec20 = {x["id"]: "Estilo do autor" for x in so20}
        avaliar = v51.preparar(b, so20, dec20)[0]
        cli = v5.OpenAI(v5.MODELO, v5.ESFORCO, orcamento=None, transporte=T5.Transporte())
        p2 = cli.custo_maximo(v51.SISTEMA, v51.pedido(avaliar[:2], b)[0], v51.ESQUEMA, v5.limite_de_saida(2))
        p4 = cli.custo_maximo(v51.SISTEMA, v51.pedido(avaliar, b)[0], v51.ESQUEMA, v5.limite_de_saida(4))
        teto = p2 * 1.25
        self.assertGreater(p4, teto)
        t = T5.Transporte(fn=self.pedidos_ok())
        with TemporaryDirectory() as pasta:
            r, _, resumo, = v51.avaliar(b, so20, dec20, pasta=pasta, teto=teto, transporte=t)
        posts = [c for c in t.chamadas if c[0] == "POST"]
        self.assertEqual(resumo["analisadas_agora"], 4)
        self.assertTrue(all(len(T.ids_do(c[2]["input"])) <= 2 for c in posts))
        self.assertIn("orcamento", {d["motivo"] for d in resumo["divisoes"]})
        self.assertLessEqual(resumo["custo_usd"], teto)

    def test_single_item_above_the_ceiling_is_not_sent_and_stays_resumable(self):
        b, f, dec, a = cenario(com_construcao=False)
        t = T5.Transporte(fn=self.pedidos_ok())
        with TemporaryDirectory() as pasta:
            r, avisos, resumo = v51.avaliar(b, f, dec, pasta=pasta, teto=0.01, transporte=t)
            estado = json.loads((Path(pasta) / v51.ARQUIVO).read_text(encoding="utf-8"))
        self.assertEqual([c for c in t.chamadas if c[0] == "POST"], [])
        self.assertTrue(resumo["interrompida"] and resumo["sem_resposta"] == len(f))
        self.assertFalse(any(x.get("estado_validacao") == "em_processamento" for x in estado["itens"].values()))

    def test_truncated_group_is_split_and_documented(self):
        from coerencia.modelo import TetoAtingido  # noqa: F401
        b, f, dec, a = cenario(com_construcao=False)

        def fn(corpo):
            if len(T.ids_do(corpo["input"])) > 2:
                return T5.resposta(None, status="incomplete", motivo="max_output_tokens", saida_extra=[])
            return self.pedidos_ok()(corpo)
        t = T5.Transporte(fn=fn)
        with TemporaryDirectory() as pasta:
            _, _, resumo = v51.avaliar(b, f, dec, pasta=pasta, teto=5.0, transporte=t)
        self.assertEqual(resumo["sem_resposta"], 0)
        self.assertIn("resposta_cortada", {d["motivo"] for d in resumo["divisoes"]})


class DeclaracoesTests(unittest.TestCase):
    def rodar_com(self, relacoes):
        b, f, dec, a = cenario(com_construcao=False)
        mapa = {a["era2"]["id"]: dict(INTERPRETATIVO)}
        with TemporaryDirectory() as pasta:
            r, _, resumo, _ = rodar(b, f, dec, pasta, Cliente(mapa, relacoes(a)))
        return r, resumo, a

    def test_references_are_verified_and_bad_ones_do_not_touch_the_verdict(self):
        base, _, a = self.rodar_com(lambda a: {})
        lixo = lambda a: {a["era2"]["id"]: [
            {"com": "inexistente", "tipo": "depende_de", "propriedade": "x", "motivo": "nada disso existe aqui", "trecho": ""},
            {"com": a["era2"]["id"], "tipo": "independente", "propriedade": "", "motivo": "", "trecho": ""},
            {"com": a["era1"]["id"], "tipo": "diferenca", "propriedade": "", "motivo": "curto", "trecho": "frase que não existe"},
            {"com": a["foi"]["id"], "tipo": "independente", "propriedade": "", "motivo": "", "trecho": ""},
            {"com": a["foi"]["id"], "tipo": "depende_de", "propriedade": "", "motivo": "ligação qualquer entre os dois", "trecho": ""}],
            a["cruzavam"]["id"]: "não é lista"}
        r, resumo, a = self.rodar_com(lixo)
        d = resumo["descartes"]
        for k in ("relacao_desconhecida", "relacao_consigo_mesmo", "relacao_trecho_inexistente",
                  "relacao_duplicada_contraditoria", "relacoes_invalidas"):
            self.assertGreaterEqual(d.get(k, 0), 1, k)
        declarada = {x["com"]: x for x in r[a["era2"]["id"]]["relacoes"]}
        self.assertEqual(set(declarada), {a["era1"]["id"]})
        self.assertFalse(declarada[a["era1"]["id"]]["completa"])
        self.assertEqual(declarada[a["era1"]["id"]]["trecho"], "")
        for k in a:
            for campo in ("estado", "prioridade_revisao", "problema_tecnico", "adequacao_decisao", "decisao"):
                self.assertEqual(r[a[k]["id"]][campo], base[a[k]["id"]][campo], (k, campo))

    def test_unprovided_declaration_is_missing_not_error(self):
        r, resumo, a = self.rodar_com(lambda a: {a["era2"]["id"]: []})
        self.assertEqual(len(r[a["era2"]["id"]]["relacoes_nao_declaradas"]), 3)

    def test_difference_explanation_is_formal_not_proof(self):
        completa = declaracao("x", "diferenca", "função da forma no período", "este descreve propriedade isolada")
        sem_prop = declaracao("x", "diferenca", "", "este descreve propriedade isolada do objeto")
        b, f, dec, a = cenario(com_construcao=False)
        avaliar = v51.preparar(b, f, dec)[0]
        e1, e2 = item_de(avaliar, a["era1"]), item_de(avaliar, a["era2"])
        arestas = [e for e in v51.relacoes_contextuais(avaliar) if {e["a"], e["b"]} == {e1["id"], e2["id"]}]

        def estado(decl):
            regs = {e1["id"]: registro(e1, existe="incerto"), e2["id"]: registro(e2, existe="sim", estado="revisao_recomendada",
                                                                              relacoes=[{**decl, "com": e1["id"]}])}
            return v51.consistencia(avaliar, regs, arestas)["pares"][0]
        self.assertEqual((estado(completa)["estado"], estado(completa)["verificacao"]), ("diferenca_declarada", "formal"))
        autentica = {**completa, "trecho": "Ela era", "trecho_autentico": True}
        self.assertEqual(estado(autentica)["verificacao"], "formal_com_trecho_autentico")
        self.assertEqual(estado(sem_prop)["estado"], "diferenca_nao_articulada")
        self.assertNotIn("justificada", json.dumps(estado(completa)))


class ConsistenciaTests(unittest.TestCase):
    def setUp(self):
        self.b, self.f, self.dec, self.a = cenario(com_construcao=False)
        self.avaliar = v51.preparar(self.b, self.f, self.dec)[0]
        self.arestas = v51.relacoes_contextuais(self.avaliar)
        self.i = {k: item_de(self.avaliar, x) for k, x in self.a.items()}

    def par(self, regs, x, y):
        rel = v51.consistencia(self.avaliar, regs, self.arestas)
        ids = {self.i[x]["id"], self.i[y]["id"]}
        return next(p for p in rel["pares"] if {p["a"], p["b"]} == ids)

    def test_equal_fields_are_aligned_without_claiming_correctness(self):
        regs = {self.i[k]["id"]: registro(self.i[k]) for k in ("era1", "era2")}
        p = self.par(regs, "era1", "era2")
        self.assertEqual((p["estado"], p["atencao"]), ("classificacoes_alinhadas", False))
        self.assertNotIn("coerente", json.dumps(p))
        self.assertEqual(p["campos_comparados"], ["existe", "natureza", "certeza"])

    def test_unarticulated_difference_only_draws_attention_when_existence_differs(self):
        regs = {self.i["era1"]["id"]: registro(self.i["era1"], existe="incerto"),
                self.i["era2"]["id"]: registro(self.i["era2"], existe="sim"),
                self.i["cruzavam"]["id"]: registro(self.i["cruzavam"], existe="sim", certeza="clara")}
        existe = self.par(regs, "era1", "era2")
        self.assertEqual((existe["estado"], existe["grau"], existe["atencao"]), ("diferenca_nao_articulada", "existe", True))
        menor = self.par(regs, "era2", "cruzavam")
        self.assertEqual((menor["estado"], menor["grau"], menor["atencao"]), ("diferenca_nao_articulada", "classificacao", False))

    def test_neighbour_without_verdict_is_not_a_dependency(self):
        regs = {self.i["era1"]["id"]: registro(self.i["era1"])}
        rel = v51.consistencia(self.avaliar, regs, self.arestas)
        self.assertEqual(self.par(regs, "era1", "era2")["estado"], "comparacao_indisponivel")
        self.assertEqual(rel["dependencias"], [])
        self.assertEqual(rel["atencao"], [])
        self.assertFalse(any(k.startswith("dependencia") for k in rel["resumo"]))

    def test_declared_dependencies_are_structural_states(self):
        e1, e2, tr = self.i["era1"], self.i["era2"], self.i["cruzavam"]
        base = {e2["id"]: registro(e2, relacoes=[declaracao(e1["id"], "depende_de", motivo="a leitura de um sustenta o outro")])}

        def dep(regs):
            return v51.consistencia(self.avaliar, regs, self.arestas)["dependencias"][0]
        self.assertEqual(dep(base)["estado"], "dependencia_nao_analisada")              # B sem veredito válido
        self.assertTrue(dep(base)["atencao"])
        self.assertEqual(dep({**base, e1["id"]: registro(e1)})["estado"], "dependencia_declarada")
        self.assertEqual(dep({**base, e1["id"]: registro(e1, estado="inconclusiva")})["estado"], "dependencia_condicional")
        velho = registro(e1)
        velho["chave_conteudo"] = "outra"
        self.assertEqual(dep({**base, e1["id"]: velho})["estado"], "dependencia_nao_analisada")
        fora = [i for i in self.avaliar if i["id"] != e1["id"]]
        self.assertEqual(v51.consistencia(fora, base, self.arestas)["dependencias"][0]["estado"], "dependencia_nao_analisada")
        self.assertEqual(tr["id"] in base, False)

    def test_cycles_are_circular_dependency_not_contradiction(self):
        e1, e2, tr = self.i["era1"], self.i["era2"], self.i["cruzavam"]
        d = lambda para: declaracao(para["id"], "depende_de", motivo="a leitura de um sustenta o outro")
        dupla = {e1["id"]: registro(e1, relacoes=[d(e2)]), e2["id"]: registro(e2, relacoes=[d(e1)])}
        rel = v51.consistencia(self.avaliar, dupla, self.arestas)
        self.assertEqual({x["estado"] for x in rel["dependencias"]}, {"dependencia_circular"})
        self.assertNotIn("contradicao_declarada", rel["resumo"])
        tripla = {e1["id"]: registro(e1, relacoes=[d(e2)]), e2["id"]: registro(e2, relacoes=[d(tr)]),
                  tr["id"]: registro(tr, relacoes=[d(e1)])}
        rel = v51.consistencia(self.avaliar, tripla, self.arestas)
        self.assertEqual([x["estado"] for x in rel["dependencias"]], ["dependencia_circular"] * 3)
        aberta = {e1["id"]: registro(e1, relacoes=[d(e2)]), e2["id"]: registro(e2)}
        self.assertEqual(v51.consistencia(self.avaliar, aberta, self.arestas)["dependencias"][0]["estado"],
                         "dependencia_declarada")

    def test_declared_contradiction_is_reserved_for_incompatible_statements(self):
        e1, e2 = self.i["era1"], self.i["era2"]
        mesma = declaracao(e2["id"], "mesma_questao", "correlação de tempos", "mesmo critério em ambos os casos")
        dif = declaracao(e1["id"], "diferenca", "função da forma", "casos de natureza distinta no período")
        regs = {e1["id"]: registro(e1, relacoes=[mesma]), e2["id"]: registro(e2, relacoes=[dif])}
        self.assertEqual(self.par(regs, "era1", "era2")["estado"], "contradicao_declarada")
        regs = {e1["id"]: registro(e1, existe="sim", relacoes=[mesma]), e2["id"]: registro(e2, existe="nao")}
        self.assertEqual(self.par(regs, "era1", "era2")["estado"], "contradicao_declarada")
        regs = {e1["id"]: registro(e1, existe="incerto", relacoes=[mesma]), e2["id"]: registro(e2, existe="sim")}
        self.assertEqual(self.par(regs, "era1", "era2")["estado"], "diferenca_nao_articulada")

    def test_consistency_never_changes_records_decisions_or_priority(self):
        e1, e2 = self.i["era1"], self.i["era2"]
        regs = {e1["id"]: registro(e1, existe="incerto"), e2["id"]: registro(e2, existe="sim", estado="revisao_recomendada")}
        regs[e2["id"]]["prioridade_revisao"] = "baixa"
        antes = json.dumps(regs, sort_keys=True)
        decs = json.dumps(self.dec, sort_keys=True)
        v51.consistencia(self.avaliar, regs, self.arestas)
        self.assertEqual(json.dumps(regs, sort_keys=True), antes)
        self.assertEqual(json.dumps(self.dec, sort_keys=True), decs)


class PersistenciaTests(unittest.TestCase):
    def setUp(self):
        self.b, self.f, self.dec, self.a = cenario()

    def test_v5_state_is_neither_read_nor_rewritten(self):
        t = T5.Transporte(fn=T5.por_entrada())
        with TemporaryDirectory() as pasta:
            v5.avaliar(self.b, self.f, self.dec, pasta=pasta, teto=5.0, transporte=t)
            antes = (Path(pasta) / v5.ARQUIVO).read_bytes()
            plano = v51.planejar(self.b, self.f, self.dec, pasta)
            self.assertEqual(plano["situacoes"], {"nova": len(self.f)})
            self.assertEqual(plano["reutilizadas"], 0)
            _, _, resumo, _ = rodar(self.b, self.f, self.dec, pasta)
            self.assertEqual(resumo["reutilizadas_sem_custo"], 0)
            self.assertEqual((Path(pasta) / v5.ARQUIVO).read_bytes(), antes)
            self.assertNotEqual(v51.ARQUIVO, v5.ARQUIVO)
            self.assertNotEqual(v51.TRAVA, v5.TRAVA)

    def test_reuse_without_calls_and_selective_invalidation(self):
        with TemporaryDirectory() as pasta:
            _, _, r1, c1 = rodar(self.b, self.f, self.dec, pasta)
            self.assertEqual(r1["analisadas_agora"], len(self.f))
            _, _, r2, c2 = rodar(self.b, self.f, self.dec, pasta)
            self.assertEqual((r2["reutilizadas_sem_custo"], c2.pedidos), (len(self.f), []))
            # parágrafo vizinho (dentro da janela de §19 e §20) muda
            b2 = livro({22: "Parágrafo diferente, agora sobre a chuva."})
            f2 = [T.alerta(b2, x["paragraph"] if "paragraph" in x else 0, "x") for x in []]
            plano = v51.planejar(b2, self.f, self.dec, pasta)
            nome = {self.a[k]["id"]: k for k in self.a}
            invalidos = {nome[i] for i, s in plano["itens"].items() if s["situacao"] == "desatualizada_conteudo"}
            self.assertEqual(invalidos, {"prendeu", "era19", "cruzavam", "era1", "era2", "foi"})
            validos = {nome[i] for i, s in plano["itens"].items() if s["situacao"] == "valida"}
            self.assertEqual(validos, {"estava", "c30", "c50", "c60"})
            # decisão de um relacionado muda: só ele é invalidado
            dec = dict(self.dec)
            dec[self.a["era2"]["id"]] = "Intencional"
            plano = v51.planejar(self.b, self.f, dec, pasta)
            self.assertEqual({nome[i] for i, s in plano["itens"].items() if s["situacao"] != "valida"}, {"era2"})
            # veredito de um relacionado mudar também não invalida ninguém
            self.assertEqual(plano["reutilizadas"], len(self.f) - 1)

    def test_new_alert_in_the_paragraph_changes_only_that_paragraph_keys(self):
        with TemporaryDirectory() as pasta:
            rodar(self.b, self.f, self.dec, pasta)
            extra = T.alerta(self.b, 20, "ainda", "Tempo verbal")
            f2 = self.f + [extra]
            dec2 = {**self.dec, extra["id"]: "Estilo do autor"}
            plano = v51.planejar(self.b, f2, dec2, pasta)
            nome = {self.a[k]["id"]: k for k in self.a}
            nome[extra["id"]] = "ainda"
            self.assertEqual({nome[i] for i, s in plano["itens"].items() if s["situacao"] != "valida"},
                             {"cruzavam", "era1", "era2", "foi", "ainda"})
            self.assertEqual(plano["itens"][self.a["prendeu"]["id"]]["situacao"], "valida")

    def test_configuration_and_prompt_changes_invalidate_without_reprocessing(self):
        with TemporaryDirectory() as pasta:
            rodar(self.b, self.f, self.dec, pasta)
            plano = v51.planejar(self.b, self.f, self.dec, pasta, esforco="high")
            self.assertEqual(plano["situacoes"], {"desatualizada_configuracao": len(self.f)})
            _, _, r, c = rodar(self.b, self.f, self.dec, pasta, esforco="high")
            self.assertEqual((r["analisadas_agora"], c.pedidos), (0, []))     # só revalida a pedido

    def test_state_has_no_paragraph_text_and_logs_have_no_key(self):
        with TemporaryDirectory() as pasta:
            rodar(self.b, self.f, self.dec, pasta)
            bruto = (Path(pasta) / v51.ARQUIVO).read_text(encoding="utf-8")
        for bloco in self.b:
            if len(bloco.text) > 40:
                self.assertNotIn(bloco.text, bruto)
        estado = json.loads(bruto)
        self.assertEqual(estado[v51.MARCA], 1)
        for r in estado["itens"].values():
            for rel in r["relacionados"]:
                self.assertEqual(set(rel), {"id", "tipo", "paragrafo", "inicio", "fim"})

    def test_decisions_manuscript_and_findings_are_untouched(self):
        antes = (json.dumps(self.dec, sort_keys=True), json.dumps(self.f, sort_keys=True),
                 [(x.number, x.text) for x in self.b])
        with TemporaryDirectory() as pasta:
            rodar(self.b, self.f, self.dec, pasta)
        self.assertEqual((json.dumps(self.dec, sort_keys=True), json.dumps(self.f, sort_keys=True),
                          [(x.number, x.text) for x in self.b]), antes)


class TravaTests(unittest.TestCase):
    def test_lock_is_exclusive_released_and_survives_failures(self):
        with TemporaryDirectory() as pasta:
            self.assertFalse(v51.ocupada(pasta))
            with v51.trava(pasta):
                self.assertTrue(v51.ocupada(pasta))
                with self.assertRaises(v4.ValidacaoEmAndamento):
                    with v51.trava(pasta):
                        pass
                b, f, dec, _ = cenario(com_construcao=False)
                with self.assertRaises(v4.ValidacaoEmAndamento):
                    rodar(b, f, dec, pasta)
            self.assertFalse(v51.ocupada(pasta))
            with self.assertRaises(RuntimeError):
                with v51.trava(pasta):
                    raise RuntimeError("falha")
            self.assertFalse(v51.ocupada(pasta))                   # a trava caiu com a exceção
            with v51.trava(pasta):                                 # e a V5 não é bloqueada pela V5.1
                with v5.trava(pasta):
                    pass

    def test_interrupted_run_leaves_no_processing_record_and_stale_ones_count_as_new(self):
        b, f, dec, a = cenario(com_construcao=False)

        class Quebra(Cliente):
            def json(self, *args, **kw):
                raise KeyboardInterrupt
        with TemporaryDirectory() as pasta:
            with self.assertRaises(KeyboardInterrupt):
                rodar(b, f, dec, pasta, Quebra())
            estado = json.loads((Path(pasta) / v51.ARQUIVO).read_text(encoding="utf-8"))
            self.assertEqual(estado["itens"], {})
            avaliar = v51.preparar(b, f, dec)[0]
            v51.gravar(pasta, {avaliar[0]["id"]: {"id": avaliar[0]["id"], "estado_validacao": "em_processamento"}})
            plano = v51.planejar(b, f, dec, pasta)                  # processo morto: sem trava ativa
            self.assertEqual(plano["itens"][avaliar[0]["id"]]["situacao"], "nova")

    def test_unreadable_state_is_reported_and_not_trusted(self):
        with TemporaryDirectory() as pasta:
            (Path(pasta) / v51.ARQUIVO).write_text("{ não é json", encoding="utf-8")
            itens, aviso = v51.ler(pasta)
            self.assertEqual(itens, {})
            self.assertIn("V5.1", aviso)
            (Path(pasta) / v51.ARQUIVO).write_text(json.dumps({"v5": 1, "itens": {"x": {}}}), encoding="utf-8")
            self.assertEqual(v51.ler(pasta)[0], {})                # formato da V5 não é lido como V5.1


class ContratoTests(unittest.TestCase):
    def test_editorial_contract_is_the_v4_1_one_plus_relations_and_v4_1_v5_are_untouched(self):
        self.assertIn("Cada item é independente.", v41.SISTEMA)
        self.assertIs(v5.SISTEMA, v41.SISTEMA)
        self.assertNotIn("Cada item é independente.", v51.SISTEMA)
        self.assertIn("NÃO obriga o mesmo resultado", v51.SISTEMA)
        sem = v51.SISTEMA.replace(v51._BLOCO_RELACOES, "").replace("Cada item é julgado por si.", v51._LINHA_ANTIGA)
        self.assertEqual(sem, v41.SISTEMA)
        propriedades = v51.ESQUEMA["properties"]["avaliacoes"]["items"]
        self.assertEqual(set(propriedades["required"]), set(propriedades["properties"]))
        self.assertIn("relacoes", propriedades["required"])
        self.assertFalse(propriedades["properties"]["relacoes"]["items"]["additionalProperties"])
        self.assertNotIn("relacoes", v5.ESQUEMA["properties"]["avaliacoes"]["items"]["properties"])
        self.assertEqual(v51.configuracao()["relacoes"], 1)
        self.assertNotEqual(v51.configuracao()["prompt_sha256"], v5.configuracao()["prompt_sha256"])

    def test_request_follows_the_responses_contract_with_the_strict_relations_schema(self):
        b, f, dec, a = cenario(com_construcao=False)
        t = T5.Transporte(fn=lambda corpo: T5.resposta({"avaliacoes": [
            {**T.base(i, corpo["input"]), "relacoes": []} for i in T.ids_do(corpo["input"])]}))
        with TemporaryDirectory() as pasta:
            v51.avaliar(b, f, dec, pasta=pasta, teto=5.0, transporte=t)
        corpo = next(c[2] for c in t.chamadas if c[0] == "POST")
        self.assertEqual(corpo["instructions"], v51.SISTEMA)
        self.assertFalse(corpo["store"])
        self.assertTrue(corpo["text"]["format"]["strict"])
        self.assertEqual(corpo["text"]["format"]["schema"], v51.ESQUEMA)
        tudo = json.dumps(corpo, ensure_ascii=False)
        for proibido in ("Sonnet", "Opus", "Claude", "veredito de", "V5 ", "validacoes-v5"):
            self.assertNotIn(proibido, tudo, proibido)

    def test_second_round_of_context_keeps_the_relations_block(self):
        b, f, dec, a = cenario(com_construcao=False)
        pedidos = []

        class Pede(Cliente):
            def json(self, sistema, usuario, esquema, etapa, max_saida=None):
                pedidos.append(usuario)
                r = super().json(sistema, usuario, esquema, etapa, max_saida)
                if "única ampliação" not in usuario:
                    for e in r["avaliacoes"]:
                        if e["id"] == a["era1"]["id"]:
                            e.update(precisa_mais_contexto=True, paragrafos_solicitados=[40])
                return r
        with TemporaryDirectory() as pasta:
            _, _, resumo, c = rodar(b, f, dec, pasta, Pede(), teto=5.0)
        segundo = [p for p in pedidos[1:] if "Esta é a única ampliação" in p]
        self.assertTrue(segundo)
        self.assertIn(f"[RELACOES ITEM {a['era1']['id']}]", segundo[0])


class EstimativaTests(unittest.TestCase):
    def test_components_are_separate_and_scenarios_are_not_guarantees(self):
        b, f, dec, a = cenario()
        e = v51.estimar(b, f, dec)
        comp = e["custo_por_componente_usd"]
        self.assertEqual(set(comp), {"entrada_nao_cacheada", "cache_prompt_fixo", "saida_visivel"})
        self.assertIn("raciocinio_usd_por_cenario", e)
        total0 = e["custo_total_usd_por_cenario"]["0"]
        self.assertAlmostEqual(total0, sum(comp.values()), places=3)
        cen = list(e["custo_total_usd_por_cenario"].values())
        self.assertEqual(cen, sorted(cen))
        self.assertLessEqual(cen[-1], e["custo_maximo_primeira_rodada_usd"])
        self.assertGreater(e["teto_minimo_usd"], e["pior_pedido_usd"])
        self.assertEqual(e["chamadas_primeira_rodada"], len(e["limite_de_saida_por_pedido"]))
        self.assertTrue(any("raciocínio por item não medido" in p for p in e["premissas"]))
        self.assertNotIn("%", json.dumps(e))

    def test_local_comparison_with_v5_needs_no_state_or_network(self):
        b, f, dec, a = cenario()
        c = v51.comparar_com_v5(b, f, dec)
        self.assertEqual(c["itens"], len(f))
        self.assertGreater(len(c["v5"]["paragrafos_divididos"]), 0)
        self.assertEqual(c["v5_1"]["paragrafos_divididos"], [])
        self.assertEqual(sorted(x for l in c["v5_1"]["composicao"] for x in l), sorted(x for l in c["v5"]["composicao"] for x in l))
        self.assertGreaterEqual(c["v5_1"]["tokens_saida_visivel_esperados"], c["v5"]["tokens_saida_visivel_esperados"])
        self.assertEqual(c["arestas"]["mesma_construcao"], 1)

    def test_ceiling_splits_groups_by_cost_and_reports_when_even_one_item_does_not_fit(self):
        b, f, dec, a = cenario()
        livre = v51.estimar(b, f, dec)
        metade = v51.estimar(b, f, dec, teto=livre["pior_pedido_usd"] / 2)
        self.assertGreater(metade["chamadas_primeira_rodada"], livre["chamadas_primeira_rodada"])
        self.assertTrue(metade["cabe_no_teto"])
        self.assertTrue(all(x <= livre["pior_pedido_usd"] / 2 for x in metade["pior_caso_por_pedido_usd"]))
        self.assertTrue(any(d["motivo"] == "excede_orcamento" for d in metade["divisoes"]))
        minimo = v51.estimar(b, f, dec, teto=0.001)
        self.assertFalse(minimo["cabe_no_teto"])


if __name__ == "__main__":
    unittest.main()
