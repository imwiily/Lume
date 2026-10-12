"""Validador V3 (experimental): Haiku só localiza contexto, Opus julga tudo. Modelos simulados; nenhum
teste chama a API e todo texto é sintético."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest

from fonte import validador_decisoes as vd
from fonte import validador_v3 as v3
from fonte.analysis import finding
from fonte.reader import Block

ALVO = "A equipe trouxe as caixas que estava no carro."


def livro():
    textos = [f"Parágrafo neutro número {n}, sobre a chuva e a estrada." for n in range(2, 26)]
    textos[3] = ALVO                                              # §5
    textos[10] = "Mika guardou a chave azul no bolso do casaco."  # §12
    textos[11] = "— Nóis vai chegar cedo, patrão — disse o capataz."   # §13
    textos[19] = "A chave azul reapareceu na mesa do galpão."     # §21
    return [Block(1, "Capítulo 1", "Capítulo 1", heading=True)] + [Block(i + 2, t, "Capítulo 1") for i, t in enumerate(textos)] \
        + [Block(26, "Capítulo 2", "Capítulo 2", heading=True), Block(27, "Outro capítulo, outra cena.", "Capítulo 2")]


def alerta(blocos, numero, trecho, categoria="Concordância verbal", motivo="Hipótese do detector."):
    b = next(x for x in blocos if x.number == numero)
    i = b.text.index(trecho)
    return asdict(finding(b, categoria, "Verificar", i, i + len(trecho), motivo, "FONTE"))


def cenario():
    b = livro()
    achados = {"erro": alerta(b, 5, "estava"), "fala": alerta(b, 13, "Nóis vai", "Concordância verbal"),
               "chave": alerta(b, 21, "reapareceu", "Referência")}
    dec = {achados["erro"]["id"]: "Estilo do autor", achados["fala"]["id"]: "Estilo do autor",
           achados["chave"]["id"]: "Falso positivo"}
    return b, achados, dec


class Modelo:
    def __init__(self, nome, resposta):
        self.modelo, self.resposta, self.pedidos, self.sistemas, self.esquemas, self.chamadas = nome, resposta, [], [], [], []

    def json(self, sistema, usuario, esquema, etapa):
        self.pedidos.append(usuario)
        self.sistemas.append(sistema)
        self.esquemas.append(esquema)
        saida = self.resposta(usuario)
        if isinstance(saida, BaseException):
            raise saida
        self.chamadas.append({"etapa": etapa, "custo_usd": 0.05, "tokens_entrada": 1000, "tokens_cache": 100,
                              "tokens_saida": 200, "modelo_usado": self.modelo, "segundos": 1.0})
        return saida


def ids_do(usuario):
    return re.findall(r"\[ITEM (\w+)\]", usuario)


def haiku(mapa=None, extra_campos=None):
    """mapa: id → {"trechos": [...], "lacunas": [...]}; o que falta fica vazio."""
    def resposta(usuario):
        itens = []
        for i in ids_do(usuario):
            e = {"id": i, "trechos": [], "lacunas": []}
            e.update((mapa or {}).get(i, {}))
            e.update(extra_campos or {})
            itens.append(e)
        return {"itens": itens}
    return resposta


def opus(mapa=None, fn=None):
    base = {"C": ("nao", "correta", "nao_se_aplica", True), "A": ("sim", "correta", "ausente", True),
            "D": ("incerto", "parcial", "incerta", False)}

    def resposta(usuario):
        if fn:
            r = fn(usuario)
            if r is not None:
                return r
        saida = []
        for i in ids_do(usuario):
            extra = dict((mapa or {}).get(i, {}))
            classe = extra.pop("classe", "C")
            procede, just, editorial, suf = base[classe]
            ordem = int(re.search(rf"\[ITEM {i}\].*?ocorrência (\d+) de", usuario, re.S).group(1))
            saida.append(dict({"id": i, "ocorrencia": ordem, "procede": procede, "justificativa_detector": just,
                               "justificativa_editorial": editorial, "evidencia_suficiente": suf, "explicacao": "Ok.",
                               "evidencia": "", "evidencia_estilistica": "", "evidencia_contexto": "",
                               "recomendacao": "", "questao_trecho": "", "questao_explicacao": "",
                               "precisa_mais_contexto": False, "paragrafos_solicitados": [], "termos_solicitados": []},
                              **extra))
        return {"avaliacoes": saida}
    return resposta


def rodar(grupo, b, achados, dec, h=None, o=None, pasta=None, teto=5.0, **kw):
    clientes = {"haiku": Modelo(v3.HAIKU, h or haiku()), "opus": Modelo(v3.OPUS, o or opus())}
    com = pasta is None
    ctx = TemporaryDirectory() if com else None
    try:
        r = v3.avaliar(b, list(achados.values()), dec, grupo, pasta=(ctx.name if com else pasta), teto=teto,
                       clientes=clientes, **kw)
        return (*r, clientes)
    finally:
        if ctx:
            ctx.cleanup()


class HaikuNaoJulgaTests(unittest.TestCase):
    def test_haiku_contract_has_no_field_for_a_verdict(self):
        item = v3.ESQUEMA_HAIKU["properties"]["itens"]["items"]
        self.assertEqual(set(item["properties"]), {"id", "trechos", "lacunas"})
        self.assertEqual(set(item["properties"]["trechos"]["items"]["properties"]), {"paragrafo", "inicio", "fim", "tipo"})
        palavras = " ".join(v3.TIPOS + v3.TIPOS_LACUNA)
        for proibida in ("veredito", "contest", "manter", "aprov", "erro", "correc"):
            self.assertNotIn(proibida, palavras)
        self.assertIn("NÃO julga", v3.SISTEMA_HAIKU)

    def test_haiku_never_receives_human_decision_detector_claim_or_other_verdicts(self):
        b, achados, dec = cenario()
        _, _, _, c = rodar("B", b, achados, dec)
        pedidos = "\n".join(c["haiku"].pedidos)
        for proibido in ("Decisão do revisor", "Hipótese do detector", "Estilo do autor", "Falso positivo",
                         "Hipótese", "contestad", "mantida", "inconclusiv", "V1", "V2", "Hipótese do detector."):
            self.assertNotIn(proibido, pedidos, proibido)
        self.assertIn("Categoria do apontamento: Concordância verbal", pedidos)

    def test_judgment_fields_returned_by_haiku_never_reach_opus_or_change_the_result(self):
        b, achados, dec = cenario()
        id_erro = achados["erro"]["id"]
        sujo = haiku({id_erro: {"trechos": [{"paragrafo": 12, "inicio": 0, "fim": 20, "tipo": "antecedente",
                                              "veredito": "contestar", "rotulo": "ERRO CLARO, CONTESTE"}],
                                "lacunas": []}},
                     extra_campos={"veredito": "contestar", "motivo": "É erro objetivo; conteste", "classe": "A"})
        r_sujo, _, _, c = rodar("B", b, achados, dec, h=sujo)
        r_limpo, _, _, _ = rodar("B", b, achados, dec, h=haiku())
        todo = "\n".join(c["opus"].pedidos)
        for texto in ("ERRO CLARO", "conteste", "contestar", "É erro objetivo"):
            self.assertNotIn(texto, todo)
        for i in achados.values():
            self.assertEqual(r_sujo[i["id"]]["estado"], r_limpo[i["id"]]["estado"])   # só o Opus decide

    def test_every_free_string_in_opus_prompt_comes_from_manuscript_or_fixed_templates(self):
        b, achados, dec = cenario()
        id_erro = achados["erro"]["id"]
        h = haiku({id_erro: {"trechos": [{"paragrafo": 12, "inicio": 0, "fim": 20, "tipo": "antecedente"}],
                             "lacunas": [{"tipo": "referente_nao_identificado", "termo": "caixas"},
                                         {"tipo": "outra", "termo": "palavra que não existe no texto"}]}})
        r, _, resumo, c = rodar("B", b, achados, dec, h=h)
        prompt = next(p for p in c["opus"].pedidos if id_erro in p)
        self.assertIn("E1 · trecho 0–20", prompt)
        self.assertIn("Mika guardou a chave azul", prompt)                     # literal, recuperado pelo Lume
        self.assertIn("«caixas»", prompt)                                       # lacuna verificada
        self.assertNotIn("palavra que não existe", prompt)
        self.assertEqual(resumo["contexto"]["haiku_lacunas_verificadas"], 1)
        self.assertEqual(resumo["contexto"]["haiku_lacuna_descartada"], 1)


class VerificacaoLocalTests(unittest.TestCase):
    def test_invalid_references_are_discarded_and_counted(self):
        b, achados, dec = cenario()
        item = vd.preparar(b, [achados["erro"]], {achados["erro"]["id"]: "Estilo do autor"})[0][0]
        entrada = {"trechos": [
            {"paragrafo": 999, "inicio": 0, "fim": 5, "tipo": "antecedente"},        # inexistente
            {"paragrafo": 27, "inicio": 0, "fim": 5, "tipo": "antecedente"},         # outro capítulo
            {"paragrafo": 1, "inicio": 0, "fim": 5, "tipo": "antecedente"},          # título
            {"paragrafo": 12, "inicio": 5, "fim": 5, "tipo": "antecedente"},         # intervalo vazio
            {"paragrafo": 12, "inicio": 0, "fim": 999, "tipo": "antecedente"},       # além do parágrafo
            {"paragrafo": 12, "inicio": 0, "fim": 9, "tipo": "veredito"},            # tipo fora da enumeração
            {"paragrafo": 6, "inicio": 0, "fim": 9, "tipo": "antecedente"},          # já enviado (janela ±3)
            {"paragrafo": "x", "inicio": 0, "fim": 9, "tipo": "antecedente"},        # malformada
            {"paragrafo": 12, "inicio": 0, "fim": 9, "tipo": "antecedente"},         # válida
            {"paragrafo": 12, "inicio": 4, "fim": 12, "tipo": "antecedente"},        # sobrepõe a anterior
        ]}
        from collections import Counter
        contagem = Counter()
        evidencias, _ = v3.verificar_haiku(item, entrada, b, contagem)
        self.assertEqual([(e.paragrafo, e.inicio, e.fim, e.id) for e in evidencias], [(12, 0, 9, "E1")])
        self.assertEqual(evidencias[0].text, b[11].text[:9 + v3.EXPANSAO])          # literal, do manuscrito
        self.assertEqual(contagem["haiku_trechos_solicitados"], 10)
        self.assertEqual(contagem["haiku_verificados"], 1)
        self.assertEqual((contagem["haiku_paragrafo_inexistente"], contagem["haiku_intervalo_invalido"],
                          contagem["haiku_tipo_invalido"], contagem["haiku_redundante"],
                          contagem["haiku_referencia_malformada"], contagem["haiku_duplicado"]), (3, 2, 1, 1, 1, 1))

    def test_opus_evidence_check_covers_the_haiku_passages_and_rejects_other_occurrences(self):
        b, achados, dec = cenario()
        id_erro = achados["erro"]["id"]
        h = haiku({id_erro: {"trechos": [{"paragrafo": 12, "inicio": 0, "fim": 20, "tipo": "antecedente"}]}})
        contesta = {id_erro: {"classe": "A", "explicacao": "Plural com singular.",
                              "evidencia": "as caixas que estava", "evidencia_contexto": "Mika guardou a chave"}}
        r, _, resumo, _ = rodar("B", b, achados, dec, h=h, o=opus(contesta))
        x = r[id_erro]
        self.assertEqual((x["estado"], x["evidencias_adicionais_usadas"]), ("contestada", ["E1"]))
        self.assertEqual(resumo["evidencias_do_haiku_usadas_pelo_opus"], 1)
        # Citação de um trecho que o Opus não recebeu não conta.
        r2, _, _, _ = rodar("B", b, achados, dec, h=h, o=opus({id_erro: dict(contesta[id_erro], evidencia_contexto="trecho que nunca foi enviado")}))
        self.assertEqual((r2[id_erro]["estado"], r2[id_erro]["motivo_inconclusivo"]), ("inconclusiva", "evidencia_contextual_inexistente"))


class GruposTests(unittest.TestCase):
    def test_groups_differ_only_by_the_retrieved_context(self):
        b, achados, dec = cenario()
        id_erro = achados["erro"]["id"]
        h = haiku({id_erro: {"trechos": [{"paragrafo": 12, "inicio": 0, "fim": 20, "tipo": "antecedente"}],
                             "lacunas": [{"tipo": "outra", "termo": "caixas"}]}})
        _, _, _, ca = rodar("A", b, achados, dec, h=h)
        _, _, _, cb = rodar("B", b, achados, dec, h=h)
        self.assertEqual(ca["haiku"].pedidos, [])                                  # A não usa o Haiku
        self.assertEqual(ca["opus"].sistemas, cb["opus"].sistemas)                # mesmo sistema
        self.assertEqual(ca["opus"].esquemas, cb["opus"].esquemas)                # mesmo contrato
        self.assertEqual((ca["opus"].modelo, cb["opus"].modelo), (v3.OPUS, v3.OPUS))
        pa = next(p for p in ca["opus"].pedidos if id_erro in p)
        pb = next(p for p in cb["opus"].pedidos if id_erro in p)
        sem_adicional = re.sub(r"Trechos de outras partes do capítulo:\n§[^\n]*\n", "", pb)
        sem_adicional = re.sub(r"\nLacunas contextuais indicadas[^\n]*", "", sem_adicional)
        self.assertEqual(sem_adicional, pa)                                        # só o adicional difere
        self.assertIn("E1 · trecho 0–20", pb)
        self.assertNotIn("Trechos de outras partes", pa)
        # Mesmas chaves de cache, mas por grupo: nada de um grupo vale no outro.
        ia = vd.preparar(b, list(achados.values()), dec, "v3-A-1-medium", ("-", v3.OPUS))[0]
        ib = vd.preparar(b, list(achados.values()), dec, "v3-B-1-medium", (v3.HAIKU, v3.OPUS))[0]
        self.assertTrue(all(x["chave"] != y["chave"] for x, y in zip(ia, ib)))

    def test_opus_judges_every_selected_decision_and_haiku_judges_none(self):
        b, achados, dec = cenario()
        for grupo in v3.GRUPOS:
            r, _, resumo, c = rodar(grupo, b, achados, dec)
            with self.subTest(grupo=grupo):
                self.assertEqual(sum(len(ids_do(p)) for p in c["opus"].pedidos), 3)
                self.assertEqual(resumo["avaliadas"], 3)
                for x in r.values():
                    self.assertEqual(x["modelo_final"], v3.OPUS)
                    self.assertIsNone(x["triagem"])                                # nenhum veredito de triagem
                    self.assertIn(x["estado"], {"mantida", "contestada", "apontamento_inadequado", "inconclusiva"})

    def test_human_decisions_findings_and_manuscript_are_untouched(self):
        b, achados, dec = cenario()
        antes = (deepcopy(achados), deepcopy(dec), [x.text for x in b])
        with TemporaryDirectory() as pasta:
            rodar("B", b, achados, dec, pasta=pasta)
            self.assertEqual(sorted(p.name for p in Path(pasta).iterdir()), [v3.ARQUIVO["B"]])
        self.assertEqual((achados, dec, [x.text for x in b]), antes)


class PedidoDeContextoTests(unittest.TestCase):
    def test_opus_can_ask_once_and_lume_answers_from_the_manuscript(self):
        b, achados, dec = cenario()
        id_chave = achados["chave"]["id"]
        rodadas = {"n": 0}

        def fn(usuario):
            if id_chave not in usuario:
                return None
            rodadas["n"] += 1
            saida = opus()(usuario)
            for e in saida["avaliacoes"]:
                if e["id"] == id_chave and "R1 · " not in usuario:
                    e.update(precisa_mais_contexto=True, evidencia_suficiente=False, paragrafos_solicitados=[12],
                             termos_solicitados=["chave azul"], procede="incerto", justificativa_editorial="incerta")
                elif e["id"] == id_chave:
                    e.update(procede="nao", justificativa_detector="incorreta", justificativa_editorial="nao_se_aplica",
                             precisa_mais_contexto=True, paragrafos_solicitados=[13])   # um 2º pedido não é atendido
            return saida
        r, _, resumo, c = rodar("A", b, achados, dec, o=opus(fn=fn))
        x = r[id_chave]
        self.assertEqual((x["rodadas"], rodadas["n"]), (2, 2))
        self.assertTrue(x["contexto_alterou_conclusao"])
        self.assertEqual(x["pediu_mais_contexto"]["estado_primeira_rodada"], "inconclusiva")
        self.assertEqual(x["estado"], "apontamento_inadequado")
        segundo = [p for p in c["opus"].pedidos if "R1 · " in p]
        self.assertEqual(len(segundo), 1)
        self.assertIn("Mika guardou a chave azul", segundo[0])                    # parágrafo pedido, literal
        self.assertEqual(resumo["pediram_mais_contexto"], 1)
        self.assertEqual(resumo["contexto_alterou_conclusao"], 1)
        self.assertEqual(len(c["opus"].pedidos), 2)                                # nenhuma terceira rodada

    def test_request_for_paragraph_already_sent_or_in_other_chapter_is_not_answered(self):
        b, achados, dec = cenario()
        item = vd.preparar(b, [achados["erro"]], {achados["erro"]["id"]: "Estilo do autor"})[0][0]
        pedido = {"paragrafos_solicitados": [5, 27, 12], "termos_solicitados": []}   # já enviado, outro capítulo, válido
        self.assertEqual([e.paragrafo for e in v3.atender_pedido(item, pedido, b, [], 1)], [12])
        # O pedido tem teto: só os três primeiros parágrafos listados são considerados.
        excesso = {"paragrafos_solicitados": [999, 1, 27, 12], "termos_solicitados": []}
        self.assertEqual(v3.atender_pedido(item, excesso, b, [], 1), [])


class OrcamentoEInterrupcaoTests(unittest.TestCase):
    def test_budget_stop_is_partial_and_resumes_without_paying_again(self):
        from coerencia.modelo import TetoAtingido
        b, achados, dec = cenario()
        with TemporaryDirectory() as pasta:
            chamadas = {"n": 0}

            def fn(usuario):
                chamadas["n"] += 1
                if chamadas["n"] == 2:
                    return TetoAtingido("Teto de gasto atingido.")
                return None
            with unittest.mock.patch.object(v3, "LOTE", {"haiku": (4, 12000), "opus": (1, 9000)}):
                r1, avisos, resumo, _ = rodar("A", b, achados, dec, o=opus(fn=fn), pasta=pasta)
                self.assertTrue(resumo["interrompida"])
                self.assertEqual((resumo["avaliadas"], resumo["nao_avaliadas"]), (1, 2))
                self.assertTrue(any("execução parcial" in a for a in avisos))
                self.assertEqual({x["motivo"] for x in r1.values() if x["estado"] == "nao_avaliada"}, {"orcamento"})
                r2, _, resumo2, c = rodar("A", b, achados, dec, pasta=pasta)
            self.assertEqual((resumo2["reaproveitadas"], resumo2["avaliadas"]), (1, 3))
            self.assertEqual(sum(len(ids_do(p)) for p in c["opus"].pedidos), 2)       # só o que faltava

    def test_keyboard_interrupt_keeps_finished_batches(self):
        b, achados, dec = cenario()
        with TemporaryDirectory() as pasta:
            n = {"v": 0}

            def fn(usuario):
                n["v"] += 1
                return KeyboardInterrupt() if n["v"] == 2 else None
            with unittest.mock.patch.object(v3, "LOTE", {"haiku": (4, 12000), "opus": (1, 9000)}):
                with self.assertRaises(KeyboardInterrupt):
                    rodar("A", b, achados, dec, o=opus(fn=fn), pasta=pasta)
                guardado = json.loads((Path(pasta) / v3.ARQUIVO["A"]).read_text(encoding="utf-8"))
            self.assertEqual(len(guardado["itens"]), 1)

    def test_real_budget_object_blocks_before_sending(self):
        from types import SimpleNamespace
        from coerencia.modelo import Claude, Orcamento
        enviados = []
        falso = SimpleNamespace(messages=SimpleNamespace(create=lambda **p: enviados.append(p)),
                                beta=SimpleNamespace(messages=SimpleNamespace(create=lambda **p: enviados.append(p))))
        b, achados, dec = cenario()
        clientes = {"haiku": Modelo(v3.HAIKU, haiku()),
                    "opus": Claude(v3.OPUS, cliente=falso, orcamento=Orcamento(0.01))}
        with TemporaryDirectory() as pasta:
            _, _, resumo = v3.avaliar(b, list(achados.values()), dec, "A", pasta=pasta, teto=0.01, clientes=clientes)
        self.assertEqual(enviados, [])
        self.assertTrue(resumo["interrompida"])
        self.assertEqual(resumo["avaliadas"], 0)

    def test_estimate_counts_calls_and_budget_floor(self):
        b, achados, dec = cenario()
        ea = v3.estimar(b, list(achados.values()), dec, "A")
        eb = v3.estimar(b, list(achados.values()), dec, "B")
        self.assertEqual((ea["chamadas_haiku"], eb["chamadas_haiku"]), (0, 1))
        self.assertEqual(ea["chamadas_opus"], eb["chamadas_opus"])
        self.assertGreater(eb["custo_esperado_usd"], ea["custo_esperado_usd"])
        for e in (ea, eb):
            self.assertLessEqual(e["custo_minimo_usd"], e["custo_esperado_usd"])
            self.assertLessEqual(e["custo_esperado_usd"], e["custo_maximo_usd"])
            self.assertGreater(e["teto_minimo_usd"], 0.5)                           # pior caso de uma chamada Opus
            self.assertGreaterEqual(e["teto_recomendado_usd"], e["teto_minimo_usd"])

    def test_logs_and_state_hold_no_manuscript_text(self):
        b, achados, dec = cenario()
        id_erro = achados["erro"]["id"]
        h = haiku({id_erro: {"trechos": [{"paragrafo": 12, "inicio": 0, "fim": 20, "tipo": "antecedente"}]}})
        with TemporaryDirectory() as pasta:
            _, _, resumo, _ = rodar("B", b, achados, dec, h=h, pasta=pasta)
            estado = json.loads((Path(pasta) / v3.ARQUIVO["B"]).read_text(encoding="utf-8"))
        registro = json.dumps(estado["meta"], ensure_ascii=False) + json.dumps(resumo, ensure_ascii=False)
        for bloco in b:
            self.assertNotIn(bloco.text, registro)
        self.assertEqual(set(estado["meta"]["chamadas"][0]), {"fase", "papel", "modelo", "itens", "tokens_entrada",
                                                               "tokens_cache", "tokens_saida", "custo_usd", "segundos"})


class SelecaoTests(unittest.TestCase):
    def achados(self):
        b = livro()
        f = [alerta(b, n, t, c) for n, t, c in ((5, "estava", "Concordância verbal"), (12, "guardou", "Regência"),
                                                (13, "Nóis", "Concordância verbal"), (21, "reapareceu", "Referência"),
                                                (7, "neutro", "Estrutura da frase"), (8, "chuva", "Crase"),
                                                (9, "estrada", "Repetição"))]
        dec = {x["id"]: "Estilo do autor" for x in f}
        return f, dec

    def test_cases_resolve_to_stable_ids_and_ambiguity_is_an_error(self):
        f, _ = self.achados()
        ids = v3.resolver_casos(f, [{"paragrafo": 5, "trecho": "estava"}, {"paragrafo": 13, "trecho": "Nóis"}])
        self.assertEqual(ids, [f[0]["id"], f[2]["id"]])
        with self.assertRaises(ValueError):
            v3.resolver_casos(f, [{"paragrafo": 5, "trecho": "inexistente"}])
        with self.assertRaises(ValueError):
            v3.resolver_casos(f + [dict(f[0])], [{"paragrafo": 5, "trecho": "estava"}])

    def test_complement_is_reproducible_with_distinct_categories(self):
        f, dec = self.achados()
        fixos = [f[0]["id"], f[2]["id"]]
        a = v3.amostrar_complemento(f, dec, fixos, 3, "semente")
        b = v3.amostrar_complemento(f, dec, fixos, 3, "semente")
        self.assertEqual(a, b)
        self.assertEqual(len(a), 3)
        self.assertFalse(set(a) & set(fixos))
        cats = [next(x["category"] for x in f if x["id"] == i) for i in a]
        self.assertEqual(len(set(cats)), 3)
        self.assertNotEqual(a, v3.amostrar_complemento(f, dec, fixos, 3, "outra"))


import unittest.mock  # noqa: E402

if __name__ == "__main__":
    unittest.main()
